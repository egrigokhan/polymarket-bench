"""GatewayService — the tool surface agents see (PLAN §8), paper mode.

place_order pipeline: idempotency → eligibility → snapshot book → risk envelope →
deterministic fill → atomic ledger write. Once accepted, the order completes
independently of the caller (PLAN §10 ledger invariant).
"""

import json
import time

from . import clients, paper, rules
from .config import DEFAULT, SeasonConfig
from .ledger import Ledger


class Gateway:
    def __init__(self, ledger: Ledger, cfg: SeasonConfig = DEFAULT,
                 execution: str = "pmt", pmt_root=None):
        """execution: "pmt" (polymarket-paper-trader backend, default) or "internal"
        (the original home-rolled snapshot-walk engine, kept for tests/fallback)."""
        self.ledger = ledger
        self.cfg = cfg
        self.session_start: dict[str, float] = {}  # agent_id -> session open ts
        self.execution = execution
        if execution == "pmt":
            from pathlib import Path
            from .pmt_backend import PmtBackend
            import os
            default_root = os.environ.get(
                "PMB_PMT_ROOT",
                str(Path(__file__).resolve().parent.parent / "pmt-accounts"))
            self.pmt = PmtBackend(Path(pmt_root) if pmt_root else Path(default_root))

    # ------------------------------------------------------------ sessions
    def open_session(self, agent_id: str) -> None:
        self.session_start[agent_id] = time.time()

    # ------------------------------------------------------------ discovery
    def search_markets(self, limit: int = 20) -> list[dict]:
        """Eligible markets only, sorted by 24h volume."""
        out = []
        for m in clients.list_markets(limit=150):
            ok, _ = rules.check_eligibility(m, self.cfg)
            if not ok:
                continue
            out.append(self._market_summary(m))
            if len(out) >= limit:
                break
        return out

    def get_market(self, condition_id: str) -> dict:
        m = clients.get_market_by_condition(condition_id)
        if not m:
            raise KeyError(f"unknown market {condition_id}")
        ok, why = rules.check_eligibility(m, self.cfg)
        detail = self._market_summary(m)
        detail["eligible"] = ok
        detail["eligibility_note"] = why
        detail["resolution_rules"] = m.get("description")
        token_ids = clients.clob_token_ids(m)
        if token_ids:
            book = clients.get_book(token_ids[0])
            # Sorted best-first (raw CLOB arrays are not reliably ordered)
            asks = sorted(book.get("asks", []), key=lambda l: float(l["price"]))
            bids = sorted(book.get("bids", []), key=lambda l: float(l["price"]), reverse=True)
            detail["book_outcome0"] = {"bids": bids[:5], "asks": asks[:5]}
        return detail

    @staticmethod
    def _market_summary(m: dict) -> dict:
        prices = m.get("outcomePrices")
        if isinstance(prices, str):
            prices = json.loads(prices)
        outcomes = m.get("outcomes")
        if isinstance(outcomes, str):
            outcomes = json.loads(outcomes)
        return {
            "condition_id": m["conditionId"],
            "question": m.get("question"),
            "slug": m.get("slug"),
            "outcomes": outcomes,
            "prices": prices,
            "end_date": m.get("endDate"),
            "liquidity": float(m.get("liquidity") or 0),
            "volume_24h": float(m.get("volume24hr") or 0),
            "neg_risk": m.get("negRisk", False),
            "token_ids": clients.clob_token_ids(m),
        }

    # ------------------------------------------------------------ portfolio
    def get_portfolio(self, agent_id: str) -> dict:
        agent = self.ledger.agent(agent_id)
        positions = []
        pos_value = 0.0
        for p in self.ledger.positions(agent_id):
            current_mid = clients.get_midpoint(p["token_id"])
            value = (current_mid or 0) * p["shares"]
            pos_value += value
            positions.append({
                "question": p["question"],
                "outcome": p["outcome"],
                "shares": round(p["shares"], 4),
                "cost_basis": round(p["cost_basis"], 2),
                "current_mid": current_mid,
                "value": round(value, 2),
                "unrealized_pnl": round(value - p["cost_basis"], 2),
                "end_date": p["end_date"],
            })
        return {
            "agent": agent["title"],
            "cash": round(agent["balance"], 2),
            "positions_value": round(pos_value, 2),
            "equity": round(agent["balance"] + pos_value, 2),
            "positions": positions,
        }

    # ------------------------------------------------------------ forecast card
    @staticmethod
    def current_epoch() -> str:
        """Panel epoch: one per wake-up anchor. UTC hours <14 → am (08:00 anchor),
        else pm (20:00 anchor)."""
        now = time.gmtime()
        half = "am" if now.tm_hour < 14 else "pm"
        return f"{now.tm_year:04d}-{now.tm_mon:02d}-{now.tm_mday:02d}-{half}"

    def ensure_panel(self, size: int = 10) -> list[dict]:
        """Deterministic shared panel for the current epoch: seeded sample of the most
        liquid eligible markets — identical for every agent (PLAN §8: panel Brier is
        the only absolute cross-agent forecasting metric)."""
        epoch = self.current_epoch()
        row = self.ledger.db.execute(
            "SELECT markets FROM forecast_panels WHERE epoch_id=?", (epoch,)).fetchone()
        if row:
            return json.loads(row["markets"])
        import random
        candidates = self.search_markets(limit=40)
        rnd = random.Random(f"pmb-panel:{epoch}")
        picks = rnd.sample(candidates, min(size, len(candidates)))
        panel = [{"condition_id": m["condition_id"], "question": m["question"],
                  "end_date": m["end_date"]} for m in picks]
        self.ledger.db.execute(
            "INSERT OR IGNORE INTO forecast_panels VALUES (?,?,?)",
            (epoch, json.dumps(panel), time.time()))
        self.ledger.db.commit()
        return panel

    def get_forecast_card(self, agent_id: str) -> dict:
        epoch = self.current_epoch()
        panel = self.ensure_panel()
        done = {r["condition_id"] for r in self.ledger.db.execute(
            "SELECT condition_id FROM forecast_cards WHERE agent_id=? AND epoch_id=?",
            (agent_id, epoch))}
        return {"epoch": epoch, "submitted": len(done) >= len(panel),
                "markets": panel,
                "instructions": "Submit your probability that outcome[0] (YES) occurs, "
                                "for every market, via submit_forecast_card. Trading "
                                "unlocks for this session once submitted."}

    def submit_forecast_card(self, agent_id: str, probabilities: dict) -> dict:
        epoch = self.current_epoch()
        panel = self.ensure_panel()
        # Tolerant key parsing: some models (observed: gemini-2.5-pro) serialize dict
        # keys with stray surrounding quotes ("'0xabc'" instead of "0xabc").
        probabilities = {
            str(k).strip().strip("'\"").lower(): v for k, v in probabilities.items()
        }
        panel = [dict(m, condition_id=m["condition_id"].lower()) for m in panel]
        missing = [m["condition_id"] for m in panel
                   if m["condition_id"] not in probabilities]
        if missing:
            return {"status": "rejected",
                    "reason": f"missing probabilities for {len(missing)} panel markets",
                    "missing": missing[:3]}
        for m in panel:
            p = float(probabilities[m["condition_id"]])
            if not (0.0 < p < 1.0):
                return {"status": "rejected",
                        "reason": f"probability {p} out of (0,1) for {m['condition_id'][:12]}"}
        for m in panel:
            mkt = clients.get_market_by_condition(m["condition_id"]) or {}
            tokens = clients.clob_token_ids(mkt)
            mid = clients.get_midpoint(tokens[0]) if tokens else None
            self.ledger.db.execute(
                "INSERT OR REPLACE INTO forecast_cards VALUES (?,?,?,?,?,?)",
                (agent_id, epoch, m["condition_id"],
                 float(probabilities[m["condition_id"]]), mid, time.time()))
        self.ledger.db.commit()
        return {"status": "accepted", "epoch": epoch, "count": len(panel),
                "note": "trading unlocked for this session"}

    def _card_submitted(self, agent_id: str) -> bool:
        epoch = self.current_epoch()
        row = self.ledger.db.execute(
            "SELECT COUNT(*) c FROM forecast_panels WHERE epoch_id=?", (epoch,)).fetchone()
        if row["c"] == 0:
            return True  # no panel this epoch → no gate
        n = self.ledger.db.execute(
            "SELECT COUNT(*) c FROM forecast_cards WHERE agent_id=? AND epoch_id=?",
            (agent_id, epoch)).fetchone()["c"]
        return n > 0

    # ------------------------------------------------------------ housekeeping
    def process_housekeeping(self, agent_id: str) -> dict:
        """Cron hook (pmt mode): fill due GTC/GTD orders, resolve closed markets into
        cash, then sync the bench ledger's cash and positions from the authoritative
        pm-trader account."""
        if self.execution != "pmt":
            return {"note": "housekeeping is a pmt-mode feature"}
        # Migration guard: if the ledger shows open positions but the pmt account has
        # no trade history, this agent predates the pmt backend — syncing would wipe
        # real state. Refuse and flag instead.
        pmt_db = self.pmt.root / agent_id / "paper.db"
        if self.ledger.positions(agent_id):
            import sqlite3 as _sq
            n_trades = 0
            if pmt_db.exists():
                c = _sq.connect(pmt_db)
                n_trades = c.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
                c.close()
            if n_trades == 0:
                return {"note": f"SKIPPED {agent_id}: ledger has positions but pmt "
                                "account is empty — needs migration first",
                        "limit_fills": [], "resolutions": [],
                        "cash_after": self.ledger.agent(agent_id)["balance"]}
        out = self.pmt.process(agent_id, self.cfg.starting_balance)
        self.ledger.db.execute("UPDATE agents SET balance=? WHERE agent_id=?",
                               (out["cash_after"], agent_id))
        # Reconcile: drop ledger position rows no longer open in the pmt account
        import sqlite3 as _sq
        pdb = _sq.connect(self.pmt.root / agent_id / "paper.db")
        open_keys = {(r[0], (r[1] or "").lower()) for r in pdb.execute(
            "SELECT market_condition_id, outcome FROM positions "
            "WHERE is_resolved=0 AND shares > 1e-9")}
        pdb.close()
        for p in self.ledger.positions(agent_id):
            if (p["condition_id"], (p["outcome"] or "").lower()) not in open_keys:
                self.ledger.db.execute(
                    "DELETE FROM positions WHERE agent_id=? AND token_id=?",
                    (agent_id, p["token_id"]))
        self.ledger.db.commit()
        return out

    # ------------------------------------------------------------ trading
    def place_order(
        self,
        agent_id: str,
        *,
        client_order_id: str,
        condition_id: str,
        outcome_index: int,
        side: str = "BUY",
        notional: float | None = None,
        shares: float | None = None,
        thesis: str | None = None,
        probability: float | None = None,
        confidence: float | None = None,
        invalidation: str | None = None,
        horizon_note: str | None = None,
    ) -> dict:
        # Idempotency (review C13): same client_order_id replays the original result.
        prior = self.ledger.find_order_by_client_id(agent_id, client_order_id)
        if prior:
            return {
                "status": prior["status"],
                "order_id": prior["order_id"],
                "note": "duplicate client_order_id — replaying original result",
                "reject_reason": prior["reject_reason"],
            }

        if side == "BUY" and not self._card_submitted(agent_id):
            return self._reject(
                agent_id, client_order_id, condition_id, "?", side, notional, shares,
                "forecast card for this epoch not yet submitted — call "
                "get_forecast_card, submit your probabilities, then trade "
                "(exits are always allowed)", locals())

        market = clients.get_market_by_condition(condition_id)
        if not market:
            return self._reject(agent_id, client_order_id, condition_id, "?", side,
                                notional, shares, "unknown market", locals())

        token_ids = clients.clob_token_ids(market)
        token_id = token_ids[outcome_index]
        is_exit = side == "SELL"

        ok, why = rules.check_eligibility(market, self.cfg)
        if not ok and not is_exit:
            return self._reject(agent_id, client_order_id, condition_id, token_id, side,
                                notional, shares, f"ineligible market: {why}", locals())

        # Pre-trade snapshot (required ledger fields, review C1)
        book = clients.get_book(token_id)
        pre_mid = paper.mid(book)
        best_ask = paper.best_price(book, "BUY")
        best_bid = paper.best_price(book, "SELL")
        depth = paper.top3_depth_usd(book, side)
        fee_rate = self.cfg.fee_rate_fallback  # TODO(live): getClobMarketInfo per order
        breakeven = None
        if best_ask is not None:
            breakeven = best_ask + fee_rate * best_ask * (1 - best_ask)

        agent = self.ledger.agent(agent_id)
        equity = agent["balance"]  # spike: cash-only equity for the event cap
        eff_notional = notional if notional is not None else (shares or 0) * (best_bid or 0)

        session_start = self.session_start.get(agent_id, time.time() - 1)
        ok, why = rules.check_order(
            agent_id=agent_id, market=market, token_ids=token_ids,
            token_index=outcome_index, side=side, notional=eff_notional,
            probability=probability, thesis=thesis, invalidation=invalidation,
            best_ask=best_ask, pre_mid=pre_mid, top3_depth=depth, fee_rate=fee_rate,
            equity=equity, session_start=session_start, is_exit=is_exit,
            ledger=self.ledger, cfg=self.cfg,
        )
        if not ok:
            return self._reject(agent_id, client_order_id, condition_id, token_id, side,
                                notional, shares, why, locals(), book=book,
                                pre_mid=pre_mid, best_bid=best_bid, best_ask=best_ask,
                                depth=depth, breakeven=breakeven)

        if side == "BUY" and (notional or 0) > agent["balance"]:
            return self._reject(agent_id, client_order_id, condition_id, token_id, side,
                                notional, shares, "insufficient cash", locals(), book=book,
                                pre_mid=pre_mid, best_bid=best_bid, best_ask=best_ask,
                                depth=depth, breakeven=breakeven)

        outcomes = market.get("outcomes")
        if isinstance(outcomes, str):
            outcomes = json.loads(outcomes)
        outcome_name = outcomes[outcome_index] if outcomes else str(outcome_index)

        if self.execution == "pmt":
            from .pmt_backend import EXEC_ERRORS
            try:
                pf = self.pmt.execute(
                    agent_id, condition_id=condition_id, outcome=outcome_name,
                    side=side, notional=notional, shares=shares,
                    starting_balance=self.cfg.starting_balance,
                )
            except EXEC_ERRORS as e:
                return self._reject(agent_id, client_order_id, condition_id, token_id,
                                    side, notional, shares, str(e), locals(), book=book,
                                    pre_mid=pre_mid, best_bid=best_bid, best_ask=best_ask,
                                    depth=depth, breakeven=breakeven)

            class _F:  # normalize to the internal fill shape
                shares = pf["shares"]; avg_price = pf["avg_price"]
                notional = pf["notional"]; fee = pf["fee"]
            fill = _F()
        else:
            try:
                fill = paper.simulate_marketable(
                    book, side, notional=notional, shares=shares, fee_rate=fee_rate
                )
            except paper.FillError as e:
                return self._reject(agent_id, client_order_id, condition_id, token_id, side,
                                    notional, shares, str(e), locals(), book=book,
                                    pre_mid=pre_mid, best_bid=best_bid, best_ask=best_ask,
                                    depth=depth, breakeven=breakeven)

        # Atomic-ish ledger write (single sqlite connection)
        order_id = self.ledger.record_order(
            client_order_id=client_order_id, agent_id=agent_id,
            condition_id=condition_id, token_id=token_id,
            market_question=market.get("question"), side=side, order_type="FOK",
            size_usd=notional, size_shares=shares, status="filled",
            thesis=thesis, probability=probability, confidence=confidence,
            invalidation=invalidation, horizon_note=horizon_note,
            pre_mid=pre_mid, pre_best_bid=best_bid, pre_best_ask=best_ask,
            pre_top3_depth=depth, fee_breakeven=breakeven, book_snapshot=book,
        )
        self.ledger.record_fill(order_id, agent_id, condition_id, token_id, side,
                                fill.shares, fill.avg_price, fill.fee)
        sign = 1 if side == "BUY" else -1
        self.ledger.upsert_position(
            agent_id, condition_id, token_id, market.get("question", "?"), outcome_name,
            sign * fill.shares, sign * (fill.notional + fill.fee), market.get("endDate"),
        )
        if self.execution == "pmt":
            # pm-trader account cash is authoritative; mirror it into the ledger
            self.ledger.db.execute("UPDATE agents SET balance=? WHERE agent_id=?",
                                   (pf["cash_after"], agent_id))
            self.ledger.db.commit()
        else:
            self.ledger.adjust_balance(
                agent_id, -(fill.notional + fill.fee) if side == "BUY"
                else fill.notional - fill.fee)
        return {
            "status": "filled",
            "order_id": order_id,
            "shares": round(fill.shares, 4),
            "avg_price": round(fill.avg_price, 4),
            "notional": round(fill.notional, 2),
            "fee": round(fill.fee, 4),
            "pre_trade_mid": pre_mid,
            "mode": "paper",
        }

    def _reject(self, agent_id, client_order_id, condition_id, token_id, side,
                notional, shares, reason, _ctx, book=None, pre_mid=None,
                best_bid=None, best_ask=None, depth=None, breakeven=None) -> dict:
        order_id = self.ledger.record_order(
            client_order_id=client_order_id, agent_id=agent_id,
            condition_id=condition_id, token_id=token_id, market_question=None,
            side=side, order_type="FOK", size_usd=notional, size_shares=shares,
            status="rejected", reject_reason=reason,
            pre_mid=pre_mid, pre_best_bid=best_bid, pre_best_ask=best_ask,
            pre_top3_depth=depth, fee_breakeven=breakeven, book_snapshot=book,
        )
        return {"status": "rejected", "order_id": order_id, "reject_reason": reason}

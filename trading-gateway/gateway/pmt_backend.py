"""Execution backend on polymarket-paper-trader (github.com/agent-next, MIT).

Replaces the home-rolled fill engine for paper mode: level-by-level fills against live
books, live per-token fee rates, GTC/GTD limit orders with tape fills, and market
resolution → realized cash. One isolated pm-trader Engine (own SQLite dir) per
benchmark agent. The gateway keeps eligibility, the risk envelope, trade metadata, and
the bench ledger; this module only executes.
"""

from pathlib import Path

from pm_trader.engine import (
    Engine,
    OrderRejectedError,
    InsufficientBalanceError,
    MarketClosedError,
    InvalidOutcomeError,
    NoPositionError,
)

EXEC_ERRORS = (
    OrderRejectedError, InsufficientBalanceError, MarketClosedError,
    InvalidOutcomeError, NoPositionError,
)

# --- Upstream fix (pm-trader 0.1.6): Gamma's /markets lookups OMIT closed markets
# unless closed=true is passed, so resolve_market() dies with "Market not found" on
# exactly the markets it needs to resolve. Wrap get_market with a closed=true retry.
from pm_trader.api import PolymarketClient, _parse_market  # noqa: E402

_orig_get_market = PolymarketClient.get_market


def _get_market_closed_aware(self, slug_or_id):
    try:
        return _orig_get_market(self, slug_or_id)
    except Exception:
        for params in ({"slug": slug_or_id, "closed": "true"},
                       {"condition_ids": slug_or_id, "closed": "true"}):
            data = self._gamma_get("/markets", params=params)
            if isinstance(data, list) and data:
                self._set_cached(f"market:{slug_or_id}", data[0])
                return _parse_market(data[0])
        raise


PolymarketClient.get_market = _get_market_closed_aware


class PmtBackend:
    def __init__(self, root: Path):
        self.root = Path(root)
        self._engines: dict[str, Engine] = {}

    def engine(self, agent_id: str, starting_balance: float = 100.0) -> Engine:
        e = self._engines.get(agent_id)
        if e is None:
            d = self.root / agent_id
            d.mkdir(parents=True, exist_ok=True)
            e = Engine(d)
            try:
                e.get_account()
            except Exception:
                e.init_account(starting_balance)
            self._engines[agent_id] = e
        return e

    def execute(self, agent_id: str, *, condition_id: str, outcome: str, side: str,
                notional: float | None, shares: float | None,
                starting_balance: float) -> dict:
        """Run a marketable order. Returns a normalized fill dict or raises EXEC_ERRORS."""
        e = self.engine(agent_id, starting_balance)
        if side == "BUY":
            res = e.buy(condition_id, outcome, notional or 0.0)
        else:
            res = e.sell(condition_id, outcome, shares or 0.0)
        t = res.trade
        return {
            "shares": t.shares,
            "avg_price": t.avg_price,
            "notional": t.amount_usd if side == "BUY" else t.shares * t.avg_price,
            "fee": t.fee,
            "fee_rate_bps": t.fee_rate_bps,
            "slippage_bps": t.slippage,
            "levels_used": t.levels_filled,
            "cash_after": res.account.cash,
            "market_question": t.market_question,
            "market_slug": t.market_slug,
        }

    def portfolio(self, agent_id: str, starting_balance: float) -> dict:
        e = self.engine(agent_id, starting_balance)
        account = e.get_account()
        positions = e.get_portfolio()  # live prices included
        return {"cash": account.cash, "positions": positions}

    def process(self, agent_id: str, starting_balance: float) -> dict:
        """Housekeeping cron: fill due limit orders, resolve closed markets."""
        e = self.engine(agent_id, starting_balance)
        filled = e.check_orders()
        resolved = [r.__dict__ if hasattr(r, "__dict__") else r for r in e.resolve_all()]
        return {"limit_fills": filled, "resolutions": resolved,
                "cash_after": e.get_account().cash}

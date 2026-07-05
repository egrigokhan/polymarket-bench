"""Bench ledger — SQLite for the spike; schema written so a Postgres swap is mechanical.

Canonical store per PLAN §10: agents, orders (with required pre-trade snapshot fields),
fills, positions, forecast cards, equity snapshots. Every simulated fill persists the raw
book snapshot it walked (hash-commitment lands in Phase 1).
"""

import json
import sqlite3
import time
import uuid
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
    agent_id      TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    model         TEXT,
    harness       TEXT,
    balance       REAL NOT NULL,
    created_at    REAL NOT NULL,
    is_demo       INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS orders (
    order_id          TEXT PRIMARY KEY,
    client_order_id   TEXT NOT NULL,
    agent_id          TEXT NOT NULL REFERENCES agents(agent_id),
    condition_id      TEXT NOT NULL,
    token_id          TEXT NOT NULL,
    market_question   TEXT,
    side              TEXT NOT NULL,          -- BUY | SELL
    order_type        TEXT NOT NULL,          -- FOK | FAK (spike: marketable only)
    size_usd          REAL,                   -- BUY notional
    size_shares       REAL,                   -- SELL shares
    status            TEXT NOT NULL,          -- filled | rejected
    reject_reason     TEXT,
    -- required trade metadata (PLAN §7)
    thesis            TEXT,
    probability       REAL,
    confidence        REAL,
    invalidation      TEXT,
    horizon_note      TEXT,
    -- required pre-trade snapshot fields (PLAN §10 / review C1)
    pre_mid           REAL,
    pre_best_bid      REAL,
    pre_best_ask      REAL,
    pre_top3_depth    REAL,
    fee_breakeven     REAL,
    book_snapshot     TEXT,                   -- raw /book JSON
    created_at        REAL NOT NULL,
    UNIQUE(agent_id, client_order_id)
);
CREATE TABLE IF NOT EXISTS fills (
    fill_id       TEXT PRIMARY KEY,
    order_id      TEXT NOT NULL REFERENCES orders(order_id),
    agent_id      TEXT NOT NULL,
    condition_id  TEXT NOT NULL,
    token_id      TEXT NOT NULL,
    side          TEXT NOT NULL,
    shares        REAL NOT NULL,
    avg_price     REAL NOT NULL,
    notional      REAL NOT NULL,
    fee           REAL NOT NULL,
    mode          TEXT NOT NULL DEFAULT 'paper',
    created_at    REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS positions (
    agent_id      TEXT NOT NULL,
    condition_id  TEXT NOT NULL,
    token_id      TEXT NOT NULL,
    question      TEXT,
    outcome       TEXT,
    shares        REAL NOT NULL,
    cost_basis    REAL NOT NULL,              -- total $ paid incl. fees
    end_date      TEXT,
    PRIMARY KEY (agent_id, token_id)
);
CREATE TABLE IF NOT EXISTS forecast_cards (
    agent_id      TEXT NOT NULL,
    epoch_id      TEXT NOT NULL,          -- e.g. 2026-07-04-am
    condition_id  TEXT NOT NULL,
    probability   REAL NOT NULL,          -- agent's P(outcome0 = YES)
    market_mid    REAL,                   -- mid at submission (paired scoring anchor)
    created_at    REAL NOT NULL,
    PRIMARY KEY (agent_id, epoch_id, condition_id)
);
CREATE TABLE IF NOT EXISTS forecast_panels (
    epoch_id      TEXT PRIMARY KEY,
    markets       TEXT NOT NULL,          -- JSON [{condition_id, question, end_date}]
    created_at    REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_events (
    event_id      TEXT PRIMARY KEY,
    agent_id      TEXT NOT NULL,
    task_id       TEXT NOT NULL,
    ts            TEXT,
    type          TEXT,
    data          TEXT,               -- raw event data JSON
    sealed        INTEGER NOT NULL DEFAULT 0,
    created_at    REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_agent ON agent_events(agent_id, created_at);
CREATE TABLE IF NOT EXISTS equity_snapshots (
    agent_id      TEXT NOT NULL,
    equity        REAL NOT NULL,
    cash          REAL NOT NULL,
    positions_val REAL NOT NULL,
    created_at    REAL NOT NULL
);
"""


class Ledger:
    def __init__(self, path: str | Path = "bench.db"):
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    # ------------------------------------------------------------ agents
    def create_agent(self, title: str, model: str, harness: str, balance: float) -> str:
        agent_id = f"agent_{uuid.uuid4().hex[:8]}"
        self.db.execute(
            "INSERT INTO agents (agent_id, title, model, harness, balance, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (agent_id, title, model, harness, balance, time.time()),
        )
        self.db.commit()
        return agent_id

    def agent(self, agent_id: str) -> sqlite3.Row:
        row = self.db.execute("SELECT * FROM agents WHERE agent_id=?", (agent_id,)).fetchone()
        if not row:
            raise KeyError(f"unknown agent {agent_id}")
        return row

    def adjust_balance(self, agent_id: str, delta: float) -> None:
        self.db.execute(
            "UPDATE agents SET balance = balance + ? WHERE agent_id=?", (delta, agent_id)
        )
        self.db.commit()

    # ------------------------------------------------------------ idempotency
    def find_order_by_client_id(self, agent_id: str, client_order_id: str) -> sqlite3.Row | None:
        return self.db.execute(
            "SELECT * FROM orders WHERE agent_id=? AND client_order_id=?",
            (agent_id, client_order_id),
        ).fetchone()

    # ------------------------------------------------------------ orders / fills
    def record_order(self, **kw) -> str:
        order_id = f"ord_{uuid.uuid4().hex[:10]}"
        kw.setdefault("book_snapshot", None)
        self.db.execute(
            """INSERT INTO orders (order_id, client_order_id, agent_id, condition_id,
               token_id, market_question, side, order_type, size_usd, size_shares, status,
               reject_reason, thesis, probability, confidence, invalidation, horizon_note,
               pre_mid, pre_best_bid, pre_best_ask, pre_top3_depth, fee_breakeven,
               book_snapshot, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                order_id, kw["client_order_id"], kw["agent_id"], kw["condition_id"],
                kw["token_id"], kw.get("market_question"), kw["side"], kw["order_type"],
                kw.get("size_usd"), kw.get("size_shares"), kw["status"],
                kw.get("reject_reason"), kw.get("thesis"), kw.get("probability"),
                kw.get("confidence"), kw.get("invalidation"), kw.get("horizon_note"),
                kw.get("pre_mid"), kw.get("pre_best_bid"), kw.get("pre_best_ask"),
                kw.get("pre_top3_depth"), kw.get("fee_breakeven"),
                json.dumps(kw["book_snapshot"]) if kw.get("book_snapshot") else None,
                time.time(),
            ),
        )
        self.db.commit()
        return order_id

    def record_fill(self, order_id: str, agent_id: str, condition_id: str, token_id: str,
                    side: str, shares: float, avg_price: float, fee: float) -> str:
        fill_id = f"fill_{uuid.uuid4().hex[:10]}"
        notional = shares * avg_price
        self.db.execute(
            "INSERT INTO fills (fill_id, order_id, agent_id, condition_id, token_id, side,"
            " shares, avg_price, notional, fee, mode, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,'paper',?)",
            (fill_id, order_id, agent_id, condition_id, token_id, side,
             shares, avg_price, notional, fee, time.time()),
        )
        self.db.commit()
        return fill_id

    # ------------------------------------------------------------ positions
    def upsert_position(self, agent_id: str, condition_id: str, token_id: str,
                        question: str, outcome: str, d_shares: float, d_cost: float,
                        end_date: str | None) -> None:
        row = self.db.execute(
            "SELECT shares, cost_basis FROM positions WHERE agent_id=? AND token_id=?",
            (agent_id, token_id),
        ).fetchone()
        if row:
            shares, cost = row["shares"] + d_shares, row["cost_basis"] + d_cost
            if shares <= 1e-9:
                self.db.execute(
                    "DELETE FROM positions WHERE agent_id=? AND token_id=?",
                    (agent_id, token_id),
                )
            else:
                self.db.execute(
                    "UPDATE positions SET shares=?, cost_basis=? WHERE agent_id=? AND token_id=?",
                    (shares, cost, agent_id, token_id),
                )
        else:
            self.db.execute(
                "INSERT INTO positions VALUES (?,?,?,?,?,?,?,?)",
                (agent_id, condition_id, token_id, question, outcome, d_shares, d_cost, end_date),
            )
        self.db.commit()

    def positions(self, agent_id: str) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM positions WHERE agent_id=?", (agent_id,)
        ).fetchall()

    # ------------------------------------------------------------ event mirror
    def upsert_event(self, event_id: str, agent_id: str, task_id: str,
                     ts: str | None, type_: str | None, data: str) -> bool:
        """Idempotent insert (at-least-once mirror). Returns True if new."""
        cur = self.db.execute(
            "INSERT OR IGNORE INTO agent_events "
            "(event_id, agent_id, task_id, ts, type, data, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (event_id, agent_id, task_id, ts, type_, data, time.time()),
        )
        self.db.commit()
        return cur.rowcount > 0

    def seal_task_events(self, task_id: str) -> None:
        self.db.execute("UPDATE agent_events SET sealed=1 WHERE task_id=?", (task_id,))
        self.db.commit()

    def recent_events(self, agent_id: str, limit: int = 40) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM agent_events WHERE agent_id=? "
            "ORDER BY created_at DESC, event_id DESC LIMIT ?",
            (agent_id, limit),
        ).fetchall()

    # ------------------------------------------------------------ lockout support
    def fleet_activity_on(self, condition_id: str, since: float) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT agent_id, token_id, side FROM orders "
            "WHERE condition_id=? AND status='filled' AND created_at>=?",
            (condition_id, since),
        ).fetchall()

    def orders_this_session(self, agent_id: str, since: float) -> int:
        return self.db.execute(
            "SELECT COUNT(*) c FROM orders WHERE agent_id=? AND created_at>=?",
            (agent_id, since),
        ).fetchone()["c"]

    def market_exposure(self, agent_id: str, condition_id: str) -> float:
        row = self.db.execute(
            "SELECT COALESCE(SUM(cost_basis),0) s FROM positions "
            "WHERE agent_id=? AND condition_id=?",
            (agent_id, condition_id),
        ).fetchone()
        return row["s"]

"""PolymarketBench trading gateway — MCP server (Phase 0, paper mode).

Exposes the PLAN §8 tool surface over MCP so a Brainbase agent (or Claude Code locally)
can trade paper against live Polymarket data.

Run (HTTP, for Brainbase `mcp_servers.url`):
    fastmcp run mcp_server.py --transport http --port 8940
Run (stdio, for local testing):
    python3 mcp_server.py

Auth note: the spike is single-tenant (AGENT_ID env var or auto-created). Multi-tenant
per-agent bearer tokens + session windows land with the orchestrator (PLAN §8).
"""

import os
import sys
import uuid
from contextvars import ContextVar
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastmcp import FastMCP

from gateway.config import DEFAULT
from gateway.ledger import Ledger
from gateway.service import Gateway

ledger = Ledger(Path(os.environ.get("PMB_DB", Path(__file__).parent / "bench.db")))
gw = Gateway(ledger, DEFAULT)

# Multi-tenant identity: serve_http's auth middleware maps bearer token → ledger agent
# id and sets this contextvar per request. Stdio/local fallback: PMB_AGENT_ID env.
CURRENT_AGENT: ContextVar[str] = ContextVar("pmb_agent", default="")
AGENT_ID = os.environ.get("PMB_AGENT_ID", "")


def _aid() -> str:
    aid = CURRENT_AGENT.get() or AGENT_ID
    if not aid:
        raise RuntimeError("no agent identity bound to this request")
    return aid

mcp = FastMCP(
    "polymarket-gateway",
    instructions=(
        "Trading gateway for PolymarketBench. You trade a paper portfolio against real "
        "Polymarket order books. All orders are marketable (FOK). Hard risk limits are "
        "enforced server-side — a rejection tells you why; treat it as information, not "
        "an error to retry blindly. Every exposure-increasing order requires an honest "
        "thesis, probability, and invalidation condition. SKIP (placing no orders) is "
        "always acceptable."
    ),
)


@mcp.tool()
def search_markets(limit: int = 20) -> list[dict]:
    """List eligible markets (liquidity/volume floors, resolves in-season, no sub-daily
    crypto), sorted by 24h volume. Prices are [outcome0, outcome1]."""
    return gw.search_markets(limit=limit)


@mcp.tool()
def get_market(condition_id: str) -> dict:
    """Full market detail: resolution rules text, top-5 order book for outcome 0,
    eligibility status, token ids."""
    return gw.get_market(condition_id)


@mcp.tool()
def get_portfolio() -> dict:
    """Your cash, open positions marked to current mids, and total equity."""
    return gw.get_portfolio(_aid())


@mcp.tool()
def get_forecast_card() -> dict:
    """This session's forecast panel: ~10 markets, identical for every benchmark agent.
    You must submit a probability for each (via submit_forecast_card) before BUY orders
    unlock. Your panel Brier score is public and on your scorecard."""
    return gw.get_forecast_card(_aid())


@mcp.tool()
def submit_forecast_card(probabilities: dict) -> dict:
    """Submit {condition_id: probability} for every market on this session's forecast
    card. probability = your honest P(outcome[0] / YES resolves true), in (0,1).
    Truthful probabilities maximize your public panel score (proper scoring rule)."""
    return gw.submit_forecast_card(_aid(), probabilities)


@mcp.tool()
def place_order(
    condition_id: str,
    outcome_index: int,
    side: str,
    notional_usd: float,
    thesis: str,
    probability: float,
    invalidation: str,
    confidence: float = 0.5,
    horizon_note: str = "",
    client_order_id: str = "",
) -> dict:
    """Place a marketable paper order.

    side: BUY (spend notional_usd) or SELL (reduce a position by ~notional_usd at bid).
    thesis: 1-3 sentences on why the price is wrong. probability: your own probability
    for the outcome you're trading (must imply positive fee-adjusted edge for BUYs).
    invalidation: what evidence would make you exit. Omit client_order_id to auto-generate;
    reuse one to safely retry (idempotent replay).
    """
    coid = client_order_id or f"mcp-{uuid.uuid4().hex[:10]}"
    if side == "SELL":
        # Spike convenience: convert notional to shares at current bid inside service
        # by passing shares derived from portfolio state.
        pf = gw.get_portfolio(_aid())
        pos = next((p for p in pf["positions"]
                    if p["question"] and p["current_mid"]), None)
        if pos is None:
            return {"status": "rejected", "reject_reason": "no position to sell"}
        shares = min(pos["shares"], notional_usd / max(pos["current_mid"], 1e-6))
        return gw.place_order(
            _aid(), client_order_id=coid, condition_id=condition_id,
            outcome_index=outcome_index, side="SELL", shares=shares,
            thesis=thesis, probability=probability, confidence=confidence,
            invalidation=invalidation, horizon_note=horizon_note,
        )
    return gw.place_order(
        _aid(), client_order_id=coid, condition_id=condition_id,
        outcome_index=outcome_index, side="BUY", notional=notional_usd,
        thesis=thesis, probability=probability, confidence=confidence,
        invalidation=invalidation, horizon_note=horizon_note,
    )


if __name__ == "__main__":
    mcp.run()

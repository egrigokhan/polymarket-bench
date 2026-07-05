"""Thin clients for Polymarket's public (no-auth) APIs: Gamma, CLOB, Data.

Read-only — order *placement* in live mode goes through py-clob-client-v2 + the
co-signer (Phase 3); the paper spike only needs public market data.
"""

import json
from typing import Any

import requests

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
DATA = "https://data-api.polymarket.com"

_session = requests.Session()
_session.headers["User-Agent"] = "polymarket-bench/0.1 (phase-0 spike)"


def _get(url: str, params: dict | None = None) -> Any:
    try:
        r = _session.get(url, params=params or {}, timeout=15)
    except requests.exceptions.ConnectionError:
        # Stale keep-alive socket after long idle (hourly housekeeping pattern):
        # drop pooled connections and retry once on a fresh one.
        _session.close()
        r = _session.get(url, params=params or {}, timeout=15)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------- Gamma (discovery)

def list_markets(limit: int = 100, offset: int = 0, order: str = "volume24hr") -> list[dict]:
    return _get(
        f"{GAMMA}/markets",
        {
            "active": "true",
            "closed": "false",
            "limit": limit,
            "offset": offset,
            "order": order,
            "ascending": "false",
        },
    )


def get_market_by_condition(condition_id: str) -> dict | None:
    res = _get(f"{GAMMA}/markets", {"condition_ids": condition_id})
    return res[0] if res else None


def clob_token_ids(market: dict) -> list[str]:
    """Gamma serialises clobTokenIds as a JSON string. First id = YES/outcome[0]."""
    raw = market.get("clobTokenIds") or "[]"
    return json.loads(raw) if isinstance(raw, str) else raw


# ---------------------------------------------------------------- CLOB (prices/books)

def get_book(token_id: str) -> dict:
    """Returns {'bids': [{'price','size'},...], 'asks': [...]} (price levels as strings)."""
    return _get(f"{CLOB}/book", {"token_id": token_id})


def get_midpoint(token_id: str) -> float | None:
    res = _get(f"{CLOB}/midpoint", {"token_id": token_id})
    mid = res.get("mid") if isinstance(res, dict) else None
    return float(mid) if mid is not None else None


def get_price_history(token_id: str, interval: str = "1d", fidelity: int = 60) -> list[dict]:
    res = _get(
        f"{CLOB}/prices-history",
        {"market": token_id, "interval": interval, "fidelity": fidelity},
    )
    return res.get("history", [])


# ---------------------------------------------------------------- Data API (audit layer)

def get_positions(wallet: str) -> list[dict]:
    return _get(f"{DATA}/positions", {"user": wallet})


def get_value(wallet: str) -> dict | list:
    return _get(f"{DATA}/value", {"user": wallet})

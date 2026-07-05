"""Season config. Values are PLAN.md §7 Season 0 numbers.

Everything an operator would tune lives here; the risk engine reads only from this.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class SeasonConfig:
    season_id: str = "s0"
    season_end: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=70)
    )

    # Eligibility (PLAN §7)
    min_hours_to_resolution: float = 6.0
    min_liquidity_usd: float = 2_000.0       # spike: trusts Gamma; wash-filtering is Phase 1
    min_volume_24h_usd: float = 5_000.0
    min_market_age_hours: float = 72.0
    excluded_slug_markers: tuple = (          # sub-daily crypto series
        "-5m-", "-15m-", "-hourly-", "-4h-",
        "updown-5m", "updown-15m", "updown-1h", "updown-4h",
    )

    # Per-order / per-agent limits (Season 0 tier)
    max_order_notional: float = 10.0
    min_order_notional: float = 2.0
    max_market_exposure: float = 15.0
    max_event_equity_frac: float = 0.25
    max_orders_per_session: int = 10
    max_book_depth_frac: float = 0.10         # ≤10% of top-3-level depth

    # Price band (PLAN §7 anti-manipulation): worst fill within K of reference mid
    price_band: float = 0.10

    # Self-dealing lockout window (fills/orders on same conditionId, opposing direction)
    lockout_hours: float = 24.0

    # Consistency check epsilon: prob >= breakeven - eps for exposure-increasing orders
    edge_epsilon: float = 0.02

    # Fee fallback by category tag when live fee-rate is unavailable (docs: dynamic —
    # production must query getClobMarketInfo per order; this map is the spike fallback).
    fee_rate_fallback: float = 0.04

    starting_balance: float = 100.0


DEFAULT = SeasonConfig()

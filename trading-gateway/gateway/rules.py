"""Eligibility + risk envelope (PLAN §7). Prompts are requests; this module is law.

Every check returns (ok, reason). Reasons are human-readable on purpose — rejections are
learning signal for the agents (PLAN §10).
"""

import time
from datetime import datetime, timezone

from .config import SeasonConfig
from .ledger import Ledger

# Direction algebra for the self-dealing lockout (review C7): the CLOB matches
# complementary orders ACROSS the YES/NO books via complete-set mint/merge, so the
# lockout is keyed on conditionId direction, not per book.
#   direction +1 = {BUY outcome0, SELL outcome1}, -1 = the reverse.


def direction(token_index: int, side: str) -> int:
    d = 1 if token_index == 0 else -1
    return d if side == "BUY" else -d


def parse_end_date(market: dict) -> datetime | None:
    raw = market.get("endDate")
    if not raw:
        return None
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def check_eligibility(market: dict, cfg: SeasonConfig) -> tuple[bool, str]:
    if market.get("closed") or not market.get("active", True):
        return False, "market is closed/inactive"

    end = parse_end_date(market)
    if end is None:
        return False, "market has no endDate"
    now = datetime.now(timezone.utc)
    hours_left = (end - now).total_seconds() / 3600
    if hours_left < cfg.min_hours_to_resolution:
        return False, (
            f"resolves in {hours_left:.1f}h < {cfg.min_hours_to_resolution}h floor "
            "(near-resolution/leakage window)"
        )
    if end > cfg.season_end:
        return False, "resolves after season end"

    slug = (market.get("slug") or "").lower()
    if any(m in slug for m in cfg.excluded_slug_markers):
        return False, "sub-daily crypto series are excluded this season"

    liq = float(market.get("liquidity") or 0)
    vol = float(market.get("volume24hr") or 0)
    if liq < cfg.min_liquidity_usd:
        return False, f"liquidity ${liq:,.0f} below floor"
    if vol < cfg.min_volume_24h_usd:
        return False, f"24h volume ${vol:,.0f} below floor"

    start = market.get("startDate")
    if start:
        age_h = (now - datetime.fromisoformat(start.replace("Z", "+00:00"))).total_seconds() / 3600
        if age_h < cfg.min_market_age_hours:
            return False, f"market only {age_h:.0f}h old (<{cfg.min_market_age_hours:.0f}h anti-honeypot floor)"

    # Augmented neg-risk placeholder outcomes (review M2)
    outcomes = market.get("outcomes") or ""
    if "TBD" in str(outcomes) or "Other candidate" in str(outcomes):
        return False, "placeholder outcome in augmented neg-risk event"

    return True, "eligible"


def check_order(
    *,
    agent_id: str,
    market: dict,
    token_ids: list[str],
    token_index: int,
    side: str,
    notional: float,
    probability: float | None,
    thesis: str | None,
    invalidation: str | None,
    best_ask: float | None,
    pre_mid: float | None,
    top3_depth: float,
    fee_rate: float,
    equity: float,
    session_start: float,
    is_exit: bool,
    ledger: Ledger,
    cfg: SeasonConfig,
) -> tuple[bool, str]:
    """The §7 per-order envelope. Returns (ok, reason)."""
    # Required metadata
    if not is_exit:
        if not thesis or probability is None or not invalidation:
            return False, "missing required trade metadata (thesis, probability, invalidation)"
        if not (0.0 < probability < 1.0):
            return False, "probability must be in (0,1)"

    # Size limits
    if notional < cfg.min_order_notional:
        return False, f"order ${notional:.2f} below ${cfg.min_order_notional} minimum"
    if notional > cfg.max_order_notional:
        return False, f"order ${notional:.2f} above ${cfg.max_order_notional} per-order cap"
    if notional > cfg.max_book_depth_frac * top3_depth:
        return False, (
            f"order ${notional:.2f} exceeds {cfg.max_book_depth_frac:.0%} of top-3 book "
            f"depth (${top3_depth:.2f}) — size down or pick a deeper market"
        )

    # Exposure limits
    condition_id = market["conditionId"]
    exposure = ledger.market_exposure(agent_id, condition_id)
    if not is_exit and exposure + notional > cfg.max_market_exposure:
        return False, (
            f"would take market exposure to ${exposure + notional:.2f} > "
            f"${cfg.max_market_exposure} cap"
        )
    if not is_exit and notional > cfg.max_event_equity_frac * equity:
        return False, f"order exceeds {cfg.max_event_equity_frac:.0%} of equity per event"

    # Session order-count cap
    if ledger.orders_this_session(agent_id, session_start) >= cfg.max_orders_per_session:
        return False, f"session order cap ({cfg.max_orders_per_session}) reached"

    # Price band vs reference mid (anti-honeypot / thin-book protection)
    if best_ask is not None and pre_mid is not None and side == "BUY":
        if best_ask - pre_mid > cfg.price_band:
            return False, (
                f"best ask {best_ask:.3f} deviates >{cfg.price_band:.2f} from mid "
                f"{pre_mid:.3f} — price band rejection"
            )

    # Consistency check (review C1): exposure-increasing orders must imply positive
    # fee-adjusted edge for the direction taken.
    if not is_exit and probability is not None and best_ask is not None:
        p = best_ask
        breakeven = p + fee_rate * p * (1 - p)
        if probability < breakeven - cfg.edge_epsilon:
            return False, (
                f"stated probability {probability:.2f} is below fee-adjusted breakeven "
                f"{breakeven:.3f} for this direction — thesis and trade disagree"
            )

    # Fleet self-dealing lockout (review C7) — direction algebra on conditionId
    my_dir = direction(token_index, side)
    since = time.time() - cfg.lockout_hours * 3600
    for row in ledger.fleet_activity_on(condition_id, since):
        if row["agent_id"] == agent_id:
            continue
        try:
            other_index = token_ids.index(row["token_id"])
        except ValueError:
            continue  # token not in this market's pair (shouldn't happen)
        if direction(other_index, row["side"]) != my_dir:
            return False, (
                "fleet integrity lockout: an opposing-direction benchmark order exists on "
                "this market within the lockout window"
            )

    return True, "ok"

"""Paper fill engine — the deterministic function (snapshot + order → fill) of PLAN §10.

Marketable orders only in the spike (FOK/FAK). Resting-order tape fills are Phase 1.
Pure: no I/O, no clock, no randomness — recomputable bit-for-bit from the persisted
snapshot, which is what the hash-commitment scheme (review C21) relies on.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Fill:
    shares: float
    avg_price: float
    notional: float
    fee: float
    levels_used: int


class FillError(Exception):
    pass


def _levels(book: dict, side: str) -> list[tuple[float, float]]:
    """Sorted (price, size) levels the taker consumes: asks ascending for BUY,
    bids descending for SELL."""
    key = "asks" if side == "BUY" else "bids"
    levels = [(float(l["price"]), float(l["size"])) for l in book.get(key, [])]
    return sorted(levels, key=lambda x: x[0], reverse=(side == "SELL"))


def top3_depth_usd(book: dict, side: str) -> float:
    return sum(p * s for p, s in _levels(book, side)[:3])


def best_price(book: dict, side: str) -> float | None:
    lv = _levels(book, side)
    return lv[0][0] if lv else None


def mid(book: dict) -> float | None:
    a, b = best_price(book, "BUY"), best_price(book, "SELL")
    if a is None or b is None:
        return None
    return (a + b) / 2


def simulate_marketable(
    book: dict, side: str, *, notional: float | None = None,
    shares: float | None = None, fee_rate: float = 0.0,
) -> Fill:
    """Walk the snapshot. BUY spends `notional` dollars; SELL sells `shares` shares.
    Taker fee = shares × feeRate × p × (1−p) applied at the average fill price
    (docs/research/polymarket-api.md §2)."""
    levels = _levels(book, side)
    if not levels:
        raise FillError("empty book on the taker side")

    got_shares = 0.0
    spent = 0.0
    used = 0
    if side == "BUY":
        assert notional is not None
        remaining = notional
        for price, size in levels:
            level_cost = price * size
            take = min(remaining, level_cost)
            got_shares += take / price
            spent += take
            remaining -= take
            used += 1
            if remaining <= 1e-9:
                break
        if remaining > 1e-9:
            raise FillError("insufficient book depth for FOK order")
    else:
        assert shares is not None
        remaining = shares
        for price, size in levels:
            take = min(remaining, size)
            got_shares += take
            spent += take * price
            remaining -= take
            used += 1
            if remaining <= 1e-9:
                break
        if remaining > 1e-9:
            raise FillError("insufficient book depth to sell FOK")

    avg = spent / got_shares
    fee = got_shares * fee_rate * avg * (1 - avg)
    return Fill(shares=got_shares, avg_price=avg, notional=spent, fee=fee, levels_used=used)

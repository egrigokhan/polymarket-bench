"""Phase 0 demo: exercise the paper gateway end-to-end against LIVE Polymarket data.

Run: python3 demo.py
Creates a throwaway agent with $100, finds eligible markets, places a paper trade with
required metadata, demonstrates a risk rejection + idempotent replay, prints portfolio.
"""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from gateway.config import DEFAULT
from gateway.ledger import Ledger
from gateway.service import Gateway


def main() -> None:
    ledger = Ledger(Path(__file__).parent / "bench-demo.db")
    gw = Gateway(ledger, DEFAULT)

    agent_id = ledger.create_agent(
        "pmb-demo-opus48-claudecode", "claude-opus-4-8", "claude_code_cloud",
        DEFAULT.starting_balance,
    )
    gw.open_session(agent_id)
    print(f"agent {agent_id} created with ${DEFAULT.starting_balance}")

    print("\n=== eligible markets (top by 24h volume) ===")
    markets = gw.search_markets(limit=5)
    for m in markets:
        print(f"  {m['prices']}  {m['question'][:70]}  (liq ${m['liquidity']:,.0f})")
    if not markets:
        print("no eligible markets found — check API access")
        return

    # Pick a mid-priced market so the fee-adjusted consistency check has teeth
    # (on a 0.3¢ longshot, breakeven ≈ 0.003 and no probability can sit below it).
    target = next(
        (m for m in markets if m["prices"] and 0.05 <= float(m["prices"][0]) <= 0.95),
        markets[0],
    )
    print(f"\n=== market detail: {target['question'][:70]} ===")
    detail = gw.get_market(target["condition_id"])
    print(f"  eligible={detail['eligible']} ({detail['eligibility_note']})")
    print(f"  book (outcome 0): {detail['book_outcome0']}")

    ask = float(detail["book_outcome0"]["asks"][0]["price"]) if detail["book_outcome0"]["asks"] else 0.5

    print("\n=== place paper order: $5 BUY outcome 0 ===")
    coid = f"demo-{uuid.uuid4().hex[:8]}"
    res = gw.place_order(
        agent_id,
        client_order_id=coid,
        condition_id=target["condition_id"],
        outcome_index=0,
        side="BUY",
        notional=5.0,
        thesis="Demo trade: exercising the Phase 0 pipeline end to end.",
        probability=min(0.99, ask + 0.05),  # consistent with direction (passes edge check)
        confidence=0.5,
        invalidation="This is a pipeline test; any real market move invalidates it.",
        horizon_note="resolves within the season by construction",
    )
    print(f"  {res}")

    print("\n=== idempotency: replay the same client_order_id ===")
    print(f"  {gw.place_order(agent_id, client_order_id=coid, condition_id=target['condition_id'], outcome_index=0, side='BUY', notional=5.0)}")

    print("\n=== risk rejection: $50 order (over the $10 Season-0 cap) ===")
    res = gw.place_order(
        agent_id,
        client_order_id=f"demo-{uuid.uuid4().hex[:8]}",
        condition_id=target["condition_id"],
        outcome_index=0,
        side="BUY",
        notional=50.0,
        thesis="too big on purpose",
        probability=min(0.99, ask + 0.05),
        invalidation="n/a",
    )
    print(f"  {res}")

    print("\n=== consistency-check rejection: bearish probability on a BUY ===")
    res = gw.place_order(
        agent_id,
        client_order_id=f"demo-{uuid.uuid4().hex[:8]}",
        condition_id=target["condition_id"],
        outcome_index=0,
        side="BUY",
        notional=5.0,
        thesis="I think this is overpriced",  # ...while buying it
        probability=max(0.01, ask - 0.30),
        invalidation="n/a",
    )
    print(f"  {res}")

    print("\n=== portfolio ===")
    pf = gw.get_portfolio(agent_id)
    print(f"  cash ${pf['cash']}  positions ${pf['positions_value']}  equity ${pf['equity']}")
    for p in pf["positions"]:
        print(f"  {p['shares']} sh {p['outcome']} @ cost ${p['cost_basis']} "
              f"(mid {p['current_mid']}, uPnL ${p['unrealized_pnl']}) — {p['question'][:55]}")


if __name__ == "__main__":
    main()

# trading-gateway/

The single choke point between agents and Polymarket. Three faces (PLAN.md §10):

1. **MCP server** — multi-tenant tool surface (`search_markets`, `get_market`,
   `get_portfolio`, `submit_forecast_card`, `place_order`, `cancel_order`,
   `get_activity`) + the bench-operated per-agent SQL memory MCP. Per-agent short-TTL
   tokens; gateway-side session windows (PLAN §8).
2. **Execution engine** — `py-clob-client-v2`, eligibility + risk envelope (PLAN §7:
   price bands, conditionId self-dealing lockout, `client_order_id` idempotency,
   anti-honeypot heuristics), auto-redeem cron, relayer queue, reconciliation. Signing
   delegated to the co-signer (PLAN §9). **Paper mode** = same path, one flag: snapshot
   walk for takers, trade-tape strictly-through rule for resting orders, per-fill raw
   book snapshots persisted + daily Merkle-root commitment.
3. **Bench ledger** (Postgres) — canonical store incl. required pre-trade snapshot
   fields (mid/bid/ask/depth/fee-breakeven). The dashboard reads only from here.

Phase 0 scope: Gamma/CLOB/Data clients, eligibility + risk engine, ledger, paper
taker-fill engine, CLI test harness.

## Spike status (2026-07-03): WORKING against live Polymarket data

- `python3 demo.py` — end-to-end CLI demo: creates a $100 agent, lists eligible markets,
  fills a $5 paper order off the real book, demonstrates idempotent replay, the $10
  size-cap rejection, and the probability-consistency rejection, prints the portfolio.
- `python3 mcp_server.py` (stdio) or
  `fastmcp run mcp_server.py --transport http --port 8940` (HTTP, for Brainbase
  `mcp_servers.url`) — exposes `search_markets` / `get_market` / `get_portfolio` /
  `place_order` over MCP. Smoke-tested: an MCP client placed a filled paper order
  through the full risk pipeline.
- Implemented from PLAN §7/§10: eligibility (6h floor, in-season, liquidity/volume
  floors, sub-daily-crypto exclusion, 72h anti-honeypot age, placeholder-outcome
  rejection), risk envelope ($10/$15/$2 Season-0 caps, 10%-of-depth, price band,
  session order cap), `client_order_id` idempotency, conditionId-direction self-dealing
  lockout, required thesis/probability metadata + fee-adjusted consistency check,
  pre-trade snapshot fields persisted with the raw book on every order.
- Not yet (Phase 1+): multi-tenant tokens + session windows, forecast card, Merkle
  commitments, Postgres, the co-signer/watchdog split.

## Execution backend (2026-07-04): polymarket-paper-trader

Paper fills now run on [polymarket-paper-trader](https://github.com/agent-next/polymarket-paper-trader)
(MIT, `pip install polymarket-paper-trader`) via [gateway/pmt_backend.py](gateway/pmt_backend.py)
— Gateway default `execution="pmt"` (`"internal"` keeps the original engine for tests).
This buys: live per-token fee rates, GTC/GTD limit orders with tape fills, and market
resolution → realized cash (`Gateway.process_housekeeping(agent_id)`, to be cron'd by
the orchestrator). One isolated pmt account per agent under `pmt-accounts/<agent_id>/`.
The gateway still owns eligibility, the risk envelope, thesis metadata, the consistency
check, the self-dealing lockout, idempotency, and the bench ledger.

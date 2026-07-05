# dashboard/

Next.js public dashboard, reading only from the bench ledger + sealed Brainbase event
mirror (PLAN.md §13).

Surfaces: front-page leaderboard (equity + CIs + luck band + baselines), **The Grid**
(`/grid` — model×harness matrix; Season 0 shows panel Brier as the confirmatory number
with equity badged "N=1 — descriptive"; the Live/Paper toggle arrives with Season 1's
replicate fleet), agent pages with the
permalinkable reasoning feed (6h lag), `/moments` (curated, criteria published),
`/market/{slug}`, `/built-with` (Brainbase showcase + CTA), and the methods page
(pre-registered analysis plan, commitment hashes, publishing-lag honesty, missed-session
policy).

Publishing lags: fills 1h (pacing only — chain is real-time public), open orders never,
transcripts 6h, Mystery Agent transcripts embargoed to season end (daily hash commits).

Phase 1 scope: leaderboard, equity curves, agent pages, reasoning feed, Grid.
Phase 4: /moments, /market/{slug}.

## Spike status (2026-07-03): WORKING

[app.py](app.py) — Flask over the gateway ledger, dark-terminal aesthetic, 60s
auto-refresh. Run `python3 app.py` (port 8941; `PMB_DB` env var points at a ledger,
default `../trading-gateway/bench-demo.db`). Serves:
- **Leaderboard** — rank, agent, model, harness, cash, positions value (marked to live
  Polymarket mids), equity, return %, fees paid, rejection count.
- **Per-agent cards** — open positions with unrealized PnL, recent orders with the
  thesis on fills and the human-readable reason on rejections.
- `/api/state` — the JSON shape the Phase 1 Next.js app will consume.

The Next.js production dashboard replaces this in Phase 1; this is the working window
into the Season 0 ledger.

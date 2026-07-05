# PolymarketBench

**The live benchmark where AI agents trade real money on Polymarket.**

A matrix of agents — different **models** (Claude, GPT, Gemini, Grok) × different
**harnesses** (Claude Code, Codex, Kafka) — each gets a $100 wallet, wakes up twice a day,
researches the world with its own tools under a hard token budget, and trades real
prediction markets. A public dashboard shows the leaderboard, every position, every trade,
and every agent's full reasoning — live. Season 0 runs ~$5k all-in; the replicated,
claims-grade Season 1 is funded by lab-donated credits.

Sponsored by [Brainbase Labs](https://brainbaselabs.com); agents are created and driven via
the [Brainbase v2 Managed Agents API](https://docs.brainbaselabs.com/api).

## Why

- Prediction markets are **contamination-proof** (the future isn't in training data) and
  give both a Brier score and a dollar PnL per resolved market.
- Nobody has published a clean **model × harness** grid on a real-money task — is the model
  or the scaffold doing the work?
- Prior art says most agents will lose to fees (PolyBench, Prophet Arena, Alpha Arena).
  Beating the market is the story; failing to is the finding.

## The design in 30 seconds

- **Budget-tiered seasons, one architecture**: Season 0 (now, ~$5k) = 16 agents, $100
  wallets, token-capped sessions, no replicate fleet — cross-agent claims come from the
  shared forecast-card panel; equity rankings are labeled descriptive against a luck
  band. Season 1 (lab-credit-funded) adds $1,000 wallets and a 5-replicate Paper Division
  for claims-grade equity rankings.
- **Two execution modes, one code path**: paper (simulated fills on real order books,
  hash-committed — the public preseason) and live (real pUSD, on-chain auditable).
- **Wake-ups**: 2 scheduled/day + queued event triggers (position moved, resolution near).
  SKIP is always allowed — no forced trades.
- **Access**: agents never touch signing keys. A risk-guarded **trading gateway** (MCP
  server) enforces market eligibility, price bands, position caps, and integrity rules,
  and requires a thesis + probability + invalidation condition on every order.
- **Scoring**: equity (headline, with T+14 certification), skill vs. each agent's
  zero-edge line, panel Brier/calibration (the confirmatory cross-agent numbers), paired
  edge vs. market price, compute spend — with event-level cluster-bootstrap CIs and
  checkpoint-gated significance labels, per a pre-registered analysis plan.
- **Baselines on the board**: random bot (plus a 1,000-run simulated luck band),
  favorite-bias bot, hold-cash bot.

**Read [PLAN.md](PLAN.md)** — the full design doc. Research backing it is in
[docs/research/](docs/research/).

## Repo layout

| Dir | What |
|---|---|
| [PLAN.md](PLAN.md) | Master plan: design, money flow, compliance, milestones |
| [docs/research/](docs/research/) | Polymarket API, live-benchmark prior art, Brainbase API |
| [docs/open-questions.md](docs/open-questions.md) | Decision log & open asks |
| `trading-gateway/` | MCP server, risk engine, execution (py-clob-client-v2), paper fills, ledger |
| `orchestrator/` | Scheduler, event triggers, Brainbase client, SSE ingest |
| `harness/` | Versioned agent instructions + wake-up templates (frozen per season) |
| `baselines/` | Coinflip Carl, Chalk Charlie, Cash Cathy |
| `dashboard/` | Next.js public dashboard |

## Status

Planning complete (v1.2, 2026-07-03) — v1.0 survived an adversarial 5-lens review
([docs/plan-review-v1.md](docs/plan-review-v1.md), 34 findings, all incorporated in v1.1);
v1.2 re-tiered the budget to a ~$5k lean Season 0 with the replicated science config gated
on lab credits. Next: Phase 0 spike — gateway core + one Brainbase agent trading paper,
end to end, with the interrupt-safety and cost-measurement gates. See [PLAN.md §16](PLAN.md).

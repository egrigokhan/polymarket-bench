# PolymarketBench — Master Plan

**A live benchmark where AI agents — different models × different harnesses — trade real
money on Polymarket, with a public dashboard showing every position, trade, and thought.**

Sponsored by Brainbase Labs. Agents are created and driven via the
[Brainbase v2 Managed Agents API](https://docs.brainbaselabs.com/api).

> Status: plan **v1.2** (2026-07-03). v1.0 went through an adversarial 5-lens review
> (statistics, Polymarket mechanics, Brainbase integration, security, product/ops); all 34
> findings and their verifications are archived in
> [docs/plan-review-v1.md](docs/plan-review-v1.md) and incorporated in v1.1. **v1.2
> re-tiers the budget**: Season 0 launches lean (~$5k all-in: $100 wallets, 2 sessions/day,
> hard token caps, no paper replicate fleet); the replicated science config becomes Season
> 1, gated on lab-donated credits. Research backing every decision lives in
> [docs/research/](docs/research/) — [polymarket-api.md](docs/research/polymarket-api.md),
> [live-benchmarks.md](docs/research/live-benchmarks.md),
> [brainbase-api.md](docs/research/brainbase-api.md).

---

## 1. Executive summary

PolymarketBench pits a matrix of **(model × harness)** agents against each other on real
Polymarket prediction markets. Each agent gets a **$100 pUSD wallet**, wakes up **2× per
day plus event triggers**, researches under a **hard per-session token budget**, and trades
through a **risk-guarded trading gateway** we operate. A live dashboard shows the
leaderboard, equity curves, every position, every trade, and every agent's **full reasoning
feed** (published on a short lag; one disclosed exception for the Mystery Agent, §3).

Seasons are **budget-tiered** — the architecture is identical, only the parameters scale:

- **Season 0 (the launch config, ~$5k all-in)**: 16 agents (12-cell grid + Mystery Agent +
  3 baseline bots), $100 wallets, 2 scheduled sessions/day, ~$0.50–1 token cap per
  session. Cross-agent **forecasting** claims come from the shared **forecast-card panel**
  (§8) — identical questions for every agent, hundreds of shared resolutions, real
  statistical power. **Equity rankings are explicitly descriptive spectacle** (N=1 per
  cell), displayed against a 1,000-run simulated luck band and per-agent zero-edge lines
  so nobody mistakes luck for skill.
- **Season 1 (the replicated science config — gated on lab-donated credits + Season 0
  landing)**: $1,000 wallets, 3 sessions/day, and a Paper Division at 5 replicates per
  cell, which is what claims-grade *equity* rankings and the harness-vs-model variance
  decomposition cost (~$69–230k inference, §15 — the Metaculus model: labs donate credits
  to be benchmarked).

Two execution modes share one code path: **paper** (simulated fills against real live
order books, hash-committed and recomputable) and **live** (real pUSD, on-chain
auditable). Season 0 runs the same fleet **paper-first** — a public preseason with zero
ToS exposure — and flips to live $100 wallets when the legal/partnership track clears
(§14).

The stance that survives every tier, learned from Alpha Arena's public shredding: a
pre-registered analysis plan frozen at season start, luck bands and zero-edge lines on the
board, and every number labeled **confirmatory or descriptive** — nothing buys
unconditional alpha claims from one season's realized world, and the methods page says
exactly that.

## 2. Why this benchmark is worth doing

- **Structural contamination immunity**: the future isn't in anyone's training data. Every
  resolved market is fresh ground truth.
- **Many small ~independent bets** beat one leveraged equity curve statistically. Prediction
  markets give Brier scores AND dollar PnL per resolution — two decoupled result axes
  (Prophet Arena showed frontier models are calibrated yet still don't beat the market;
  reproducing or breaking that finding *is* the scientific contribution).
- **Harness as a first-class variable**: nobody has published a clean model×harness grid on
  a real-money task. Brainbase's `runtime_kind` (Claude Code / Codex / Kafka) makes this a
  one-field experiment — and it's exactly Brainbase's pitch: the agent is a *stack* (model +
  harness + tools + memory), not just a model.
- **Virality is designed in**: real money + on-chain verifiable wallets + a MODELCHAT-style
  reasoning feed + lab-rivalry horse race + Polymarket itself listing meta-markets on the
  outcome (they did for Alpha Arena).

## 3. The competitors

### Season 1 matrix (Live Division)

| | Claude Code harness | Codex harness | Kafka harness |
|---|---|---|---|
| **Claude Opus 4.8** | agent 1 | agent 5 | agent 9 |
| **GPT-5.5** | agent 2 | agent 6 | agent 10 |
| **Gemini 3.5 Flash** (or 2.5 Pro) | agent 3 | agent 7 | agent 11 |
| **Grok 4** | agent 4 | agent 8 | agent 12 |

- Season 0: 12 grid agents × **$100 = $1,200 capital at risk** (13 with the Mystery
  Agent; ~$1,600 float with baselines). Capital is the *recoverable* cost — inference is
  the real budget (§15). Upgrade path: $1,000 wallets in Season 1, $10k flagships later.
- All 12 created via `POST /v2/agents` with identical `instructions`, differing only in
  `default_model` and `runtime_kind`.
- ⚠ `runtime_kind` strings for Codex/Kafka are unpublished — week-1 internal ask. If cells
  are unsupported (e.g., Codex harness only runs OpenAI models), we run a **pre-declared
  balanced subgrid** for the harness-vs-model question (≥2 harnesses fully crossed with ≥3
  models); non-crossed cells render as labeled exhibition cells and are never pooled into
  the headline answer. If no balanced subgrid survives, we publicly drop the
  harness-vs-model question for the season rather than report a confounded estimate.
- **+1 Mystery Agent** (13th wallet): an unnamed model/harness combo. Its trades (standard
  publishing lag), equity, rank, and full scorecard are live all season; its **reasoning
  feed is embargoed until the season-end reveal** (free-form transcripts self-identify —
  "As Claude…" — so a live feed would kill the mystery in days). Integrity: we publish a
  SHA-256 of its identity on day 1 AND a daily hash of its accumulated transcript log, so
  the feed released at reveal is verifiably unedited. Weekly "guess the agent" excerpts
  with pre-committed curation rules (only literal self-identification and harness-syntax
  markers scrubbed, each scrub marked). This is the one disclosed exception to the
  full-reasoning-feed promise, stated in the FAQ from day 1.

### Baselines (non-negotiable, run as real wallets in both divisions)

1. **Coinflip Carl** — at each scheduled wake-up: random eligible market, random side,
   fixed **$2** marketable order (stakes scale with the wallet tier: $2 at $100 wallets,
   $25 at $1,000). The live Carl is *one draw* from the luck distribution — the actual
   null is the **simulated Carl cohort**: ≥1,000 offline Coinflip Carls (no LLM — free to
   run; same eligibility filter, same stakes, same cadence, fills at logged prices, real
   resolutions), whose 5–95% band is drawn directly on the leaderboard and equity chart.
2. **Chalk Charlie** — *favorite-bias harvester, a known simple strategy* (not "the
   market": always-buying-favorites harvests the documented favorite-longshot bias, and
   the fee formula `p(1−p)` makes favorites fee-cheap — he may plot above zero and we say
   why). Spec mirrors Carl: each wake-up, random eligible market, buy the higher-priced
   outcome if in [0.60, 0.95], $2 marketable order.
3. **Cash Cathy** — never trades. The "was doing nothing optimal?" line.
4. *(Paper only)* **Kelly Kelly** — simple heuristic bot marking where cheap classical
   automation sits.
5. *(Stretch, Season 2)* Human superforecaster panel, Metaculus-style.

The **zero-edge line** (the true "market" benchmark) is not a wallet at all — it's computed
per agent from the ledger (§12): value every fill at its logged pre-trade market price, at
which market-implied expected gross PnL is zero, so each agent's zero-edge line is simply
−(fees + slippage) over its own trade set, and skill = realized PnL − market-implied PnL.

### Execution modes and the Season 1 replicate fleet

- **Paper mode** (Season 0 preseason + Season 1's Paper Division): fills simulated against
  the real live order book with a fully specified, published fill model (§10) — paper
  agents are real Brainbase agents doing real research; only execution is simulated.
- **Season 0 has no replicate fleet** — that is the entire cost saving (§15), and it's why
  Season 0's equity rankings are labeled descriptive. The forecast-card panel (§8) carries
  the cross-agent claims instead: every agent answers the same ~10 questions at every
  scheduled wake-up, which accumulates ~700 shared, resolvable predictions per agent over
  the season — real power on the *forecasting* axis, no replicates required.
- **Season 1 Paper Division** (gated, §15): the 12-cell grid + baselines at **5 replicates
  per cell** (Vending-Bench needed 5 runs in a *replayable sim* and still saw 8× spreads).
  Replicates share the frozen harness and differ only in pre-registered ways (wake-jitter
  seed; sampling/temperature policy stated in the frozen harness doc). Replicates estimate
  *decision noise*; cross-cell contrasts are **paired on the common market draw** (common
  random numbers); absolute per-cell claims stay conditional on that season's realized
  world. An **exhibition set** (unranked, 1 replicate: Haiku 4.5, GPT-5-Mini, Gemini
  Flash, Grok 4 Fast, open-weights via proxy) rides along if credits allow — first thing
  cut.

## 4. Season structure

- **Each ranked season: 10 weeks.** Long enough for hundreds of resolutions per agent
  (and ~700 forecast-card resolutions each); short enough to keep narrative tension.
  (Alpha Arena's 2 weeks was the most-criticized choice they made.) Season 0 is preceded
  by a public **paper preseason** (§16 Phase 2) on the same fleet.
- **Harness freeze**: instructions, tools, risk limits, wake-up templates, AND the
  analysis plan (§12) are versioned (`harness/v1.x`) and **frozen at season start**.
  Mid-season changes only for safety/integrity bugs, publicly changelogged. Never for
  performance.
- **No mid-season additions to the ranked table.** New model releases join as clearly
  flagged **exhibition wallets** (unranked) and enter the ranked grid next season.
- **No removals, ever.** Losing agents stay on the board (Leaderboard Illusion lesson).
  A bankrupt agent (< $1 buying power, no open positions) is marked BUST with a tombstone
  — which is excellent content.
- **Settlement protocol** (pre-committed, on the methods page): provisional standings are
  frozen at a pre-announced season-close timestamp using the §12 terminal-valuation rule;
  the **official final ranking** is the certification at **T+14 days**, when straggling
  resolutions (UMA disputes run 4–6 days; postponements happen) have been replaced by
  realized outcomes. Pre-committing which number is official closes the "they rewrote the
  results" attack.
- End-of-season: full data dump (every prompt, every raw model output, every order, every
  fill, every paper-fill book snapshot) published as a dataset + a written report.

## 5. The wake-up model (how often agents trade)

**Design principle** (Vending-Bench + the Boris-Again critique of Alpha Arena):
*scheduled-but-sparse wake-ups with an explicit SKIP option, plus event triggers.*
Prediction markets move on news cadence, not tick cadence; forcing a decision every few
minutes manufactures noise and hallucinated conviction.

### Scheduled wake-ups: 2 per day per agent (Season 0; 3/day at Season 1 scale)
- Anchored at 08:00 / 20:00 UTC **± 0–30 min per-agent jitter**. The jitter RNG
  seed and full schedule are **hash-committed on day 1** and revealed at season end (same
  sealed-envelope mechanism as the Mystery Agent — the operator must be provably unable to
  retro-fit a favorable schedule).
- Each wake-up = **one new Brainbase task** (`POST /v2/tasks`, `auto_run: true`) with a
  standardized wake-up message (§8). One-task-per-wakeup keeps context fresh; continuity
  lives in the agent's memory DB + `/workspace/Shared` journal — *whether and how agents
  use memory is itself an observed variable*.
- **Session budget — the cost-control heart of the Season 0 config**: 30 wall-clock
  minutes (hard ceiling) AND a **~100k-token cap (≈ $0.50–1/session)**, measured **from
  the first agent event** (not task creation — cold-start latency must not eat the budget
  or skew across harnesses; per-runtime latency is a Phase-0 measurement). Most wake-ups
  should be cheap "check portfolio, scan, skip" sessions; deep research becomes something
  agents must *budget for* — itself an observed behavior. Enforcement is layered (§7,
  §11): the **gateway is the primary enforcer** — the orchestrator registers each
  session's absolute UTC deadline with the gateway, which rejects new `place_order` calls
  after T−2min with a machine-readable "session ending" rejection
  (`cancel_order`/`get_portfolio` stay open until T); Brainbase `/interrupt` is the
  *backstop* that reaps the sandbox. The token cap's enforcement mechanism (usage
  telemetry vs. heuristic SSE-text metering) is an explicit Phase-0 deliverable (§11
  asks); until it lands, wall-clock is the enforceable control and the cap value is
  tuned from measured Phase-0 $/session.
- **One active task per agent, always.** The orchestrator never starts a second session
  while one runs.

### Event-triggered wake-ups (max 3/day extra per agent in Season 0; 5/day at Season 1)
Triggers, evaluated by the orchestrator against each agent's portfolio:
1. A held position's mid moves ≥ 10¢ since last wake-up.
2. A held position's market enters its final 24h.
3. A fill or resolution occurred (informational — rendered into the next wake-up).
4. Balance idle > 72h with < 20% deployed (information, not an instruction to trade).

While a session is live, triggers **queue and deduplicate** (multiple 10¢ moves on one
position collapse to one line). When the session ends — terminal SSE event, status poll
fallback, `/interrupt` as hard backstop, always confirming terminal status before
proceeding — a non-empty queue fires one event wake-up immediately (counted against the
daily cap), because pre-resolution triggers are time-sensitive.

### Why 2/day is right for Season 0 (and what changes at scale)
- Edge-relevant information (news, polls, injuries, data prints) arrives on an hours
  cadence, and morning/evening anchors bracket the US news day. 2/day ≈ 140 scheduled
  sessions per agent per season; with 1–3 actions per session that's 150–400 trades per
  agent — plus ~700 forecast-card predictions, which is where the statistical power lives
  anyway (§3).
- Season 1 restores 3/day; a "day-trader arm" (hourly wake-ups, sports/daily-crypto only)
  is a Season 2 condition arm, Nof1-Season-1.5-style. Cadence is published as a known
  limitation at every tier.

## 6. Trade lifecycle & realistic expectations (the honest section)

### How long does a trade take to realize?
- **Fill**: seconds on liquid books (FOK/FAK marketable orders); resting GTC orders may
  sit indefinitely (agents can cancel at any wake-up).
- **Resolution**: the market's own horizon — hours (sports, daily crypto) to weeks
  (politics). After a market ends: UMA optimistic-oracle proposal + 2h challenge window;
  undisputed markets are redeemable **~2h after end**; disputed ones take **4–6 days**,
  and 50/50 resolutions are possible.
- **Redemption**: gasless via relayer; the gateway **auto-redeems** resolved positions
  hourly, so winnings recycle without burning agent wake-ups on bookkeeping.
- So: mark-to-market equity updates continuously; *realized* PnL streams in from day 1
  (sports/crypto dailies) with a long tail. Eligibility rules (§7) make in-season
  realization the **dominant case** — but disputes, postponements, and end-date slips can
  straggle past season close, which is exactly what the terminal-valuation rule (§12) and
  the T+14 certification (§4) exist for. We never claim a guarantee.

### What results should we expect? (calibrate the sponsor, calibrate the audience)
Evidence says: **most agents will lose money after fees.**
- PolyBench: 2 of 7 models profitable on simulated Polymarket fills.
- Prophet Arena: frontier models well-calibrated (ECE < 0.05) yet don't beat the market —
  the bottleneck is information aggregation, not probability estimation.
- Alpha Arena S1: 4 of 6 models deeply negative; fees ate 13% of one model's capital.
- Metaculus: pro forecasters still beat top bot ensembles (p=0.00001).

The headline questions, restated precisely (with the season that can answer each):
1. **Does any (model × harness) cell beat its own zero-edge line after fees?** Within-
   agent paired test — answerable per agent in Season 0 (cluster-robust, checkpoint-only);
   cross-cell *rankings* of it need Season 1 replicates.
2. **Does harness matter more than model?** On the *forecasting* axis, Season 0's shared
   panel already supports the paired grid comparison (~700 identical predictions per
   agent). On the *equity* axis, the variance decomposition needs Season 1's 5
   replicates/cell on the pre-declared balanced subgrid.
3. Are agents calibrated but unprofitable (Prophet Arena's split), and do research tools
   close that gap? (Forecast-card panel + trade outcomes, §12 — Season 0.)
4. Behavioral fingerprints: overtrading, long-bias, category preferences, risk-rule
   adherence, memory usage — the content people actually share.
5. Discipline under drawdown: who panics, who revenge-trades, who goes to cash.

**Failure is a finding.** If everything loses to fees, the conclusion is "current agent
stacks can't yet extract edge from prediction markets" — publishable, honest, and it sets
up Season 2 as the redemption arc.

### Statistical validity, stated up front
- **Resampling unit**: cluster bootstrap over **events** (trades nest in markets; neg-risk
  sibling markets share an outcome), never over trades or replicates — trade-level CIs
  would be anticonservative. Each agent page shows **effective sample size** next to raw
  trade count. The ~350-resolutions-for-0.02-edge power figure (Foresight Arena) is per
  *independent* prediction; we quote it with that caveat.
- **Estimands**: within-cell replicates → decision noise (report mean with min/max,
  VB-style); cross-cell contrasts → paired on the common market draw; absolute alpha
  claims → conditional on this season's world, labeled as such.
- **Significance discipline**: labels update only at pre-registered checkpoints
  (mid-season, season end) — continuously flickering "statistical tie" badges are textbook
  sequential peeking and a screenshot liability. Between checkpoints, CIs display as
  "descriptive, not confirmatory". Multiplicity: BH-FDR (q=0.10) across cells, applied
  only to the two pre-declared primary metrics (final equity; paired forecasting edge);
  everything else on the scorecard is explicitly descriptive.
- **Tier-scoped claims**: in Season 0, cross-agent confirmatory claims come *only* from
  the shared forecast-card panel; equity rankings are descriptive (N=1 per cell, shown
  against the luck band). Season 1's replicated Paper Division upgrades equity rankings
  to confirmatory. This is the enforceable version of "claims from the panel and the
  replicates; stories from the live wallets."
- The full pre-registered analysis plan is frozen at season start on the methods page.

## 7. Market eligibility & the risk envelope

Enforced by the **gateway** (not by prompting — prompts are requests, the gateway is law):

**Eligible markets** (checked at order time, on Gamma `endDate`):
- `endDate − now ≥ 6h` (near-resolution/leakage floor; also the Brier exclusion boundary).
  Resting orders placed earlier may still *fill* inside the window; those fills execute
  but are excluded from forecasting scores (§12).
- `endDate ≤ season_end` (positions may straggle past close; §12's terminal-valuation rule
  + §4's T+14 certification handle it — this keeps the finale tradeable to the last
  session instead of creating a dead final fortnight).
- Liquidity floor: computed from **raw trade and book data with wash-trade filtering**,
  not from Gamma's spoofable `liquidity`/`volume_24hr` aggregates (target: ≈$2k depth /
  ≈$5k 24h genuine volume; exact thresholds private, see anti-manipulation below).
- **Sub-daily crypto series (5-min/15-min/hourly/4-hour) excluded** — bot-dominated books,
  0.07 fee tier, HFT-contest risk; hourly/4h are de facto unreachable under the 6h floor
  anyway. Daily+ crypto allowed. Hourly revisits in the Season-2 day-trader arm.
- Neg-risk markets allowed (gateway handles the `negRisk` flag); **placeholder outcomes in
  augmented neg-risk events are rejected** with an explanatory error.

**Anti-manipulation guards** (the envelope is public; a fully published filter is an attack
spec, so these run gateway-side with private thresholds, disclosed *as existing* on the
methods page — standard anti-fraud practice):
- **Per-order price band**: reject any taker order whose worst fill deviates more than K
  from the more conservative of (a) current book mid and (b) a time/volume-weighted price
  from trailing prices-history. Spot mid alone is attacker-settable in a thin book; the
  TWAP anchor is not. This also bounds ordinary thin-book slippage.
- Honeypot heuristics: minimum market age since listing (~72h), minimum distinct
  historical traders/makers over a trailing window (Data API trades), rejection when one
  address supplies most of top-of-book depth or when liquidity arrived as a step-spike,
  plus an operator blacklist with a fleet-wide delist switch.
- We reserve the right to exclude trades on markets later shown to be manipulated, with
  post-hoc public disclosure. Order-time eligibility is not part of score recomputation,
  so this doesn't break the recomputability story.
- This exact attack (wash-pumped honeypot book) is a scripted red-team drill in Phase 2.

**Per-order / per-agent limits** (Season 0 values; Season 1 in parentheses — all scale
with the wallet tier):
- Max $10 ($100) notional per order; max order ≤ 10% of top-3-level book depth on that
  side.
- Max $15 ($150) net exposure per market; max 25% of current equity per *event*.
- Max 10 orders per session; min $2 order — above the venue's $1 marketable minimum; note
  resting orders carry a ~5-share venue minimum (≈$2.50 at 50¢), so small resting orders
  may be venue-rejected and the gateway surfaces that reason.
- Order types: FOK/FAK/GTC/GTD; no post-only games in Season 1.
- Every `place_order` carries a required agent-generated **`client_order_id`** (UUID); the
  gateway deduplicates on it and replays the original result on retry — no interrupt,
  timeout, or harness retry can double-submit an order.

**Fleet-wide integrity constraints** (the mechanical guarantee §14 relies on):
- **Self-dealing lockout, defined economically on `conditionId`** (not per book — the CLOB
  matches complementary orders *across* the YES and NO books by minting/merging complete
  sets, so BUY YES and BUY NO are directly matchable): direction A = {BUY YES, SELL NO},
  direction B = {BUY NO, SELL YES}. The gateway rejects any fleet order whose direction
  opposes (a) any **live resting fleet order** on that conditionId — regardless of age —
  or (b) any fleet fill/order there within 24h. For neg-risk events, direction is computed
  through the NegRiskAdapter equivalence; conservatively, after any fleet order in a
  neg-risk event, only same-market same-direction fleet orders are accepted for the
  window. Rejection errors name the conflicting *direction*, never the other agent's
  identity or thesis (no cross-agent information leakage).
- Fleet-wide exposure cap per market, stated in verifiable terms: fleet net exposure ≤ 5%
  of (book depth + 24h volume) — pending verification of a reliable open-interest source
  (docs/open-questions.md), in which case ≤ 5% of OI.

**Required trade metadata** (rejected without it):
```json
{
  "thesis": "1-3 sentences: why this price is wrong",
  "probability": 0.71,          // agent's own probability for YES
  "confidence": 0.6,            // conviction in the thesis itself, 0-1
  "invalidation": "what evidence would make me exit",
  "horizon_note": "when I expect the market to converge"
}
```
Plus a **consistency check**: exposure-*increasing* orders must state a probability that
implies non-negative fee-adjusted edge for the direction taken (YES buy ⇒ `probability ≥
executable ask + fees − ε`), or they're rejected with the reason — this keeps the stated
probability honest instead of decorative. Position-reducing/exit orders are exempt (exits
are risk management, not forecasts) and excluded from forecasting scores.

## 8. Agent harness (the frozen contract)

### System prompt (identical across all agents, versioned in `harness/`)
Core clauses: you are a trading agent in a public benchmark (hiding this is infeasible —
models would infer it; benchmark-awareness is documented as a known limitation); your only
goal is to maximize final equity by season end; your forecast-card panel score is also
public and on your scorecard; you may research anything on the open web; SKIP is always
acceptable and often correct; your memory DB is yours to organize; your reasoning is
published (on a lag); the gateway enforces hard limits — treat rejections as information;
you will be woken ~2×/day and on portfolio events; every session has a hard time and
token budget — spend it deliberately; there is no human to ask.

### Wake-up message template (standardized, injected by the orchestrator)
```
WAKE-UP #{n} — {utc_ts} — Season 1, day {d}/70 — session ends {deadline_utc}
PORTFOLIO: equity ${e} (cash ${c} + positions ${p}) | {k} open positions | rank {r}/13
SINCE LAST WAKE: {fills}, {resolutions}, {price_moves}, {gateway_notices}
TRIGGER: {scheduled | position_move | pre_resolution | fill | idle_capital}
FORECAST CARD: submit probabilities on today's panel before trading unlocks.
```
Identical structure for every agent; portfolio numbers come from the gateway, not the
agent's possibly-stale memory. Disputed positions are labeled
`disputed (capital locked, est. 4–6d)` so agents can reason about locked capital.

### The forecast card (what makes forecasting scores comparable)
At each scheduled wake-up epoch, **all agents receive the same deterministic panel of ~10
open eligible markets** and must submit probabilities via a gateway tool before trading
tools unlock for that session. Submissions are timestamped (jitter is auditable). Panel
Brier and panel ECE are the **only absolute cross-agent forecasting columns** on the
leaderboard — self-selected-trade metrics aren't comparable across agents (different
markets, base rates, horizons) and live on the agent page with a selection-bias caveat.
Brier is a proper scoring rule, so truthful reporting is optimal for any agent that cares
about the public score; the prompt says so explicitly.

### Tools
- **Trading gateway MCP** (attached via `mcp_servers`, per-agent auth in `headers`):
  - `search_markets(query, tags, sort, filters)` → eligible markets + prices + liquidity
  - `get_market(condition_id)` → detail incl. **resolution rules text**, order book, live fee rate
  - `get_price_history(token_id, interval)`
  - `get_portfolio()` → balance, positions (marked to market, dispute status), open
    orders, locked capital, PnL
  - `submit_forecast_card(probabilities)` (session-gating, see above)
  - `place_order({client_order_id, token_id, side, type, price?, size, thesis,
    probability, confidence, invalidation, horizon_note})`
  - `cancel_order(order_id)`
  - `get_activity(since)` → own fills/resolutions/redemptions
- **Memory: a bench-operated, multi-tenant per-agent SQL memory MCP** served from the
  gateway stack (per-agent Postgres schemas in the bench DB, same bearer-token pattern,
  frozen tool schema: `memory_sql` / `memory_tables` / `memory_schema`). Three reasons it's
  ours rather than Brainbase's observed-but-undocumented Neon memory connector: (a) memory
  availability becomes exactly co-extensive with gateway availability across every
  `runtime_kind` — no Codex/Kafka unknown; (b) every memory read/write lands in the bench
  ledger, which serves "memory usage as an observed variable" far better than SSE
  mirroring; (c) the freeze covers the tool *schema*, not the vendor — if Brainbase
  confirms their SQL-memory MCP is stable across all runtime_kinds before harness freeze,
  it can be swapped in behind the same tool names as a sponsor-showcase upgrade. We seed a
  suggested schema in the prompt but don't mandate it.
- **`/workspace/Shared`** — persistent scratch (notes, scripts the agent writes itself).
- **Open web** — whatever the harness natively provides. This is the "tool-use division"
  design: agents do their own research; the harness's native web stack *is part of what's
  being benchmarked*. (A unified-context division à la Prophet Arena is a Season 2 arm.)

### Credential reality (stated plainly, because overclaiming here is how you get burned)
**Signing keys, seed phrases, and exchange credentials never enter any sandbox** — signing
happens only in the gateway/co-signer stack (§9–10). The gateway **bearer token, however,
is agent-visible by design** (the in-sandbox MCP client must present it) and must be
treated as leakable under prompt injection — agents browse an attacker-writable web and
read attacker-authored market rules. Controls, in order of load-bearing-ness:
1. **Gateway-side session windows** (primary): the orchestrator opens a window per agent
   at task start and closes it at task end/interrupt/timeout; calls outside the window are
   rejected regardless of token validity. A leaked token is useless while its agent
   sleeps.
2. **Short-lived, narrowly-scoped tokens**: minted per wake-up (TTL ≤ session), scoped to
   the agent's own wallet only — with explicit cross-tenant IDOR tests in CI. Never
   planted via Brainbase `secrets` (plain env vars); delivered via `mcp_servers.headers`
   (whether PATCHed headers propagate to the next task's sandbox is an open question —
   fallback is a static per-agent token with controls 1, 3, 4 carrying the load).
3. **Redaction**: token patterns and env dumps are scrubbed from the SSE mirror before
   anything reaches the public feed; Authorization headers are redacted in ledger logging.
4. **Detection**: out-of-window and bad-token attempts are alerted on and tracked as a
   public integrity metric.
Bounded blast radius, stated in the plan: a fully leaked token = adversarial trading
within one ~$1k wallet's §7 envelope during an open window — no withdrawal path exists on
the MCP surface. Bad, detectable, capped.

## 9. Money: funding, custody, flow of funds

```
Sponsor treasury (Brainbase)
  └─ buy USDC on exchange → withdraw native-Polygon USDC
       └─ per-agent Bridge deposit address  (POST /deposit)
            └─ auto-converts → pUSD in the agent's Polymarket deposit wallet
                 (signature type 3 proxy; owner key = per-agent KMS-held EOA)
                 ├─ relayer-batch approvals (Exchange, NegRiskAdapter, CTF)  ← gasless
                 └─ trade / redeem via CLOB + relayer                        ← gasless
```

- **Bridge API is the primary funding path** — exchange USDC lands on the per-wallet
  Bridge deposit address and auto-converts to pUSD *inside the deposit wallet*, gasless
  end-to-end. This kills two v1.0 bugs at once: the EOA→deposit-wallet transfer (an
  EOA-signed tx that needs POL — the relayer can't pay the EOA's gas) and the manual
  `wrap()` step. The per-agent EOA remains as the deposit wallet's **owner/signing key**
  (KMS-held), not a funds hop. Fallback if exchange→Bridge withdrawals misbehave: small
  POL balance per EOA + documented wrap+transfer txs — validated either way with the $100
  test deposits before the full float moves.
- Bridge gotchas: check `/supported-assets` minimums (below-minimum deposits are silently
  dropped); confirm crediting via `/status/{address}`; mis-sends go through
  recovery.polymarket.com. The >$50k third-party-bridge caveat is irrelevant at $1k/agent.
- **One deposit wallet per agent** — addresses public on day 1 (auditability is the
  credibility core; the full list also goes to Polymarket immediately, §14).
- **Custody is split so no single box can steal the float** (v1.0 had the gateway as sole
  signer *and* sole policy enforcer — a compromised gateway could exfiltrate the whole
  float *by trading it* against an attacker-controlled counterparty; KMS protects key
  extraction, not intent, and ledger-vs-chain reconciliation both agree when money leaves
  via a losing trade):
  1. **Co-signer** in front of KMS (minimal hardened service the gateway cannot modify):
     signs only well-formed CLOB order structs for known token IDs; refuses relayer
     transfer/approval/withdrawal payloads unless accompanied by a 2-person-approved
     request (closing the relayer's gasless pUSD-transfer hole); enforces dumb,
     independently computed caps — per-wallet signing rate, max notional per order,
     rolling hourly notional budget. The gateway keeps the smart §7 rules; the co-signer
     is the blast-radius limiter.
  2. **Watchdog** on separate host/credentials, reading only on-chain fills + Data API:
     computes per-wallet loss velocity and repeated-external-counterparty concentration
     (order-fill maker/taker addresses — counterparties are unknowable at sign time, so
     this check is necessarily post-fill); on breach it flips the co-signer to refuse-all.
     This makes the kill switch effective *under gateway compromise*, unlike a
     gateway-internal flag.
  3. **Reconciliation** every 15 min (ledger vs. Data API `/positions` + `/value` vs.
     chain): detects accounting drift (>$1 alert). Documented for what it is — a drift
     detector, not a theft detector; the watchdog is the theft control.
- Both refusal paths are **rehearsed in the closed beta**: a simulated-compromised gateway
  attempts a self-cross and a relayer transfer; the co-signer must refuse both.
- Withdrawal keys (back to treasury): 2-person action, technical (co-signer-enforced), not
  procedural.
- Relayer is rate-limited (25/min fleet-wide) → the gateway queues relayer ops.
- Season 0 float: ~$1.6k in wallets + $400 treasury buffer (Season 1: $13k + $2k).
  Co-signer caps scale with the tier.

## 10. Polymarket access architecture: the trading gateway

One service (`trading-gateway/`), three faces:

1. **MCP server** (what agents see) — the §8 tool surface, multi-tenant, per-agent
   session-scoped tokens. Every call logged to the bench DB with agent_id, full
   request/response (auth headers redacted), latency. `place_order` responses include fill
   status, fees paid, and any rejection with a human-readable reason (rejections are
   learning signal).
2. **Execution engine** — wraps `py-clob-client-v2`: L2 API creds per wallet, order
   construction, tick-size + neg-risk handling, the §7 envelope, fleet-wide checks,
   auto-redemption cron, relayer queue, reconciliation loop, session windows. Signing is
   delegated to the co-signer (§9). **Ledger invariant**: once the gateway accepts an
   order it completes signing, venue submission, and ledgering atomically in its own
   process, independent of the agent/task lifecycle — an interrupt or agent death never
   orphans an accepted order, and `client_order_id` replay makes retries no-ops.
3. **Bench ledger** (Postgres) — canonical store: agents, wallets, orders (with required
   **pre-trade market snapshot fields**: mid, best bid/ask, top-3 depth, fee-adjusted
   breakeven — these anchor the §12 paired forecasting metric and the zero-edge line),
   fills, resolutions, equity snapshots (5-min cadence; prices snapshotted live because
   Polymarket's `prices-history` degrades on closed markets), trade metadata, session
   records, memory-tool calls, rejections. The dashboard reads only from this DB + the
   Brainbase-events mirror; on-chain + Data API are the audit layer it must reconcile
   with.

### Paper mode (same code path, one flag — and fully specified, because fill assumptions
alone can invert rankings)
- **Snapshot semantics**: the book is fetched when `place_order` reaches the gateway
  (submission time — stated precisely; "decision time" was ambiguous).
- **Marketable orders** (FOK/FAK, and GTC/GTD that cross at placement): fill by walking
  that snapshot, capped per §7, taker fees at the per-market rate queried at match time
  (`getClobMarketInfo` — the schedule is dynamic, never hardcoded).
- **Resting orders**: fill as makers via the public WS trade tape — a resting paper order
  fills at its limit price (maker fee = 0, per the live schedule) only against tape volume
  printing **strictly through** its price (zero queue priority: prints *at* the price
  never fill it), pro-rated when tape volume is smaller. Conservative by construction
  (real resting orders suffer adverse selection; this model under-fills rather than
  over-fills). Fallback: if the tape engine isn't ready for Phase 1, Season 0 restricts
  paper to FOK/FAK and changelogs it — undefined GTC behavior never ships.
- **Replicate liquidity**: replicate fills stay independent (a shared shadow ledger would
  make replicates non-independent, defeating their purpose), but each paper taker fill is
  capped at top-3 depth ÷ (number of benchmark paper agents that traded that market in the
  trailing 30 min); both naive and depth-adjusted fills are logged for sensitivity
  analysis; the methods page states paper fills are independent per replicate and
  therefore optimistic in aggregate.
- **Verifiability** (the division that carries claims must be auditable — v1.0 had this
  inverted): every simulated fill persists its exact inputs (timestamped raw `GET /book`
  response, tick size, negRisk flag, fee rate, order request); the fill simulator is a
  **pure deterministic function (snapshot + order → fill), open-sourced in this repo**; a
  **daily Merkle root of fill records is published** (signed git tag) so snapshots can't
  be retro-fabricated — recomputation from public history is impossible (no historical
  depth API), so committed operator snapshots are the only feasible evidence base. All
  snapshots ship in the end-of-season dump. And the baselines run as real wallets in
  *both* divisions, so every live baseline fill doubles as a continuous live-vs-simulated
  slippage check, published on the methods page — an empirical bound on simulator bias.

Why a gateway instead of handing agents `py-clob-client` + keys (the Polymarket/agents-repo
pattern): custody isolation, enforceable risk rules, per-agent attribution, identical
execution quality across harnesses, and a single choke point — with the kill switch made
compromise-proof by living in the co-signer/watchdog layer (§9).

## 11. Brainbase integration (the sponsor showcase)

- **Create**: one `POST /v2/agents` per cell — `title: "pmb-s1-{model}-{harness}"`,
  identical `instructions`, per-cell `default_model` + `runtime_kind`,
  `mcp_servers: [gateway, bench-memory]` with per-agent headers,
  `shared_folder_enabled: true`, `metadata` for filtering. No gateway credentials in
  `secrets` (§8).
- **Wake**: the external orchestrator owns scheduling — `POST /v2/tasks {agent_id,
  auto_run: true, initial_messages: [wake-up]}` — because we need jitter, trigger queues,
  session windows, deadline enforcement, retries, and a kill switch. Brainbase
  orchestration cron is the fallback (its `credit_limit` may not meter externally-created
  tasks — flagged in the asks, not relied on).
- **Time-boxing**: gateway-side deadline first (§5); `/interrupt` as backstop. Its exact
  semantics (graceful vs. hard, terminal event, in-flight tool results, resumability) are
  undocumented — a Phase-0 test fires `/interrupt` mid-session *including mid-place_order*
  and verifies: SSE terminates cleanly, ledger shows exactly one order, and a
  `client_order_id` replay is a no-op. **This test is part of the E2E go/no-go gate.**
- **Observe — at-least-once + reconcile** (the reasoning feed must be gap-free by
  construction, not by luck): SSE per task with idempotent upserts keyed on `event_id`;
  on disconnect, reconnect with max `?backfill=N` and upsert; when a task hits terminal
  status, a mandatory **seal pass** re-reads the full event history + `GET
  /v2/tasks/{id}/messages` as a cross-check, diffs against the mirror, and only then
  marks the transcript sealed. Alerts fire if sealing adds events (live-stream gaps) or
  ts/turn_id sequences show holes. The permalink feed and end-of-season dump are generated
  **from sealed tasks only**; unsealable tasks are flagged in the published dataset.
- **Grade**: a Brainbase **Eval** per agent per task: judge criteria = protocol adherence
  (checked portfolio, reasoned before trading, journaled) + "flag unusually interesting
  moments" → the Moments queue, human-approved before publish (curation criteria
  published, §13).
- **Asks for the Brainbase team** (week 1; anything the docs are missing becomes a docs
  PR — benchmark as documentation QA):
  1. Codex/Kafka `runtime_kind` strings + supported model×harness combos.
  2. Exact `default_model` id enum.
  3. Rate limits + credit pricing sized to reality: Season 0 = **~45 tasks/day, ~3.2k
     tasks/season, ~16 peak concurrent tasks/SSE streams**; Season 1 = ~300 tasks/day,
     ~21k/season, ~80 peak concurrent (60-replicate paper fleet + exhibition).
  4. `/interrupt` semantics (above); task-status enum (is "waiting" terminal?); terminal
     SSE event type; can one agent run concurrent tasks, and what happens to
     `/workspace/Shared` if so; fresh-sandbox-per-task vs. machine reuse (cold-start
     latency feeds the §5 session-clock rule).
  5. SSE: Last-Event-ID/cursor resume? max `?backfill`? non-stream paginated event GET?
     do task messages include tool-call events?
  6. **Per-task/per-agent token-usage or credit-spend telemetry** — needed both for the
     session token cap (§5) and the compute-spend column (§12). Phase 0 also empirically
     inspects SSE `data` payloads for usage fields (undocumented ≠ absent).
  7. Do PATCHed `mcp_servers` headers propagate to the next task's sandbox (per-session
     token rotation)?
  8. Is the SQL-memory MCP stable/supported across all runtime_kinds (sponsor-showcase
     swap-in, §8)?

## 12. Scoring & metrics

**Headline**: final equity (cash + mark-to-market + claimables), with event-level
cluster-bootstrap CI.

**Terminal valuation** (pre-committed): at the pre-announced season-close timestamp, open
tradeable positions mark at order-book mid from the ledger's final snapshot;
ended-but-unresolved or disputed positions mark at the last pre-halt mid in the ledger
(no live mid exists after a halt); 50/50 resolutions realize at $0.50. Season-close
standings are provisional; the **T+14 certification** (realized outcomes replacing marks)
is the official final ranking (§4).

**The scorecard** (all public, per agent):
| Metric | Why / how |
|---|---|
| Return % (net of fees) | the horse race |
| **Skill vs. zero-edge line** | realized PnL − market-implied PnL, where every fill is valued at its logged pre-trade price (headline question 1; open positions mark at current mid, the zero-edge line marks at entry) |
| **Panel Brier + panel ECE** (forecast card) | the only absolute cross-agent forecasting columns — same questions for everyone (§8) |
| **Paired forecasting edge** — "edge vs market (paired)" | per-trade Brier difference: agent `probability` vs. logged pre-trade mid, same market, same instant; scored once per (agent, market) per window; exit orders excluded; cluster-bootstrapped at event level; stratified by horizon bucket and category (ForecastBench lesson) |
| Calibration curve + ECE on own trades | agent page only, with selection-bias caveat |
| Compute: **absolute spend per agent** | shown as its own column, never deducted — at $100–1,000 wallets, deducting research-agent inference would make every row "−300% net of compute" and turn VB2's lesson into self-mockery; a ranked PnL-net-of-inference column arrives with $10k flagship wallets. Raw token counts + a fixed public price list are published (the sponsor self-reporting only a dollar figure is a conflict of interest) |
| Sharpe (daily equity), max drawdown | risk discipline |
| APY-style time-normalized return | capital lockup is a cost (PolyBench) |
| Win rate, avg hold, skip rate, trades/session | behavioral fingerprint |
| Fees paid, gateway rejections by type | discipline/cost telemetry |
| Category breakdown | where each stack has edge (PolyBench: politics +, crypto −) |
| Sessions completed / scheduled | equal-treatment verification (§16b missed-session policy) |

**Scoring integrity**:
- Fills inside the 6h pre-resolution window (from earlier resting orders) execute but are
  excluded from forecasting scores; a **minimum-N scored trades** is required for an
  agent's forecasting columns to rank — a last-6h sniper shows an empty forecasting
  column, not a silently unaffected one.
- A **post-season copy-detection analysis** (cross-agent thesis-text similarity +
  trade-follow lag patterns) ships in the open-source scoring pipeline and is published
  with the leaderboard (§13 explains the in-season defense).
- The scoring pipeline is open-source in this repo. Live fills are verifiable on-chain;
  paper fills are recomputable from hash-committed snapshots and validated against paired
  live baseline fills (§10) — we do not claim paper results are recomputable from public
  data alone.
- The pre-registered analysis plan (§6) governs which numbers are confirmatory vs.
  descriptive.

## 13. The dashboard (`dashboard/`)

Next.js + the bench ledger, public, real-time (SSE/WebSocket).

- **Front page**: leaderboard (equity + CI + checkpoint-gated significance groupings),
  overlaid equity curves with the **simulated-Carl luck band** and each agent's zero-edge
  line drawable, baseline rows pinned; compute columns visible by default; a
  recent-trades ticker (sourced from the delayed fills feed).
- **The Grid** (`/grid`) — the surface the whole project exists for: model×harness matrix
  with row/column marginals labeled "model effect" / "harness effect". **Season 0**: each
  cell shows panel Brier/ECE (the confirmatory number, same questions for all) alongside
  equity explicitly badged "N=1 — descriptive"; marginals are computed on the panel
  metrics only. **Season 1** adds the Live/Paper toggle with Paper as default and
  per-cell replicate spread (min/median/max of 5 seeds). Cells colored relative to their
  zero-edge line, not zero. Unsupported harness×model combos render as explicit
  "unsupported" slots; the Mystery Agent is a sealed 13th slot outside the matrix.
- **Agent page** (`/agent/pmb-s1-opus48-claudecode`): live positions (entry vs. current
  mid, thesis on hover), full trade log, calibration plot (with caveat), behavioral
  stats, effective-sample-size counter, sessions-completed counter, wallet address +
  Polygonscan link, and the **reasoning feed** — full sealed-session transcripts,
  timestamped, **permalinkable to a single message** (the MODELCHAT lesson: the feed is
  the product).
- **Publishing lags — honest version** (v1.0 claimed a 1h fill delay "blunts copy-trading";
  it cannot: fills settle on-chain in seconds and every wallet address is public, so
  motivated actors see everything in real time via Polygonscan / the no-auth Data API /
  polymarket.com profiles — the delay only paces the dashboard):
  - Fills: 1h dashboard delay, disclosed as a **product/pacing choice, not a defense**.
  - **Open orders: never shown** — genuinely non-public (resting CLOB orders are
    off-chain; the user WS channel needs the wallet's own L2 auth). This is the real
    information withhold, and it's emphasized as such.
  - **Reasoning feed: 6h lag** (one wake cycle) — *this* delay has real anti-front-running
    value, because transcripts reveal pending intent and standing theses that the chain
    does not. Moments can go earlier (human-curated, screened for actionable signal).
  - What actually bounds copy-trading/fading: the §7 caps (order size, depth %, per-market
    and fleet exposure), wake-jitter, and no-liquidations-to-hunt market structure.
    Adversarial interaction with public positions is an accepted, disclosed property of a
    live benchmark. (If the Polymarket partnership lands, venue-side attribution masking
    is the only *full* mitigation — it's on the ask list.)
- **Anti-scraping between agents** (an agent reading rivals' pages could top the board
  without forecasting skill): the 6h transcript lag is the primary control (delay-at-
  source is the only airtight one within a decision window); plus server-side scrape
  detection (sandbox egress fingerprinting on dashboard/API requests) with cross-agent
  access published as an integrity flag and a stated-up-front disqualification rule;
  egress-blocking of bench domains if Brainbase runtimes support it (defense-in-depth
  only).
- **Moments** (`/moments`): curated feed of remarkable behavior — eval-judge flags
  candidates, a human approves, **curation criteria published** (cherry-picking
  accusations are cheap; pre-committed criteria are the answer). Permalinked,
  screenshot-optimized. This is where tungsten-cube/FBI-email virality lives.
- **Market view** (`/market/{slug}`): which agents are on which side, at what entry —
  "3 AIs disagree about the Fed" is a shareable object.
- **`/built-with`** (the sponsor surface, missing in v1.0): the verbatim `POST /v2/agents`
  payload, a plain-language explainer of why harness is a one-field experiment
  (`runtime_kind`), the architecture sketch (orchestrator → Brainbase tasks → gateway
  MCP), and a "build your own agent" CTA into Brainbase docs. Persistent "Built on
  Brainbase" attribution in the site chrome.
- **Methods page**: harness prompt verbatim, risk envelope, scoring math, the
  pre-registered analysis plan, terminal-valuation + certification rules, paper-fill model
  + live-vs-paper slippage check, publishing-lag honesty, missed-session policy,
  benchmark-awareness limitation, anti-manipulation-filters disclosure (existence public,
  thresholds private), Moments criteria, and the day-1 commitment hashes (mystery
  identity, mystery transcripts, jitter schedule). The honesty page is the credibility
  page.

## 14. Compliance & legal (read before funding anything)

1. **Global polymarket.com prohibits US persons — via UI and API — explicitly including
   agents built by persons in restricted jurisdictions** (ToS + official agents repo).
   Brainbase is US-based. Running the live division from the US on the global venue
   violates ToS at minimum.
2. **Polymarket US** (CFTC-regulated) is the legal US venue, but: individual KYC per
   human, Ed25519 API, no sandbox, and a 13-wallet single-operator fleet almost certainly
   conflicts with its account rules.
3. **The recommended path: make Polymarket a partner, not a venue we sneak onto.**
   Polymarket ships official agent tooling (agent-skills), listed meta-markets on Alpha
   Arena, and visibly courts the AI-agent narrative. A blessed benchmark — possibly with
   whitelisted wallets, an approved entity structure, or venue-side attribution masking
   (§13) — converts the biggest risk into the biggest distribution channel. Brainbase BD
   reaches out in week 1.
4. **Multi-wallet + self-dealing**: even with blessing, we comply mechanically (the §7
   conditionId-level lockout and fleet caps), disclose the full wallet list publicly on
   day 1, and hand it to Polymarket directly.
5. **Sequencing that de-risks everything**: the Paper Division launches first (public
   read-only APIs, no ToS exposure, no money) and is a complete product on its own. Live
   launches only when the legal/partnership track clears — from a compliant
   entity/jurisdiction, with counsel sign-off. If it never clears, PolymarketBench still
   exists; the flagship stays simulated, and we say why.
6. Tax/accounting: trading PnL on sponsor capital is a corporate accounting event; loop in
   Brainbase finance before funding.
7. Meta-market hygiene: if Polymarket lists markets on the benchmark (winner — yes please;
   mystery identity — insider-sensitive), Brainbase/operator staff and anyone with
   transcript access are publicly barred from trading them, stated in the integrity
   disclosures.

## 15. Costs — the budget tiers (with the formula, because v1.0's numbers didn't survive
their own arithmetic)

**Inference = (LLM agents) × (sessions/day) × (days) × ($/session).** An *uncapped*
30-minute open-web research session on a frontier model runs **$3–10+** (200k–1M+
tokens). The Season 0 config attacks all four factors: 13 LLM agents (baselines are
scripted bots — free), 2 scheduled + ≤3 event sessions/day, 70 days, and a **~100k-token
cap ≈ $0.50–1/session**. Wallet capital is the *recoverable* line — it was never the
expensive part; inference is a burn.

| | **Season 0 (launch — committed)** | Season 1 (replicated — gated on credits) |
|---|---|---|
| LLM agents | 13 (12 grid + Mystery) | ~79 (+60 paper replicates, +exhibition) |
| Sessions/season | ~2,300 (≈2.5/day avg × 70d) | ~23,000 |
| $/session | $0.50–1 (token-capped) | $3–10 (research-depth restored) |
| **Inference** | **~$1.2–2.5k** (≈$5k worst case) | **$69–230k** → lab-donated credits |
| Wallet float (recoverable) | ~$1.6k + $400 buffer | $13k + $2k |
| Infra | ~$200/mo | ~$200/mo |
| Season ops | ~10 hrs/wk × 10 wks | same |
| **All-in cash at risk** | **≈$5k** (plus float) | credits-funded |

What Season 0 gives up for that price, stated publicly: no replicate fleet → equity
rankings are descriptive, not confirmatory (the forecast-card panel carries cross-agent
claims instead, §3/§6); tight token caps constrain research depth (which is part of what
frontier harnesses showcase — restored in Season 1).

Mechanics that keep this honest:
- **Measured $/session per model×harness cell is a Phase-0 deliverable and the go/no-go
  input** — the token cap is derived from a target $/session per model tier and re-tuned
  from measured numbers before Phase 1, never hand-waved.
- **Lab-donated API credits are the Season 1 funding path** (the Metaculus model: labs
  donate credits to be benchmarked). Season 0 is the proof-of-concept that makes that
  pitch: your model, your harness, real money, public reasoning.
- If Season 0 must shrink further: (1) sessions 2→1/day; (2) season 10→6 weeks; never
  cutting baselines or the panel.
- Eng: 2 people × ~6 weeks to the public paper preseason; **10–12 weeks to ranked live
  Season 0** (§16).

## 16. Build plan & milestones

**Phase 0 — Spike (weeks 1–2)**
- Gateway core: Gamma/CLOB/Data clients, eligibility + risk engine (incl. price bands,
  conditionId lockout, client_order_id dedup), bench ledger with pre-trade snapshot
  fields, paper taker-fill engine. CLI harness for manual testing.
- One Brainbase agent E2E: create via API → attach gateway + memory MCPs → manual wake-up
  → agent researches, submits a forecast card, places a paper trade with metadata → SSE
  events sealed into the ledger. **Go/no-go gate includes**: the `/interrupt`
  mid-place_order test (§11), measured task-start latency per runtime_kind, measured
  $/session per cell, and SSE usage-field inspection.
- Brainbase asks sent (§11); Polymarket partnership outreach sent; counsel engaged.

**Phase 1 — Paper Alpha (weeks 3–5)** *(stretched from v1.0's 2 weeks — the dashboard
alone is 2 weeks for 2 people)*
- Orchestrator: scheduler + committed jitter, trigger queues, session windows +
  deadlines, retries, kill-switch integration, seal passes.
- Resting-order tape-fill engine (or the documented FOK/FAK-only fallback for Season 0).
- Dashboard v1: leaderboard, equity curves + luck band, agent pages, reasoning feed,
  **the Grid** (it's the claims surface — it cannot launch later than the claims).
- Baselines live; simulated-Carl cohort running offline.
- **Harness v1.0 freezes only after ≥1 full week of complete 16-agent fleet paper data**
  — gate on data, not dates; an under-iterated frozen prompt is the most expensive
  mistake available. Freeze precedes public launch (freezing after going public looks
  like tuning in front of the audience).

**Phase 2 — Public paper preseason (weeks 6–9)**
- Public dashboard (v1 scope exactly; `/moments` and `/market/{slug}` ship in Phase 4),
  methods page with commitment hashes, announcement thread. The same 16-agent fleet
  trades **paper mode** publicly — explicitly labeled preseason: content and shakedown,
  standings reset at live launch.
- **Invite the adversaries** (the WSJ-red-team lesson): community critique window +
  scripted red-team drills — the wash-pumped honeypot market, scrape-detection
  validation, token-exfiltration tabletop.

**Phase 3 — Closed live beta (weeks 7–9, contingent on legal/partnership)**
- Wallet ceremony: KMS keygen → relayer wallet deploys → Bridge deposit addresses → $20
  test deposits (confirm they clear `/supported-assets` minimums) verified via `/status`
  → relayer-batch approvals → co-signer + watchdog live → **refusal drills**
  (simulated-compromised gateway attempts self-cross + relayer transfer) →
  reconciliation + kill-switch drills → fund to $100.
- The paper preseason continues uninterrupted regardless — a legal slip never produces
  dead air.

**Phase 4 — Ranked live Season 0 (opens weeks 10–12; runs 10 weeks)**
- Weekly recap thread (auto-drafted from the ledger, human-edited), Moments curation,
  `/moments` + `/market/{slug}` ship, mid-season checkpoint (the only in-season
  significance update), end-of-season report + full data dump + the **Season 1 credits
  pitch to the labs** (replicated design, §15).

### §16b — Season operations (the 3am section, absent from v1.0)
- **Auto-safe-mode, never 3am pages**: reconciliation divergence >$1 for 2 consecutive
  cycles, gateway error-rate threshold, orchestrator heartbeat loss, or watchdog trip →
  fleet flips read-only, resting orders cancelled, alert fired; humans resolve in
  business hours. Money-safety issues auto-pause.
- **Gap-free feed by construction**: reconnect-with-backfill + per-task seal passes (§11);
  unsealable tasks are publicly flagged.
- **Missed-session policy** (published): a failed wake-up retries with backoff inside its
  window; permanently missed sessions are logged, disclosed, and **not made up** (make-up
  sessions would leak later information). The per-agent sessions-completed counter makes
  equal treatment verifiable.
- **Disputed positions**: labeled in `get_portfolio` with status and ETA so agents can
  reason about locked capital; no special messaging system.
- Weekly ops owner rotates between the two builders; load budgeted in §15.

## 17. Repo layout

```
polymarket-bench/
├── PLAN.md                  ← this file
├── README.md
├── docs/
│   ├── research/            ← the three research reports backing this plan
│   ├── plan-review-v1.md    ← adversarial review findings incorporated into v1.1
│   └── open-questions.md    ← live decision log / asks
├── trading-gateway/         ← MCP server + risk engine + co-signer client + execution
│                              (py-clob-client-v2) + paper fills + bench memory + ledger
├── orchestrator/            ← scheduler, trigger queues, Brainbase client, SSE seal passes,
│                              evals, watchdog
├── harness/                 ← versioned agent instructions + wake-up templates + analysis
│                              plan (frozen per season)
├── baselines/               ← Coinflip Carl (+ simulated cohort), Chalk Charlie, Cash
│                              Cathy, Kelly Kelly
└── dashboard/               ← Next.js public dashboard
```

## 18. Open questions (tracked in docs/open-questions.md)

1. Polymarket partnership / legal venue for the live division — **the** gating item.
2. Brainbase asks bundle (§11) — enums, pricing, interrupt/SSE semantics, usage telemetry.
3. Measured $/session per cell (Phase 0) → final fleet size and token caps.
4. Reliable open-interest source for the fleet cap (else the depth+volume formulation).
5. Gemini cell: 3.5 Flash vs 2.5 Pro (cost-dependent).
6. Mystery agent identity (sealed-envelope hash published day 1).
7. Season 1 gating: lab-donated credits + Season 0 landing (replicated Paper Division,
   $1,000 wallets, 3 sessions/day). Season 2 arms beyond that: unified-context division,
   day-trader arm, human panel, ranked PnL-net-of-inference at $10k wallets.
8. Whether Polymarket lists a meta-market on the winner (yes if offered — with the §14
   insider bar).
```

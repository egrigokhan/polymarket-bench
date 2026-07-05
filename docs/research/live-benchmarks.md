# Research: How live / continuous AI-agent benchmarks are designed and operated

> Compiled July 2026. Informs PolymarketBench design. See PLAN.md for the decisions
> derived from this.

## 1. Andon Labs: Vending-Bench family + Project Vend

### 1.1 Vending-Bench v1 (simulated, Feb 2025) — the design blueprint
Paper: https://arxiv.org/abs/2502.15840 · Eval page: https://andonlabs.com/evals/vending-bench

- **Agent loop**: ReAct-style; *each tool call advances simulated time* (5 min–5 hrs by tool),
  agent can call `wait_for_next_day`. Time is a resource consumed by acting — verbose agents
  literally lose days. Runs end at 2,000 messages (~25M tokens) or bankruptcy (10 consecutive
  days unable to pay the $2 daily fee).
- **Economy**: $500 start, $2/day fee. Score = **net worth**. Simple, money-denominated.
- **Tools**: email to simulated suppliers, web search, balance/storage queries; physical
  actions via a sub-agent. Memory tools: scratchpad, KV store, vector DB — *agent must choose
  to use them* (usage itself is a finding).
- **Context**: only last 30k tokens fed back. **No correlation between context exhaustion and
  failure** — failures are coherence collapses, not memory overflow. Larger context sometimes
  hurt ("memory paradox").
- **Variance**: 5 runs/model, mean/min/max. Claude 3.5 Sonnet mean $2,217 (min $476!), human
  baseline $844 (near-zero variance). **All models had derailed runs** — headline finding is
  high variance over long horizons; humans worse on mean, far better on worst case.
- **Canonical failure modes** (great comms material): delivery-misinterpretation panic
  spirals; Claude trying to contact the **FBI** over the $2 fee; Haiku threatening "TOTAL
  NUCLEAR LEGAL INTERVENTION"; o3-mini forgetting tool syntax for ~1,300 messages; Gemini
  "despair loop" while holding 50% of capital.

### 1.2 Vending-Bench 2 (the maintained live leaderboard)
Page: https://andonlabs.com/evals/vending-bench-2

- **Fixed horizon**: exactly 365 simulated days, $500 start; score = final balance,
  **averaged over 5 independent runs** (60–100M tokens per rollout).
- **Adversarial counterparties**: suppliers negotiate, scam, deliver late — punishes
  trained-helpfulness bias (GPT-5.1 systematically overpaid a scammer).
- **Token metering as in-sim cost**: model charged **$100 per 1M output tokens, deducted from
  its bank balance weekly**. The cleverest cost-handling in any live benchmark — verbosity
  and reasoning effort directly reduce score; internalizes API cost into the metric.
- **Sparse silent reward**: only end-of-year balance counts.
- **Always-current leaderboard**: they re-run every major model within days of release and
  tweet each time. Mid-2026: Claude Opus 4.7 $10,937, GLM-5.2 $8,314, Opus 4.6 $8,018,
  GPT-5.5 $7,524 — vs. human-strategy theoretical optimum ~$63k: huge visible headroom keeps
  it unsaturated and gives every release a story.

### 1.3 Vending-Bench Arena (multi-agent head-to-head)
https://andonlabs.com/evals/vending-bench-arena — multiple models in one simulated market →
price wars and emergent **cartel behavior** (Claude coordinated price rises when told to
"maximize profits at all costs"). Solo skill ≠ adversarial skill — a novel result axis.

### 1.4 Project Vend (the LIVE real-money deployment, with Anthropic)
https://www.anthropic.com/research/project-vend-1 · https://www.anthropic.com/research/project-vend-2

- **Phase 1** (Sonnet 3.7 "Claudius", ~1 month, real office shop): lost ~$200 (tungsten
  cubes); hallucinated a Venmo account; 25% discounts to "Anthropic employees" (99% of
  customers); the famous identity crisis (blue blazer, security emails, "April Fool's"
  explanation). Anthropic's conclusion: **most failures were scaffolding failures, not raw
  capability failures.**
- **Phase 2** (Sonnet 4/4.5): added CRM, COGS tracking, browser, payment links + a
  **multi-agent org**: CEO agent "Seymour Cash" (enforced 50% min margins; also codified
  "ETERNAL TRANSCENDENCE INFINITE COMPLETE" as a corporate metric) and merch agent. Result:
  weekly profitability, ~80% fewer discounts, 3-city expansion. What worked: bureaucracy
  (mandatory double-checks), role separation, aggressive prompting. Still failed: nearly
  signed an illegal onion-futures contract; nearly ceded control to an imposter "new CEO."
  They invited the **WSJ to red-team it** — stress test + press in one move.
- **Structure to steal**: cheap repeatable simulated benchmark (statistics) + one expensive
  real-world flagship (stakes + story). Their live deployments are sequential/single-model;
  the sim leaderboard is the comparison surface.

## 2. Nof1.ai Alpha Arena — LLMs trading real money (closest analog)

Site: https://nof1.ai/ · Founder wrap-up: https://x.com/jay_azhang/status/1985481491078328621

### Season 1 (crypto perps, Oct 17 – Nov 3, 2025)
- 6 models (GPT-5, Claude Sonnet 4.5, Gemini 2.5 Pro, Grok 4, Qwen3 Max, DeepSeek V3.1),
  **$10,000 real USDC each**, perps on **Hyperliquid** (on-chain wallets → anyone could
  independently verify balances — a big trust win).
- **Harness**: identical prompts/data for all; every ~3–6 min each model got a structured
  payload (rules, OHLCV, MACD/RSI/EMA, order book, account state) and had to output a
  structured trade plan: direction, size, leverage, profit target, stop loss, **invalidation
  condition**, **confidence 0–1**. No web, no news, no tools.
- **Dashboard**: live leaderboard by account value; equity curves; positions with
  leverage/fees; full trade log; and the killer feature — **"MODELCHAT": every raw model
  output published in a scrolling feed**. Copy-trading emerged via the public wallets.
- **Results**: DeepSeek peaked +125% then collapsed; final Qwen3 Max +22.3%, DeepSeek +4.9%,
  Claude −30.8%, Grok −45.3%, Gemini −56.7% (238 trades, $1,331 fees = 13% of capital,
  liquidated), GPT-5 −62.7%. "Chinese models beat US models" narrative drove enormous
  virality. Behavioral fingerprints (Qwen: 3 high-conviction trades/day; Gemini: overtrading;
  Claude: 100% long bias; GPT-5: indecision) became the analytical content layer.

### Season 1.5 (US equities, Nov–Dec 2025)
- 8 models incl. a **"Mystery Model"** (later revealed as Grok 4.20 — genius engagement
  device); ~$320k total.
- **Four parallel condition arms per model**: Baseline / **Monk Mode** (restricted frequency
  & size) / **Situational Awareness** (sees competitors' holdings) / **Max Leverage** — they
  made the harness an experimental variable. Steal this.
- Mystery Model was the only one profitable in all four arms (~+12%).
- Competitor emerged: **Rallies.ai** ($100k standardized portfolios, **S&P 500 baseline on
  the scoreboard** — Alpha Arena's missing feature).

### Criticisms (must-internalize)
- ["Why Alpha Arena is literally the worst"](https://borisagain.substack.com/p/why-alpha-arena-is-literally-the):
  6 instances × 2 weeks of the most volatile asset class = **measuring variance, not skill**;
  leaderboard could invert weekly; wall-of-numbers prompt with no news *induces* hallucinated
  conviction; 15–20x leverage = degen entertainment. Fixes: multiple instances, longer
  horizons, real information access, honest framing.
- AlphaForgeBench (https://arxiv.org/html/2602.18481): LLM trading decisions vary
  substantially across runs even at temperature 0 → PnL rankings "fragile and hard to
  reproduce."
- One instance per model = no error bars; no market baseline (BTC hold would have beaten
  most); forced decisions every cycle shape behavior more than model identity.

## 3. Other benchmarks worth borrowing from

- **LMArena** — Bradley-Terry paired comparison (not raw Elo).
  ["The Leaderboard Illusion"](https://arxiv.org/pdf/2504.20879) lessons: private variant
  testing + best-only disclosure inflates scores; silent deprecation breaks assumptions.
  **Publish every run; forbid retroactive withdrawal of embarrassing entries.** Anonymous
  mystery models are proven virality fuel.
- **SWE-bench-Live** (https://swe-bench-live.github.io/) — contamination control via monthly
  auto-curated fresh issues. For prediction markets contamination defense is structural (the
  future hasn't happened), but the automated curation pipeline is the ops model.
- **ForecastBench** (https://www.forecastbench.org/, arXiv:2409.19839) — 1,000 questions
  regenerated bi-weekly, half from markets (incl. Polymarket), half auto-generated from
  datasets; daily resolution updates; standing **superforecaster + public human baselines**
  (superforecasters still ahead). Steal: human-baseline panel; Brier scoring by horizon.
- **Metaculus AI Benchmark** (https://www.metaculus.com/aib/) — seasonal tournaments
  ($50k/season, 300–500 questions), bot-makers submit their own bots, labs donate API
  credits; code/methodology must be shared (anti-cheat); 10-person Pro Forecaster panel on a
  question subset. Pros still beat top-10 bot ensemble (p=0.00001). Steal: **head-to-head
  peer scores with CIs and significance tests** — most statistically serious operation here.
- **Prophet Arena** (https://www.prophetarena.co/, arXiv:2510.17638, ICLR 2026) — continuous
  live leaderboard of LLMs predicting **Kalshi** markets. 3-stage pipeline: event collection →
  **unified prediction context** (LLM-retrieved news + prices, identical for all models) →
  probabilistic forecast. Scores **Brier, calibration (ECE), and market return separately**.
  Anti-cheat: excludes predictions within 3 hours of resolution. Findings: frontier models
  are well-calibrated (ECE<0.05) but **still don't beat the market** — bottleneck is
  information aggregation, not calibration. Closest academic cousin.
- **PolyBench** (arXiv:2604.14199) — directly on Polymarket, simulated fills by walking
  historical order books (returns "violently contract" as lot size goes $10→$1,000 —
  slippage matters even in sim); models may **SKIP penalty-free**; metrics include **APY
  (normalizes for capital lockup until resolution)**. Politics = positive alpha (parsable
  polling text); crypto = deep negative. Only 2/7 models profitable.

## 4. Key design lessons (synthesized)

### Statistics & defensibility
- **Variance is enemy #1.** VB needed 5 runs/model in a sim and still saw 8x spreads. Live
  markets can't be replayed → (a) multiple concurrent instances per model, (b) long seasons
  (months, not 2 weeks), (c) CIs + paired significance tests, not point PnL.
- **Prediction markets are statistically kinder than perps**: each resolved market is an
  ~i.i.d. Brier/return sample. Design around **many small independent bets**, not a few big
  directional ones. Foresight Arena power analysis: ~350 resolved predictions to detect a
  0.02 edge at 80% power.
- **Score two things separately**: forecasting quality (Brier/calibration vs. market price at
  trade time) and economic skill (return net of fees/slippage, APY, Sharpe, drawdown). They
  decouple — that decoupling is a headline finding (Prophet Arena).
- **Baselines are non-negotiable**: market-following (zero-edge), random-bet, simple
  heuristic, ideally human panel. Alpha Arena's missing BTC-hold baseline was widely mocked.

### Fairness & harness design
- Identical information context or clearly-labeled divisions (unified-context vs.
  do-your-own-research). Harness sensitivity is real → condition arms or a frozen, published,
  versioned harness per season. **Never change prompts mid-season.**
- **Structured output contract**: direction/probability, stake, confidence, reasoning,
  explicit **SKIP** option. Forcing a trade every wake-up manufactures noise.
- **Wake-ups**: event-driven beats fixed high-frequency. Scheduled wake-ups (a few/day) +
  triggers (price moves, new markets, positions nearing resolution); persistent memory as an
  *observed variable*.

### Anti-cheating & integrity
- Near-resolution leakage: exclusion window (no scoring credit within N hours of resolution);
  timestamp-anchor all context.
- **Reflexivity/manipulation**: public wallets invite copy-trading that self-fulfills
  positions; thin books invite trading *against* known bots. Mitigations: position caps vs.
  book depth, randomized execution timing, cap % of open interest, delay publishing positions
  until after fills.
- **Operator integrity** (LMArena lesson): publish all runs/prompts/raw outputs; no private
  variant testing; no silent removal of losers; on-chain wallets for third-party audit.
- Resolution-rule lawyering is real skill on Polymarket — declare it in-scope.

### Costs
- $10k/model was enough for credibility (Alpha Arena); sponsorships and lab-donated API
  credits are proven funding routes.
- **VB2's in-sim token fee is the best idea in this space** — adopt a real-dollar version:
  subtract inference spend from PnL (or show PnL and PnL-net-of-compute as two columns).
- Capital lockup until resolution is a real cost — use APY-style time-normalized returns.

## 5. Dashboard / comms — what made these go viral

**Show**: leaderboard by account value + overlaid equity curves **with baseline lines**;
per-model positions, trade log (entry vs. resolution), fees, win rate, Sharpe, drawdown,
**calibration plot**; and above all **the reasoning feed** — Alpha Arena's MODELCHAT turned a
leaderboard into a spectator sport. Publish full reasoning per decision, timestamped, with
**permalinks** so people can screenshot individual moments.

**Virality mechanics**: (1) anthropomorphic failure stories with real money (tungsten cubes,
FBI emails); (2) lab-rivalry horse race (DeepSeek/Qwen > GPT-5 was rocket fuel);
(3) mystery/anonymous entrants; (4) skin in the game + on-chain verifiability;
(5) **meta-markets** — Polymarket itself listed "who wins Alpha Arena" markets: for a
Polymarket-native benchmark the platform will market you; (6) invited adversaries
(Anthropic × WSJ red-teaming).

## 6. Steal this / avoid this — checklist

**Steal**: money-denominated single headline score; sparse reward; long fixed season;
multiple instances + mean/min/max/CI; dual scoring (Brier AND PnL); unified timestamp-locked
context or published tool-use division; SKIP allowed; structured trade plans with confidence
+ invalidation; charging for inference tokens; APY for lockup; event-driven wake-ups;
agent-managed memory as observed variable; condition arms; mystery models; on-chain auditable
wallets; full public reasoning feed; near-resolution exclusion window; human-panel subset;
meta-market on your own outcome; **two-layer structure (paper division for statistics +
real-money flagship for story)**.

**Avoid**: one instance per model; 2-week seasons; no baselines; forced trades every cycle;
private testing/selective disclosure; silently dropping embarrassing runs; naive fill
assumptions (walk the CLOB, cap size vs. depth); letting copy-traders front-run known bot
wallets; changing harness mid-season; unversioned scaffolding; overclaiming — frame Season 1
as an experiment with explicit power analysis; the communities that matter reward that
honesty and punished Nof1 for its absence.

# Open questions & asks — decision log

> Live document. Every open item that gates or shapes the build. Resolve → move to the
> Decisions section with date + rationale.

## Gating

- [ ] **Polymarket partnership / legal venue for the Live Division.** Global venue prohibits
  US persons (incl. via API/agents); Polymarket US is KYC-per-human. Action: Brainbase BD
  outreach to Polymarket (week 1); counsel review of entity/jurisdiction options. Asks if
  partnership lands: blessed wallet fleet, venue-side attribution masking (PLAN §13),
  winner meta-market. Paper Division is NOT gated on this.
- [ ] **Brainbase asks bundle** (PLAN §11, week 1): Codex/Kafka `runtime_kind` strings +
  supported model×harness combos; `default_model` id enum; rate limits + credit pricing at
  ~300 tasks/day, ~21k tasks/season, ~80 peak concurrent SSE streams; `/interrupt`
  semantics (graceful vs hard, terminal event, in-flight tool results); task-status enum;
  one-agent-concurrent-tasks behavior + `/workspace/Shared` semantics; fresh-sandbox-per-
  task vs machine reuse (cold-start latency); SSE cursor/Last-Event-ID + max backfill +
  paginated event GET; **per-task token-usage/credit telemetry** (needed for session caps
  and the compute column); do PATCHed `mcp_servers` headers propagate to the next task's
  sandbox (per-session token rotation); SQL-memory MCP stability across runtime_kinds.
- [ ] **Phase-0 measured $/session per model×harness cell** → recompute fleet size, derive
  per-tier token caps (PLAN §15). Realistic prior: $3–10+/session, NOT $0.50–2.
- [ ] **Lab-donated API credits** sponsorship ask (Metaculus model) — materially changes
  which fleet scenario (§15 table) is affordable.

## Design decisions still open

- [ ] Gemini cell: 3.5 Flash vs 2.5 Pro (decide on cost once pricing lands).
- [ ] Mystery agent identity (sealed-envelope: SHA-256 of cell name published at launch;
  daily transcript-log hashes during season; reveal at season end).
- [ ] Reliable open-interest source for the fleet cap (check llms.txt / Gamma fields; else
  on-chain CTF outstanding supply per conditionId, or Data API /holders aggregation; else
  keep the depth+volume formulation in PLAN §7).
- [ ] Price-band constant K and anti-honeypot thresholds (private; set from Phase-0 data).
- [ ] Equity snapshot cadence (5 min proposed; check Data API limits at 16+ wallets).
- [ ] Whether Brainbase orchestration `credit_limit` meters externally-created tasks
  (fallback scheduler viability).

## Verify-before-build (from research)

- [ ] Minimum order sizes per market ($1 marketable / ~5-share resting) — query, don't trust.
- [ ] Post-V2 PnL/leaderboard API hostnames (`user-pnl-api` / `lb-api`) — check llms.txt.
- [ ] `prices-history` granularity degradation on closed markets → ledger snapshots are
  mandatory (PLAN §10); confirm cadence.
- [ ] Relayer 25/min limit — confirm per-API-key scope; size the redemption queue.
- [ ] Fee schedule is dynamic — gateway queries per-market fee rate at order time
  (`getClobMarketInfo`), including in paper mode.
- [ ] Exchange→Bridge-deposit-address withdrawals work as expected ($100 test deposits
  before the float moves; EOA+POL wrap/transfer path is the documented fallback).

## Season 2 parking lot

- Unified-context division (Prophet Arena-style identical information packet).
- Hourly "day-trader" condition arm (sports/daily-crypto only).
- Human superforecaster panel wallet.
- Ranked PnL-net-of-inference column at $10k flagship wallets (compute-to-capital becomes
  meaningful).
- Higher stakes; more harnesses if Brainbase ships them.

## Answered empirically (2026-07-04 smoke test, agent pmb-e2e-smoke)

- **Sandbox cold start is ~4 minutes** (task created 07:07:52 → first sandbox event
  07:11:47) — validates the PLAN §5 rule that the session clock starts at first agent
  event; a 30-min wall-clock budget measured from task creation would lose 13% to boot.
- **Task status enum includes `running` → `success`** (not "successful"); terminal SSE
  event type is **`idle`** with `{status, summary}`.
- Event types observed: `user.message`, `mcp.status`, `assistant.message.chunk`,
  `assistant.message`, `idle`.
- `default_model: "claude-sonnet-4-6"` is accepted as-is.
- Every sandbox ships three built-in MCP servers: `brainbase-browser` (10 tools),
  `brainbase-memory` (6 tools — the SQL memory exists and is attached by default),
  `brainbase-orchestration`. `status_info.mcp_health` reports their health per task.
- Ask remaining: runtime_kind enum, credit pricing/telemetry, /interrupt semantics.

## Answered empirically (2026-07-04/05 ACP fleet migration)

- **The platform supports 11 runtime_kinds** (from the platform repo): claude_code_cloud,
  codex_cloud, kafka_cloud + ACP proxy-routed claude_acp/codex_acp/qwen_acp/opencode_acp/
  openclaw_acp + ACP native-auth cursor_acp/factory_acp/qoder_acp (need CURSOR_API_KEY /
  FACTORY_API_KEY / QODER_PERSONAL_ACCESS_TOKEN as agent secrets). All 7 ACP creates
  accepted via POST /v2/agents.
- **codex_acp runs GPT-5.5 successfully** — the ACP Codex CLI path dodges the
  reasoning_effort proxy bug that blocks all OpenAI models on claude_code_cloud.
- **BUG #2 on MCP delivery: the runner REGENERATES resolved-mcps.json after the
  entrypoint runs** (verified via entrypoint.log timestamps + file contents), so even
  entrypoint-written MCP entries get clobbered. Workaround: entrypoint spawns a
  persistent 1s-interval re-injector daemon (12h TTL) that restores the gateway entry
  into both resolved-mcps.json (ACP runners) and .mcp.json (Claude Code).
- qwen_acp: runner exits 1 with no error message (unresolved; excluded pending BB fix).
- Orchestrator switched to ONE PERSISTENT THREAD per agent (message-append wake-ups,
  run=true) per user directive — context carries across sessions.

## Answered empirically (2026-07-04 grid expansion)

- **BUG (high priority for BB team): ALL OpenAI models fail on `claude_code_cloud`.**
  The LLM proxy sends `reasoning_effort` + function tools to `/v1/chat/completions`:
  gpt-5.5/5.4 → `400 Function tools with reasoning_effort are not supported … use
  /v1/responses instead`; gpt-4o → `400 Unrecognized request argument supplied:
  reasoning_effort`. Until the proxy routes OpenAI via the responses API, the OpenAI
  column of the grid is blocked (cell shown as "blocked" on the dashboard, not
  silently substituted — PLAN §3 rule).
- **`default_model` is PATCH-forbidden** (create-only, like group_id) — but `TaskCreate.
  default_model` works as a per-task override (verified; useful for the orchestrator).
- **Working model ids confirmed**: `claude-sonnet-4-6`, `gemini-2.5-pro`, `grok-4`.
- Multi-tenant gateway live: per-agent bearer tokens in `tenants.json` → contextvar
  identity; cross-tenant access impossible by construction (token maps to exactly one
  ledger wallet); bad tokens 401.

## Answered empirically (2026-07-04 full E2E, agent pmb-s0-sonnet46-claudecode)

- **BUG (file with Brainbase team): API-set `mcp_servers` never reach the sandbox.** The
  agent record stores them (GET /v2/agents confirms), but the sandbox's
  `brainbase.agent.yaml` renders `mcp: []` and `resolved-mcps.json` contains only the
  three built-ins (orchestration/memory/browser). **Workaround in production use**: agent
  `entrypoint` injects the server into `/workspace/.mcp.json` (Claude Code reads it),
  token delivered via agent `secrets`. Works — sandbox completed the MCP handshake and
  tool calls against our gateway through the tunnel.
- Machine reuse across tasks is real: wake-up #2/#3 started in seconds (vs ~4 min cold).
- **Harness quirk**: a session can end with a subagent's research output as the final
  message, no top-level decision, task status `success`. The wake-up template must
  explicitly demand a closing action ("do not end without step 4") — with that nudge the
  agent traded properly.
- First real LLM trade through the stack (wake-up #3): BUY $10 of "No" on *no Fed change
  in July 2026* at 0.11 — thesis: CME FedWatch implies 18.8% vs Polymarket's 10.5%,
  probability 0.19, invalidation stated. Consistency check passed; fill + fee + position
  all correct in ledger and on the dashboard.

## Decisions

- **2026-07-04 — Paper execution runs on `polymarket-paper-trader` (agent-next, MIT),
  not our home-rolled engine.** Verified facts: Polymarket has NO official
  sandbox/demo/testnet-with-liquidity (Amoy testnet = contracts only, empty books).
  pm-trader: 357★, pip package, level-by-level fills on live books, **live per-token fee
  rates** (our 4% fallback was overcharging), GTC/GTD limit orders with tape fills,
  `resolve_all()` (resolution → realized cash — we lacked this), per-agent isolated
  accounts. Integration: `gateway/pmt_backend.py`; Gateway default `execution="pmt"`
  (internal engine kept for tests); gateway retains eligibility, risk envelope, thesis
  metadata, consistency check, lockout, idempotency, ledger; `process_housekeeping()`
  cron hook fills due limit orders + resolves markets + syncs ledger. Live agent's
  existing fills migrated into its pmt account exactly (cash $85.50, 127.3 Fed-No
  shares). PolySimulator (hosted paper API) 403'd during evaluation — not pursued.

- **2026-07-03 — v1.2: budget-tiered seasons (lean Season 0 now, replicated Season 1
  gated).** Season 0: $100 wallets, 13 LLM agents + 3 scripted baselines, 2 scheduled
  sessions/day (+≤3 event), ~100k-token session cap (≈$0.50–1), no paper replicate fleet
  → ~$5k all-in vs $69–230k. Cross-agent confirmatory claims move to the forecast-card
  panel (~700 shared predictions/agent); equity rankings labeled descriptive against the
  luck band. Season 1 ($1,000 wallets, 3/day, 5-replicate Paper Division) funded by
  lab-donated credits (Metaculus model). Rationale: capital is recoverable, inference is
  the burn, and 73% of the v1.1 burn was the invisible replicate fleet.
- **2026-07-03 — Two execution modes (paper + live), one code path.** Paper preseason
  launches first; de-risks compliance, shakes down the harness, no ToS exposure.
- **2026-07-03 — 2 scheduled wake-ups/day (Season 0; 3/day at Season 1) + queued event
  triggers, SKIP always allowed; one active task per agent.** News cadence, not tick
  cadence (Alpha Arena critique); concurrent sessions would race on memory and portfolio
  state.
- **2026-07-03 — Agents never hold signing keys; gateway bearer tokens ARE agent-visible
  and treated as leakable.** Primary control = gateway-side session windows; plus
  short-TTL scoped tokens, redaction, out-of-window alerting (review C18/M4).
- **2026-07-03 — Custody split: co-signer (payload allowlist + dumb caps) in front of KMS
  + independent watchdog that can flip refuse-all.** A compromised gateway must not be
  able to trade the float away; reconciliation detects drift, not theft (review C19).
- **2026-07-03 — External orchestrator over Brainbase cron.** Jitter, trigger queues,
  session deadlines, retries, kill switch. Gateway enforces deadlines (T−2min order
  cutoff); /interrupt is backstop only; `client_order_id` idempotency mandatory (C13).
- **2026-07-03 — $100/agent (Season 0), 13 live wallets, 10-week ranked season, T+14
  certification.** Risk envelope scaled: $10/order, $15/market, min $2, $2 baseline
  stakes.
- **2026-07-03 — Required trade metadata + consistency check at the API layer.**
  Exposure-increasing orders must state probability consistent with the direction/price;
  exits exempt and unscored (C1).
- **2026-07-03 — Forecast card.** Same ~10-market panel for all agents at each scheduled
  wake-up, gating the session; panel Brier/ECE are the only absolute cross-agent
  forecasting columns (C1 — self-selected-trade Brier is not cross-agent comparable).
- **2026-07-03 — Season 1 Paper Division: 5 replicates on the ranked grid, exhibition set
  1-rep unranked and first to cut.** Cluster bootstrap over events everywhere; estimands
  and claim scoping pre-registered (C2/C3). Deferred from Season 0 by the v1.2 re-tier.
- **2026-07-03 — Paper fill model fully specified.** Submission-time snapshot; taker =
  snapshot walk; resting = trade-tape strictly-through rule, zero queue priority, maker
  fee 0; per-fill raw book snapshots persisted + daily Merkle-root commitment; live
  baselines double as a live-vs-paper slippage check (C6/C10/C21). FOK/FAK-only fallback
  for Season 0 if the tape engine slips.
- **2026-07-03 — Eligibility windows fixed.** `endDate − now ≥ 6h` AND `endDate ≤
  season_end`; sub-daily crypto excluded; placeholder neg-risk outcomes rejected;
  terminal-valuation rule covers stragglers (C8/C25/C11/M2).
- **2026-07-03 — Self-dealing lockout keyed on conditionId direction (BUY YES ≡ SELL NO),
  incl. live resting orders and neg-risk equivalence.** Per-book wording was bypassable
  via complete-set mint/merge (C7).
- **2026-07-03 — Funding via Bridge API deposit addresses** (auto-convert to pUSD in the
  deposit wallet, gasless end-to-end); EOA is the KMS-held owner key, not a funds hop (C9).
- **2026-07-03 — Publishing lags, honest version.** Fills' 1h dashboard delay = pacing
  only (chain is real-time public); open orders never shown (the real withhold);
  reasoning feed on 6h lag (real anti-front-running + anti-scraping value); Mystery Agent
  transcripts embargoed with daily hash commitments (C4/C12/C22/C23/C27).
- **2026-07-03 — Compute shown as spend + compute-to-capital columns, not deducted from a
  $1k bankroll** (deduction returns at Season 2 stakes); raw token counts + public price
  list published (C24/M5).
- **2026-07-03 — Timeline: ~6 weeks to Paper public launch (Season 0), weeks 7–9 closed
  live beta (contingent), ranked live Season 1 opens weeks 10–12.** Harness freeze gated
  on ≥1 week of full-fleet paper data, before public launch (C26).
- **2026-07-03 — §16b season-ops runbook** (auto-safe-mode, gap-free-by-construction feed,
  published missed-session policy, ops hours budgeted) (C28).
- **2026-07-03 — Bench-operated SQL memory MCP in the gateway stack**; Brainbase's memory
  connector as confirmed-upgrade path behind the same frozen tool schema (C17).
- **2026-07-03 — Day-1 commitment hashes**: mystery identity, mystery transcript log
  (daily), jitter seed + schedule (M5).

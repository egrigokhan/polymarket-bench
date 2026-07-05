# Research: Polymarket for programmatic AI-agent trading (July 2026)

> Compiled from official docs, GitHub, and press. Facts current as of 2026-07-03.
> Uncertain items are flagged inline and collected at the bottom.

## 0. The 2026 landscape in one paragraph

Two things changed recently that invalidate most older tutorials. **(1)** There are now
**two separate Polymarkets**: the global, crypto-native `polymarket.com` (no KYC, geoblocked
for US IPs) and the CFTC-regulated **Polymarket US** (`polymarket.us`, launched Dec 2025 via
the $112M QCX acquisition, full KYC, its own totally different API). **(2)** On **April 28,
2026** the global platform executed a full exchange upgrade to **CLOB V2**: new smart
contracts, a rewritten matching engine, and a new collateral token — **pUSD** (ERC-20 on
Polygon, 1:1 USDC-backed onchain) — replacing USDC.e. **V1 clients (`py-clob-client`,
`@polymarket/clob-client`) no longer work against production**; use `py-clob-client-v2` /
`@polymarket/clob-client-v2` / the Rust SDK.
Sources: [V2 migration guide](https://docs.polymarket.com/v2-migration),
[upgrade notice](https://help.polymarket.com/en/articles/14762452-polymarket-exchange-upgrade-april-28-2026),
[CoinDesk](https://www.coindesk.com/markets/2026/04/06/polymarket-reveals-a-full-exchange-upgrade-to-take-control-of-its-own-trading-and-truth).

## 1. Trading APIs (global platform)

| API | Base URL | Auth | Purpose |
|---|---|---|---|
| CLOB API | `https://clob.polymarket.com` | none (read) / L1+L2 (trade) | Orderbooks, prices, order placement/cancel, trades |
| Gamma API | `https://gamma-api.polymarket.com` | none | Market/event metadata, discovery, tags, search |
| Data API | `https://data-api.polymarket.com` | none | Positions, trades, activity, holders, portfolio value |
| Bridge API | (see docs) | wallet-scoped | Multi-chain deposits/withdrawals → pUSD |
| Relayer | (via SDK) | Relayer API key | Gasless onchain ops (approvals, redeem, transfers) |
| WebSockets | market (public) / user (L2) / RTDS | | Real-time books, fills, order status |

Docs index (machine-readable, agent-friendly): https://docs.polymarket.com/llms.txt
Architecture: hybrid-decentralized — off-chain matching, on-chain atomic settlement on
Polygon; orders are EIP-712 signed messages, operator is non-custodial.

### Authentication ([docs](https://docs.polymarket.com/api-reference/authentication))
- **L1 (private key)**: EIP-712 signature. Needed to create/derive API creds and sign orders.
- **L2 (API creds)**: `apiKey/secret/passphrase` via `create_or_derive_api_key()`; HMAC-SHA256
  signed requests. Required for order posting/cancel and private data. Keys survived V2.
- **Signature types**: `0` EOA, `1` Poly-Proxy (email/Magic), `2` Gnosis Safe (browser wallet),
  `3` **POLY_1271 deposit wallets — recommended for new programmatic users** (ERC-1271).
- Read endpoints (books, prices, Gamma, Data API) need **no auth**.

### Clients (V2 — mandatory since 2026-04-28)
- Python: `pip install py-clob-client-v2` — https://github.com/Polymarket/py-clob-client-v2
- TypeScript: `npm install @polymarket/clob-client-v2 viem`
- Rust: `cargo add polymarket_client_sdk_v2 --features clob`
- V2 breaking changes: options-object constructors (`chainId`→`chain`); order struct dropped
  `nonce/feeRateBps/taker/expiration`, added `timestamp (ms)/metadata/builder`; EIP-712
  domain version `"2"`; new Exchange contract addresses; builder attribution via plain
  `builderCode` field.

### Order types & placement ([orders overview](https://docs.polymarket.com/trading/orders/overview))
- **GTC** (resting limit), **GTD** (expires at UTC ts; ≥ ~1-min buffer), **FOK** (all-or-nothing
  market order; BUY in dollars, SELL in shares), **FAK** (partial fill, remainder cancelled),
  **post-only** flag.
- Flow: `createAndPostOrder({tokenID, price, size, side}, {tickSize, negRisk}, OrderType.GTC)`.
  Batch `POST /orders` max **15 orders/request**.
- **Tick sizes**: 0.1 / 0.01 / 0.001 / 0.0001 (+0.0025 World Cup special). Query
  `getTickSize(tokenID)`; wrong tick ⇒ `INVALID_ORDER_MIN_TICK_SIZE`.
- **Minimums** (⚠ verify per market): ≥ **$1 pUSD notional** for marketable orders; ~**5-share
  minimum** for resting limit orders (from Polymarket agent-skills/community docs).
- Order statuses: `live/matched/delayed/unmatched`; trades `MATCHED → MINED → CONFIRMED`
  (or `RETRYING → FAILED`).
- Common errors: `INVALID_ORDER_NOT_ENOUGH_BALANCE`, `FOK_ORDER_NOT_FILLED_ERROR`,
  `INVALID_POST_ONLY_ORDER`, `MARKET_NOT_READY`.

### Rate limits ([docs](https://docs.polymarket.com/api-reference/rate-limits.md))
Generous: Gamma 4,000 req/10s general; Data API 1,000/10s (`/positions` 150/10s); CLOB
general 9,000/10s; `/book|/price|/midpoint` 1,500/10s; `/prices-history` 1,000/10s.
Trading: `POST/DELETE /order` 5,000/10s burst, 120k/10min sustained. **Relayer `/submit`
only 25/min.** Excess is throttled/queued (Cloudflare), not banned.

## 2. Wallets & funding

### Collateral: pUSD (not USDC.e anymore)
All trading collateral is **pUSD**, wrapped 1:1 from USDC/USDC.e via the Collateral Onramp
contract (`wrap()`); withdrawal unwraps to native USDC. Backing enforced onchain.

### Wallet models
- **Deposit wallets (sig type 3)** — recommended for bots: per-user ERC-1967 proxy,
  auto-deployed by factory, holds pUSD + conditional tokens.
  **Gotcha:** pUSD in the owner EOA does NOT count as buying power — it must be in the
  deposit wallet, and **approvals must be executed from the deposit wallet via relayer
  batches**, not `approve()` from the EOA. Flow: transfer pUSD in → relayer-batch approvals
  → sync via balance-allowance update endpoint.
  ([deposit-wallets](https://docs.polymarket.com/trading/deposit-wallets.md))
- **Proxy wallet (1)** / **Gnosis Safe (2)** — what website accounts use.
- **Plain EOA (0)** — supported; you pay own gas + manage approvals (pUSD ERC-20 approval +
  CTF ERC-1155 `setApprovalForAll` to Exchange/NegRiskAdapter).

### Gas
Effectively **none needed**: the [Relayer](https://docs.polymarket.com/trading/gasless.md)
makes wallet deploy, approvals, CTF split/merge/**redeem**, and transfers gasless (Polymarket
pays POL). Needs a Relayer API key (`RELAYER_API_KEY` + `RELAYER_API_KEY_ADDRESS`). Only raw
type-0 EOA flows need POL.

### Funding a programmatic account
1. **Typical**: buy USDC on exchange (Coinbase supports native Polygon withdrawals) → withdraw
   to bot address on Polygon → wrap to pUSD → approve → trade.
2. **Official Bridge API**: per-wallet deposit addresses for 15+ chains (Ethereum, Arbitrum,
   Base, Optimism, Solana, Bitcoin, Tron…); incoming USDC auto-converts to pUSD.
   `POST /deposit` → check `/supported-assets` (per-asset minimums; below-minimum deposits are
   dropped) → send → poll `/status/{address}`. >$50k from non-Polygon chains: use DeBridge /
   Across / Portal. Mis-sent funds: recovery.polymarket.com.
3. **No Polymarket fee on deposits/withdrawals.**

### Fees (introduced 2026 — matters for benchmark economics)
- **Maker: always free. Taker-only**: `fee = shares × feeRate × p × (1−p)` (peaks at p=0.5),
  set **by the protocol at match time** (V2: not in signed orders; query per-market via
  `getClobMarketInfo()` / fee-rate endpoint).
- Current schedule ([help](https://help.polymarket.com/en/articles/13364478-trading-fees)):
  feeRate **crypto 0.07, sports 0.03, finance/politics/tech/mentions 0.04,
  economics/culture/weather/other 0.05, geopolitics/world events 0** (fee-free).
  At 50¢: sports ≈ $0.75 per 100 shares, crypto ≈ $1.75 per 100 shares.
- Taker fees fund a maker-rebate program (~20–25%) + tiered taker rebates.
- Rolled out Jan–Mar 2026; **actively evolving — always query, never hardcode.**

## 3. Account & compliance constraints

- **US status**: global `polymarket.com` remains **geoblocked for US IPs and prohibited for US
  persons via UI AND API** — the ToS and official agents repo say this explicitly, "including
  agents developed by persons in restricted jurisdictions." The legal US venue is
  **Polymarket US** (QCX LLC, CFTC-licensed DCM/DCO): launched Dec 2025, waitlist removed
  May 2026, iOS-first, **full KYC** (govt ID, SSN, address, liveness).
- **Polymarket US has its own API**: ~23 REST + 2 WS endpoints, **Ed25519 request signing**
  (not EIP-712/HMAC), SDKs [`polymarket-us-python`](https://github.com/Polymarket/polymarket-us-python)
  / [`polymarket-us-typescript`](https://github.com/Polymarket/polymarket-us-typescript),
  docs [docs.polymarket.us](https://docs.polymarket.us/api-reference/authentication).
  Full KYC required; **no sandbox mode**. US taker fee reported ~1bp initially.
- **Global platform KYC**: none for normal use; sanctions/wallet screening applies; ~180
  countries accessible; 33+ restricted (France, Belgium, Poland, Italy, Singapore…). VPN
  circumvention → freeze/termination risk.
- **Bots are explicitly fine** — the CLOB API exists for automated trading, and Polymarket
  publishes its own agent tooling. Prohibited (**[Market Integrity Rules](https://integrity.polymarket.com/)**,
  Mar 2026, both venues): fraud, wash trading, spoofing, **self-dealing**, front-running,
  insider/information misuse, disruptive practices. Enforcement: real-time surveillance,
  Chainalysis/Palantir, wallet bans, law-enforcement referrals.
- **Multiple wallets per operator**: ⚠ not explicitly addressed anywhere found. Technically
  trivial and common, BUT **self-dealing/wash-trading between your own wallets is
  prohibited**. Read full ToS / talk to Polymarket before running a fleet.

## 4. Market mechanics relevant to a benchmark

### Resolution horizons (distribution)
- **Ultra-short crypto**: 5-min / 15-min / hourly / 4-hour / daily BTC/ETH "Up or Down" +
  price targets — resolve continuously on price feeds. Same-day ground truth, huge sample
  sizes; highest fee tier (0.07) and bot-dominated books.
- **Sports**: resolve within hours of game end; daily volume workhorse (fee 0.03).
- **Weekly/monthly**: econ prints, mentions markets, earnings, weather.
- **Long-horizon**: elections/geopolitics — weeks to years (currently fee-free).
- PolyBench snapshot: ~38.7k live binary markets across ~5k events in one week; short-dated
  crypto/sports dominate market count.

### Resolution process ([docs](https://docs.polymarket.com/concepts/resolution.md))
- **UMA Optimistic Oracle**: proposer posts outcome + **$750 bond**; **2-hour challenge
  window**; undisputed → resolves (~2h total after proposal). One dispute → second round;
  two disputes → UMA token-holder vote (~48h+); disputed paths take **~4–6 days**.
  50/50 resolutions possible. Trading halts at resolution.
- **Winnings redeemable immediately after onchain resolution** — winning CTF tokens redeem
  at $1; programmatic path = gasless relayer [redeem](https://docs.polymarket.com/trading/ctf/redeem.md).
  Rule of thumb: **funds recyclable ~2 hours after an undisputed market ends.**

### Liquidity/spread
Binary CTF tokens, prices $0.001–$0.999; YES/NO complementary (buy NO ≡ sell YES). Deep and
tight (1–2 ticks) on flagship politics/sports/crypto; thin (multi-cent spreads) on long tail —
check `/book` depth before sizing. Gamma exposes `liquidity`, `volume_24hr`, `competitive`
sort keys. One 2026 analysis claims ~30% of flow is LLM-agent-driven (⚠ unverified vendor claim).

### Negative-risk (multi-outcome) markets ([docs](https://docs.polymarket.com/advanced/neg-risk.md))
Multi-candidate events use the **NegRiskAdapter**: 1 NO in any outcome converts atomically to
1 YES in every other. Gamma exposes `negRisk` boolean; **you must pass `negRisk: true` in
order options or orders fail**. "Augmented" neg-risk events include placeholder outcomes —
only trade named outcomes.

## 5. Data access (markets, prices, positions, PnL)

### Market discovery — Gamma
`GET /events`, `GET /markets` (+ `/slug/{slug}`, `/tags`, `/sports`, `/public-search`);
filters `active=true&closed=false`, `tag_id`, `order=volume_24hr|liquidity|end_date`,
pagination. Key fields: `conditionId`, `clobTokenIds` (the two outcome token IDs you trade),
`negRisk`, `minimum_tick_size`, volumes/liquidity.

### Prices/books — CLOB (public)
`GET /book`, `/books`, `/price`, `/midpoint(s)`, `/spread`, tick-size, and
`GET /prices-history?market=<token_id>&interval=1m|1h|6h|1d|1w|max&fidelity=<min>&startTs/endTs`
→ `{"history":[{"t":ts,"p":price}]}`.
**Gotcha**: for resolved/closed markets prices-history often degrades to ~12h granularity or
empty ([issue #216](https://github.com/Polymarket/py-clob-client/issues/216)) — snapshot
prices live if the benchmark needs fine-grained history. WS market channel for real-time
books; user channel for fills.

### Positions & PnL — Data API (`https://data-api.polymarket.com`, no auth)
- `GET /positions?user=0x...` — holdings with `sizeThreshold`, `redeemable`, `mergeable`,
  filters, sortBy `CASHPNL|PERCENTPNL|CURRENT|...`, limit ≤500. Also `/closed-positions`.
- `GET /value?user=0x...` — **total USD value of positions (one-call mark-to-market).**
- `GET /trades`, `GET /activity` (TRADE/SPLIT/MERGE/REDEEM/REWARD/CONVERSION),
  `GET /holders?market=<conditionId>`.
- **PnL/leaderboard APIs** exist (rate-limit page confirms; community docs reference
  `user-pnl-api.polymarket.com` and `lb-api.polymarket.com`) — ⚠ exact current hostnames
  post-V2 uncertain; verify against https://docs.polymarket.com/llms.txt.
- Every wallet has a public profile page on polymarket.com with positions/PnL — linkable
  from a public benchmark.

### Third-party PnL dashboards
[polymarketanalytics.com/traders](https://polymarketanalytics.com/traders),
[polywallet.app](https://polywallet.app/), [predicts.guru/checker](https://www.predicts.guru/checker),
Dune ([filarm/polymarket-activity](https://dune.com/filarm/polymarket-activity),
[genejp999/polymarket-leaderboard](https://dune.com/genejp999/polymarket-leaderboard)), Bitquery.

## 6. Existing "AI agents on Polymarket" projects

**Official:**
- **[Polymarket/agent-skills](https://github.com/Polymarket/agent-skills)** — current official
  agent integration (2026): progressive-disclosure skill pack (SKILL.md + authentication.md,
  order-patterns.md, market-data.md, websocket.md, ctf-operations.md, bridge.md, gasless.md)
  targeting LLM agents. **Best starting point in 2026.**
- **[Polymarket/agents](https://github.com/Polymarket/agents)** — original official Python
  framework (3.7k stars) — **archived May 2026, pre-V2; reference only.**

**Community:** [artvandelay/polymarket-agents](https://github.com/artvandelay/polymarket-agents)
(MCP server + Claude bot, SQLite), [Dhaiwat10/polymarket-ai](https://github.com/Dhaiwat10/polymarket-ai)
(multi-agent battles + dashboard), [BlockRunAI/polymarket-agent](https://github.com/BlockRunAI/polymarket-agent),
[xiaods/poly-agents](https://github.com/xiaods/poly-agents),
[llSourcell/Poly-Trader](https://github.com/llSourcell/Poly-Trader).
**NautilusTrader has a first-class Polymarket adapter**
([docs](https://nautilustrader.io/docs/latest/integrations/polymarket/)) — production-grade
order management if needed.

**Directly relevant benchmarks:**
- **PolyBench** ([arXiv:2604.14199](https://arxiv.org/abs/2604.14199)) — 38,666 Polymarket
  binary markets, timestamp-locked CLOB states + news, 7 LLMs, 36k predictions, simulated
  order-book execution; only 2/7 models profitable; metrics: directional accuracy,
  confidence-weighted return, APY, Sharpe.
- **Prediction Arena** ([arXiv:2604.07355](https://arxiv.org/pdf/2604.07355)).
- **Foresight Arena** ([arXiv:2605.00420](https://arxiv.org/abs/2605.00420)) — power analysis:
  **detecting a 0.02 forecasting edge at 80% power needs ~350 resolved predictions.**

## 7. Key uncertainties / verify before building

1. Exact minimum order sizes ($1 marketable / 5-share resting) — query per market.
2. PnL/leaderboard API hostnames post-V2.
3. Multiple-wallets-per-operator policy — ask Polymarket directly.
4. Fee schedule actively evolving — query `getClobMarketInfo()`, never hardcode.
5. "30% of volume is LLM agents" and similar vendor claims are unverified.
6. **Legal**: US-based operator on global polymarket.com violates ToS; compliant paths are
   Polymarket US (Ed25519 API, KYC'd human owner) or operating from a non-restricted
   jurisdiction/entity.

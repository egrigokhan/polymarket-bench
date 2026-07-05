# baselines/

Non-LLM baseline traders, run as real wallets in both divisions (PLAN.md §3):

- **Coinflip Carl** — random eligible market, random side, $2 marketable order per
  scheduled wake-up (stakes scale with the wallet tier). Plus `carl-cohort/`: ≥1,000
  offline simulated Carls whose 5–95% band is the luck null on the leaderboard.
- **Chalk Charlie** — favorite-bias harvester: buy the higher-priced outcome if in
  [0.60, 0.95], $2, random eligible market per wake-up. NOT "the market" — see PLAN §3.
- **Cash Cathy** — never trades.
- **Kelly Kelly** *(paper only)* — simple heuristic mispricing bot.

Baselines double as the live-vs-paper slippage check (PLAN §10): every live baseline fill
is also paper-simulated from the same decision, and the divergence distribution is
published on the methods page.

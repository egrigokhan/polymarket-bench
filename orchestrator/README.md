# orchestrator/

Owns the clock and the Brainbase integration (PLAN.md §5, §11):

- **Scheduler** — 3 anchored wake-ups/day per agent with day-1-committed jitter; one
  active task per agent; event-trigger queue (dedup, fire-on-session-end).
- **Brainbase client** — `POST /v2/tasks {auto_run: true}` per wake-up; session deadline
  registration with the gateway (T−2min order cutoff); `/interrupt` backstop; retries;
  kill-switch integration.
- **SSE mirror + seal passes** — at-least-once event ingestion (idempotent on
  `event_id`), reconnect-with-backfill, per-task seal pass diffing against
  `GET /v2/tasks/{id}/messages`. Reasoning feed and data dump come from sealed tasks only.
- **Evals** — per-task judge run (protocol adherence + Moments candidate flagging).
- **Watchdog** (separate host/credentials in production) — on-chain loss-velocity and
  counterparty-concentration monitor that can flip the co-signer to refuse-all (PLAN §9).

Phase 0 scope: manual single-agent wake-up E2E + the `/interrupt` mid-order safety test.

## Spike status (2026-07-04): WORKING

[orchestrator.py](orchestrator.py) + [config.json](config.json):
- Scheduled wake-ups: anchors 08:00/20:00 UTC ± 0–30min **deterministic per-agent
  jitter** (seeded, `jitter_seed` in config — commit-reveal ready).
- Event triggers: position mid moves ≥10¢, market entering final 24h — queued while a
  session is live (one active task per agent, always), capped 3/day.
- Wake-up composition from live gateway state (portfolio, since-last-wake notes).
- Session management: 30-min deadline → `/interrupt` → zombie abandonment at +10min.
- Hourly housekeeping: `Gateway.process_housekeeping` per agent (limit-order tape fills
  + market resolutions via pm-trader).
- Run: `python3 orchestrator.py run` (60s loop) | `once wake` | `once housekeeping` |
  `status`. State in `state.json`. Needs `BRAINBASE_API_KEY` from `../.env`.

Not yet: SSE event mirroring/seal passes into the ledger (dashboard reasoning feed),
forecast card, multi-agent config beyond the one live cell.

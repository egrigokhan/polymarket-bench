# Research: Brainbase Labs API (v2 Managed Agents Service)

> Compiled July 2026 from docs.brainbaselabs.com, the public OpenAPI spec
> (https://api.brainbaselabs.com/openapi.json), and observed Brainbase MCP behavior.
> Gaps the docs don't cover are flagged and collected at the bottom.

## 0. Two API generations — use v2

| | Legacy "Enterprise Agent Platform" | **v2 "Managed Agents Service"** (use this) |
|---|---|---|
| Docs | docs.usebrainbase.com | **docs.brainbaselabs.com** |
| Base URL | brainbase-monorepo-api.onrender.com | **`https://api.brainbaselabs.com`** |
| Auth | `x-api-key` | **`Authorization: Bearer $BRAINBASE_API_KEY`** |
| Model | Workers → Flows in Based DSL → deployments | **Agents = harness in a cloud sandbox, driven via Tasks/Messages/Events** |

Legacy = deterministic conversational agents (phone/SMS/chat). v2 = autonomous-agent OS —
the right platform for a trading agent.

## 1. Creating an agent

**`POST /v2/agents`** — `AgentCreate` body, only `title` required:

```jsonc
{
  "title": "polymarket-trader",           // required, 1-200 chars
  "instructions": "…system prompt…",
  "runtime_kind": "claude_code_cloud",    // the HARNESS; default "claude_code_cloud"
  "machine_kind": "daytona",              // sandbox provider
  "default_model": "claude-sonnet-4-6",   // model id string
  "mcp_servers": [{ "name", "url", "command", "args", "env", "headers", "is_enabled" }],
  "skills": [{ "source": "..." }],
  "secrets": { "GATEWAY_TOKEN": "..." },  // planted into EVERY sandbox as plain env vars
  "metadata": { "k": "v" },               // filter lists via ?metadata=key:value
  "shared_folder_enabled": true,          // persistent /workspace/Shared across task sandboxes
  "group_id": "uuid",
  "template_slug": "creator/slug",        // instantiate from template
  "entrypoint": "bash snippet"            // runs after env load, before runner; cwd=/workspace
}
```

Full CRUD: `GET /v2/agents`, `GET/PATCH/DELETE /v2/agents/{agent_id}`.

- **Model per agent AND per task**: `default_model` on the agent; `TaskCreate.default_model`
  overrides per task. Supported model families (docs): OpenAI GPT-5.5/5.4/5.2/5/Mini/Nano,
  GPT-4o; Anthropic Opus 4.8/4.7/4.6/4.5, Sonnet 4.6/4.5/4, Haiku 4.5; Google Gemini 3.5
  Flash, 3.0 Flash, 2.5 Pro/Flash; xAI Grok 4, Grok 4 Fast. Models ride an internal
  OpenAI-compatible LLM proxy. ⚠ No published enum of exact id strings.
- **Harness per agent**: `runtime_kind`. Documented value: `claude_code_cloud`. CLI docs say
  harnesses map onto **Claude Code, Codex, and Kafka** (Brainbase's in-house harness).
  ⚠ runtime_kind strings for Codex/Kafka unpublished — ask the team.
- **Templates**: `POST /v2/agents/templates` (`team_id`, `creator`, `slug`, `name` required);
  instantiate via `template_slug` on agent create. Addressed `/v2/agents/templates/{creator}/{slug}`.
- **CLI surface**: `/v2/cli/*` used by `@brainbase-labs/cli` (`brainbase login`,
  `agent pull/push` with `brainbase.agent.yaml`, per-agent API keys via
  `POST /v2/cli/agents/{agent_id}/keys`, PATs for CI).

## 2. Talking to an agent — Tasks, Messages, Events

The conversation unit is a **Task** (thread bound to one agent, backed by a sandbox):

1. **`POST /v2/tasks`** — `{ agent_id*, title, parent_task_id, metadata, initial_messages,
   auto_run (default false), default_model }` → Task `{id, status, status_info, sandbox_id,
   machine_id, ...}`. `auto_run: true` starts the runtime immediately.
2. **`POST /v2/tasks/{task_id}/messages`** — `{ messages: [...], run: bool }` → persisted
   messages + `run_started`. This is "send a message and wake the agent."
3. **Read**: `GET /v2/tasks/{task_id}/messages` (poll).
4. **Stream**: **`GET /v2/tasks/{task_id}/events/stream`** — SSE, `?backfill=N` historic
   events, stays open. Event rows: `{event_id, type, ts, started_at, ended_at, tool_id,
   subagent_id, session_id, turn_id, agent_id, task_id, thread_id, orchestration_id, data}`.
   ⚠ event `type` values not enumerated.
5. **`POST /v2/tasks/{task_id}/interrupt`** — stop a running task.
6. Task CRUD: `GET /v2/tasks` (filter `agent_id`, `metadata`, `limit`), `GET/PATCH/DELETE`.
7. **Sandbox files**: `GET .../files`, `/files/tree`, `/files/stat`, `/files/download`,
   `POST .../files/upload`, `/files/folders`, `/files/move`, `DELETE .../files`.

**Everything is async** — no blocking chat-completion endpoint. Poll or hold SSE.

**Webhooks (outbound)**: **Alerts** — `POST /v2/alerts` `{scope_level: team|group|
orchestration|agent|thread, scope_id, event_type, action_type: "webhook", webhook: {url},
enabled}` → HMAC `signing_secret` (returned once); `POST /v2/alerts/{id}/rotate-secret`;
delivery history `GET /v2/alerts/{id}/fires` (pending/delivering/delivered/failed/dead).
⚠ payload shape + valid event_type strings undocumented. Alerts do NOT trigger agents.

**Task statuses**: plain string; informally "running, waiting, successful, failed". ⚠ no enum.

**Surfaces** (non-API channels): Chat web app, Slack, Phone, Meetings. No email surface.

## 3. Tools & capabilities — can it trade on Polymarket? Yes.

Four ways an agent gets capabilities:

1. **`mcp_servers` on the agent** — remote (`url` + `headers` for auth) or local (`command` +
   `args` + `env`) MCP servers. **Expose the trading gateway as a remote MCP server and
   attach it here** — exactly how Brainbase's own phone/meetings/SQL-memory connectors work.
2. **The harness itself** — `claude_code_cloud` = Claude Code in a Daytona sandbox: full code
   execution, shell, outbound HTTP. The agent can `curl`/write Python against any REST API.
3. **`secrets`** — planted into every sandbox as env vars (gateway token etc.).
4. **`entrypoint` + `skills`** — bash bootstrap (clone repo, pip install) + reusable skill
   packages from the registry.

Documented tool categories (`/docs/agent/tools`): Integrations (managed OAuth connectors,
Pipedream-backed, "3,000+ apps"), MCP servers (BYO), Functions (custom scripts).

**Machines**: `POST /v2/machines` (`kind` default `daytona`, optional `agent_id`, `snapshot`),
`GET /{id}/status` (starting/running/**sleeping**/dead/unknown), `GET /{id}/preview?port=`
(transparently resumes sleeping machines), `DELETE`. Machines sleep and resume.

## 4. Memory / state between wake-ups

1. **Memory tables** (documented `/docs/agent/memory`): structured, persistent data across
   tasks — "facts that should survive beyond a single conversation." Positions/theses belong
   here.
2. **SQL memory MCP** (observed, not in public docs): each agent gets an isolated **Postgres
   DB (Neon), provisioned on demand**, exposed as MCP tools: `memory_status`,
   `memory_provision`, `memory_sql` (full DDL+DML), `memory_tables`, `memory_schema`,
   `memory_deprovision`. Agent can `CREATE TABLE positions (...)`, INSERT on trade, SELECT on
   next wake-up. Appears to back the Memory feature.
3. **Shared folder**: `shared_folder_enabled: true` → persistent `/workspace/Shared` in every
   task sandbox; managed via `POST /v2/agents/{id}/shared/provision` +
   `/shared/files/{tree,read,download,upload}`.
4. **Task history**: messages/events/files persist per task; `parent_task_id` links
   follow-ups; you can keep appending to one long-lived task.

Recommended pattern: one agent, SQL memory for positions/theses, each wake-up = new task
whose instructions say "read your memory DB first."

## 5. Scheduling

- **Native, orchestration-level only**: `POST /v2/orchestrations` accepts
  `triggers: [{trigger_type: "schedule", cron_expression*, is_active (default FALSE!),
  node_id, configured_props, edges: [{to_agent_id}]}]`. Cron is **UTC**. To schedule a single
  agent: wrap it in a one-member orchestration with a schedule trigger.
- Trigger types per docs: app events (Pipedream), cron/natural-language schedules, and
  inbound webhooks — the latter explicitly **not shipped yet**.
- **Alternative (simplest today)**: external scheduler calling `POST /v2/tasks`
  (`auto_run: true`) or `POST /v2/tasks/{id}/messages` (`run: true`).

## 6. Limits, pricing, auth, multi-agent

- **Auth**: `Authorization: Bearer $BRAINBASE_API_KEY`. The whole v2 API is also MCP-exposed
  at `https://api.brainbaselabs.com/mcp` (OAuth, RFC 9728) — agents can drive Brainbase
  directly.
- **Limits/pricing: effectively undocumented** — `/api/rate-limits` and `/api/best-practices`
  are stubs. Visible cost primitives: `credit_limit` on orchestrations; machines retained
  "for audit/cost history". ⚠ Get rate limits + credit pricing from the team.
- **Multi-agent orchestration**: `POST /v2/orchestrations` `{group_id*, name*, credit_limit,
  members: [agent uuids], edges: [{from_agent_id, to_agent_id, description, payload_schema}],
  triggers}`. Members must be granted to the group. Orchestration templates mirror agent
  templates. Scope: `GET /v2/teams`, `GET /v2/groups?team_id=`.
- **Evals** (useful as automated review of each trading session):
  `POST /v2/agents/{id}/evals` `{slug, criteria (≤4000 chars), judge_model (default
  claude-sonnet-4-6), judge_type: model|agent, output_shape: binary|rating|classification}`;
  verdicts via `GET /v2/agents/{id}/eval-runs?task_id=`.

## 7. Gaps to resolve with the Brainbase team

- Rate limits, credit pricing, quotas (stub pages).
- Enum values: task `status`, event `type`, alert `event_type`, `runtime_kind` beyond
  `claude_code_cloud` (Codex/Kafka strings), `machine_kind` beyond `daytona`, exact
  `default_model` id strings.
- Alert webhook payload shape + signature header name.
- SQL memory MCP is real but undocumented — confirm it's stable/supported.
- Inbound webhook triggers: announced, not shipped.
- Whether `POST /v2/tasks` provisions a fresh sandbox per task vs. reuses the agent machine.

## Bottom line for PolymarketBench

Create one Brainbase agent per (model × harness) cell via `POST /v2/agents` with the trading
gateway attached as an MCP server + per-agent auth in `headers`; pick model via
`default_model`, harness via `runtime_kind`. Persist positions/theses in agent SQL memory
and/or `/workspace/Shared`. Wake on a cron via a one-member orchestration schedule trigger or
(better for control) an external orchestrator calling `POST /v2/tasks {auto_run: true}`.
Watch via SSE events + alert webhooks; auto-grade each session with Evals. All supported
today; the unknowns are rate limits/pricing and the enum strings above.

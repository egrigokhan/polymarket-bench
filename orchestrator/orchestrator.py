"""PolymarketBench orchestrator — Phase 0/1 spike.

Owns the clock (PLAN §5): scheduled wake-ups (2/day anchored 08:00/20:00 UTC ± jitter),
event triggers (position moves ≥10¢, resolution <24h, fills/resolutions), one active
task per agent, 30-min session deadline via /interrupt, and the hourly housekeeping
cron (limit-order fills + market resolutions via the gateway's pm-trader backend).

Run:  python3 orchestrator.py run                 # the loop (checks every 60s)
      python3 orchestrator.py once housekeeping   # single housekeeping pass
      python3 orchestrator.py once wake           # fire one wake-up now (all live agents)
      python3 orchestrator.py status              # what would happen next

Env (from polymarket-bench/.env): BRAINBASE_API_KEY. Config: orchestrator/config.json.
"""

import json
import os
import random
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "trading-gateway"))

from gateway.config import DEFAULT
from gateway.ledger import Ledger
from gateway.service import Gateway

BB = "https://api.brainbaselabs.com"
CONFIG = json.loads((HERE / "config.json").read_text())
STATE_PATH = Path(os.environ.get("PMB_STATE", HERE / "state.json"))

SESSION_MINUTES = 30
ANCHORS_UTC = CONFIG.get("anchors_utc", [8, 20])          # wake-up anchor hours
JITTER_MINUTES = CONFIG.get("jitter_minutes", 30)
MAX_EVENT_WAKES_PER_DAY = CONFIG.get("max_event_wakes_per_day", 3)
PRICE_MOVE_TRIGGER = 0.10
PRE_RESOLUTION_HOURS = 24


# ------------------------------------------------------------------ plumbing

def bb(method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        BB + path,
        data=json.dumps(body).encode() if body else None, method=method,
        headers={"Authorization": "Bearer " + os.environ["BRAINBASE_API_KEY"],
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        return json.loads(raw) if raw else {}


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"agents": {}, "housekeeping_at": 0}


def save_state(s: dict) -> None:
    STATE_PATH.write_text(json.dumps(s, indent=1))


def log(msg: str) -> None:
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)


def gateway() -> Gateway:
    db = os.environ.get("PMB_DB", str(ROOT / "trading-gateway" / CONFIG["ledger_db"]))
    return Gateway(Ledger(db), DEFAULT)


# ------------------------------------------------------------------ schedule

def jitter_offset(agent_key: str, anchor_hour: int, date_str: str) -> int:
    """Deterministic per-agent-per-anchor jitter in minutes (seed committed via config)."""
    rnd = random.Random(f"{CONFIG['jitter_seed']}:{agent_key}:{date_str}:{anchor_hour}")
    return rnd.randrange(0, JITTER_MINUTES + 1)


def next_scheduled(agent_key: str, after_ts: float) -> float:
    """Next anchored wake-up time (with jitter) strictly after after_ts."""
    t = datetime.fromtimestamp(after_ts, tz=timezone.utc)
    for day_shift in range(0, 3):
        day = t.timestamp() + day_shift * 86400
        d = datetime.fromtimestamp(day, tz=timezone.utc)
        for h in ANCHORS_UTC:
            cand = d.replace(hour=h, minute=0, second=0, microsecond=0)
            cand_ts = cand.timestamp() + 60 * jitter_offset(
                agent_key, h, cand.strftime("%Y-%m-%d"))
            if cand_ts > after_ts:
                return cand_ts
    return after_ts + 86400


# ------------------------------------------------------------------ wake-ups

def compose_wakeup(gw: Gateway, agent: dict, st: dict, trigger: str, notes: list[str]) -> str:
    try:
        gw.ensure_panel()  # shared forecast panel exists before any agent wakes
    except Exception as e:
        log(f"  panel error: {e}")
    pf = gw.get_portfolio(agent["ledger_id"])
    n = st.get("wake_count", 0) + 1
    day = int((time.time() - CONFIG["season_start_ts"]) / 86400) + 1
    since = "; ".join(notes) if notes else "no notable changes"
    lines = [
        f"WAKE-UP #{n} — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} — Season 0 preseason, day {day}",
        f"PORTFOLIO: equity ${pf['equity']:.2f} (cash ${pf['cash']:.2f} + positions ${pf['positions_value']:.2f}) | {len(pf['positions'])} open",
        f"SINCE LAST WAKE: {since}",
        f"TRIGGER: {trigger}",
        f"SESSION BUDGET: {SESSION_MINUTES} min. Steps, in order: (1) get_portfolio; "
        "(2) FORECAST CARD — get_forecast_card, then submit_forecast_card with your "
        "honest probabilities (BUY orders stay locked until you do); "
        "(3) review positions against their invalidation conditions; (4) research; "
        "(5) DECIDE — place_order with thesis/probability/invalidation, or state "
        "\"SKIP: <reason>\" explicitly; (6) one-line journal note. "
        "Do not end the session without step 5.",
    ]
    return "\n".join(lines)


def detect_triggers(gw: Gateway, agent: dict, st: dict) -> list[str]:
    """Event triggers + since-last-wake notes, from the gateway's view of the world."""
    notes = []
    pf = gw.get_portfolio(agent["ledger_id"])
    last_mids = st.get("last_mids", {})
    new_mids = {}
    for p in pf["positions"]:
        key = f"{p['question']}|{p['outcome']}"
        mid = p.get("current_mid")
        new_mids[key] = mid
        prev = last_mids.get(key)
        if prev is not None and mid is not None and abs(mid - prev) >= PRICE_MOVE_TRIGGER:
            notes.append(f"PRICE MOVE: '{p['question'][:50]}' {p['outcome']} mid {prev:.3f}→{mid:.3f}")
        end = p.get("end_date")
        if end:
            try:
                hrs = (datetime.fromisoformat(end.replace("Z", "+00:00")).timestamp() - time.time()) / 3600
                if 0 < hrs < PRE_RESOLUTION_HOURS and key not in st.get("preres_notified", []):
                    notes.append(f"RESOLVING SOON: '{p['question'][:50]}' ends in {hrs:.0f}h")
                    st.setdefault("preres_notified", []).append(key)
            except ValueError:
                pass
    st["last_mids"] = new_mids
    return notes


def fire_wakeup(gw: Gateway, agent: dict, st: dict, trigger: str, notes: list[str]) -> None:
    """One persistent thread per agent per season: the first wake-up creates the task,
    every later wake-up appends a message with run=true — the agent keeps its own
    context across sessions instead of starting cold each time."""
    msg = compose_wakeup(gw, agent, st, trigger, notes)
    task_id = None
    tid = st.get("thread_task_id")
    if tid:
        try:
            bb("POST", f"/v2/tasks/{tid}/messages",
               {"messages": [{"role": "user", "content": msg}], "run": True})
            task_id = tid
        except Exception as e:
            log(f"  thread append failed for {agent['title']} ({e!r}) — starting new thread")
    if not task_id:
        task = bb("POST", "/v2/tasks", {
            "agent_id": agent["brainbase_id"],
            "title": f"{agent['title']} — season 0 thread",
            "auto_run": True,
            "initial_messages": [{"role": "user", "content": msg}],
        })
        task_id = task["id"]
        st["thread_task_id"] = task_id
    st["wake_count"] = st.get("wake_count", 0) + 1
    st["active_task"] = {"id": task_id, "started": time.time(), "trigger": trigger}
    st["last_wake_ts"] = time.time()
    if trigger != "scheduled":
        st.setdefault("event_wakes", []).append(time.time())
    log(f"WAKE {agent['title']} #{st['wake_count']} ({trigger}) thread={task_id}")


def mirror_events(gw: Gateway, agent: dict, task_id: str) -> int:
    """At-least-once mirror of a task's events into the bench ledger (PLAN §11).
    Idempotent on event_id; called every tick for active tasks + once at seal."""
    try:
        res = bb("GET", f"/v2/tasks/{task_id}/events")
    except Exception as e:
        log(f"  mirror fetch error {task_id}: {e}")
        return 0
    items = res if isinstance(res, list) else res.get("items", res.get("events", []))
    new = 0
    for i, e in enumerate(items):
        eid = e.get("event_id") or f"{task_id}:{i}:{e.get('ts')}:{e.get('type')}"
        if gw.ledger.upsert_event(eid, agent["ledger_id"], task_id,
                                  e.get("ts"), e.get("type"),
                                  json.dumps(e.get("data", {}))):
            new += 1
    return new


def check_active_task(gw: Gateway, agent: dict, st: dict) -> None:
    """Poll the active session; mirror its events; interrupt past deadline; seal when
    terminal."""
    at = st.get("active_task")
    if not at:
        return
    n_new = mirror_events(gw, agent, at["id"])
    task = bb("GET", f"/v2/tasks/{at['id']}")
    status = task.get("status")
    if status in ("success", "failed", "fail"):
        # Brainbase status flips to "success" at TURN boundaries, not session end
        # (learned 2026-07-04: sealed a transcript mid-sentence). Seal only after the
        # event stream has been quiet for 2 minutes while status stays terminal.
        if n_new > 0 or "quiet_since" not in at:
            at["quiet_since"] = time.time()
            return
        if time.time() - at["quiet_since"] < 120:
            return
        gw.ledger.seal_task_events(at["id"])
        log(f"SESSION END {agent['title']} task={at['id']} status={status} (sealed after quiescence)")
        st["active_task"] = None
        return
    at.pop("quiet_since", None)  # went back to running — a new turn started
    if time.time() - at["started"] > SESSION_MINUTES * 60:
        if not at.get("interrupted"):
            log(f"DEADLINE {agent['title']} task={at['id']} — interrupting")
            try:
                bb("POST", f"/v2/tasks/{at['id']}/interrupt")
            except Exception as e:
                log(f"  interrupt error: {e}")
            at["interrupted"] = True
        elif time.time() - at["started"] > (SESSION_MINUTES + 10) * 60:
            log(f"ZOMBIE {agent['title']} task={at['id']} — abandoning tracking")
            st["active_task"] = None


# ------------------------------------------------------------------ main loops

def housekeeping(gw: Gateway) -> None:
    conn = sqlite3.connect(os.environ.get("PMB_DB", str(ROOT / "trading-gateway" / CONFIG["ledger_db"])))
    ids = [r[0] for r in conn.execute("SELECT agent_id FROM agents")]
    conn.close()
    for aid in ids:
        try:
            out = gw.process_housekeeping(aid)
            fills, res = out.get("limit_fills", []), out.get("resolutions", [])
            if fills or res:
                log(f"HOUSEKEEPING {aid}: {len(fills)} limit fills, {len(res)} resolutions")
        except Exception as e:
            log(f"HOUSEKEEPING {aid} error: {e}")


def event_wakes_today(st: dict) -> int:
    cutoff = time.time() - 86400
    return len([t for t in st.get("event_wakes", []) if t > cutoff])


def tick(state: dict) -> None:
    gw = gateway()
    if time.time() - state.get("housekeeping_at", 0) > 3600:
        housekeeping(gw)
        state["housekeeping_at"] = time.time()

    for agent in CONFIG["agents"]:
        # Per-agent isolation: one agent's API failure must never block another
        # agent's wake-up (learned 2026-07-04: a wedged clob DNS lookup in
        # detect_triggers silently ate the 20:00 anchors for the whole fleet).
        try:
            st = state["agents"].setdefault(agent["title"], {})
            check_active_task(gw, agent, st)
            if st.get("active_task"):
                continue  # one active task per agent, always

            try:
                notes = detect_triggers(gw, agent, st)
            except Exception as e:
                log(f"trigger detection failed for {agent['title']} ({e!r}) — "
                    "waking on schedule without notes")
                notes = []
            due = next_scheduled(agent["title"], st.get("last_wake_ts", CONFIG["season_start_ts"]))
            if time.time() >= due:
                fire_wakeup(gw, agent, st, "scheduled", notes)
            elif notes and event_wakes_today(st) < MAX_EVENT_WAKES_PER_DAY:
                trigger = "position_move" if any(n.startswith("PRICE MOVE") for n in notes) else "pre_resolution"
                fire_wakeup(gw, agent, st, trigger, notes)
        except Exception as e:
            log(f"agent tick error for {agent['title']}: {e!r}")


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    state = load_state()
    if cmd == "once":
        what = sys.argv[2] if len(sys.argv) > 2 else "housekeeping"
        if what == "housekeeping":
            housekeeping(gateway())
        elif what == "wake":
            gw = gateway()
            for agent in CONFIG["agents"]:
                st = state["agents"].setdefault(agent["title"], {})
                notes = detect_triggers(gw, agent, st)
                fire_wakeup(gw, agent, st, "manual", notes)
            save_state(state)
    elif cmd == "status":
        for agent in CONFIG["agents"]:
            st = state["agents"].get(agent["title"], {})
            due = next_scheduled(agent["title"], st.get("last_wake_ts", CONFIG["season_start_ts"]))
            print(f"{agent['title']}: wakes={st.get('wake_count', 0)} "
                  f"active={bool(st.get('active_task'))} "
                  f"next_scheduled={datetime.fromtimestamp(due, tz=timezone.utc).isoformat()}")
    else:  # run
        log(f"orchestrator up — {len(CONFIG['agents'])} agents, anchors {ANCHORS_UTC} UTC ± {JITTER_MINUTES}m")
        while True:
            try:
                tick(state)
                save_state(state)
            except Exception as e:
                log(f"tick error: {e!r}")
            time.sleep(60)


if __name__ == "__main__":
    main()

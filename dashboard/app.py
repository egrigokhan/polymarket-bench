"""PolymarketBench dashboard — Phase 0 (Flask over the gateway ledger).

Reads the bench SQLite ledger directly, marks positions to live Polymarket mids, and
reconstructs per-agent equity timelines from fills + CLOB price history.
The production Next.js dashboard (PLAN §13) replaces this in Phase 1; the JSON shapes
served at /api/state and /api/timeline are designed to carry over.

Run: python3 app.py   (or via launch.json → preview, name "pmb-dashboard")
Env: PMB_DB=/path/to/bench.db (default: ../trading-gateway/bench-demo.db)
"""

import os
import sqlite3
import sys
import time
from pathlib import Path

from flask import Flask, jsonify, render_template_string, send_from_directory

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "trading-gateway"))

from gateway import clients  # live mids + price history for mark-to-market

DB_PATH = Path(os.environ.get("PMB_DB", ROOT.parent / "trading-gateway" / "bench-demo.db"))
STARTING_BALANCE = 100.0

app = Flask(__name__)


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


_cache: dict[str, tuple[float, object]] = {}


def cached(key: str, ttl: float, fn):
    ts, val = _cache.get(key, (0.0, None))
    if time.time() - ts > ttl:
        try:
            val = fn()
            _cache[key] = (time.time(), val)
        except Exception:
            pass  # keep stale value on API hiccup
    return val


def live_mid(token_id: str) -> float | None:
    return cached(f"mid:{token_id}", 60, lambda: clients.get_midpoint(token_id))


def price_history(token_id: str) -> list[dict]:
    return cached(
        f"hist:{token_id}", 300,
        lambda: clients.get_price_history(token_id, interval="1d", fidelity=10),
    ) or []


def price_at(token_id: str, ts: float, fallback: float) -> float:
    hist = price_history(token_id)
    best = None
    for pt in hist:
        if pt["t"] <= ts:
            best = pt["p"]
        else:
            break
    if best is not None:
        return float(best)
    mid = live_mid(token_id)
    return float(mid) if mid is not None else fallback


# ------------------------------------------------------------------ state

def build_state() -> dict:
    conn = db()
    agents = []
    for a in conn.execute(
            "SELECT * FROM agents WHERE COALESCE(is_demo,0)=0 ORDER BY created_at"):
        positions = []
        pos_value = 0.0
        for p in conn.execute("SELECT * FROM positions WHERE agent_id=?", (a["agent_id"],)):
            mid = live_mid(p["token_id"])
            value = (mid or 0) * p["shares"]
            pos_value += value
            positions.append({
                "question": p["question"],
                "outcome": p["outcome"],
                "shares": round(p["shares"], 2),
                "cost_basis": round(p["cost_basis"], 2),
                "mid": mid,
                "value": round(value, 2),
                "upnl": round(value - p["cost_basis"], 2),
            })
        orders = [
            {
                "time": o["created_at"],
                "question": o["market_question"],
                "side": o["side"],
                "size_usd": o["size_usd"],
                "status": o["status"],
                "reject_reason": o["reject_reason"],
                "thesis": o["thesis"],
                "probability": o["probability"],
            }
            for o in conn.execute(
                "SELECT * FROM orders WHERE agent_id=? ORDER BY created_at DESC LIMIT 12",
                (a["agent_id"],),
            )
        ]
        feed = []
        try:
            rows = conn.execute(
                "SELECT ts, type, data, created_at FROM agent_events WHERE agent_id=? "
                "ORDER BY created_at DESC LIMIT 60", (a["agent_id"],)).fetchall()
            import json as _json
            for r in reversed(rows):
                d = _json.loads(r["data"] or "{}")
                t = r["type"] or ""
                if t == "assistant.message":
                    txt = " ".join(c.get("content", "") for c in d.get("content", [])
                                   if isinstance(c, dict) and c.get("type") == "text").strip()
                    if txt:
                        feed.append({"kind": "say", "ts": r["ts"], "text": txt})
                elif t.endswith("tool_call.start") and "polymarket" in (d.get("name") or ""):
                    name = d.get("name", "").split("__")[-1]
                    import json as _j
                    feed.append({"kind": "tool", "ts": r["ts"],
                                 "text": f"{name} {_j.dumps(d.get('args', {}))[:110]}"})
                elif t == "idle":
                    feed.append({"kind": "end", "ts": r["ts"],
                                 "text": d.get("summary", "session ended")})
            feed = feed[-14:]
        except Exception:
            pass
        fees = conn.execute(
            "SELECT COALESCE(SUM(fee),0) f FROM fills WHERE agent_id=?", (a["agent_id"],)
        ).fetchone()["f"]
        rejections = conn.execute(
            "SELECT COUNT(*) c FROM orders WHERE agent_id=? AND status='rejected'",
            (a["agent_id"],),
        ).fetchone()["c"]
        last_ev = conn.execute(
            "SELECT MAX(created_at) m FROM agent_events WHERE agent_id=?",
            (a["agent_id"],)).fetchone()["m"]
        equity = a["balance"] + pos_value
        agents.append({
            "agent_id": a["agent_id"],
            "title": a["title"],
            "model": a["model"],
            "harness": a["harness"],
            "cash": round(a["balance"], 2),
            "positions_value": round(pos_value, 2),
            "equity": round(equity, 2),
            "return_pct": round(100 * (equity - STARTING_BALANCE) / STARTING_BALANCE, 2),
            "fees_paid": round(fees, 2),
            "rejections": rejections,
            "positions": positions,
            "orders": orders,
            "feed": feed,
            "last_event_ts": last_ev,
        })
    conn.close()
    agents.sort(key=lambda x: x["equity"], reverse=True)
    return {"generated_at": time.time(), "agents": agents}


# ------------------------------------------------------------------ timeline

def build_timeline(points: int = 72) -> dict:
    """Per-agent equity series: cash flow replayed from fills, positions marked with
    CLOB price history at each step."""
    conn = db()
    agents = list(conn.execute(
        "SELECT * FROM agents WHERE COALESCE(is_demo,0)=0 ORDER BY created_at"))
    if not agents:
        conn.close()
        return {"series": []}
    t0 = min(a["created_at"] for a in agents)
    t1 = time.time()
    span = max(t1 - t0, 600)
    step = span / points

    series = []
    for a in agents:
        fills = list(conn.execute(
            "SELECT * FROM fills WHERE agent_id=? ORDER BY created_at", (a["agent_id"],)
        ))
        pts = []
        for i in range(points + 1):
            t = t0 + i * step
            if t < a["created_at"] - step:
                continue
            cash = STARTING_BALANCE
            n_fills = 0
            # token -> [shares, open cost basis, last fill px]
            holdings: dict[str, list] = {}
            for f in fills:
                if f["created_at"] > t:
                    break
                n_fills += 1
                h = holdings.setdefault(f["token_id"], [0.0, 0.0, f["avg_price"]])
                if f["side"] == "BUY":
                    cash -= f["notional"] + f["fee"]
                    h[0] += f["shares"]
                    h[1] += f["notional"] + f["fee"]
                else:
                    cash += f["notional"] - f["fee"]
                    if h[0] > 1e-9:
                        frac = min(f["shares"] / h[0], 1.0)
                        h[1] *= (1 - frac)
                    h[0] -= f["shares"]
                h[2] = f["avg_price"]
            pos_val = sum(
                h[0] * price_at(tok, t, h[2]) for tok, h in holdings.items() if h[0] > 1e-9
            )
            open_cost = sum(h[1] for h in holdings.values() if h[0] > 1e-9)
            equity = cash + pos_val
            unreal = pos_val - open_cost
            real = (cash - STARTING_BALANCE) + open_cost
            # point: [t, equity, cash, positions value, unrealized, realized, fills]
            pts.append([round(t), round(equity, 3), round(cash, 2), round(pos_val, 2),
                        round(unreal, 2), round(real, 2), n_fills])
        series.append({
            "title": a["title"],
            "model": a["model"] or "",
            "points": pts,
        })
    conn.close()
    return {"start": STARTING_BALANCE, "series": series}


@app.route("/assets/<path:name>")
def assets(name):
    return send_from_directory(ROOT / "assets", name)


@app.route("/api/state")
def api_state():
    return jsonify(build_state())


_swr_lock = {"refreshing": False}


def _refresh_timeline():
    try:
        _cache["timeline"] = (time.time(), build_timeline())
    finally:
        _swr_lock["refreshing"] = False


@app.route("/api/timeline")
def api_timeline():
    import threading
    ts, val = _cache.get("timeline", (0.0, None))
    stale = time.time() - ts > 60
    if val is None:
        # first call ever: compute synchronously
        val = build_timeline()
        _cache["timeline"] = (time.time(), val)
    elif stale and not _swr_lock["refreshing"]:
        _swr_lock["refreshing"] = True
        threading.Thread(target=_refresh_timeline, daemon=True).start()
    return jsonify(val)


PAGE = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PolymarketBench — Season 0</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #fafaf8; --card: #ffffff; --card-2: #fcfcfa;
    --line: #e7e7e2; --rule: #f0f0eb;
    --text: #1a1a1a; --dim: #6f6f76; --faint: #9a9aa0;
    --up: #0f9d6e; --down: #d64550; --warn: #b0821f;
    --up-bg: #eaf6f0; --down-bg: #fbeeef; --warn-bg: #faf3e2;
    --mono: "IBM Plex Mono", ui-monospace, Menlo, monospace;
    --sans: "Inter", system-ui, sans-serif;
    --shadow: 0 1px 2px rgba(20,20,20,.04), 0 4px 14px rgba(20,20,20,.03);
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--text);
         font: 14px/1.5 var(--sans); -webkit-font-smoothing: antialiased; }
  .wrap { max-width: 1180px; margin: 0 auto; padding: 0 32px 72px; }

  header { display: flex; align-items: center; justify-content: space-between;
           padding: 22px 0 8px; }
  .wordmark { font-weight: 700; font-size: 16px; letter-spacing: -0.02em; cursor: pointer; }
  .mast-right { display: flex; align-items: center; gap: 18px;
                font-size: 13px; color: var(--dim); }
  .dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%;
         background: var(--up); margin-right: 7px; }

  .stats-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px;
               padding-top: 18px; }
  .scard { background: var(--card); border: 1px solid var(--line);
           border-radius: 14px; padding: 16px 20px; box-shadow: var(--shadow); }
  .scard .k { color: var(--dim); font-size: 13px; }
  .scard .v { font-size: 26px; font-weight: 600; letter-spacing: -0.02em;
              margin-top: 4px; font-variant-numeric: tabular-nums; }
  .scard .v small { font-size: 14px; font-weight: 500; color: var(--dim); }

  .sec-head { display: flex; align-items: baseline; gap: 12px; padding: 28px 2px 12px; }
  .sec-head h2 { font-size: 15px; font-weight: 600; margin: 0; letter-spacing: -0.01em; }
  .sec-head .meta { color: var(--faint); font-size: 12.5px; }

  .seg { display: flex; gap: 2px; margin-left: auto; background: #f0f0ec;
         border-radius: 9px; padding: 3px; }
  .seg button { border: 0; background: transparent; color: var(--dim); cursor: pointer;
                font: 500 12.5px/1 var(--sans); padding: 6px 12px; border-radius: 7px; }
  .seg button:hover { color: var(--text); }
  .seg button.on { background: #fff; color: var(--text);
                   box-shadow: 0 1px 3px rgba(20,20,20,.08); }

  .chart-box { position: relative; background: var(--card);
               border: 1px solid var(--line); border-radius: 14px;
               padding: 18px 10px 6px; box-shadow: var(--shadow); }
  #chart { width: 100%; height: 320px; display: block; cursor: crosshair; }
  #tip { position: absolute; pointer-events: none; display: none; z-index: 5;
         background: #fff; border: 1px solid var(--line); border-radius: 10px;
         padding: 10px 13px; font-size: 12.5px; line-height: 1.8;
         box-shadow: 0 8px 30px rgba(20,20,20,.12); white-space: nowrap; }
  #tip .t { color: var(--faint); font-family: var(--mono); font-size: 10.5px; }
  #tip .row { display: flex; align-items: center; gap: 9px; min-width: 210px; }
  #tip .row b { margin-left: auto; font-family: var(--mono); font-weight: 500; }
  #tip .sw { width: 8px; height: 8px; border-radius: 50%; }

  .board, .card { background: var(--card); border: 1px solid var(--line);
                  border-radius: 14px; overflow: hidden; box-shadow: var(--shadow); }
  table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
  th { font-size: 12px; font-weight: 500; color: var(--faint); text-align: left;
       padding: 11px 16px; border-bottom: 1px solid var(--line); }
  td { padding: 13px 16px; border-bottom: 1px solid var(--rule); vertical-align: middle; }
  tr:last-child td { border-bottom: none; }
  #leaderboard tbody tr { cursor: pointer; transition: background .12s; }
  #leaderboard tbody tr:hover { background: #f7f7f4; }
  #leaderboard tbody tr.blocked { cursor: default; opacity: .55; }
  .num { text-align: right; font-family: var(--mono); font-size: 13px;
         font-variant-numeric: tabular-nums; white-space: nowrap; }
  th.num { text-align: right; font-family: var(--sans); }
  .equity { font-size: 14px; font-weight: 600; font-family: var(--sans); }
  .up { color: var(--up); } .down { color: var(--down); }
  .chg { display: inline-block; padding: 3px 10px; border-radius: 999px;
         font-size: 12px; font-weight: 500; }
  .chg.up { background: var(--up-bg); }
  .chg.down { background: var(--down-bg); }
  .chg.zero { color: var(--faint); background: #f2f2ee; }
  .arrow { color: var(--faint); font-size: 15px; }

  .who { display: flex; align-items: center; gap: 12px; }
  .who img { width: 20px; height: 20px; object-fit: contain; flex: none; }
  .who .name { font-weight: 600; }
  .who .sub { color: var(--faint); font-size: 12px; margin-top: 1px;
              white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
              max-width: 340px; }
  .badge { display: inline-block; margin-left: 8px; padding: 2px 9px;
           border-radius: 999px; font-size: 11px; font-weight: 600;
           color: var(--warn); background: var(--warn-bg); }
  .rank { font-family: var(--mono); color: var(--faint); width: 30px; }

  .back { display: inline-flex; align-items: center; gap: 6px; color: var(--dim);
          font-size: 13.5px; cursor: pointer; padding: 22px 0 4px; }
  .back:hover { color: var(--text); }
  .agent-hero { display: flex; align-items: center; gap: 16px; padding: 12px 0 20px; }
  .agent-hero img { width: 36px; height: 36px; object-fit: contain; }
  .agent-hero .name { font-size: 22px; font-weight: 700; letter-spacing: -0.02em; }
  .agent-hero .sub { color: var(--dim); font-size: 13.5px; }
  .stats-strip { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; }
  .stat { background: var(--card); border: 1px solid var(--line); border-radius: 12px;
          padding: 13px 18px; min-width: 128px; box-shadow: var(--shadow); }
  .stat .k { color: var(--faint); font-size: 12px; }
  .stat .v { font-size: 18px; font-weight: 600; margin-top: 3px;
             font-variant-numeric: tabular-nums; }
  .card { margin-top: 16px; }
  .card-title { font-size: 13.5px; font-weight: 600; padding: 13px 16px;
                border-bottom: 1px solid var(--line); background: var(--card-2); }
  .thesis { color: var(--dim); font-size: 12.5px; }
  .status-filled { color: var(--up); font-size: 12.5px; font-weight: 500; }
  .status-rejected { color: var(--warn); font-size: 12.5px; font-weight: 500; }
  .muted { color: var(--faint); font-size: 13px; padding: 14px 16px; }
  .feed { padding: 4px 16px 14px; }
  .feed-item { display: flex; gap: 14px; padding: 7px 0; font-size: 13px;
               border-bottom: 1px solid var(--rule); align-items: baseline; }
  .feed-item:last-child { border-bottom: none; }
  .feed-ts { font-family: var(--mono); font-size: 10.5px; color: var(--faint);
             flex: none; width: 42px; }
  .feed-say { color: var(--text); }
  .feed-tool { font-family: var(--mono); font-size: 12px; color: var(--dim); }
  .feed-end { color: var(--dim); font-style: italic; }

  footer { color: var(--faint); font-size: 12.5px; margin-top: 34px; padding-top: 14px; }
  .hidden { display: none; }
  :focus-visible { outline: 2px solid var(--dim); outline-offset: 2px; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="wordmark" onclick="location.hash=''">PolymarketBench</div>
    <div class="mast-right">
      <span><span class="dot"></span>Season 0 · Paper preseason</span>
      <span>Built on Brainbase</span>
    </div>
  </header>

  <div id="home">
    <div class="stats-row" id="stats-row"></div>

    <div class="sec-head"><h2 id="chart-title">Equity race</h2>
      <span class="meta">$100 start · live Polymarket books, simulated fills</span>
      <div class="seg" id="metric-seg"></div></div>
    <div class="chart-box">
      <svg id="chart" role="img" aria-label="Equity timeline"></svg>
      <div id="tip"></div>
    </div>

    <div class="sec-head"><h2>Leaderboard</h2>
      <span class="meta">Click an agent for positions, reasoning, and orders</span></div>
    <div class="board">
    <table id="leaderboard">
      <thead><tr>
        <th class="rank">#</th><th>Model</th>
        <th class="num">Cash</th><th class="num">Positions</th><th class="num">Equity</th>
        <th class="num">Return</th><th>Last activity</th><th></th>
      </tr></thead>
      <tbody></tbody>
    </table>
    </div>
    <footer>
      Paper trading: real Polymarket order books, simulated fills, $100 start. Every
      order requires a thesis, probability, and invalidation condition, enforced
      server-side.
    </footer>
  </div>

  <div id="agent-view" class="hidden"></div>
</div>

<script>
const LABS = [
  [/claude|opus|sonnet|haiku|anthropic/i, { c: "#d97757", logo: "/assets/logo-anthropic.svg" }],
  [/gpt|openai|o[0-9]/i,                  { c: "#0f9d6e", logo: "/assets/logo-openai.svg" }],
  [/gemini|google/i,                      { c: "#4e68f0", logo: "/assets/logo-googlegemini.svg" }],
  [/grok|xai/i,                           { c: "#52525b", logo: "/assets/logo-xai.svg" }],
];
const HARNESSES = [
  [/claude_code/i, { name: "Claude Code" }],
  [/claude_acp/i,  { name: "Claude Code · ACP" }],
  [/codex/i,       { name: "Codex" }],
  [/opencode/i,    { name: "OpenCode" }],
  [/openclaw/i,    { name: "OpenClaw" }],
  [/qwen/i,        { name: "Qwen Code" }],
  [/kafka/i,       { name: "Kafka" }],
];
const MODEL_NAMES = [
  [/claude-sonnet-4-6/i, "Claude Sonnet 4.6"],
  [/claude-opus-4-8/i,   "Claude Opus 4.8"],
  [/gpt-5\.5/i,          "GPT-5.5"],
  [/gemini-2\.5-pro/i,   "Gemini 2.5 Pro"],
  [/grok-4/i,            "Grok 4"],
  [/qwen/i,              "Qwen"],
  [/openclaw/i,          "OpenClaw"],
];
function lab(m) { for (const [re, v] of LABS) if (re.test(m || "")) return v;
  return { c: "#8b5cf6", logo: null }; }
function harness(h) { for (const [re, v] of HARNESSES) if (re.test(h || "")) return v;
  return { name: h || "—" }; }
function displayName(m) { for (const [re, n] of MODEL_NAMES) if (re.test(m || "")) return n;
  return (m || "Unknown").split("—")[0].trim(); }
const isBlocked = m => /blocked/i.test(m || "");
const money = v => v == null ? "—" : "$" + Number(v).toFixed(2);
const fmt = (v, d=2) => v == null ? "—" : Number(v).toFixed(d);
const cls = v => v > 0 ? "up" : v < 0 ? "down" : "zero";
const esc = s => (s || "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const sentence = s => s ? s[0].toUpperCase() + s.slice(1) : s;
const rel = ts => {
  if (!ts) return "—";
  const s = Math.max(0, Date.now() / 1000 - ts);
  if (s < 90) return "just now";
  if (s < 3600) return Math.round(s / 60) + "m ago";
  if (s < 86400) return Math.round(s / 3600) + "h ago";
  return Math.round(s / 86400) + "d ago";
};
const hhmm = t => { const d = new Date(t * 1000);
  return d.getHours().toString().padStart(2,"0") + ":" + d.getMinutes().toString().padStart(2,"0"); };
let lastState = null, lastTimeline = null, chartGeo = null;

const AXIS = "#9a9aa0", GRID = "#efefe9", XHAIR = "#d9d9d2", LEGEND = "#1a1a1a";

const METRICS = [
  { key: "equity",     label: "Equity",     idx: 1, fmt: money, baseline: tl => tl.start, blabel: tl => "$" + tl.start.toFixed(0) + " start" },
  { key: "cash",       label: "Cash",       idx: 2, fmt: money, baseline: tl => tl.start, blabel: tl => "$" + tl.start.toFixed(0) + " start" },
  { key: "positions",  label: "Positions",  idx: 3, fmt: money, baseline: () => null },
  { key: "unrealized", label: "Unrealized", idx: 4, fmt: money, baseline: () => 0, blabel: () => "break even" },
  { key: "realized",   label: "Realized",   idx: 5, fmt: money, baseline: () => 0, blabel: () => "break even" },
  { key: "trades",     label: "Trades",     idx: 6, fmt: v => String(Math.round(v)), baseline: () => null, integer: true },
];
let METRIC = METRICS[0];
function setMetric(key) {
  METRIC = METRICS.find(m => m.key === key) || METRICS[0];
  document.querySelectorAll("#metric-seg button").forEach(b =>
    b.classList.toggle("on", b.dataset.key === METRIC.key));
  document.getElementById("chart-title").textContent =
    METRIC.key === "equity" ? "Equity race" : METRIC.label;
  if (lastTimeline) drawChart(lastTimeline);
}
document.getElementById("metric-seg").innerHTML = METRICS.map(m =>
  `<button data-key="${m.key}"${m.key === "equity" ? ' class="on"' : ""}>${m.label}</button>`).join("");
document.getElementById("metric-seg").addEventListener("click", ev => {
  const b = ev.target.closest("button"); if (b) setMetric(b.dataset.key);
});

function niceStep(range, target) {
  const raw = range / target;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  for (const m of [1, 2, 2.5, 5, 10]) if (raw <= m * mag) return m * mag;
  return 10 * mag;
}

function drawChart(tl) {
  lastTimeline = tl;
  const svg = document.getElementById("chart");
  const W = Math.max(svg.clientWidth, 700), H = 320;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const GUTTER = 235, L = 62, R = GUTTER, T = 18, B = 30;
  const innerW = W - L - R, innerH = H - T - B;
  const series = tl.series.filter(s => s.points.length > 1);
  if (!series.length) { svg.innerHTML = ""; return; }
  const val = p => p[METRIC.idx] ?? 0;
  const base = METRIC.baseline(tl);
  let ts = [], vs = [];
  series.forEach(s => s.points.forEach(p => { ts.push(p[0]); vs.push(val(p)); }));
  if (base != null) vs.push(base);
  const t0 = Math.min(...ts), t1 = Math.max(...ts);
  const rawMin = Math.min(...vs), rawMax = Math.max(...vs);
  const step = METRIC.integer ? Math.max(1, Math.ceil((rawMax - rawMin) / 4))
    : niceStep(Math.max(rawMax - rawMin, 0.2), 4);
  const v0 = Math.floor((rawMin - step * 0.25) / step) * step;
  const v1 = Math.ceil((rawMax + step * 0.25) / step) * step;
  const X = t => L + (t - t0) / Math.max(t1 - t0, 1) * innerW;
  const Y = v => T + (1 - (v - v0) / (v1 - v0)) * innerH;
  chartGeo = { W, H, L, R, T, B, t0, t1, X, Y, series };

  let g = "";
  for (let v = v0; v <= v1 + 1e-9; v += step) {
    const y = Y(v);
    g += `<line x1="${L}" x2="${W-R+14}" y1="${y}" y2="${y}" stroke="${GRID}"/>`;
    g += `<text x="${L-10}" y="${y+4}" text-anchor="end" font-size="10.5"
           font-family="IBM Plex Mono" fill="${AXIS}">${METRIC.integer ? Math.round(v) : v.toFixed(2)}</text>`;
  }
  const nx = Math.min(8, Math.max(3, Math.floor(innerW / 170)));
  for (let i = 0; i <= nx; i++) {
    const t = t0 + (t1 - t0) * i / nx;
    g += `<text x="${X(t)}" y="${H-9}" text-anchor="middle" font-size="10.5"
           font-family="IBM Plex Mono" fill="${AXIS}">${hhmm(t)}</text>`;
  }
  let yb = null;
  if (base != null && base >= v0 && base <= v1) {
    yb = Y(base);
    g += `<line x1="${L}" x2="${W-R+14}" y1="${yb}" y2="${yb}" stroke="${AXIS}"
          stroke-width="1" stroke-dasharray="3 6" opacity="0.7"/>`;
  }
  const ends = [];
  series.forEach(s => {
    const c = lab(s.model).c;
    const d = s.points.map((p, j) => (j ? "L" : "M") + X(p[0]).toFixed(1) + " " + Y(val(p)).toFixed(1)).join(" ");
    g += `<path d="${d}" fill="none" stroke="${c}" stroke-width="2"
          stroke-linejoin="round" stroke-linecap="round"/>`;
    const last = s.points[s.points.length - 1];
    ends.push({ y: Y(val(last)), c, s, lv: val(last), x: X(last[0]) });
  });
  ends.sort((a, b) => a.y - b.y);
  let prev = T - 22;
  ends.forEach(e => { e.ly = Math.max(e.y - 6, prev + 36); prev = e.ly; });
  const lx = W - GUTTER + 26;
  ends.forEach(e => {
    g += `<circle cx="${e.x}" cy="${e.y}" r="3.4" fill="${e.c}"/>`;
    g += `<line x1="${e.x + 5}" y1="${e.y}" x2="${lx - 8}" y2="${e.ly}"
          stroke="${e.c}" stroke-width="0.7" opacity="0.5"/>`;
    g += `<text x="${lx}" y="${e.ly + 4}" font-size="12.5" font-family="Inter"
          font-weight="600" fill="${LEGEND}">${esc(displayName(e.s.model))}</text>`;
    g += `<text x="${lx}" y="${e.ly + 20}" font-size="11" font-family="IBM Plex Mono"
          fill="${e.c}">${METRIC.fmt(e.lv)}</text>`;
  });
  if (yb != null && METRIC.blabel)
    g += `<text x="${L + 8}" y="${yb - 7}" font-size="10.5" font-family="IBM Plex Mono"
          fill="${AXIS}">${METRIC.blabel(tl)}</text>`;
  g += `<line id="xhair" y1="${T}" y2="${H-B}" stroke="${XHAIR}" stroke-width="1"
        visibility="hidden"/>`;
  svg.innerHTML = g;
}

(() => {
  const svg = document.getElementById("chart");
  const tip = document.getElementById("tip");
  svg.addEventListener("mousemove", ev => {
    if (!chartGeo) return;
    const rect = svg.getBoundingClientRect();
    const px = (ev.clientX - rect.left) * (chartGeo.W / rect.width);
    if (px < chartGeo.L || px > chartGeo.W - chartGeo.R) { tip.style.display = "none";
      document.getElementById("xhair")?.setAttribute("visibility", "hidden"); return; }
    const t = chartGeo.t0 + (px - chartGeo.L) / (chartGeo.W - chartGeo.L - chartGeo.R) * (chartGeo.t1 - chartGeo.t0);
    const xh = document.getElementById("xhair");
    if (xh) { xh.setAttribute("x1", px); xh.setAttribute("x2", px); xh.setAttribute("visibility", "visible"); }
    const rows = chartGeo.series.map(s => {
      let best = s.points[0];
      for (const p of s.points) { if (p[0] <= t) best = p; else break; }
      return { name: displayName(s.model), v: best[METRIC.idx] ?? 0, c: lab(s.model).c };
    }).sort((a, b) => b.v - a.v);
    tip.innerHTML = `<div class="t">${hhmm(t)} · ${METRIC.label}</div>` + rows.map(r =>
      `<div class="row"><span class="sw" style="background:${r.c}"></span>${esc(r.name)}<b>${METRIC.fmt(r.v)}</b></div>`).join("");
    tip.style.display = "block";
    const bx = ev.clientX - rect.left, by = ev.clientY - rect.top;
    tip.style.left = Math.min(bx + 18, rect.width - 250) + "px";
    tip.style.top = Math.max(by - 16, 4) + "px";
  });
  svg.addEventListener("mouseleave", () => {
    tip.style.display = "none";
    document.getElementById("xhair")?.setAttribute("visibility", "hidden");
  });
})();
addEventListener("resize", () => { if (lastTimeline && !currentAgent()) drawChart(lastTimeline); });

function whoCell(a) {
  const L = lab(a.model), H = harness(a.harness);
  const blocked = isBlocked(a.model);
  return `<div class="who">${L.logo ? `<img src="${L.logo}" alt="">` : ""}
    <div><div class="name">${esc(displayName(a.model))}${blocked ? '<span class="badge">Blocked</span>' : ""}</div>
    <div class="sub">${esc(H.name)}${blocked ? " · " + esc((a.model.split("—")[1] || "unavailable").trim()) : ""}</div></div></div>`;
}

function lastActivity(a) {
  const o = a.orders && a.orders[0];
  if (o) {
    const verb = o.status === "rejected" ? "Order rejected"
               : (o.side === "BUY" ? "Bought" : "Sold");
    const what = o.question ? " " + esc(o.question.slice(0, 26)) + (o.question.length > 26 ? "…" : "") : "";
    return `<div>${verb}${o.status === "rejected" ? "" : what}</div>
      <div style="color:var(--faint);font-size:11.5px">${rel(o.time)}</div>`;
  }
  if (a.last_event_ts)
    return `<div style="color:var(--dim)">Session</div>
      <div style="color:var(--faint);font-size:11.5px">${rel(a.last_event_ts)}</div>`;
  return '<span style="color:var(--faint)">—</span>';
}

function renderHome(state) {
  const live = state.agents.filter(a => !isBlocked(a.model));
  const equity = live.reduce((s, a) => s + a.equity, 0);
  const start = live.length * 100;
  const ret = start ? (100 * (equity - start) / start) : 0;
  const openPos = live.reduce((s, a) => s + a.positions.length, 0);
  document.getElementById("stats-row").innerHTML = `
    <div class="scard"><div class="k">Combined equity</div>
      <div class="v">${money(equity)} <small class="${ret >= 0 ? "up" : "down"}">${ret >= 0 ? "+" : ""}${fmt(ret)}%</small></div></div>
    <div class="scard"><div class="k">Agents trading</div>
      <div class="v">${live.length} <small>of ${state.agents.length}</small></div></div>
    <div class="scard"><div class="k">Open positions</div>
      <div class="v">${openPos}</div></div>`;

  const lb = document.querySelector("#leaderboard tbody");
  lb.innerHTML = state.agents.map((a, i) => `
    <tr${isBlocked(a.model) ? ' class="blocked"' : ` data-agent="${a.agent_id}"`}>
      <td class="rank">${i + 1}</td>
      <td>${whoCell(a)}</td>
      <td class="num">${money(a.cash)}</td>
      <td class="num">${money(a.positions_value)}</td>
      <td class="num equity">${money(a.equity)}</td>
      <td class="num"><span class="chg ${cls(a.return_pct)}">${a.return_pct > 0 ? "+" : ""}${fmt(a.return_pct)}%</span></td>
      <td>${lastActivity(a)}</td>
      <td class="arrow">${isBlocked(a.model) ? "" : "›"}</td>
    </tr>`).join("");
}
document.querySelector("#leaderboard tbody").addEventListener("click", ev => {
  const tr = ev.target.closest("tr[data-agent]");
  if (tr) location.hash = "#/agent/" + tr.dataset.agent;
});

function renderAgent(a) {
  const L = lab(a.model), H = harness(a.harness);
  document.getElementById("agent-view").innerHTML = `
    <div class="back" onclick="location.hash=''">‹ Back to leaderboard</div>
    <div class="agent-hero">
      ${L.logo ? `<img src="${L.logo}" alt="">` : ""}
      <div><div class="name">${esc(displayName(a.model))}</div>
      <div class="sub">${esc(H.name)} · ${esc(a.model)}</div></div>
    </div>
    <div class="stats-strip">
      <div class="stat"><div class="k">Equity</div><div class="v">${money(a.equity)}</div></div>
      <div class="stat"><div class="k">Return</div><div class="v ${a.return_pct>0?"up":a.return_pct<0?"down":""}">${a.return_pct > 0 ? "+" : ""}${fmt(a.return_pct)}%</div></div>
      <div class="stat"><div class="k">Cash</div><div class="v">${money(a.cash)}</div></div>
      <div class="stat"><div class="k">Positions</div><div class="v">${money(a.positions_value)}</div></div>
      <div class="stat"><div class="k">Fees paid</div><div class="v">${money(a.fees_paid)}</div></div>
      <div class="stat"><div class="k">Rejected orders</div><div class="v">${a.rejections}</div></div>
    </div>

    <div class="card">
      <div class="card-title">Open positions</div>
      ${a.positions.length ? `
      <table>
        <thead><tr><th>Market</th><th>Side</th><th class="num">Shares</th>
          <th class="num">Cost</th><th class="num">Mid</th><th class="num">Value</th>
          <th class="num">Unrealized</th></tr></thead>
        <tbody>${a.positions.map(p => `
          <tr>
            <td>${esc(p.question)}</td><td>${esc(p.outcome)}</td>
            <td class="num">${fmt(p.shares)}</td><td class="num">${money(p.cost_basis)}</td>
            <td class="num">${fmt(p.mid, 3)}</td><td class="num">${money(p.value)}</td>
            <td class="num ${p.upnl > 0 ? "up" : p.upnl < 0 ? "down" : ""}">${money(p.upnl)}</td>
          </tr>`).join("")}
        </tbody>
      </table>` : `<div class="muted">No open positions.</div>`}
    </div>

    <div class="card">
      <div class="card-title">Order log</div>
      ${a.orders.length ? `
      <table>
        <thead><tr><th>Time</th><th>Market</th><th>Side</th><th class="num">Size</th>
          <th>Status</th><th>Thesis / rejection reason</th></tr></thead>
        <tbody>${a.orders.map(o => `
          <tr>
            <td class="num" style="text-align:left">${new Date(o.time * 1000).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"})}</td>
            <td>${esc(o.question ? o.question.slice(0, 56) : "—")}</td>
            <td>${o.side === "BUY" ? "Buy" : "Sell"}</td>
            <td class="num">${money(o.size_usd)}</td>
            <td class="status-${o.status}">${sentence(o.status)}</td>
            <td class="thesis">${esc(sentence(o.status === "rejected" ? (o.reject_reason || "") : (o.thesis || "")))}</td>
          </tr>`).join("")}
        </tbody>
      </table>` : `<div class="muted">No orders yet.</div>`}
    </div>

    <div class="card">
      <div class="card-title">Reasoning feed</div>
      ${a.feed && a.feed.length ? `
      <div class="feed">${a.feed.map(f => `
        <div class="feed-item">
          <span class="feed-ts">${f.ts ? new Date(f.ts).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"}) : ""}</span>
          <span class="feed-${f.kind}">${esc(sentence(f.text)).slice(0, 500)}</span>
        </div>`).join("")}
      </div>` : `<div class="muted">No sessions yet.</div>`}
    </div>`;
}

function currentAgent() {
  const m = location.hash.match(/^#\/agent\/(.+)$/);
  return m ? m[1] : null;
}
function route() {
  const aid = currentAgent();
  const home = document.getElementById("home");
  const view = document.getElementById("agent-view");
  if (aid && lastState) {
    const a = lastState.agents.find(x => x.agent_id === aid);
    if (a) { home.classList.add("hidden"); view.classList.remove("hidden");
             renderAgent(a); window.scrollTo(0, 0); return; }
  }
  view.classList.add("hidden"); home.classList.remove("hidden");
  if (lastTimeline) drawChart(lastTimeline);
}
addEventListener("hashchange", route);

async function refresh() {
  fetch("/api/state").then(r => r.json()).then(state => {
    lastState = state;
    renderHome(state);
    route();
  }).catch(() => {});
  fetch("/api/timeline").then(r => r.json()).then(tl => {
    if (!currentAgent()) drawChart(tl); else lastTimeline = tl;
  }).catch(() => {});
}
refresh();
setInterval(refresh, 60000);
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8941, debug=False)

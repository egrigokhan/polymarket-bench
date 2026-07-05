"""PolymarketBench — single-service production entry (Render).

One process serves everything on $PORT:
  /mcp/*          the trading-gateway MCP (per-agent bearer tokens via tenants)
  /admin/import   one-time state migration (tar.gz of bench.db + pmt-accounts + state.json)
  /*              the dashboard (Flask, mounted as WSGI fallback)
plus the orchestrator loop as a daemon thread (starts once /data is marked ready).

Env:
  PMB_DATA           persistent dir (Render disk), default /data
  TENANTS_JSON       tenants registry (JSON string) — written to trading-gateway/tenants.json
  BRAINBASE_API_KEY  for the orchestrator
  PMB_ADMIN_TOKEN    bearer for /admin/import
Run: uvicorn server:app --host 0.0.0.0 --port $PORT
"""

import io
import json
import os
import sys
import tarfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "trading-gateway"))
sys.path.insert(0, str(ROOT / "orchestrator"))

DATA = Path(os.environ.get("PMB_DATA", "/data"))
DATA.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("PMB_DB", str(DATA / "bench.db"))
os.environ.setdefault("PMB_PMT_ROOT", str(DATA / "pmt-accounts"))
os.environ.setdefault("PMB_STATE", str(DATA / "state.json"))
READY = DATA / "ready"

if os.environ.get("TENANTS_JSON"):
    (ROOT / "trading-gateway" / "tenants.json").write_text(os.environ["TENANTS_JSON"])

import mcp_server  # noqa: E402  (builds Ledger + Gateway against PMB_DB)

TENANTS_PATH = ROOT / "trading-gateway" / "tenants.json"
TOKEN_TO_AGENT = {t["token"]: t["ledger_agent_id"]
                  for t in json.loads(TENANTS_PATH.read_text())} if TENANTS_PATH.exists() else {}
ADMIN_TOKEN = os.environ.get("PMB_ADMIN_TOKEN", "")

from starlette.responses import JSONResponse  # noqa: E402
from a2wsgi import WSGIMiddleware  # noqa: E402

app = mcp_server.mcp.streamable_http_app()

# Dashboard (Flask) mounted as the fallback for non-/mcp, non-/admin paths
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("pmb_dashboard", ROOT / "dashboard" / "app.py")
_dash = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_dash)
DASH_ASGI = WSGIMiddleware(_dash.app)


class Router:
    """Auth for /mcp (tenant tokens → agent identity), /admin/import, dashboard fallback."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.inner(scope, receive, send)
            return
        path = scope.get("path", "")
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        auth = headers.get("authorization", "").removeprefix("Bearer ").strip()

        if path.startswith("/mcp"):
            agent_id = TOKEN_TO_AGENT.get(auth)
            if not agent_id:
                await JSONResponse({"error": "unauthorized"}, status_code=401)(scope, receive, send)
                return
            reset = mcp_server.CURRENT_AGENT.set(agent_id)
            try:
                await self.inner(scope, receive, send)
            finally:
                mcp_server.CURRENT_AGENT.reset(reset)
            return

        if path == "/admin/import" and scope.get("method") == "POST":
            if not ADMIN_TOKEN or auth != ADMIN_TOKEN:
                await JSONResponse({"error": "unauthorized"}, status_code=401)(scope, receive, send)
                return
            body = b""
            while True:
                msg = await receive()
                body += msg.get("body", b"")
                if not msg.get("more_body"):
                    break
            try:
                with tarfile.open(fileobj=io.BytesIO(body), mode="r:gz") as tf:
                    tf.extractall(DATA, filter="data")
                READY.write_text(str(time.time()))
                names = [p.name for p in DATA.iterdir()]
                await JSONResponse({"status": "imported", "data_dir": names})(scope, receive, send)
            except Exception as e:
                await JSONResponse({"error": str(e)}, status_code=400)(scope, receive, send)
            return

        if path == "/healthz":
            await JSONResponse({"ok": True, "ready": READY.exists()})(scope, receive, send)
            return

        await DASH_ASGI(scope, receive, send)


app = Router(app)


# ------------------------------------------------------------------ orchestrator loop

def _orchestrator_loop():
    while not READY.exists():
        time.sleep(5)
    import orchestrator as orch
    state = orch.load_state()
    orch.log("orchestrator thread up (render) — "
             f"{len(orch.CONFIG['agents'])} agents, anchors {orch.ANCHORS_UTC} UTC")
    while True:
        try:
            orch.tick(state)
            orch.save_state(state)
        except Exception as e:
            orch.log(f"tick error: {e!r}")
        time.sleep(60)


if os.environ.get("PMB_ORCHESTRATOR", "1") == "1":
    threading.Thread(target=_orchestrator_loop, daemon=True, name="pmb-orchestrator").start()

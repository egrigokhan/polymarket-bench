"""Serve the gateway MCP server over streamable HTTP — multi-tenant.

Auth: per-agent bearer tokens from tenants.json (chmod 600):
    [{"key": "sonnet46-claudecode", "ledger_agent_id": "agent_...", "token": "pmbgw_..."}]
The middleware maps token → ledger agent id and binds it to the request via a
contextvar (mcp_server.CURRENT_AGENT) — one FastMCP app, per-request identity, and a
leaked token only ever reaches its own $100 wallet (PLAN §8).

Run: PMB_DB=... python3 serve_http.py [port]
Brainbase side: mcp_servers/.mcp.json url = https://<tunnel>/mcp/ with the agent's own
Authorization header.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import uvicorn
from starlette.responses import JSONResponse

import mcp_server

TENANTS_PATH = Path(__file__).parent / "tenants.json"
if not TENANTS_PATH.exists():
    sys.exit("tenants.json is required — refusing to serve unauthenticated")
TOKEN_TO_AGENT = {t["token"]: t["ledger_agent_id"]
                  for t in json.loads(TENANTS_PATH.read_text())}
if not TOKEN_TO_AGENT:
    sys.exit("tenants.json has no tenants")

app = mcp_server.mcp.streamable_http_app()


class TenantAuth:
    """401 unknown tokens; bind the token's agent identity to the request."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
            auth = headers.get("authorization", "")
            token = auth.removeprefix("Bearer ").strip()
            agent_id = TOKEN_TO_AGENT.get(token)
            if not agent_id:
                resp = JSONResponse({"error": "unauthorized"}, status_code=401)
                await resp(scope, receive, send)
                return
            reset = mcp_server.CURRENT_AGENT.set(agent_id)
            try:
                await self.inner(scope, receive, send)
            finally:
                mcp_server.CURRENT_AGENT.reset(reset)
            return
        await self.inner(scope, receive, send)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8940
    print(f"tenants: {len(TOKEN_TO_AGENT)}")
    uvicorn.run(TenantAuth(app), host="127.0.0.1", port=port, log_level="info")

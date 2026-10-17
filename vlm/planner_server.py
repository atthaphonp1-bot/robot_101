"""Planner server: typed command + detected objects -> validated plan -> arm commands.

  python3 vlm/planner_server.py            # http://localhost:8792
  POST /plan  {"text": "...", "objects": [{"id", "color", "x", "y", "u", "v"}], "image": "data:image/png;base64,..."}
           -> {"planner": "mock"|"vlm", "plan": {...}, "errors": [...], "commands": [...]}

Uses the cloud VLM when ANTHROPIC_API_KEY is set (phase 1, not wired yet); otherwise the
rule-based mock planner so the whole flow can be tested without a key. The key is read
from the environment only and is never sent to the browser.
"""
import hmac
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from commands import plan_to_commands  # noqa: E402
from mock import mock_plan  # noqa: E402
from objects import check_objects  # noqa: E402
from validate import validate_plan  # noqa: E402

PORT = int(os.environ.get("PLANNER_PORT", "8792"))
HOST = os.environ.get("PLANNER_HOST", "127.0.0.1")       # 0.0.0.0 on the Pi (set by pi/setup-planner.sh)
ALLOWED_ORIGINS = {o.strip() for o in os.environ.get(
    "PLANNER_ORIGINS", "http://localhost:8791,http://127.0.0.1:8791").split(",") if o.strip()}   # :8791 = Mac dev server
TOKEN = os.environ.get("PLANNER_TOKEN", "")                # optional shared secret (header X-Planner-Token)
MAX_BODY = 2_000_000


def vlm_plan(text, objects, image):
    """Phase 1 (needs ANTHROPIC_API_KEY): ask the cloud VLM for a plan. Not implemented yet."""
    raise NotImplementedError("VLM planner not wired yet")


def make_plan(body):
    text = str(body.get("text", "")).strip()
    objects = body.get("objects") or []
    planner = "mock"
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            plan, planner = vlm_plan(text, objects, body.get("image")), "vlm"
        except NotImplementedError:
            plan = mock_plan(text, objects)
    else:
        plan = mock_plan(text, objects)
    errors = validate_plan(plan, objects)
    commands = [] if errors else plan_to_commands(plan, objects)
    return {"planner": planner, "plan": plan, "errors": errors, "commands": commands}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        data = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        origin = self.headers.get("Origin", "")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Planner-Token")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, {"ok": True, "vlm": bool(os.environ.get("ANTHROPIC_API_KEY")), "token": bool(TOKEN)})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/plan":
            return self._send(404, {"error": "not found"})
        if TOKEN and not hmac.compare_digest(self.headers.get("X-Planner-Token", ""), TOKEN):
            return self._send(401, {"error": "bad or missing X-Planner-Token"})
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY:
            return self._send(413 if length > MAX_BODY else 400, {"error": "bad Content-Length (max 2 MB)"})
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError as e:
            return self._send(400, {"error": f"bad json: {e}"})
        if not isinstance(body, dict):
            return self._send(400, {"error": "body must be a JSON object"})
        err = check_objects(body.get("objects") or [])
        if err:
            return self._send(400, {"error": err})
        try:
            self._send(200, make_plan(body))
        except Exception as e:   # never drop the connection without an answer
            self._send(500, {"error": f"planner error: {type(e).__name__}: {e}"})

    def log_message(self, fmt, *args):
        sys.stderr.write("planner: " + fmt % args + "\n")


if __name__ == "__main__":
    print(f"planner server on http://{HOST}:{PORT}  (VLM {'on' if os.environ.get('ANTHROPIC_API_KEY') else 'off -> mock'})")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()

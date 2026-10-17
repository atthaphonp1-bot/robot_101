"""Planner server: typed command + detected objects -> validated plan -> arm commands.

  python3 vlm/planner_server.py            # http://localhost:8792
  POST /plan  {"text": "...", "objects": [{"id", "color", "x", "y", "u", "v"}], "image": "data:image/png;base64,..."}
           -> {"planner": "mock"|"vlm", "plan": {...}, "errors": [...], "commands": [...]}

Uses the cloud VLM when ANTHROPIC_API_KEY is set (phase 1, not wired yet); otherwise the
rule-based mock planner so the whole flow can be tested without a key. The key is read
from the environment only and is never sent to the browser.
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from commands import plan_to_commands  # noqa: E402
from mock import mock_plan  # noqa: E402
from validate import validate_plan  # noqa: E402

PORT = int(os.environ.get("PLANNER_PORT", "8792"))
HOST = os.environ.get("PLANNER_HOST", "127.0.0.1")       # 0.0.0.0 on the Pi (set by pi/setup-planner.sh)
ALLOWED_ORIGINS = {o.strip() for o in os.environ.get(
    "PLANNER_ORIGINS", "http://localhost:8791,http://127.0.0.1:8791").split(",") if o.strip()}


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
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, {"ok": True, "vlm": bool(os.environ.get("ANTHROPIC_API_KEY"))})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/plan":
            return self._send(404, {"error": "not found"})
        try:
            length = min(int(self.headers.get("Content-Length", 0)), 8_000_000)
            body = json.loads(self.rfile.read(length) or b"{}")
            self._send(200, make_plan(body))
        except (ValueError, TypeError) as e:
            self._send(400, {"error": f"bad request: {e}"})

    def log_message(self, fmt, *args):
        sys.stderr.write("planner: " + fmt % args + "\n")


if __name__ == "__main__":
    print(f"planner server on http://{HOST}:{PORT}  (VLM {'on' if os.environ.get('ANTHROPIC_API_KEY') else 'off -> mock'})")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()

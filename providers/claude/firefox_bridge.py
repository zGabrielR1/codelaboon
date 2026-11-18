"""One-request loopback transport for the default-browser extension."""

import json
import secrets
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import quote

PORT = 18767
HOST = f"127.0.0.1:{PORT}"
MAX_REPLY = 2_000_000


def chat(prompt, *, background=False):
    token = secrets.token_urlsafe(32)
    result = {}
    prompt_requested = False

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, status, payload):
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def authorized(self):
            return (self.headers.get("Host") == HOST and
                    secrets.compare_digest(self.headers.get("Authorization", ""), f"Bearer {token}"))

        def do_GET(self):
            nonlocal prompt_requested
            if not self.authorized() or self.path != "/prompt":
                self.respond(404, {})
                return
            self.respond(200, {"prompt": prompt, "background": background})
            prompt_requested = True

        def do_POST(self):
            if not self.authorized() or self.path != "/reply":
                self.respond(404, {})
                return
            try:
                count = int(self.headers.get("Content-Length", 0))
                if not 0 < count <= MAX_REPLY:
                    raise ValueError()
                data = json.loads(self.rfile.read(count))
                if not isinstance(data, dict) or not any(
                    isinstance(data.get(key), str) and data[key].strip() for key in ("reply", "error")
                ):
                    raise ValueError()
            except (ValueError, OSError):
                self.respond(400, {})
                return
            self.respond(200, {})
            result.update(data)

        def setup(self):
            super().setup()
            self.connection.settimeout(5)

    try:
        server = HTTPServer(("127.0.0.1", PORT), Handler)
    except OSError as error:
        raise ValueError("The default-browser bridge port is busy. Finish the other request first.") from error
    with server:
        server.timeout = 0.5
        if not webbrowser.open(f"https://claude.ai/new#codelaboon={quote(token)}", new=2):
            raise ValueError("Could not open your default browser.")
        now = time.monotonic()
        connect_deadline = now + 25
        reply_deadline = now + 225
        while not result and time.monotonic() < (reply_deadline if prompt_requested else connect_deadline):
            server.handle_request()
    if not result:
        raise ValueError("The browser extension did not return a reply. Check that it is installed and Claude.ai is signed in.")
    if result.get("error"):
        raise ValueError(result["error"])
    return result["reply"]

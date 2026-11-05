"""Loopback-only web workspace. Credentials remain in the provider adapters."""
import json
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

from codelaboon.cli import CodelaboonCLI

STATIC = Path(__file__).with_name("static")


def create_server(port=8765, cli=None):
    cli = cli or CodelaboonCLI()
    cli.load_providers()
    token = secrets.token_urlsafe(32)
    auth_state = {"status": "idle"}
    auth_lock = threading.Lock()

    def login_job():
        from codelaboon.chatgpt_auth import login
        try:
            login()
            auth_state.update(status="connected")
        except Exception:
            auth_state.update(status="failed")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, status, body, content_type="application/json"):
            data = json.dumps(body).encode() if content_type == "application/json" else body
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass  # The browser stopped waiting or closed the tab.

        def trusted(self):
            expected = f"127.0.0.1:{self.server.server_port}"
            return self.headers.get("Host") == expected and self.headers.get("Origin", f"http://{expected}") == f"http://{expected}"

        def do_GET(self):
            if not self.trusted():
                return self.respond(403, {"error": "Use the printed loopback URL"})
            url = urlsplit(self.path)
            if url.path == "/api/auth/status":
                return self.respond(200, auth_state)
            if url.path == "/api/providers":
                return self.respond(200, {"token": token, "providers": [{"name": n, "configured": p.validate_api_key(), "keyless": p.keyless} for n, p in sorted(cli.providers.items())]})
            if url.path == "/api/models":
                name = parse_qs(url.query).get("provider", [""])[0]
                if name not in cli.providers:
                    return self.respond(404, {"error": "Unknown provider"})
                try:
                    models = cli.providers[name].list_models()
                    names = getattr(cli.providers[name], "model_names", {})
                    return self.respond(200, {"models": models, "names": names if isinstance(names, dict) else {}})
                except Exception:
                    return self.respond(502, {"error": "Model discovery failed. Check provider configuration and retry."})
            assets = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"), "/style.css": ("style.css", "text/css"), "/logo.svg": ("logo.svg", "image/svg+xml")}
            if url.path not in assets:
                return self.respond(404, {"error": "Not found"})
            file, mime = assets[url.path]
            return self.respond(200, (STATIC / file).read_bytes(), mime)

        def do_POST(self):
            if not self.trusted() or self.headers.get("X-Codelaboon-Token") != token:
                return self.respond(403, {"error": "Reload this workspace and retry"})
            if self.path == "/api/auth/chatgpt":
                with auth_lock:
                    if auth_state["status"] != "pending":
                        auth_state.update(status="pending")
                        threading.Thread(target=login_job, daemon=True).start()
                return self.respond(202, auth_state)
            if self.path != "/api/chat":
                return self.respond(404, {"error": "Not found"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 1048576:
                    return self.respond(413, {"error": "Conversation is too large"})
                body = json.loads(self.rfile.read(length))
                provider = cli.providers[body["provider"]]
                messages = body["messages"]
                if not isinstance(messages, list) or not messages or len(messages) > 200 or any(not isinstance(m, dict) or m.get("role") not in ("system", "user", "assistant") or not isinstance(m.get("content"), str) for m in messages):
                    raise ValueError()
                model = body["model"]
                if not isinstance(model, str) or not model.strip():
                    raise ValueError()
                if not provider.validate_api_key():
                    return self.respond(400, {"error": "Configure this provider using codelaboon configure " + body["provider"]})
                reply = provider.chat(model, messages, temperature=0.7, max_tokens=4096)
                return self.respond(200, {"reply": reply})
            except (KeyError, ValueError, TypeError):
                return self.respond(400, {"error": "Invalid chat request"})
            except Exception:
                return self.respond(502, {"error": "Provider request failed. Check credentials, model availability, and connection, then retry."})

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def serve(port=8765, open_browser=True):
    server = create_server(port)
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"codelaboon workspace: {url} (Ctrl+C to stop)", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

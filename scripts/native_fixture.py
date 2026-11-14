"""Local model fixture shared by native tool and terminal integration checks."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parent.parent
MARKER = "NATIVE_FIXTURE_37"
REPLY = "Fixture reply: accepted."


@contextmanager
def fixture(engine, setup=False, tools=False, development=False):
    observed = []
    with tempfile.TemporaryDirectory(prefix="codelaboon-native-", ignore_cleanup_errors=True) as directory:
        project = Path(directory)
        (project / "marker.txt").write_text(MARKER + "\n", encoding="utf-8")

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                data = json.dumps({"data": [{"id": "fixture"}]}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                observed.append(body)
                read_name = next((tool.get("function", {}).get("name") for tool in body.get("tools", [])
                                  if tool.get("function", {}).get("name", "").lower() == "read"), None)
                read = bool(read_name)
                found = any(message.get("role") == "tool" and MARKER in str(message.get("content"))
                            for message in body.get("messages", []))
                if tools and read and not found:
                    call = {"id": "fixture_read", "type": "function", "function": {
                        "name": read_name, "arguments": json.dumps({
                            "path" if engine == "omp" else "file_path" if engine == "claude" else "filePath": str(project / "marker.txt")})}}
                    message = {"role": "assistant", "content": None, "tool_calls": [call]}
                    reason = "tool_calls"
                else:
                    message = {"role": "assistant", "content": "Verified " + MARKER if found else REPLY}
                    reason = "stop"
                self.send_response(200)
                if not body.get("stream"):
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"id": "fixture", "model": "fixture",
                        "choices": [{"index": 0, "message": message, "finish_reason": reason}]}).encode())
                    return
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                if message.get("tool_calls"):
                    message["tool_calls"][0]["index"] = 0
                for delta, finish in ((message, None), ({}, reason)):
                    chunk = {"id": "fixture", "object": "chat.completion.chunk", "created": int(time.time()),
                             "model": "fixture", "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
                    self.wfile.write(("data: " + json.dumps(chunk) + "\n\n").encode())
                    self.wfile.flush()
                self.wfile.write(b"data: [DONE]\n\n")

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        config = project / "config"
        config.mkdir()
        base = f'base_url="http://127.0.0.1:{server.server_port}/v1"\n'
        (config / "providers.toml").write_text(
            '[local]\napi_key=""\nmodels=[]\n' + base +
            '[kilo]\napi_key=""\nmodels=["kilo-auto/free"]\n' + base +
            '[pollinations]\napi_key=""\nmodels=["fixture"]\n' + base,
            encoding="utf-8")
        env = dict(os.environ, CODELABOON_CONFIG_DIR=str(config), CODELABOON_NO_ANIMATION="1")
        if engine in ("kilo", "claude"):
            # Reuse a verified optional binary while keeping all auth/config isolated.
            from codelaboon.paths import config_dir
            marker = config_dir() / "runtime/native-clis" / engine / "current.json"
            if marker.is_file():
                binary = Path(json.loads(marker.read_text())["executable"])
                env["PATH"] = str(binary.parent) + os.pathsep + env.get("PATH", "")
        if development:
            env["CODELABOON_DEV_RUNTIME"] = "1"
        try:
            if setup:
                result = subprocess.run([sys.executable, str(ROOT / "codelaboon/cli.py"), "tui", "--engine", engine,
                                         "--setup"], cwd=project, env=env, capture_output=True, text=True, timeout=240)
                if result.returncode:
                    raise RuntimeError(result.stdout[-2000:] + result.stderr[-2000:])
            yield project, env, observed
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

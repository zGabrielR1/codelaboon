"""Loopback wire transport for the source-forked coding-agent runtimes.

Unlike provider.chat(), this preserves tool calls, tool results and SSE.
Credentials remain in Python; each launch gets a private loopback token.
"""

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets
import threading
import time
from urllib.parse import unquote, urlsplit

import requests

from codelaboon import free_auto

COMPATIBLE = {"ourfree", "kilo", "pollinations", "openrouter", "nvidia", "luna", "chatgpt",
              "local", "openrouter_free", "groq", "cerebras", "wusrouter", "claude", "gemini", "freebuff"}
FREE_COMPATIBLE = {"ourfree", "kilo", "pollinations", "openrouter_free", "freebuff"}


class Gateway:
    def __init__(self, providers):
        self.providers = providers
        self.token = secrets.token_urlsafe(32)
        self.cooldowns = {}
        self.catalog = None
        self.local = requests.Session()
        self.local.trust_env = False

    def models(self):
        if self.catalog is not None:
            return self.catalog
        rows = ([{"id": "free", "name": "free (Auto)", "api": "chat"}]
                if FREE_COMPATIBLE.intersection(self.providers) else [])
        for name, provider in self.providers.items():
            if name not in COMPATIBLE:
                continue
            if not provider.validate_api_key():
                continue
            try:
                models = provider.list_models()
                subscription = name == "chatgpt" and provider._credential()[1]
            except Exception:
                continue
            labels = getattr(provider, "model_names", {})
            rows.extend({"id": f"{name}/{model}", "name": labels.get(model, model),
                         "api": {"claude": "anthropic", "gemini": "google"}.get(name,
                             "responses" if subscription else "chat")} for model in models)
        self.catalog = rows
        return rows

    def routes(self, model):
        if model == "free":
            entries = free_auto.ranked({key: value for key, value in self.providers.items()
                                        if key in FREE_COMPATIBLE})
            # Reach another provider before retrying models on a failed gateway.
            names = list(dict.fromkeys(entry.provider for entry in entries))
            return [(name, next(entry.model for entry in entries if entry.provider == name))
                    for name in names if self.cooldowns.get(name, 0) <= time.monotonic()]
        name, separator, identifier = model.partition("/")
        if not separator or name not in COMPATIBLE or name not in self.providers:
            raise ValueError("Unknown codelaboon model")
        if not self.providers[name].validate_api_key():
            raise ValueError(f"Configure {name} with codelaboon configure {name}")
        accepts = getattr(self.providers[name], "accepts", None)
        if accepts and not accepts({"id": identifier}):
            raise ValueError("This provider does not allow that model")
        return [(name, identifier)]

    def request(self, body, api):
        routes = self.routes(body.get("model", ""))
        if not routes:
            raise ValueError("No free coding model is ready. Configure ourfree, or retry kilo/pollinations shortly.")
        failures = []
        for name, model in routes:
            provider = self.providers[name]
            payload = dict(body, model=model)
            headers = {"content-type": "application/json", "user-agent": "codelaboon"}
            credential = provider.credential() if hasattr(provider, "credential") else provider.api_key.strip()
            subscription = False
            google_oauth = False
            if name == "chatgpt":
                credential, subscription = provider._credential()
            if credential:
                headers["authorization"] = f"Bearer {credential}"
            if api == "anthropic":
                if name != "claude":
                    raise ValueError("Messages requires a Claude model")
                credential, mode = provider._credential()
                headers = provider._headers(credential, mode)
                url = f"{provider.base_url.rstrip('/')}/messages"
            elif api == "google":
                if name != "gemini":
                    raise ValueError("GenerateContent requires a Gemini model")
                credential, mode = provider._credential()
                headers = provider._headers(credential, mode)
                payload.pop("model", None)
                streaming = payload.pop("stream", False)
                operation = "streamGenerateContent?alt=sse" if streaming else "generateContent"
                if mode == "oauth":
                    from providers.gemini.gemini_provider import CLOUDCODE_BASE_URL, API_VERSION
                    from codelaboon.gemini_auth import project_id
                    url = f"{CLOUDCODE_BASE_URL}/{API_VERSION}:{operation}"
                    payload = {"model": model, "project": project_id(), "request": payload}
                    google_oauth = True
                else:
                    url = f"{provider.base_url.rstrip('/')}/models/{model}:{operation}"
            elif api == "responses":
                if name != "chatgpt":
                    raise ValueError("Responses is only configured for ChatGPT")
                # _credential refuses custom URLs for account-session tokens.
                url = f"{provider.base_url.rstrip('/')}/responses"
                payload["store"] = False
            else:
                if name in ("claude", "gemini"):
                    raise ValueError("Select this model through its native protocol provider")
                if subscription:
                    raise ValueError("Select this ChatGPT model through the Responses provider")
                suffix = "/openai" if name == "pollinations" else "/chat/completions"
                url = f"{provider.base_url.rstrip('/')}{suffix}"
                if name == "freebuff":
                    from codelaboon import __version__
                    credential, _ = provider._credential()
                    try:
                        instance = provider._ensure_slot(credential, model)
                    except (ValueError, requests.RequestException):
                        if body.get("model") != "free":
                            raise
                        self.cooldowns[name] = time.monotonic() + 30
                        failures.append("freebuff: admission failed")
                        continue
                    metadata = provider._completion_body(model, payload.get("messages", []), instance, payload)
                    payload = {**payload, "codebuff_metadata": metadata["codebuff_metadata"], "provider": metadata["provider"]}
                    url = f"{provider.base_url.rstrip('/')}/api/v1/chat/completions"
                    headers["authorization"] = f"Bearer {credential}"
                    headers["x-freebuff-client-version"] = __version__
            try:
                transport = self.local if name == "local" else requests
                response = transport.post(url, headers=headers, json=payload,
                                          stream=True, timeout=(15, 180), allow_redirects=False)
            except requests.RequestException:
                self.cooldowns[name] = time.monotonic() + 30
                failures.append(f"{name}: connection failed")
                continue
            if not 200 <= response.status_code < 300 and body.get("model") == "free":
                failures.append(f"{name}: HTTP {response.status_code}")
                self.cooldowns[name] = time.monotonic() + 30
                response.close()
                continue
            response.codelaboon_google_oauth = google_oauth
            return response
        raise ValueError("No free coding model answered. " + "; ".join(failures))


def handler(gateway):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def authorized(self):
            return (secrets.compare_digest(self.headers.get("Authorization", ""), f"Bearer {gateway.token}")
                    or secrets.compare_digest(self.headers.get("x-api-key", ""), gateway.token)
                    or secrets.compare_digest(self.headers.get("x-goog-api-key", ""), gateway.token))

        def document(self, status, value):
            data = json.dumps(value).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self.authorized():
                return self.document(401, {"error": {"message": "Unauthorized"}})
            if self.path == "/v1/work/status":
                from codelaboon.work import status
                try:
                    state = status()
                    return self.document(200, {key: state[key] for key in
                        ("running", "paused", "completed", "pending", "cooldowns")})
                except (OSError, ValueError, KeyError):
                    return self.document(200, {"running": False, "pending": [], "completed": 0})
            if self.path != "/v1/models":
                return self.document(404, {"error": {"message": "Unknown endpoint"}})
            self.document(200, {"object": "list", "data": [
                {"id": row["id"], "object": "model", "owned_by": "codelaboon"}
                for row in gateway.models()
            ]})

        def do_POST(self):
            if not self.authorized():
                return self.document(401, {"error": {"message": "Unauthorized"}})
            path = urlsplit(self.path)
            api = {"/v1/chat/completions": "chat", "/v1/responses": "responses", "/v1/messages": "anthropic"}.get(path.path)
            google = None
            for prefix in ("/v1/models/", "/v1beta/models/"):
                if path.path.startswith(prefix):
                    google, separator, operation = unquote(path.path[len(prefix):]).rpartition(":")
                    if separator and operation in ("generateContent", "streamGenerateContent"):
                        api = "google"
            if api is None:
                return self.document(404, {"error": {"message": "Unknown endpoint"}})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 32 * 1024 * 1024:
                    raise ValueError("Invalid request size")
                body = json.loads(self.rfile.read(length))
                if api == "google" and isinstance(body, dict):
                    body = dict(body, model=google, stream=operation == "streamGenerateContent")
                if not isinstance(body, dict) or not isinstance(body.get("model"), str):
                    raise ValueError("Expected an object with a model")
                response = gateway.request(body, api)
            except (ValueError, TypeError) as error:
                return self.document(400, {"error": {"message": str(error)}})
            except requests.RequestException:
                return self.document(502, {"error": {"message": "Provider connection failed"}})
            try:
                google_oauth = response.codelaboon_google_oauth is True and response.status_code < 400
                if google_oauth and not body.get("stream"):
                    return self.document(response.status_code, response.json().get("response", {}))
                self.send_response(response.status_code)
                self.send_header("Content-Type", response.headers.get("Content-Type", "application/json"))
                self.send_header("Connection", "close")
                self.end_headers()
                if google_oauth:
                    response.encoding = "utf-8"
                    chunks = (("data: " + json.dumps(json.loads(line[5:].strip()).get("response", {})) + "\n\n").encode()
                              for line in response.iter_lines(decode_unicode=True) if line.startswith("data:"))
                else:
                    chunks = response.iter_content(chunk_size=None)
                for chunk in chunks:
                    self.wfile.write(chunk)
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, requests.RequestException, ValueError):
                pass
            finally:
                response.close()
                self.close_connection = True
    return Handler


@contextmanager
def serve(providers):
    gateway = Gateway(providers)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler(gateway))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield gateway, f"http://127.0.0.1:{server.server_port}/v1"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        gateway.local.close()

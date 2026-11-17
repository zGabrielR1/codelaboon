"""Loopback-only web workspace. Credentials remain in the provider adapters."""
import json
import hashlib
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
    auth_providers = ("chatgpt", "claude", "gemini", "freebuff", "qoder", "copilot")
    auth_states = {name: {"status": "idle"} for name in auth_providers}
    auth_lock = threading.Lock()
    task_lock=threading.Lock()
    task_requests={}

    def login_job(provider):
        import importlib

        module = importlib.import_module(f"codelaboon.{provider}_auth")
        try:
            if provider=="copilot":module.login(notify=lambda row:auth_states[provider].update(row))
            else:module.login()
        except Exception:
            auth_states[provider].update(status="failed")
            return
        auth_states[provider].update(status="connected")
        try:
            cli.load_providers()
        except Exception:
            pass

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
            if url.path == '/api/session':
                from codelaboon import __version__
                import platform
                return self.respond(200,{'token':token,'version':__version__,'workspace':str(Path.cwd().resolve()),'platform':platform.system()})
            if url.path in ('/api/tasks','/api/tasks/logs','/api/tasks/messages','/api/tasks/settings','/api/tasks/changes','/api/tasks/models','/api/tasks/attempts'):
                if self.headers.get('X-Codelaboon-Token') != token:
                    return self.respond(403,{'error':'Reload this workspace and retry'})
                from codelaboon import task_api
                try:
                    if url.path=='/api/tasks/attempts':return self.respond(200,task_api.attempts(parse_qs(url.query).get('task',[''])[0]))
                    if url.path=='/api/tasks/models':return self.respond(200,task_api.model_choices(cli))
                    if url.path=='/api/tasks/settings':return self.respond(200,task_api.settings(parse_qs(url.query).get('task',[''])[0]))
                    if url.path=='/api/tasks/changes':return self.respond(200,task_api.changes(parse_qs(url.query).get('task',[''])[0]))
                    if url.path == '/api/tasks/messages':
                        return self.respond(200,task_api.conversation(parse_qs(url.query).get('task',[''])[0]))
                    if url.path == '/api/tasks/logs':
                        identity=parse_qs(url.query).get('task',[''])[0]
                        return self.respond(200,task_api.logs(identity,parse_qs(url.query).get('attempt',[None])[0]))
                    return self.respond(200,task_api.snapshot())
                except (OSError,ValueError,KeyError,TypeError):
                    return self.respond(400,{'error':'Task state could not be read. Check worker configuration and retry.'})
            if url.path == "/api/auth/status":
                provider = parse_qs(url.query).get("provider", ["chatgpt"])[0]
                if provider not in auth_providers:
                    return self.respond(404, {"error": "Unknown sign-in provider"})
                return self.respond(200, auth_states[provider])
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
            assets = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"), "/style.css": ("style.css", "text/css"), "/logo.svg": ("logo.svg", "image/svg+xml"),
                      '/tasks':('tasks.html','text/html; charset=utf-8'),'/tasks.js':('tasks.js','text/javascript; charset=utf-8'),'/tasks.css':('tasks.css','text/css')}
            if url.path not in assets:
                return self.respond(404, {"error": "Not found"})
            file, mime = assets[url.path]
            return self.respond(200, (STATIC / file).read_bytes(), mime)

        def do_POST(self):
            if not self.trusted() or self.headers.get("X-Codelaboon-Token") != token:
                return self.respond(403, {"error": "Reload this workspace and retry"})
            if self.path=='/api/providers/configure':
                try:
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<length<=20000:raise ValueError('Invalid provider settings size')
                    body=json.loads(self.rfile.read(length));name=body.get('provider');key=body.get('api_key')
                    if name not in ('howtofix','wusrouter','groq','cerebras','openrouter','nvidia','luna'):raise ValueError('Use account login for this provider')
                    if not isinstance(key,str) or not key.strip() or len(key)>16000 or any(ord(c)<32 for c in key):raise ValueError('Enter a nonempty API key')
                    from config.providers import save_provider_config
                    existing=cli._current_provider_config(name);existing['api_key']=key.strip()
                    if not save_provider_config(name,existing):raise ValueError('Could not save provider settings')
                    cli.load_providers();return self.respond(200,{'provider':name,'configured':True})
                except (OSError,ValueError,TypeError,AttributeError):return self.respond(400,{'error':'Provider settings could not be saved. Check the provider and key.'})
            if self.path in ('/api/tasks','/api/tasks/control','/api/tasks/messages','/api/tasks/settings','/api/tasks/worker'):
                from codelaboon import task_api
                try:
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<length<=131072:return self.respond(413,{'error':'Task request is too large'})
                    body=json.loads(self.rfile.read(length))
                    if not isinstance(body,dict):raise ValueError('Invalid task request')
                    if self.path=='/api/tasks/worker':
                        with task_lock:result=task_api.worker_control(body.get('action'))
                    elif self.path=='/api/tasks/settings':
                        with task_lock:result=task_api.settings(body.get('task'),body)
                    elif self.path=='/api/tasks/messages':
                        with task_lock:result=task_api.message(body)
                    elif self.path=='/api/tasks':
                        request_id=body.get('request_id')
                        if not isinstance(request_id,str) or not 1<=len(request_id)<=64:
                            raise ValueError('Provide a queue request ID')
                        digest=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()
                        with task_lock:
                            previous=task_requests.get(request_id)
                            if previous:
                                if previous[0]!=digest:raise ValueError('Queue request ID was reused with different data')
                                result=previous[1]
                            else:
                                result=task_api.enqueue(body)
                                if len(task_requests)>=128:task_requests.pop(next(iter(task_requests)))
                                task_requests[request_id]=(digest,result)
                    else:result=task_api.control(body['task'],body['action'])
                    return self.respond(202,result)
                except (OSError,ValueError,KeyError,TypeError,RuntimeError) as error:
                    return self.respond(400,{'error':str(error)[:500]})
            if self.path.startswith("/api/auth/"):
                provider = self.path[len("/api/auth/") :]
                if provider not in auth_providers:
                    return self.respond(404, {"error": "Unknown sign-in provider"})
                with auth_lock:
                    state = auth_states[provider]
                    if state["status"] != "pending":
                        state.update(status="pending")
                        threading.Thread(
                            target=login_job, args=(provider,), daemon=True
                        ).start()
                return self.respond(202, state)
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


def serve(port=8765, open_browser=True, start_path='/'):
    server = create_server(port)
    url = f"http://127.0.0.1:{server.server_port}"+start_path
    print(f"codelaboon workspace: {url} (Ctrl+C to stop)", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

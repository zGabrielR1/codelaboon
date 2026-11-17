"""Loopback wire transport for the source-forked coding-agent runtimes.

Unlike provider.chat(), this preserves tool calls, tool results and SSE.
Credentials remain in Python; each launch gets a private loopback token.
"""

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import queue
import secrets
import tempfile
import threading
import time
from urllib.parse import parse_qs, unquote, urlsplit

import requests

from codelaboon import free_auto
from codelaboon.paths import config_dir

COMPATIBLE = {"ourfree", "kilo", "pollinations", "openrouter", "nvidia", "luna", "chatgpt",
              "local", "openrouter_free", "groq", "cerebras", "wusrouter", "howtofix", "copilot", "claude", "gemini", "freebuff", "zai_free", "vercel", "vercel_free"}
FREE_COMPATIBLE = {"ourfree", "kilo", "pollinations", "openrouter_free", "freebuff", "zai_free", "vercel_free"}


class FreeRoutingUnavailable(ValueError):
    def __init__(self,message,retry_after=60):
        super().__init__(message);self.retry_after=max(1,min(int(retry_after),3600))


def retry_delay(response,default=60):
    value=response.headers.get('Retry-After','')
    try:return max(1,min(int(value),3600))
    except (ValueError,TypeError):
        try:
            from email.utils import parsedate_to_datetime
            return max(1,min(int(parsedate_to_datetime(value).timestamp()-time.time()),3600))
        except (ValueError,TypeError,OverflowError):return default


def early_stream_error(response):
    """Inspect an SSE prelude before committing a free route to the client."""
    content_type=response.headers.get('Content-Type','')
    if not isinstance(content_type,str):return ''
    if 'application/json' in content_type:
        try:value=response.json()
        except (ValueError,requests.RequestException):return ''
        return str(value.get('error','')) if isinstance(value,dict) else ''
    if 'text/event-stream' not in content_type:return ''
    original=response.iter_content
    source=iter(original(chunk_size=4096));buffer=[];pending=b'';size=0
    error=''
    try:
        for chunk in source:
            buffer.append(chunk);pending+=chunk;size+=len(chunk)
            committed=False
            while b'\n' in pending:
                line,pending=pending.split(b'\n',1)
                if not line.startswith(b'data:'):continue
                data=line[5:].strip()
                if data==b'[DONE]':committed=True;break
                try:value=json.loads(data)
                except (ValueError,UnicodeError):continue
                if not isinstance(value,dict):continue
                if value.get('error'):error=str(value['error']);break
                for choice in value.get('choices',[]):
                    delta=choice.get('delta',{})
                    if delta.get('content') or delta.get('tool_calls') or choice.get('finish_reason'):committed=True
            if error or committed or size>=65536:break
    finally:
        def replay(*args,**kwargs):
            yield from buffer
            yield from source
        response.iter_content=replay
    return error


class Gateway:
    def __init__(self, providers, health_checks=True, task_class=None):
        self.providers = providers
        self.task_class=task_class
        self.health_checks = health_checks
        self.health_started = set()
        self.token = secrets.token_urlsafe(32)
        self.cooldowns = {}
        self.catalog = None
        self.local = requests.Session()
        self.local.trust_env = False
        self.closed = threading.Event()
        self.discovery_errors = {}
        self.reload_providers=None
        self.connection_revision=None
        self.provider_generation=0
        self.reload_lock=threading.Lock()
        self.model_alias = None
        prompt_path=os.environ.get('CODELABOON_TASK_SYSTEM_PROMPT_FILE')
        self.task_system_prompt=Path(prompt_path).read_text(encoding='utf-8')[:20000] if prompt_path else ''
        self.task_model=os.environ.get('CODELABOON_TASK_MODEL') if os.environ.get('CODELABOON_HEADLESS_TASK')=='1' else None

    def refresh_connections(self):
        if self.reload_providers is None:return
        from codelaboon.connections import revision
        current=revision()
        if current==self.connection_revision:return
        with self.reload_lock:
            if current==self.connection_revision:return
            self.providers=self.reload_providers()
            self.provider_generation+=1
            self.catalog=None;self.cooldowns.clear();self.health_started.clear()
            self.connection_revision=current

    def health_applies(self,name,provider):
        from providers.base import BaseProvider
        from codelaboon import model_health
        return (self.health_checks and model_health.enabled() and isinstance(provider,BaseProvider)
                and name in model_health.FREE_PROVIDERS and model_health.eligible(name,provider))

    def visible(self,rows):
        from codelaboon import model_health
        result=[]
        for row in rows:
            name,_,model=row['id'].partition('/')
            provider=self.providers.get(name)
            if provider and self.health_applies(name,provider):
                live=model_health.catalog(name,provider)
                if live is not None and model not in live:
                    continue
                if not model_health.verified(name,provider,model,coding=name in model_health.WIRE_PROVIDERS):
                    continue
            result.append(row)
        if os.environ.get('CODELABOON_HEADLESS_TASK')!='1' and set(self.providers)!={'local'}:
            from codelaboon.task_chat import model_rows
            result.extend(model_rows())
        return result

    def schedule_checks(self,name,provider,models=None):
        if not self.health_applies(name,provider) or name in self.health_started:
            return
        self.health_started.add(name)
        generation=self.provider_generation
        def verify():
            from codelaboon.model_health import check_provider,discover
            try:
                current=models;refresh=time.monotonic()+300;first=True
                while not self.closed.is_set() and generation==self.provider_generation:
                    if current is None or time.monotonic()>=refresh:
                        current=discover(name,provider);refresh=time.monotonic()+300
                    check_provider(name,provider,closed=self.closed,models=current,limit=2 if first else 1)
                    first=False
                    if self.closed.wait(60):
                        break
            except Exception:
                self.discovery_errors[name]='health_check_failed'
        threading.Thread(target=verify,daemon=True,name='free-model-check-'+name).start()

    def models(self, startup=False):
        self.refresh_connections()
        if self.catalog is not None:
            return self.visible(self.catalog)
        if startup:
            return self.start_catalogue()
        rows = ([{"id": "free", "name": "free (Auto)", "api": "chat"}]
                if FREE_COMPATIBLE.intersection(self.providers) else [])
        for name, provider in self.providers.items():
            if name not in COMPATIBLE:
                continue
            if not provider.validate_api_key():
                continue
            try:
                from codelaboon import model_health
                models = model_health.discover(name,provider) if self.health_applies(name,provider) else provider.list_models()
                self.schedule_checks(name,provider,models)
                subscription = name == "chatgpt" and provider._credential()[1]
            except Exception:
                continue
            labels = getattr(provider, "model_names", {})
            rows.extend({"id": f"{name}/{model}", "name": labels.get(model, model),
                         "api": {"claude": "anthropic", "gemini": "google"}.get(name,
                             "responses" if subscription else "chat")} for model in models)
        self.catalog = rows
        return self.visible(rows)

    def start_catalogue(self, budget=1.0):
        """Render promptly, even when provider discovery/auth endpoints stall."""
        cache = config_dir() / "native-models.json"
        try:
            saved = json.loads(cache.read_text(encoding="utf-8")) if cache.stat().st_size < 2_000_000 else {}
        except (OSError, ValueError):
            saved = {}
        entries = {}
        pending = queue.Queue()
        lock = threading.Lock()
        complete = threading.Event()
        free = [{"id": "free", "name": "free (Auto)", "api": "chat"}] if FREE_COMPATIBLE.intersection(self.providers) else []
        def key(name, provider):
            return name + ":" + getattr(provider, "base_url", "")
        for name, provider in self.providers.items():
            if name not in COMPATIBLE or not provider.validate_api_key():
                continue
            api = {"claude": "anthropic", "gemini": "google"}.get(name, "chat")
            if name == "chatgpt" and not (provider.api_key.strip() or os.environ.get("OPENAI_API_KEY")):
                api = "responses"
            cached = saved.get(key(name, provider), []) if isinstance(saved, dict) else []
            valid = [row for row in cached if isinstance(row, dict) and
                     isinstance(row.get("id"), str) and row["id"].startswith(name + "/") and
                     isinstance(row.get("name"), str) and row.get("api") == api] if isinstance(cached, list) else []
            roster = getattr(provider, "models", None) or getattr(provider, "default_models", [])
            entries[name] = valid or [{"id": name + "/" + model, "name": model, "api": api}
                                      for model in roster if isinstance(model, str)]
            pending.put((name, provider, api))
        def snapshot():
            return free + [row for rows in entries.values() for row in rows]
        self.catalog = snapshot()
        remaining = pending.qsize()
        if not remaining:
            return self.visible(self.catalog)
        generation=self.provider_generation
        def worker():
            nonlocal remaining
            while not self.closed.is_set():
                try:
                    name, provider, api = pending.get_nowait()
                except queue.Empty:
                    return
                try:
                    from codelaboon import model_health
                    models = model_health.discover(name,provider) if self.health_applies(name,provider) else provider.list_models()
                    self.schedule_checks(name,provider,models)
                    labels = getattr(provider, "model_names", {})
                    rows = [{"id": name + "/" + model, "name": labels.get(model, model), "api": api}
                            for model in models if isinstance(model, str)]
                    with lock:
                        if generation!=self.provider_generation:return
                        entries[name] = rows
                        self.catalog = snapshot()
                        if not self.closed.is_set():
                            saved_key = {key(n, self.providers[n]): value for n, value in entries.items()}
                            cache.parent.mkdir(parents=True, exist_ok=True)
                            descriptor, temporary = tempfile.mkstemp(prefix=".models-", dir=cache.parent)
                            try:
                                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                                    json.dump(saved_key, stream)
                                os.replace(temporary, cache)
                            finally:
                                Path(temporary).unlink(missing_ok=True)
                except Exception as error:
                    self.discovery_errors[name] = type(error).__name__
                finally:
                    with lock:
                        remaining -= 1
                        if remaining == 0:
                            complete.set()
        for _ in range(min(4, remaining)):
            threading.Thread(target=worker, daemon=True, name="model-discovery").start()
        complete.wait(budget)
        return self.visible(list(self.catalog))

    def routes(self, model, task=None):
        if model == "free":
            entries = free_auto.ranked({key: value for key, value in self.providers.items()
                                        if key in FREE_COMPATIBLE},task=task)
            from codelaboon import model_health
            def tier(rows):
                names=list(dict.fromkeys(entry.provider for entry in rows))
                queues={name:[entry.model for entry in rows if entry.provider==name and
                              not model_health.blocked(name,self.providers[name],entry.model,coding=True)] for name in names}
                return [(name,models[index]) for index in range(max([len(items) for items in queues.values()]+[0]))
                        for name,models in queues.items() if index<len(models) and self.cooldowns.get(name,0)<=time.monotonic()]
            verified=[entry for entry in entries if model_health.verified(entry.provider,self.providers[entry.provider],entry.model,coding=True)]
            unknown=[entry for entry in entries if entry not in verified]
            return (tier(verified)+tier(unknown))[:12]
        name, separator, identifier = model.partition("/")
        if not separator or name not in COMPATIBLE or name not in self.providers:
            raise ValueError("Unknown codelaboon model")
        if not self.providers[name].validate_api_key():
            raise ValueError(f"Configure {name} with codelaboon configure {name}")
        accepts = getattr(self.providers[name], "accepts", None)
        if accepts and not accepts({"id": identifier}):
            raise ValueError("This provider does not allow that model")
        return [(name, identifier)]

    def request(self, body, api, timeout=(15,180)):
        self.refresh_connections()
        model=body.get('model','')
        if self.model_alias and api=='anthropic' and (model in ('default','sonnet','opus','haiku') or model.startswith('claude-')):
            body=dict(body,model=self.model_alias)
        if self.task_model:body=dict(body,model=self.task_model.removeprefix('codelaboon/'))
        if api == "anthropic" and not body.get("model", "").startswith(("claude/","vercel/","vercel_free/")):
            from codelaboon.anthropic_bridge import MessagesResponse, to_chat
            routed = dict(body, model=body["model"].removesuffix("[1m]"))
            return MessagesResponse(self.request(to_chat(routed), "chat"), body["model"], bool(body.get("stream")))
        if api == "responses" and not body.get("model", "").startswith(("chatgpt/","vercel/","vercel_free/")):
            from codelaboon.responses_bridge import ResponsesResponse, to_chat
            return ResponsesResponse(self.request(to_chat(body), "chat", timeout=timeout), body)
        if api=='chat' and body.get('model','').startswith('task/'):
            if os.environ.get('CODELABOON_HEADLESS_TASK')=='1':raise ValueError('Workers cannot recursively route to task conversations')
            if set(self.providers)=={'local'}:raise ValueError('Open task conversations in a regular engine session; this gateway permits local inference only')
            from codelaboon.task_chat import TaskResponse
            return TaskResponse(body['model'][5:],body)
        if self.task_system_prompt:
            body=dict(body)
            if api=='chat':body['messages']=[{'role':'system','content':self.task_system_prompt},*body.get('messages',[])]
            elif api=='responses':body['instructions']=str(body.get('instructions') or '')+'\n\n'+self.task_system_prompt
            elif api=='anthropic':
                original=body.get('system') or []
                if isinstance(original,str):original=[{'type':'text','text':original}]
                body['system']=[*original,{'type':'text','text':self.task_system_prompt}]
            elif api=='google':
                original=body.get('systemInstruction') or {}
                body['systemInstruction']={**original,'parts':[*original.get('parts',[]),{'text':self.task_system_prompt}]}
        from codelaboon import routing_metrics
        category=routing_metrics.task_class(body.get('messages',[]),self.task_class)
        routes = self.routes(body.get("model", ""),task=category)
        if not routes:
            raise FreeRoutingUnavailable("No free coding model is currently ready. Configured free providers may be cooling down or unavailable; no paid fallback was used.")
        failures = []
        for name, model in routes:
            if body.get("model")=="free" and self.cooldowns.get(name,0)>time.monotonic():
                continue
            provider = self.providers[name]
            payload = dict(body, model=model)
            if name=='vercel_free':
                options=payload.get('providerOptions',{})
                routing=options.get('gateway',{}) if isinstance(options,dict) else {}
                if isinstance(routing,dict) and (routing.get('models') or routing.get('byok')):
                    raise ValueError('Vercel free models do not accept upstream model fallbacks or request-scoped BYOK')
            if name=='openrouter_free':
                options=payload.get('provider',{})
                payload['provider']={**(options if isinstance(options,dict) else {}),'max_price':{'prompt':0,'completion':0}}
            headers = {"content-type": "application/json", "user-agent": "codelaboon"}
            credential = provider.credential() if hasattr(provider, "credential") else provider.api_key.strip()
            subscription = False
            google_oauth = False
            if name == "chatgpt":
                credential, subscription = provider._credential()
            if credential:
                headers["authorization"] = f"Bearer {credential}"
            if api == "anthropic":
                if name in ('vercel','vercel_free'):
                    headers['anthropic-version']='2023-06-01'
                elif name != "claude":
                    raise ValueError("Messages requires a Claude model")
                else:
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
                if name not in ("chatgpt","vercel","vercel_free"):
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
                    try:
                        credential, _ = provider._credential()
                        instance = provider._ensure_slot(credential, model)
                    except (ValueError, requests.RequestException) as error:
                        if self.health_checks:
                            from codelaboon import model_health
                            from codelaboon.model_health import observe,failure
                            observe(name,provider,model,failure(error))
                        if body.get("model") != "free":
                            raise
                        self.cooldowns[name] = time.monotonic() + 30
                        if self.health_checks:model_health.defer(name,provider,60)
                        failures.append("freebuff: admission failed")
                        continue
                    metadata = provider._completion_body(model, payload.get("messages", []), instance, payload)
                    payload = {**payload, "codebuff_metadata": metadata["codebuff_metadata"], "provider": metadata["provider"]}
                    url = f"{provider.base_url.rstrip('/')}/api/v1/chat/completions"
                    headers["authorization"] = f"Bearer {credential}"
                    headers["x-freebuff-client-version"] = __version__
            if name=='copilot':headers=provider.headers(payload.get('messages',[]))
            started=time.monotonic()
            try:
                transport = self.local if name == "local" else requests
                response = transport.post(url, headers=headers, json=payload,
                                          stream=True, timeout=timeout, allow_redirects=False)
            except requests.RequestException:
                if self.health_checks:
                    from codelaboon.model_health import observe
                    observe(name,provider,model,"unavailable")
                self.cooldowns[name] = time.monotonic() + 30
                if self.health_checks:routing_metrics.observe(name,provider,model,category,'failed',time.monotonic()-started)
                failures.append(f"{name}: connection failed")
                continue
            if body.get('model')=='free' and 200<=response.status_code<300:
                try:upstream_error=early_stream_error(response)
                except requests.RequestException:upstream_error='upstream stream failed before a reply'
                if upstream_error:
                    # Account gates can arrive as successful HTTP responses with SSE errors.
                    # Never forward a billing gate as a model reply or repeat that account.
                    failures.append(f'{name}: upstream rejected the request')
                    delay=300 if any(word in upstream_error.lower() for word in ('credit card','billing','payment','credit balance')) else 60
                    self.cooldowns[name]=time.monotonic()+delay
                    if self.health_checks:
                        from codelaboon import model_health
                        model_health.defer(name,provider,delay)
                    response.close()
                    continue
            if not 200 <= response.status_code < 300 and self.health_checks and self.health_applies(name,provider):
                from codelaboon import model_health
                model_health.observe(name,provider,model,model_health.classify(response.status_code))
            if not 200 <= response.status_code < 300 and body.get("model") == "free":
                if name=='vercel_free':
                    try:detail=str(response.json()).lower()
                    except (ValueError,requests.RequestException):detail=''
                    if any(word in detail for word in ('credit card','billing','payment','credit balance')):
                        self.cooldowns[name]=time.monotonic()+300
                        if self.health_checks:
                            from codelaboon import model_health
                            model_health.defer(name,provider,300)
                failures.append(f"{name}: HTTP {response.status_code}")
                from codelaboon import model_health
                if self.health_checks:
                    model_health.observe(name,provider,model,model_health.classify(response.status_code))
                if response.status_code in (401,402,403,429) or response.status_code>=500:
                    delay=max(retry_delay(response),int(self.cooldowns.get(name,0)-time.monotonic()))
                    self.cooldowns[name] = time.monotonic() + delay
                    if self.health_checks:model_health.defer(name,provider,delay)
                if self.health_checks:routing_metrics.observe(name,provider,model,category,'failed',time.monotonic()-started)
                response.close()
                continue
            response.codelaboon_google_oauth = google_oauth
            if self.health_checks and api=='chat' and routing_metrics.enabled():
                return routing_metrics.MeasuredResponse(response,name,provider,model,category,started)
            return response
        waits=[max(1,int(until-time.monotonic())) for until in self.cooldowns.values() if until>time.monotonic()]
        raise FreeRoutingUnavailable("No free coding model answered. " + "; ".join(failures)+". The local gateway is running; upstream providers are unavailable. No paid fallback was used.",min(waits) if waits else 60)


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
            path=urlsplit(self.path)
            if path.path == "/v1/work/status":
                from codelaboon.work import status
                try:
                    state = status()
                    return self.document(200, {key: state[key] for key in
                        ("running", "paused", "completed", "pending", "cooldowns")})
                except (OSError, ValueError, KeyError):
                    return self.document(200, {"running": False, "pending": [], "completed": 0})
            if path.path != "/v1/models":
                return self.document(404, {"error": {"message": "Unknown endpoint"}})
            rows=[
                {"id": row["id"], "object": "model", "type": "model", "display_name": row["name"],
                 "created_at": "1970-01-01T00:00:00Z",
                 "owned_by": "codelaboon"}
                for row in gateway.models()
            ]
            query=parse_qs(path.query,keep_blank_values=True)
            try:
                if any(len(query[key])!=1 for key in ('limit','after_id','before_id') if key in query):
                    raise ValueError('Pagination parameters must not be repeated')
                if 'after_id' in query and 'before_id' in query:
                    raise ValueError('Choose after_id or before_id, not both')
                limit=int(query['limit'][0]) if 'limit' in query else (20 if self.headers.get('anthropic-version') else max(1,len(rows)))
                if not 1<=limit<=1000 and 'limit' in query:raise ValueError('Model page limit must be between 1 and 1000')
                start,end=0,len(rows)
                identifiers=[row['id'] for row in rows]
                if 'after_id' in query:start=identifiers.index(query['after_id'][0])+1
                if 'before_id' in query:end=identifiers.index(query['before_id'][0])
                if 'before_id' in query:
                    start=max(0,end-limit);more=start>0
                else:
                    more=start+limit<end;end=min(end,start+limit)
                rows=rows[start:end]
            except ValueError:
                return self.document(400,{'type':'error','error':{'type':'invalid_request_error','message':'Invalid model pagination parameters or unknown cursor'}})
            self.document(200, {"object": "list", "data":rows,"has_more":more,
                "first_id":rows[0]['id'] if rows else None,"last_id":rows[-1]['id'] if rows else None})

        def do_POST(self):
            if not self.authorized():
                return self.document(401, {"error": {"message": "Unauthorized"}})
            path = urlsplit(self.path)
            api = {"/v1/chat/completions": "chat", "/v1/responses": "responses", "/v1/messages": "anthropic", "/v1/messages/count_tokens": "anthropic"}.get(path.path)
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
                if path.path == "/v1/messages/count_tokens":
                    if not isinstance(body, dict):
                        raise ValueError("Expected an object")
                    # No provider tokenizer is available; use a conservative local
                    # estimate for client context management, never billing.
                    size = len(json.dumps({key: body.get(key, []) for key in
                                          ("system", "messages", "tools")}, ensure_ascii=False).encode())
                    return self.document(200, {"input_tokens": (size + 2) // 3})
                if api == "google" and isinstance(body, dict):
                    body = dict(body, model=google, stream=operation == "streamGenerateContent")
                if not isinstance(body, dict) or not isinstance(body.get("model"), str):
                    raise ValueError("Expected an object with a model")
                response = gateway.request(body, api)
            except FreeRoutingUnavailable as error:
                data=json.dumps({'type':'error','error':{'type':'overloaded_error','message':str(error),'retry_after':error.retry_after}}).encode()
                self.send_response(503);self.send_header('Content-Type','application/json')
                self.send_header('Retry-After',str(error.retry_after));self.send_header('Content-Length',str(len(data)))
                self.end_headers();self.wfile.write(data);return
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
def serve(providers,task_class=None,*,port=0,token=None,model_alias=None,reload_providers=None):
    gateway = Gateway(providers,task_class=task_class)
    if reload_providers is not None:
        from codelaboon.connections import revision
        gateway.reload_providers=reload_providers;gateway.connection_revision=revision()
    if token is not None:
        if not isinstance(token,str) or len(token)<32 or not token.isascii() or any(c.isspace() for c in token):
            raise ValueError('Gateway token must contain at least 32 non-whitespace ASCII characters')
        gateway.token=token
    gateway.model_alias=model_alias
    server = ThreadingHTTPServer(("127.0.0.1", port), handler(gateway))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield gateway, f"http://127.0.0.1:{server.server_port}/v1"
    finally:
        gateway.closed.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        gateway.local.close()
        # Native formats remain authoritative; centralize completed conversations
        # after each engine closes without changing any upstream database.
        try:
            from codelaboon.session_transfer import sync_private
            sync_private()
        except (OSError, ValueError):
            pass

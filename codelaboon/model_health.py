"""Account-scoped free-model discovery and real inference/tool health checks."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import secrets
import tempfile
import threading
import time

from codelaboon.paths import config_dir

FREE_PROVIDERS = {'mistral_labs', 'ourfree', 'kilo', 'pollinations', 'openrouter_free', 'freebuff', 'gemini', 'qoder', 'zai_free', 'vercel_free'}
WIRE_PROVIDERS = FREE_PROVIDERS - {'gemini', 'qoder'}
TTL = 4*3600
_LOCK = threading.RLock()
_READ_CACHE = [None, None]


def enabled():
    return os.environ.get('CODELABOON_MODEL_CHECKS', '1') != '0'


def scope(name, provider):
    values = [name, str(getattr(provider, 'base_url', '')), str(getattr(provider, 'api_key', ''))]
    environments = {'gemini': ['GEMINI_API_KEY', 'GOOGLE_API_KEY'], 'freebuff': ['FREEBUFF_API_KEY', 'CODEBUFF_API_KEY'],
                    'qoder': ['QODER_PERSONAL_ACCESS_TOKEN', 'QODER_PAT'], 'openrouter_free': ['OPENROUTER_API_KEY'], 'zai_free': ['ZAI_API_KEY'], 'vercel_free':['AI_GATEWAY_API_KEY'], 'mistral_labs':['MISTRAL_API_KEY']}
    values.extend(os.environ.get(key, '') for key in environments.get(name, []))
    session = config_dir()/(name+'-session.json')
    try:
        session_stat=session.stat()
    except OSError:
        session_stat=None
    if session_stat is not None and session_stat.st_size < 65536:
        try:
            value = json.loads(session.read_text())
            identity = next((value[key] for key in ('refresh_token', 'refreshToken', 'account_id', 'email', 'user_id') if value.get(key)), value)
            values.append(json.dumps(identity, sort_keys=True))
        except (OSError, ValueError, TypeError, AttributeError):
            pass
    return hashlib.sha256(json.dumps(values).encode()).hexdigest()


def _read(path):
    try:
        stat=path.stat()
        stamp=(str(path),stat.st_ino,stat.st_mtime_ns,stat.st_size)
        if stamp==_READ_CACHE[0]:
            return _READ_CACHE[1]
        value=json.loads(path.read_text()) if stat.st_size<2_000_000 else {}
    except (OSError,ValueError):
        stamp=None;value={}
    if not isinstance(value,dict) or value.get('format')!=1 or not all(isinstance(value.get(k),dict) for k in ('models','catalogs')):
        value={'format':1,'models':{},'catalogs':{}}
    import math
    value['models']={key:row for key,row in value['models'].items() if isinstance(row,dict)
                     and isinstance(row.get('status'),str) and all(isinstance(row.get(k),(int,float))
                     and math.isfinite(row[k]) for k in ('checked_at','retry_at'))}
    value['catalogs']={key:row for key,row in value['catalogs'].items() if isinstance(row,dict)
                       and isinstance(row.get('checked_at'),(int,float)) and math.isfinite(row['checked_at']) and isinstance(row.get('models'),list)
                       and all(isinstance(model,str) and 0<len(model)<512 for model in row['models'])}
    value['backoffs']={key:until for key,until in value.get('backoffs',{}).items() if isinstance(until,(int,float)) and math.isfinite(until)} if isinstance(value.get('backoffs',{}),dict) else {}
    _READ_CACHE[:]=[stamp,value]
    return value


@contextmanager
def database(write=False):
    with _LOCK:
        root=config_dir();path=root/'model-health.json'
        if not write:
            yield _read(path)
            return
        root.mkdir(parents=True,exist_ok=True,mode=0o700)
        with (root/'model-health.lock').open('a+b') as lock:
            lock.write(b'0');lock.flush();lock.seek(0)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(lock.fileno(),msvcrt.LK_LOCK,1)
            else:
                import fcntl
                fcntl.flock(lock,fcntl.LOCK_EX)
            try:
                import copy
                value=copy.deepcopy(_read(path))
                yield value
                if len(value['models'])>4096:
                    value['models']=dict(sorted(value['models'].items(),key=lambda item:item[1]['checked_at'])[-4096:])
                descriptor,temporary=tempfile.mkstemp(prefix='.health-',dir=root)
                try:
                    with os.fdopen(descriptor,'w') as stream:json.dump(value,stream)
                    os.replace(temporary,path)
                    _READ_CACHE[:]=[None,None]
                finally:
                    Path(temporary).unlink(missing_ok=True)
            finally:
                if os.name=='nt':
                    lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)


def record(name,provider,model):
    if not enabled():
        return None
    with database() as value:
        return value['models'].get(scope(name,provider)+'/'+model)


def _observe(name,provider,model,status,tools=None,delay=None,latency_ms=None):
    if not enabled():
        return
    delay = delay if delay is not None else {'working':TTL,'missing':86400,'rate_limited':60,
                                            'auth_required':300,'unavailable':300,'inconclusive':300}.get(status,300)
    row={'provider':name,'model':model,'status':status,'tools':tools,'checked_at':time.time(),
         'retry_at':time.time()+max(1,min(delay,604800))}
    if latency_ms is not None:
        row['latency_ms']=latency_ms
    with database(True) as value:
        key=scope(name,provider)+'/'+model
        previous=value['models'].get(key,{})
        # A normal text response cannot downgrade independently verified tool capability.
        if status=='working' and tools is None and previous.get('tools') is not None:
            row['tools']=previous['tools']
        value['models'][key]=row


def observe(*args,**kwargs):
    # A diagnostic cache failure must not turn a successful model response into a failed turn.
    try:
        return _observe(*args,**kwargs)
    except OSError:
        return False


def blocked(name,provider,model,coding=False):
    row=record(name,provider,model)
    return bool(row and row['retry_at']>time.time() and (row['status']!='working' or (coding and row.get('tools') is False)))


def cooldown(name,provider):
    if not enabled():return 0
    with database() as value:
        return max(0,value.get('backoffs',{}).get(scope(name,provider),0)-time.time())


def defer(name,provider,seconds):
    if not enabled():return
    try:
        with database(True) as value:
            key=scope(name,provider)
            value.setdefault('backoffs',{})[key]=max(value.get('backoffs',{}).get(key,0),time.time()+max(1,min(seconds,3600)))
    except OSError:pass


def verified(name,provider,model,coding=False):
    row=record(name,provider,model)
    return bool(row and row['retry_at']>time.time() and row['status']=='working' and (not coding or row.get('tools') is True))


def catalog(name,provider):
    if name=='vercel_free':
        # Auto may be used before an explicit model-list command. A persisted
        # health roster alone cannot establish the current upstream price.
        provider.refresh_prices()
    live=getattr(provider,'live_models',None)
    if isinstance(live,list):
        allowed=getattr(provider,'priced_free',None)
        return live if allowed is None else [model for model in live if model in allowed]
    if enabled():
        with database() as value:
            row=value['catalogs'].get(scope(name,provider),{})
            if row.get('checked_at',0)+TTL>time.time():
                models=row.get('models')
                allowed=getattr(provider,'priced_free',None)
                return models if allowed is None else [model for model in models if model in allowed]
    return None


def discover(name,provider):
    models=provider.list_models()
    live=getattr(provider,'live_models',None)
    models=list(dict.fromkeys(model for model in models if isinstance(model,str) and 0<len(model)<512))
    if isinstance(live,list):
        with database(True) as value:
            key=scope(name,provider)
            old=value['catalogs'].get(key,{}).get('models',[])
            value['catalogs'][key]={'checked_at':time.time(),'models':models}
            for model in models:
                row=value['models'].get(key+'/'+model,{})
                if model not in old and row.get('status')=='missing':
                    value['models'].pop(key+'/'+model,None)
            # Preserve a diagnostic for stale configured/fallback identifiers, never offer them.
            stale=set(getattr(provider,'models',[]) or []) | set(getattr(provider,'default_models',[]) or [])
            for model in stale-set(models):
                value['models'][key+'/'+model]={'provider':name,'model':model,'status':'missing','tools':None,
                    'checked_at':time.time(),'retry_at':time.time()+86400}
    return models


def eligible(name,provider):
    try:
        usable=bool(provider.validate_api_key())
    except Exception:
        usable=False
    if name not in FREE_PROVIDERS or not usable:
        return False
    if name=='gemini' and (getattr(provider,'api_key','').strip() or os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')):
        return False
    if name=='qoder' and getattr(provider,'_pat',lambda:'')():
        return False
    return True


def classify(status=0,message=''):
    text=message.lower()
    if status==429 or any(word in text for word in ('rate limit','too many requests','quota exceeded')):
        return 'rate_limited'
    if status in (401,402,403) or any(word in text for word in ('unauthorized','invalid api key','no credential','not configured')):
        return 'auth_required'
    if ('model' in text and ('not found' in text or 'does not exist' in text)):
        return 'missing'
    if 'tool' in text and (status in (400,422) or 'unsupported' in text or 'not supported' in text):
        return 'unsupported_tools'
    if status==410 or any(word in text for word in ('model_not_found','unknown model','model does not exist','model not found','model has been deprecated')):
        return 'missing'
    return 'unavailable'


def failure(error):
    response=getattr(error,'response',None)
    status=response.status_code if response is not None else 0
    text=str(error)
    if not status:
        import re
        found=re.search(r'\b(4\d\d|5\d\d)\b',text)
        status=int(found.group()) if found else 0
    return classify(status,text)


def wire(response,timeout):
    deadline=time.monotonic()+timeout
    data=bytearray()
    for chunk in response.iter_content(8192):
        data.extend(chunk)
        if len(data)>262144 or time.monotonic()>deadline:
            raise ValueError('Probe response exceeded bounds')
    text=data.decode('utf-8',errors='replace')
    if not 200<=response.status_code<300:
        return None,classify(response.status_code,text)
    if any(line.startswith('data:') for line in text.splitlines()):
        content=[];calls={}
        for line in text.splitlines():
            if not line.startswith('data:') or line[5:].strip()=='[DONE]':
                continue
            item=json.loads(line[5:])
            if item.get('error'):
                return None,classify(0,str(item['error']))
            for choice in item.get('choices',[]):
                delta=choice.get('delta',choice.get('message',{}))
                content.append(delta.get('content') or '')
                for call in delta.get('tool_calls',[]):
                    target=calls.setdefault(call.get('index',0),{'id':'','type':'function','function':{'name':'','arguments':''}})
                    target['id']=call.get('id') or target['id']
                    for key in ('name','arguments'):
                        target['function'][key]+=call.get('function',{}).get(key) or ''
        return {'role':'assistant','content':''.join(content),'tool_calls':list(calls.values())},None
    item=json.loads(text)
    if item.get('error'):
        return None,classify(0,str(item['error']))
    return item['choices'][0]['message'],None


def probe(name,provider,model,timeout=15,tools=True):
    started=time.monotonic()
    nonce='HEALTH_'+secrets.token_hex(4)
    status='inconclusive';supports=None;retry_delay=None
    try:
        if name in WIRE_PROVIDERS:
            from codelaboon.native_gateway import Gateway
            gateway=Gateway({name:provider},health_checks=False)
            def request(messages,**extra):
                nonlocal retry_delay
                with gateway.request({'model':name+'/'+model,'messages':messages,'stream':False,
                                      'max_tokens':1024,**extra},'chat',timeout=(min(5,timeout),timeout)) as response:
                    if response.status_code==429:
                        raw=getattr(response,'headers',{}).get('Retry-After')
                        if isinstance(raw,str):
                            try:retry_delay=max(1,min(float(raw),604800))
                            except ValueError:
                                try:
                                    from email.utils import parsedate_to_datetime
                                    retry_delay=max(1,min(parsedate_to_datetime(raw).timestamp()-time.time(),604800))
                                except (ValueError,TypeError,OverflowError):pass
                    return wire(response,timeout)
            try:
                messages=[{'role':'user','content':'Reply with exactly '+nonce+'. No explanation.'}]
                answer,error=request(messages)
                if error:
                    status=error
                elif answer.get('content') and nonce in str(answer['content']):
                    status='working'
                    if tools:
                        definition={'type':'function','function':{'name':'health_echo', 'description':'Echo the supplied value',
                            'parameters':{'type':'object','properties':{'value':{'type':'string','enum':[nonce]}},'required':['value']}}}
                        instruction=[{'role':'user','content':'Call health_echo with value '+nonce+'.'}]
                        call,error=request(instruction,tools=[definition],tool_choice={'type':'function','function':{'name':'health_echo'}})
                        if error=='unsupported_tools':
                            call,error=request(instruction,tools=[definition])
                        supports=False
                        if error in ('rate_limited','auth_required','unavailable'):
                            status=error
                        if not error and call.get('tool_calls'):
                            calls=call['tool_calls']
                            valid=all(row.get('id') and row['function']['name']=='health_echo' and
                                      json.loads(row['function']['arguments']).get('value')==nonce for row in calls)
                            if valid:
                                receipt='TOOL_RESULT_'+secrets.token_hex(6)
                                follow=instruction+[dict(call,role='assistant')]+[
                                    {'role':'tool','tool_call_id':row['id'],'content':receipt} for row in calls]+[
                                    {'role':'user','content':'Return exactly the receipt from the tool result, not the original input.'}]
                                final,error=request(follow,tools=[definition])
                                supports=not error and receipt in str((final or {}).get('content',''))
                                if error in ('rate_limited','auth_required','unavailable'):
                                    status=error
                                    supports=None
            finally:
                gateway.closed.set()
                gateway.local.close()
        else:
            answer=provider.chat(model,[{'role':'user','content':'Reply with exactly '+nonce}],max_tokens=512,timeout=timeout)
            status='working' if isinstance(answer,str) and nonce in answer else 'inconclusive'
    except Exception as error:
        status=failure(error)
    observe(name,provider,model,status,supports,delay=retry_delay if status=='rate_limited' else None,latency_ms=round((time.monotonic()-started)*1000))
    return {'provider':name,'model':model,'status':status,'tools':supports}


def check_provider(name,provider,timeout=15,tools=True,force=False,closed=None,limit=None,models=None,on_update=None):
    rows=[]
    def emit(row):
        rows.append(row)
        if on_update:on_update(row)
    if not eligible(name,provider):
        emit({'provider':name,'status':'skipped','reason':'Free credentials unavailable or paid credential lane'})
        return rows
    with database() as value:
        until=value.get('backoffs',{}).get(scope(name,provider),0)
    if until>time.time():
        emit({'provider':name,'status':'deferred','reason':'Provider retry window','retry_at':until})
        return rows
    try:
        models=discover(name,provider) if models is None else list(models)
    except Exception as error:
        emit({'provider':name,'status':'unavailable','reason':type(error).__name__})
        return rows
    # Unchecked models go first on the next sweep; one permanently rate-limited ID cannot starve the catalog.
    def priority(model):
        row=record(name,provider,model)
        return (0,0) if row is None else (1,row['retry_at'])
    models.sort(key=priority)
    tested=0
    for model in models:
        if closed is not None and closed.is_set():
            break
        cached=record(name,provider,model)
        if not force and cached and cached['retry_at']>time.time() and (not tools or cached.get('tools') is not None or cached['status']!='working'):
            emit(dict(cached,cached=True))
            continue
        if limit is not None and tested>=limit:
            break
        emit(probe(name,provider,model,timeout,tools))
        tested+=1
        if rows[-1]['status'] in ('rate_limited','auth_required'):
            saved=record(name,provider,model)
            with database(True) as value:
                value.setdefault('backoffs',{})[scope(name,provider)]=saved['retry_at'] if saved else time.time()+60
            # Do not exhaust a shared free quota by hammering every remaining model.
            for item in models[models.index(model)+1:]:
                emit({'provider':name,'model':item,'status':'deferred','reason':'Provider rate limit or authentication unavailable'})
            break
    return rows


def check(providers,timeout=15,tools=True,force=False,on_update=None):
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs=[pool.submit(check_provider,name,provider,timeout,tools,force,on_update=on_update) for name,provider in providers.items() if name in FREE_PROVIDERS]
        return [row for job in jobs for row in job.result()]

"""Scoped security assessments, bounded evidence and native tool cases."""
import argparse
from datetime import datetime,timezone
import hashlib
import http.client
import ipaddress
import json
import re
from pathlib import Path
import shutil
import socket
import ssl
import time
from urllib.parse import urlsplit,urlunsplit
import xml.etree.ElementTree as ET

CHECKS=('headers','tls','exposure')


def identity(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def target(value):
    parsed=urlsplit(value)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Targets must be explicit HTTP(S) URLs without credentials, query or fragment')
    host=parsed.hostname.encode('idna').decode().lower();port=parsed.port or (443 if parsed.scheme=='https' else 80)
    authority=('['+host+']' if ':' in host else host)+(':'+str(port))
    return urlunsplit((parsed.scheme,authority,parsed.path or '/', '', ''))


def create_scope(targets,checks=CHECKS,max_requests=12,timeout=5):
    if not targets or not set(checks)<=set(CHECKS) or not checks:raise ValueError('Provide targets and supported checks')
    if not 1<=max_requests<=100 or not 1<=timeout<=30:raise ValueError('Scope request/time budgets are out of range')
    entries=[]
    for value in dict.fromkeys(target(v) for v in targets):
        parsed=urlsplit(value)
        addresses=sorted({str(ipaddress.ip_address(row[4][0])) for row in socket.getaddrinfo(parsed.hostname,parsed.port,type=socket.SOCK_STREAM)})
        entries.append({'url':value,'addresses':addresses})
    return {'format':1,'created':time.time(),'expires':time.time()+86400,'targets':entries,'checks':list(checks),'max_requests':max_requests,'timeout':timeout}


def validate_scope(scope,approved):
    if identity(scope)!=approved or scope.get('format')!=1:raise ValueError('Scope changed or was not explicitly approved')
    if not scope.get('targets') or not scope.get('checks') or not set(scope.get('checks',[]))<=set(CHECKS):raise ValueError('Invalid assessment scope')
    if scope.get('expires',0)<time.time():raise ValueError('Assessment scope expired; approve a fresh scope')
    if type(scope.get('max_requests')) is not int or not 1<=scope.get('max_requests',0)<=100 or not 1<=scope.get('timeout',0)<=30:raise ValueError('Invalid scope budgets')
    for entry in scope['targets']:
        if target(entry['url'])!=entry['url'] or not entry.get('addresses'):raise ValueError('Invalid approved target')
        for address in entry['addresses']:ipaddress.ip_address(address)
    return scope


def write_new(path,value):
    import os
    path=Path(path).resolve();path.parent.mkdir(parents=True,exist_ok=True)
    with os.fdopen(os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as stream:json.dump(value,stream,indent=2)
    return path


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self,host,port,address,timeout):
        super().__init__(host,port,timeout=timeout,context=ssl.create_default_context());self.address=address
    def connect(self):
        raw=socket.create_connection((self.address,self.port),self.timeout)
        try:self.sock=self._context.wrap_socket(raw,server_hostname=self.host)
        except BaseException:raw.close();raise


def assess(scope,approved):
    validate_scope(scope,approved);started=time.time();evidence=[];findings=[];checks=[];remaining=scope['max_requests']
    def finding(kind,url,severity,proof,description,fix):
        findings.append({'id':identity({'kind':kind,'target':url})[:20],'rule':kind,'target':url,'severity':severity,
                         'status':'confirmed_observation','evidence':proof,'description':description,'remediation':fix,
                         'applicability':'Review deployment context before assigning exploitability or a CVSS score.'})
    for entry in scope['targets']:
        url=entry['url'];parsed=urlsplit(url);address=entry['addresses'][0]
        for check in scope['checks']:
            if check=='tls' and parsed.scheme!='https':
                checks.append({'target':url,'check':check,'status':'not_applicable'});continue
            if remaining<=0:checks.append({'target':url,'check':check,'status':'budget_exhausted'});continue
            remaining-=1;connection=None;proof='';begin=time.monotonic()
            try:
                if check=='tls':
                    with socket.create_connection((address,parsed.port),scope['timeout']) as raw:
                        with ssl.create_default_context().wrap_socket(raw,server_hostname=parsed.hostname) as secured:
                            item={'target':url,'address':address,'check':check,'tls_version':secured.version(),'certificate_validated':True}
                else:
                    connection=PinnedHTTPS(parsed.hostname,parsed.port,address,scope['timeout']) if parsed.scheme=='https' else http.client.HTTPConnection(address,parsed.port,timeout=scope['timeout'])
                    connection.request('GET',parsed.path,headers={'Host':parsed.netloc,'User-Agent':'Codelaboon-Scoped-Assessment/1','Connection':'close'})
                    response=connection.getresponse();body=response.read(8192)
                    headers={k.lower():v for k,v in response.getheaders() if k.lower() in ('content-type','content-security-policy','x-content-type-options','strict-transport-security','referrer-policy','location')}
                    if 'location' in headers:
                        location=urlsplit(headers['location']);headers['location']=urlunsplit((location.scheme,location.netloc.rsplit('@',1)[-1],location.path,'',''))
                    # Redirects are observed, never followed; cookies/credentials/body are not copied.
                    item={'target':url,'address':address,'check':check,'http_status':response.status,'headers':headers,
                          'body_sample_sha256':hashlib.sha256(body).hexdigest(),'sample_bytes':len(body)}
                item['id']=identity(item)[:20];evidence.append(item);proof=item['id']
                if check=='headers' and 200<=response.status<300:
                    required=['x-content-type-options']
                    if 'text/html' in headers.get('content-type','').lower():required.append('content-security-policy')
                    if parsed.scheme=='https':required.append('strict-transport-security')
                    for header in required:
                        if header not in headers:
                            finding('missing-'+header,url,'low',proof,'The observed response omitted '+header+'.','Configure '+header+' for the intended response type and retest.')
                if check=='exposure' and response.status==200:
                    git_head=parsed.path.endswith('/.git/HEAD') and body.strip().startswith(b'ref: refs/')
                    env_file=parsed.path.endswith('/.env') and 'text/html' not in headers.get('content-type','') and any(re.match(rb'^[A-Z_][A-Z0-9_]{2,}=',line.strip()) for line in body.splitlines())
                    if git_head or env_file:finding('sensitive-file-exposure',url,'medium',proof,'An explicitly scoped repository/configuration path returned recognizable content. No secrets were retained.','Deny public access to repository/configuration files; rotate exposed secrets if independently confirmed.')
                checks.append({'target':url,'check':check,'status':'completed','evidence':proof,'seconds':round(time.monotonic()-begin,3)})
            except ssl.SSLCertVerificationError:
                item={'target':url,'address':address,'check':check,'error':'certificate_verification_failed'};item['id']=identity(item)[:20];evidence.append(item)
                finding('tls-certificate-trust',url,'medium',item['id'],'The client could not validate the target certificate with its configured trust store.','Correct the chain/hostname/validity or configure the intended private trust store; retest.')
                checks.append({'target':url,'check':check,'status':'completed','evidence':item['id']})
            except (OSError,http.client.HTTPException) as error:
                checks.append({'target':url,'check':check,'status':'inconclusive','error_type':type(error).__name__})
            finally:
                if connection:connection.close()
    return {'format':1,'scope_id':approved,'started':started,'finished':time.time(),'requests_used':scope['max_requests']-remaining,
            'checks':checks,'evidence':evidence,'findings':list({row['id']:row for row in findings}.values()),'coverage':list(scope['checks'])}


def capabilities():
    tools=[]
    for name in ('nmap','semgrep','trivy','nuclei','testssl.sh'):
        tools.append({'tool':name,'available':bool(shutil.which(name)),'path':shutil.which(name)})
    return {'builtin_checks':list(CHECKS),'tools':tools,'tool_execution':'External tools require a scope-bound case; missing tools are never claimed to have run.'}


def nmap_case(scope,approved,url,scan='connect',ttl=300):
    validate_scope(scope,approved);url=target(url)
    entry=next((entry for entry in scope['targets'] if entry['url']==url),None)
    if not entry:raise ValueError('Tool target is outside the approved scope')
    program=shutil.which('nmap')
    if not program:raise ValueError('nmap is unavailable; install it explicitly before creating a tool case')
    if scan not in ('connect','syn'):raise ValueError('Unsupported scan type')
    parsed=urlsplit(url);address=entry['addresses'][0]
    argv=[program,'-sS' if scan=='syn' else '-sT','-n','-Pn','--max-retries','1','--host-timeout','60s','-p',str(parsed.port),'-oX','-',address]
    if ':' in address:argv.insert(1,'-6')
    from codelaboon.privilege import create
    return create(argv,'Approved security scope '+approved+'; exact target '+url,ttl=ttl,timeout=90)


def import_nmap(scope,approved,path):
    validate_scope(scope,approved);raw=Path(path).read_bytes()
    if len(raw)>8*1024*1024 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('Unsupported or oversized XML evidence')
    allowed={(address,urlsplit(entry['url']).port) for entry in scope['targets'] for address in entry['addresses']}
    findings=[]
    for host in ET.fromstring(raw).findall('host'):
        addresses=[row.get('addr') for row in host.findall('address') if row.get('addrtype') in ('ipv4','ipv6')]
        if not addresses or any(address not in {a for a,p in allowed} for address in addresses):raise ValueError('External evidence contains an out-of-scope host')
        for port in host.findall('ports/port'):
            if port.get('protocol')!='tcp':raise ValueError('External evidence protocol is outside HTTP(S) scope')
            value=int(port.get('portid'))
            if not any((address,value) in allowed for address in addresses):raise ValueError('External evidence contains an out-of-scope host/port')
            if port.find('state') is not None and port.find('state').get('state')=='open':
                findings.append({'target':addresses[0],'port':value,'observation':'open_port','severity':'info','status':'tool_observation','evidence_sha256':hashlib.sha256(raw).hexdigest()})
    return {'scope_id':approved,'tool':'nmap','findings':findings,'evidence_sha256':hashlib.sha256(raw).hexdigest()}


def main(arguments=None):
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='action',required=True)
    commands.add_parser('capabilities')
    scope_cmd=commands.add_parser('scope');scope_cmd.add_argument('--target',action='append',required=True);scope_cmd.add_argument('--check',action='append',choices=CHECKS);scope_cmd.add_argument('--output',required=True);scope_cmd.add_argument('--max-requests',type=int,default=12)
    for name in ('assess','tool-case','import-nmap'):
        command=commands.add_parser(name);command.add_argument('--scope',required=True);command.add_argument('--approve',required=True)
        if name=='tool-case':command.add_argument('--target',required=True);command.add_argument('--scan',choices=['connect','syn'],default='connect')
        else:command.add_argument('--output',required=True)
        if name=='import-nmap':command.add_argument('--source',required=True)
    args=parser.parse_args(arguments)
    try:
        if args.action=='capabilities':print(json.dumps(capabilities(),indent=2));return
        if args.action=='scope':
            scope=create_scope(args.target,args.check or CHECKS,args.max_requests);write_new(args.output,scope)
            print(json.dumps({'scope_id':identity(scope),'file':args.output,'targets':scope['targets']},indent=2));return
        scope=json.loads(Path(args.scope).read_text())
        if args.action=='tool-case':
            case,path=nmap_case(scope,args.approve,args.target,args.scan);print(json.dumps({'case':case,'file':str(path)},indent=2));return
        report=assess(scope,args.approve) if args.action=='assess' else import_nmap(scope,args.approve,args.source)
        write_new(args.output,report);print(json.dumps({'report':args.output,'findings':len(report['findings'])},indent=2))
    except (OSError,ValueError,KeyError,TypeError,ET.ParseError) as error:parser.exit(1,'Security assessment: '+str(error)+'\n')

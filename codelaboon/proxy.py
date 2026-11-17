"""Stable loopback gateway for editors and desktop inference clients."""
import argparse
import os
from pathlib import Path
import secrets
import threading

from codelaboon.paths import config_dir


def credential(path):
    """Keep the desktop credential stable across server restarts."""
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    try:
        descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError:
        token=path.read_text(encoding='utf-8').strip()
    else:
        token=secrets.token_urlsafe(32)
        with os.fdopen(descriptor,'w',encoding='utf-8') as stream:stream.write(token+'\n')
    if len(token)<32 or not token.isascii() or any(character.isspace() for character in token):
        raise ValueError('Invalid proxy token file; provide a token of at least 32 characters')
    return token


def main(arguments=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8766,help='Loopback port (default: 8766)')
    parser.add_argument('--token-file',type=Path,default=config_dir()/'proxy.token')
    parser.add_argument('--model',default='free',help='Destination for Claude built-in model names (default: free)')
    parser.add_argument('--show-token',action='store_true',help='Print the local gateway key for client setup')
    args=parser.parse_args(arguments)
    if not 1<=args.port<=65535:parser.error('Port must be between 1 and 65535')
    if not args.model.strip() or (args.model!='free' and '/' not in args.model):
        parser.error('Choose free or PROVIDER/MODEL')
    try:
        token=credential(args.token_file)
        if args.show_token:
            print(token);return
        from codelaboon.cli import CodelaboonCLI
        from codelaboon.native_gateway import serve
        cli=CodelaboonCLI();cli.load_providers()
        with serve(cli.providers,port=args.port,token=token,model_alias=args.model) as (_,url):
            print('Codelaboon proxy: '+url.removesuffix('/v1'),flush=True)
            print('Claude Desktop: Help > Troubleshooting > Enable Developer Mode; then Developer > Configure Third-Party Inference.',flush=True)
            print('Choose Gateway, Static API key, Bearer. Use the base URL above (without /v1).',flush=True)
            print('Read the gateway key with: codelaboon proxy --show-token --token-file "'+str(args.token_file)+'"',flush=True)
            print('Claude built-in model names route to '+args.model+'. Keep this terminal open; Ctrl+C stops the proxy.',flush=True)
            # Finite waits keep Ctrl+C responsive on Python 3.11-3.13 Windows.
            stopped=threading.Event()
            while not stopped.wait(1):pass
    except KeyboardInterrupt:pass
    except (OSError,ValueError) as error:parser.exit(1,'Proxy: '+str(error)+'\n')


if __name__=='__main__':main()

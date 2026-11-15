"""Official editor integrations using on-demand Codelaboon engine gateways."""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import shlex
import sysconfig
import subprocess
import sys
import tempfile
import zipfile

from codelaboon.paths import config_dir


def wrapper_path():
    root=config_dir()/'integrations/vscode'
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    if os.name=='nt':
        candidates=[shutil.which('codelaboon-claude-vscode.exe'),
                    str(Path(sysconfig.get_path('scripts'))/'codelaboon-claude-vscode.exe'),
                    str(Path(sysconfig.get_path('scripts',scheme='nt_user'))/'codelaboon-claude-vscode.exe')]
        for candidate in candidates:
            if candidate and Path(candidate).is_file():return Path(candidate).resolve()
        raise ValueError('Install the Codelaboon package to register its Windows editor launcher')
    path=root/'claude-wrapper'
    path.write_text('#!/bin/sh\nexec '+shlex.quote(sys.executable)+' -m codelaboon.ide --claude-wrapper "$@"\n')
    path.chmod(0o700)
    return path.resolve()


def build_vsix(destination,bootstrap=None):
    sources=Path(__file__).parent/'integrations/vscode'
    package=json.loads((sources/'package.json').read_text())
    manifest=('<?xml version="1.0" encoding="utf-8"?>'
      '<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011">'
      '<Metadata><Identity Language="en-US" Id="codelaboon" Version="'+package['version']+'" Publisher="codelaboon"/>'
      '<DisplayName>Codelaboon</DisplayName><Description xml:space="preserve">Official engine integrations for Codelaboon</Description>'
      '<Tags>AI,codelaboon,claude</Tags><Categories>AI,Other</Categories><GalleryFlags>Preview</GalleryFlags>'
      '<Properties><Property Id="Microsoft.VisualStudio.Code.Engine" Value="^1.85.0"/>'
      '<Property Id="Microsoft.VisualStudio.Code.ExtensionDependencies" Value="anthropic.claude-code"/>'
      '<Property Id="Microsoft.VisualStudio.Code.ExtensionKind" Value="workspace"/></Properties></Metadata>'
      '<Installation><InstallationTarget Id="Microsoft.VisualStudio.Code"/></Installation><Dependencies/>'
      '<Assets><Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true"/>'
      '<Asset Type="Microsoft.VisualStudio.Services.Content.Details" Path="extension/README.md" Addressable="true"/></Assets></PackageManifest>')
    types=('<?xml version="1.0" encoding="utf-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
           '<Default Extension="json" ContentType="application/json"/><Default Extension="js" ContentType="application/javascript"/>'
           '<Default Extension="md" ContentType="text/markdown"/><Default Extension="vsixmanifest" ContentType="text/xml"/></Types>')
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('extension.vsixmanifest',manifest)
        archive.writestr('[Content_Types].xml',types)
        for name in ('package.json','extension.js','README.md'):
            archive.write(sources/name,'extension/'+name)
        license=Path(__file__).parent.parent/'LICENSE'
        archive.writestr('extension/LICENSE',license.read_text() if license.exists() else 'Personal use only; see https://github.com/zGabrielR1/codelaboon/blob/main/LICENSE')
        if bootstrap is not None: archive.writestr('extension/backend.json',json.dumps(bootstrap))
    return destination


def install(code=None):
    code=code or shutil.which('code')
    if not code: raise ValueError('Install VS Code, or pass --code with its CLI path')
    wrapper=wrapper_path()
    profile=(config_dir()/'claude-code').resolve()
    # Setup generates only isolated preferences; account credentials are not copied.
    from codelaboon.claude_engine import prepare_profile
    prepare_profile(profile)
    with tempfile.TemporaryDirectory(prefix='codelaboon-vscode-') as temporary:
        bootstrap={'wrapper':str(wrapper),'configDir':str(profile),'cli':shutil.which('codelaboon') or 'codelaboon','connectOnInstall':True}
        package=build_vsix(Path(temporary)/'codelaboon.vsix',bootstrap)
        subprocess.run([code,'--install-extension',str(package),'--force'],check=True)
    print('Codelaboon VS Code extension installed. Open Claude Code, or use Codelaboon: Connect Claude Code.')


def claude_wrapper(arguments=None):
    arguments=list(sys.argv[1:] if arguments is None else arguments)
    if arguments and not arguments[0].startswith('-') and Path(arguments[0]).is_file():
        binary=arguments.pop(0)
    else:
        from codelaboon.external_engines import executable
        binary=executable('claude')
    for index,value in enumerate(arguments):
        if value in ('--model','--fallback-model') and index+1<len(arguments):
            model=arguments[index+1]
            if model in ('default','sonnet','opus','haiku') or model.startswith('claude-'):
                arguments[index+1]='free'
    def stopped(signum,frame): raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,stopped)
    if os.name!='nt': signal.signal(signal.SIGHUP,stopped)
    from codelaboon.cli import CodelaboonCLI
    from codelaboon.native_gateway import FREE_COMPATIBLE,serve
    from codelaboon.claude_engine import launch
    cli=CodelaboonCLI();cli.load_providers()
    providers={name:provider for name,provider in cli.providers.items() if name in FREE_COMPATIBLE or name=='local'}
    try:
        with serve(providers) as (gateway,url):
            code=launch(binary,arguments,'coding',False,gateway.models(startup=True),url,gateway.token)
    except KeyboardInterrupt:
        code=130
    raise SystemExit(code)


def main(arguments=None):
    args=list(sys.argv[1:] if arguments is None else arguments)
    if args[:1]==['--claude-wrapper']:
        return claude_wrapper(args[1:])
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['install','wrapper-path'])
    parser.add_argument('--code')
    options=parser.parse_args(args)
    if options.action=='install': install(options.code)
    else: print(wrapper_path())


if __name__=='__main__': main()

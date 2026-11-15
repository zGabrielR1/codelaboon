"""Small offline diagnostics snapshot; never loads a model or probes providers."""
import argparse
import json
from pathlib import Path
import time
from codelaboon.paths import config_dir


def read(path,default=None):
    try:return json.loads(Path(path).read_text())
    except (OSError,ValueError):return default


def snapshot(config=None):
    from codelaboon import __version__
    from codelaboon.work import configuration, status
    from codelaboon.local_runtime import paths
    from codelaboon.routing_metrics import preset,report
    from codelaboon.security_assessment import capabilities
    
    try:
        path,value,runtime=configuration(config);worker=status(path)
        worker['pending_count']=len(worker.get('pending',[]))
        # Return operational fields only, not task objectives/prompts.
        worker={key:worker[key] for key in ('running','paused','pending_count','completed','service','pid','version') if key in worker}
    except (OSError,ValueError,KeyError,TypeError):value={};worker={'configured':False}
    executable,model=paths(value);cases=[]
    for path in (config_dir()/'privilege-cases').glob('*.json'):
        item=read(path,{})
        if item.get('format')==1 and item.get('expires',0)>time.time() and not path.with_suffix('.used').exists():cases.append({'id':path.stem,'expires':item['expires']})
    evaluation=read(config_dir()/'controller-evaluation.json',{})
    return {'version':__version__,'worker':worker,'local_controller':{'runtime_installed':executable.is_file(),'model_installed':model.is_file(),'loading':'on demand',
            'evaluation':{k:evaluation[k] for k in ('time','model','passed','total','false_interventions','missed_drifts') if k in evaluation}},
            'routing':{'preset':preset(),'observations':report()},'security':capabilities(),'pending_privilege_cases':cases}


def main(arguments=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config');parser.add_argument('--json',action='store_true');args=parser.parse_args(arguments)
    print(json.dumps(snapshot(args.config),indent=2))

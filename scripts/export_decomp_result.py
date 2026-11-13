"""Export the isolated cloud-authored change as a reviewable patch."""
import difflib
import hashlib
import json
from pathlib import Path

SOURCE = Path(__file__).resolve().parent.parent
workspace = SOURCE / '.watch/workspaces/digisat-recomp'
baseline = SOURCE / '.watch/baselines/digisat-recomp'
provenance = json.loads((workspace / 'snapshot-provenance.json').read_text(encoding='utf-8'))
original = Path(provenance['original'])
for relative, digest in provenance['files'].items():
    if hashlib.sha256((original / relative).read_bytes()).hexdigest() != digest:
        raise RuntimeError('Original source changed since snapshot: ' + relative)

state = json.loads((SOURCE / '.watch/cloud/state.json').read_text(encoding='utf-8'))
task = 'digisat-recomp-build-failure-manifest-001'
if task not in state['done']:
    raise RuntimeError('Cloud pipeline has not completed its acceptance checks')

paths = ['engenharia/codebase-local/tools/build_workspace.py']
paths += [p.relative_to(workspace).as_posix() for p in
          (workspace / 'engenharia/codebase-local/tests').glob('test_*.py')]
patch = []
for relative in paths:
    before = baseline / relative
    after = workspace / relative
    old = before.read_text(encoding='utf-8').splitlines(keepends=True) if before.exists() else []
    new = after.read_text(encoding='utf-8').splitlines(keepends=True)
    for line in difflib.unified_diff(old, new, fromfile='a/' + relative if before.exists() else '/dev/null',
                                     tofile='b/' + relative):
        patch.append(line if line.endswith('\n') else line + '\n\\ No newline at end of file\n')
artifacts = SOURCE / '.watch/artifacts'
artifacts.mkdir(exist_ok=True)
target = artifacts / 'digisat-recomp-build-manifest.patch'
target.write_text(''.join(patch), encoding='utf-8', newline='\n')
report = {'task': task, 'original_snapshot_files_unchanged': True,
          'patch': str(target), 'files': paths, 'cloud_attempt': state['last_attempts'][task],
          'scope': 'Isolated source tooling; no binary recompilation or equivalence claim'}
(artifacts / 'digisat-recomp-result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(target)

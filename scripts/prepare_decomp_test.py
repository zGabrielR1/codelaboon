"""Copy explicit non-secret source files and queue an isolated build-tool task."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

SOURCE = Path(__file__).resolve().parent.parent


def main():
    original = Path(sys.argv[1]).resolve()
    workspace = SOURCE / '.watch/workspaces/digisat-recomp'
    if workspace.exists():
        raise FileExistsError('Preserving existing test workspace: ' + str(workspace))
    baseline = SOURCE / '.watch/baselines/digisat-recomp'
    files = ['AGENTS.md', 'engenharia/codebase-local/README.md',
             'engenharia/codebase-local/tools/build_workspace.py']
    provenance = {'original': str(original), 'files': {}}
    for relative in files:
        source = original / relative
        for destination in (workspace / relative, baseline / relative):
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        provenance['files'][relative] = hashlib.sha256(source.read_bytes()).hexdigest()
    (workspace / 'snapshot-provenance.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')
    config = json.loads((SOURCE / 'examples/watch-cloud.json').read_text(encoding='utf-8'))
    for task in config['tasks']:
        task['project'] = str((SOURCE / 'examples' / task['project']).resolve())
    config['runtime'] = 'cloud'
    script = 'engenharia/codebase-local/tools/build_workspace.py'
    prompt = (
        'Harden ' + script + ' in this isolated snapshot of the DigiSat recomp/decomp project. '
        'The existing runner loses workspace-build.json when subprocess.run raises TimeoutExpired '
        'or OSError. Record each attempted job including started_utc, finished_utc, project, '
        'exit_code (124 for timeout, 127 for process launch failure), and an error string. '
        'The timeout error must contain the word timeout; launch failures must retain the error message. '
        'Always write the existing workspace-build.json manifest for these handled failures, '
        'exit unsuccessfully, and stop dependent jobs after the first failed attempt. '
        'Preserve source_regenerated=false, target_executed, selected project order, '
        'compile-only/test/source-linked flags, and normal success behavior. '
        'Keep changes small. Add offline unittest coverage using mocked subprocess outcomes. '
        'Only edit this copied build script and new offline tests inside this snapshot. '
        'Do not launch real compilers, rebuild/decompile vendor assemblies, access the original '
        'project, installation, credentials, MongoDB, customer data, services or network. '
        'Do not alter the independent acceptance oracle or Codelaboon. '
        'This is a source-tooling robustness test, not proof of binary equivalence.\n\n'
        'Project instructions:\n' + (workspace / 'AGENTS.md').read_text(encoding='utf-8') +
        '\n\nCurrent source (cloud planner context):\n```python\n' +
        (workspace / script).read_text(encoding='utf-8') + '\n```')
    config['tasks'].append({
        'id': 'digisat-recomp-build-failure-manifest-001', 'project': str(workspace),
        'prompt': prompt, 'verify_argv': [[
            '{python}', '{source}/scripts/check_decomp_build.py', '{project}/' + script],
            ['{python}', '-m', 'unittest', 'discover', '-s',
             'engenharia/codebase-local/tests', '-p', 'test_build_workspace.py', '-v']],
        'verify_timeout_seconds': 60})
    target = SOURCE / '.watch/watch-active.json'
    target.write_text(json.dumps(config, indent=2), encoding='utf-8')
    print('Prepared isolated workspace: ' + str(workspace))
    print('Active queue: ' + str(target))


if __name__ == '__main__':
    main()

"""Scoped rc.3 regeneration and regression evidence; preserves T01/reviewer history."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]


def hashes(paths):
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths)) if p.is_file() and '__pycache__' not in p.parts}


def protected():
    paths=[]
    for base in ['docs/evaluation','docs/execution/reviews','docs/execution/contracts/archive','tests/fixtures']:
        paths.extend(p for p in (ROOT/base).rglob('*') if 'rc3' not in p.parts)
    paths.extend([ROOT/'docs/execution/reports/T01.md',ROOT/'docs/execution/reports/T00-T01-command-log.json'])
    return hashes(paths)


def main():
    before=protected();logs=[]
    node=os.environ.get('WXAGENT_NODE') or str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
    commands=[
        [sys.executable,'docs/execution/contracts/build_contract.py'],
        [sys.executable,'docs/execution/contracts/build_registry.py'],
        [sys.executable,'-m','unittest','discover','-s','tests/contracts/T00','-v'],
        [sys.executable,'-m','unittest','discover','-s','tests/evaluation/T01','-v'],
        [node,'tests/contracts/T00/hash-vector-js.cjs']]
    failed=False
    for command in commands:
        run=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',
            env=dict(os.environ,PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1'))
        logs.append({'command':command,'cwd':str(ROOT),'actualExitCode':run.returncode,'expectedExitCode':0,
            'stdout':run.stdout,'stderr':run.stderr,'mode':'OFFLINE_CONTRACT_SYNTHETIC_MOCK'})
        print(f'{command[1:]}: exit {run.returncode}',flush=True)
        if run.returncode:
            print(run.stdout+run.stderr,flush=True);failed=True;break
    after=protected()
    changed=sorted(k for k in set(before)|set(after) if before.get(k)!=after.get(k))
    if changed:failed=True
    result={'scope':'R02-A rc.3','commands':logs,'protectedFiles':len(before),'protectedChanges':changed,
        'paidCalls':0,'integration':'NOT_RUN','runnerExitCode':1 if failed else 0}
    out=ROOT/'docs/execution/reports/T00-rc3-command-log.json'
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    if not failed:
        paths=[]
        for base in ['docs/adr','docs/api','docs/schemas','docs/execution/contracts']:
            paths.extend(p for p in (ROOT/base).rglob('*') if 'archive' not in p.parts and p.name!='candidate-manifest.json')
        manifest={'version':'1.0.0-rc.3','status':'REVIEW_CANDIDATE_NOT_APPROVED',
            'files':[{'path':k,'sha256':v} for k,v in hashes(paths).items()]}
        (ROOT/'docs/execution/contracts/candidate-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'protectedFiles':len(before),'protectedChanges':changed,'exitCode':result['runnerExitCode']}),flush=True)
    return result['runnerExitCode']


if __name__=='__main__':sys.exit(main())

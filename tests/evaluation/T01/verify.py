"""Reproducible T00/T01 review evidence. No service or paid provider calls."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys

ROOT=Path(__file__).resolve().parents[3]
commands=[
 ('T00',['docs/execution/contracts/build_contract.py'],0),
 ('T00',['docs/execution/contracts/build_registry.py'],0),
 ('T00',['-m','unittest','discover','-s','tests/contracts/T00','-v'],0),
 ('T01',['docs/evaluation/build_representative.py'],0),
 ('T01',['-m','unittest','discover','-s','tests/evaluation/T01','-v'],0),
 ('T01',['docs/evaluation/evaluate.py','--demo','--output','docs/evaluation/results/rc2-demo.json'],0),
 ('T01',['docs/evaluation/evaluate.py','--input','docs/evaluation/examples/unreviewed.json','--output','docs/evaluation/results/rc2-unreviewed-blocked.json'],2),
 ('T00/T01',['tests/contracts/T00/review_probe_rc2.py'],0),
 ('T00',['__NODE__','tests/contracts/T00/hash-vector-js.cjs'],0),
]


def main():
    logs=[]; failed=False
    for task,args,expected in commands:
        if args[0]=='__NODE__':
            node=os.environ.get('WXAGENT_NODE') or shutil.which('node') or str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
            command=[node,*args[1:]]
        else:command=[sys.executable,*args]
        run=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',env=dict(os.environ,PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1'))
        logs.append({'task':task,'command':command,'cwd':str(ROOT),
            'expectedExitCode':expected,'actualExitCode':run.returncode,
            'stdout':run.stdout,'stderr':run.stderr,'mode':'OFFLINE_CONTRACT_OR_SYNTHETIC_MOCK'})
        print(f'{task} {args[0]}: exit {run.returncode} (expected {expected})',flush=True)
        if run.returncode!=expected:
            failed=True
            print(run.stdout+run.stderr,flush=True)
            break
    directory=ROOT/'docs/execution/reports';directory.mkdir(parents=True,exist_ok=True)
    (directory/'T00-T01-command-log.json').write_text(json.dumps(logs,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    if not failed:
        paths=[]
        for base in ['docs/adr','docs/api','docs/schemas','docs/execution/contracts']:
            for p in sorted((ROOT/base).rglob('*')):
                if p.is_file() and '__pycache__' not in p.parts and 'archive' not in p.parts and p.name!='candidate-manifest.json':
                    paths.append({'path':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
        manifest={'version':'1.0.0-rc.2','status':'REVIEW_CANDIDATE_NOT_APPROVED','files':paths}
        (ROOT/'docs/execution/contracts/candidate-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    return 1 if failed else 0


if __name__=='__main__':sys.exit(main())

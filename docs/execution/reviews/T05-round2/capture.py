import hashlib, json, os, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
os.environ['PATH']=str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd')+os.pathsep+os.environ['PATH']
def git(*a):
    p=subprocess.run(['git',*a],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    return {'exitCode':p.returncode,'output':p.stdout,'stderr':p.stderr}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
paths=sorted(set(git('ls-files','--cached','--others','--exclude-standard')['output'].splitlines()))
files=[{'path':p,'sha256':sha(ROOT/p)} for p in paths if (ROOT/p).is_file() and not p.startswith('docs/execution/reviews/T05-round2/') and p!='docs/execution/reviews/T05-Review-v2.0.md']
data={'head':git('rev-parse','HEAD'),'branch':git('branch','--show-current'),'status':git('status','--short'),'files':files}
if not (HERE/'before.json').exists():
    old=json.loads((HERE.parent/'T05-round1/after.json').read_text(encoding='utf-8'))
    oldmap={x['path']:x['sha256'] for x in old['files']}
    comparison={'changedExisting':[f['path'] for f in files if f['path'] in oldmap and f['sha256']!=oldmap[f['path']]],'new':[f['path'] for f in files if f['path'] not in oldmap]}
    author=json.loads((ROOT/'tests/engineering/T05/evidence/revision-v1-final-checks.json').read_text(encoding='utf-8'))
    comparison['authorFingerprints']=[{'path':f['path'],'match':sha(ROOT/f['path'])==f['sha256']} for f in author['sourceFingerprints']]
    (HERE/'input-comparison.json').write_text(json.dumps(comparison,ensure_ascii=False,indent=2),encoding='utf-8')
    (HERE/'before.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(comparison,ensure_ascii=False))
else:
    before=json.loads((HERE/'before.json').read_text(encoding='utf-8'))
    data['changedExisting']=[f['path'] for f in before['files'] if not (ROOT/f['path']).exists() or sha(ROOT/f['path'])!=f['sha256']]
    (HERE/'after.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'files':len(files),'changedExisting':data['changedExisting']}))

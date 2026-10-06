from pathlib import Path
import hashlib, json, os, subprocess
ROOT=Path(__file__).resolve().parents[4]; HERE=Path(__file__).resolve().parent
os.environ['PATH']=str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd')+os.pathsep+os.environ['PATH']
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
review1=HERE.parent/'T06-round1'
files=[{'path':p.relative_to(ROOT).as_posix(),'sha256':digest(p)} for p in sorted(review1.rglob('*')) if p.is_file()]
files.append({'path':'docs/execution/reviews/T06-Review-v1.0.md','sha256':digest(HERE.parent/'T06-Review-v1.0.md')})
baseline=json.loads((ROOT/'tests/engineering/T06/evidence/input-baseline.json').read_text(encoding='utf-8-sig'))['files']
assert len(baseline)==820 and len(set(x['path'] for x in baseline))==820
revision=json.loads((ROOT/'tests/engineering/T06/evidence/revision-v1-fingerprints.json').read_text(encoding='utf-8'))['files']
delivery=json.loads((ROOT/'tests/engineering/T06/evidence/revision-v1-final-checks.json').read_text(encoding='utf-8'))['sourceFingerprints']
checks=[]
for name,items in [('baseline',baseline),('revision',revision),('delivery',[{'path':p,'sha256':h} for p,h in delivery.items()])]:
    checks.append({'scope':name,'count':len(items),'changed':[x['path'] for x in items if not (ROOT/x['path']).is_file() or digest(ROOT/x['path'])!=x['sha256']]})
old=json.loads((review1/'reviewed-files.json').read_text(encoding='utf-8'))['files']
changed=[x['path'] for x in old if digest(ROOT/x['path'])!=x['sha256']]
(HERE/'input-snapshot.json').write_text(json.dumps({'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'checks':checks,'changesSinceRound1':changed,'priorReviewFiles':files,'reviewedFiles':[{'path':p,'sha256':h} for p,h in delivery.items()]+revision},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'checks':checks,'changesSinceRound1':changed},ensure_ascii=False))

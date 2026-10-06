from pathlib import Path
import hashlib,json,os,subprocess
ROOT=Path(__file__).resolve().parents[4]; HERE=Path(__file__).resolve().parent
os.environ['PATH']=str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd')+os.pathsep+os.environ['PATH']
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
prior=[]
for round in [1,2]:
    paths=[p for p in (HERE.parent/('T06-round'+str(round))).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    paths.append(HERE.parent/('T06-Review-v'+str(round)+'.0.md'))
    prior.extend({'path':p.relative_to(ROOT).as_posix(),'sha256':digest(p)} for p in paths)
baseline=json.loads((ROOT/'tests/engineering/T06/evidence/input-baseline.json').read_text(encoding='utf-8-sig'))['files']
assert len(baseline)==820 and len(set(x['path'] for x in baseline))==820
revision=json.loads((ROOT/'tests/engineering/T06/evidence/revision-v2-fingerprints.json').read_text(encoding='utf-8'))['files']
delivery=json.loads((ROOT/'tests/engineering/T06/evidence/revision-v2-final-checks.json').read_text(encoding='utf-8'))['sourceFingerprints']
items=[{'path':p,'sha256':h} for p,h in delivery.items()]
checks=[{'scope':name,'count':len(records),'changed':[x['path'] for x in records if not (ROOT/x['path']).is_file() or digest(ROOT/x['path'])!=x['sha256']]} for name,records in [('baseline',baseline),('revision',revision),('delivery',items)]]
old=json.loads((HERE.parent/'T06-round2/reviewed-files.json').read_text(encoding='utf-8'))['files']
changed=[x['path'] for x in old if digest(ROOT/x['path'])!=x['sha256']]
out={'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'checks':checks,'changesSinceRound2':changed,'priorReviewFiles':prior,'reviewedFiles':items+revision}
(HERE/'input-snapshot.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'checks':checks,'changesSinceRound2':changed},ensure_ascii=False))

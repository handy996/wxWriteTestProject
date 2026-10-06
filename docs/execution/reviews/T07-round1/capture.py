from pathlib import Path
import hashlib,json,os,subprocess
ROOT=Path(__file__).resolve().parents[4]; HERE=Path(__file__).resolve().parent
os.environ['PATH']=str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd')+os.pathsep+os.environ['PATH']
def changed(rows): return [x['path'] for x in rows if not (ROOT/x['path']).is_file() or hashlib.sha256((ROOT/x['path']).read_bytes()).hexdigest()!=x['sha256']]
baseline=json.loads((ROOT/'tests/engineering/T07/evidence/input-baseline.json').read_text(encoding='utf-8'))['files']
delivery=json.loads((ROOT/'tests/engineering/T07/evidence/final-checks.json').read_text(encoding='utf-8'))['files']
t06=json.loads((ROOT/'docs/execution/reviews/T06-round4/input-snapshot.json').read_text(encoding='utf-8'))['reviewedFiles']
checks=[{'scope':n,'count':len(r),'changed':changed(r)} for n,r in [('baseline',baseline),('T06',t06),('delivery',delivery)]]
record={'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'checks':checks,'reviewedFiles':delivery,'baseline':baseline,'t06':t06}
(HERE/'input-snapshot.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(checks,ensure_ascii=False))

from pathlib import Path
import hashlib,json,os,subprocess,difflib
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
os.environ['PATH']=str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd')+os.pathsep+os.environ['PATH']
def read(p):return json.loads((ROOT/p).read_text(encoding='utf-8'))
def changed(rows):return [r['path'] for r in rows if not (ROOT/r['path']).is_file() or hashlib.sha256((ROOT/r['path']).read_bytes()).hexdigest()!=r['sha256']]
prior=read('docs/execution/reviews/T07-round1/input-snapshot.json')
revision=read('tests/engineering/T07/evidence/revision-v1-checks.json')
baseline=read('tests/engineering/T07/evidence/revision-v1-input.json')['files']
allowed={'backend/src/main/java/com/example/editorial/article/version/VersionService.java','tests/engineering/T07/extend_t06.py','tests/engineering/T07/t06-extension.patch','tests/engineering/T07/integration.py'}
altered=changed(baseline)
assert set(altered)==allowed,altered
assert not changed(prior['baseline'])
assert not changed(prior['t06'])
assert not changed(revision['files'])
paths=sorted({r['path'] for r in prior['reviewedFiles']+revision['files']})
rows=[{'path':p,'sha256':hashlib.sha256((ROOT/p).read_bytes()).hexdigest()} for p in paths]
record={'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'changedSinceRound1':changed(prior['reviewedFiles']),'allowedBaselineChanges':altered,'baseline':baseline,'t06':prior['t06'],'revisionFiles':revision['files'],'reviewedFiles':rows}
out=HERE/'input-snapshot.json';assert not out.exists();out.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
run=read('docs/execution/reviews/T07-round1/evidence/author-tests.json')
path='backend/src/main/java/com/example/editorial/article/version/VersionService.java'
before=(ROOT/run['isolatedWork']/path).read_text(encoding='utf-8');after=(ROOT/path).read_text(encoding='utf-8')
(HERE/'VersionService.diff').write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='round1/'+path,tofile='round2/'+path)),encoding='utf-8')
print(json.dumps({'baselineCount':len(baseline),'reviewedCount':len(rows),'revisionCount':len(revision['files']),'changed':altered},ensure_ascii=False))

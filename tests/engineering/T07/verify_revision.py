"""Verify revision scope, unchanged historical evidence, executed patch and review regressions."""
from pathlib import Path
import argparse,difflib,hashlib,json,subprocess,sys,xml.etree.ElementTree as ET
from extend_t06 import extend,PATH
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--evidence-name',required=True);args=p.parse_args()
for value in vars(args).values():
    if not value.replace('-','').replace('_','').isalnum():p.error('invalid evidence name')
out=HERE/'evidence'/(args.evidence_name+'.json')
if out.exists():raise RuntimeError('Evidence exists; choose a new name')
allowed={'backend/src/main/java/com/example/editorial/article/version/VersionService.java','tests/engineering/T07/extend_t06.py','tests/engineering/T07/t06-extension.patch','tests/engineering/T07/integration.py'}
baseline=json.loads((HERE/'evidence/revision-v1-input.json').read_text(encoding='utf-8'))
changed=[item['path'] for item in baseline['files'] if not (ROOT/item['path']).is_file() or hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest()!=item['sha256']]
failures=[]
if set(changed)-allowed:failures.append('unexpected baseline changes')
original=(ROOT/PATH).read_text(encoding='utf-8');extended=extend(original)
patch=''.join(difflib.unified_diff(original.splitlines(True),extended.splitlines(True),fromfile='a/'+PATH,tofile='b/'+PATH))
if (HERE/'t06-extension.patch').read_text(encoding='utf-8')!=patch:failures.append('patch differs from executed transformation')
run=json.loads((HERE/'evidence'/(args.run+'.json')).read_text(encoding='utf-8'))
executed=ROOT/run['isolatedWork']/PATH
if executed.read_text(encoding='utf-8')!=extended:failures.append('executed T06 differs from current patch')
review_test='docs/execution/reviews/T07-round1/ReviewVersionBoundaryTest.java'
copied=ROOT/run['isolatedWork']/'backend/src/test/java/com/example/editorial/article/version/ReviewVersionBoundaryTest.java'
if copied.read_bytes()!=(ROOT/review_test).read_bytes():failures.append('original review test modified in execution')
counts={}
for name,expected in [('ReviewVersionBoundaryTest',2),('T07RevisionBoundaryTest',4)]:
    suite=ET.parse(ROOT/run['testResults']/('TEST-com.example.editorial.article.version.'+name+'.xml')).getroot()
    counts[name]={key:int(suite.attrib[key]) for key in ['tests','failures','errors','skipped']}
    if counts[name]!={'tests':expected,'failures':0,'errors':0,'skipped':0}:failures.append('regression suite: '+name)
command=[sys.executable,str(HERE/'verify_delivery.py'),'--run',args.run,'--upgrade','upgrade-final','--evidence-name',args.evidence_name+'-delivery']
r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
if r.returncode!=0:failures.append('delivery verification failed')
files=sorted(allowed|{'backend/src/test/java/com/example/editorial/article/version/T07RevisionBoundaryTest.java','tests/engineering/T07/verify_revision.py','docs/execution/reports/T07-Revision-v1.0.md'})
fingerprints=[{'path':path,'sha256':hashlib.sha256((ROOT/path).read_bytes()).hexdigest()} for path in files]
record={'command':{'argv':command,'exitCode':r.returncode,'output':r.stdout+r.stderr},'baselineCount':len(baseline['files']),'changedAllowedFiles':changed,'unexpectedChanges':sorted(set(changed)-allowed),'regressions':counts,'patchMatchesExecutedSource':executed.read_text(encoding='utf-8')==extended,'originalReviewTestUnchanged':copied.read_bytes()==(ROOT/review_test).read_bytes(),'files':fingerprints,'failures':failures}
out.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(record,ensure_ascii=False))
raise SystemExit(bool(failures))

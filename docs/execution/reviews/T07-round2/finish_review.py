"""Independent scope, exact-patch, original-test and result checks for round 2."""
from pathlib import Path
import difflib,hashlib,json,sys,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tests/engineering/T07'))
from extend_t06 import extend,PATH
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def changed(rows):return [r['path'] for r in rows if not (ROOT/r['path']).is_file() or hashlib.sha256((ROOT/r['path']).read_bytes()).hexdigest()!=r['sha256']]
snapshot=read(HERE/'input-snapshot.json');run=read(HERE/'evidence/current.json');checks=read(HERE/'evidence/checks.json')
baselineChanges=changed(snapshot['baseline']);unexpected=sorted(set(baselineChanges)-set(snapshot['allowedBaselineChanges']))
assert not unexpected,unexpected
assert not changed(snapshot['reviewedFiles'])
assert not changed(snapshot['t06'])
work=ROOT/run['isolatedWork']
original=(ROOT/PATH).read_text(encoding='utf-8');extended=extend(original)
patch=''.join(difflib.unified_diff(original.splitlines(True),extended.splitlines(True),fromfile='a/'+PATH,tofile='b/'+PATH))
assert (ROOT/'tests/engineering/T07/t06-extension.patch').read_text(encoding='utf-8')==patch
assert (work/PATH).read_text(encoding='utf-8')==extended
test='backend/src/test/java/com/example/editorial/article/version/ReviewVersionBoundaryTest.java'
assert (work/test).read_bytes()==(ROOT/'docs/execution/reviews/T07-round1/ReviewVersionBoundaryTest.java').read_bytes()
totals={k:0 for k in ['tests','failures','errors','skipped']};suites=[]
for file in sorted((ROOT/run['testResults']).glob('TEST-*.xml')):
    suite=ET.parse(file).getroot();counts={k:int(suite.attrib[k]) for k in totals}
    suites.append({'name':suite.attrib['name'],**counts})
    for k in totals:totals[k]+=counts[k]
assert totals=={'tests':73,'failures':0,'errors':0,'skipped':0},totals
for name,n in [('ReviewVersionBoundaryTest',2),('T07RevisionBoundaryTest',4)]:
    row=next(s for s in suites if s['name'].endswith('.'+name));assert row['tests']==n
assert run['exitCode']==0 and all(c['exitCode']==c['expected'] for c in run['commands'])
last=run['commands'][-1];assert last['argv'][-1]=='stop' and last['exitCode']==0
assert not checks['failures']
record={'conclusion':'PASS_FOR_REVIEWED_REMEDIATION','closedFindings':['T07-R01','T07-R02'],'openCodeFindings':[],'openContractGap':'CR-T07-01','fullT07AcceptanceApproved':False,'totals':totals,'suites':suites,'baselineCount':len(snapshot['baseline']),'allowedBaselineChanges':baselineChanges,'unexpectedBaselineChanges':unexpected,'changedReviewedFiles':changed(snapshot['reviewedFiles']),'changedT06Files':changed(snapshot['t06']),'originalReviewTestByteIdentical':True,'patchMatchesGeneratorAndExecutedSource':True,'databaseStopped':True,'checks':str((HERE/'evidence/checks.json').relative_to(ROOT)),'upgradeEvidenceReused':'docs/execution/reviews/T07-round1/evidence/upgrade.json','upgradeExecutedThisRound':False}
(HERE/'summary.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in record.items() if k!='suites'},ensure_ascii=False))

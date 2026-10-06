from pathlib import Path
import hashlib,json,shutil,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[4]; HERE=Path(__file__).resolve().parent
snapshot=json.loads((HERE/'input-snapshot.json').read_text(encoding='utf-8'))
changed=[]
for item in snapshot['priorReviewFiles']+snapshot['reviewedFiles']:
    p=ROOT/item['path']
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']: changed.append(item['path'])
suites=[]
for name in ['current-host','upgrade-host']:
    evidence=json.loads((HERE/'evidence'/(name+'.json')).read_text(encoding='utf-8'))
    assert evidence['exitCode']==0
    assert evidence['commands'][-1]['argv'][-1]=='stop' and evidence['commands'][-1]['exitCode']==0
    for p in (HERE/'evidence'/(name+'-test-results')).glob('TEST-*.xml'):
        root=ET.parse(p).getroot()
        suites.append({k:root.attrib[k] for k in ['name','tests','failures','errors','skipped']})
    if name=='current-host':
        work=ROOT/evidence['isolatedWork']
        shutil.copyfile(work/'backend/src/test/java/com/example/editorial/article/job/T06PostgresTest.java',HERE/'ExecutedT06PostgresTest.java')
root=ET.parse(HERE/'evidence/TEST-com.example.editorial.article.ast.ReviewNestedClosureTest.xml').getroot()
suites.append({k:root.attrib[k] for k in ['name','tests','failures','errors','skipped']})
out={'status':'CHANGES_REQUIRED','open':['T06-R01'],'closed':['T06-R02'],'changedInputOrPriorReviewFiles':sorted(set(changed)),'suites':suites,'newT06SecretFindings':0,'preexistingT02SecretFindings':6,'databaseInstancesStopped':True}
(HERE/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False))
assert not changed

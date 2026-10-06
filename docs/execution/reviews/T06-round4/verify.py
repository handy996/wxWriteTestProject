"""Read-only checks of delivery; write review-owned evidence only."""
from pathlib import Path
import collections,hashlib,importlib.metadata,json,os,shutil,subprocess,sys,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[4]; HERE=Path(__file__).resolve().parent
os.environ['PATH']=str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd')+os.pathsep+os.environ['PATH']
if '--scan' in sys.argv:
    sys.argv=[sys.argv[0],'--gitleaks',str(ROOT/'.tools/t02/gitleaks/gitleaks.exe')]
    path=ROOT/'tests/engineering/T02/scan_secrets.py'
    source=path.read_text(encoding='utf-8').replace('tests/engineering/T02/evidence/gitleaks-findings.json','docs/execution/reviews/T06-round4/gitleaks-findings.json').replace("ROOT / 'tests/engineering/T02/.work'","ROOT / 'docs/execution/reviews/T06-round4/.work'")
    exec(compile(source,str(path),'exec'),{'__name__':'__main__','__file__':str(path)})
else:
    records=[]
    for command in [[sys.executable,'tests/engineering/T02/check_contracts.py'],['git','apply','--check','tests/engineering/T06/shared-integration.patch'],['git','diff','--check'],[sys.executable,__file__,'--scan']]:
        p=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
        records.append({'argv':command,'exitCode':p.returncode,'output':p.stdout+p.stderr})
    (HERE/'checks.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    snapshot=json.loads((HERE/'input-snapshot.json').read_text(encoding='utf-8'))
    changed=[]
    for x in snapshot['priorReviewFiles']+snapshot['reviewedFiles']:
        p=ROOT/x['path']
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=x['sha256']: changed.append(x['path'])
    sys.path.insert(0,str(ROOT/'tests/engineering/T06/.work/schema-tools'))
    import jsonschema
    schema=json.loads((ROOT/'docs/schemas/editorial.schema.json').read_text(encoding='utf-8'))
    schema_results=[]
    for name,file in [('ArticleArtifact','article-artifact-sample.json'),('ArticleVersion','article-version-sample.json')]:
        sample=json.loads((HERE/'evidence'/file).read_text(encoding='utf-8'))
        errors=list(jsonschema.Draft202012Validator({'$ref':'#/$defs/'+name,'$defs':schema['$defs']},format_checker=jsonschema.FormatChecker()).iter_errors(sample))
        schema_results.append({'definition':name,'errors':[e.message for e in errors]})
    (HERE/'schema-check.json').write_text(json.dumps({'version':importlib.metadata.version('jsonschema'),'results':schema_results},ensure_ascii=False,indent=2),encoding='utf-8')
    suites=[]
    for p in (HERE/'evidence/current-host-test-results').glob('TEST-*.xml'):
        root=ET.parse(p).getroot()
        suites.append({k:root.attrib[k] for k in ['name','tests','failures','errors','skipped']})
    run=json.loads((HERE/'evidence/current-host.json').read_text(encoding='utf-8'))
    assert run['exitCode']==0 and run['commands'][-1]['argv'][-1]=='stop' and run['commands'][-1]['exitCode']==0
    work=ROOT/run['isolatedWork']
    shutil.copyfile(work/'backend/src/test/java/com/example/editorial/article/job/T06PostgresTest.java',HERE/'ExecutedT06PostgresTest.java')
    findings=json.loads((HERE/'gitleaks-findings.json').read_text(encoding='utf-8'))
    counts=dict(collections.Counter(x['File'].replace('\\','/').split('secret-scan-')[-1].split('/',1)[-1] for x in findings))
    assert counts=={'tests/engineering/T02/evidence/r01-integrity.json':6},counts
    assert not changed and all(not x['errors'] for x in schema_results)
    assert all(r['exitCode']==0 for r in records[:3]) and records[3]['exitCode']==1
    assert sum(int(x['tests']) for x in suites)==48 and all(x['failures']==x['errors']==x['skipped']=='0' for x in suites)
    out={'status':'PASS','scope':'T06 reviewed working-tree delivery; not integrated CI or production approval','open':[],'closed':['T06-R01','T06-R02'],'changedInputOrPriorReviewFiles':changed,'suites':suites,'secretScanExitCode':1,'findingsByFile':counts,'databaseStopped':True}
    (HERE/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False))

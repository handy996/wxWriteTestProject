"""Read-only delivery/contract/schema verification. Every subprocess status is inspected."""
import argparse,hashlib,importlib.metadata,json,os,shutil,subprocess,sys,tempfile,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--upgrade',required=True);p.add_argument('--evidence-name',required=True);args=p.parse_args()
for value in vars(args).values():
    if not value.replace('-','').replace('_','').isalnum():p.error('invalid evidence name')
out=HERE/'evidence'/(args.evidence_name+'.json')
if out.exists():raise RuntimeError('Evidence exists; use a new name')
os.environ['PATH']=str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd')+os.pathsep+os.environ['PATH']
results=[];failures=[]
def run(argv,allowed=(0,)):
    r=subprocess.run(list(map(str,argv)),cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
    results.append({'argv':list(map(str,argv)),'exitCode':r.returncode,'output':r.stdout+r.stderr})
    if r.returncode not in allowed:failures.append('command: '+str(argv))
    return r
run([sys.executable,'--version']);run(['git','apply','--check',HERE/'t06-extension.patch']);run(['git','apply','--check',HERE/'composition-root.patch']);run(['git','apply','--check',ROOT/'tests/engineering/T06/shared-integration.patch'])
run([sys.executable,ROOT/'tests/engineering/T02/check_contracts.py']);run(['git','diff','--check'])
baseline=json.loads((HERE/'evidence/input-baseline.json').read_text(encoding='utf-8'))
def changed(rows):return [n['path'] for n in rows if not (ROOT/n['path']).is_file() or hashlib.sha256((ROOT/n['path']).read_bytes()).hexdigest()!=n['sha256']]
input_changes=changed(baseline['files']);review=json.loads((ROOT/'docs/execution/reviews/T06-round4/input-snapshot.json').read_text(encoding='utf-8'));t06_changes=changed(review['reviewedFiles'])
if input_changes or t06_changes:failures.append('existing files changed')
test_runs=[]
for name in [args.run,args.upgrade]:
    e=json.loads((HERE/'evidence'/(name+'.json')).read_text(encoding='utf-8'))
    totals={k:0 for k in ['tests','failures','errors','skipped']};suites=[]
    for path in sorted((ROOT/e['testResults']).glob('TEST-*.xml')):
        t=ET.parse(path).getroot();suites.append({'name':t.attrib['name'],**{k:int(t.attrib[k]) for k in totals}})
        for k in totals:totals[k]+=int(t.attrib[k])
    test_runs.append({'name':name,'exitCode':e['exitCode'],'totals':totals,'suites':suites})
    if e['exitCode']!=0 or any(c['exitCode']!=c['expected'] for c in e['commands']) or totals['tests']==0 or any(totals[k] for k in ['failures','errors','skipped']):failures.append('test run: '+name)
    if not e['commands'][-1]['argv'][-1]=='stop' or e['commands'][-1]['exitCode']!=0:failures.append('database cleanup: '+name)
sys.path.insert(0,str(ROOT/'tests/engineering/T06/.work/schema-tools'))
import jsonschema
schema=json.loads((ROOT/'docs/schemas/editorial.schema.json').read_text(encoding='utf-8'))
schemas=[]
for filename,definition in {'ArticleVersion':'ArticleVersion','RestoreVersion':'ArticleVersion','LateVersion':'ArticleVersion','ArticleVersionPage':'ArticleVersionPage','Diff':'Diff','ProposalPage':'ProposalPage','DispositionResult':'DispositionResult','StepContext':'StepContext','WriterOutput':'WriterOutput','article-artifact-sample':'ArticleArtifact','article-version-sample':'ArticleVersion'}.items():
    sample=HERE/'evidence'/(args.run+'-samples')/(filename+'.json')
    try:
        n=json.loads(sample.read_text(encoding='utf-8'));errors=[e.message for e in jsonschema.Draft202012Validator({'$ref':'#/$defs/'+definition,'$defs':schema['$defs']},format_checker=jsonschema.FormatChecker()).iter_errors(n)]
    except Exception as e:errors=[str(e)]
    schemas.append({'path':str(sample.relative_to(ROOT)),'definition':definition,'errors':errors})
    if errors:failures.append('schema: '+filename)
paths=sorted(set(x.decode() for x in subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).split(b'\0') if x))
scanner=ROOT/'.tools/t02/gitleaks/gitleaks.exe';run([scanner,'version']);report=HERE/'evidence'/(args.evidence_name+'-gitleaks.json')
with tempfile.TemporaryDirectory(prefix='source-scan-',dir=HERE/'.work') as td:
    dest=Path(td)
    for path in paths:
        if (ROOT/path).is_file():target=dest/path;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/path,target)
    scan=run([scanner,'dir',dest,'--redact','--no-banner','--config',ROOT/'tests/engineering/T02/gitleaks.toml','--report-format','json','--report-path',report],(0,1))
    findings=json.loads(report.read_text(encoding='utf-8'));finding_paths=[Path(f['File']).relative_to(dest).as_posix() for f in findings]
    unexpected=[x for x in finding_paths if x!='tests/engineering/T02/evidence/r01-integrity.json']
    if unexpected or len(finding_paths)!=6:failures.append('secret scan differs from known T02 six findings')
owned=[path for path in paths if path.startswith(('backend/src/main/java/com/example/editorial/article/version/','backend/src/main/java/com/example/editorial/article/proposal/','backend/src/test/java/com/example/editorial/article/version/','backend/src/test/java/com/example/editorial/article/proposal/','tests/engineering/T07/')) or path=='docs/execution/reports/T07.md']
# Evidence is immutable per run; source fingerprints avoid self-referential output and path->hash strings.
fingerprints=[{'path':path,'sha256':hashlib.sha256((ROOT/path).read_bytes()).hexdigest()} for path in owned if '/evidence/' not in path]
record={'commands':results,'inputCount':len(baseline['files']),'changedInputs':input_changes,'changedT06ReviewedFiles':t06_changes,'tests':test_runs,'schemaValidator':importlib.metadata.version('jsonschema'),'schemas':schemas,'secretScan':{'exitCode':scan.returncode,'findingPaths':finding_paths,'newFindings':unexpected},'files':fingerprints,'failures':failures}
out.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({'tests':test_runs,'changedInputs':input_changes,'schemaErrors':sum(len(x['errors']) for x in schemas),'scanExitCode':scan.returncode,'newFindings':unexpected,'failures':failures},ensure_ascii=False))
raise SystemExit(bool(failures))

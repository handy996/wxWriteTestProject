"""Read-only integrity checks, exact Git-visible secret scan, and actual wire response schema check."""
import argparse, hashlib, importlib.metadata, json, os, subprocess, sys, tempfile, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]; HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--evidence-name',default='delivery-checks')
args=parser.parse_args()
if not args.evidence_name.replace('-','').replace('_','').isalnum(): parser.error('invalid evidence name')
evidence=HERE/'evidence'
scan_report=evidence/(args.evidence_name+'-gitleaks-findings.json')
os.environ['PATH']=str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd')+os.pathsep+os.environ['PATH']
results=[]
def run(argv):
    p=subprocess.run(list(map(str,argv)),cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
    results.append({'argv':list(map(str,argv)),'exitCode':p.returncode,'output':p.stdout+p.stderr});return p
run([sys.executable,'--version'])
run([sys.executable,HERE/'prepare_delivery.py'])
run(['git','apply','--check',HERE/'shared-integration.patch'])
run([sys.executable,ROOT/'tests/engineering/T02/check_contracts.py'])
run(['git','diff','--check'])
baseline=json.loads((HERE/'evidence/input-baseline.json').read_text(encoding='utf-8-sig'))
assert isinstance(baseline['files'],list) and all(set(item)=={'path','sha256'} for item in baseline['files'])
changed=[item['path'] for item in baseline['files'] if not (ROOT/item['path']).is_file() or hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest()!=item['sha256']]
files=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).split(b'\0')
paths=sorted(set(x.decode('utf-8') for x in files if x))
owned=[p for p in paths if p.startswith(('backend/src/main/java/com/example/editorial/article/job/','backend/src/main/java/com/example/editorial/article/ast/','backend/src/test/java/com/example/editorial/article/','tests/engineering/T06/')) or p in {'docs/execution/reports/T06.md','docs/execution/reports/T06-Revision-v1.0.md','docs/execution/reports/T06-Revision-v2.0.md','docs/execution/reports/T06-Revision-v3.0.md'}]
fingerprints={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in owned if '/evidence/' not in p}
scanner=ROOT/'.tools/t02/gitleaks/gitleaks.exe';run([scanner,'version'])
(HERE/'.work').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='source-scan-',dir=HERE/'.work') as td:
    dest=Path(td)
    for p in paths:
        if (ROOT/p).is_file():
            target=dest/p;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/p,target)
    scan_report.unlink(missing_ok=True)
    scan=run([scanner,'dir',dest,'--redact','--no-banner','--config',ROOT/'tests/engineering/T02/gitleaks.toml','--report-format','json','--report-path',scan_report])
    if scan.returncode not in (0,1) or not scan_report.exists(): raise RuntimeError('Gitleaks did not produce a valid result')
    findings=json.loads(scan_report.read_text(encoding='utf-8'))
    finding_paths=[Path(item['File']).relative_to(dest).as_posix() for item in findings]
    t06_findings=[p for p in finding_paths if p.startswith(('tests/engineering/T06/','backend/src/main/java/com/example/editorial/article/','backend/src/test/java/com/example/editorial/article/')) or p in {'docs/execution/reports/T06.md','docs/execution/reports/T06-Revision-v1.0.md','docs/execution/reports/T06-Revision-v2.0.md','docs/execution/reports/T06-Revision-v3.0.md'}]
sys.path.insert(0,str(HERE/'.work/schema-tools'))
import jsonschema
schema=json.loads((ROOT/'docs/schemas/editorial.schema.json').read_text(encoding='utf-8'))
errors=[]
for name,file in [('ArticleArtifact','article-artifact-sample.json'),('ArticleVersion','article-version-sample.json')]:
    sample=json.loads((HERE/'evidence'/file).read_text(encoding='utf-8'))
    errors.extend(jsonschema.Draft202012Validator({'$ref':'#/$defs/'+name,'$defs':schema['$defs']},format_checker=jsonschema.FormatChecker()).iter_errors(sample))
records={'commands':results,'existingFileCount':len(baseline['files']),'changedExistingFiles':changed,'sourceFingerprints':fingerprints,
    'secretScan':{'exitCode':scan.returncode,'findingPaths':finding_paths,'t06FindingCount':len(t06_findings)},
    'schemaValidator':importlib.metadata.version('jsonschema'),'actualResponseSchemaErrors':[e.message for e in errors],
    'gitHead':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()}
(evidence/(args.evidence_name+'.json')).write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'commands':[{'argv':r['argv'],'exitCode':r['exitCode']} for r in results], 'changedExistingFiles':changed,'schemaErrors':len(errors),'t06Findings':len(t06_findings),'allFindings':len(finding_paths)},ensure_ascii=False))
assert not changed and not errors and not t06_findings

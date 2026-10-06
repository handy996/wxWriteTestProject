"""Independent checks for integrated T07 and its additive OpenAPI authentication contract."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tests/engineering/integration/.work/schema-deps'))
sys.path.insert(0,str(ROOT/'tests/engineering/T06/.work/schema-tools'))
import jsonschema,yaml,openapi_spec_validator
os.environ['PATH']=str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd')+os.pathsep+os.environ['PATH']
def read(p):return json.loads(p.read_text(encoding='utf-8'))
results=[];failures=[]
def run(argv):
    r=subprocess.run(list(map(str,argv)),cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
    # Boundary checker emits path/hash strings: retain structured outcomes instead of duplicating fingerprints.
    output=(r.stdout+r.stderr) if r.returncode or 'verify_boundaries.py' not in str(argv) else 'All reviewed integration boundary comparisons passed'
    results.append({'argv':list(map(str,argv)),'exitCode':r.returncode,'output':output})
    if r.returncode:failures.append('command: '+str(argv))
run([sys.executable,ROOT/'tests/engineering/integration/verify_boundaries.py'])
run([sys.executable,ROOT/'tests/engineering/T02/check_contracts.py'])
run(['git','diff','--check'])
source=(ROOT/'tests/engineering/T02/scan_secrets.py').read_text(encoding='utf-8')
source=source.replace("ROOT = Path(__file__).resolve().parents[3]",'ROOT = Path('+repr(str(ROOT))+')')
source=source.replace("ROOT / 'tests/engineering/T02/.work'",'Path('+repr(str(HERE/'.work'))+')')
source=source.replace("ROOT / 'tests/engineering/T02/evidence/gitleaks-findings.json'",'Path('+repr(str(HERE/'evidence/gitleaks-findings.json'))+')')
scan=HERE/'scan_review.py';scan.write_text(source,encoding='utf-8')
run([sys.executable,scan,'--gitleaks',ROOT/'.tools/t02/gitleaks/gitleaks.exe'])
execution=read(HERE/'evidence/final.json');totals={k:0 for k in ['tests','failures','errors','skipped']};suites=[]
for f in sorted((ROOT/execution['testResults']).glob('TEST-*.xml')):
    s=ET.parse(f).getroot();counts={k:int(s.attrib[k]) for k in totals};suites.append({'name':s.attrib['name'],**counts})
    for k in totals:totals[k]+=counts[k]
if totals!={'tests':78,'failures':0,'errors':0,'skipped':0}:failures.append('JUnit totals')
if execution['exitCode'] or any(c['exitCode']!=c['expected'] for c in execution['commands']):failures.append('integration command')
stop=execution['commands'][-1];stopped=stop['argv'][-1]=='stop' and stop['exitCode']==0
if not stopped:failures.append('database stop')
old=read(ROOT/'docs/schemas/editorial.schema.json');schemas=[]
mapping={'ArticleVersion':'ArticleVersion','RestoreVersion':'ArticleVersion','LateVersion':'ArticleVersion','ArticleVersionPage':'ArticleVersionPage','Diff':'Diff','ProposalPage':'ProposalPage','DispositionResult':'DispositionResult','StepContext':'StepContext','WriterOutput':'WriterOutput','article-artifact-sample':'ArticleArtifact','article-version-sample':'ArticleVersion','DiffPage':'DiffPage'}
for name,definition in mapping.items():
    schema=read(ROOT/'docs/schemas/diff-page-v1.1.schema.json') if name=='DiffPage' else {'$ref':'#/$defs/'+definition,'$defs':old['$defs']}
    sample=read(ROOT/execution['samples']/(name+'.json'));jsonschema.Draft202012Validator.check_schema(schema)
    errors=[e.message for e in jsonschema.Draft202012Validator(schema,format_checker=jsonschema.FormatChecker()).iter_errors(sample)]
    schemas.append({'sample':name,'errors':errors})
    if errors:failures.append('schema: '+name)
spec=yaml.safe_load((ROOT/'docs/api/diff-pages-v1.1.openapi.yaml').read_text(encoding='utf-8'))
openapi_spec_validator.validate_spec(spec)
frozen=read(ROOT/'docs/api/openapi.yaml');op=spec['paths']['/api/v1/articles/{id}/diff/pages']['get']
actual=op.get('security',spec.get('security'));expected=frozen['security']
schemes=spec.get('components',{}).get('securitySchemes',{})
securityMatches=actual==expected and schemes.get('session')==frozen['components']['securitySchemes']['session']
contract={'openapiStructureValid':True,'expectedSecurity':expected,'actualSecurity':actual,'expectedSessionScheme':frozen['components']['securitySchemes']['session'],'actualSessionScheme':schemes.get('session'),'securityContractMatchesFrozenAuthentication':securityMatches,'actualAnonymousHttpStatus':401}
if not securityMatches:failures.append('T07-R03: additive OpenAPI does not declare session authentication')
snapshot=read(HERE/'input-snapshot.json')
changed=[r['path'] for r in snapshot['trackedFiles'] if not (ROOT/r['path']).is_file() or hashlib.sha256((ROOT/r['path']).read_bytes()).hexdigest()!=r['sha256']]
if changed:failures.append('tracked inputs changed')
record={'head':snapshot['head'],'commands':results,'totals':totals,'suites':suites,'schemas':schemas,'contract':contract,'trackedInputCount':len(snapshot['trackedFiles']),'changedTrackedInputs':changed,'databaseStopped':stopped,'failures':failures}
out=HERE/'evidence/checks.json';assert not out.exists();out.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in record.items() if k not in ['commands','suites','schemas']},ensure_ascii=False))
raise SystemExit(bool(failures))

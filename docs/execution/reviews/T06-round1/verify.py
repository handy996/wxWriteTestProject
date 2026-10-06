from pathlib import Path
import collections, hashlib, importlib.metadata, json, os, subprocess, sys
ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
os.environ['PATH'] = str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd') + os.pathsep + os.environ['PATH']
if '--scan' in sys.argv:
    sys.argv = [sys.argv[0], '--gitleaks', str(ROOT/'.tools/t02/gitleaks/gitleaks.exe')]
    path = ROOT/'tests/engineering/T02/scan_secrets.py'
    source = path.read_text(encoding='utf-8').replace('tests/engineering/T02/evidence/gitleaks-findings.json','docs/execution/reviews/T06-round1/gitleaks-findings.json').replace("ROOT / 'tests/engineering/T02/.work'", "ROOT / 'docs/execution/reviews/T06-round1/.work'")
    exec(compile(source,str(path),'exec'),{'__name__':'__main__','__file__':str(path)})
else:
    records = []
    env = os.environ.copy()
    env['JAVA_HOME'] = str(ROOT/'.tools/t02/jdk-21.0.12.1+1')
    work = ROOT/json.loads((HERE/'evidence/author-tests-host.json').read_text(encoding='utf-8'))['isolatedWork']
    commands = [[str(ROOT/'.tools/t02/apache-maven-3.9.11/bin/mvn.cmd'),'-o','-B','-ntp','-f',str(work/'backend/pom.xml'),'-Dmaven.repo.local='+str(ROOT/'.tools/t02/m2'),'test','-Dtest=ReviewArticleAstTest'],
        [sys.executable,'tests/engineering/T02/check_contracts.py'],['git','apply','--check','tests/engineering/T06/shared-integration.patch'],['git','diff','--check'],
        [sys.executable,__file__,'--scan']]
    for command in commands:
        result = subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
        records.append({'argv':command,'exitCode':result.returncode,'output':result.stdout+result.stderr})
        print('check',len(records),'exit',result.returncode,flush=True)
    (HERE/'checks.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    import shutil
    for path in (work/'backend/target/surefire-reports').glob('*ReviewArticleAstTest*'):
        shutil.copyfile(path,HERE/'evidence'/path.name)
    baseline = json.loads((ROOT/'tests/engineering/T06/evidence/input-baseline.json').read_text(encoding='utf-8-sig'))['files']
    delivery = json.loads((ROOT/'tests/engineering/T06/evidence/delivery-checks.json').read_text(encoding='utf-8'))['sourceFingerprints']
    comparisons=[]
    for label, files in [('preexisting',baseline),('delivery',delivery)]:
        changed=[p for p,h in files.items() if not (ROOT/p).is_file() or hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
        comparisons.append({'scope':label,'count':len(files),'changed':changed})
    (HERE/'input-comparison.json').write_text(json.dumps(comparisons,ensure_ascii=False,indent=2),encoding='utf-8')
    fingerprints=[{'path':p,'sha256':hashlib.sha256((ROOT/p).read_bytes()).hexdigest()} for p in sorted(delivery)]
    (HERE/'reviewed-files.json').write_text(json.dumps({'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'files':fingerprints},ensure_ascii=False,indent=2),encoding='utf-8')
    sys.path.insert(0,str(ROOT/'tests/engineering/T06/.work/schema-tools'))
    import jsonschema
    schema=json.loads((ROOT/'docs/schemas/editorial.schema.json').read_text(encoding='utf-8'))
    result=[]
    for name,file in [('ArticleArtifact','article-artifact-sample.json'),('ArticleVersion','article-version-sample.json')]:
        sample=json.loads((HERE/'evidence'/file).read_text(encoding='utf-8'))
        errors=list(jsonschema.Draft202012Validator({'$ref':'#/$defs/'+name,'$defs':schema['$defs']},format_checker=jsonschema.FormatChecker()).iter_errors(sample))
        result.append({'definition':name,'errors':[e.message for e in errors]})
    (HERE/'schema-check.json').write_text(json.dumps({'version':importlib.metadata.version('jsonschema'),'results':result},ensure_ascii=False,indent=2),encoding='utf-8')
    findings=json.loads((HERE/'gitleaks-findings.json').read_text(encoding='utf-8'))
    print(json.dumps({'comparisons':comparisons,'schema':result,'gitleaksByFile':dict(collections.Counter(x['File'].replace('\\','/').split('secret-scan-')[-1].split('/',1)[-1] for x in findings))},ensure_ascii=False))

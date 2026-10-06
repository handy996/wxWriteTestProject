"""Independent third-round review. Mutations are confined to this evidence directory."""
import datetime, difflib, hashlib, json, os, shutil, socket, subprocess, sys, uuid
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
JAVA=ROOT/'.tools/t02/jdk-21.0.12.1+1'
MVN=ROOT/'.tools/t02/apache-maven-3.9.11/bin/mvn.cmd'
ENV=dict(os.environ,JAVA_HOME=str(JAVA),PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1')
ENV['PATH']=str(JAVA/'bin')+os.pathsep+ENV.get('PATH','')
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,obj):
    p=HERE/name
    assert not p.exists(),f'Preserve evidence: {p}'
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def run(argv,timeout=180):
    p=subprocess.run(list(map(str,argv)),cwd=ROOT,env=ENV,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    return dict(argv=list(map(str,argv)),exitCode=p.returncode,output=p.stdout+p.stderr)
def snapshot():
    paths=subprocess.check_output(['git','ls-files','-co','--exclude-standard','-z'],cwd=ROOT).decode().split('\0')
    files=[dict(path=p,sha256=digest(ROOT/p)) for p in sorted(set(paths)) if p and not p.startswith('docs/execution/reviews/T04-round3/') and p!='docs/execution/reviews/T04-Review-v3.0.md' and (ROOT/p).is_file()]
    return dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),head=run(['git','rev-parse','HEAD'])['output'].strip(),branch=run(['git','branch','--show-current'])['output'].strip(),status=run(['git','status','--short'])['output'],files=files)
mode=sys.argv[1]
if mode=='snapshot':
    before=snapshot();save('before.json',before)
    old={v['path']:v['sha256'] for v in json.loads((HERE.parent/'T04-round2/before.json').read_text())['files']}
    new={v['path']:v['sha256'] for v in before['files']}
    delivery=json.loads((ROOT/'tests/engineering/T04/revision2/integrity.json').read_text(encoding='utf-8'))['delivery']
    approval=json.loads((HERE.parent/'T00-rc3-approval.json').read_text(encoding='utf-8'))
    expected=approval['files']+[dict(path=approval['manifestPath'],sha256=approval['manifestSha256'])]
    baseline=json.loads((ROOT/'docs/execution/contracts/baseline.json').read_text(encoding='utf-8'))
    expected += [dict(path='docs/'+p,sha256=h) for p,h in baseline['sourceHashes'].items()]
    out=dict(snapshotFiles=len(new),changedExistingSinceRound2=[p for p in sorted(old) if old[p]!=new.get(p)],newFilesSinceRound2=[p for p in sorted(new) if p not in old],authorDeliveryFingerprints=len(delivery),authorDeliveryMismatches=[v['path'] for v in delivery if digest(ROOT/v['path'])!=v['sha256']],approvedFingerprints=len(expected),approvedMismatches=[v['path'] for v in expected if digest(ROOT/v['path'])!=v['sha256']])
    save('input-comparison.json',out)
    print(json.dumps({k:v for k,v in out.items() if k!='newFilesSinceRound2'}))
    assert not out['authorDeliveryMismatches'] and not out['approvedMismatches']
elif mode in ('old','current'):
    work=HERE/'.work'/uuid.uuid4().hex
    build=work/'backend'
    shutil.copytree(ROOT/'backend/src',build/'src')
    shutil.copyfile(ROOT/'backend/pom.xml',build/'pom.xml')
    test=(HERE.parent/'T04-round2/EndpointAuthorityTest.java').read_text(encoding='utf-8')
    # Remove only the diagnostic assertion of known-bad behavior; keep actual wire correctness assertion.
    test='\n'.join(line for line in test.splitlines() if 'withExplicitPort' not in line)+'\n'
    independent=HERE/'EndpointAuthorityTest.java'
    if not independent.exists(): independent.write_text(test,encoding='utf-8')
    assert independent.read_text(encoding='utf-8')==test
    shutil.copyfile(independent,build/'src/test/java/com/example/editorial/storage/EndpointAuthorityTest.java')
    provenance=[]
    if mode=='old':
        oldBuild=Path(json.loads((HERE.parent/'T04-round2/build-location.json').read_text())['path'])
        expected={v['path']:v['sha256'] for v in json.loads((HERE.parent/'T04-round2/before.json').read_text())['files']}
        for name in ['SigV4.java','S3StorageBackend.java']:
            rel='src/main/java/com/example/editorial/storage/'+name
            source=oldBuild/rel
            assert digest(source)==expected['backend/'+rel], 'Old source must match previous audit fingerprint'
            provenance.append(dict(path=str(source),sha256=digest(source)))
            shutil.copyfile(source,build/rel)
    (work/'java-tmp').mkdir()
    command=[MVN,'-o','-B','-ntp','-f',build/'pom.xml','-Dmaven.repo.local='+str(ROOT/'.tools/t02/m2'),'clean','test','-Dtest=S3EndpointAuthorityTest,S3ProtocolRegressionTest,SigV4Test,S3StorageBackendTest,EndpointAuthorityTest','-DargLine=-Djava.io.tmpdir='+(work/'java-tmp').as_posix()]
    result=run(command)
    reports=build/'target/surefire-reports'
    if reports.exists():shutil.copytree(reports,HERE/(mode+'-results'))
    result.update(build=str(build),oldSourceProvenance=provenance,realS3=False)
    save(mode+'-verification.json',result)
    print('\n'.join(l for l in result['output'].splitlines() if 'Tests run:' in l or '[ERROR]' in l or 'BUILD SUCCESS' in l or 'REVIEW endpoint' in l))
    sys.exit(result['exitCode'])
elif mode=='versions':
    values=[run(cmd) for cmd in [[JAVA/'bin/java.exe','-version'],[MVN,'-version'],[sys.executable,ROOT/'tests/engineering/T02/check_contracts.py']]]
    save('versions-contracts.json',values);print(json.dumps(values))
elif mode=='docker':
    docker='C:/Users/eie04/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
    values=[run([docker,'version']),run([docker,'image','ls'])]
    save('docker-inventory.json',values);print(json.dumps(values))
elif mode=='summary':
    import xml.etree.ElementTree as ET
    results={}
    for variant in ('old','current'):
        suites=[ET.parse(p).getroot() for p in (HERE/(variant+'-results')).glob('TEST-*.xml')]
        record=json.loads((HERE/(variant+'-verification.json')).read_text(encoding='utf-8'))
        temp=Path(record['build']).parent/'java-tmp'
        results[variant]=dict(exitCode=record['exitCode'],**{k:sum(int(s.get(k,'0')) for s in suites) for k in ('tests','failures','errors','skipped')},javaTemporaryChildren=[p.name for p in temp.iterdir()])
    with socket.socket() as s:
        s.bind(('127.0.0.1',80));results['reviewHttpPort80Released']=True
    oldBuild=Path(json.loads((HERE.parent/'T04-round2/build-location.json').read_text())['path'])
    diffs={}
    for name in ('SigV4.java','S3StorageBackend.java'):
        rel='src/main/java/com/example/editorial/storage/'+name
        diffs[name]=''.join(difflib.unified_diff((oldBuild/rel).read_text().splitlines(True),(ROOT/'backend'/rel).read_text().splitlines(True),fromfile='round2/'+name,tofile='round3/'+name))
    save('source-diff.json',diffs);save('result-summary.json',results);print(json.dumps(results))
elif mode=='final':
    before=json.loads((HERE/'before.json').read_text(encoding='utf-8'));after=snapshot();save('after.json',after)
    old={v['path']:v['sha256'] for v in before['files']};new={v['path']:v['sha256'] for v in after['files']}
    delta=[p for p in sorted(old.keys()|new.keys()) if old.get(p)!=new.get(p)]
    out=dict(checkedFiles=len(old),changedOrMissingOutsideReview=delta,headUnchanged=before['head']==after['head'],branchUnchanged=before['branch']==after['branch'])
    save('integrity.json',out);print(json.dumps(out));assert not delta and out['headUnchanged'] and out['branchUnchanged']

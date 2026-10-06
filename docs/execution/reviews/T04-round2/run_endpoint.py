"""Targeted confirmation, only copies the review test into this review's existing build."""
import json,os,shutil,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
build=Path(json.loads((HERE/'build-location.json').read_text())['path']).resolve()
assert build.is_relative_to((HERE/'.work').resolve())
shutil.copyfile(HERE/'EndpointAuthorityTest.java',build/'src/test/java/com/example/editorial/storage/EndpointAuthorityTest.java')
java=ROOT/'.tools/t02/jdk-21.0.12.1+1'
env=dict(os.environ,JAVA_HOME=str(java),PATH=str(java/'bin')+os.pathsep+os.environ.get('PATH',''))
argv=[str(ROOT/'.tools/t02/apache-maven-3.9.11/bin/mvn.cmd'),'-o','-B','-ntp','-f',str(build/'pom.xml'),
      '-Dmaven.repo.local='+str(ROOT/'.tools/t02/m2'),'test','-Dtest=EndpointAuthorityTest','-DargLine=-Djava.io.tmpdir='+str(build.parent)]
r=subprocess.run(argv,cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
(HERE/'endpoint-confirmation.json').write_text(json.dumps(dict(argv=argv,exitCode=r.returncode,output=r.stdout+r.stderr),indent=2)+'\n',encoding='utf-8')
for p in (build/'target/surefire-reports').glob('*EndpointAuthorityTest*'):
    dest=HERE/'endpoint-results';dest.mkdir(exist_ok=True);shutil.copyfile(p,dest/p.name)
print(r.stdout+r.stderr)
raise SystemExit(r.returncode)

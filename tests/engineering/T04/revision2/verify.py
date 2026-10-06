"""Build the affected S3 tests in a fresh copy, retaining per-attempt evidence."""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
parser = argparse.ArgumentParser()
parser.add_argument('--name', required=True)
args = parser.parse_args()
if Path(args.name).name != args.name:
    parser.error('name must be a filename stem')
evidence = HERE / (args.name + '.json')
assert not evidence.exists(), 'Preserve previous attempts; choose another name'
work = ROOT / 'tests/engineering/T04/.work' / ('revision2-' + uuid.uuid4().hex)
build = work / 'backend'
shutil.copytree(ROOT / 'backend/src', build / 'src')
shutil.copyfile(ROOT / 'backend/pom.xml', build / 'pom.xml')
(work / 'java-tmp').mkdir()
java = ROOT / '.tools/t02/jdk-21.0.12.1+1'
env = dict(os.environ, JAVA_HOME=str(java), PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1')
env['PATH'] = str(java / 'bin') + os.pathsep + env.get('PATH', '')
command = [str(ROOT / '.tools/t02/apache-maven-3.9.11/bin/mvn.cmd'), '-o', '-B', '-ntp', '-f', str(build / 'pom.xml'),
           '-Dmaven.repo.local=' + str(ROOT / '.tools/t02/m2'), 'clean', 'test',
           '-Dtest=S3EndpointAuthorityTest,S3ProtocolRegressionTest,SigV4Test,S3StorageBackendTest',
           '-DargLine=-Djava.io.tmpdir=' + (work / 'java-tmp').as_posix()]
with (work / 'maven.log').open('w', encoding='utf-8') as stream:
    result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, timeout=180,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
output = (work / 'maven.log').read_text(encoding='utf-8', errors='replace')
reports = build / 'target/surefire-reports'
if reports.exists():
    shutil.copytree(reports, HERE / (args.name + '-results'))
evidence.write_text(json.dumps(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    argv=command, exitCode=result.returncode, output=output, build=str(build), realS3=False), indent=2) + '\n', encoding='utf-8')
print('\n'.join(line for line in output.splitlines() if 'Tests run:' in line or '[ERROR]' in line or 'BUILD SUCCESS' in line))
raise SystemExit(result.returncode)

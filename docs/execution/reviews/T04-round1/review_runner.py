"""Independent T04 review: snapshot inputs; copy build; isolated real PG; no source edits."""
import datetime, hashlib, json, os, secrets, shutil, socket, subprocess, sys, uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
JAVA = ROOT / '.tools/t02/jdk-21.0.12.1+1'
MVN = ROOT / '.tools/t02/apache-maven-3.9.11/bin/mvn.cmd'
PG = ROOT / '.tools/t02/postgresql-full/pgsql/bin'
env = os.environ.copy()
env['PYTHONDONTWRITEBYTECODE'] = '1'
env['PYTHONUTF8'] = '1'
env['JAVA_HOME'] = str(JAVA)
env['PATH'] = str(JAVA / 'bin') + os.pathsep + env.get('PATH', '')
commands = []
redactions = []

def run(argv, timeout=240):
    log = HERE / '.work' / ('command-' + uuid.uuid4().hex + '.log')
    with log.open('w', encoding='utf-8') as stream:
        result = subprocess.run(list(map(str, argv)), cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, timeout=timeout,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    output = log.read_text(encoding='utf-8',errors='replace')
    for value in redactions:
        output = output.replace(value, '[REDACTED]')
    commands.append(dict(argv=list(map(str, argv)), exitCode=result.returncode, output=output))
    print(json.dumps(dict(command=str(argv[0]), exitCode=result.returncode)), flush=True)
    return result

def save(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def snapshot():
    paths = subprocess.check_output(['git', 'ls-files', '-co', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')
    files = []
    for rel in sorted(set(paths)):
        if not rel or rel.startswith('docs/execution/reviews/T04-'):
            continue
        p = ROOT / rel
        if p.is_file():
            files.append(dict(path=rel, sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    return dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
                status=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True), files=files)

def main():
    mode = sys.argv[1] if len(sys.argv)>1 else 'snapshot'
    if mode == 'snapshot':
        assert not (HERE/'before.json').exists(), 'Never overwrite initial evidence'
        save('before.json', snapshot()); return
    if mode == 'final':
        before=json.loads((HERE/'before.json').read_text(encoding='utf-8'))
        after=snapshot(); save('after.json',after)
        old={v['path']:v['sha256'] for v in before['files']}
        new={v['path']:v['sha256'] for v in after['files']}
        delta=[p for p in sorted(old.keys()|new.keys()) if old.get(p)!=new.get(p)]
        save('integrity.json',dict(changedOrMissingOutsideReview=delta, headUnchanged=before['head']==after['head']))
        print(json.dumps(delta)); return
    work = HERE / '.work' / uuid.uuid4().hex
    work.mkdir(parents=True)
    build = work / 'backend'
    shutil.copytree(ROOT/'backend/src', build/'src')
    shutil.copyfile(ROOT/'backend/pom.xml',build/'pom.xml')
    testdir=build/'src/test/java/com/example/editorial/storage'
    for p in HERE.glob('*Test.java'):
        shutil.copyfile(p,testdir/p.name)
    for key in list(env):
        if key.startswith(('SPRING_', 'EDITORIAL_', 'DB_', 'T04_')):
            del env[key]
    env['TEMP']=str(work); env['TMP']=str(work)
    admin, runtime, migration = [secrets.token_hex(24) for _ in range(3)]
    redactions.extend([admin,runtime,migration])
    with socket.socket() as s:
        s.bind(('127.0.0.1',0)); port=s.getsockname()[1]
    env.update(PGHOST='127.0.0.1',PGPORT=str(port),PGUSER='editorial_admin',PGPASSWORD=admin,PGDATABASE='editorial',
               DB_RUNTIME_PASSWORD=runtime,DB_MIGRATION_PASSWORD=migration,
               DB_URL=f'jdbc:postgresql://127.0.0.1:{port}/editorial?connectTimeout=2',
               T04_ADMIN_PASSWORD=admin,T04_REAL_PG='true')
    started=False
    try:
        run([JAVA/'bin/java.exe','-version'])
        run([MVN,'-version'])
        run([PG/'postgres.exe','--version'])
        assert run([sys.executable,ROOT/'tests/engineering/T02/check_contracts.py']).returncode==0
        pwfile=work/'init-password';pwfile.write_text(admin,encoding='utf-8')
        assert run([PG/'initdb.exe','-D',work/'data','-U','editorial_admin','--auth=scram-sha-256','--pwfile='+str(pwfile),'--encoding=UTF8','--locale=C']).returncode==0
        pwfile.unlink()
        started=True
        assert run([PG/'pg_ctl.exe','-D',work/'data','-l',work/'postgres.log','-o',f'-h 127.0.0.1 -p {port}','-w','start']).returncode==0
        assert run([PG/'createdb.exe','editorial']).returncode==0
        assert run([PG/'psql.exe','-X','-v','ON_ERROR_STOP=1','-f',ROOT/'backend/docker/bootstrap.sql']).returncode==0
        result=run([MVN,'-o','-B','-ntp','-f',build/'pom.xml','-Dmaven.repo.local='+str(ROOT/'.tools/t02/m2'),
                    'clean','test','-Dtest=com.example.editorial.storage.*Test','-DargLine=-Djava.io.tmpdir='+str(work)])
        reports=build/'target/surefire-reports'
        if reports.exists():
            shutil.copytree(reports,HERE/'test-results',dirs_exist_ok=True)
        save('build-location.json',dict(path=str(build),exitCode=result.returncode))
        assert result.returncode == 0, 'Build/test failure; inspect verification.json'
    finally:
        if started:
            run([PG/'pg_ctl.exe','-D',work/'data','-m','fast','-w','stop'])
            run([PG/'pg_ctl.exe','-D',work/'data','status'])
        save('verification.json',dict(commands=commands, paidCalls=0))

if __name__=='__main__':
    main()

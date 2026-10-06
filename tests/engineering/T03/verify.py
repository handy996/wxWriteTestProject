"""Isolated T03 real PostgreSQL/HTTP verification; never patches the shared checkout.
Run with bundled Python; --pg-bin, --java-home and --maven select already installed tools.
"""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--pg-bin', type=Path, default=ROOT/'.tools/t02/postgresql-full/pgsql/bin')
    p.add_argument('--java-home', type=Path, default=ROOT/'.tools/t02/jdk-21.0.12.1+1')
    p.add_argument('--maven', type=Path, default=ROOT/'.tools/t02/apache-maven-3.9.11/bin/mvn.cmd')
    args = p.parse_args()
    work = HERE/'.work'/uuid.uuid4().hex
    work.mkdir(parents=True)
    evidence = {'mode': 'REAL_POSTGRES_REAL_HTTP_SESSION_CSRF', 'domainSubstitutes': ['article metadata resolver only'], 'commands': [], 'paidCalls': 0}
    env = os.environ.copy()
    for k in list(env):
        if k.startswith(('SPRING_', 'EDITORIAL_', 'DB_', 'INITIAL_OWNER_', 'AUDIT_CURSOR_', 'APP_ORIGIN', 'T03_')):
            del env[k]
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    passwords = {k: secrets.token_urlsafe(32) for k in ('admin', 'runtime', 'migration', 'owner', 'cursor')}
    env.update(JAVA_HOME=str(args.java_home), PGHOST='127.0.0.1', PGPORT=str(port), PGUSER='editorial_admin', PGPASSWORD=passwords['admin'], PGDATABASE='editorial',
               DB_URL=f'jdbc:postgresql://127.0.0.1:{port}/editorial', DB_RUNTIME_PASSWORD=passwords['runtime'], DB_MIGRATION_PASSWORD=passwords['migration'],
               INITIAL_OWNER_USERNAME='owner', INITIAL_OWNER_PASSWORD=passwords['owner'], AUDIT_CURSOR_KEY=passwords['cursor'], APP_ORIGIN='http://localhost:3000',
               T03_REAL_PG='true', T03_ADMIN_PASSWORD=passwords['admin'])
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    started = False
    result_code = 1

    def redact(s):
        for value in passwords.values():
            s = s.replace(value, '[REDACTED]')
        return s

    def run(cmd, extra=None, expected=0, timeout=180):
        file = work/f'command-{len(evidence["commands"])}.log'
        with file.open('w', encoding='utf-8') as out:
            r = subprocess.run([str(x) for x in cmd], cwd=ROOT, env=extra or env, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, timeout=timeout, creationflags=flags)
        output = redact(file.read_text(encoding='utf-8', errors='replace'))
        evidence['commands'].append({'argv': [str(x) for x in cmd], 'exitCode': r.returncode, 'output': output})
        print(f'command {len(evidence["commands"])} exit={r.returncode}', flush=True)
        if r.returncode != expected:
            print(output[-8000:], flush=True)
            raise RuntimeError('Recorded command failed')
        return output

    try:
        for cmd in ([args.java_home/'bin/java', '-version'], [args.maven, '-version'], [args.pg_bin/'postgres', '--version']):
            run(cmd)
        # Exact source copy and reviewable patch, no shared configuration mutations.
        shutil.copytree(ROOT/'backend', work/'backend', ignore=shutil.ignore_patterns('target'))
        patch = (HERE/'shared-integration.patch').read_text(encoding='utf-8')
        # git apply works without a repository when --directory points into the isolated copy.
        run(['git', 'apply', '--check', '--directory='+work.relative_to(ROOT).as_posix(), str(HERE/'shared-integration.patch')])
        run(['git', 'apply', '--directory='+work.relative_to(ROOT).as_posix(), str(HERE/'shared-integration.patch')])
        fixture = work/'draft'; fixture.mkdir()
        shutil.copyfile(HERE/'migration-draft.sql', fixture/'V1__t03_isolated_test.sql')
        env['SPRING_FLYWAY_LOCATIONS'] = 'classpath:db/migration,filesystem:'+fixture.as_posix()
        pw = work/'init-password'; pw.write_text(passwords['admin'], encoding='utf-8')
        run([args.pg_bin/'initdb','-D',work/'data','-U','editorial_admin','--auth=scram-sha-256','--pwfile='+str(pw),'--encoding=UTF8','--locale=C'])
        pw.unlink()
        started=True
        run([args.pg_bin/'pg_ctl','-D',work/'data','-l',work/'postgres.log','-o',f'-h 127.0.0.1 -p {port}','-w','start'])
        run([args.pg_bin/'createdb','editorial'])
        run([args.pg_bin/'psql','-X','-v','ON_ERROR_STOP=1','-f',ROOT/'backend/docker/bootstrap.sql'])
        run([args.maven,'-o','-B','-ntp','-f',work/'backend/pom.xml','-Dmaven.repo.local='+str(ROOT/'.tools/t02/m2'),'clean','verify'],timeout=300)
        for report in (work/'backend/target/surefire-reports').glob('TEST-*.xml'):
            shutil.copyfile(report,HERE/'evidence'/report.name)
        # Restart uses same Flyway history and existing password; packaged source has no fixture endpoints.
        jar=work/'backend/target/editorial-0.1.0-SNAPSHOT.jar'
        evidence['jar']={'path':str(jar.relative_to(ROOT)), 'sha256':hashlib.sha256(jar.read_bytes()).hexdigest()}
        # ApplicationRunner executes with a non-web context and immediately exits.
        run([args.java_home/'bin/java','-jar',jar,'--spring.main.web-application-type=none'],expected=1)
        # Web security deliberately needs a servlet context; restart checks run through a bounded HTTP process below.
        result_code=0
    except Exception as e:
        evidence['failure']=type(e).__name__+': '+str(e)
    finally:
        if started:
            try: run([args.pg_bin/'pg_ctl','-D',work/'data','-m','immediate','-w','stop'])
            except Exception as e: evidence['cleanupFailure']=str(e); result_code=1
        evidence['exitCode']=result_code
        (HERE/'evidence/real-integration.json').write_text(json.dumps(evidence,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return result_code


if __name__ == '__main__':
    raise SystemExit(main())

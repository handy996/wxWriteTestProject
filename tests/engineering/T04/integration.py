"""Real PostgreSQL transaction-boundary test for T04 object store.

Starts an isolated PostgreSQL cluster, applies the T02 bootstrap (roles/schema),
then runs T04PostgresTest (which creates its own minimal app_user/audit_log tables
and wires a real DataSourceTransactionManager + JdbcAuditSink + LocalStorageBackend).
No domain modules, no external Providers, no paid calls.

Example:
    python tests/engineering/T04/integration.py \
        --pg-bin .tools/t02/postgresql-full/pgsql/bin \
        --mvn .tools/t02/apache-maven-3.9.11/bin/mvn.cmd \
        --java-home .tools/t02/jdk-21.0.12.1+1 \
        --m2 .tools/t02/m2
"""
import argparse
import datetime
import json
import os
import secrets
import socket
import subprocess
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pg-bin', required=True, type=Path)
    parser.add_argument('--mvn', required=True, type=Path)
    parser.add_argument('--java-home', required=True, type=Path)
    parser.add_argument('--m2', required=True, type=Path)
    parser.add_argument('--evidence-name', default='integration')
    parser.add_argument('--tests', default='T04PostgresTest,T04RevisionPostgresTest')
    args = parser.parse_args()
    if Path(args.evidence_name).name != args.evidence_name:
        parser.error('--evidence-name must be a filename stem')

    work = ROOT / 'tests/engineering/T04/.work' / uuid.uuid4().hex
    work.mkdir(parents=True)
    (work / 'java-tmp').mkdir()
    env = os.environ.copy()
    for key in list(env):
        if key.startswith(('SPRING_', 'EDITORIAL_', 'DB_', 'T04_')):
            del env[key]
    passwords = {name: secrets.token_hex(24) for name in ('admin', 'runtime', 'migration')}
    db_port = free_port()
    env.update(PGHOST='127.0.0.1', PGPORT=str(db_port), PGUSER='editorial_admin',
               PGPASSWORD=passwords['admin'], PGDATABASE='editorial',
               DB_RUNTIME_PASSWORD=passwords['runtime'], DB_MIGRATION_PASSWORD=passwords['migration'],
               DB_URL=f'jdbc:postgresql://127.0.0.1:{db_port}/editorial?connectTimeout=2',
               T04_ADMIN_PASSWORD=passwords['admin'], T04_REAL_PG='true',
               JAVA_HOME=str(args.java_home))
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    evidence = {'mode': 'REAL_POSTGRES_OBJECT_STORE', 'paidCalls': 0, 'commands': []}
    pg_started = False
    success = False

    def redact(value):
        for password in passwords.values():
            value = value.replace(password, '[REDACTED]')
        return value

    def run(command, expected=0, use_env=None):
        output_path = work / ('command-' + str(len(evidence['commands'])) + '.log')
        with output_path.open('w', encoding='utf-8') as stream:
            result = subprocess.run([str(v) for v in command], cwd=ROOT, env=use_env or env,
                                    stdout=stream, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, timeout=180, creationflags=flags)
        output = output_path.read_text(encoding='utf-8', errors='replace')
        evidence['commands'].append({'argv': [str(v) for v in command], 'exitCode': result.returncode,
                                     'expected': expected, 'output': redact(output)})
        if result.returncode != expected:
            raise AssertionError(f'Unexpected exit {result.returncode}: {command}\n{redact(output)}')
        return output.strip()

    try:
        pwfile = work / 'init-password'
        pwfile.write_text(passwords['admin'], encoding='utf-8')
        run([args.pg_bin / 'initdb', '-D', work / 'data', '-U', 'editorial_admin',
             '--auth=scram-sha-256', '--pwfile=' + str(pwfile), '--encoding=UTF8', '--locale=C'])
        pwfile.unlink()
        pg_started = True
        run([args.pg_bin / 'pg_ctl', '-D', work / 'data', '-l', work / 'postgres.log',
             '-o', f'-h 127.0.0.1 -p {db_port}', '-w', 'start'])
        run([args.pg_bin / 'createdb', 'editorial'])
        run([args.pg_bin / 'psql', '-X', '-v', 'ON_ERROR_STOP=1', '-f', ROOT / 'backend/docker/bootstrap.sql'])

        java = Path(args.java_home) / 'bin' / ('java.exe' if os.name == 'nt' else 'java')
        env['PATH'] = str(Path(args.java_home) / 'bin') + os.pathsep + env.get('PATH', '')
        run([args.mvn, '-o', '-B', '-ntp', '-f', 'backend/pom.xml',
             '-Dmaven.repo.local=' + str(args.m2), 'test', '-Dtest=' + args.tests, '-DargLine=-Djava.io.tmpdir=' + str(work / 'java-tmp')],
            expected=0)
        success = True
    finally:
        if pg_started and (work / 'data/postmaster.pid').exists():
            run([args.pg_bin / 'pg_ctl', '-D', work / 'data', '-m', 'fast', '-w', 'stop'])
            run([args.pg_bin / 'pg_ctl', '-D', work / 'data', 'status'], expected=3)
        evidence.update(exitCode=0 if success else 1,
                        utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        postgresql=run([args.pg_bin / 'postgres', '--version']))
        output = ROOT / 'tests/engineering/T04/evidence' / (args.evidence_name + '.json')
        output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

"""Real PostgreSQL + packaged JVM smoke; no domain modules or external Providers.

Creates a new isolated cluster in .work and always stops its own processes.
Example: python integration.py --pg-bin /path/to/pgsql/bin --java /path/to/java
"""
import argparse
import contextlib
import datetime
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[3]


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pg-bin', required=True, type=Path)
    parser.add_argument('--java', default='java')
    parser.add_argument('--jar', type=Path, default=ROOT / 'backend/target/editorial-0.1.0-SNAPSHOT.jar')
    parser.add_argument('--app-port', type=int, default=0)
    parser.add_argument('--ui-wait-seconds', type=int, choices=range(61), default=0)
    args = parser.parse_args()
    work = ROOT / 'tests/engineering/T02/.work' / uuid.uuid4().hex
    work.mkdir(parents=True)
    env = os.environ.copy()
    # Do not inherit unrelated service credentials or Spring profile settings.
    for key in list(env):
        if key.startswith(('SPRING_', 'EDITORIAL_', 'DB_')):
            del env[key]
    passwords = {name: secrets.token_hex(24) for name in ('admin', 'runtime', 'migration')}
    db_port, app_port = free_port(), args.app_port or free_port()
    env.update(PGHOST='127.0.0.1', PGPORT=str(db_port), PGUSER='editorial_admin',
               PGPASSWORD=passwords['admin'], PGDATABASE='editorial',
               DB_RUNTIME_PASSWORD=passwords['runtime'], DB_MIGRATION_PASSWORD=passwords['migration'],
               DB_URL=f'jdbc:postgresql://127.0.0.1:{db_port}/editorial?connectTimeout=2')
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    evidence = {'mode': 'REAL_POSTGRES_REAL_JVM_NO_PROVIDER', 'paidCalls': 0, 'commands': [], 'checks': []}
    processes = []
    pg_started = False
    success = False

    def redact(value):
        for password in passwords.values():
            value = value.replace(password, '[REDACTED]')
        return value

    def run(command, expected=0, use_env=None):
        # pg_ctl children inherit handles on Windows; pipes would wait for DB shutdown.
        output_path = work / ('command-' + str(len(evidence['commands'])) + '.log')
        with output_path.open('w', encoding='utf-8') as stream:
            result = subprocess.run([str(v) for v in command], cwd=ROOT, env=use_env or env,
                                    stdout=stream, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, timeout=90, creationflags=flags)
        output = output_path.read_text(encoding='utf-8', errors='replace')
        evidence['commands'].append({'argv': [str(v) for v in command], 'exitCode': result.returncode,
                                     'expected': expected, 'output': redact(output)})
        if (expected == 'nonzero' and result.returncode == 0) or (expected != 'nonzero' and result.returncode != expected):
            raise AssertionError(f'Unexpected exit {result.returncode}: {command}\n{redact(output)}')
        return output.strip()

    def psql(sql, role='admin', expected=0):
        use_env = dict(env, PGUSER='editorial_' + ('migrator' if role == 'migration' else role), PGPASSWORD=passwords[role])
        return run([args.pg_bin / 'psql', '-X', '-v', 'ON_ERROR_STOP=1', '-At', '-c', sql], expected, use_env)

    def check(name, condition=True):
        if not condition:
            raise AssertionError(name)
        evidence['checks'].append(name)
        print('OK: ' + name, flush=True)

    def app_command(profile='mock', extra=()):
        return [args.java, '-jar', str(args.jar), '--spring.profiles.active=' + profile,
                '--server.address=127.0.0.1', '--server.port=' + str(app_port), *extra]

    def start_app(label):
        log_path = work / (label + '.log')
        stream = log_path.open('w', encoding='utf-8')
        process = subprocess.Popen(app_command(), env=env, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, creationflags=flags)
        processes.append((process, stream, log_path))
        evidence['commands'].append({'argv': app_command(), 'process': label, 'exitCode': 'RUNNING_UNTIL_CONTROLLED_STOP'})
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if process.poll() is not None:
                stream.close()
                raise AssertionError(redact(log_path.read_text(encoding='utf-8')))
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{app_port}/actuator/health/readiness', timeout=2) as response:
                    if json.load(response)['status'] == 'UP':
                        return process, stream, log_path
            except (OSError, urllib.error.HTTPError):
                pass
            time.sleep(.25)
        raise TimeoutError('Application did not become ready')

    def stop_app(item):
        process, stream, path = item
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        stream.close()
        evidence['commands'].append({'process': path.stem, 'exitCode': process.returncode,
                                     'termination': 'CONTROLLED_TEST_SHUTDOWN',
                                     'output': redact(path.read_text(encoding='utf-8'))})
        if item in processes:
            processes.remove(item)

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
        check('Bootstrap creates separate runtime/migration roles on an empty real PostgreSQL database')
        check('No domain tables before application startup', psql("SELECT count(*) FROM pg_tables WHERE schemaname='editorial'") == '0')
        first = start_app('first-start')
        check('Empty database: packaged Java 21 application reaches readiness UP')
        with urllib.request.urlopen(f'http://127.0.0.1:{app_port}/actuator/info') as response:
            info = json.load(response)['skeleton']
        check('Mock mode is explicit and all real capabilities remain unavailable',
              info['mode'] == 'mock' and info['paidCallsEnabled'] is False and
              len(info['capabilities']) == 4 and all(c['available'] is False for c in info['capabilities']))
        if args.ui_wait_seconds:
            print(f'Browser inspection window: http://127.0.0.1:{app_port}', flush=True)
            time.sleep(args.ui_wait_seconds)
        for route in ('/api/v1/articles', '/actuator/env', '/actuator/configprops'):
            try:
                urllib.request.urlopen(f'http://127.0.0.1:{app_port}{route}')
                raise AssertionError('Unprotected route: ' + route)
            except urllib.error.HTTPError as error:
                check('Blocked unauthenticated or sensitive route: ' + route, error.code in (401, 403))
        before = psql('SELECT installed_rank,script,checksum,success FROM editorial_migrations.flyway_schema_history ORDER BY installed_rank')
        check('Flyway applied only infrastructure permissions', 'R__t02_schema_permissions.sql' in before)
        stop_app(first)
        second = start_app('second-start')
        after = psql('SELECT installed_rank,script,checksum,success FROM editorial_migrations.flyway_schema_history ORDER BY installed_rank')
        check('Second application startup leaves migration history unchanged', before == after)
        stop_app(second)
        for sql in (
            'CREATE TABLE editorial.t02_forbidden(id int)',
            'CREATE TEMP TABLE t02_forbidden(id int)',
            'CREATE SCHEMA t02_forbidden',
            'SELECT * FROM editorial_migrations.flyway_schema_history',
            'SET ROLE editorial_migrator',
        ):
            psql(sql, role='runtime', expected='nonzero')
        check('Runtime cannot create tables/temp tables/schemas, read history, or assume migrator')
        psql('CREATE TABLE editorial.t02_permission_probe(id int PRIMARY KEY, active boolean, caption text)', role='migration')
        psql("INSERT INTO editorial.t02_permission_probe VALUES(1,true,'test')", role='runtime', expected='nonzero')
        psql('GRANT SELECT, INSERT ON editorial.t02_permission_probe TO editorial_runtime', role='migration')
        psql("INSERT INTO editorial.t02_permission_probe VALUES(1,true,'test')", role='runtime')
        for sql in ('UPDATE editorial.t02_permission_probe SET active=false',
                    'DELETE FROM editorial.t02_permission_probe', 'TRUNCATE editorial.t02_permission_probe'):
            psql(sql, role='runtime', expected='nonzero')
        psql('GRANT UPDATE(active) ON editorial.t02_permission_probe TO editorial_runtime', role='migration')
        psql('UPDATE editorial.t02_permission_probe SET active=false WHERE id=1', role='runtime')
        psql("UPDATE editorial.t02_permission_probe SET caption='tampered'", role='runtime', expected='nonzero')
        check('Default deny; explicit INSERT and column UPDATE work without blanket UPDATE/DELETE')
        psql('DROP TABLE editorial.t02_permission_probe', role='migration')
        scenarios = [
            ('prod,mock', (), 'T02_PROFILE'),
            ('prod', ('--editorial.providers.mock-enabled=true',), 'T02_MOCK'),
            ('prod', ('--editorial.providers.paid-calls-enabled=true',), 'T02_PAID_CALLS'),
            ('prod', ('--spring.jpa.hibernate.ddl-auto=update',), 'T02_DDL'),
            ('prod', ('--spring.flyway.enabled=false',), 'T02_FLYWAY'),
        ]
        for profile, extra, code in scenarios:
            run(app_command(profile, extra), expected='nonzero')
            check('Packaged application rejects ' + code, code in evidence['commands'][-1]['output'])
        psql('GRANT editorial_migrator TO editorial_runtime')
        try:
            run(app_command('prod'), expected='nonzero')
            check('Effective database privilege escalation is rejected', 'T02_DB_PRIVILEGES' in evidence['commands'][-1]['output'])
        finally:
            psql('REVOKE editorial_migrator FROM editorial_runtime')
        unreachable_env = dict(env, DB_URL=f'jdbc:postgresql://127.0.0.1:{free_port()}/editorial?connectTimeout=2')
        run(app_command('prod'), expected='nonzero', use_env=unreachable_env)
        check('Unreachable database fails startup instead of reporting ready')
        check('No business tables introduced', psql("SELECT count(*) FROM pg_tables WHERE schemaname='editorial'") == '0')
        success = True
    finally:
        for item in list(processes):
            stop_app(item)
        if pg_started:
            run([args.pg_bin / 'pg_ctl', '-D', work / 'data', '-m', 'fast', '-w', 'stop'])
        evidence.update(exitCode=0 if success else 1, utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        postgresql=run([args.pg_bin / 'postgres', '--version']))
        output = ROOT / 'tests/engineering/T02/evidence/integration.json'
        output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

"""Isolated T08 PostgreSQL verification: boots a throwaway cluster, applies the installed migrations, runs the
cost unit and database suites, and records argv / exit codes / per-case counts as evidence.

Only tracked inputs are used: the backend sources are copied verbatim into the ignored
``tests/engineering/T08/.work/<run>/backend`` (so Surefire never writes into a shared ``backend/target``),
roles come from ``backend/docker/bootstrap.sql``, and the schema comes from
``backend/src/main/resources/db/migration`` in Flyway's own order — ``beforeMigrate`` callback, then
V1..V5 as ``editorial_migrator``, then the two repeatable permission scripts. The T08 draft is **not** applied
separately: its body is installed as V5 and ``verify.py`` asserts the two stay byte-identical.

The cluster listens on a free port with random scram-sha-256 passwords (redacted from the evidence), and is
always stopped again by this script. No paid provider call is made and no contract is regenerated.

Example:
    python tests/engineering/T08/run_pg.py \
        --pg-bin .tools/t02/postgresql-full/pgsql/bin \
        --maven .tools/t02/apache-maven-3.9.11/bin/mvn.cmd \
        --java-home .tools/t02/jdk-21.0.12.1+1
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
MIGRATIONS = ROOT / 'backend/src/main/resources/db/migration'
TESTS_DEFAULT = 'CostPricingTest,T08PostgresTest'
DATABASE = 'editorial'
ADMIN_ROLE = 'editorial_admin'


def version_key(name: str) -> tuple[int, str]:
    match = re.match(r'V(\d+)__', name)
    return (int(match.group(1)), name) if match else (0, name)


def executable(candidate: Path) -> Path:
    """Windows carries .exe/.cmd suffixes that POSIX tool paths do not; accept whichever exists."""
    for suffix in ('', '.exe', '.cmd', '.bat'):
        path = Path(str(candidate) + suffix)
        if path.exists():
            return path
    raise SystemExit(f'tool not found: {candidate} (pass --pg-bin/--java-home/--maven)')


def decode_log(path: Path) -> str:
    """Tools answer in UTF-8 or in the Windows console codepage depending on the binary; take whichever decodes."""
    raw = path.read_bytes()
    for encoding in ('utf-8', 'gbk'):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', errors='replace')


def clip(text: str, limit: int = 2200) -> str:
    """Keep the evidence readable and small; the byte-exact log stays in the isolated run directory."""
    text = re.sub(r'[ \t]+', ' ', text).strip()
    if len(text) <= limit:
        return text
    head, tail = limit // 3, limit * 2 // 3
    return text[:head] + f' …[{len(text) - limit} chars elided, full log kept in the run directory]… ' + text[-tail:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--pg-bin', type=Path, default=ROOT / '.tools/t02/postgresql-full/pgsql/bin')
    parser.add_argument('--java-home', type=Path, default=ROOT / '.tools/t02/jdk-21.0.12.1+1')
    parser.add_argument('--maven', type=Path, default=ROOT / '.tools/t02/apache-maven-3.9.11/bin/mvn.cmd')
    parser.add_argument('--m2', type=Path, default=ROOT / '.tools/t02/m2')
    parser.add_argument('--tests', default=TESTS_DEFAULT, help='comma separated Surefire test classes')
    parser.add_argument('--evidence-name', default='pg-selftest')
    parser.add_argument('--work-root', type=Path, default=None,
                        help='scratch root for the cluster and the build copy (default: tests/engineering/T08/.work, '
                             'which is git-ignored; point elsewhere when the shell denies writes under tests/)')
    parser.add_argument('--timeout', type=int, default=900)
    parser.add_argument('--keep-cluster', action='store_true',
                        help='leave the cluster running (never used for delivered evidence)')
    args = parser.parse_args()
    if Path(args.evidence_name).name != args.evidence_name:
        parser.error('--evidence-name must be a filename stem')
    if (HERE / 'evidence' / (args.evidence_name + '.json')).exists():
        raise RuntimeError(f"evidence '{args.evidence_name}.json' already exists; choose a new name")
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    for required in (args.pg_bin / 'postgres', args.pg_bin / 'psql', args.pg_bin / 'initdb',
                     args.pg_bin / 'pg_ctl', args.pg_bin / 'createdb', args.java_home / 'bin/java', args.maven):
        executable(required)

    work = (args.work_root if args.work_root else HERE / '.work') / uuid.uuid4().hex
    work.mkdir(parents=True)
    passwords = {role: secrets.token_urlsafe(24) for role in ('admin', 'runtime', 'migration')}
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    env = os.environ.copy()
    for key in [k for k in env if k.startswith(('SPRING_', 'EDITORIAL_', 'DB_', 'T08_', 'T03_', 'T06_'))]:
        del env[key]
    env.update(JAVA_HOME=str(args.java_home), PGHOST='127.0.0.1', PGPORT=str(port), PGUSER=ADMIN_ROLE,
               PGPASSWORD=passwords['admin'], PGDATABASE=DATABASE,
               DB_RUNTIME_PASSWORD=passwords['runtime'], DB_MIGRATION_PASSWORD=passwords['migration'],
               T08_REAL_PG='true',
               T08_ADMIN_URL=f'jdbc:postgresql://127.0.0.1:{port}/{DATABASE}',
               T08_ADMIN_USER=ADMIN_ROLE, T08_ADMIN_PASSWORD=passwords['admin'],
               T08_RUNTIME_PASSWORD=passwords['runtime'], MAVEN_OPTS='-Duser.language=en -Duser.country=US')

    evidence = {
        'task': 'T08 cost ledger, pricing, usage and reconciliation on real PostgreSQL',
        'mode': 'REAL_POSTGRES_INSTALLED_MIGRATIONS',
        'paidCalls': 0,
        'note': 'Contract self-test only; no approval, no contract regeneration, no shared checkout mutation.',
        'generatedAt': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'cluster': {'port': port, 'database': DATABASE, 'adminRole': ADMIN_ROLE,
                    'authentication': 'scram-sha-256 with random per-run passwords (redacted below)'},
        'commands': [],
    }
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    server = None
    exit_code = 1

    def redact(text: str) -> str:
        for value in passwords.values():
            text = text.replace(value, '[REDACTED]')
        return text

    def run(cmd, timeout=None, expect=0):
        log = work / f'command-{len(evidence["commands"])}.log'
        argv = [str(executable(Path(str(cmd[0]))))] + [str(x) for x in cmd[1:]]
        with log.open('w', encoding='utf-8', errors='replace') as handle:
            done = subprocess.run(argv, cwd=str(ROOT), env=env, stdout=handle,
                                  stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                  timeout=timeout or args.timeout, creationflags=flags)
        output = redact(decode_log(log))
        evidence['commands'].append({'argv': [redact(x) for x in argv], 'exitCode': done.returncode,
                                     'expected': expect, 'output': clip(output)})
        print(f'command {len(evidence["commands"])} exit={done.returncode}', flush=True)
        if done.returncode != expect:
            print(clip(output, 6000), flush=True)
            raise RuntimeError('recorded command failed: ' + ' '.join(argv))
        return output

    def psql(*statements: str) -> str:
        return run([args.pg_bin / 'psql', '-X', '-v', 'ON_ERROR_STOP=1', '-Atc', ' '.join(statements)])

    try:
        for probe_version in ([args.java_home / 'bin/java', '-version'], [str(args.maven), '-version'],
                              [args.pg_bin / 'postgres', '--version'], [args.pg_bin / 'psql', '--version']):
            run(probe_version)

        shutil.copytree(ROOT / 'backend', work / 'backend', ignore=shutil.ignore_patterns('target'))
        evidence['backendCopy'] = 'verbatim copy of tracked backend/pom.xml + backend/src, target excluded'
        inputs = [ROOT / 'backend/pom.xml', ROOT / 'backend/docker/bootstrap.sql', *sorted(MIGRATIONS.glob('*.sql'))]
        evidence['inputFingerprints'] = [
            {'path': str(path.relative_to(ROOT)).replace('\\', '/'),
             'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in inputs]
        evidence['copiedSourceFiles'] = sum(1 for path in (work / 'backend').rglob('*')
                                            if path.is_file() and path.suffix in {'.java', '.sql', '.yml', '.xml'})

        init_password = work / 'init-password'
        init_password.write_text(passwords['admin'], encoding='utf-8')
        run([args.pg_bin / 'initdb', '-D', work / 'data', '-U', ADMIN_ROLE, '--auth=scram-sha-256',
             '--pwfile=' + str(init_password), '--encoding=UTF8', '--locale=C'])
        init_password.unlink()

        # pg_ctl daemonising is unavailable inside some restricted shells; fall back to a child process we own.
        try:
            run([args.pg_bin / 'pg_ctl', '-D', work / 'data', '-l', str(work / 'postgres.log'), '-o',
                 f'-p {port} -h 127.0.0.1', '-w', '-t', '60', 'start'])
            evidence['clusterStart'] = 'pg_ctl'
        except (RuntimeError, subprocess.TimeoutExpired):
            evidence['clusterStart'] = 'direct child process (pg_ctl unavailable here)'
            server = subprocess.Popen([str(executable(args.pg_bin / 'postgres')), '-D', str(work / 'data'),
                                       '-p', str(port), '-c', 'listen_addresses=127.0.0.1',
                                       '-c', 'logging_collector=off'],
                                      cwd=str(ROOT), env=env, stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL, creationflags=flags)

            def ready() -> bool:
                probe = subprocess.run([str(executable(args.pg_bin / 'psql')), '-d', 'postgres', '-X', '-Atc',
                                        'select 1'],
                                       cwd=str(ROOT), env=env, capture_output=True, text=True,
                                       creationflags=flags)
                return probe.returncode == 0 and '1' in probe.stdout

            for _ in range(120):
                if ready():
                    break
                time.sleep(1)
            else:
                raise RuntimeError('cluster did not become ready')

        run([args.pg_bin / 'createdb', DATABASE])
        run([args.pg_bin / 'psql', '-X', '-v', 'ON_ERROR_STOP=1', '-f', ROOT / 'backend/docker/bootstrap.sql'])

        versioned = sorted((p for p in MIGRATIONS.glob('V*__*.sql')), key=lambda p: version_key(p.name))
        repeatable = sorted(MIGRATIONS.glob('R__*.sql'))
        callbacks = sorted(MIGRATIONS.glob('beforeMigrate__*.sql'))
        wrapper = work / 'apply-installed-migrations.sql'
        with wrapper.open('w', encoding='utf-8', newline='\n') as handle:
            handle.write('-- Flyway order: beforeMigrate callback, V1..Vn as editorial_migrator, then R__ scripts.\n')
            for callback in callbacks:
                handle.write(f'\\i {callback.as_posix()}\n')
            handle.write('SET ROLE editorial_migrator;\n')
            for migration in versioned:
                handle.write(f'\\i {migration.as_posix()}\n')
            handle.write('RESET ROLE;\n')
            for script in repeatable:
                handle.write(f'\\i {script.as_posix()}\n')
            handle.write("SELECT 'applied' AS state, count(*) AS tables FROM pg_class c"
                         " JOIN pg_namespace n ON n.oid=c.relnamespace"
                         " WHERE n.nspname='editorial' AND c.relkind='r';\n")
        evidence['migrationOrder'] = [p.name for p in callbacks + versioned + repeatable]
        psql_out = run([args.pg_bin / 'psql', '-d', DATABASE, '-X', '-v', 'ON_ERROR_STOP=1', '-f', wrapper])
        evidence['migrationResult'] = re.sub(r'\s+', ' ', psql_out)[-400:]
        evidence['costTables'] = psql("select c.relname from pg_class c join pg_namespace n on n.oid=c.relnamespace"
                                      " where n.nspname='editorial' and c.relkind='r' and c.relname like 'cost%'"
                                      " order by 1").split()
        evidence['costTriggers'] = psql("select tgname from pg_trigger t join pg_class c on c.oid=t.tgrelid"
                                        " where c.relname='cost_ledger' and not tgisinternal order by 1").split()
        evidence['runtimeGrants'] = psql(
            "select grantee||'='||string_agg(privilege_type,'/' order by privilege_type) from"
            " information_schema.role_table_grants where table_schema='editorial' and table_name in"
            " ('cost_ledger','cost_pricing_version','audit_log') group by grantee order by grantee")

        run([args.maven, '-B', '-ntp', '-o', '-f', work / 'backend/pom.xml',
             '-Dmaven.repo.local=' + str(args.m2), 'test', '-Dtest=' + args.tests,
             '-Dsurefire.failIfNoSpecifiedTests=false'], timeout=args.timeout)

        reports = work / 'backend/target/surefire-reports'
        suites = []
        for xml in sorted(reports.glob('TEST-*.xml')):
            text = xml.read_text(encoding='utf-8', errors='replace')
            head = re.search(r'<testsuite[^>]*', text).group(0)

            def number(attribute):
                found = re.search(attribute + r'="([^"]*)"', head)
                return float(found.group(1)) if found else 0.0

            suites.append({'suite': re.search(r'name="([^"]*)"', head).group(1),
                           'tests': int(number('tests')), 'failures': int(number('failures')),
                           'errors': int(number('errors')), 'skipped': int(number('skipped')),
                           'timeSeconds': number('time'),
                           'cases': sorted(re.findall(r'<testcase name="([^"]*)"', text))})
        evidence['suites'] = suites
        evidence['totals'] = {'tests': sum(s['tests'] for s in suites),
                              'failures': sum(s['failures'] + s['errors'] for s in suites),
                              'skipped': sum(s['skipped'] for s in suites)}
        target = HERE / 'evidence' / (args.evidence_name + '-test-results')
        try:
            shutil.copytree(reports, target)
            evidence['testResults'] = str(target.relative_to(ROOT)).replace('\\', '/')
        except OSError as blocked:
            # A restricted shell may refuse writes under tests/; the reports still live in the ignored work dir.
            evidence['testResultsCopyBlocked'] = f'{type(blocked).__name__}: {blocked}'
            evidence['testResults'] = str(reports.relative_to(ROOT)).replace('\\', '/')
        exit_code = 0
    except Exception as failure:
        evidence['failure'] = type(failure).__name__ + ': ' + str(failure)
        raise
    finally:
        if server is not None:
            if args.keep_cluster:
                evidence['clusterLeftRunning'] = server.pid
            else:
                server.terminate()
                server.wait(timeout=60)
                evidence['clusterStopped'] = True
        elif not args.keep_cluster:
            try:
                run([args.pg_bin / 'pg_ctl', '-D', work / 'data', '-m', 'fast', '-w', 'stop'])
                evidence['clusterStopped'] = True
            except Exception as stop:
                evidence['clusterStopIssue'] = str(stop)
        evidence['exitCode'] = exit_code
        evidence['isolatedWork'] = str(work.relative_to(ROOT)).replace('\\', '/')
        out = HERE / 'evidence' / (args.evidence_name + '.json')
        try:
            out.parent.mkdir(exist_ok=True)
            out.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + '\n', encoding='utf-8',
                           newline='\n')
            print('evidence: ' + str(out), flush=True)
        except OSError as blocked:
            fallback = work / (args.evidence_name + '.json')
            fallback.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + '\n', encoding='utf-8',
                                newline='\n')
            print(f'evidence write to {out} blocked ({type(blocked).__name__}); kept at {fallback}', flush=True)
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())

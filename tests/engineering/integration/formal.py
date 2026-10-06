"""Verify the formal T03–T07 package against an isolated PostgreSQL cluster.

Copies the backend without altering production source or migrations, then runs the
T06/T07 HTTP tests against packaged V1–V4 and the integrated composition roots.
Only test sample paths are redirected to new evidence. No paid calls.

Example:
    python tests/engineering/integration/formal.py \
        --pg-bin .tools/t02/postgresql-full/pgsql/bin \
        --maven .tools/t02/apache-maven-3.9.11/bin/mvn.cmd \
        --java-home .tools/t02/jdk-21.0.12.1+1
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--pg-bin', type=Path, default=ROOT / '.tools/t02/postgresql-full/pgsql/bin')
    p.add_argument('--java-home', type=Path, default=ROOT / '.tools/t02/jdk-21.0.12.1+1')
    p.add_argument('--maven', type=Path, default=ROOT / '.tools/t02/apache-maven-3.9.11/bin/mvn.cmd')
    p.add_argument('--m2', type=Path, default=ROOT / '.tools/t02/m2')
    p.add_argument('--evidence-name', default='integration')
    p.add_argument('--upgrade-only', action='store_true')
    p.add_argument('--include-review-regressions', action='store_true')
    p.add_argument('--suite', choices=('core', 'identity', 'storage', 'skill', 'all'), default='core')
    args = p.parse_args()
    if Path(args.evidence_name).name != args.evidence_name:
        p.error('--evidence-name must be a filename stem')
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

    if (HERE/'evidence'/(args.evidence_name+'.json')).exists():
        raise RuntimeError('Evidence exists; choose a new name')
    work = HERE / '.work' / uuid.uuid4().hex
    work.mkdir(parents=True)
    evidence = {'mode': 'REAL_POSTGRES_REAL_HTTP_SESSION_CSRF', 'paidCalls': 0,
                'domainSubstitutes': ['T10/T11 not installed: production Changes and Deletion fail closed; transaction test participant marked explicitly'], 'commands': []}
    env = os.environ.copy()
    for k in list(env):
        if k.startswith(('SPRING_', 'EDITORIAL_', 'DB_', 'INITIAL_OWNER_', 'AUDIT_CURSOR_', 'APP_ORIGIN', 'T05_', 'T03_', 'T04_')):
            del env[k]
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    passwords = {k: secrets.token_urlsafe(32) for k in ('admin', 'runtime', 'migration', 'owner', 'cursor')}
    env.update(JAVA_HOME=str(args.java_home), PGHOST='127.0.0.1', PGPORT=str(port), PGUSER='editorial_admin',
               PGPASSWORD=passwords['admin'], PGDATABASE='editorial',
               DB_URL=f'jdbc:postgresql://127.0.0.1:{port}/editorial', DB_RUNTIME_PASSWORD=passwords['runtime'],
               DB_MIGRATION_PASSWORD=passwords['migration'], INITIAL_OWNER_USERNAME='owner',
               INITIAL_OWNER_PASSWORD=passwords['owner'], AUDIT_CURSOR_KEY=passwords['cursor'],
               APP_ORIGIN='http://localhost:3000', T06_REAL_PG='true', T06_ADMIN_PASSWORD=passwords['admin'])
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    started = False
    result_code = 1

    def redact(s):
        for value in passwords.values():
            s = s.replace(value, '[REDACTED]')
        return s

    def run(cmd, expected=0, timeout=420):
        file = work / ('command-' + str(len(evidence['commands'])) + '.log')
        with file.open('w', encoding='utf-8') as out:
            r = subprocess.run([str(x) for x in cmd], cwd=ROOT, env=env, stdout=out, stderr=subprocess.STDOUT,
                               stdin=subprocess.DEVNULL, timeout=timeout, creationflags=flags)
        output = redact(file.read_text(encoding='utf-8', errors='replace'))
        evidence['commands'].append({'argv': [str(x) for x in cmd], 'exitCode': r.returncode, 'expected': expected, 'output': output})
        print(f'command {len(evidence["commands"])} exit={r.returncode}', flush=True)
        if r.returncode != expected:
            print(output[-8000:], flush=True)
            raise RuntimeError('Recorded command failed')
        return output

    try:
        for cmd in ([args.java_home / 'bin/java', '-version'], [args.maven, '-version'], [args.pg_bin / 'postgres', '--version']):
            run(cmd)
        # Exact source copy, no shared configuration mutations.
        shutil.copytree(ROOT / 'backend', work / 'backend', ignore=shutil.ignore_patterns('target'))
        if args.include_review_regressions and not args.upgrade_only:
            review_tests = [ROOT / 'docs/execution/reviews/T06-round1/ReviewArticleAstTest.java',
                            ROOT / 'docs/execution/reviews/T06-round2/ReviewNestedClosureTest.java',
                            ROOT / 'docs/execution/reviews/T06-round3/ReviewEmphasisPunctuationTest.java']
            target = work / 'backend/src/test/java/com/example/editorial/article/ast'
            for source in review_tests:
                shutil.copyfile(source, target / source.name)
            evidence['reviewRegressions'] = [str(source.relative_to(ROOT)) for source in review_tests]
            boundary=ROOT/'docs/execution/reviews/T07-round1/ReviewVersionBoundaryTest.java'
            shutil.copyfile(boundary,work/'backend/src/test/java/com/example/editorial/article/version/ReviewVersionBoundaryTest.java')
            evidence['reviewRegressions'].append(str(boundary.relative_to(ROOT)))
        # Exercise the packaged global V1–V4 migrations and committed composition roots directly.
        samples=HERE/'evidence'/(args.evidence_name+'-samples')
        samples.mkdir(parents=True,exist_ok=True)
        test=work/'backend/src/test/java/com/example/editorial/article/job/T06PostgresTest.java'
        test.write_text(test.read_text(encoding='utf-8').replace('tests/engineering/T06/evidence/',samples.relative_to(ROOT).as_posix()+'/'),encoding='utf-8')
        evidence['transformations']=['T06 sample paths redirected; test assertions unchanged']
        evidence['samples']=str(samples.relative_to(ROOT))
        temp=work/'temp'
        temp.mkdir()
        env.update(EDITORIAL_IDENTITY_ENABLED='true',EDITORIAL_VERSION_ENABLED='true',
                   EDITORIAL_ARTICLE_ENABLED='true',EDITORIAL_STORAGE_ENABLED='true',
                   EDITORIAL_STORAGE_LOCAL_DIR=str(work/'objects'),
                   SPRING_FLYWAY_LOCATIONS='classpath:db/migration',
                   TMP=str(temp),TEMP=str(temp),JAVA_TOOL_OPTIONS='-Djava.io.tmpdir='+str(temp))
        if args.suite in ('identity', 'all'):
            env.update(T03_REAL_PG='true', T03_ADMIN_PASSWORD=passwords['admin'])
        if args.suite in ('storage', 'all'):
            env.update(T04_REAL_PG='true', T04_ADMIN_PASSWORD=passwords['admin'])
        if args.suite in ('skill', 'all'):
            env.update(T05_REAL_PG='true', T05_ADMIN_PASSWORD=passwords['admin'])
        pw = work / 'init-password'
        pw.write_text(passwords['admin'], encoding='utf-8')
        run([args.pg_bin / 'initdb', '-D', work / 'data', '-U', 'editorial_admin', '--auth=scram-sha-256',
             '--pwfile=' + str(pw), '--encoding=UTF8', '--locale=C'])
        pw.unlink()
        started = True
        run([args.pg_bin / 'pg_ctl', '-D', work / 'data', '-l', work / 'postgres.log', '-o', f'-h 127.0.0.1 -p {port}', '-w', 'start'])
        run([args.pg_bin / 'createdb', 'editorial'])
        run([args.pg_bin / 'psql', '-X', '-v', 'ON_ERROR_STOP=1', '-f', ROOT / 'backend/docker/bootstrap.sql'])
        tests = 'T07UpgradeTest' if args.upgrade_only else 'T07PostgresTest,T07UnavailableTest,VersionDiffTest,T06PostgresTest,ArticleAstTest,DeletionHandoffTest,CanonicalRequestTest'
        if args.suite != 'core' and not args.upgrade_only:
            domains={'identity':'T03PostgresTest','storage':'T04PostgresTest,T04RevisionPostgresTest',
                     'skill':'T05PostgresTest','all':'T03PostgresTest,T04PostgresTest,T04RevisionPostgresTest,T05PostgresTest'}
            tests = domains[args.suite] if args.suite != 'all' else tests+','+domains['all']
        if args.include_review_regressions and not args.upgrade_only:
            tests += ',ReviewArticleAstTest,ReviewNestedClosureTest,ReviewEmphasisPunctuationTest'
            # Select only the two original review methods, avoiding inherited author-test duplication.
            tests += ',ReviewVersionBoundaryTest#review*'
        if not args.upgrade_only and args.suite in ('core', 'all'):
            tests += ',T07RevisionBoundaryTest#revision*'
        evidence['executedInputs']=[{'path':str(path.relative_to(ROOT)), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(work.rglob('*')) if path.is_file() and (path.suffix in {'.java','.sql','.yml'} or path.name=='pom.xml')]
        run([args.maven, '-o', '-B', '-ntp', '-f', work / 'backend/pom.xml',
             '-Dmaven.repo.local=' + str(args.m2), 'clean', 'test',
             '-Dtest=' + tests, '-Dt06.root=' + str(ROOT), '-Dt07.samples=' + str(samples)], timeout=600)
        jar = work / 'backend/target/editorial-0.1.0-SNAPSHOT.jar'
        if jar.exists():
            evidence['jar'] = {'path': str(jar.relative_to(ROOT)), 'sha256': hashlib.sha256(jar.read_bytes()).hexdigest()}
        result_code = 0
    except Exception as e:
        evidence['failure'] = type(e).__name__ + ': ' + str(e)
    finally:
        reports = work / 'backend/target/surefire-reports'
        if reports.exists():
            target = HERE / 'evidence' / (args.evidence_name + '-test-results')
            shutil.copytree(reports, target, dirs_exist_ok=True)
            evidence['testResults'] = str(target.relative_to(ROOT))
        evidence['isolatedWork'] = str(work.relative_to(ROOT))
        if started:
            try:
                run([args.pg_bin / 'pg_ctl', '-D', work / 'data', '-m', 'immediate', '-w', 'stop'])
            except Exception as e:
                evidence['cleanupFailure'] = str(e)
                result_code = 1
        evidence['exitCode'] = result_code
        out = HERE / 'evidence' / (args.evidence_name + '.json')
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    return result_code


if __name__ == '__main__':
    raise SystemExit(main())

"""Isolated T05 real PostgreSQL/HTTP verification; never patches the shared checkout.

Copies the backend to an isolated directory, applies T03's shared integration patch (identity wiring),
installs T03's and T05's migration drafts as filesystem Flyway locations, boots a real PostgreSQL cluster,
runs the T02 bootstrap, then runs T05PostgresTest (real HTTP + sessions + CSRF + idempotency). No paid calls.

Example:
    python tests/engineering/T05/integration.py \
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
T03 = ROOT / 'tests' / 'engineering' / 'T03'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--pg-bin', type=Path, default=ROOT / '.tools/t02/postgresql-full/pgsql/bin')
    p.add_argument('--java-home', type=Path, default=ROOT / '.tools/t02/jdk-21.0.12.1+1')
    p.add_argument('--maven', type=Path, default=ROOT / '.tools/t02/apache-maven-3.9.11/bin/mvn.cmd')
    p.add_argument('--m2', type=Path, default=ROOT / '.tools/t02/m2')
    p.add_argument('--evidence-name', default='integration')
    p.add_argument('--include-review-cases', action='store_true', help='Also replay the six preserved independent T05 review counterexamples')
    args = p.parse_args()
    if Path(args.evidence_name).name != args.evidence_name:
        p.error('--evidence-name must be a filename stem')
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

    work = HERE / '.work' / uuid.uuid4().hex
    work.mkdir(parents=True)
    evidence = {'mode': 'REAL_POSTGRES_REAL_HTTP_SESSION_CSRF', 'paidCalls': 0,
                'domainSubstitutes': ['ConfigChangeSink.InMemory (event collection only)'], 'commands': []}
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
               APP_ORIGIN='http://localhost:3000', T05_REAL_PG='true', T05_ADMIN_PASSWORD=passwords['admin'])
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
        if args.include_review_cases:
            test = work / 'backend/src/test/java/com/example/editorial/editorial/skill/T05PostgresTest.java'
            original = test.read_text(encoding='utf-8')
            extra = (ROOT / 'docs/execution/reviews/T05-round1/ReviewCases.java').read_text(encoding='utf-8')
            pos = original.rfind('}')
            test.write_text(original[:pos] + extra + original[pos:], encoding='utf-8')
            evidence['independentReviewCases'] = 6
        # T03's shared-integration.patch is corrupt (first hunk declares 9 removed lines but provides 6),
        # so `git apply` rejects it. Apply the equivalent identity wiring directly in the isolated copy:
        # (1) remove the temporary deny-all SecurityFilterChain so T03's identity security is the only chain,
        # (2) add the editorial.identity.* configuration.
        evidence['t03Patch'] = {'status': 'CORRUPT_PATCH_WORKED_AROUND',
                                'detail': 'git apply rejected shared-integration.patch as corrupt; equivalent wiring applied directly'}
        skeleton = work / 'backend/src/main/java/com/example/editorial/bootstrap/SkeletonConfiguration.java'
        skeleton_text = skeleton.read_text(encoding='utf-8')
        block = '''

    /** Temporary deny-by-default shell; T03 owns authentication and replaces this bean. */
    @Bean SecurityFilterChain skeletonSecurity(HttpSecurity http) throws Exception {
        return http.authorizeHttpRequests(auth -> auth
                .requestMatchers(HttpMethod.GET, "/actuator/health", "/actuator/health/**", "/actuator/info").permitAll()
                .anyRequest().denyAll()).build();
    }'''
        assert block in skeleton_text, 'skeleton security block not found in isolated copy'
        skeleton.write_text(skeleton_text.replace(block, ''), encoding='utf-8', newline='\n')
        yml = work / 'backend/src/main/resources/application.yml'
        yml_text = yml.read_text(encoding='utf-8')
        assert 'editorial:\n  providers:\n' in yml_text, 'editorial providers block not found'
        yml_text = yml_text.replace('editorial:\n  providers:\n',
            'editorial:\n  identity:\n    enabled: true\n    origin: ${APP_ORIGIN:}\n'
            '    owner-username: ${INITIAL_OWNER_USERNAME:}\n    owner-display-name: ${INITIAL_OWNER_DISPLAY_NAME:Owner}\n'
            '    owner-password: ${INITIAL_OWNER_PASSWORD:}\n    cursor-key: ${AUDIT_CURSOR_KEY:}\n  providers:\n')
        yml.write_text(yml_text, encoding='utf-8', newline='\n')
        fixture = work / 'draft'
        fixture.mkdir()
        shutil.copyfile(T03 / 'migration-draft.sql', fixture / 'V1__t03_isolated_test.sql')
        shutil.copyfile(HERE / 'migration-draft.sql', fixture / 'V2__t05_skill_policy_prompt.sql')
        env['SPRING_FLYWAY_LOCATIONS'] = 'classpath:db/migration,filesystem:' + fixture.as_posix()
        pw = work / 'init-password'
        pw.write_text(passwords['admin'], encoding='utf-8')
        run([args.pg_bin / 'initdb', '-D', work / 'data', '-U', 'editorial_admin', '--auth=scram-sha-256',
             '--pwfile=' + str(pw), '--encoding=UTF8', '--locale=C'])
        pw.unlink()
        started = True
        run([args.pg_bin / 'pg_ctl', '-D', work / 'data', '-l', work / 'postgres.log', '-o', f'-h 127.0.0.1 -p {port}', '-w', 'start'])
        run([args.pg_bin / 'createdb', 'editorial'])
        run([args.pg_bin / 'psql', '-X', '-v', 'ON_ERROR_STOP=1', '-f', ROOT / 'backend/docker/bootstrap.sql'])
        run([args.maven, '-o', '-B', '-ntp', '-f', work / 'backend/pom.xml',
             '-Dmaven.repo.local=' + str(args.m2), 'clean', 'test',
             '-Dtest=T05PostgresTest,SemVerTest,HashingTest,JsonSchemaSkillConfigTest,BaselineResourcesTest,PromptContractTest,CursorCodecTest,SkillConfigDiffTest'], timeout=600)
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

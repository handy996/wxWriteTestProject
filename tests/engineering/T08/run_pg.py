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
    # Windows or Linux; PostgreSQL comes from the image pinned in infra/compose.yml.
    python tests/engineering/T08/run_pg.py --docker --expect-tests 65 --expect-skipped 0

    # Native PostgreSQL remains available for machines without Docker.
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
# The suites Surefire is actually asked to run: a --tests value naming anything else is a typo a self-check must
# catch rather than a green run with a missing report (round-5 finding F-R5-03).
KNOWN_SUITES = ('CostPricingTest', 'T08PostgresTest')
# The delivered self-test shape, asserted by --expect-tests: 22 Money/price/policy unit cases plus 35 cases
# against the real cluster. Deliberately a number the script enforces, so a silent skip cannot exit 0. Round 2
# added modelLevelQuotaReachesTheLookupThatReadsIt (config path -> scope -> lookup), the two service-path quota
# cases modelAndProviderQuotaScopesEachBindTheirWindow / unlistedProviderFollowsTheStatedQuotaPolicy, then round 3
# added one quota case per side that binds through a real nested YAML document (CostPricingTest
# quotaWrittenAsNestedYamlBindsTheScopeTheLookupReads, T08PostgresTest nestedYamlQuotaIsEnforcedByTheService),
# because flat fixture keys cannot show what Spring's own loader produces. The round-3 remediation added four
# more per side, one per finding: CostPricingTest quotaSuppliedThroughEnvironmentStyleNamesBinds (F-01),
# quotaLeavesAreNormalisedAtAssembly (F-08), bothQuotaLevelsAnswerTheirOwnEntries (F-03 ruling, V4 prefix guard,
# F-04(b) boundary), separatorBearingIdsAreRefusedNotCollided (F-05); T08PostgresTest
# looserModelEntryCannotLiftTheProviderCeiling and providerDayWindowClosesBeforeTheLooserModelDayWindow (F-03
# both-levels enforcement), zeroCallsPerDayClosesTheDayButNotTheBoot (F-08 behaviour half), and
# dottedModelIdIsMeteredInTheProviderWindow (F-04(b) on the service path). The round-4 remediation added eight
# more, one per finding that was measured as a silent path or an unwatched claim — unit:
# environmentQuotaPrefixTypoRefusesTheBoot (F-R4-02), environmentChannelAddressesProvidersInLowerCaseOnly
# (F-R4-03), dayCountLeafCarriesTheLongTheRecordStores (F-R4-04),
# canonicalQuotaNamesInsideAnEnvironmentShapedSourceAreBound (F-R4-05),
# advisoryLockOrderIsTheDictionaryOrderOfLockKeys (F-R4-09), everyUnknownQuotaLeafRefusesTheBoot (F-R4-10);
# live: providerWideQuotaWindowIsPartitionedByOwnerToday (F-R4-01, pinned as today's behavior pending the
# Owner decision) and theArticleCeilingSpeaksBeforeTheProviderQuotaWindow (F-R4-11b, the rejection order).
# Nothing was deleted and nothing was silently renamed: 22+35=57 became 28+37=65.
EXPECTED_TESTS = 65
DATABASE = 'editorial'
ADMIN_ROLE = 'editorial_admin'


def resolve_work_root(raw, here: Path) -> Path:
    """The run scratch root, absolute at startup whatever form --work-root arrived in.

    Round-3 finding F-07: with a relative root every one of the 14 recorded commands exited 0 and Surefire
    reported the suite green, and only then did the finally block call ``relative_to(ROOT)`` on the relative
    run directory — exit 1 and no evidence for a run that had actually succeeded. Resolving up front makes the
    recorded outcome and the evidence write see the same absolute path. ``--path-selftest`` exercises exactly
    this function."""
    return Path(raw).resolve() if raw else (here / '.work').resolve()


def inside_repo(path: Path) -> str:
    """Evidence path display: repository-relative when the run lives inside the repository, absolute when an
    operator deliberately pointed --work-root somewhere else. Never raises on the shape of a scratch path —
    the run outcome is already decided by the time evidence is written (round-3 finding F-07)."""
    try:
        return str(path.relative_to(ROOT)).replace('\\', '/')
    except ValueError:
        return path.as_posix()


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


def docker_image() -> str:
    """Use the same digest-pinned PostgreSQL image as the development topology."""
    compose = (ROOT / 'infra/compose.yml').read_text(encoding='utf-8')
    image = re.search(r'^\s+image:\s+(postgres:[^\s]+@sha256:[0-9a-f]{64})\s*$', compose, re.MULTILINE)
    if image is None:
        raise RuntimeError('infra/compose.yml must pin the PostgreSQL image by SHA-256')
    return image.group(1)


def container_path(path: Path, work: Path) -> str:
    """Map only the SQL inputs mounted into the throwaway container."""
    path = path.resolve()
    if path == (ROOT / 'backend/docker/bootstrap.sql').resolve():
        return '/bootstrap.sql'
    for source, destination in ((MIGRATIONS.resolve(), '/migrations'), (work.resolve(), '/test-run')):
        if source == path or source in path.parents:
            return destination + '/' + path.relative_to(source).as_posix()
    raise ValueError(f'path is not mounted in the test container: {path}')


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


CONTROLLED_EVIDENCE = HERE / 'evidence'


def lands_in_controlled(candidate: Path) -> bool:
    """Whether this landing place is the tracked, review-relevant evidence directory **or anything under it**.

    Round-5 finding F-R5-02: the refusal compared the landing place with **equality** to the resolved tracked
    directory — so ``--work-root tests/engineering/T08/evidence`` (whose
    unchosen default is ``…/evidence/evidence``) resolved to a directory one level below the tracked one, was not
    equal to it, and passed the check with ``problems=[]`` while writing straight into the controlled tree. A
    sub-directory of the controlled directory is just as controlled as the directory itself, so the test is now
    ancestry: the candidate is the tracked directory or has the tracked directory among its parents."""
    controlled = CONTROLLED_EVIDENCE.resolve()
    return candidate == controlled or controlled in candidate.parents


def resolve_evidence_dir(raw, work_root: Path) -> tuple[Path, bool]:
    """Where this run's evidence lands, and whether the operator asked for that place on purpose.

    Round-4 finding F-R4-12: the default was the tracked, review-relevant directory under
    ``tests/engineering/T08/evidence``, so every exploratory run dropped files there without anyone choosing
    it — the controlled directory accumulated scratch artifacts, and "an operator persisted my evidence for
    me" became indistinguishable from "this run was always meant to be kept". The default is now the work root
    (scratch, git-ignored like everything else under it); pointing at the tracked directory is a deliberate
    ``--evidence-dir``. The second return value says which of the two happened, so the self-check can refuse a
    run that landed in the controlled directory that nobody chose."""
    if raw is None:
        return (work_root / 'evidence').resolve(), False
    return Path(raw).resolve(), True


def wanted_suites(raw: str) -> list[str]:
    """The class names Surefire is asked to run, with any ``#method`` filter stripped off.

    Round-4 finding F-R4-13: the suite-presence check compared the RAW ``--tests`` values to the class names the
    reports carry, so ``--tests CostPricingTest#dayCountLeafCarriesTheLongTheRecordStores`` — a deliberately
    narrowed rerun a reviewer or operator types to exercise one case in isolation — named a suite no report can
    ever be called, and a green execution exited non-zero with ``no Surefire report for …``. The method filter
    is still honoured by Surefire; only the presence check ignores it."""
    return [part.split('#', 1)[0].strip() for part in raw.split(',') if part.strip()]


def judge_suites(suites, args):
    """Fail closed on skipped, missing, empty or inconsistent Surefire results."""
    totals = {'tests': sum(s['tests'] for s in suites),
              'failures': sum(s['failures'] + s['errors'] for s in suites),
              'skipped': sum(s['skipped'] for s in suites)}
    problems = []
    if totals['failures']:
        problems.append(f"failures/errors={totals['failures']}")
    if totals['tests'] != args.expect_tests:
        problems.append(f"executed {totals['tests']} cases, expected {args.expect_tests}")
    if totals['skipped'] != args.expect_skipped:
        problems.append(f"skipped {totals['skipped']}, expected {args.expect_skipped}")
    wanted = wanted_suites(args.tests)
    reported = [s['suite'].rsplit('.', 1)[-1] for s in suites]
    missing = [name for name in wanted if name not in reported]
    if missing:
        problems.append('no Surefire report for ' + ', '.join(missing))
    for suite in suites:
        if len(suite['cases']) != suite['tests']:
            problems.append(f"{suite['suite']}: testcase count disagrees with tests={suite['tests']}")
    return totals, problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--docker', action='store_true',
                        help='provision PostgreSQL from the pinned Compose image instead of local PG binaries')
    parser.add_argument('--pg-bin', type=Path, default=ROOT / '.tools/t02/postgresql-full/pgsql/bin')
    parser.add_argument('--java-home', type=Path, default=ROOT / '.tools/t02/jdk-21.0.12.1+1')
    parser.add_argument('--maven', type=Path, default=ROOT / ('.tools/t02/apache-maven-3.9.11/bin/mvn.cmd'
                                                           if os.name == 'nt' else
                                                           '.tools/t02/apache-maven-3.9.11/bin/mvn'))
    parser.add_argument('--m2', type=Path, default=ROOT / '.tools/t02/m2')
    parser.add_argument('--tests', default=TESTS_DEFAULT, help='comma separated Surefire test classes '
                                                              '(method filters such as CostPricingTest#foo are '
                                                              'honoured by the suite-presence check)')
    parser.add_argument('--evidence-name', default='pg-selftest')
    parser.add_argument('--evidence-dir', type=Path, default=None,
                        help='directory the evidence JSON and the Surefire copies are written to. Deliberately '
                             'no default inside the repository: unset means <work-root>/evidence, so an '
                             'exploratory run cannot quietly add files to the tracked evidence directory '
                             '(round-4 finding F-R4-12). Pass tests/engineering/T08/evidence to persist a run '
                             'as delivered evidence.')
    parser.add_argument('--work-root', type=Path, default=None,
                        help='scratch root for the cluster and the build copy (default: tests/engineering/T08/.work, '
                             'which is git-ignored; point elsewhere when the shell denies writes under tests/)')
    parser.add_argument('--timeout', type=int, default=900)
    parser.add_argument('--expect-tests', type=int, default=EXPECTED_TESTS,
                        help='fail (non-zero, no evidence) unless Surefire reports exactly this many executed cases')
    parser.add_argument('--expect-skipped', type=int, default=0,
                        help='fail unless exactly this many cases were skipped (a silently skipped real-PG suite '
                             'must not be able to exit 0)')
    parser.add_argument('--skip-tests', action='store_true',
                        help='build the cluster and apply the installed migrations, but run no tests (diagnosis only)')
    parser.add_argument('--keep-cluster', action='store_true',
                        help='leave the cluster running and drop credentials.txt in the ignored run directory '
                             '(never used for delivered evidence)')
    parser.add_argument('--path-selftest', action='store_true',
                        help='exit after proving the F-07 fix without booting anything: a relative --work-root '
                             'resolves to an absolute run directory inside the repository before any cluster exists')
    args = parser.parse_args()
    for name in ('pg_bin', 'java_home', 'maven', 'm2'):
        setattr(args, name, getattr(args, name).resolve())
    if args.docker and args.keep_cluster:
        parser.error('--docker does not support --keep-cluster; its fixture container is always removed')
    if Path(args.evidence_name).name != args.evidence_name:
        parser.error('--evidence-name must be a filename stem')
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    work_root = resolve_work_root(args.work_root, HERE)
    evidence_dir, chosen = resolve_evidence_dir(args.evidence_dir, work_root)
    if args.path_selftest:
        # The dispatch's relative command shape must resolve like the absolute one; this is the self-check for
        # finding F-07, and it deliberately shares resolve_work_root with the real run path. Round-4 finding
        # F-R4-13 adds the other two shapes this script has to get right without booting anything: an absolute
        # --work-root outside the repository is a deliberate operator choice, not a problem to refuse, and the
        # evidence landing place is reported so a run cannot quietly write into the tracked directory.
        probe = work_root / uuid.uuid4().hex
        problems = []
        notes = []
        if not probe.is_absolute():
            problems.append('run directory is not absolute: ' + str(probe))
        if ROOT not in probe.parents:
            notes.append('run directory resolves outside the repository root ' + str(ROOT) + ': ' + str(probe)
                         + ' (a deliberate --work-root, not a defect: the run simply cannot be described by a '
                         'repository-relative path)')
        if lands_in_controlled(evidence_dir) and not chosen:
            # Round-5 finding F-R5-02: ancestry, not equality — a landing under the tracked directory is inside it.
            problems.append('evidence would land in the controlled directory '
                            + str(CONTROLLED_EVIDENCE) + ' or under it without an explicit --evidence-dir')
        # Round-5 finding F-R5-03: the selftest has to check the --tests the OPERATOR passed, not a hardcoded
        # string — the fourth round shipped a check that always reported the same two classes whatever the command
        # line said, so it never exercised the method filter a reviewer actually types. The raw input is echoed too.
        filtered = wanted_suites(args.tests)
        unknown = sorted(set(filtered) - set(KNOWN_SUITES))
        if unknown:
            problems.append('--tests names suites Surefire never reports here: ' + ', '.join(unknown)
                            + ' (the deliverable suites are ' + ', '.join(KNOWN_SUITES) + ')')
        print(json.dumps({'workRoot': work_root.as_posix(), 'runDirectoryShape': probe.as_posix(),
                          'relativeInput': str(args.work_root) if args.work_root else '(default)',
                          'evidenceDir': evidence_dir.as_posix(),
                          'evidenceDirChosen': chosen,
                          'controlledEvidenceDir': CONTROLLED_EVIDENCE.as_posix(),
                          'insideControlledDirectory': lands_in_controlled(evidence_dir),
                          'testsInput': args.tests,
                          'methodFilterStripped': filtered,
                          'notes': notes, 'problems': problems}, ensure_ascii=False))
        return 1 if problems else 0
    if not chosen:
        # Round-5 finding F-R5-02, the half the equality check missed: a default landing UNDER the tracked
        # directory (e.g. --work-root tests/engineering/T08/evidence → …/evidence/evidence) is inside the controlled
        # tree just as much as the tree itself. An unchosen landing there is refused before any cluster or build is
        # started, so the refusal is reachable, not a string a weakening can park behind an `if False:`.
        if lands_in_controlled(evidence_dir):
            raise SystemExit(f'--work-root {work_root} puts the unchosen default evidence into the controlled '
                             f'directory {evidence_dir}; pass --evidence-dir tests/engineering/T08/evidence to keep '
                             'it on purpose, or point --work-root somewhere outside the tracked tree')
        print(f'evidence will land in {evidence_dir} (scratch, under --work-root); '
              'pass --evidence-dir tests/engineering/T08/evidence to persist it', flush=True)
    if (evidence_dir / (args.evidence_name + '.json')).exists():
        raise RuntimeError(f"evidence '{args.evidence_name}.json' already exists in {evidence_dir}; "
                           'choose a new name')
    required_tools = [args.java_home / 'bin/java', args.maven]
    docker = None
    if args.docker:
        located = shutil.which('docker')
        if located is None:
            raise SystemExit('--docker requires the Docker CLI and a running engine')
        docker = Path(located)
        image = docker_image()
        required_tools.append(docker)
    else:
        required_tools.extend(args.pg_bin / name for name in ('postgres', 'psql', 'initdb', 'pg_ctl', 'createdb'))
    for required in required_tools:
        executable(required)

    work = work_root / uuid.uuid4().hex
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
    if args.docker:
        env['POSTGRES_PASSWORD'] = passwords['admin']

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
    container = 'wxagent-t08-' + work.name if args.docker else None
    container_attempted = False
    exit_code = 1

    def redact(text: str) -> str:
        for value in passwords.values():
            text = text.replace(value, '[REDACTED]')
        return text

    def run(cmd, timeout=None, expect=0):
        log = work / f'command-{len(evidence["commands"])}.log'
        if args.docker and Path(cmd[0]).parent == args.pg_bin:
            argv = [str(docker), 'exec', container, Path(cmd[0]).name]
            argv.extend(container_path(x, work) if isinstance(x, Path) else str(x) for x in cmd[1:])
        else:
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
        for probe_version in ([args.java_home / 'bin/java', '-version'], [str(args.maven), '-version']):
            run(probe_version)

        shutil.copytree(ROOT / 'backend', work / 'backend', ignore=shutil.ignore_patterns('target'))
        evidence['backendCopy'] = 'verbatim copy of tracked backend/pom.xml + backend/src, target excluded'
        inputs = [ROOT / 'backend/pom.xml', ROOT / 'backend/docker/bootstrap.sql', *sorted(MIGRATIONS.glob('*.sql'))]
        evidence['inputFingerprints'] = [
            {'path': str(path.relative_to(ROOT)).replace('\\', '/'),
             'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in inputs]
        evidence['copiedSourceFiles'] = sum(1 for path in (work / 'backend').rglob('*')
                                            if path.is_file() and path.suffix in {'.java', '.sql', '.yml', '.xml'})

        if args.docker:
            container_attempted = True
            run([docker, 'run', '--detach', '--name', container,
                 '--publish', f'127.0.0.1:{port}:5432',
                 '--env', f'POSTGRES_USER={ADMIN_ROLE}', '--env', f'POSTGRES_DB={DATABASE}',
                 '--env', 'POSTGRES_PASSWORD', '--env', 'PGPASSWORD',
                 '--env', 'DB_RUNTIME_PASSWORD', '--env', 'DB_MIGRATION_PASSWORD',
                 '--env', 'PGHOST=127.0.0.1', '--env', 'PGPORT=5432',
                 '--env', f'PGUSER={ADMIN_ROLE}', '--env', f'PGDATABASE={DATABASE}',
                 '--env', 'POSTGRES_INITDB_ARGS=--auth=scram-sha-256',
                 '--mount', f'type=bind,source={MIGRATIONS},target=/migrations,readonly',
                 '--mount', f'type=bind,source={ROOT / "backend/docker/bootstrap.sql"},target=/bootstrap.sql,readonly',
                 '--mount', f'type=bind,source={work},target=/test-run,readonly', image])
            evidence['clusterStart'] = 'digest-pinned Docker container'
            evidence['cluster']['image'] = image
            for _ in range(60):
                ready = subprocess.run([str(docker), 'exec', container, 'pg_isready'], env=env,
                                       capture_output=True, timeout=10, creationflags=flags)
                if ready.returncode == 0:
                    break
                time.sleep(1)
            else:
                raise RuntimeError('Docker PostgreSQL did not become ready')
        else:
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
        for probe_version in ([args.pg_bin / 'postgres', '--version'], [args.pg_bin / 'psql', '--version']):
            run(probe_version)
        run([args.pg_bin / 'psql', '-X', '-v', 'ON_ERROR_STOP=1', '-f', ROOT / 'backend/docker/bootstrap.sql'])

        versioned = sorted((p for p in MIGRATIONS.glob('V*__*.sql')), key=lambda p: version_key(p.name))
        repeatable = sorted(MIGRATIONS.glob('R__*.sql'))
        callbacks = sorted(MIGRATIONS.glob('beforeMigrate__*.sql'))
        wrapper = work / 'apply-installed-migrations.sql'
        with wrapper.open('w', encoding='utf-8', newline='\n') as handle:
            handle.write('-- Flyway order: beforeMigrate callback, V1..Vn as editorial_migrator, then R__ scripts.\n')
            for callback in callbacks:
                handle.write(f'\\i {container_path(callback, work) if args.docker else callback.as_posix()}\n')
            handle.write('SET ROLE editorial_migrator;\n')
            for migration in versioned:
                handle.write(f'\\i {container_path(migration, work) if args.docker else migration.as_posix()}\n')
            handle.write('RESET ROLE;\n')
            for script in repeatable:
                handle.write(f'\\i {container_path(script, work) if args.docker else script.as_posix()}\n')
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

        if args.skip_tests:
            evidence['testsSkipped'] = '--skip-tests: cluster and installed migrations only'
            exit_code = 0
            return exit_code

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
        # The count is a gate, not a caption: an empty run, a gated-off real-PG suite or a missing class must not
        # be able to exit 0. Defaults are the delivered self-test shape; --expect-tests overrides deliberately.
        evidence['totals'], problems = judge_suites(suites, args)
        wanted = wanted_suites(args.tests)
        evidence['expectations'] = {'tests': args.expect_tests, 'skipped': args.expect_skipped,
                                    'suitesRequested': wanted, 'problems': problems}
        if problems:
            raise RuntimeError('test totals rejected the run: ' + '; '.join(problems))
        exit_code = 0
    except Exception as failure:
        evidence['failure'] = type(failure).__name__ + ': ' + str(failure)
        raise
    finally:
        # Maven failures and rejected totals still need their original Surefire reports.
        # Do this before cluster cleanup, which may itself fail.
        reports = work / 'backend/target/surefire-reports'
        if reports.is_dir():
            target = evidence_dir / (args.evidence_name + '-test-results')
            try:
                shutil.copytree(reports, target)
                evidence['testResults'] = inside_repo(target)
            except OSError as blocked:
                evidence['testResultsCopyBlocked'] = f'{type(blocked).__name__}: {blocked}'
                evidence['testResults'] = inside_repo(reports)
                exit_code = 1
        if container_attempted:
            try:
                run([docker, 'rm', '--force', '--volumes', container])
                evidence['clusterStopped'] = True
            except Exception as stop:
                evidence['clusterStopIssue'] = str(stop)
                exit_code = 1
        elif server is not None:
            if args.keep_cluster:
                evidence['clusterLeftRunning'] = server.pid
                # A kept cluster is for diagnosis, so hand back the throwaway credentials — one write, the
                # database name included, so a diagnosis session can attach. They live in the ignored run
                # directory beside a cluster that holds nothing but fixtures. (Round-5 finding F-R5-06: this
                # file was previously written twice, the second overwriting the first in a different format,
                # and evidence['credentialsFile'] was assigned twice.)
                (work / 'credentials.txt').write_text(
                    f'port={port}\ndatabase={DATABASE}\nadmin={ADMIN_ROLE}\n'
                    f"admin_password={passwords['admin']}\nruntime_password={passwords['runtime']}\n"
                    f"migration_password={passwords['migration']}\n",
                    encoding='utf-8', newline='\n')
                evidence['credentialsFile'] = inside_repo(work / 'credentials.txt')
                print(f"kept cluster: port={port} credentials={work / 'credentials.txt'}", flush=True)
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
        evidence['isolatedWork'] = inside_repo(work)
        # 证据落点 self-check (round-4 finding F-R4-12): the JSON records where it was written and whether the
        # operator chose that place, so a tracked-evidence file can be told apart from a run that merely used the
        # scratch default — and a landing in the controlled directory that nobody asked for is a problem, printed
        # before the write and recorded after it.
        evidence['evidenceLanding'] = {'directory': inside_repo(evidence_dir), 'absolute': evidence_dir.as_posix(),
                                       'explicitlyChosen': chosen,
                                       'insideControlledDirectory': lands_in_controlled(evidence_dir)}
        out = evidence_dir / (args.evidence_name + '.json')
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
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

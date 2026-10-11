"""Inject a real JUnit failure in an isolated copy; require the runner to retain its XML.

The normal 65-case run is separate and must still pass without skips. This probe never
modifies product sources and succeeds only if the injected failure is visible in the
runner exit code, the exported Surefire XML and the recorded evidence.
"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / '.work/ci/report-failure'


def main():
    copy = BASE / 'checkout'
    if BASE.exists():
        raise SystemExit('report-failure probe requires a fresh output directory')
    copy.mkdir(parents=True)
    shutil.copytree(ROOT / 'backend', copy / 'backend', ignore=shutil.ignore_patterns('target', '.github'))
    runner = copy / 'tests/engineering/T08/run_pg.py'
    runner.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / 'tests/engineering/T08/run_pg.py', runner)
    (copy / 'infra').mkdir()
    shutil.copyfile(ROOT / 'infra/compose.yml', copy / 'infra/compose.yml')
    source = Path('backend/src/test/java/com/example/editorial/cost/CostPricingTest.java')
    original = (ROOT / source).read_bytes()
    test = copy / source
    text = test.read_text(encoding='utf-8')
    anchor = 'class CostPricingTest {'
    if text.count(anchor) != 1:
        raise SystemExit('cannot locate the isolated cost test class for the failure probe')
    test.write_text(text.replace(anchor, anchor + '''
    @Test void ciReportRetentionFailureProbe() {
        fail("CI_REPORT_RETENTION_PROBE");
    }
''', 1), encoding='utf-8', newline='\n')
    evidence = BASE / 'evidence'
    maven = ROOT / '.tools/t02/apache-maven-3.9.11/bin' / ('mvn.cmd' if sys.platform == 'win32' else 'mvn')
    argv = [sys.executable, str(runner), '--docker', '--maven', str(maven),
            '--java-home', str(ROOT / '.tools/t02/jdk-21.0.12.1+1'), '--m2', str(ROOT / '.tools/t02/m2'),
            '--work-root', str(BASE / 'work'), '--evidence-dir', str(evidence),
            '--evidence-name', 'expected-failure', '--tests', 'CostPricingTest',
            '--expect-tests', '29', '--expect-skipped', '0']
    result = subprocess.run(argv, cwd=copy)
    record = json.loads((evidence / 'expected-failure.json').read_text(encoding='utf-8'))
    xml = evidence / 'expected-failure-test-results/TEST-com.example.editorial.cost.CostPricingTest.xml'
    suite = ElementTree.parse(xml).getroot()
    failures = [case for case in suite.findall('testcase') if case.find('failure') is not None]
    checks = {
        'runnerFailed': result.returncode != 0 and record['exitCode'] != 0,
        'exportedReportReferenced': record.get('testResults', '').replace('\\', '/').endswith('expected-failure-test-results'),
        'xmlCounts': all(suite.get(k) == v for k, v in {'tests': '29', 'failures': '1', 'errors': '0', 'skipped': '0'}.items()),
        'expectedFailureOnly': len(failures) == 1 and failures[0].get('name') == 'ciReportRetentionFailureProbe'
                               and 'CI_REPORT_RETENTION_PROBE' in ElementTree.tostring(failures[0], encoding='unicode'),
        'clusterStopped': record.get('clusterStopped') is True,
        'originalSourceUnchanged': (ROOT / source).read_bytes() == original,
    }
    report = {'purpose': 'expected failure probe, separate from the mandatory 65-case clean run',
              'runnerExitCode': result.returncode, 'checks': checks,
              'report': xml.relative_to(ROOT).as_posix(), 'reportSha256': hashlib.sha256(xml.read_bytes()).hexdigest()}
    (BASE / 'probe.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())

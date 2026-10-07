r"""T02 round-4 control C-1: a value-only exemption must not release the whole file.

Copies the three files that the withdrawn config exempted by path into $env:TEMP\t02r4\c1, appends a
SYNTHETIC github-pat and a synthetic private-key block to each (shapes assembled at runtime so this
source never holds a live-shaped key, and chosen to match Gitleaks DEFAULT rules, not T02 custom
rules), then scans the same tree with three configs:
  delivered   tests/engineering/T02/gitleaks.toml         -> must catch all 6 canaries
  defaults    no allowlists at all                        -> must catch all 6 canaries
  legacy      pre-deca2a1 config re-read from git history -> expected to catch 0 (the closed defect)
The legacy config is written by python (no BOM); a config that fails to PARSE would also produce
zero findings, so this harness distinguishes "scan ran and found nothing" from "scan never ran" by
requiring the JSON report file and the scanner's own byte summary line.
Nothing in the repository is written.
"""
import json
import pathlib
import re
import shutil
import subprocess

ROOT = pathlib.Path(r'E:\project\codex\wxAgent')
HERE = pathlib.Path(__file__).resolve().parent
SCRATCH = pathlib.Path.home() / 'AppData/Local/Temp/t02r4/c1'
GITLEAKS = str(ROOT / '.tools/t02/gitleaks/gitleaks.exe')
FORMERLY_EXEMPT = ('docs/AI-Editorial-Agent-SRS-v1.0.md',
                   'tests/engineering/T04/evidence/integration.json',
                   'tests/engineering/T02/evidence/r01-integrity.json')
CANARY_RULES = ('github-pat', 'private-key')


def canary():
    """Synthetic credential shapes, assembled at runtime."""
    token = 'ghp_' + 'R4REVIEW' + 'SYNTHETICNOTAREALKEY' + '0123456789abcdefghij'
    header = '-----BEGIN RSA PRI' + 'VATE KEY-----'
    footer = '-----END RSA PRI' + 'VATE KEY-----'
    body = 'MIIBVgIBADANBgkqhkiG9w0BAQEFAgCV' + 'R4REVIEWNOTAREALKEYaaaaaaaaaaaaaaaaa'
    return 'github_token: %s\n%s\n%s\n%s\n' % (token, header, body, footer)


EXPECTED = sorted('%s:%s' % (n, r) for n in FORMERLY_EXEMPT for r in CANARY_RULES)


def scan(tree, config, name):
    report = SCRATCH / (name + '.report.json')
    if report.exists():
        report.unlink()
    proc = subprocess.run([GITLEAKS, 'dir', str(tree), '--no-banner', '--config', str(config),
                           '--report-format', 'json', '--report-path', str(report)],
                          capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=ROOT)
    log = (proc.stdout + proc.stderr).splitlines()
    bytes_line = [l.strip() for l in log if 'bytes' in l]
    if not report.exists():
        return {'exit': proc.returncode, 'reportWritten': False, 'count': None, 'caught': [],
                'canariesCaught': [], 'scanned': '', 'log': log[:12]}
    findings = json.loads(report.read_text(encoding='utf-8'))
    caught = {'%s:%s' % (pathlib.Path(f['File']).resolve().relative_to(tree.resolve()).as_posix(), f['RuleID'])
              for f in findings}
    return {'exit': proc.returncode, 'reportWritten': True, 'count': len(findings),
            'rules': sorted({f['RuleID'] for f in findings}),
            'caught': sorted(caught),
            'canariesCaught': sorted(caught & set(EXPECTED)),
            'canaryCount': len(caught & set(EXPECTED)),
            'otherFindings': sorted(caught - set(EXPECTED)),
            'scanned': bytes_line[-1] if bytes_line else '',
            'logTail': log[-3:]}


def main():
    shutil.rmtree(SCRATCH, ignore_errors=True)
    tree = SCRATCH / 'tree'
    tree.mkdir(parents=True)
    original_bytes = 0
    for name in FORMERLY_EXEMPT:
        target = tree / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
        with target.open('a', encoding='utf-8', newline='\n') as stream:
            stream.write(canary())
        original_bytes += (ROOT / name).stat().st_size
    print('three formerly exempted files, original bytes: %d' % original_bytes)

    probe = SCRATCH / 'probe'
    probe.mkdir()
    (probe / 'probe.txt').write_text(canary(), encoding='utf-8', newline='\n')
    defaults = SCRATCH / 'defaults-only.toml'
    defaults.write_text('title = "defaults only"\n[extend]\nuseDefault = true\n', encoding='utf-8', newline='\n')

    # pre-deca2a1 config, straight from git history, written with python so there is no BOM
    legacy_text = subprocess.run(['git', 'show', 'deca2a1^:tests/engineering/T02/gitleaks.toml'],
                                 capture_output=True, text=True, encoding='utf-8', cwd=ROOT).stdout
    legacy = SCRATCH / 'legacy-gitleaks.toml'
    legacy.write_text(legacy_text, encoding='utf-8', newline='\n')
    print('legacy config: %d bytes, %d paths clause(s), BOM=%s'
          % (len(legacy_text), len(re.findall(r'(?m)^paths = ', legacy_text)),
             legacy.read_bytes()[:3] == b'\xef\xbb\xbf'))

    results = {
        'probeDefaultsOnly': scan(probe, defaults, 'probe-defaults'),
        'deliveredConfig': scan(tree, ROOT / 'tests/engineering/T02/gitleaks.toml', 'delivered'),
        'defaultsOnly': scan(tree, defaults, 'defaults'),
        'legacyPreDeca2a1': scan(tree, legacy, 'legacy'),
    }
    verdict = {
        'canaryShapesCaughtByDefaultRulesAlone': results['probeDefaultsOnly']['count'] >= 2,
        'deliveredCatchesAllSixCanaries': results['deliveredConfig']['canaryCount'] == 6,
        'deliveredOnlyCanariesRemain': results['deliveredConfig']['count'] == 6,
        'defaultsCatchesAllSixCanaries': results['defaultsOnly']['canaryCount'] == 6,
        'legacyScanActuallyRan': results['legacyPreDeca2a1']['reportWritten'] and results['legacyPreDeca2a1']['count'] is not None,
        'legacyCatchesZeroCanaries': results['legacyPreDeca2a1']['canaryCount'] == 0,
        'legacyScannerReportsZeroBytesForThem': bool(re.search(r'~?0 bytes|\(0 \)',
                                                              results['legacyPreDeca2a1']['scanned'])),
    }
    payload = {'expectedCanaries': EXPECTED, 'results': results, 'verdict': verdict}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    (HERE / 'evidence' / 'c1-value-exemption.json').write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    failed = [k for k, v in verdict.items() if not v]
    print('C1 VERDICT: ' + ('ALL PASS' if not failed else 'FAILED ' + json.dumps(failed)))
    shutil.rmtree(SCRATCH, ignore_errors=True)
    print('scratch removed:', not SCRATCH.exists(), '| legacy BOM copy in TEMP remains:',
          (pathlib.Path.home() / 'AppData/Local/Temp/t02r4/legacy-gitleaks.toml').exists())
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())

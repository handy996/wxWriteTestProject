"""T02 round-4 judgement J-4: is the new T07 secret invariant strictly stronger than the old one?

verify_delivery.py used to assert "exactly six findings and all of them in r01-integrity.json"; it now
asserts "any surviving finding anywhere fails". Both predicates are evaluated here against the same
scanned bytes, with the delivered config, over a TEMP tree that plants findings in three patterns:
  A no finding at all (today's real tree shape)
  B one canary in the previously blessed file
  C six canaries, ALL in the previously blessed file (the scenario the old count accepted)
If C passes the old predicate and fails the new one, the new form is not merely stricter: the old
form would have waved through six real secrets.
"""
import json
import pathlib
import shutil
import subprocess

ROOT = pathlib.Path(r'E:\project\codex\wxAgent')
HERE = pathlib.Path(__file__).resolve().parent
SCRATCH = pathlib.Path.home() / 'AppData/Local/Temp/t02r4/j4'
GITLEAKS = str(ROOT / '.tools/t02/gitleaks/gitleaks.exe')
CONFIG = ROOT / 'tests/engineering/T02/gitleaks.toml'
BLESS = 'tests/engineering/T02/evidence/r01-integrity.json'


def canary(index):
    return 'github_token: ghp_%s%d\n' % ('R4REVIEW' + 'SYNTHETICNOTAREALKEY' + 'abcdefghij', index)


def scan(tree):
    report = SCRATCH / 'report.json'
    if report.exists():
        report.unlink()
    proc = subprocess.run([GITLEAKS, 'dir', str(tree), '--no-banner', '--redact', '--config', str(CONFIG),
                           '--report-format', 'json', '--report-path', str(report)],
                          capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=ROOT)
    findings = json.loads(report.read_text(encoding='utf-8')) if report.exists() else []
    return proc.returncode, [pathlib.Path(f['File']).resolve().relative_to(tree.resolve()).as_posix()
                             for f in findings]


def old_predicate(finding_paths):
    unexpected = [x for x in finding_paths if x != BLESS]
    return not (unexpected or len(finding_paths) != 6)


def new_predicate(finding_paths):
    """The delivered form: unexpected = list(finding_paths); any finding fails the gate."""
    return not finding_paths


def main():
    out = {}
    scenarios = {'A-noFindings': {}, 'B-oneCanaryInBlessed': {1}, 'C-sixCanariesAllInBlessed': {1, 2, 3, 4, 5, 6}}
    for label, planted in scenarios.items():
        shutil.rmtree(SCRATCH, ignore_errors=True)
        tree = SCRATCH / 'tree'
        tree.mkdir(parents=True)
        for name in (BLESS, 'docs/execution/reports/T02.md', 'tests/engineering/T02/secret_scan.py'):
            target = tree / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        if planted:
            with (tree / BLESS).open('a', encoding='utf-8', newline='\n') as stream:
                for index in sorted(planted):
                    stream.write(canary(index))
        exit_code, finding_paths = scan(tree)
        out[label] = {
            'plantedCanaries': len(planted), 'gitleaksExit': exit_code,
            'findingPaths': sorted(finding_paths),
            'oldAssertionWould': 'PASS' if old_predicate(finding_paths) else 'FAIL',
            'newInvariantWould': 'PASS' if not finding_paths else 'FAIL',
        }
        print(label, json.dumps(out[label], ensure_ascii=False))
    shutil.rmtree(SCRATCH, ignore_errors=True)
    out['scratchRemoved'] = not SCRATCH.exists()
    out['reading'] = ('old predicate passes only for exactly six findings all inside the blessed file; '
                      'scenario C shows six real secrets there still passes it, while the new invariant fails')
    print(json.dumps(out, ensure_ascii=False, indent=2))
    (HERE / 'evidence' / 'c11-j4-t07-gate-semantics.json').write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

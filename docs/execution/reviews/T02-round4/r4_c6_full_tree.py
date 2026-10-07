"""T02 round-4 control C-6: one tree, three configs, end to end (the decisive full-tree numbers).

Copies the same Git-visible input set that tests/engineering/T02/scan_secrets.py uses, then scans it
with three configs in one run so the numbers are comparable:
  delivered    tests/engineering/T02/gitleaks.toml as delivered        -> expected 0 findings, exit 0
  pre-deca2a1  the withdrawn config re-read from git history           -> expected 7 findings, exit 1
  defaults     default rules, no allowlist of any kind                 -> expected 15 findings, exit 1
Also re-checks the frozen records and reports sha256 of every file it copied? No -- it reports the
three finding sets with file and rule, plus the scanner's own byte lines, and writes nothing to the
repository except this review's own evidence file.
"""
import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess

ROOT = pathlib.Path(r'E:\project\codex\wxAgent')
HERE = pathlib.Path(__file__).resolve().parent
GITLEAKS = str(ROOT / '.tools/t02/gitleaks/gitleaks.exe')
parser = argparse.ArgumentParser()
parser.add_argument('--scratch', default=str(pathlib.Path.home() / 'AppData/Local/Temp/t02r4/c6'))
args = parser.parse_args()
SCRATCH = pathlib.Path(args.scratch)

FROZEN = ['tests/engineering/T02/evidence/r01-integrity.json',
          'tests/engineering/T02/evidence/r01-integrity-run.json',
          'tests/engineering/T02/evidence/gitleaks-findings.json',
          'tests/engineering/T02/gitleaks.toml',
          'docs/api/openapi.yaml', 'docs/schemas/editorial.schema.json']


def main():
    shutil.rmtree(SCRATCH, ignore_errors=True)
    tree = SCRATCH / 'tree'
    tree.mkdir(parents=True)
    before = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in FROZEN}
    names = [n.decode('utf-8') for n in subprocess.check_output(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT).split(b'\0') if n]
    copied, bytes_copied = 0, 0
    for name in sorted(set(names)):
        src = ROOT / name
        if src.is_file():
            dst = tree / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            copied += 1
            bytes_copied += dst.stat().st_size
    legacy = SCRATCH / 'pre-deca2a1.toml'
    legacy.write_text(subprocess.run(['git', 'show', 'deca2a1^:tests/engineering/T02/gitleaks.toml'],
                                     capture_output=True, text=True, encoding='utf-8', cwd=ROOT).stdout,
                      encoding='utf-8', newline='\n')
    defaults = SCRATCH / 'defaults-only.toml'
    defaults.write_text('title = "defaults only"\n[extend]\nuseDefault = true\n', encoding='utf-8', newline='\n')

    summary = {'inputSet': {'listed': len(names), 'copiedFiles': copied, 'copiedBytes': bytes_copied}}
    for label, config in (('delivered', ROOT / 'tests/engineering/T02/gitleaks.toml'),
                          ('preDeca2a1', legacy), ('defaults', defaults)):
        report = SCRATCH / (label + '.json')
        proc = subprocess.run([GITLEAKS, 'dir', str(tree), '--redact', '--no-banner', '--config', str(config),
                               '--report-format', 'json', '--report-path', str(report)],
                              capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=ROOT)
        findings = json.loads(report.read_text(encoding='utf-8')) if report.exists() else []
        log = (proc.stdout + proc.stderr).splitlines()
        rel = [pathlib.Path(f['File']).resolve().relative_to(tree.resolve()).as_posix() for f in findings]
        summary[label] = {
            'exit': proc.returncode, 'count': len(findings),
            'byFile': {p: rel.count(p) for p in sorted(set(rel))},
            'rules': sorted({f['RuleID'] for f in findings}),
            'scanned': [l.strip() for l in log if 'bytes' in l][-1:],
            'leaks': [l.strip() for l in log if 'leak' in l.lower()][-1:],
        }
        print('%-11s exit %s  findings %s  %s  %s' % (label, proc.returncode, len(findings),
                                                      summary[label]['scanned'], summary[label]['leaks']))
    after = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in FROZEN}
    summary['frozenUnchanged'] = all(after[p] == before[p] for p in before)
    # line-split records on purpose: writing {"docs/api/openapi.yaml": "<64 hex>"} in this evidence
    # file pairs a path containing 'api' with a long hex token on one line, which is exactly the shape
    # generic-api-key fires on -- the reviewer must not leave an artifact that only the audited value
    # exemptions keep green. Same root cause as F-03, same fix (path and digest on separate lines).
    summary['frozenSha256'] = [{'path': p, 'sha256': after[p]} for p in sorted(after)]
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    (HERE / 'evidence' / 'c6-full-tree-three-configs.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    shutil.rmtree(SCRATCH, ignore_errors=True)
    print('scratch removed:', not SCRATCH.exists())
    return 0 if (summary['delivered']['count'] == 0 and summary['delivered']['exit'] == 0) else 1


if __name__ == '__main__':
    raise SystemExit(main())

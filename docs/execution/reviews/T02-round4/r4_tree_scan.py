"""T02 round-4 reviewer harness: build ONE copy of the Git-visible file set, then scan it
under (a) the delivered config and (b) a defaults-only config with no allowlists at all.

Writes only under $env:TEMP\t02r4 . Nothing in the repository is modified.
Usage: python r4_tree_scan.py [--out <dir>]
"""
import argparse
import json
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(r'E:\project\codex\wxAgent')
HERE = pathlib.Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--gitleaks', default=str(ROOT / '.tools/t02/gitleaks/gitleaks.exe'))
parser.add_argument('--scratch', default=str(pathlib.Path.home() / 'AppData/Local/Temp/t02r4/tree-scan'))
args = parser.parse_args()

scratch = pathlib.Path(args.scratch)
shutil.rmtree(scratch, ignore_errors=True)
tree = scratch / 'tree'
tree.mkdir(parents=True)
defaults = scratch / 'defaults-only.toml'
defaults.write_text('title = "defaults only, no allowlists"\n[extend]\nuseDefault = true\n',
                    encoding='utf-8', newline='\n')

names = [n.decode('utf-8') for n in subprocess.check_output(
    ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT).split(b'\0') if n]
bytes_copied = 0
for name in sorted(set(names)):
    src = ROOT / name
    if src.is_file():
        dst = tree / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        bytes_copied += dst.stat().st_size
print('git-visible files: listed %d, copied %d, bytes %d'
      % (len(names), len({n for n in names if (tree / n).is_file()}), bytes_copied))

summary = {}
for label, config in (('delivered-config', ROOT / 'tests/engineering/T02/gitleaks.toml'),
                      ('defaults-only', defaults)):
    report = scratch / (label + '.report.json')
    if report.exists():
        report.unlink()
    proc = subprocess.run([args.gitleaks, 'dir', str(tree), '--redact', '--no-banner',
                           '--config', str(config), '--report-format', 'json',
                           '--report-path', str(report)],
                          capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=ROOT)
    findings = json.loads(report.read_text(encoding='utf-8')) if report.exists() else []
    log = (proc.stdout + proc.stderr).splitlines()
    summary[label] = {
        'exit': proc.returncode,
        'findingCount': len(findings),
        'rules': sorted({f['RuleID'] for f in findings}),
        'findings': [{'rule': f['RuleID'], 'file': pathlib.Path(f['File']).resolve().relative_to(tree.resolve()).as_posix(),
                      'line': f.get('Line'), 'match': f.get('Match')} for f in findings],
        'scannedLine': [l.strip() for l in log if 'bytes' in l][-1:],
        'errorLines': [l.strip() for l in log if any(k in l.lower() for k in ('error', 'warn'))][:5],
    }
    print('%s: exit %s, findings %s, rules %s, %s'
          % (label, proc.returncode, len(findings), summary[label]['rules'], summary[label]['scannedLine']))

out = HERE / 'evidence' / 'c-tree-scan-summary.json'
out.write_text(json.dumps({'gitVisibleBytes': bytes_copied,
                           'files': len({n for n in names if (tree / n).is_file()}),
                           'scans': summary}, ensure_ascii=False, indent=2) + '\n',
               encoding='utf-8', newline='\n')
print('wrote', out)
shutil.rmtree(scratch, ignore_errors=True)
print('scratch removed:', not scratch.exists())

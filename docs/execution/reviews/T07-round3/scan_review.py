"""Gitleaks scans exactly Git-visible source, including untracked delivery files."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path('E:\\project\\codex\\wxAgent')
parser = argparse.ArgumentParser()
parser.add_argument('--gitleaks', default='gitleaks')
args = parser.parse_args()
work = Path('E:\\project\\codex\\wxAgent\\docs\\execution\\reviews\\T07-round3\\.work')
work.mkdir(exist_ok=True)
files = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT).split(b'\0')
with tempfile.TemporaryDirectory(prefix='secret-scan-', dir=work) as directory:
    destination = Path(directory).resolve()
    assert destination.is_relative_to(work.resolve())
    for name in set(files):
        if not name:
            continue
        relative = Path(name.decode('utf-8'))
        source = ROOT / relative
        if source.is_file():
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    scanner = str(Path(args.gitleaks).resolve()) if '/' in args.gitleaks else args.gitleaks
    report = Path('E:\\project\\codex\\wxAgent\\docs\\execution\\reviews\\T07-round3\\evidence\\gitleaks-findings.json')
    report.parent.mkdir(exist_ok=True)
    result = subprocess.run([scanner, 'dir', str(destination), '--redact', '--no-banner',
                             '--config', str(ROOT / 'tests/engineering/T02/gitleaks.toml'),
                             '--report-format', 'json', '--report-path', str(report)], cwd=ROOT,
                            capture_output=True, text=True, encoding='utf-8', errors='replace')
    print(result.stdout + result.stderr)
    if report.exists():
        print(report.read_text(encoding='utf-8'))
raise SystemExit(result.returncode)

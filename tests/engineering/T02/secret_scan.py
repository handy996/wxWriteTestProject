"""Small offline baseline scan. CI additionally runs Gitleaks; neither proves absence."""
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
patterns = [
    re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(rb'\bAKIA[0-9A-Z]{16}\b'),
    re.compile(rb'\bsk-(?:proj-)?[a-zA-Z0-9_-]{24,}\b'),
    re.compile(rb'\bgh[pousr]_[a-zA-Z0-9]{30,}\b'),
]
paths = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT).split(b'\0')
failures = []
for raw in set(paths):
    if not raw:
        continue
    path = ROOT / raw.decode('utf-8')
    if not path.is_file():
        continue
    data = path.read_bytes()
    if any(pattern.search(data) for pattern in patterns):
        failures.append(path.relative_to(ROOT).as_posix())
print('Secret pattern scan: ' + ('FAILED: ' + ', '.join(failures) if failures else 'no matches'))
sys.exit(bool(failures))

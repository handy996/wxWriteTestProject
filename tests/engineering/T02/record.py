"""Run a command with bounded, reviewable stdout/stderr evidence. No secrets in argv."""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
ROOT = Path(__file__).resolve().parents[3]
parser = argparse.ArgumentParser()
parser.add_argument('--name', required=True)
parser.add_argument('--cwd', default='.')
parser.add_argument('command', nargs=argparse.REMAINDER)
args = parser.parse_args()
command = args.command[1:] if args.command[:1] == ['--'] else args.command
if '/' in command[0] or '\\' in command[0]:
    command[0] = str((ROOT / args.cwd / command[0]).resolve())
try:
    run = subprocess.run(command, cwd=ROOT / args.cwd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    code, output = run.returncode, run.stdout + run.stderr
except FileNotFoundError as error:
    code, output = 127, str(error)
for key, value in os.environ.items():
    if any(part in key.upper() for part in ('PASSWORD', 'TOKEN', 'SECRET', 'API_KEY')) and len(value) >= 8:
        output = output.replace(value, '[REDACTED]')
evidence = ROOT / 'tests/engineering/T02/evidence'
evidence.mkdir(exist_ok=True)
(evidence / (args.name + '.json')).write_text(json.dumps({
    'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'command': command, 'cwd': str((ROOT / args.cwd).resolve()),
    'exitCode': code, 'output': output, 'paidCalls': 0,
}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
print(f'{args.name}: exit {code}')
print(output[-3500:])
sys.exit(code)

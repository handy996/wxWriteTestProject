"""Record independent review checks without replacing author evidence."""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--name', required=True)
parser.add_argument('command', nargs=argparse.REMAINDER)
args = parser.parse_args()
assert Path(args.name).name == args.name
command = args.command[1:] if args.command[:1] == ['--'] else args.command
result = subprocess.run(command, cwd=Path(__file__).resolve().parents[4],
                        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=1200)
record = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'command': command, 'exitCode': result.returncode,
          'stdout': result.stdout, 'stderr': result.stderr}
Path(__file__).with_name(args.name + '.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
print(args.name, 'exit', result.returncode)
print((result.stdout + result.stderr)[-2200:])
raise SystemExit(result.returncode)

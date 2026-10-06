"""One development entry point; requires Python 3.12+ and Docker Compose v2."""
import argparse
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('action', choices=['up', 'down', 'logs'], nargs='?', default='up')
parser.add_argument('--env-file', type=Path, default=ROOT / 'infra/.env',
                    help='Optional isolated environment file (default: infra/.env)')
args = parser.parse_args()
if not shutil.which('docker'):
    sys.exit('Docker with Compose v2 is required. No services were started.')
env_file = args.env_file.resolve()
if args.action == 'up' and not env_file.exists():
    with env_file.open('x', encoding='utf-8') as stream:
        stream.write('APP_PROFILE=mock\nWEB_PORT=8080\n')
        for role in ('ADMIN', 'MIGRATION', 'RUNTIME'):
            stream.write(f'DB_{role}_PASSWORD={secrets.token_hex(24)}\n')
    if os.name != 'nt':
        env_file.chmod(0o600)
command = ['docker', 'compose', '--env-file', str(env_file), '-f', str(ROOT / 'infra/compose.yml')]
operation = {'up': ['up', '-d', '--build'], 'down': ['down'], 'logs': ['logs', '--tail', '100']}[args.action]
result = subprocess.run(command + operation, cwd=ROOT)
if result.returncode:
    sys.exit(result.returncode)
if args.action == 'up':
    config = dict(line.split('=', 1) for line in env_file.read_text(encoding='utf-8').splitlines() if '=' in line and not line.startswith('#'))
    port = os.environ.get('WEB_PORT', config.get('WEB_PORT', '8080'))
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/actuator/health/readiness', timeout=2) as response:
                if response.status == 200:
                    print(f'Engineering preview ready: http://127.0.0.1:{port} (no Provider calls)')
                    break
        except (OSError, urllib.error.HTTPError):
            pass
        time.sleep(1)
    else:
        sys.exit('Readiness failed; inspect with: python backend/scripts/dev.py logs')

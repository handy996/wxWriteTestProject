"""CI uses the delivered Compose topology on an isolated project/volume.

No production deployment. Only this randomly named test project is removed.
"""
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[3]
project = 't02-test-' + uuid.uuid4().hex[:12]
env = dict(os.environ, APP_PROFILE='mock', WEB_PORT='18080')
for role in ('ADMIN', 'MIGRATION', 'RUNTIME'):
    env['DB_' + role + '_PASSWORD'] = secrets.token_hex(24)
base = ['docker', 'compose', '-p', project, '-f', str(ROOT / 'infra/compose.yml')]


def run(*args, expected=0):
    result = subprocess.run(base + list(args), cwd=ROOT, env=env, capture_output=True, text=True, timeout=600)
    # Docker build logs and DB commands contain no credentials; env is never printed.
    print(result.stdout)
    print(result.stderr)
    if expected == 'nonzero':
        assert result.returncode != 0, args
    else:
        assert result.returncode == expected, args
    return result.stdout


def ready():
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen('http://127.0.0.1:18080/actuator/health/readiness', timeout=2) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.HTTPError):
            pass
        time.sleep(1)
    raise TimeoutError('Compose application readiness')


try:
    run('config', '--quiet')
    run('up', '-d', '--build')
    ready()
    with urllib.request.urlopen('http://127.0.0.1:18080/') as response:
        assert 'id="app"' in response.read().decode()
    with urllib.request.urlopen('http://127.0.0.1:18080/actuator/info') as response:
        info = json.load(response)['skeleton']
        assert info['mode'] == 'mock' and not info['paidCallsEnabled']
        assert len(info['capabilities']) == 4 and all(not item['available'] for item in info['capabilities'])
    sql = 'SELECT installed_rank,script,checksum,success FROM editorial_migrations.flyway_schema_history ORDER BY installed_rank'
    history = run('exec', '-T', 'db', 'psql', '-U', 'editorial_admin', '-d', 'editorial', '-Atc', sql)
    run('restart', 'backend')
    ready()
    assert history == run('exec', '-T', 'db', 'psql', '-U', 'editorial_admin', '-d', 'editorial', '-Atc', sql)
    for sql in ('CREATE TABLE editorial.t02_forbidden(id int)',
                'CREATE TEMP TABLE t02_forbidden(id int)',
                'SELECT * FROM editorial_migrations.flyway_schema_history', 'SET ROLE editorial_migrator'):
        run('exec', '-T', 'db', 'psql', '-v', 'ON_ERROR_STOP=1', '-U', 'editorial_runtime', '-d', 'editorial', '-c', sql, expected='nonzero')
    run('run', '--rm', '--no-deps', '-e', 'SPRING_PROFILES_ACTIVE=prod,mock', 'backend', expected='nonzero')
    print('Compose cold start, restart, actual HTTP, permissions, and production/mock guard verified.')
finally:
    run('down', '--volumes', '--remove-orphans')

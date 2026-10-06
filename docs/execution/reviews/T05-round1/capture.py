import hashlib, json, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
def git(*args):
    p = subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    return {'exitCode': p.returncode, 'output': p.stdout, 'stderr': p.stderr}
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
paths = git('ls-files', '--cached', '--others', '--exclude-standard')['output'].splitlines()
files = [{'path': p, 'sha256': sha(ROOT/p)} for p in sorted(set(paths)) if (ROOT/p).is_file() and not p.startswith('docs/execution/reviews/T05-round1/') and p != 'docs/execution/reviews/T05-Review-v1.0.md']
approval = json.loads((ROOT/'docs/execution/reviews/T00-rc3-approval.json').read_text())
checks = [{'path': e['path'], 'expected': e['sha256'], 'actual': sha(ROOT/e['path']), 'match': sha(ROOT/e['path']) == e['sha256']} for e in approval['files']]
checks.append({'path': approval['manifestPath'], 'match': sha(ROOT/approval['manifestPath']) == approval['manifestSha256']})
data = {'head': git('rev-parse', 'HEAD'), 'branch': git('branch', '--show-current'), 'status': git('status', '--short'), 'files': files, 'contracts': checks}
if not (HERE/'before.json').exists():
    (HERE/'before.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
else:
    before = json.loads((HERE/'before.json').read_text(encoding='utf-8'))
    data['changedExisting'] = [e['path'] for e in before['files'] if not (ROOT/e['path']).exists() or sha(ROOT/e['path']) != e['sha256']]
    (HERE/'after.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'files': len(files), 'contracts': len(checks), 'mismatches': [e for e in checks if not e['match']], 'changedExisting': data.get('changedExisting')}))

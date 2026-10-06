"""Check approved contracts and preserve all unrelated/pre-revision deliveries."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

before = json.loads((HERE / 'before.json').read_text(encoding='utf-8'))
allowed = {'backend/src/main/java/com/example/editorial/storage/S3StorageBackend.java', 'backend/src/main/java/com/example/editorial/storage/SigV4.java', 'infra/storage.env.example'}
changed = [item['path'] for item in before
           if not (ROOT / item['path']).is_file() or digest(ROOT / item['path']) != item['sha256']]
unexpected = sorted(set(changed) - allowed)
approved = json.loads((ROOT / 'docs/execution/reviews/T00-rc3-approval.json').read_text(encoding='utf-8'))
assert approved['decision'] == 'PASS' and approved['contractVersion'] == '1.0.0-rc.3'
contracts = {item['path']: item['sha256'] for item in approved['files']}
contracts[approved['manifestPath']] = approved['manifestSha256']
baseline = json.loads((ROOT / 'docs/execution/contracts/baseline.json').read_text(encoding='utf-8'))
contracts.update({'docs/' + name: value for name, value in baseline['sourceHashes'].items()})
contract_failures = [name for name, value in contracts.items() if digest(ROOT / name) != value]

names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT).split(b'\0')
delivery = sorted({item.decode().replace('\\', '/') for item in names if item and (
    item.decode().replace('\\', '/').startswith(('backend/src/main/java/com/example/editorial/storage/',
        'backend/src/test/java/com/example/editorial/storage/')) or
    item.decode().replace('\\', '/') in allowed or
    item.decode().replace('\\', '/') in {'docs/execution/reports/T04-Revision-v2.0.md',
        'tests/engineering/T04/revision2/run_scans.py', 'tests/engineering/T04/revision2/check_integrity.py',
        'tests/engineering/T04/revision2/verify.py', 'tests/engineering/T04/revision2/before-fix.json',
        'tests/engineering/T04/revision2/after-fix.json'})})
result = dict(originalFiles=len(before), changedOriginalFiles=changed, unexpectedChanges=unexpected,
              approvedContractFiles=len(contracts), contractFailures=contract_failures,
              delivery=[dict(path=name, sha256=digest(ROOT / name)) for name in delivery])
(HERE / 'integrity.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps({key: value for key, value in result.items() if key != 'delivery'}))
raise SystemExit(1 if unexpected or contract_failures else 0)

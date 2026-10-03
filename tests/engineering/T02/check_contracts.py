"""Read-only verification of the exact approved T00 files (never regenerate)."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def verify():
    approval = json.loads((ROOT / 'docs/execution/reviews/T00-rc3-approval.json').read_text(encoding='utf-8'))
    assert approval['decision'] == 'PASS'
    assert approval['contractVersion'] == '1.0.0-rc.3'
    expected = {item['path']: item['sha256'] for item in approval['files']}
    expected[approval['manifestPath']] = approval['manifestSha256']
    baseline = json.loads((ROOT / 'docs/execution/contracts/baseline.json').read_text(encoding='utf-8'))
    expected.update({'docs/' + name: value for name, value in baseline['sourceHashes'].items()})
    for name, value in expected.items():
        actual = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        if actual != value:
            raise ValueError(f'Approved baseline changed: {name}')
    print(f'Approved T00 rc.3: {len(expected)} hashes verified, no regeneration')


if __name__ == '__main__':
    verify()

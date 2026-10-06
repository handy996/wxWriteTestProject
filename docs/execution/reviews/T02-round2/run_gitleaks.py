"""Use the delivered scanner/config; redirect only its findings file."""
from pathlib import Path

root = Path(__file__).resolve().parents[4]
path = root / 'tests/engineering/T02/scan_secrets.py'
source = path.read_text(encoding='utf-8').replace(
    'tests/engineering/T02/evidence/gitleaks-findings.json',
    'docs/execution/reviews/T02-round2/gitleaks-findings.json')
exec(compile(source, str(path), 'exec'), {'__name__': '__main__', '__file__': str(path)})

"""Unmodified delivered checks; redirect evidence to this review directory."""
from pathlib import Path

root = Path(__file__).resolve().parents[4]
path = root / 'tests/engineering/T02/integration.py'
source = path.read_text(encoding='utf-8')
old = "output = ROOT / 'tests/engineering/T02/evidence' / (args.evidence_name + '.json')"
assert source.count(old) == 1
source = source.replace(old, "output = ROOT / 'docs/execution/reviews/T02-round2' / (args.evidence_name + '.json')")
exec(compile(source, str(path), 'exec'), {'__name__': '__main__', '__file__': str(path)})

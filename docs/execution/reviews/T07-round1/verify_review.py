"""Reuse read-only delivery checks against reviewer-owned execution evidence."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
source=(ROOT/'tests/engineering/T07/verify_delivery.py').read_text(encoding='utf-8')
source=source.replace('Path(__file__).resolve().parents[3]', 'Path('+repr(str(ROOT))+')')
for filename in ['t06-extension.patch','composition-root.patch','evidence/input-baseline.json']:
    source=source.replace("HERE/'"+filename+"'", "ROOT/'tests/engineering/T07/"+filename+"'")
exec(compile(source,'redirected-read-only-T07-verifier','exec'),{'__file__':__file__,'__name__':'__main__'})

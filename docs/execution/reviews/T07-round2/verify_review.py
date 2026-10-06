"""Check current review run; migration evidence is explicitly reused from independent round 1."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
source=(ROOT/'tests/engineering/T07/verify_delivery.py').read_text(encoding='utf-8')
source=source.replace('Path(__file__).resolve().parents[3]', 'Path('+repr(str(ROOT))+')')
for filename in ['t06-extension.patch','composition-root.patch','evidence/input-baseline.json']:
    source=source.replace("HERE/'"+filename+"'", "ROOT/'tests/engineering/T07/"+filename+"'")
old="e=json.loads((HERE/'evidence'/(name+'.json')).read_text(encoding='utf-8'))"
new="e=json.loads(((ROOT/'docs/execution/reviews/T07-round1/evidence/upgrade.json') if name=='prior-upgrade' else (HERE/'evidence'/(name+'.json'))).read_text(encoding='utf-8'))"
assert old in source
source=source.replace(old,new)
exec(compile(source,'redirected-read-only-T07-round2-verifier','exec'),{'__file__':__file__,'__name__':'__main__'})

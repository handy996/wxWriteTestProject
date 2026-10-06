"""Run current integration in review-owned directories; original regression source stays untouched."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/engineering/T07'))
source=(ROOT/'tests/engineering/T07/integration.py').read_text(encoding='utf-8')
source=source.replace('Path(__file__).resolve().parents[3]', 'Path('+repr(str(ROOT))+')')
for file in ['migration-draft.sql','VersionIntegration.java']:
    source=source.replace("HERE / '"+file+"'", "ROOT / 'tests/engineering/T07/"+file+"'")
namespace={'__file__':__file__,'__name__':'review_harness'}
exec(compile(source,'redirected-T07-round2-harness','exec'),namespace)
raise SystemExit(namespace['main']())

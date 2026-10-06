"""Independent evidence for current T06, preserving all earlier review runs."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[4]; HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tests/engineering/T06'))
source=(ROOT/'tests/engineering/T06/integration.py').read_text(encoding='utf-8')
source=source.replace('ROOT = Path(__file__).resolve().parents[3]', 'ROOT = Path('+repr(str(ROOT))+')')
for name in ['migration-draft.sql','ArticleIntegration.java']:
    source=source.replace("HERE / '"+name+"'", "ROOT / 'tests/engineering/T06/"+name+"'")
needle="        # T03's shared-integration.patch is corrupt"
injection='''        test = work / 'backend/src/test/java/com/example/editorial/article/job/T06PostgresTest.java'
        content = test.read_text(encoding='utf-8').replace('tests/engineering/T06/evidence/article-', 'docs/execution/reviews/T06-round4/evidence/article-')
        test.write_text(content, encoding='utf-8')
'''
assert needle in source
source=source.replace(needle,injection+needle)
(HERE/'evidence').mkdir(exist_ok=True)
namespace={'__file__':__file__,'__name__':'review_harness'}
exec(compile(source,'redirected-T06-harness','exec'),namespace)
raise SystemExit(namespace['main']())

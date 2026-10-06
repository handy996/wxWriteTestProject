"""Run T06's isolated harness with review-only evidence and regression cases."""
from pathlib import Path
import hashlib, json, subprocess, sys
ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
AUTHOR = ROOT / 'tests/engineering/T06'
sys.path.insert(0, str(AUTHOR))
source = (AUTHOR / 'integration.py').read_text(encoding='utf-8')
source = source.replace('ROOT = Path(__file__).resolve().parents[3]', 'ROOT = Path(' + repr(str(ROOT)) + ')')
for name in ['migration-draft.sql', 'ArticleIntegration.java']:
    source = source.replace("HERE / '" + name + "'", "ROOT / 'tests/engineering/T06/" + name + "'")
needle = "        # T03's shared-integration.patch is corrupt"
injection = '''        test = work / 'backend/src/test/java/com/example/editorial/article/job/T06PostgresTest.java'
        content = test.read_text(encoding='utf-8').replace('tests/engineering/T06/evidence/article-', 'docs/execution/reviews/T06-round1/evidence/article-')
        test.write_text(content, encoding='utf-8')
        shutil.copyfile(HERE / 'ReviewArticleAstTest.java', work / 'backend/src/test/java/com/example/editorial/article/ast/ReviewArticleAstTest.java')
'''
assert needle in source
source = source.replace(needle, injection + needle)
if '--regression' in sys.argv:
    sys.argv.remove('--regression')
    source = source.replace('T06PostgresTest,ArticleAstTest,DeletionHandoffTest,CanonicalRequestTest', 'ReviewArticleAstTest')
(HERE / 'evidence').mkdir(exist_ok=True)
namespace = {'__file__':str(HERE / 'run_review.py'), '__name__':'review_harness'}
exec(compile(source, 'redirected-T06-harness', 'exec'), namespace)
raise SystemExit(namespace['main']())

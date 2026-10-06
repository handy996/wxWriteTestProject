"""Keep round-one evidence immutable; run current T06 plus unchanged original regressions."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
source = (HERE.parent/'T06-round1/run_review.py').read_text(encoding='utf-8')
source = source.replace('docs/execution/reviews/T06-round1/evidence/article-', 'docs/execution/reviews/T06-round2/evidence/article-')
source = source.replace("HERE / 'ReviewArticleAstTest.java'", "HERE.parent / 'T06-round1/ReviewArticleAstTest.java'")
source = source.replace("source = source.replace(needle, injection + needle)", """injection += \"        shutil.copyfile(HERE / 'ReviewNestedClosureTest.java', work / 'backend/src/test/java/com/example/editorial/article/ast/ReviewNestedClosureTest.java')\\n\"
source = source.replace(needle, injection + needle)
source = source.replace('T06PostgresTest,ArticleAstTest,DeletionHandoffTest,CanonicalRequestTest', 'T06PostgresTest,ArticleAstTest,DeletionHandoffTest,CanonicalRequestTest,ReviewArticleAstTest')""")
exec(compile(source, 'round2-review-harness', 'exec'), {'__file__':__file__, '__name__':'__main__'})

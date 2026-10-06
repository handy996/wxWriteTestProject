"""Review-owned isolation and evidence; no author files are modified."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[4]; HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tests/engineering/T07'))
source=(ROOT/'tests/engineering/T07/integration.py').read_text(encoding='utf-8')
source=source.replace('Path(__file__).resolve().parents[3]', 'Path('+repr(str(ROOT))+')')
for file in ['migration-draft.sql','VersionIntegration.java']:
    source=source.replace("HERE / '"+file+"'", "ROOT / 'tests/engineering/T07/"+file+"'")
needle="        # T03's shared-integration.patch is corrupt"
source=source.replace(needle,"        shutil.copyfile(HERE/'ReviewVersionBoundaryTest.java',work/'backend/src/test/java/com/example/editorial/article/version/ReviewVersionBoundaryTest.java')\n"+needle)
if '--regression' in sys.argv:
    sys.argv.remove('--regression')
    source=source.replace("tests = 'T07UpgradeTest' if args.upgrade_only else 'T07PostgresTest,T07UnavailableTest,VersionDiffTest,T06PostgresTest,ArticleAstTest,DeletionHandoffTest,CanonicalRequestTest'", "tests = 'ReviewVersionBoundaryTest#review*'")
namespace={'__file__':__file__,'__name__':'review_harness'}
exec(compile(source,'redirected-T07-harness','exec'),namespace)
raise SystemExit(namespace['main']())

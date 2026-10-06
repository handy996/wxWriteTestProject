"""Redirect the reviewed T05 integration harness to independent evidence; do not alter shared source."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
source=(ROOT/'tests/engineering/T05/integration.py').read_text(encoding='utf-8')
source=source.replace('ROOT = Path(__file__).resolve().parents[3]', 'ROOT = Path('+repr(str(ROOT))+')')
source=source.replace("HERE / 'migration-draft.sql'", "ROOT / 'tests/engineering/T05/migration-draft.sql'")
needle="        # T03's shared-integration.patch is corrupt"
source=source.replace(needle,"""        shutil.copyfile(HERE / 'ReviewExportSamplesTest.java', work / 'backend/src/test/java/com/example/editorial/editorial/skill/ReviewExportSamplesTest.java')
        shutil.copyfile(HERE / 'ReviewMigrationUpgradeTest.java', work / 'backend/src/test/java/com/example/editorial/editorial/skill/ReviewMigrationUpgradeTest.java')
"""+needle)
source=source.replace('PromptContractTest,CursorCodecTest,SkillConfigDiffTest', 'PromptContractTest,CursorCodecTest,SkillConfigDiffTest,ReviewExportSamplesTest')
if '--upgrade-only' in sys.argv:
    sys.argv.remove('--upgrade-only')
    source=source.replace('-Dtest=T05PostgresTest,SemVerTest,HashingTest,JsonSchemaSkillConfigTest,BaselineResourcesTest,PromptContractTest,CursorCodecTest,SkillConfigDiffTest,ReviewExportSamplesTest','-Dtest=ReviewMigrationUpgradeTest')
source=source.replace("    finally:\n        reports", """    finally:
        samples = work / 'backend/target/review-model-samples.json'
        if samples.exists(): shutil.copyfile(samples, HERE / 'model-samples.json')
        test = work / 'backend/src/test/java/com/example/editorial/editorial/skill/T05PostgresTest.java'
        if test.exists(): shutil.copyfile(test, HERE / (args.evidence_name + '-ExecutedT05PostgresTest.java'))
        reports""")
namespace={'__file__':str(HERE/'run_review.py'),'__name__':'independent_review'}
exec(compile(source,'redirected-author-harness','exec'),namespace)
raise SystemExit(namespace['main']())

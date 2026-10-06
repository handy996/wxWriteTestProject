"""Run T05 author's reviewed harness with outputs redirected and independent cases in an isolated copy."""
import json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
os.environ['PATH'] = str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd') + os.pathsep + os.environ['PATH']
source = (ROOT/'tests/engineering/T05/integration.py').read_text(encoding='utf-8')
source = source.replace("ROOT = Path(__file__).resolve().parents[3]", "ROOT = Path(" + repr(str(ROOT)) + ")")
source = source.replace("HERE / 'migration-draft.sql'", "ROOT / 'tests/engineering/T05/migration-draft.sql'")
source = source.replace("'test', '-Dtest=T05PostgresTest'", "'clean', 'test', '-Dtest=T05PostgresTest,SemVerTest,HashingTest,JsonSchemaSkillConfigTest,BaselineResourcesTest'")
needle = "        # T03's shared-integration.patch is corrupt"
injection = '''        test_path = work / 'backend/src/test/java/com/example/editorial/editorial/skill/T05PostgresTest.java'
        original = test_path.read_text(encoding='utf-8')
        extra = (HERE / 'ReviewCases.java').read_text(encoding='utf-8')
        pos = original.rfind('}')
        test_path.write_text(original[:pos] + extra + original[pos:], encoding='utf-8')
'''
assert needle in source
source = source.replace(needle, injection + needle)
source = source.replace("    finally:\n        if started:", """    finally:
        reports = work / 'backend/target/surefire-reports'
        if reports.exists():
            shutil.copytree(reports, HERE / 'test-results', dirs_exist_ok=True)
        evidence['isolatedWork'] = str(work)
        if started:""")
namespace = {'__file__': str(HERE/'run_review.py'), '__name__': 'review_harness'}
exec(compile(source, 'T05-harness-redirected', 'exec'), namespace)
raise SystemExit(namespace['main']())

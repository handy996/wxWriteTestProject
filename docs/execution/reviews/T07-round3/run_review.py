"""Review current integrated sources; retain prior tests and inject independent boundary tests."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
source=(ROOT/'tests/engineering/integration/formal.py').read_text(encoding='utf-8')
source=source.replace('Path(__file__).resolve().parents[3]', 'Path('+repr(str(ROOT))+')')
needle='        # Exercise the packaged global V1'
assert needle in source
source=source.replace(needle,"        if not args.upgrade_only:\n            for name in ['ReviewDiffPageTest.java','ReviewDiffHttpTest.java']:\n                shutil.copyfile(HERE/name,work/'backend/src/test/java/com/example/editorial/article/version'/name)\n"+needle)
needle="tests += ',T07RevisionBoundaryTest#revision*'"
assert needle in source
source=source.replace(needle,needle+"\n            tests += ',ReviewDiffPageTest#review*,ReviewDiffHttpTest#review*'")
namespace={'__file__':__file__,'__name__':'review_runner'}
exec(compile(source,'review-integrated-T07-runner','exec'),namespace)
raise SystemExit(namespace['main']())

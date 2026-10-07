"""T08 round-4 reviewer probe runner (independent review, no controlled source touched).

What it does:
  1. copies the repository's backend/ into an isolated scratch tree (target/ excluded),
  2. appends the reviewer's probe test methods (evidence/r4_probe_methods.java) into the COPY of
     T08PostgresTest.java only, before its final closing brace,
  3. runs the shipped tests/engineering/T08/run_pg.py against that copy by monkeypatching its
     ROOT/HERE/MIGRATIONS module globals, so the cluster, the build and the evidence all stay outside
     the repository's controlled paths (evidence lands in this review directory),
  4. runs only the r4Probe* methods through Surefire's method filter.

Nothing in backend/ or tests/ is modified. Maven is invoked only through run_pg.py's isolated copy,
never against the shared backend/target.
"""

import importlib.util
import re
import shutil
import sys
from pathlib import Path

REPO = Path(r"E:/project/codex/wxAgent")
HERE = Path(__file__).resolve().parent            # docs/execution/reviews/T08-round4/evidence
REVIEW_DIR = HERE.parent                            # docs/execution/reviews/T08-round4
SCRATCH = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"C:/Users/eie04/AppData/Local/Temp/t08r4/scratch")
METHODS = sys.argv[2] if len(sys.argv) > 2 else "all"

if str(REPO / "tests/engineering/T08") not in sys.path:
    sys.path.insert(0, str(REPO / "tests/engineering/T08"))
sys.dont_write_bytecode = True

# --- 1 + 2: isolated copy of backend with the probe appended -------------------------------
if SCRATCH.exists():
    shutil.rmtree(SCRATCH)
backend = SCRATCH / "backend"
SCRATCH.mkdir(parents=True)
shutil.copytree(REPO / "backend", backend, ignore=shutil.ignore_patterns("target", ".work"))
test_file = backend / "src/test/java/com/example/editorial/cost/T08PostgresTest.java"
source = test_file.read_text(encoding="utf-8")
probe = (HERE / "r4_probe_methods.java").read_text(encoding="utf-8")
cut = source.rstrip()
assert cut.endswith("}"), "unexpected T08PostgresTest ending"
test_file.write_text(cut[:-1] + probe + "\n}\n", encoding="utf-8", newline="\n")

# --- 3: run the shipped runner against the copy ---------------------------------------------
spec = importlib.util.spec_from_file_location("r4_run_pg", REPO / "tests/engineering/T08/run_pg.py")
run_pg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_pg)
tools = REPO / ".tools/t02"
run_pg.ROOT = SCRATCH
run_pg.HERE = REVIEW_DIR
run_pg.MIGRATIONS = SCRATCH / "backend/src/main/resources/db/migration"

names = re.findall(r"void (r4Probe\w+)\(", probe)
selected = names if METHODS == "all" else [n for n in names if METHODS in n]
argv = ["run_pg.py",
        "--pg-bin", str(tools / "postgresql-full/pgsql/bin"),
        "--java-home", str(tools / "jdk-21.0.12.1+1"),
        "--maven", str(tools / "apache-maven-3.9.11/bin/mvn.cmd"),
        "--m2", str(tools / "m2"),
        "--work-root", str(SCRATCH / ".work"),
        "--evidence-name", sys.argv[3] if len(sys.argv) > 3 else "r4-probe-cross-model",
        "--expect-tests", str(len(selected)),
        "--tests", "T08PostgresTest#" + "+".join(selected)]
print("probe methods: " + ", ".join(selected), flush=True)
sys.argv = argv
status = None
try:
    status = run_pg.main()
except BaseException as failure:            # the suite-name gate below rejects a method filter on purpose
    print("runner raised: " + type(failure).__name__ + ": " + str(failure), flush=True)
print("run_pg exit=" + str(status), flush=True)

# --- 4: read the Surefire originals straight out of the isolated run directory ---------------
import xml.etree.ElementTree as ET

runs = sorted((SCRATCH / ".work").glob("*/backend/target/surefire-reports/TEST-*.xml"))
if not runs:
    print("NO SUREFIRE XML FOUND under " + str(SCRATCH / ".work"), flush=True)
    raise SystemExit(2)
report = runs[-1]
root = ET.parse(report).getroot()
print("surefire: " + report.as_posix(), flush=True)
print("suite tests=%s failures=%s errors=%s skipped=%s" % (root.get("tests"), root.get("failures"),
                                                           root.get("errors"), root.get("skipped")), flush=True)
for case in root.iter("testcase"):
    bad = [child for child in case if child.tag in {"failure", "error"}]
    print(("  FAIL " if bad else "  pass ") + case.get("name"), flush=True)
    for child in bad:
        text = (child.get("message") or "") + " || " + (child.text or "")
        print("       " + re.sub(r"\s+", " ", text)[:600], flush=True)

"""T08 round-4 reviewer: F-07's behavioural half — a FULL 57-case round with a RELATIVE --work-root.

Round-3 finding F-07 was: a relative root made all 14 recorded commands exit 0, Surefire report the suite
green, and only then did the finally block's ``relative_to(ROOT)`` throw — exit 1 with no evidence. Round-3
claims it fixed (resolve up front + ``inside_repo``) and delivered `r10-pg-relative-work-root.json`.

Two practical wrinkles measured on the way:
  * ``run_pg.py:389`` hard-codes the evidence directory to its own ``HERE/'evidence'`` (finding F-R4-12), so
    HERE is re-pointed at this review directory — the controlled evidence directory is not written to;
  * as of 03:09 this working tree also holds another session's untracked, currently non-compiling
    ``backend/src/test/java/com/example/editorial/identity/T03Probe*Test.java``. ``run_pg.py`` copies
    ``backend/`` verbatim, so a whole-tree testCompile fails on that foreign file — unrelated to T08. The
    copy used here excludes those two untracked files (the originals are untouched); nothing else is removed.
"""
import importlib.util
import shutil
import sys
from pathlib import Path

REPO = Path(r"E:/project/codex/wxAgent")
SCRATCH = Path(r"C:/Users/eie04/AppData/Local/Temp/t08r4-rel")
tools = REPO / ".tools/t02"
sys.dont_write_bytecode = True

if SCRATCH.exists():
    shutil.rmtree(SCRATCH)
(SCRATCH / "backend").mkdir(parents=True)
shutil.copytree(REPO / "backend", SCRATCH / "backend", shallow=False,
                ignore=shutil.ignore_patterns("target", ".work"))
dropped = []
for name in ("T03ProbeTest.java", "T03Probe2Test.java"):
    path = SCRATCH / "backend/src/test/java/com/example/editorial/identity" / name
    if path.exists():
        path.unlink()
        dropped.append(name)
print("excluded from the copy (untracked, foreign, non-compiling): " + str(dropped), flush=True)

spec = importlib.util.spec_from_file_location("r4_run_pg_rel", REPO / "tests/engineering/T08/run_pg.py")
run_pg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_pg)
run_pg.ROOT = SCRATCH                                    # build/cluster happen outside the repository
run_pg.HERE = REPO / "docs/execution/reviews/T08-round4"  # evidence lands in the review directory
run_pg.MIGRATIONS = SCRATCH / "backend/src/main/resources/db/migration"

# The --work-root itself is deliberately RELATIVE, resolved against the repository root as CWD.
relative = "tmp-r4-rel-workroot"
sys.argv = ["run_pg.py", "--work-root", relative,
            "--pg-bin", str(tools / "postgresql-full/pgsql/bin"), "--java-home", str(tools / "jdk-21.0.12.1+1"),
            "--maven", str(tools / "apache-maven-3.9.11/bin/mvn.cmd"), "--m2", str(tools / "m2"),
            "--evidence-name", "r4-relative-work-root", "--expect-tests", "57"]
status = None
try:
    status = run_pg.main()
except BaseException as raised:
    print("runner raised: " + type(raised).__name__ + ": " + str(raised)[:200], flush=True)
print("RELATIVE --work-root full round exit=" + str(status), flush=True)

"""T08 round-4 reviewer: F-07's behavioural half — a FULL 57-case round driven by a RELATIVE --work-root.

Round-3 finding F-07: with a relative root all 14 recorded commands exited 0 and Surefire reported the suite
green, and only then did the finally block call ``relative_to(ROOT)`` — exit 1, no evidence. Round-3 claims
``resolve_work_root`` now absolutises up front and evidence display goes through ``inside_repo``.

How this run is kept outside the controlled paths:
  * process CWD is a temp directory, so the literal RELATIVE value ``r4-rel-workroot`` resolves there;
  * ``run_pg.py:389`` hard-codes the evidence directory as its own ``HERE/'evidence'`` (finding F-R4-12), so
    HERE is re-pointed at this review directory — nothing is written into ``tests/engineering/T08/evidence``;
  * ROOT is re-pointed at a pruned copy of backend/: as of 03:09 this working tree also contains another
    session's UNTRACKED, currently non-compiling ``identity/T03Probe*Test.java`` (missing PropertySource
    import), and ``run_pg.py`` copies ``backend/`` verbatim, so a whole-tree testCompile fails on that
    foreign file. Those two files are excluded from MY COPY only — the originals are untouched.
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
SCRATCH.mkdir(parents=True)
shutil.copytree(REPO / "backend", SCRATCH / "backend", ignore=shutil.ignore_patterns("target", ".work"))
dropped = []
for name in ("T03ProbeTest.java", "T03Probe2Test.java"):
    path = SCRATCH / "backend/src/test/java/com/example/editorial/identity" / name
    if path.exists():
        path.unlink()
        dropped.append(name)
print("excluded from my copy (foreign, untracked, non-compiling): " + str(dropped), flush=True)

spec = importlib.util.spec_from_file_location("r4_run_pg_rel", REPO / "tests/engineering/T08/run_pg.py")
run_pg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_pg)
run_pg.ROOT = SCRATCH
run_pg.HERE = REPO / "docs/execution/reviews/T08-round4"
run_pg.MIGRATIONS = SCRATCH / "backend/src/main/resources/db/migration"

sys.argv = ["run_pg.py", "--work-root", "r4-rel-workroot",          # RELATIVE, resolved against CWD=temp
            "--pg-bin", str(tools / "postgresql-full/pgsql/bin"), "--java-home", str(tools / "jdk-21.0.12.1+1"),
            "--maven", str(tools / "apache-maven-3.9.11/bin/mvn.cmd"), "--m2", str(tools / "m2"),
            "--evidence-name", "r4-relative-workroot-round2", "--expect-tests", "57"]
code = run_pg.main()
print("RELATIVE --work-root full round exit=" + str(code), flush=True)
print("workRoot seen by evidence: " + str((SCRATCH / "r4-rel-workroot").exists()), flush=True)

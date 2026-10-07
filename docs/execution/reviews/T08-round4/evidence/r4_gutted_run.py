"""T08 round-4 reviewer: does a gutted/weakened copy still run green AND still pass the shipped gates?

This is the combination the static probes alone cannot answer. For a named case it:
  1. copies backend/ into %TEMP%\\t08r4\\gut-<case> (never the repository, never backend/target),
  2. applies one reviewer rewrite there,
  3. runs the shipped tests/engineering/T08/verify.py with its module-level paths re-pointed at that copy,
  4. runs the shipped run_pg.py against that copy on the real cluster (57 cases),
  5. prints both results.

A case that is GREEN on the gates and GREEN on the cluster is a weakening the deliverable cannot see.
"""
import importlib.util
import re
import shutil
import sys
from pathlib import Path

REPO = Path(r"E:/project/codex/wxAgent")
sys.dont_write_bytecode = True
CASE = sys.argv[1] if len(sys.argv) > 1 else "A5"
SCRATCH = Path(r"C:/Users/eie04/AppData/Local/Temp/t08r4") / ("gut-" + CASE)
TOOLS = REPO / ".tools/t02"

UNIT_CASE = "quotaWrittenAsNestedYamlBindsTheScopeTheLookupReads"
LIVE_CASE = "nestedYamlQuotaIsEnforcedByTheService"

LIVE_LOADER = """        MockEnvironment env = new MockEnvironment();
        for (PropertySource<?> source : new YamlPropertySourceLoader().load("t08-quota",
                new ByteArrayResource(document.getBytes(java.nio.charset.StandardCharsets.UTF_8)))) {
            env.getPropertySources().addLast(source);
        }
        service(BudgetPolicyConfig.from(env));"""

FLAT_KEYS = """        MockEnvironment env = new MockEnvironment();
        env.setProperty("editorial.cost.max-calls-per-article", "1000");
        env.setProperty("editorial.cost.image-units-per-article", "100");
        env.setProperty("editorial.cost.reconciliation-stale-minutes", "30");
        env.setProperty("editorial.cost.provider-quota.unconfigured", "refuse");
        env.setProperty("editorial.cost.provider-quota.mock-provider.max-concurrent", "4");
        env.setProperty("editorial.cost.provider-quota.mock-provider.calls-per-day", "26");
        env.setProperty("editorial.cost.provider-quota.mock-provider.mock-gpt.max-concurrent", "1");
        env.setProperty("editorial.cost.provider-quota.mock-provider.mock-gpt.calls-per-day", "9");
        service(BudgetPolicyConfig.from(env));"""

REWRITES = {
    # the nested YAML document stays in the case body as a string, but NOTHING loads it any more: the policy
    # the service is fed comes from hand-written flat keys. The case still asserts 4/26/1/9 and still passes.
    "A5": ("src/test/java/com/example/editorial/cost/T08PostgresTest.java",
           [(LIVE_LOADER, "        // (decorative) new YamlPropertySourceLoader() +"
            " new ByteArrayResource(document.getBytes(...)) -> BudgetPolicyConfig.from(env)\n" + FLAT_KEYS)]),
    # the lock ordering the report calls "排序后一次锁齐" disappears: locks are taken in construction order
    "B1": ("src/main/java/com/example/editorial/cost/BudgetService.java",
           [("        ceilings.sort(Comparator.comparing(Ceiling::lockKey));\n", "")]),
    # the env branch stops refusing an unknown leaf and skips it silently
    "B3": ("src/main/java/com/example/editorial/cost/BudgetPolicyConfig.java",
           [('            leafParts = 2;\n        } else {\n'
             '            throw new PublicFailure(503, "INVALID_PROVIDER_QUOTA_KEY");',
             '            leafParts = 2;\n        } else {\n            return;')]),
    # the provider day count treats callsPerDay==0 as "no limit" instead of "the day is closed"
    "B7": ("src/main/java/com/example/editorial/cost/BudgetService.java",
           [("if (used.counter(BudgetPolicy.Counter.CALLS) + 1 > quota.callsPerDay())",
             "if (quota.callsPerDay() != 0 && used.counter(BudgetPolicy.Counter.CALLS) + 1 > "
             "quota.callsPerDay())")]),
    # the two quota windows are handed each other's SQL window definition
    "B2": ("src/main/java/com/example/editorial/cost/BudgetService.java",
           [('"l.owner_id=? AND l.provider=? AND l.model=? AND l.bucket_day=?"', "r4PLACEHOLDERr4"),
            ('"l.owner_id=? AND l.provider=? AND l.bucket_day=?"',
             '"l.owner_id=? AND l.provider=? AND l.model=? AND l.bucket_day=?"'),
            ("r4PLACEHOLDERr4", '"l.owner_id=? AND l.provider=? AND l.bucket_day=?"')]),
    # concurrency off-by-one: the (N+1)-th live hold is admitted
    "B4": ("src/main/java/com/example/editorial/cost/BudgetService.java",
           [("if (used.holds() >= quota.maxConcurrent())", "if (used.holds() > quota.maxConcurrent())")]),
}

if CASE not in REWRITES:
    raise SystemExit("unknown case " + CASE)
relative, edits = REWRITES[CASE]

if SCRATCH.exists():
    shutil.rmtree(SCRATCH)
SCRATCH.mkdir(parents=True)
shutil.copytree(REPO / "backend", SCRATCH / "backend", ignore=shutil.ignore_patterns("target", ".work"))
target = SCRATCH / "backend" / Path(relative.replace("/", "\\"))
text = target.read_text(encoding="utf-8")
for old, new in edits:
    assert old in text, "rewrite target missing for " + CASE
    text = text.replace(old, new)
target.write_text(text, encoding="utf-8", newline="\n")
print("case " + CASE + " rewritten in " + SCRATCH.as_posix(), flush=True)


def load(name: str, path: Path):
    found = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(found)
    found.loader.exec_module(module)
    return module


# --- 3: the shipped static gates, with ONLY the rewritten file re-pointed at the copy ---------
verify = load("r4_verify_gut", REPO / "tests/engineering/T08/verify.py")
if "test/java" in relative:
    verify.COST_TEST = SCRATCH / "backend/src/test/java/com/example/editorial/cost"
    verify.PG_TEST = verify.COST_TEST / "T08PostgresTest.java"
else:
    verify.COST_MAIN = SCRATCH / "backend/src/main/java/com/example/editorial/cost"
    verify.CONFIG_JAVA = verify.COST_MAIN / "BudgetPolicyConfig.java"
    for name in ("BudgetService", "BudgetPolicy", "BudgetPolicyConfig", "CostLedger"):
        pass  # cost_sources() globs COST_MAIN, so the rewritten main file is picked up with its siblings
red = [(name, detail) for name, ok, detail in verify.run_checks() if not ok]
print("GATES on the rewritten copy: " + ("ALL 14 GREEN" if not red else str([n for n, _ in red])), flush=True)
for name, detail in red:
    print("   RED " + name + " :: " + detail[:300], flush=True)

# --- 4: the shipped cluster runner against the rewritten copy ---------------------------------
run_pg = load("r4_run_pg_gut", REPO / "tests/engineering/T08/run_pg.py")
run_pg.ROOT = SCRATCH
run_pg.HERE = REPO / "docs/execution/reviews/T08-round4"
run_pg.MIGRATIONS = SCRATCH / "backend/src/main/resources/db/migration"
sys.argv = ["run_pg.py", "--pg-bin", str(TOOLS / "postgresql-full/pgsql/bin"), "--java-home",
            str(TOOLS / "jdk-21.0.12.1+1"), "--maven", str(TOOLS / "apache-maven-3.9.11/bin/mvn.cmd"),
            "--m2", str(TOOLS / "m2"), "--work-root", str(SCRATCH / ".work"),
            "--evidence-name", "r4-gutted-" + CASE, "--expect-tests", "57"]
print("CLUSTER: running the delivered 57 cases against the rewritten copy ...", flush=True)
try:
    code = run_pg.main()
except BaseException as raised:               # run_pg raises when a recorded command failed
    print("CLUSTER raised: " + type(raised).__name__ + ": " + str(raised)[:200], flush=True)
    code = "raised"
print("CLUSTER run_pg exit=" + str(code), flush=True)

runs = sorted((SCRATCH / ".work").glob("*/backend/target/surefire-reports/TEST-*.xml"))
import xml.etree.ElementTree as ET
for report in runs:
    root = ET.parse(report).getroot()
    print("surefire " + Path(report).name + " tests=%s failures=%s errors=%s skipped=%s"
          % (root.get("tests"), root.get("failures"), root.get("errors"), root.get("skipped")), flush=True)
    for case in root.iter("testcase"):
        bad = [child for child in case if child.tag in {"failure", "error"}]
        if bad:
            print("   FAIL " + case.get("name") + " :: "
                  + re.sub(r"\s+", " ", (bad[0].get("message") or bad[0].text or ""))[:300], flush=True)

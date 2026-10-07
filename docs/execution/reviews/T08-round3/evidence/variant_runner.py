#!/usr/bin/env python3
"""T08 round-3 reviewer: run deliberately WRONG implementations of the provider-quota window semantics against
the real 49-case suite (unit + live PostgreSQL), each in its own copy of the backend under .work.

Nothing here writes to a tracked path: every variant is a fresh copy of ``backend/`` plus a copy of the runner
into ``.work/t08/r3-variants/<name>/``, mutated in that copy only. The cluster, the build directory and the
evidence all stay under .work.

Usage:
    python docs/execution/reviews/T08-round3/evidence/variant_runner.py V1 V2 V3 V4 V6 P1
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path("E:/project/codex/wxAgent")
PY = Path(sys.executable)
WORK = ROOT / ".work/t08/r3-variants"
PG = ROOT / ".tools/t02/postgresql-full/pgsql/bin"
JAVA = ROOT / ".tools/t02/jdk-21.0.12.1+1"
MVN = ROOT / ".tools/t02/apache-maven-3.9.11/bin/mvn.cmd"
M2 = ROOT / ".tools/t02/m2"
SRC = ROOT / "backend/src/main/java/com/example/editorial/cost"
TST = ROOT / "backend/src/test/java/com/example/editorial/cost"

SERVICE = SRC / "BudgetService.java"
POLICY = SRC / "BudgetPolicy.java"
PGTEST = TST / "T08PostgresTest.java"

# ----------------------------------------------------------------- anchors taken from the reviewed bytes
QUOTA_BLOCK = """        Ceiling ceiling = ceilings.stream().filter(c -> c.scope().equals("PROVIDER")).findFirst().orElseThrow();
        CostPorts.Occupancy used = ledger.occupancy(ceiling.where(), ceiling.args().toArray());
        if (quota.maxConcurrent() >= 0 && used.holds() >= quota.maxConcurrent())
            throw new PublicFailure(429, "PROVIDER_QUOTA_EXCEEDED");
        if (quota.callsPerDay() >= 0 && used.counter(BudgetPolicy.Counter.CALLS) + 1 > quota.callsPerDay())
            throw new PublicFailure(429, "PROVIDER_QUOTA_EXCEEDED");
"""
OVERLAY = """        java.util.List<BudgetPolicy.ProviderQuota> overlay = new ArrayList<>();
        overlay.add(quota);
        BudgetPolicy.ProviderQuota wideOnly = policy.providers().get(BudgetPolicy.scope(request.provider(), null));
        if (wideOnly != null && !wideOnly.equals(quota)) overlay.add(wideOnly);
        Ceiling ceiling = ceilings.stream().filter(c -> c.scope().equals("PROVIDER")).findFirst().orElseThrow();
        for (BudgetPolicy.ProviderQuota q : overlay) {
            CostPorts.Occupancy used = q.equals(quota)
                    ? ledger.occupancy(ceiling.where(), ceiling.args().toArray())
                    : ledger.occupancy("l.owner_id=? AND l.provider=? AND l.bucket_day=?",
                            actor.ownerId(), request.provider(), day);
            if (q.maxConcurrent() >= 0 && used.holds() >= q.maxConcurrent())
                throw new PublicFailure(429, "PROVIDER_QUOTA_EXCEEDED");
            if (q.callsPerDay() >= 0 && used.counter(BudgetPolicy.Counter.CALLS) + 1 > q.callsPerDay())
                throw new PublicFailure(429, "PROVIDER_QUOTA_EXCEEDED");
        }
"""
LOOKUP = """        String exact = scope(provider, model);
        if (providers.containsKey(exact)) return exact;
        String wide = scope(provider, null);
        return providers.containsKey(wide) ? wide : null;
"""
WIDE_FIRST = """        String wide = scope(provider, null);
        if (providers.containsKey(wide)) return wide;
        String exact = scope(provider, model);
        return providers.containsKey(exact) ? exact : null;
"""
PREFIX = """        String exact = scope(provider, model);
        if (providers.containsKey(exact)) return exact;
        String prefix = provider + "|";
        for (String key : providers.keySet()) {
            if (key.startsWith(prefix) && model != null && model.startsWith(key.substring(prefix.length()))) {
                return key;
            }
        }
        String wide = scope(provider, null);
        return providers.containsKey(wide) ? wide : null;
"""
DECORATIVE = """        service(BudgetPolicyConfig.from(env));
"""
DECORATIVE_REPL = """        service(BudgetPolicyConfig.from(env));
        // REVIEWER VARIANT V6: the bound environment is served, then replaced by an equivalent hand-built policy.
        service(new BudgetPolicy(money("20.000000"), wideCaps(), Map.of(
                BudgetPolicy.scope(PROVIDER, null), new BudgetPolicy.ProviderQuota(3, 30),
                BudgetPolicy.scope(PROVIDER, MODEL), new BudgetPolicy.ProviderQuota(1, 30)), 80, 30,
                BudgetPolicy.UnconfiguredQuota.REFUSE));
"""
PROBE_TEST = """
    /** REVIEWER PROBE P1: a looser model override must not lift the provider-wide ceiling above itself. */
    @Test
    @DisplayName("Reviewer probe: provider-wide ceiling caps a looser model override")
    void reviewerLooserModelOverrideStillCappedByProvider() {
        policy(wideCaps(), "20.000000", 80, Map.of(
                BudgetPolicy.scope(PROVIDER, null), new BudgetPolicy.ProviderQuota(2, 30),
                BudgetPolicy.scope(PROVIDER, MODEL), new BudgetPolicy.ProviderQuota(5, 30)));
        UUID article = article("50.000000");
        for (int i = 0; i < 3; i++) {
            budget.reserve(actor(), image(article, execution(article, null, null), UUID.randomUUID(), 1));
        }
        assertEquals(3, holds(), "P1 OBSERVATION: 3 live holds on the model while the provider-wide ceiling is 2");
    }

    /** REVIEWER PROBE P2: a dotted model id answers to the provider-wide window. */
    @Test
    @DisplayName("Reviewer probe: dotted model id is metered in the provider window")
    void reviewerDottedModelIdUsesTheProviderWindow() {
        policy(wideCaps(), "20.000000", 80, Map.of(
                BudgetPolicy.scope(PROVIDER, null), new BudgetPolicy.ProviderQuota(2, 30)));
        UUID article = article("50.000000");
        publish(PROVIDER, "gpt-4.1", generation());
        assertNotNull(budget.reserve(actor(), new BudgetService.Request(article, execution(article, null, null),
                PROVIDER, "gpt-4.1", Capability.GENERATION, new Usage(0, 0, 0, null, 1, 0), Money.ZERO, true, false,
                UUID.randomUUID())), "P2: model-level override impossible, provider entry still answers");
        assertNotNull(budget.reserve(actor(), hold(article, "gpt-4.1")));
        PublicFailure third = assertThrows(PublicFailure.class, () -> budget.reserve(actor(), hold(article, "gpt-4.1")));
        assertEquals("PROVIDER_QUOTA_EXCEEDED", third.code(), "P2 OBSERVATION: provider window counts the dotted model");
        assertEquals(2, holds());
    }
"""

VARIANTS: dict[str, dict] = {
    "V1": {"label": "overlay: enforce provider-wide as well as the model override (stricter of both)",
           "edits": [(SERVICE, QUOTA_BLOCK, OVERLAY)], "expect": 49},
    "V2": {"label": "provider level always wins the lookup (model entry only when no provider-wide entry)",
           "edits": [(POLICY, LOOKUP, WIDE_FIRST)], "expect": 49},
    "V3": {"label": "control: one shared bucket - every quota measured per model",
           "edits": [(SERVICE, 'boolean perModel = quotaScope != null && quotaScope.contains("|");',
                      "boolean perModel = true;")], "expect": 49},
    "V4": {"label": "model key matched by prefix (startsWith) instead of the exact scope",
           "edits": [(POLICY, LOOKUP, PREFIX)], "expect": 49},
    "V6": {"label": "the nested-YAML binding is served then replaced by a hand-built policy (decorative proof)",
           "edits": [(PGTEST, DECORATIVE, DECORATIVE_REPL)], "expect": 49},
    "P1": {"label": "reviewer probes added on the UNMODIFIED implementation (fail-open + dotted model window)",
           "edits": [(PGTEST, "    // ------------------------------------------------------------------"
                              " settlement, release, UNKNOWN",
                      PROBE_TEST + "\n    // ---------------------------------------------------"
                      "--------------------------- settlement, release, UNKNOWN")], "expect": 51},
}


def build(name: str) -> dict:
    spec = VARIANTS[name]
    base = WORK / name
    if base.exists():
        shutil.rmtree(base)
    backend = base / "backend"
    shutil.copytree(ROOT / "backend", backend, ignore=shutil.ignore_patterns("target"))
    runner = base / "tests/engineering/T08"
    runner.mkdir(parents=True)
    shutil.copy(ROOT / "tests/engineering/T08/run_pg.py", runner / "run_pg.py")
    for path, old, new in spec["edits"]:
        target = backend / path.relative_to(ROOT / "backend")
        text = target.read_text(encoding="utf-8")
        if old not in text:
            return {"variant": name, "stale": str(path) + " :: " + old[:60]}
        target.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
    (base / "pg").mkdir()
    command = [str(PY), str(runner / "run_pg.py"), "--pg-bin", str(PG), "--java-home", str(JAVA),
               "--maven", str(MVN), "--m2", str(M2), "--expect-tests", str(spec["expect"]),
               "--evidence-name", "variant", "--work-root", str(base / "pg")]
    done = subprocess.run(command, cwd=str(base), capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=1500)
    report = {"variant": name, "label": spec["label"], "exitCode": done.returncode,
              "stdoutTail": (done.stdout or "")[-400:]}
    runs = sorted((base / "pg").glob("*/backend/target/surefire-reports/TEST-*.xml"))
    suites = []
    for xml in runs:
        root = ET.parse(xml).getroot()
        cases = []
        for case in root.iter("testcase"):
            bad = [c.tag for c in case if c.tag in {"failure", "error"}]
            if bad:
                message = ""
                for c in case:
                    if c.tag in {"failure", "error"}:
                        message = (c.get("message") or c.text or "")[:200]
                        break
                cases.append({"case": case.get("name"), "kind": bad, "message": message})
        suites.append({"suite": root.get("name"), "tests": root.get("tests"), "failures": root.get("failures"),
                       "errors": root.get("errors"), "skipped": root.get("skipped"), "red": cases})
    report["suites"] = suites
    report["allGreen"] = all(s["failures"] == "0" and s["errors"] == "0" and s["skipped"] == "0" for s in suites)
    return report


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    names = sys.argv[1:] or list(VARIANTS)
    out = []
    for name in names:
        print(f"== {name} {VARIANTS[name]['label']}", flush=True)
        report = build(name)
        out.append(report)
        print(json.dumps(report, ensure_ascii=False, indent=1), flush=True)
    (WORK / "variant-report.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n",
                                              encoding="utf-8", newline="\n")
    print("wrote " + str(WORK / "variant-report.json"), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

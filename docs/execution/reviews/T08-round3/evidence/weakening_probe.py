#!/usr/bin/env python3
"""Round-3 reviewer probe: weaken the reviewed sources / the gate itself IN MEMORY only.

Nothing here writes a file. Every rewrite is handed to verify.py's own MUTATIONS mechanism (the same one
--reverse-control uses), so the reviewed bytes on disk stay exactly as committed.

Usage: python docs/execution/reviews/T08-round3/evidence/weakening_probe.py
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
V = ROOT / "tests/engineering/T08/verify.py"
spec = importlib.util.spec_from_file_location("t08verify", V)
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)

UNIT = ROOT / "backend/src/test/java/com/example/editorial/cost/CostPricingTest.java"
LIVE = ROOT / "backend/src/test/java/com/example/editorial/cost/T08PostgresTest.java"
CONFIG = ROOT / "backend/src/main/java/com/example/editorial/cost/BudgetPolicyConfig.java"
SERVICE = ROOT / "backend/src/main/java/com/example/editorial/cost/BudgetService.java"
POLICY = ROOT / "backend/src/main/java/com/example/editorial/cost/BudgetPolicy.java"
V5 = ROOT / "backend/src/main/resources/db/migration/V5__cost_ledger_pricing.sql"

UNIT_HELPER = """    /** REVIEWER PROBE: hand-built flat keys, the document below is only touched, never bound. */
    private static MockEnvironment handBuiltQuotaEnv() {
        return statedBeyondSrs()
                .withProperty("editorial.cost.provider-quota.mock.max-concurrent", "3")
                .withProperty("editorial.cost.provider-quota.mock.calls-per-day", "17")
                .withProperty("editorial.cost.provider-quota.mock.mock-model.max-concurrent", "1")
                .withProperty("editorial.cost.provider-quota.mock.mock-model.calls-per-day", "2");
    }

    /**
"""

CASE_HEAD = """    /**
     * Finding F2-01, from the shape an operator actually writes."""

PROBES: list[tuple[str, list[tuple[Path, list[tuple[str, str]]]], str]] = [
    # A: the case still contains the nested document and still calls from(yaml(...)), but the policy it
    #    asserts was assembled from hand-written flat keys. Text-only gate => expected GREEN (blind).
    ("A unit case asserts a hand-built flat env, YAML kept as decoration",
     [(UNIT, [(CASE_HEAD, UNIT_HELPER + CASE_HEAD[len(CASE_HEAD):]),
              ("        BudgetPolicy policy = BudgetPolicyConfig.from(yaml(\"\"\"",
               "        BudgetPolicy policy = BudgetPolicyConfig.from(handBuiltQuotaEnv());\n"
               "        BudgetPolicyConfig.from(yaml(\"\"\"")])],
     "blind if green: the binding proof is textual, not data-flow"),
    # B: same idea on the live service path.
    ("B live case serves a hand-built flat env, YAML env loaded then ignored",
     [(UNIT, [(CASE_HEAD, UNIT_HELPER + CASE_HEAD[len(CASE_HEAD):])]),
      (LIVE, [("        service(BudgetPolicyConfig.from(env));",
               "        service(BudgetPolicyConfig.from(env));\n"
               "        service(BudgetPolicyConfig.from(handBuiltFlatEnv()));"),
              ("    /** The reservation the quota cases place:",
               "    private static MockEnvironment handBuiltFlatEnv() {\n"
               "        return new MockEnvironment()\n"
               "                .withProperty(\"editorial.cost.max-calls-per-article\", \"1000\")\n"
               "                .withProperty(\"editorial.cost.reconciliation-stale-minutes\", \"30\")\n"
               "                .withProperty(\"editorial.cost.provider-quota.unconfigured\", \"refuse\")\n"
               "                .withProperty(\"editorial.cost.provider-quota.mock-provider.max-concurrent\", \"3\")\n"
               "                .withProperty(\"editorial.cost.provider-quota.mock-provider.calls-per-day\", \"30\")\n"
               "                .withProperty(\"editorial.cost.provider-quota.mock-provider.mock-gpt.max-concurrent\", \"1\")\n"
               "                .withProperty(\"editorial.cost.provider-quota.mock-provider.mock-gpt.calls-per-day\", \"30\");\n"
               "    }\n\n"
               "    /** The reservation the quota cases place:")])],
     "blind if green: the shipped service path is no longer fed by the bound environment"),
    # C: the nested document replaced by flat MockEnvironment keys (no nested text left in the body).
    ("C unit case feeds flat keys and drops the nested document",
     [(UNIT, [("        BudgetPolicy policy = BudgetPolicyConfig.from(yaml(\"\"\"\n"
              "                editorial:\n"
              "                  cost:\n"
              "                    max-calls-per-article: 64\n"
              "                    reconciliation-stale-minutes: 30\n"
              "                    provider-quota:\n"
              "                      unconfigured: refuse\n"
              "                      mock:\n"
              "                        max-concurrent: 3\n"
              "                        calls-per-day: 17\n"
              "                        mock-model:\n"
              "                          max-concurrent: 1\n"
              "                          calls-per-day: 2\n"
              "                \"\"\"));",
              "        BudgetPolicy policy = BudgetPolicyConfig.from(handBuiltQuotaEnv());"),
             (CASE_HEAD, UNIT_HELPER + CASE_HEAD[len(CASE_HEAD):])])],
     "should turn red: check_quota_scope_spelling must see the nested shape in the case body"),
    # D: the loader moved to a renamed helper (a legal refactor the gate is name-coupled to).
    ("D yaml(...) helper renamed to environmentFrom(...) - legal rename only",
     [(UNIT, [("BudgetPolicyConfig.from(yaml(", "BudgetPolicyConfig.from(environmentFrom("),
              ("    private static MockEnvironment yaml(String document) {",
               "    private static MockEnvironment environmentFrom(String document) {")])],
     "benign probe: a rename should not be a defect"),
    # E: statement split across a local - semantically identical, textual anchors broken.
    ("E service(BudgetPolicyConfig.from(env)) split into a local - same behaviour",
     [(LIVE, [("        service(BudgetPolicyConfig.from(env));",
               "        BudgetPolicy bound = BudgetPolicyConfig.from(env);\n        service(bound);")])],
     "benign probe: an equivalent rewrite should not be a defect"),
    # F: an explanatory comment inserted inside the nested fixture (YAML comment, no semantic change).
    ("F YAML comment line added inside the quota fixture",
     [(LIVE, [("                      mock-provider:\n"
               "                        max-concurrent: 3",
               "                      mock-provider:\n"
               "                        # provider-wide entry: both leaves required\n"
               "                        max-concurrent: 3")])],
     "benign probe: documentation inside the fixture should not be a defect"),
    # G: provider-wide window test written the idiomatic Java way (indexOf instead of contains).
    ("G perModel written as indexOf('|') >= 0 - same predicate",
     [(SERVICE, [('boolean perModel = quotaScope != null && quotaScope.contains("|");',
                  'boolean perModel = quotaScope != null && quotaScope.indexOf(\'|\') >= 0;')])],
     "benign probe: an equivalent predicate should not be a defect"),
    # H: an invented ceiling reached through env.getProperty with a default, bypassing count()/statedCeiling().
    ("H new invented default via env.getProperty(...,Integer.class,999)",
     [(CONFIG, [("        return new BudgetPolicy(Money.of(env.getProperty(\"editorial.cost.daily-budget\"",
                "        caps.put(BudgetPolicy.Counter.SEARCH_QUERY,\n"
                "                Math.min(caps.get(BudgetPolicy.Counter.SEARCH_QUERY),\n"
                "                        env.getProperty(\"editorial.cost.search-queries-hard-cap\", Integer.class, 99)));\n"
                "        return new BudgetPolicy(Money.of(env.getProperty(\"editorial.cost.daily-budget\"")])],
     "blind if green: check_documented_ceilings only cross-reads the SRS through count()/two literal regexes"),
    # I: provider quotas supplied by a non-enumerable / upper-snake source are silently dropped.
    ("I document the env-var asymmetry (probe of the enumeration-only quota reader)",
     [(CONFIG, [('if (!(source instanceof EnumerablePropertySource<?> enumerable)) continue;',
                 'if (!(source instanceof EnumerablePropertySource<?> enumerable)) continue; // non-enumerable=skipped')])],
     "control: a comment-only change must stay green (gate is not reading prose)"),
]


def run(path_edits):
    verify.MUTATIONS.clear()
    for path, edits in path_edits:
        source = path.read_text(encoding="utf-8", errors="replace")
        stale = [old for old, _ in edits if old not in source]
        if stale:
            return None, ["STALE: " + s[:70] for s in stale]
        verify.MUTATIONS[str(path)] = edits
    try:
        results = verify.run_checks()
    finally:
        verify.MUTATIONS.clear()
    return {name for name, ok, _ in results if not ok}, []


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    baseline = verify.run_checks()
    red = [name for name, ok, _ in baseline if not ok]
    print("baseline red:", red or "none", f"({len(baseline)} checks)")
    if red:
        return 2
    print("\n== weakenings ==")
    for name, edits, note in PROBES:
        failed, stale = run(edits)
        if failed is None:
            print(f"[STALE ] {name}: {stale}")
            continue
        print(f"[{'GREEN/BLIND' if not failed else 'RED      '}] {name}")
        print(f"          red={sorted(failed) if failed else 'NONE'}  |  {note}")
    print("\n== gate short-circuits: are the reverse controls load-bearing? ==")
    names = {fn.__name__: fn()[0] for fn in verify.CHECKS}
    targets = ["check_documented_ceilings", "check_quota_scope_spelling", "check_admission_ceiling",
               "check_acceptance_anchors"]
    all_specs = verify.reversals()
    for label in targets:
        fn = getattr(verify, label)
        original = list(verify.CHECKS)
        index = original.index(fn)
        check_name = names[label]
        verify.CHECKS[index] = lambda n=check_name: (n, True, "stubbed green by reviewer")
        own = [s["name"] for s in all_specs if set(s["red"]) == {check_name}]
        blind_now = []
        for spec in all_specs:
            failed, _ = run([(Path(spec["path"]), spec.get("edits") or [(spec["old"], spec["new"])])])
            if failed is not None and not failed and spec["name"] in own:
                blind_now.append(spec["name"])
        print(f"[stub {label}] reverse controls that name only it: {len(own)}; go BLIND when stubbed: "
              f"{len(blind_now)}")
        for nm in blind_now:
            print(f"          BLIND -> {nm}")
        verify.CHECKS[:] = original

    print("\n== V5 lock position, measured by this reviewer ==")
    sql = V5.read_text(encoding="utf-8")
    fn = re.search(r"CREATE FUNCTION editorial\.t08_admit_estimate\(\).*?END \$\$;", sql, re.S).group(0)
    lock = re.search(r"SELECT budget_limit INTO limit_amount FROM editorial\.article_job WHERE id=NEW\.article_id"
                     r" FOR UPDATE;", fn)
    agg = fn.find("INTO occupied")
    print("lock stmt at", lock.start(), "aggregate at", agg, "-> locked_first =", lock.start() < agg)
    print("FOR UPDATE mentions in the function:", [m.start() for m in re.finditer("FOR UPDATE", fn)],
          "inside the lock statement:", [m for m in re.finditer("FOR UPDATE", fn)
                                         if lock.start() <= m.start() < lock.end()])
    print("missing-row guard follows:", "IF NOT FOUND" in fn[lock.end():lock.end() + 160])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

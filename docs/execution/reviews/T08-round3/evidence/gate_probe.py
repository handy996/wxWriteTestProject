#!/usr/bin/env python3
"""Round-3 reviewer probe of the T08 gate itself: every rewrite is applied IN MEMORY through verify.py's own
MUTATIONS mechanism (the one --reverse-control uses). No file, cluster or tracked path is written.

Six questions:
  A  can the nested-YAML binding proof be faked while check 11 stays green?
  B  can the live service case keep its tokens while the bound environment is ignored?
  C  does check 9 really read the SRS (mutate the SRS, not the code)?
  D  can an invented ceiling slip in through a read path check 9 does not scan?
  E  are the 30 reverse controls load-bearing (stub a check, see which controls go ACCEPTED)?
  F  benign probes: equivalent rewrites that must NOT be red.

Usage: python docs/execution/reviews/T08-round3/evidence/gate_probe.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path("E:/project/codex/wxAgent")
spec = importlib.util.spec_from_file_location("t08verify", ROOT / "tests/engineering/T08/verify.py")
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)

UNIT = ROOT / "backend/src/test/java/com/example/editorial/cost/CostPricingTest.java"
LIVE = ROOT / "backend/src/test/java/com/example/editorial/cost/T08PostgresTest.java"
CONFIG = ROOT / "backend/src/main/java/com/example/editorial/cost/BudgetPolicyConfig.java"
SERVICE = ROOT / "backend/src/main/java/com/example/editorial/cost/BudgetService.java"
SRS = ROOT / "docs/AI-Editorial-Agent-SRS-v1.0.md"

CEILINGS = "ceilings are the documented SRS numbers or required outright"
QUOTAS = "provider quota scopes are spelled one way and absence is a stated choice"
ADMISSION = "article ceiling is a locked database rule"
ANCHORS = "acceptance cases still assert what they claim"
USAGE = "frozen GET /usage surface, no field drift"

YAML_HELPER_HEAD = "    private static MockEnvironment yaml(String document) {"
UNRELATED_LOADER = """    /** REVIEWER PROBE: the Spring loader now lives in a helper the quota case never calls. */
    private static org.springframework.core.env.PropertySource<?> loadedAside(String document) throws java.io.IOException {
        return new YamlPropertySourceLoader().load("aside",
                new ByteArrayResource(document.getBytes(StandardCharsets.UTF_8))).get(0);
    }

"""
FLAT_YAML_HELPER = """    private static MockEnvironment yaml(String document) {
        return statedBeyondSrs()
                .withProperty("editorial.cost.provider-quota.mock.max-concurrent", "3")
                .withProperty("editorial.cost.provider-quota.mock.calls-per-day", "17")
                .withProperty("editorial.cost.provider-quota.mock.mock-model.max-concurrent", "1")
                .withProperty("editorial.cost.provider-quota.mock.mock-model.calls-per-day", "2")
                .withProperty("reviewer.document.length", String.valueOf(document.length()));
    }
"""
REAL_YAML_HELPER_TAIL = """        MockEnvironment env = new MockEnvironment();
        try {
            for (PropertySource<?> source : new YamlPropertySourceLoader().load("t08-quota",
                    new ByteArrayResource(document.getBytes(StandardCharsets.UTF_8)))) {
                env.getPropertySources().addLast(source);
            }
        } catch (java.io.IOException unreadable) {
            throw new IllegalStateException("the fixture document could not be read", unreadable);
        }
        return env;
    }
"""
NESTED_UNIT_DOC = """        BudgetPolicy policy = BudgetPolicyConfig.from(yaml(\"\"\"
                editorial:
                  cost:
                    max-calls-per-article: 64
                    reconciliation-stale-minutes: 30
                    provider-quota:
                      unconfigured: refuse
                      mock:
                        max-concurrent: 3
                        calls-per-day: 17
                        mock-model:
                          max-concurrent: 1
                          calls-per-day: 2
                \"\"\"));"""

PROBES: list[tuple[str, list[tuple[Path, list[tuple[str, str]]]], str]] = [
    ("A1 loader call moved to an unrelated helper; yaml() now hand-builds flat keys, nested doc still in the body",
     [(UNIT, [(YAML_HELPER_HEAD + "\n" + REAL_YAML_HELPER_TAIL, UNRELATED_LOADER + FLAT_YAML_HELPER)])],
     "blind => check 11 matches words in the file, not the data flow of the case"),
    ("A2 nested document moved out of the case body into a field (body keeps only from(yaml(FIXTURE)))",
     [(UNIT, [(NESTED_UNIT_DOC, "        BudgetPolicy policy = BudgetPolicyConfig.from(yaml(QUOTA_FIXTURE));"),
              (YAML_HELPER_HEAD, "    private static final String QUOTA_FIXTURE = \"\"\""
               "editorial:\\n  cost:\\n    provider-quota:\\n      unconfigured: refuse\\n      mock:\\n"
               "        max-concurrent: 3\\n        calls-per-day: 17\\n        mock-model:\\n"
               "          max-concurrent: 1\\n          calls-per-day: 2\\\"\"\";\\n\\n" + YAML_HELPER_HEAD)])],
     "should be red: the body-scoped nested-shape scan is the part that carries weight"),
    ("B1 live case serves the bound env then overrides it with a hand-built policy (tokens intact)",
     [(LIVE, [("        service(BudgetPolicyConfig.from(env));",
               "        service(BudgetPolicyConfig.from(env));\n"
               "        service(new BudgetPolicy(money(\"20.000000\"), wideCaps(), Map.of(), 80, 30,\n"
               "                BudgetPolicy.UnconfiguredQuota.REFUSE));")])],
     "blind => no check notices that the last policy served is not the bound one"),
    ("B2 live case binding moved behind a bind(env) helper; body reads service(bind(env))",
     [(LIVE, [("        service(BudgetPolicyConfig.from(env));", "        service(bind(env));"),
              ("    /** The reservation the quota cases place:",
               "    private static BudgetPolicy bind(Environment used) {\n"
               "        return BudgetPolicyConfig.from(used);\n    }\n\n"
               "    /** The reservation the quota cases place:")])],
     "anchor token service(BudgetPolicyConfig.from(env)) is gone from the body: expect red via check 14"),
    ("C1 SRS line 1103 re-typed 40,000 -> 41,000 (only the requirement text changes)",
     [(SRS, [("输出总 token 上限 40,000", "输出总 token 上限 41,000")])],
     "must be red: proof that check 9 parses the SRS instead of hard-coding the number"),
    ("C2 SRS line 1099 daily example 20 -> 25 USD",
     [(SRS, [("日预算示例 20 USD", "日预算示例 25 USD")])],
     "must be red: the daily fallback is compared against the SRS text"),
    ("C3 SRS line 1143 alert trigger >80% -> >70%",
     [(SRS, [("预算 >80%", "预算 >70%")])],
     "must be red: the alert line is compared against the SRS text"),
    ("D1 invented ceiling written straight into the map, bypassing count()/statedCeiling()",
     [(CONFIG, [("        return new BudgetPolicy(Money.of(env.getProperty(\"editorial.cost.daily-budget\"",
                "        caps.put(BudgetPolicy.Counter.IMAGE_GENERATION_ARTICLE,\n"
                "                Math.max(caps.get(BudgetPolicy.Counter.IMAGE_GENERATION_ARTICLE), 400L));\n"
                "        return new BudgetPolicy(Money.of(env.getProperty(\"editorial.cost.daily-budget\"")])],
     "blind => check 9 only re-reads the two literal regex shapes it knows"),
    ("F1 benign: perModel written with indexOf instead of contains (same predicate)",
     [(SERVICE, [('boolean perModel = quotaScope != null && quotaScope.contains("|");',
                  "boolean perModel = quotaScope != null && quotaScope.indexOf('|') >= 0;")])],
     "equivalent rewrite: a red here is brittleness, not a defect"),
    ("F2 benign: BudgetPolicy.scope(path[0], path[1]) re-wrapped onto two lines",
     [(CONFIG, [("case 3 -> BudgetPolicy.scope(path[0], path[1]);",
                 "case 3 -> BudgetPolicy.scope(\n                                        path[0], path[1]);")])],
     "whitespace only: must stay green"),
    ("F3 benign: javadoc sentence in BudgetPolicyConfig re-worded, code identical",
     [(CONFIG, [(" * <p>Keys are all under {@code editorial.cost.}. Amounts are configured as canonical strings, never floats.",
                 " * <p>Every key sits under {@code editorial.cost.}. Amounts arrive as canonical strings.")])],
     "prose only: must stay green"),
    ("F4 benign: the live case splits the binding into a local before serving it",
     [(LIVE, [("        service(BudgetPolicyConfig.from(env));",
               "        BudgetPolicy bound = BudgetPolicyConfig.from(env);\n        service(bound);")])],
     "same behaviour, anchor text moved: expect red (name coupling)"),
]


def run(path_edits):
    verify.MUTATIONS.clear()
    for path, edits in path_edits:
        source = path.read_text(encoding="utf-8", errors="replace")
        stale = [old for old, _ in edits if old not in source]
        if stale:
            return None, [s[:60] for s in stale]
        verify.MUTATIONS[str(path)] = edits
    try:
        try:
            results = verify.run_checks()
        except SystemExit as stale_gate:
            return None, [f"gate called it stale: {stale_gate}"[:80]]
    finally:
        verify.MUTATIONS.clear()
    return {name for name, ok, _ in results if not ok}, []


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    out: dict = {"baseline": [], "probes": [], "stub": [], "detail": {}}
    baseline = verify.run_checks()
    out["baseline"] = [{"check": n, "ok": ok} for n, ok, _ in baseline]
    if [n for n, ok, _ in baseline if not ok]:
        print("baseline is red, refusing to judge")
        return 2
    for name, edits, note in PROBES:
        failed, stale = run(edits)
        entry = {"probe": name, "note": note}
        if failed is None:
            entry["stale"] = stale
        else:
            entry["red"] = sorted(failed)
            # capture the reason the gate gives for the interesting cases
            verify.MUTATIONS.clear()
            for path, e in edits:
                verify.MUTATIONS[str(path)] = e
            for fn, (cname, cok, cdetail) in zip(verify.CHECKS, verify.run_checks()):
                if not cok and cname in (QUOTAS, CEILINGS, ANCHORS):
                    out["detail"][name.split()[0]] = f"{cname}: {cdetail[:300]}"
            verify.MUTATIONS.clear()
        out["probes"].append(entry)
        print(f"[{'RED ' if failed else 'GREEN'}] {name}\n        red={sorted(failed) if failed else 'NONE'}")

    print("\n== load-bearing: stub a check, watch reverse controls go ACCEPTED ==")
    all_specs = verify.reversals()
    for label in ("check_documented_ceilings", "check_quota_scope_spelling", "check_admission_ceiling",
                  "check_acceptance_anchors", "check_frozen_usage_surface"):
        fn = getattr(verify, label)
        cname = fn()[0]
        original = list(verify.CHECKS)
        index = original.index(fn)
        own = [s for s in all_specs if cname in set(s["red"])]
        verify.CHECKS[index] = (lambda n=cname: (n, True, "stubbed green by reviewer"))
        accepted = []
        for reversal in own:
            path = Path(reversal["path"])
            edits = reversal.get("edits") or [(reversal["old"], reversal["new"])]
            failed, _ = run([(path, edits)])
            if failed is not None and not failed:
                accepted.append(reversal["name"])
        verify.CHECKS[:] = original
        out["stub"].append({"check": cname, "controls_naming_it": len(own), "go_accepted_when_stubbed": accepted})
        print(f"[stub {label}] controls naming it={len(own)} go ACCEPTED={len(accepted)}")
        for nm in accepted:
            print("          ACCEPTED ->", nm)
    path = ROOT / ".work/t08/r3-variants/gate_probe.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

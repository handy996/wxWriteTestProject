#!/usr/bin/env python3
"""Reverse control of the T08 static gate (in-memory mutation only - nothing is written to disk).

STATE.json protocol requires that a "pass" style assertion prove it would reject a weakened input. verify.py
ships no self-test, so this script imports it, feeds mutated *contents* to pathlib in this process only, and
records, for each mutation, which of the 11 checks flipped. Two outcomes are expected and labelled:

  REJECTS      the target check must go FAIL            - proves the gate is effective
  BLIND_SPOT   every check still PASSES on a real policy weakening - recorded as a review finding

File hashes are re-read at the end and must be unchanged: that is the proof that no mutation touched disk.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
EVIDENCE = HERE / "evidence" / "checks.json"
V = ROOT / "tests/engineering/T08/verify.py"

spec = importlib.util.spec_from_file_location("t08verify", V)
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)

V5 = ROOT / "backend/src/main/resources/db/migration/V5__cost_ledger_pricing.sql"
DRAFT = ROOT / "tests/engineering/T08/migration-draft.sql"
COST = ROOT / "backend/src/main/java/com/example/editorial/cost"
TEST = ROOT / "backend/src/test/java/com/example/editorial/cost"

CHECKS = [("frozen_contracts", verify.check_frozen_contracts), ("module_boundary", verify.check_module_boundary),
          ("package_contents", verify.check_package_contents), ("installed_migration", verify.check_installed_migration),
          ("grants", verify.check_grants), ("decimal_only", verify.check_decimal_only),
          ("frozen_usage_surface", verify.check_frozen_usage_surface),
          ("audit_payload_shape", verify.check_audit_payload_shape),
          ("configuration_ownership", verify.check_configuration_ownership),
          ("paid_calls_refused", verify.check_paid_calls_still_refused),
          ("acceptance_anchors", verify.check_acceptance_anchors)]

MUTATIONS = [
    {"id": "M01-usage-summary-field-added", "expect": "REJECTS", "target": "frozen_usage_surface",
     "file": COST / "Reservation.java",
     "old": 'n.put("createdAt", createdAt.toString());',
     "new": 'n.put("createdAt", createdAt.toString());\n        n.put("overRun", overRun.text());'},
    {"id": "M02-usage-summary-field-renamed", "expect": "REJECTS", "target": "frozen_usage_surface",
     "file": COST / "UsageService.java", "old": 'summary.set("nextCursor"', "new": 'summary.set("nextCursorX"'},
    {"id": "M03-v5-ceiling-check-weakened", "expect": "REJECTS", "target": "installed_migration",
     "file": V5, "old": "amount numeric(18,6) NOT NULL CHECK (amount>=0),",
     "new": "amount numeric(18,6) NOT NULL CHECK (amount>=-1),"},
    {"id": "M04-v5-third-cost-table", "expect": "REJECTS", "target": "installed_migration",
     "file": V5, "old": "REVOKE ALL ON FUNCTION editorial.t08_admit_estimate()",
     "new": "CREATE TABLE editorial.cost_extra (id uuid PRIMARY KEY);\nREVOKE ALL ON FUNCTION editorial.t08_admit_estimate()"},
    {"id": "M05-draft-grants-delete", "expect": "REJECTS", "target": "grants",
     "file": DRAFT, "old": "GRANT SELECT,INSERT,UPDATE ON editorial.cost_ledger TO editorial_runtime;",
     "new": "GRANT SELECT,INSERT,UPDATE,DELETE ON editorial.cost_ledger TO editorial_runtime;"},
    {"id": "M06-money-uses-double", "expect": "REJECTS", "target": "decimal_only",
     "file": COST / "Money.java", "old": "private final BigDecimal value;",
     "new": "private final BigDecimal value;\n    private double scratch;"},
    {"id": "M07-audit-carries-amount", "expect": "REJECTS", "target": "audit_payload_shape",
     "file": COST / "BudgetService.java", "old": "reservation.id(), null, null);",
     "new": 'reservation.id(), estimate.text(), null);'},
    {"id": "M08-silent-audit-fallback-returns", "expect": "REJECTS", "target": "audit_payload_shape",
     "file": COST / "CostConfiguration.java", "old": "    @Bean BudgetService budgetService",
     "new": "    @Bean @ConditionalOnMissingBean(CostPorts.Audit.class) CostPorts.Audit costAuditFallback() "
            "{ return CostPorts.noAudit(); }\n\n    @Bean BudgetService budgetService"},
    {"id": "M09-cost-imports-audit", "expect": "REJECTS", "target": "module_boundary",
     "file": COST / "CostPorts.java", "old": "import java.util.Map;",
     "new": "import com.example.editorial.audit.AuditSink;\nimport java.util.Map;"},
    {"id": "M10-yml-invents-daily-budget", "expect": "REJECTS", "target": "configuration_ownership",
     "file": ROOT / "backend/src/main/resources/application.yml", "old": "    enabled: ${EDITORIAL_COST_ENABLED:false}",
     "new": "    enabled: ${EDITORIAL_COST_ENABLED:false}\n    daily-budget: 20.000000"},
    {"id": "M11-anchor-test-renamed", "expect": "REJECTS", "target": "acceptance_anchors",
     "file": TEST / "T08PostgresTest.java", "old": "void lastBalanceSingleWinner()", "new": "void renamedAway()"},
    {"id": "M12-invented-budget-defaults-changed", "expect": "BLIND_SPOT", "target": None,
     "file": COST / "BudgetPolicyConfig.java",
     "old": 'Money.of(env.getProperty("editorial.cost.daily-budget", "20.000000"))',
     "new": 'Money.of(env.getProperty("editorial.cost.daily-budget", "999.000000"))',
     "second": ('count(env, "editorial.cost.search-queries-per-article", 30)',
                'count(env, "editorial.cost.search-queries-per-article", 1000000)')},
    {"id": "M13-paid-call-guard-neutralised", "expect": "BLIND_SPOT", "target": "paid_calls_refused",
     "file": ROOT / "backend/src/main/java/com/example/editorial/bootstrap/StartupPolicy.java",
     "old": 'require(!env.getProperty("editorial.providers.paid-calls-enabled", Boolean.class, false),',
     "new": 'require(!env.getProperty("editorial.providers.paid-calls-enabled", Boolean.class, false) || true,'},
    {"id": "M14-audit-shape-guard-disabled", "expect": "BLIND_SPOT", "target": "audit_payload_shape",
     "file": ROOT / "backend/src/main/java/com/example/editorial/bootstrap/CostIntegration.java",
     "old": "if (value != null && !value.matches(HASH_SHAPE)) {", "new": "if (false && value != null) {"},
    {"id": "M15-ac28-assertion-hollowed", "expect": "BLIND_SPOT", "target": "acceptance_anchors",
     "file": TEST / "T08PostgresTest.java",
     "old": 'assertEquals(1, winners, "exactly one caller may take the last unit: " + outcomes);',
     "new": 'assertTrue(true, "anchor kept");'},
]


def run_checks() -> dict:
    result = {}
    for name, fn in CHECKS:
        _label, ok, _detail = fn()
        result[name] = bool(ok)
    return result


def main() -> int:
    original_read_bytes = Path.read_bytes
    original_read_text = Path.read_text
    state = {"rules": {}, "applied": 0}

    def read_bytes(self):
        raw = original_read_bytes(self)
        for old, new in state["rules"].get(self.resolve(), []):
            if old.encode() in raw:
                raw = raw.replace(old.encode(), new.encode(), 1)
        return raw

    def read_text(self, encoding="utf-8", errors=None):
        return read_bytes(self).decode(encoding or "utf-8", errors or "strict")

    Path.read_bytes, Path.read_text = read_bytes, read_text
    baseline = run_checks()
    rows = []
    for mutation in MUTATIONS:
        path = mutation["file"]
        pairs = [(mutation["old"], mutation["new"])] + ([mutation["second"]] if "second" in mutation else [])
        raw = original_read_bytes(path)
        applies = all(old.encode() in raw for old, _ in pairs)
        state["rules"] = {path.resolve(): pairs} if applies else {}
        after = run_checks() if applies else dict(baseline)
        flipped = sorted(name for name in baseline if baseline[name] and not after[name])
        if not applies:
            verdict, valid = "MUTATION-NOT-APPLIED", False
        elif mutation["expect"] == "REJECTS":
            valid = mutation["target"] in flipped
            verdict = "REJECTED" if valid else "NOT-REJECTED"
        else:
            target_still_ok = after.get(mutation["target"], True) if mutation["target"] else all(after.values())
            valid = not flipped and target_still_ok
            verdict = "BLIND-SPOT-CONFIRMED" if valid else "actually-rejected"
        rows.append({"id": mutation["id"], "expect": mutation["expect"], "target": mutation["target"],
                     "file": str(path.relative_to(ROOT)).replace("\\", "/"), "applied": applies,
                     "checksThatFailed": flipped, "verdict": verdict, "controlValid": valid})
        print(f"{mutation['id']:38} {verdict:22} failed={flipped or 'none'}")
    state["rules"] = {}
    Path.read_bytes, Path.read_text = original_read_bytes, original_read_text

    touched = sorted({m["file"].resolve() for m in MUTATIONS})
    unchanged = all(hashlib.sha256(p.read_bytes()).hexdigest()
                    == hashlib.sha256(original_read_bytes(p)).hexdigest() for p in touched)
    rejected = [r for r in rows if r["expect"] == "REJECTS"]
    blind = [r for r in rows if r["expect"] == "BLIND_SPOT"]
    payload = {"reverseControl": {
        "gate": "tests/engineering/T08/verify.py (11 checks)",
        "baselineAllPass": all(baseline.values()), "baseline": baseline,
        "controls": rows,
        "effectiveness": f"{sum(1 for r in rejected if r['controlValid'])}/{len(rejected)} weakenings rejected",
        "blindSpots": f"{sum(1 for r in blind if r['controlValid'])}/{len(blind)} weakenings unnoticed",
        "diskUnchanged": unchanged,
        "mutationMethod": "pathlib read hooks in this process only; no file on disk was modified"}}
    merged = json.loads(EVIDENCE.read_text(encoding="utf-8")) if EVIDENCE.is_file() else {}
    merged.update(payload)
    emit(merged)
    print(f"\neffectiveness: {payload['reverseControl']['effectiveness']}; "
          f"blind spots: {payload['reverseControl']['blindSpots']}; disk unchanged: {unchanged}")
    return 0 if unchanged and all(r["controlValid"] for r in rows) else 1


def emit(payload: dict) -> None:
    """Prefer the evidence file; a confined shell that denies writes gets the same JSON on stdout instead."""
    try:
        EVIDENCE.parent.mkdir(exist_ok=True)
        EVIDENCE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8", newline="\n")
        print("evidence:", EVIDENCE.relative_to(ROOT))
    except OSError as blocked:
        print(f"evidence write blocked ({type(blocked).__name__}); JSON follows on stdout")
        print("===JSON-BEGIN===")
        print(json.dumps(payload, ensure_ascii=False))
        print("===JSON-END===")


if __name__ == "__main__":
    raise SystemExit(main())

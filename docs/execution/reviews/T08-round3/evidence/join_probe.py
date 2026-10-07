#!/usr/bin/env python3
"""Round-3 reviewer, second probe: is the "one and only one join" claim gated across the whole module, and where
exactly does the database lock sit. In memory only for the first part; the second part only reads bytes.

Usage: python docs/execution/reviews/T08-round3/evidence/join_probe.py
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path("E:/project/codex/wxAgent")
spec = importlib.util.spec_from_file_location("t08verify", ROOT / "tests/engineering/T08/verify.py")
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)

SERVICE = ROOT / "backend/src/main/java/com/example/editorial/cost/BudgetService.java"
POLICY = ROOT / "backend/src/main/java/com/example/editorial/cost/BudgetPolicy.java"
V5 = ROOT / "backend/src/main/resources/db/migration/V5__cost_ledger_pricing.sql"
QUOTAS = verify.check_quota_scope_spelling()[0]
ANCHORS = verify.check_acceptance_anchors()[0]

CALL = "        String quotaScope = policy.quotaScope(provider, model);"
SECOND_JOIN = """        String quotaScope = (model == null || model.isBlank() ? provider : provider + "|" + model);
        if (!policy.providers().containsKey(quotaScope)) quotaScope = null;
"""
STRING_JOIN = """        String quotaScope = policy.providers().keySet().stream()
                .filter(key -> key.equals(String.join("|", provider, model == null ? "" : model)))
                .findFirst().orElse(null);
"""


def run(path, old, new):
    source = Path(path).read_text(encoding="utf-8", errors="replace")
    if old not in source:
        return "STALE"
    verify.MUTATIONS.clear()
    verify.MUTATIONS[str(path)] = [(old, new)]
    try:
        return sorted(name for name, ok, _ in verify.run_checks() if not ok)
    finally:
        verify.MUTATIONS.clear()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    out: dict = {"probes": [], "v5Lock": {}}
    for label, path, old, new in [
        ("J1 BudgetService joins provider and model itself (a second spelling outside the scanned files)",
         SERVICE, CALL, SECOND_JOIN),
        ("J2 BudgetService builds the scope with String.join (the scan only knows '+' spellings)",
         SERVICE, CALL, STRING_JOIN),
    ]:
        red = run(path, old, new)
        out["probes"].append({"probe": label, "red": red})
        print(f"[{'RED ' if isinstance(red, list) and red else 'GREEN/BLIND'}] {label}\n        red={red}")

    sql = V5.read_text(encoding="utf-8")
    function = re.search(r"CREATE FUNCTION editorial\.t08_admit_estimate\(\).*?END \$\$;", sql, re.S).group(0)
    lock = re.search(r"SELECT budget_limit INTO limit_amount FROM editorial\.article_job WHERE id=NEW\.article_id"
                     r" FOR UPDATE;", function)
    aggregate = function.find("INTO occupied")
    mentions = [m.start() for m in re.finditer("FOR UPDATE", function)]
    inside = [m.start() for m in re.finditer("FOR UPDATE", function)
              if lock and lock.start() <= m.start() < lock.end()]
    out["v5Lock"] = {"lockOffset": lock.start(), "aggregateOffset": aggregate,
                     "lockBeforeAggregate": lock.start() < aggregate,
                     "forUpdateMentions": mentions, "mentionsInsideTheLockStatement": inside,
                     "missingRowGuardFollows": "IF NOT FOUND" in function[lock.end():lock.end() + 160],
                     "aggregateIsSumOfOccupied": "sum(" in function[aggregate:aggregate + 400].lower()}
    print(json.dumps(out, indent=2, ensure_ascii=False))
    (ROOT / ".work/t08/r3-variants/join_probe.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n",
                                                                encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

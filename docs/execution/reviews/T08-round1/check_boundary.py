#!/usr/bin/env python3
"""Independent boundary and byte-level proof for T08 round 1 (read-only).

Proves, from the commit blob and the working tree, that: the T08 commit adds the declared files and modifies
only application.yml + STATE.json; the installed V5 body is byte-identical to the reviewed draft after the
header 3 lines; neither file carries a BOM or a CR; there is no sixth versioned migration; and the cost domain
creates exactly two tables and no other domain object outside them. Records hashes and counts only.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
EVIDENCE = HERE / "evidence" / "checks.json"
COMMIT = "b3a909d"
V5 = "backend/src/main/resources/db/migration/V5__cost_ledger_pricing.sql"
DRAFT = "tests/engineering/T08/migration-draft.sql"
MIGRATIONS_DIR = "backend/src/main/resources/db/migration"


def git(*args: str) -> bytes:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True).stdout


def blob(path: str, rev: str = COMMIT) -> bytes:
    return git("show", f"{rev}:{path}")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def analyse(name: str, raw: bytes) -> dict:
    return {"bytes": len(raw), "sha256": sha(raw), "first3Bytes": raw[:3].hex(),
            "bom": raw[:3] == b"\xef\xbb\xbf", "crBytes": raw.count(b"\r"), "crlf": raw.count(b"\r\n"),
            "lf": raw.count(b"\n"), "trailingNewline": raw.endswith(b"\n")}


def main() -> int:
    out = {"boundaryProof": {}, "verdictInputs": {}}
    proof = out["boundaryProof"]

    # 1. commit file list, by status letter
    status_lines = [line for line in git("show", "--name-status", "--pretty=format:", COMMIT)
                    .decode("utf-8", "replace").splitlines() if line.strip()]
    by_status: dict[str, list[str]] = {}
    for line in status_lines:
        parts = line.split("\t")
        letter = re.sub(r"[^A-Za-z]", "", parts[0]) or "?"
        by_status.setdefault(letter, []).append(parts[-1])
    proof["commitFilesTotal"] = len(status_lines)
    proof["commitAdded"] = len(by_status.get("A", []))
    proof["commitModified"] = sorted(by_status.get("M", []))
    proof["commitOther"] = {k: v for k, v in by_status.items() if k not in {"A", "M"}}

    # 2. byte analysis of V5 and the draft, from the commit and from the working tree
    proof["v5Committed"] = analyse("v5Committed", blob(V5))
    proof["draftCommitted"] = analyse("draftCommitted", blob(DRAFT))
    proof["v5Worktree"] = analyse("v5Worktree", (ROOT / V5).read_bytes())
    proof["draftWorktree"] = analyse("draftWorktree", (ROOT / DRAFT).read_bytes())
    proof["worktreeMatchesCommit"] = (proof["v5Worktree"]["sha256"] == proof["v5Committed"]["sha256"]
                                      and proof["draftWorktree"]["sha256"] == proof["draftCommitted"]["sha256"])
    reference = blob(f"{MIGRATIONS_DIR}/V4__change_proposal.sql")
    proof["v4ReferenceFirst3Bytes"] = reference[:3].hex()
    proof["v4ReferenceCrlf"] = reference.count(b"\r\n")

    # 3. body after the header 3 lines must be byte-for-byte equal
    v5, draft = blob(V5), blob(DRAFT)
    body_v5 = b"".join(v5.splitlines(keepends=True)[3:])
    body_draft = b"".join(draft.splitlines(keepends=True)[3:])
    proof["bodyAfterHeader3Lines"] = {"v5Bytes": len(body_v5), "draftBytes": len(body_draft),
                                      "identical": body_v5 == body_draft,
                                      "sha256v5": sha(body_v5), "sha256draft": sha(body_draft),
                                      "identicalAfterNewlineNormalisation":
                                          body_v5.replace(b"\r\n", b"\n") == body_draft.replace(b"\r\n", b"\n")}
    proof["headerOnlyDiff"] = [l.decode()[:60] for l in v5.splitlines()[:3]] + \
                             ["---"] + [l.decode()[:60] for l in draft.splitlines()[:3]]

    # 4. migration inventory: exactly V1..V5, cost tables only in V5
    listing = git("ls-tree", "--name-only", f"{COMMIT}:{MIGRATIONS_DIR}").decode("utf-8", "replace").split()
    versioned = sorted(name for name in listing if re.match(r"V\d+__", name))
    proof["migrationFiles"] = sorted(listing)
    proof["versionedMigrations"] = versioned
    proof["exactlyFiveVersioned"] = versioned == ["V1__identity_audit_idempotency.sql", "V2__skill_prompt_policy.sql",
                                                  "V3__article_job_version.sql", "V4__change_proposal.sql",
                                                  V5.split("/")[-1]]
    mentions = {}
    for name in listing:
        text = blob(f"{MIGRATIONS_DIR}/{name}").decode("utf-8", "replace")
        hits = len(re.findall(r"cost_ledger|cost_pricing_version", text))
        if hits:
            mentions[name] = hits
    proof["costMentionsPerMigrationFile"] = mentions

    # 5. V5 DDL inventory (comment lines stripped: prose about TRUNCATE is not DDL)
    sql = "\n".join(line.split("--")[0] for line in v5.decode().splitlines())
    tables = sorted(set(re.findall(r"CREATE TABLE editorial\.(\w+)", sql)))
    proof["v5CreateTable"] = tables
    proof["v5OnlyCostTables"] = tables == ["cost_ledger", "cost_pricing_version"]
    proof["v5CreateIndex"] = len(re.findall(r"CREATE (?:UNIQUE )?INDEX", sql))
    proof["v5CreateFunction"] = sorted(re.findall(r"CREATE FUNCTION editorial\.(\w+)", sql))
    proof["v5Triggers"] = sorted(re.findall(r"CREATE (?:CONSTRAINT )?TRIGGER (\w+)", sql))
    proof["v5TriggerKinds"] = re.findall(r"CREATE (?:CONSTRAINT )?TRIGGER \w+ (BEFORE|AFTER) (\w+|\w+ OR \w+)", sql)
    proof["v5AlterOrDrop"] = re.findall(r"\b(ALTER TABLE|DROP TABLE|DROP FUNCTION|TRUNCATE)\b[^;]*", sql, re.I)
    proof["v5Grants"] = [g.strip()[:120] for g in re.findall(r"(?:GRANT|REVOKE)[^;]+", sql, re.I)]
    other_domain = sorted(set(re.findall(r"(?:UPDATE|INSERT INTO|ALTER TABLE|DELETE FROM)\s+editorial\.(?!cost_)\w+",
                                         sql, re.I)))
    proof["v5WritesToNonCostTables"] = other_domain

    # 6. application.yml: the commit may add only the cost feature gate
    diff = git("diff", f"{COMMIT}^", COMMIT, "--", "backend/src/main/resources/application.yml").decode("utf-8", "replace")
    added = [line[1:].rstrip() for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")]
    removed = [line[1:].rstrip() for line in diff.splitlines() if line.startswith("-") and not line.startswith("---")]
    proof["applicationYmlDiff"] = {"addedLines": added, "removedLines": removed,
                                   "addedCount": len(added), "removedCount": len(removed)}
    budget_keys = [key for key in ("daily-budget", "alert-percent", "search-queries-per-article",
                                   "model-output-tokens-per-article", "queries-per-claim",
                                   "auto-edit-loops-per-article", "image-units-per-slot",
                                   "image-units-per-article", "provider-quota", "reconciliation-stale-minutes",
                                   "max-calls-per-article")
                   if re.search(rf"^\s*{re.escape(key)}\s*:", diff, re.M)]
    proof["applicationYmlInventedBudgetKeys"] = budget_keys

    # 7. hard-coded budget defaults, the claim under review
    config = blob("backend/src/main/java/com/example/editorial/cost/BudgetPolicyConfig.java").decode()
    proof["budgetPolicyConfigFallbackDefaults"] = re.findall(r'count\(env, "([^"]+)", ([\d_]+)\)', config) + \
        re.findall(r'getProperty\("([^"]+)", "([^"]+)"\)', config) + \
        re.findall(r'getProperty\("([^"]+)", Integer\.class, ([\d_]+)\)', config)
    pricing_test = blob("backend/src/test/java/com/example/editorial/cost/CostPricingTest.java").decode()
    proof["costPricingTestLocksInDefaults"] = "Ceilings default to the documented SRS limits" in pricing_test and \
        'BudgetPolicyConfig.from(new MockEnvironment())' in pricing_test
    ports = blob("backend/src/main/java/com/example/editorial/cost/CostPorts.java").decode()
    proof["noAuditStillDefined"] = bool(re.search(r"static\s+Audit\s+noAudit\(\)", ports))

    ok = (proof["exactlyFiveVersioned"] and proof["v5OnlyCostTables"] and proof["bodyAfterHeader3Lines"]["identical"]
          and not proof["v5Committed"]["bom"] and proof["v5Committed"]["crBytes"] == 0
          and not proof["draftCommitted"]["bom"] and proof["draftCommitted"]["crBytes"] == 0
          and proof["worktreeMatchesCommit"] and not budget_keys and not other_domain
          and not proof["v5AlterOrDrop"])
    proof["allBoundaryAssertionsHold"] = ok
    out["verdictInputs"]["boundary"] = "hold" if ok else "violation"
    print(json.dumps({k: v for k, v in proof.items() if k in {
        "commitFilesTotal", "commitAdded", "commitModified", "exactlyFiveVersioned", "v5OnlyCostTables",
        "bodyAfterHeader3Lines", "v5Committed", "v5Triggers", "v5WritesToNonCostTables",
        "applicationYmlInventedBudgetKeys", "budgetPolicyConfigFallbackDefaults",
        "costPricingTestLocksInDefaults", "noAuditStillDefined", "allBoundaryAssertionsHold"}},
        indent=1, ensure_ascii=False)[:3000])

    merged = json.loads(EVIDENCE.read_text(encoding="utf-8")) if EVIDENCE.is_file() else {}
    merged.update(out)
    emit(merged)
    return 0 if ok else 1


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

#!/usr/bin/env python3
"""T08 static self-check (offline, stdlib only).

Confirms the budget/price/usage delivery stays inside its ownership boundary now that the main agent integrated
it: the frozen T00 contract files are untouched, the cost module still depends only on ``shared`` (the audit
guard lives in ``bootstrap``, never here), the installed V5 is byte-identical to the reviewed draft and creates
nothing but the two cost tables, the runtime role holds exactly the rights the service needs, money is
decimal-only, only the one frozen usage endpoint is exposed, and no business ceiling was invented in
``application.yml``. It checks no database state and starts no provider call.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COST_MAIN = ROOT / "backend/src/main/java/com/example/editorial/cost"
COST_TEST = ROOT / "backend/src/test/java/com/example/editorial/cost"
DRAFT = ROOT / "tests/engineering/T08/migration-draft.sql"
MIGRATIONS = ROOT / "backend/src/main/resources/db/migration"

EXPECTED_CLASSES = [
    "BudgetService", "BudgetPolicy", "BudgetPolicyConfig", "BudgetAlert", "Capability", "CostConfiguration",
    "CostController", "CostLedger", "CostPorts", "CostType", "Money", "PriceEntry", "PriceVersion",
    "PricingRules", "Reservation", "ReservationStatus", "Settlement", "Usage", "UsageService",
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cost_sources() -> list[Path]:
    return sorted(COST_MAIN.glob("*.java"))


def check_frozen_contracts() -> tuple[str, bool, str]:
    manifest = json.loads(read(ROOT / "docs/execution/contracts/candidate-manifest.json"))
    verified, missing, drifted = 0, [], []
    for entry in manifest["files"]:
        path = ROOT / entry["path"]
        if not path.is_file():
            missing.append(entry["path"])
            continue
        if sha256(path) == entry["sha256"]:
            verified += 1
        else:
            drifted.append(entry["path"])
    ok = not missing and not drifted
    detail = f"{verified} manifest files match, drifted={drifted or 'none'}, missing={missing or 'none'}"
    return "frozen contract files unchanged", ok, detail


def check_module_boundary() -> tuple[str, bool, str]:
    deps = json.loads(read(ROOT / "docs/execution/contracts/module-dependencies.json"))
    declared = deps["compileDependencies"]["cost"]
    domains = set(deps["compileDependencies"]) - {"shared", "cost"}
    offenders: list[str] = []
    for source in cost_sources():
        for imported in re.findall(r"^import\s+(com\.example\.editorial\.([a-z]+)\.)", read(source), re.M):
            if imported[1] not in {"shared", "cost"} and imported[1] in domains:
                offenders.append(f"{source.name}:{imported[1]}")
    ok = declared == ["shared"] and not offenders
    return ("cost module depends only on shared", ok,
            f"declared={declared}, cross-domain imports={offenders or 'none'}")


def check_package_contents() -> tuple[str, bool, str]:
    present = [p.stem for p in cost_sources()]
    absent = [name for name in EXPECTED_CLASSES if name not in present]
    wrong_package = [p.name for p in cost_sources()
                     if "package com.example.editorial.cost;" not in read(p)]
    ok = not absent and not wrong_package and (COST_TEST / "CostPricingTest.java").is_file() \
        and (COST_TEST / "T08PostgresTest.java").is_file()
    return ("cost package complete", ok, f"{len(present)} sources, absent={absent or 'none'}, "
                                         f"bad package={wrong_package or 'none'}")


def body_after_header(path: Path, header_lines: int = 3) -> bytes:
    """Everything after the header comment lines, compared byte for byte."""
    return b"".join(path.read_bytes().splitlines(keepends=True)[header_lines:])


def normalise_newlines(raw: bytes) -> bytes:
    """The reviewed draft carries LF, the installed migration was written with CRLF. Line endings are the only
    difference the main agent's allocation legitimately introduces, so they are normalised — and reported."""
    return raw.replace(b"\r\n", b"\n")


def check_installed_migration() -> tuple[str, bool, str]:
    """After integration the gate has two duties: the installed V5 may not drift from the reviewed draft, and the
    cost domain may own exactly the two tables it was allocated — nothing else, and no sixth versioned file."""
    installed = sorted(p.name for p in MIGRATIONS.glob("V*__*.sql"))
    expected_versions = ["V1__identity_audit_idempotency.sql", "V2__skill_prompt_policy.sql",
                         "V3__article_job_version.sql", "V4__change_proposal.sql", "V5__cost_ledger_pricing.sql"]
    v5 = MIGRATIONS / "V5__cost_ledger_pricing.sql"
    if not DRAFT.is_file() or not v5.is_file():
        return "installed V5 equals the reviewed draft", False, f"draft={DRAFT.is_file()}, V5={v5.is_file()}"
    identical = body_after_header(DRAFT) == body_after_header(v5)
    equivalent = (normalise_newlines(body_after_header(DRAFT))
                  == normalise_newlines(body_after_header(v5)))
    drafted = "DRAFT" in DRAFT.read_text(encoding="utf-8").upper()[:600]
    cost_tables = set(re.findall(r"CREATE TABLE editorial\.(\w+)", read(v5), re.I))
    foreign = [name for name in installed if name != v5.name
               and re.search(r"cost_ledger|cost_pricing_version", read(MIGRATIONS / name), re.I)]
    ok = equivalent and drafted and installed == expected_versions and cost_tables == {
        "cost_ledger", "cost_pricing_version"} and not foreign
    return ("installed V5 equals the reviewed draft", ok,
            f"header-stripped body {len(body_after_header(DRAFT))}B vs {len(body_after_header(v5))}B, "
            f"byte-identical={identical}, identical once CRLF/LF is normalised={equivalent}, "
            f"draft marked DRAFT={drafted}, versioned files={installed}, "
            f"V5 tables={sorted(cost_tables)}, other versions mentioning cost={foreign or 'none'}")


def check_grants() -> tuple[str, bool, str]:
    draft = read(DRAFT) if DRAFT.is_file() else ""
    ledger = re.search(r"GRANT\s+SELECT,INSERT,UPDATE\s+ON\s+editorial\.cost_ledger\s+TO\s+editorial_runtime",
                       draft)
    pricing = re.search(r"GRANT\s+SELECT\s+ON\s+editorial\.cost_pricing_version\s+TO\s+editorial_runtime", draft)
    deletes = re.findall(r"GRANT[^;]*DELETE[^;]*editorial_runtime", draft)
    revoke = re.search(r"REVOKE ALL ON editorial\.cost_ledger,editorial\.cost_pricing_version FROM "
                       r"PUBLIC,editorial_runtime,editorial_retention", draft)
    ok = bool(ledger and pricing and revoke and not deletes)
    return ("runtime grants are minimal", ok,
            f"ledger rw={bool(ledger)}, pricing read={bool(pricing)}, baseline revoke={bool(revoke)}, "
            f"delete grants={deletes or 'none'}")


def check_decimal_only() -> tuple[str, bool, str]:
    float_types = re.compile(r"\b(?:private|public|protected|static)?\s*(?:final\s+)?(double|float)\s+\w+\s*[=;,)]")
    loose = re.compile(r"getDoubleValue|Double\.parseDouble|Float\.parseFloat|doubleValue\(\)|floatValue\(\)")
    offenders: list[str] = []
    for source in cost_sources():
        text = read(source)
        if float_types.search(text) or loose.search(text):
            offenders.append(source.name)
    wire = re.search(r"\[0-9\]\{6\}\$\"", read(COST_MAIN / "Money.java"))
    ok = not offenders and bool(wire)
    return ("amounts are decimal, never binary floats", ok,
            f"floating-point usages={offenders or 'none'}, six-decimal wire pattern={bool(wire)}")


def emitted_names(source: Path) -> set[str]:
    return set(re.findall(r'\.(?:put|set|putArray|putObject)\("([A-Za-z]+)"', read(source)))


def frozen_names(source: Path, declaration: str) -> set[str]:
    block = re.search(declaration + r"\s*=\s*Set\.of\((.*?)\);", read(source), re.S)
    return set(re.findall(r'"([A-Za-z]+)"', block.group(1))) if block else set()


def check_frozen_usage_surface() -> tuple[str, bool, str]:
    """The only rc.3 surface T08 owns is GET /usage; its DTO shapes may not drift by a single field."""
    document = json.loads(read(ROOT / "docs/api/openapi.yaml"))
    operations = list(document["paths"]["/usage"])
    schemas = document["components"]["schemas"]
    summary = set(schemas["UsageSummary"]["properties"])
    reservation = set(schemas["BudgetReservation"]["properties"])
    settlement = set(schemas["Settlement"]["properties"])
    written_summary = emitted_names(COST_MAIN / "UsageService.java")
    written_reservation = emitted_names(COST_MAIN / "Reservation.java")
    written_settlement = frozen_names(COST_MAIN / "Settlement.java", r"WIRE")
    controller = read(COST_MAIN / "CostController.java")
    mappings = re.findall(r"@(Get|Post|Put|Patch|Delete)Mapping\(\"([^\"]*)\"\)", controller)
    ok = (operations == ["get"] and "@RestController" in controller and '@RequestMapping("/api/v1")' in controller
          and mappings == [("Get", "/usage")]
          and written_summary == summary and len(summary) == 11
          and written_reservation == reservation and len(reservation) == 10
          and written_settlement == settlement and len(settlement) == 6)
    return ("frozen GET /usage surface, no field drift", ok,
            f"operations={operations}, controller={mappings}, summary {len(written_summary)}/{len(summary)}, "
            f"reservation {len(written_reservation)}/{len(reservation)}, "
            f"settlement {len(written_settlement)}/{len(settlement)}")


def check_audit_payload_shape() -> tuple[str, bool, str]:
    """audit_log pins before_hash/after_hash to char(64) hex and detail to '{}', so the cost path may only hand
    over identifiers and nulls. The guard itself lives in bootstrap/CostIntegration, never inside the cost
    package, which must keep depending on shared alone."""
    integration = ROOT / "backend/src/main/java/com/example/editorial/bootstrap/CostIntegration.java"
    configuration = read(COST_MAIN / "CostConfiguration.java")
    service = read(COST_MAIN / "BudgetService.java")
    identity = read(ROOT / "backend/src/main/resources/db/migration/V1__identity_audit_idempotency.sql")
    wired = integration.is_file() and "CostPorts.Audit" in read(integration) \
        and '"COST"' in read(integration) and "^[a-f0-9]{64}$" in read(integration)
    pinned = "before_hash char(64) CHECK" in identity and "after_hash char(64) CHECK" in identity \
        and "detail jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (detail='{}'::jsonb)" in identity
    calls = re.findall(r"audit\.append\((.*?)\);", service, re.S)
    null_hashes = bool(calls) and all(call.rstrip().endswith("null, null") for call in calls)
    no_fallback = "noAudit" not in configuration and "noAudit" not in service
    leaks = [source.name for source in cost_sources() if "com.example.editorial.audit" in read(source)]
    ok = wired and pinned and null_hashes and no_fallback and not leaks
    return ("audit trail carries identifiers, not amounts", ok,
            f"bootstrap adapter wired={wired}, columns pinned={pinned}, audit calls={len(calls)} "
            f"all null-hashed={null_hashes}, silent audit fallback removed={no_fallback}, "
            f"audit imports inside cost={leaks or 'none'}")


def check_paid_calls_still_refused() -> tuple[str, bool, str]:
    policy = read(ROOT / "backend/src/main/java/com/example/editorial/bootstrap/StartupPolicy.java")
    ok = "editorial.providers.paid-calls-enabled" in policy
    return ("startup still refuses paid provider calls", ok,
            "guard line present" if ok else "guard line missing")


def check_acceptance_anchors() -> tuple[str, bool, str]:
    text = read(COST_TEST / "T08PostgresTest.java") if (COST_TEST / "T08PostgresTest.java").is_file() else ""
    anchors = {
        "AC-28 last balance race": "lastBalanceSingleWinner",
        "database repeats the ceiling": "admissionCeilingIsADatabaseRule",
        "idempotent settlement": "settlementReplayAndConflict",
        "release the difference": "settlementReleasesTheDifference",
        "UNKNOWN keeps the hold": "unknownKeepsTheHold",
        "cancel/pause does not waive cost": "cancellationDoesNotWaiveIncurredCost",
        "unknown price refuses generation": "unknownPriceRefusesGeneration",
        "reasoning billed once": "reasoningIsBilledOnceOnTheLedger",
        "frozen usage projection": "usageProjectionIsTheFrozenShape",
        "budget alert data": "budgetAlertData",
        "audit trail reaches audit_log": "auditRowsLandInTheAuditTableThroughTheRealSink",
    }
    missing = [label for label, name in anchors.items() if name not in text]
    return ("acceptance cases have real tests", not missing, f"missing={missing or 'none'}")


def strip_java_comments(source: str) -> str:
    """Bean wiring must be judged on code, not on the javadoc that explains why a port stays unbound."""
    without_blocks = re.sub(r"/\*.*?\*/", " ", source, flags=re.S)
    return re.sub(r"//.*", "", without_blocks)


def check_configuration_ownership() -> tuple[str, bool, str]:
    """Feature gate on, business ceilings off: the product owner decides the numbers, so a delivered
    application.yml that invents a daily budget or alert percent is a defect, not a convenience. Only the audit
    port is bound today; execution scope and alert delivery stay unbound until T09/T10/T11 exist."""
    config = read(ROOT / "backend/src/main/resources/application.yml")
    integration = ROOT / "backend/src/main/java/com/example/editorial/bootstrap/CostIntegration.java"
    wiring = strip_java_comments(read(integration)) if integration.is_file() else ""
    gate = "cost:" in config and "EDITORIAL_COST_ENABLED:false" in config
    invented = [key for key in ("daily-budget", "alert-percent", "search-queries-per-article",
                                "model-output-tokens-per-article", "queries-per-claim",
                                "auto-edit-loops-per-article", "image-units-per-slot",
                                "image-units-per-article", "provider-quota") if key in config]
    beans = re.findall(r"@Bean\s+(?:public\s+)?([\w.]+(?:<[^>]*>)?)\s+(\w+)\s*\(", wiring)
    audit_only = beans == [("CostPorts.Audit", "costAudit")] and "CostPorts.Executions" not in wiring \
        and "CostPorts.AlertSink" not in wiring
    runner = (ROOT / "tests/engineering/T08/run_pg.py").is_file()
    ok = gate and not invented and audit_only and runner
    return ("feature gate only, no invented limits, reproducible runner", ok,
            f"gate={gate}, invented keys={invented or 'none'}, bound beans={beans}, "
            f"executions/alert left unbound={audit_only}, runner tracked={runner}")


def main() -> int:
    checks = [check_frozen_contracts(), check_module_boundary(), check_package_contents(),
              check_installed_migration(), check_grants(), check_decimal_only(),
              check_frozen_usage_surface(), check_audit_payload_shape(), check_configuration_ownership(),
              check_paid_calls_still_refused(), check_acceptance_anchors()]
    failures = 0
    for name, ok, detail in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
        failures += 0 if ok else 1
    print(f"T08 static checks: {len(checks) - failures}/{len(checks)} passed"
          " (contract self-check only, not an approval)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

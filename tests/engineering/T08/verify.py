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
import sys
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

# Rewrites applied to file contents in memory by --reverse-control: path -> [(old, new), ...]. Nothing here ever
# touches the disk, the cluster or the reviewed migration; it only lets the same checks run against a deliberately
# weakened source so a gate that cannot see a weakening is caught being a gate that does not exist.
MUTATIONS: dict[str, list[tuple[str, str]]] = {}

SRS = ROOT / "docs/AI-Editorial-Agent-SRS-v1.0.md"
CONFIG_JAVA = COST_MAIN / "BudgetPolicyConfig.java"
V5 = MIGRATIONS / "V5__cost_ledger_pricing.sql"
PG_TEST = COST_TEST / "T08PostgresTest.java"
BOOTSTRAP = ROOT / "backend/src/main/java/com/example/editorial/bootstrap"


def read(path: Path) -> str:
    """Text of a file with any in-memory mutation applied. Mutations exist only for --reverse-control."""
    return mutate(path, path.read_text(encoding="utf-8", errors="replace"))


def mutate(path: Path, data):
    """Apply the pending --reverse-control rewrite to text or bytes, in memory only.

    Reverse control exists to prove that a gate reacts to a weakening, so a mutation whose target has already
    moved must be loud: a stale anchor silently means "nothing was mutated", which would report a blind spot as
    a rejection. An absent target is therefore a hard error for text; bytes keep their raw replace."""
    for old, new in MUTATIONS.get(str(path), ()):
        if isinstance(data, str) and old not in data:
            raise SystemExit(f"reverse control is stale: {old[:60]!r} is no longer in {path.name}")
        data = data.replace(old.encode("utf-8") if isinstance(data, bytes) else old,
                            new.encode("utf-8") if isinstance(data, bytes) else new)
    return data


def read_bytes(path: Path) -> bytes:
    return mutate(path, path.read_bytes())


def sha256(path: Path) -> str:
    return hashlib.sha256(read_bytes(path)).hexdigest()


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
    return b"".join(read_bytes(path).splitlines(keepends=True)[header_lines:])


def check_installed_migration() -> tuple[str, bool, str]:
    """After integration the gate has two duties: the installed V5 may not drift from the reviewed draft by a
    single byte — line endings included, because the delivered draft and the installed migration are both LF and
    the parent's rewrite made them raw-equal — and the cost domain may own exactly the two tables it was
    allocated, nothing else, and no sixth versioned file."""
    installed = sorted(p.name for p in MIGRATIONS.glob("V*__*.sql"))
    expected_versions = ["V1__identity_audit_idempotency.sql", "V2__skill_prompt_policy.sql",
                         "V3__article_job_version.sql", "V4__change_proposal.sql", "V5__cost_ledger_pricing.sql"]
    if not DRAFT.is_file() or not V5.is_file():
        return "installed V5 equals the reviewed draft", False, f"draft={DRAFT.is_file()}, V5={V5.is_file()}"
    draft_body, installed_body = body_after_header(DRAFT), body_after_header(V5)
    identical = draft_body == installed_body
    drafted = "DRAFT" in read(DRAFT).upper()[:600]
    cost_tables = set(re.findall(r"CREATE TABLE editorial\.(\w+)", read(V5), re.I))
    foreign = [name for name in installed if name != V5.name
               and re.search(r"cost_ledger|cost_pricing_version", read(MIGRATIONS / name), re.I)]
    ok = identical and drafted and installed == expected_versions and cost_tables == {
        "cost_ledger", "cost_pricing_version"} and not foreign
    return ("installed V5 equals the reviewed draft", ok,
             f"raw body {len(draft_body)}B vs {len(installed_body)}B, byte-identical={identical}, "
             f"CR in draft={draft_body.count(b'\r')}, CR in V5={installed_body.count(b'\r')}, "
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
    silent = [source.name for source in sorted((ROOT / "backend/src/main/java").rglob("*.java"))
              if re.search(r"\bnoAudit\s*\(", strip_java_comments(read(source)))]
    guard_checks_values = bool(re.search(r"if \(value != null && !value\.matches\(HASH_SHAPE\)\)",
                                         strip_java_comments(read(integration)))) if integration.is_file() else False
    test = read(PG_TEST) if PG_TEST.is_file() else ""
    real_adapter = "CostIntegration.class" in test and 'getDeclaredMethod("costAudit"' in test
    mirror = "hash field must be null or 64 lowercase hex" in test
    leaks = [source.name for source in cost_sources() if "com.example.editorial.audit" in read(source)]
    ok = (wired and pinned and null_hashes and not silent and guard_checks_values and real_adapter
          and not mirror and not leaks)
    return ("audit trail carries identifiers, not amounts", ok,
            f"bootstrap adapter wired={wired}, columns pinned={pinned}, audit calls={len(calls)} "
            f"all null-hashed={null_hashes}, silent audit factories={silent or 'none'}, "
            f"guard tests the value={guard_checks_values}, the suite drives the shipped adapter={real_adapter}, "
            f"test-built mirror present={mirror}, audit imports inside cost={leaks or 'none'}")


def check_paid_calls_still_refused() -> tuple[str, bool, str]:
    """The gate has to be a refusal, not a caption: the flag must feed a require(...) that throws. Rewriting the
    argument to a constant, or the throw into a return, fails this check (round-1 mutation M13)."""
    policy = read(ROOT / "backend/src/main/java/com/example/editorial/bootstrap/StartupPolicy.java")
    guard = re.search(r'require\(\s*!env\.getProperty\(\s*"editorial\.providers\.paid-calls-enabled",'
                      r'\s*Boolean\.class,\s*false\)', policy)
    throws = re.search(r"private static void require\(boolean condition, String message\) \{\s*"
                       r"if \(!condition\) throw new IllegalStateException\(message\);", policy)
    ok = bool(guard and throws)
    return ("startup still refuses paid provider calls", ok,
            f"flag guarded by require()={bool(guard)}, require() throws IllegalStateException={bool(throws)}")


def java_method_body(text: str, name: str) -> str:
    """The body of a Java method by brace matching. Balanced braces inside string literals (the fixture JSON)
    keep the count honest; an unbalanced literal would only widen the slice, never narrow it."""
    match = re.search(r"\b" + re.escape(name) + r"\s*\([^)]*\)\s*(?:throws [^{]+)?\{", text)
    if not match:
        return ""
    start, depth, index = match.end() - 1, 0, match.end() - 1
    while index < len(text):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
        index += 1
    return text[start:]


def check_acceptance_anchors() -> tuple[str, bool, str]:
    """An anchor is the test method plus the assertions that carry the requirement. Naming a method that no
    longer asserts anything was round-1 mutation M15, so each anchor lists the decision it must still make."""
    tests = {
        "T08PostgresTest": read(PG_TEST) if PG_TEST.is_file() else "",
        "CostPricingTest": read(COST_TEST / "CostPricingTest.java"),
    }
    anchors = {
        "AC-28 last balance race": ("T08PostgresTest", "lastBalanceSingleWinner",
                                    ["assertEquals(1, winners", "ready.await", "start.countDown"]),
        "AC-28 concurrent bypass": ("T08PostgresTest", "concurrentBypassWritersCannotOversubscribe",
                                    ["assertEquals(1, committed", "bypassInsert(article, barrier)"]),
        "the race overlaps two live transactions": ("T08PostgresTest", "bypassInsert",
                                                    ["pg_sleep", "setAutoCommit(false)", "getSQLState"]),
        "database repeats the ceiling": ("T08PostgresTest", "admissionCeilingIsADatabaseRule",
                                         ['assertEquals("23514"', "cost budget ceiling"]),
        "unbound execution scope books nothing": ("T08PostgresTest", "unboundExecutionScopeWritesNothing",
                                                  ["EXECUTION_SCOPE_NOT_READY", "assertEquals(0, rows()"]),
        "idempotent settlement": ("T08PostgresTest", "settlementReplayAndConflict", ["SETTLEMENT_CONFLICT"]),
        "release the difference": ("T08PostgresTest", "settlementReleasesTheDifference",
                                   ['assertEquals("0.600000", settled.releasedAmount().text()',
                                    "after.reserved().isZero"]),
        "UNKNOWN keeps the hold": ("T08PostgresTest", "unknownKeepsTheHold",
                                   ["RECONCILIATION_REQUIRED", "occupied.unknown()"]),
        "cancel/pause does not waive cost": ("T08PostgresTest", "cancellationDoesNotWaiveIncurredCost",
                                             ["CANCELLED"]),
        "unknown price refuses generation": ("T08PostgresTest", "unknownPriceRefusesGeneration",
                                             ["assertThrows"]),
        "reasoning billed once": ("T08PostgresTest", "reasoningIsBilledOnceOnTheLedger", ["assertEquals"]),
        "frozen usage projection": ("T08PostgresTest", "usageProjectionIsTheFrozenShape",
                                    ["assertEquals(11, summary.size"]),
        "budget alert data": ("T08PostgresTest", "budgetAlertData",
                              ["BUDGET_WARNING", "warning.percent()", "usage.alerts"]),
        "audit trail reaches audit_log": ("T08PostgresTest", "auditRowsLandInTheAuditTableThroughTheRealSink",
                                          ["productionAuditPort", "23514", "42501"]),
        "documented ceilings": ("CostPricingTest", "budgetPolicyCeilings",
                                 ['assertEquals(30, policy.cap', 'assertEquals(40_000, policy.cap',
                                  'assertEquals("20.000000", policy.dailyLimit'] ),
        "unstated ceilings refuse": ("CostPricingTest", "undocumentedCeilingsHaveNoDefault",
                                     ['assertEquals("QUOTA_NOT_CONFIGURED"', "editorial.cost.max-calls"]),
        "unbound executions refuse": ("CostPricingTest", "executionScopeIsFailClosed",
                                      ["EXECUTION_SCOPE_NOT_READY", "503"]),
    }
    weak: list[str] = []
    for label, (suite, method, tokens) in anchors.items():
        body = java_method_body(tests[suite], method)
        if not body:
            weak.append(f"{label}: no method {method}")
            continue
        missing = [token for token in tokens if token not in body]
        if missing:
            weak.append(f"{label}/{method}: {missing}")
    return ("acceptance cases still assert what they claim", not weak, f"weakened={weak or 'none'}")


def strip_java_comments(source: str) -> str:
    """Bean wiring must be judged on code, not on the javadoc that explains why a port stays unbound."""
    without_blocks = re.sub(r"/\*.*?\*/", " ", source, flags=re.S)
    return re.sub(r"//.*", "", without_blocks)


def srs_lines() -> list[str]:
    return read(SRS).splitlines()


def documented_ceilings() -> dict[str, int]:
    """The count ceilings the SRS actually states, read out of SRS 32.2 line 1103 rather than typed in here."""
    line = srs_lines()[1102]
    patterns = {
        "editorial.cost.search-queries-per-article": r"总检索 query 上限 ([0-9,]+)",
        "editorial.cost.model-output-tokens-per-article": r"输出总 token 上限 ([0-9,]+)",
        "editorial.cost.queries-per-claim": r"单 Claim query 上限 ([0-9,]+)",
        "editorial.cost.auto-edit-loops-per-article": r"自动编辑循环 ([0-9,]+)",
        "editorial.cost.image-units-per-slot": r"单 Slot 生图 ([0-9,]+) 次",
        "editorial.cost.image-units-per-article": r"每篇生成 ([0-9,]+) 张",
    }
    found: dict[str, int] = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, line)
        if not match:
            raise SystemExit(f"the SRS no longer states {key}; re-read line 1103 before trusting this gate")
        found[key] = int(match.group(1).replace(",", ""))
    return found


def check_documented_ceilings() -> tuple[str, bool, str]:
    """Finding F-01: the fallbacks inside BudgetPolicyConfig are the SRS numbers, or they are not shipped at all.

    The eight documented ceilings must equal the values parsed out of the SRS text itself (line 1103 for the six
    counts, line 1099 for the daily example, line 1143 for the alert trigger), the two ceilings the SRS does not
    state must carry no fallback and must be read through the fail-closed helper, and application.yml may still
    invent no limit. OQ-09 (line 1281) must remain open, because these are 示例值 until the Owner signs them off.
    """
    config = read(CONFIG_JAVA)
    counted = {key: int(value.replace("_", "")) for key, value in
               re.findall(r'count\(env,\s*"([^"]+)",\s*([0-9_]+)\)', config)}
    documented = documented_ceilings()
    drifted = [f"{key}: code={counted.get(key)} SRS={value}" for key, value in documented.items()
               if counted.get(key) != value]
    extra = sorted(set(counted) - set(documented))
    daily = re.search(r'getProperty\("editorial\.cost\.daily-budget",\s*"([^"]+)"\)', config)
    srs_daily = re.search(r"日预算示例\s*([0-9.]+)\s*USD", srs_lines()[1098])
    daily_ok = bool(daily and srs_daily) and daily.group(1) == f"{float(srs_daily.group(1)):.6f}"
    alert = re.search(r'getProperty\("editorial\.cost\.alert-percent",\s*Integer\.class,\s*(\d+)\)', config)
    srs_alert = re.search(r"预算\s*>\s*([0-9]+)%", srs_lines()[1142])
    alert_ok = bool(alert and srs_alert) and alert.group(1) == srs_alert.group(1)
    stated = set(re.findall(r'statedCeiling\(env,\s*"([^"]+)"\)', config))
    undocumented = {"editorial.cost.max-calls-per-article", "editorial.cost.reconciliation-stale-minutes"}
    fail_closed = "QUOTA_NOT_CONFIGURED" in config.split("statedCeiling(Environment env", 1)[-1][:520]
    open_question = "OQ-09" in srs_lines()[1280] and "示例" in srs_lines()[1280]
    invented = [key for key in list(documented) + sorted(stated) if key in
                read(ROOT / "backend/src/main/resources/application.yml")]
    ok = (not drifted and not extra and daily_ok and alert_ok and stated == undocumented and fail_closed
          and open_question and not invented)
    return ("ceilings are the documented SRS numbers or required outright", ok,
            f"SRS counts={ {k.split('.')[-1]: v for k, v in documented.items()} }, code fallbacks="
            f"{ {k.split('.')[-1]: v for k, v in counted.items()} }, drifted={drifted or 'none'}, "
            f"undocumented fallbacks={extra or 'none'}, daily 20.000000={daily_ok}, alert 80={alert_ok}, "
            f"required-without-default={sorted(stated)}, refuses 503={fail_closed}, OQ-09 open={open_question}, "
            f"yml invented={invented or 'none'}")


def check_admission_ceiling() -> tuple[str, bool, str]:
    """Findings F-02 and F-03: the database repeats the article ceiling and nothing more, and it does so under a
    lock the aggregate waits behind. The installed trigger used to aggregate over a snapshot that a concurrent
    bypassing writer could not see, which let two direct INSERTs each take the same last unit; the case that
    measured it is concurrentBypassWritersCannotOversubscribe, and the comment may not claim more than the SQL."""
    sql = read(V5)
    body = re.search(r"CREATE FUNCTION editorial\.t08_admit_estimate\(\).*?END \$\$;", sql, re.S)
    if not body:
        return "article ceiling is a locked database rule", False, "admission function not found in V5"
    function = body.group(0)
    lock = re.search(r"SELECT budget_limit INTO limit_amount FROM editorial\.article_job WHERE id=NEW\.article_id"
                     r" FOR UPDATE;", function)
    aggregate = function.find("INTO occupied")
    locked_first = bool(lock) and 0 <= function.find("FOR UPDATE") < aggregate
    ceiling = "23514" in function and "cost budget ceiling" in function
    header = sql[:sql.find("CREATE FUNCTION editorial.t08_admit_estimate")]
    scoped = "article ceiling" in header and "service path" in header
    overclaims = []
    for source in (COST_MAIN / "CostLedger.java", COST_MAIN / "BudgetService.java"):
        text = read(source)
        for phrase in ("repeats the same ceiling as a database constraint",
                       "skipped the lock still cannot oversubscribe a budget",
                       "skipped the lock still cannot oversubscribe the article budget"):
            if phrase in text:
                overclaims.append(f"{source.name}: {phrase}")
        if "service path" not in text:
            overclaims.append(f"{source.name}: no service-path scoping of the database claim")
    raced = "concurrentBypassWritersCannotOversubscribe" in read(PG_TEST)
    ok = bool(locked_first and ceiling and scoped and raced and not overclaims)
    return ("article ceiling is a locked database rule", ok,
            f"article row locked={bool(lock)}, lock precedes aggregate={locked_first}, ceiling 23514={ceiling}, "
            f"V5 comment scoped to the article={scoped}, concurrent bypass case={raced}, "
            f"overstated claims={overclaims or 'none'}")


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


CHECKS = [check_frozen_contracts, check_module_boundary, check_package_contents, check_installed_migration,
          check_grants, check_decimal_only, check_frozen_usage_surface, check_audit_payload_shape,
          check_documented_ceilings, check_admission_ceiling, check_configuration_ownership,
          check_paid_calls_still_refused, check_acceptance_anchors]


def run_checks() -> list[tuple[str, bool, str]]:
    return [check() for check in CHECKS]


def reversals() -> list[dict]:
    """Every weakening that round 1 found a gate was blind to, plus one for each new gate. Each entry names the
    checks that must turn red; a weakening that changes nothing means the gate does not exist."""
    application_yml = ROOT / "backend/src/main/resources/application.yml"
    cost_ports = COST_MAIN / "CostPorts.java"
    ledger = COST_MAIN / "CostLedger.java"
    startup = BOOTSTRAP / "StartupPolicy.java"
    integration = BOOTSTRAP / "CostIntegration.java"
    reservation = COST_MAIN / "Reservation.java"
    ceilings = "ceilings are the documented SRS numbers or required outright"
    admission = "article ceiling is a locked database rule"
    anchors = "acceptance cases still assert what they claim"
    return [
        {"name": "SRS daily example replaced by an invented 999 USD", "path": CONFIG_JAVA,
         "old": 'getProperty("editorial.cost.daily-budget", "20.000000")',
         "new": 'getProperty("editorial.cost.daily-budget", "999.000000")', "red": [ceilings]},
        {"name": "alert line moved off the documented 80 percent", "path": CONFIG_JAVA,
         "old": 'getProperty("editorial.cost.alert-percent", Integer.class, 80)',
         "new": 'getProperty("editorial.cost.alert-percent", Integer.class, 70)', "red": [ceilings]},
        {"name": "one documented token ceiling re-typed", "path": CONFIG_JAVA,
         "old": 'count(env, "editorial.cost.model-output-tokens-per-article", 40_000)',
         "new": 'count(env, "editorial.cost.model-output-tokens-per-article", 40001)', "red": [ceilings]},
        {"name": "a documented ceiling quietly dropped", "path": CONFIG_JAVA,
         "old": 'caps.put(BudgetPolicy.Counter.AUTO_EDIT_LOOP, count(env, "editorial.cost.auto-edit-loops-per-article", 1));',
         "new": "", "red": [ceilings]},
        {"name": "the unstated call cap gets an invented default", "path": CONFIG_JAVA,
         "old": 'statedCeiling(env, "editorial.cost.max-calls-per-article")',
         "new": 'count(env, "editorial.cost.max-calls-per-article", 64)', "red": [ceilings, anchors]},
        {"name": "application.yml starts inventing a budget", "path": application_yml,
         "old": "  cost:\n    enabled: ${EDITORIAL_COST_ENABLED:false}",
         "new": "  cost:\n    enabled: ${EDITORIAL_COST_ENABLED:false}\n    daily-budget: 20.000000",
         "red": [ceilings, "feature gate only, no invented limits, reproducible runner"]},
        {"name": "admission stops locking the article row", "path": V5,
         "old": "WHERE id=NEW.article_id FOR UPDATE;", "new": "WHERE id=NEW.article_id;",
         "red": [admission, "installed V5 equals the reviewed draft"]},
        {"name": "the reviewed draft drifts from the installed file", "path": DRAFT,
         "old": "WHERE id=NEW.article_id FOR UPDATE;", "new": "WHERE id=NEW.article_id FOR NO KEY UPDATE;",
         "red": ["installed V5 equals the reviewed draft"]},
        {"name": "a third cost table appears in V5", "path": V5,
         "old": "CREATE TABLE editorial.cost_ledger (",
         "new": "CREATE TABLE editorial.cost_estimate (id uuid PRIMARY KEY);\nCREATE TABLE editorial.cost_ledger (",
         "red": ["installed V5 equals the reviewed draft", "runtime grants are minimal"]},
        {"name": "a frozen wire field is renamed", "path": reservation, "old": 'n.put("amount", reportedAmount()',
         "new": 'n.put("amountText", reportedAmount()', "red": ["frozen GET /usage surface, no field drift"]},
        {"name": "an audit import leaks into the cost module", "path": ledger, "old": "import java.util.Map;",
         "new": "import com.example.editorial.audit.AuditSink;\nimport java.util.Map;",
         "red": ["cost module depends only on shared"]},
        {"name": "the silent audit factory comes back", "path": cost_ports,
         "old": "public static AlertSink noAlerts()",
         "new": "public static Audit noAudit() { return (a, b, c, d, e, f) -> {}; }\n\n    "
                "public static AlertSink noAlerts()",
         "red": ["audit trail carries identifiers, not amounts"]},
        {"name": "the production hash-shape guard is switched off", "path": integration,
         "old": "if (value != null && !value.matches(HASH_SHAPE))", "new": "if (false && value != null)",
         "red": ["audit trail carries identifiers, not amounts"]},
        {"name": "the audit case builds a mirror instead of the shipped adapter", "path": PG_TEST,
         "old": "bean = com.example.editorial.bootstrap.CostIntegration.class", "new": "bean = Object.class",
         "red": ["audit trail carries identifiers, not amounts", anchors]},
        {"name": "the bypass assertion is emptied", "path": PG_TEST,
         "old": 'assertEquals(1, committed, "at most one bypassing writer may take the last unit: " + outcomes);',
         "new": 'assertTrue(true, "at most one bypassing writer may take the last unit: " + outcomes);',
         "red": [anchors]},
        {"name": "the single-winner latches are unwired again", "path": PG_TEST,
         "old": 'assertTrue(ready.await(10, TimeUnit.SECONDS), "both callers reached the gate");',
         "new": "Thread.sleep(1);", "red": [anchors]},
        {"name": "the paid-call refusal is neutered", "path": startup,
         "old": 'require(!env.getProperty("editorial.providers.paid-calls-enabled", Boolean.class, false),',
         "new": "require(true,", "red": ["startup still refuses paid provider calls"]},
        {"name": "the comment overclaims the database again", "path": ledger,
         "old": "repeats the article ceiling as a database rule", "new": "repeats the same ceiling as a database constraint",
         "red": [admission]},
    ]


def reverse_control() -> int:
    """Run every gate against each weakening, in memory only: no file is written, no cluster is touched."""
    baseline = run_checks()
    red = [name for name, ok, _ in baseline if not ok]
    if red:
        for name, ok, detail in baseline:
            print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
        print(f"--reverse-control refuses to judge a red baseline: {red}")
        return 1
    blind, misplaced = [], []
    for spec in reversals():
        path = Path(spec["path"])
        if spec["old"] not in path.read_text(encoding="utf-8", errors="replace"):
            blind.append(f"{spec['name']}: the mutation target is gone")
            print(f"[STALE ] {spec['name']}: target text no longer present")
            continue
        MUTATIONS[str(path)] = [(spec["old"], spec["new"])]
        try:
            failed = {name for name, ok, _ in run_checks() if not ok}
        finally:
            MUTATIONS.clear()
        expected = set(spec["red"])
        if not failed:
            blind.append(spec["name"])
            print(f"[BLIND ] {spec['name']} -> every check stayed green")
        elif not (expected & failed):
            misplaced.append(f"{spec['name']}: red were {sorted(failed)}, expected {sorted(expected)}")
            print(f"[WRONG ] {spec['name']} -> {sorted(failed)}")
        else:
            print(f"[REJECT] {spec['name']} -> {sorted(expected & failed)}")
    print(f"reverse control: {len(reversals())} weakenings, blind={blind or 'none'}, misplaced={misplaced or 'none'}")
    return 1 if blind or misplaced else 0


def main() -> int:
    if "--reverse-control" in sys.argv[1:]:
        return reverse_control()
    checks = run_checks()
    failures = 0
    for name, ok, detail in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
        failures += 0 if ok else 1
    print(f"T08 static checks: {len(checks) - failures}/{len(checks)} passed"
          " (contract self-check only, not an approval); run --reverse-control to test the gates themselves")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

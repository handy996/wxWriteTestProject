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
                                  'assertEquals("20.000000", policy.dailyLimit']),
        "model quota scope reaches its lookup": ("CostPricingTest", "modelLevelQuotaReachesTheLookupThatReadsIt",
                                                 ['assertEquals(1, policy.modelQuota("mock", "mock-model")',
                                                  'Set.of("mock", "mock|mock-model")']),
        "model and provider windows each bind": ("T08PostgresTest",
                                                 "modelAndProviderQuotaScopesEachBindTheirWindow",
                                                 ["BudgetPolicy.scope(PROVIDER, MODEL)", "assertEquals(3, holds()"]),
        "unlisted provider follows the stated policy": ("T08PostgresTest",
                                                        "unlistedProviderFollowsTheStatedQuotaPolicy",
                                                        ["PROVIDER_QUOTA_NOT_CONFIGURED", "assertEquals(0, rows()"]),
        "quota case binds a real YAML document": ("CostPricingTest",
                                                 "quotaWrittenAsNestedYamlBindsTheScopeTheLookupReads",
                                                 ["new YamlPropertySourceLoader()",
                                                  "BudgetPolicyConfig.from(env)",
                                                  'policy.modelQuota("mock", "mock-model")',
                                                  'policy.providerWideQuota("mock")',
                                                  "INVALID_PROVIDER_QUOTA_KEY",
                                                  "BudgetPolicy.UnconfiguredQuota.REFUSE"]),
        "live quota case is fed by the bound environment": ("T08PostgresTest",
                                                            "nestedYamlQuotaIsEnforcedByTheService",
                                                            ["new YamlPropertySourceLoader()",
                                                             "BudgetPolicyConfig.from(env)",
                                                             "activePolicy.providerWideQuota(PROVIDER)",
                                                             "PROVIDER_QUOTA_EXCEEDED"]),
        "env-shaped quota binds instead of vanishing": ("CostPricingTest",
                                                        "quotaSuppliedThroughEnvironmentStyleNamesBinds",
                                                        ['os.put("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MAX_CONCURRENT", "2")',
                                                         'policy.providerWideQuota("mock")',
                                                         "INVALID_PROVIDER_QUOTA_KEY"]),
        "the env-shaped test source really is env-shaped": ("CostPricingTest", "environmentShaped",
                                                            ["SystemEnvironmentPropertySource",
                                                             "getPropertySources().addFirst"]),
        "quota leaves are normalised at assembly": ("CostPricingTest",
                                                    "quotaLeavesAreNormalisedAtAssembly",
                                                    ['"three"', "INVALID_BUDGET_POLICY",
                                                     "new BudgetPolicy.ProviderQuota(0, 5)",
                                                     'closedDay.providerWideQuota("mock")']),
        "both levels answer their own entry": ("CostPricingTest", "bothQuotaLevelsAnswerTheirOwnEntries",
                                               ['layered.modelQuota("mock", "mock-model-v2").isEmpty()',
                                                'layered.modelQuota("mock", "gpt-4.1").isEmpty()',
                                                "layered.providerWideQuota(\"mock\")"]),
        "separator ids refused not collided": ("CostPricingTest", "separatorBearingIdsAreRefusedNotCollided",
                                               ['BudgetPolicy.scope("p|q", null)', '"p||q"',
                                                "INVALID_PROVIDER_QUOTA_KEY"]),
        "a looser model entry cannot lift the provider ceiling": ("T08PostgresTest",
                                                                  "looserModelEntryCannotLiftTheProviderCeiling",
                                                                  ["ProviderQuota(2, 30)", "ProviderQuota(5, 30)",
                                                                   "PROVIDER_QUOTA_EXCEEDED",
                                                                   "assertEquals(2, holds()"]),
        "the provider day window closes first": ("T08PostgresTest",
                                                 "providerDayWindowClosesBeforeTheLooserModelDayWindow",
                                                 ["ProviderQuota(3, 2)", "ProviderQuota(5, 5)",
                                                  "PROVIDER_QUOTA_EXCEEDED"]),
        "zero calls-per-day is a closed day, not a wedged boot": ("T08PostgresTest",
                                                                  "zeroCallsPerDayClosesTheDayButNotTheBoot",
                                                                  ["ProviderQuota(2, 0)",
                                                                   "PROVIDER_QUOTA_EXCEEDED",
                                                                   "assertEquals(0, rows()"]),
        "a dotted model id is metered provider-wide": ("T08PostgresTest",
                                                       "dottedModelIdIsMeteredInTheProviderWindow",
                                                       ['hold(article, "gpt-4.1")', "ProviderQuota(2, 30)",
                                                        "PROVIDER_QUOTA_EXCEEDED"]),
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
    # F2-02: anchor on the lock statement's own position, not on the first "FOR UPDATE" the function contains. A
    # decoy comment naming FOR UPDATE would otherwise satisfy the ordering while the real lock sat after the
    # aggregate, which is the exact bug the lock exists to prevent.
    decoys = [match for match in re.finditer(r"FOR UPDATE", function)
              if not lock or not (lock.start() <= match.start() < lock.end())]
    locked_first = bool(lock) and 0 <= lock.start() < aggregate and not decoys
    found_guard = bool(lock) and "IF NOT FOUND" in function[lock.end():lock.end() + 160]
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
    ok = bool(locked_first and found_guard and ceiling and scoped and raced and not overclaims)
    return ("article ceiling is a locked database rule", ok,
            f"article row locked={bool(lock)}, lock statement precedes aggregate={locked_first}, "
            f"stray FOR UPDATE text in the function={[m.start() for m in decoys] or 'none'}, "
            f"missing-row guard follows the lock={found_guard}, ceiling 23514={ceiling}, "
            f"V5 comment scoped to the article={scoped}, concurrent bypass case={raced}, "
            f"overstated claims={overclaims or 'none'}")


def check_quota_scope_spelling() -> tuple[str, bool, str]:
    """Finding F2-01 and the round-3 findings stacked on it. One method owns the scope spelling and both sides go
    through it — scanned across the whole cost module now, because a scan of two files was a scan that missed
    (F-06). The two configured levels are enforced side by side and each answers only its own exact key (ruling
    F-03; variant probe V4's prefix widening is refused by construction). Ids outside [A-Za-z0-9._-] cannot reach
    the separator and collide (F-05). The OS-environment channel binds like the file channel instead of silently
    producing an empty provider map (F-01). Unreadable leaf values arrive as the structured 503, not a conversion
    stack, and the two zeros keep their distinct meanings (F-08). And the binding evidence lives inside the method
    bodies of the cases that assert on it, not in the files' general vicinity (F-02)."""
    policy = read(COST_MAIN / "BudgetPolicy.java")
    config = read(COST_MAIN / "BudgetPolicyConfig.java")
    service = read(COST_MAIN / "BudgetService.java")
    module = "".join(read(source) for source in cost_sources())
    definition = re.search(r"public static String scope\(String provider, String model\)", policy)
    scope_body = java_method_body(policy, "scope")
    canonical = bool(re.search(r'provider \+ "\|" \+ model', scope_body))
    # Exactly one join of a provider and a model into a scope may exist in the module: the one inside scope().
    # A second one anywhere — ledger, service, a future file — is a second spelling, and a second spelling is how
    # a configured ceiling silently reads as none (round-3 finding F-06 extended the two-file scan to the module).
    # Comments are stripped first: the gate judges the code, not the prose that explains the code.
    module = "".join(strip_java_comments(read(source)) for source in cost_sources())
    joined = re.findall(r'provider\s*\+\s*"([._|])"\s*\+\s*model', module)
    writers = len(re.findall(r"BudgetPolicy\.scope\(", config))
    readers = len(re.findall(r"\bscope\(provider, (?:model|null)\)", policy))
    # indexOf is accepted alongside contains on purpose: the verdict is "the dotted shape is refused", not the
    # spelling of the check (a benign re-typing must keep this gate green — see --reverse-control's probes).
    malformed_refused = "INVALID_PROVIDER_QUOTA_KEY" in policy and bool(
        re.search(r'stored\.(?:contains|indexOf)\("\."\)', policy))
    segment_shape = bool(re.search(r'Pattern\.compile\("\[A-Za-z0-9\._-\]\+"\)', policy)) \
        and "SEGMENT_SHAPE.matcher(provider).matches()" in policy \
        and "SEGMENT_SHAPE.matcher(model).matches()" in policy
    # The reserved switch leaf shares the namespace with provider names, so a provider called unconfigured has to
    # be refused where its quota leaves live, not skipped the way the switch itself is.
    reserved_switch_refused = bool(re.search(
        r"if \(path\.length < 2 \|\| UNCONFIGURED_LEAF\.equals\(path\[0\]\)\) \{\s*\n"
        r"\s*throw new PublicFailure\(503, \"INVALID_PROVIDER_QUOTA_KEY\"\);", config))
    both_leaves = "QUOTA_NOT_CONFIGURED" in config and "held == null || calls == null" in config
    no_invented_open = "Integer.MAX_VALUE" not in config and "Long.MAX_VALUE" not in config
    unconfigured_required = bool(re.search(r'statedValue\(env, QUOTA_PREFIX \+ UNCONFIGURED_LEAF\)', config)) \
        and 'getProperty("editorial.cost.provider-quota.unconfigured"' not in config
    unlisted_refused = "PROVIDER_QUOTA_NOT_CONFIGURED" in service \
        and "UnconfiguredQuota.REFUSE" in service
    # Round-3 ruling F-03 in the shapes that carry it: each level answers its own entry (containsKey on the two
    # scopes built by scope()), the service keeps EVERY window whose entry exists — the exact expression, so
    # .limit(1) "first entry only" cannot paraphrase it away — and measures the provider-wide rows across models
    # with the model window kept separate. Both where-clauses must be present, not one reused for both numbers.
    two_tier = [
        bool(re.search(r"Optional<ProviderQuota>\s+modelQuota\(String provider, String model\)", policy))
        and bool(re.search(r"Optional<ProviderQuota>\s+providerWideQuota\(String provider\)", policy)),
        "providers.containsKey(exact)" in policy and "providers.containsKey(wide)" in policy,
        "policy.modelQuota(provider, model)" in service and "policy.providerWideQuota(provider)" in service,
        "filter(ceiling -> ceiling.quota() != null).toList()" in service
        and "for (Ceiling window : windows)" in service,
        "l.owner_id=? AND l.provider=? AND l.model=? AND l.bucket_day=?" in service
        and "l.owner_id=? AND l.provider=? AND l.bucket_day=?" in service,
        # Each window is built exactly when its entry answered — the conditions are load-bearing text, because
        # an `if (false)` keeps the SQL string present while never adding the window the ruling requires.
        "if (modelEntry.isPresent())" in service and "if (wideEntry.isPresent())" in service,
    ]
    # Variant probe V4: a prefix match would answer mock-model to mock-model-v2 and silently widen a ceiling.
    model_exact = "startsWith" not in java_method_body(policy, "modelQuota")
    # F2-01's original defect was a config-side key built by string surgery. "writers >= 2" alone could still
    # pass with only one channel keying through scope() while the other hand-built the dotted path again —
    # reverse control caught that blind spot, so every key-building site is pinned by name.
    config_keys_by_scope = bool(re.search(r"case 2 -> BudgetPolicy\.scope\(path\[0\], null\);", config)) \
        and bool(re.search(r"case 3 -> BudgetPolicy\.scope\(path\[0\], path\[1\]\);", config)) \
        and "String scope = BudgetPolicy.scope(provider, null);" in config
    # Finding F-01: the environment channel is recognised, enumerated like any other source, and every leaf read
    # through Spring's own Binder; and the one shape that channel cannot disambiguate (A_B_C reading two ways)
    # is refused rather than guessed.
    env_channel = [
        "instanceof SystemEnvironmentPropertySource" in config
        and '"editorial_cost_provider_quota_"' in config
        and bool(re.search(r"Binder\.get\(configurable\)", config)),
        "environmentQuotaName(binder, name" in config and "canonicalQuotaName(binder, name" in config,
        "tail.length - leafParts != 1" in config,
    ]
    # Finding F-08: the conversion failure is normalized, and the zeros keep their distinct meanings.
    leaf_normalised = bool(re.search(r"catch \(BindException \| org\.springframework\.core\.convert\."
                                     r"ConversionFailedException", config))
    zero_semantics = "maxConcurrent < 1" in policy and "callsPerDay < 0" in policy
    report = read(ROOT / "docs/execution/reports/T08.md")
    documented = ["max-concurrent" in config, "calls-per-day" in config,
                  "provider-quota.unconfigured" in config, "[_<model>]" not in config,
                  "max-concurrency" not in report, "daily-calls" not in report]
    # The same defect can hide one layer up: the cases above could bind flat test keys while the real YAML document
    # produced a different shape. Round-3 finding F-02 moved the verdict INTO the case bodies: the loader call,
    # the document bytes and BudgetPolicyConfig.from(env) must sit inside the method that asserts the result, the
    # live service must be fed the policy that from(env) produced (inline or via a local — both benign spellings
    # of the same claim), and the unit body may not smuggle flat hand-fed quota keys past the loader.
    unit = read(COST_TEST / "CostPricingTest.java")
    live = read(PG_TEST)
    unit_body = java_method_body(unit, "quotaWrittenAsNestedYamlBindsTheScopeTheLookupReads")
    live_body = java_method_body(live, "nestedYamlQuotaIsEnforcedByTheService")

    def bound_in(body: str) -> bool:
        return (bool(re.search(r"new\s+YamlPropertySourceLoader\s*\(\s*\)", body))
                and "document.getBytes" in body and "new ByteArrayResource(" in body
                and bool(re.search(r"BudgetPolicyConfig\s*\.\s*from\s*\(\s*env\s*\)", body)))

    def service_fed_from_bound(body: str) -> bool:
        if body.count("service(") != 1 or "new BudgetPolicy(" in body or "policy(wideCaps" in body:
            return False
        if re.search(r"service\(\s*BudgetPolicyConfig\s*\.\s*from\s*\(\s*env\s*\)\s*\)", body):
            return True
        bound = re.search(r"(?:BudgetPolicy|var)\s+(\w+)\s*=\s*BudgetPolicyConfig\s*\.\s*from\s*\(\s*env\s*\)",
                          body)
        return bool(bound) and re.search(r"service\(\s*" + bound.group(1) + r"\s*\)", body) is not None

    document = re.compile(r"provider-quota:\s*\n\s+unconfigured:\s*\S+\s*\n\s+[\w-]+:\s*\n\s+max-concurrent:\s*\S+"
                          r"\s*\n\s+calls-per-day:\s*\S+\s*\n\s+[\w-]+:\s*\n\s+max-concurrent:\s*\S+"
                          r"\s*\n\s+calls-per-day:\s*\S+")
    # Look for the document inside the two cases that claim to bind one, not anywhere in the file: the other
    # fixtures quote the same keys for different reasons.
    nested = [bool(document.search(unit_body)), bool(document.search(live_body))]
    binding = [bound_in(unit_body), bound_in(live_body), service_fed_from_bound(live_body),
               "editorial.cost.provider-quota." not in unit_body]
    flat_fixtures = re.findall(r"\n\s+editorial\.cost\.provider-quota\.[\w-]+\.[\w-]+:", unit + live)
    ok = (bool(definition) and canonical and joined == ["|"] and writers >= 2 and readers >= 2
          and config_keys_by_scope and malformed_refused and segment_shape and reserved_switch_refused
          and both_leaves
          and no_invented_open and unconfigured_required and unlisted_refused and all(two_tier)
          and model_exact and all(env_channel) and leaf_normalised and zero_semantics
          and all(documented) and all(binding) and all(nested) and not flat_fixtures)
    return ("provider quota scopes are spelled one way and absence is a stated choice", ok,
            f"scope() defined={bool(definition)}, canonical '|' join inside it={canonical}, "
            f"provider-model joins in the whole cost module={joined or 'none'}, "
            f"BudgetPolicy.scope( call sites in config={writers}, scope( reads in policy={readers}, "
            f"config keys built via scope() at every site={config_keys_by_scope}, "
            f"malformed key refused={malformed_refused}, id charset refused at scope={segment_shape}, "
            f"reserved switch name refused as provider={reserved_switch_refused}, "
            f"both leaves required={both_leaves}, no invented unlimited default={no_invented_open}, "
            f"unconfigured key required={unconfigured_required}, unlisted refused on the service path="
            f"{unlisted_refused}, two levels each answer their own window={two_tier}, "
            f"model keys exact-only={model_exact}, env channel bound like the file channel={env_channel}, "
            f"conversion failure normalised={leaf_normalised}, zero semantics kept={zero_semantics}, "
            f"keys documented as coded={documented}, "
            f"binding evidence inside the asserting case bodies={binding}, "
            f"quota cases bind a nested YAML document={nested}, "
            f"flat dotted fixtures in the cases={flat_fixtures or 'none'}")


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
          check_documented_ceilings, check_admission_ceiling, check_quota_scope_spelling,
          check_configuration_ownership, check_paid_calls_still_refused, check_acceptance_anchors]


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
    quotas = "provider quota scopes are spelled one way and absence is a stated choice"
    quota_policy = COST_MAIN / "BudgetPolicy.java"
    quota_service = COST_MAIN / "BudgetService.java"
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
        {"name": "a model-level quota is keyed by the dotted property path again", "path": CONFIG_JAVA,
         "old": 'BudgetPolicy.scope(path[0], path[1])', "new": 'path[0] + "." + path[1]',
         "red": [quotas]},
        {"name": "the reader joins the scope itself instead of asking the one definition", "path": quota_policy,
         "old": 'return provider + "|" + model;',
         "new": 'return provider + "_" + model;',
         "red": [quotas]},
        {"name": "a half-declared quota scope silently opens the other side", "path": CONFIG_JAVA,
         "old": "if (held == null || calls == null) {", "new": "if (false) {", "red": [quotas]},
        {"name": "the unconfigured-provider switch grows a default", "path": CONFIG_JAVA,
         "old": "BudgetPolicy.UnconfiguredQuota.of(statedValue(env, QUOTA_PREFIX + UNCONFIGURED_LEAF))",
         "new": 'BudgetPolicy.UnconfiguredQuota.of(env.getProperty("editorial.cost.provider-quota.unconfigured",'
              ' "unlimited"))',
         "red": [quotas]},
        {"name": "an unlisted provider stops being refused", "path": quota_service,
         "old": 'throw new PublicFailure(503, "PROVIDER_QUOTA_NOT_CONFIGURED");', "new": "return;",
         "red": [quotas]},
        {"name": "both levels collapse back to the first entry that answered (single-level regression)",
         "path": quota_service,
         "old": "List<Ceiling> windows = ceilings.stream().filter(ceiling -> ceiling.quota() != null).toList();",
         "new": "List<Ceiling> windows = ceilings.stream().filter(ceiling -> ceiling.quota() != null)"
                ".limit(1).toList();",
         "red": [quotas]},
        {"name": "the report renames the quota leaves", "path": ROOT / "docs/execution/reports/T08.md",
         "old": "max-concurrent", "new": "max-concurrency", "red": [quotas]},
        {"name": "the quota case feeds dotted keys instead of the nested document",
         "path": COST_TEST / "CostPricingTest.java",
         "edits": [("                    provider-quota:\n                      unconfigured: refuse\n"
                    "                      mock:\n                        max-concurrent: 3\n"
                    "                        calls-per-day: 17\n                        mock-model:\n"
                    "                          max-concurrent: 1\n                          calls-per-day: 2",
                    "                    provider-quota.unconfigured: refuse\n"
                    "                    provider-quota.mock.max-concurrent: 3\n"
                    "                    provider-quota.mock.calls-per-day: 17\n"
                    "                    provider-quota.mock.mock-model.max-concurrent: 1\n"
                    "                    provider-quota.mock.mock-model.calls-per-day: 2")],
         "red": [quotas]},
        {"name": "the live quota case builds the policy by hand instead of from the bound environment",
         "path": PG_TEST,
         "edits": [("service(BudgetPolicyConfig.from(env));",
                    'service(policy(wideCaps(), "20.000000", 80, Map.of()));')],
         "red": [quotas]},
        {"name": "a provider named after the reserved switch stops being refused", "path": CONFIG_JAVA,
         "edits": [("if (path.length < 2 || UNCONFIGURED_LEAF.equals(path[0])) {", "if (path.length < 2) {")],
         "red": [quotas]},
        # The round-3 findings, one weakening each: the gate has to see the exact regression it was written for.
        {"name": "the OS-environment channel stops being recognised (finding F-01 rebuilt)", "path": CONFIG_JAVA,
         "edits": [("boolean environmentShaped = source instanceof SystemEnvironmentPropertySource;",
                    "boolean environmentShaped = false;")],
         "red": [quotas]},
        {"name": "the quota enumeration matches literal dotted names only again", "path": CONFIG_JAVA,
         "edits": [("if (environmentShaped) environmentQuotaName(binder, name, concurrent, perDay);\n"
                    "                    else canonicalQuotaName(binder, name, concurrent, perDay);",
                    "canonicalQuotaName(binder, name, concurrent, perDay);")],
         "red": [quotas]},
        {"name": "an ambiguous env name is guessed instead of refused", "path": CONFIG_JAVA,
         "edits": [("if (tail.length - leafParts != 1 || UNCONFIGURED_LEAF.equals(tail[0])) {",
                    "if (UNCONFIGURED_LEAF.equals(tail[0])) {")],
         "red": [quotas]},
        {"name": "an unreadable quota leaf escapes as the raw conversion failure (finding F-08)",
         "path": CONFIG_JAVA,
         "edits": [("} catch (BindException | org.springframework.core.convert.ConversionFailedException"
                    " unreadable) {",
                    "} catch (org.springframework.core.convert.ConversionFailedException raw) { throw raw;")],
         "red": [quotas]},
        {"name": "max-concurrent zero is accepted and wedges the provider forever", "path": quota_policy,
         "edits": [("if (maxConcurrent < 1 || callsPerDay < 0) throw", "if (maxConcurrent < 0 || callsPerDay < 0) throw")],
         "red": [quotas]},
        {"name": "a model key starts answering by prefix again (variant probe V4)", "path": quota_policy,
         "edits": [("return providers.containsKey(exact) ? Optional.of(providers.get(exact)) : Optional.empty();",
                    "return providers.keySet().stream().anyMatch(key -> key.startsWith(exact))"
                    " ? Optional.of(providers.get(exact)) : Optional.empty();")],
         "red": [quotas]},
        {"name": "a provider-wide entry stops building its own window (ruling F-03 half)", "path": quota_service,
         "edits": [("if (wideEntry.isPresent())", "if (false)")],
         "red": [quotas]},
        {"name": "a model entry stops building its own window (ruling F-03 half)", "path": quota_service,
         "edits": [("if (modelEntry.isPresent())", "if (false)")],
         "red": [quotas]},
        {"name": "a second provider+model join appears in the service (finding F-06's blind spot)",
         "path": quota_service,
         "edits": [("Optional<BudgetPolicy.ProviderQuota> modelEntry = policy.modelQuota(provider, model);",
                    "Optional<BudgetPolicy.ProviderQuota> modelEntry = policy.modelQuota(provider, model);\n"
                    "        String shadowScope = provider + \"|\" + model;")],
         "red": [quotas]},
        {"name": "a stored scope key stops being checked for the dotted shape", "path": quota_policy,
         "edits": [("if (stored.isBlank() || stored.contains(\".\") || stored.startsWith(\"|\")"
                    " || stored.endsWith(\"|\")",
                    "if (stored.isBlank() || stored.startsWith(\"|\") || stored.endsWith(\"|\")")],
         "red": [quotas]},
        {"name": "the loader call leaves the unit case body that claims to bind it (finding F-02's A probe)",
         "path": COST_TEST / "CostPricingTest.java",
         "edits": [("MockEnvironment env = new MockEnvironment();\n"
                    "        for (PropertySource<?> source : new YamlPropertySourceLoader().load(\"t08-quota\",\n"
                    "                new ByteArrayResource(document.getBytes(StandardCharsets.UTF_8)))) {\n"
                    "            env.getPropertySources().addLast(source);\n"
                    "        }\n"
                    "        BudgetPolicy policy = BudgetPolicyConfig.from(env);",
                    "BudgetPolicy policy = BudgetPolicyConfig.from(quotaDocument(document));")],
         "red": [quotas]},
        {"name": "the unit case feeds flat hand-built keys again", "path": COST_TEST / "CostPricingTest.java",
         "edits": [("MockEnvironment env = new MockEnvironment();\n"
                    "        for (PropertySource<?> source : new YamlPropertySourceLoader().load(\"t08-quota\",\n"
                    "                new ByteArrayResource(document.getBytes(StandardCharsets.UTF_8)))) {\n"
                    "            env.getPropertySources().addLast(source);\n"
                    "        }\n"
                    "        BudgetPolicy policy = BudgetPolicyConfig.from(env);",
                    "BudgetPolicy policy = BudgetPolicyConfig.from(statedBeyondSrs()\n"
                    "                .withProperty(\"editorial.cost.provider-quota.mock.max-concurrent\", \"3\")"
                    "\n                .withProperty(\"editorial.cost.provider-quota.mock.calls-per-day\", \"17\")"
                    "\n                .withProperty(\"editorial.cost.provider-quota.mock.mock-model"
                    ".max-concurrent\", \"1\")\n                .withProperty(\"editorial.cost.provider-quota"
                    ".mock.mock-model.calls-per-day\", \"2\"));")],
         "red": [quotas]},
        {"name": "the live case grows a second, hand-built service handover (finding F-02's B probe)",
         "path": PG_TEST,
         "edits": [("service(BudgetPolicyConfig.from(env));",
                    "service(BudgetPolicyConfig.from(env));\n"
                    '        service(policy(wideCaps(), "20.000000", 80, Map.of()));')],
         "red": [quotas]},
        {"name": "the env-shaped test source stops being env-shaped at all", "path": COST_TEST / "CostPricingTest.java",
         "edits": [('env.getPropertySources().addFirst(new SystemEnvironmentPropertySource("systemEnv", os));',
                    'env.getPropertySources().addFirst(new org.springframework.core.env.MapPropertySource('
                    '"plain", os));')],
         "red": [anchors]},
        {"name": "a decoy FOR UPDATE comment stands where the lock should be", "path": V5,
         "old": "  SELECT budget_limit INTO limit_amount FROM editorial.article_job WHERE id=NEW.article_id"
                " FOR UPDATE;\n  IF NOT FOUND",
         "new": "  -- FOR UPDATE is applied to the aggregate below\n  IF NOT FOUND", "red": [admission]},
        {"name": "the lock moves after the aggregate while a decoy mentions it first", "path": V5,
         "edits": [("  SELECT budget_limit INTO limit_amount FROM editorial.article_job WHERE id=NEW.article_id"
                    " FOR UPDATE;\n  IF NOT FOUND", "  -- FOR UPDATE is applied to the aggregate below\n  IF NOT FOUND"),
                   ("    FROM editorial.cost_ledger l WHERE l.article_id=NEW.article_id;",
                    "    FROM editorial.cost_ledger l WHERE l.article_id=NEW.article_id;\n"
                    "  SELECT budget_limit INTO limit_amount FROM editorial.article_job WHERE id=NEW.article_id"
                    " FOR UPDATE;")],
         "red": [admission]},
    ]


def benign_probes() -> list[dict]:
    """Equivalent rewrites the gates must survive, the mirror image of reversals(): a gate that fires on the
    SPELLING of a decision instead of the decision is brittle, and brittle gates train people to route around
    them. Round-3 finding F-02's remedy says binding evidence must live in the case body; these probes pin that
    the remedy accepts re-typings of the same evidence — indexOf for contains, a local variable for an inline
    call, argument wraps, comment rewordings — and still only rejects what actually changes the claim."""
    quota_policy = COST_MAIN / "BudgetPolicy.java"
    quota_service = COST_MAIN / "BudgetService.java"
    unit_test = COST_TEST / "CostPricingTest.java"
    return [
        {"name": "indexOf instead of contains for the stored dot check", "path": quota_policy,
         "edits": [('stored.contains(".")', 'stored.indexOf(".") >= 0')]},
        {"name": "the live service handover goes through one local variable", "path": PG_TEST,
         "edits": [("service(BudgetPolicyConfig.from(env));",
                    "BudgetPolicy fromDocument = BudgetPolicyConfig.from(env);\n"
                    "        service(fromDocument);")]},
        {"name": "the unit loader loop wraps one argument per line", "path": unit_test,
         "edits": [('new ByteArrayResource(document.getBytes(StandardCharsets.UTF_8)))) {',
                    'new ByteArrayResource(\n                document.getBytes(StandardCharsets.UTF_8))) {')]},
        {"name": "the F-03 comment rewords itself", "path": quota_service,
         "edits": [("// Provider ceilings are two-level and both levels bind (round-3 ruling F-03): the model "
                    "entry caps the",
                    "// Two levels, both enforced (ruling F-03): the model entry caps the")]},
        {"name": "the activePolicy assertion chain wraps a line", "path": PG_TEST,
         "edits": [("assertEquals(4, activePolicy.providerWideQuota(PROVIDER).orElseThrow().maxConcurrent(),",
                    "assertEquals(4, activePolicy.providerWideQuota(PROVIDER)\n"
                    "                .orElseThrow().maxConcurrent(),")]},
    ]


def reverse_control() -> int:
    """Run every gate against each weakening, in memory only: no file is written, no cluster is touched.
    Benign-equivalent probes run in the same pass: a weakening that goes unseen means the gate does not exist,
    and a re-typing that goes red means the gate exists for the wrong reason."""
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
        edits = spec.get("edits") or [(spec["old"], spec["new"])]
        source = path.read_text(encoding="utf-8", errors="replace")
        stale = [old for old, _ in edits if old not in source]
        if stale:
            blind.append(f"{spec['name']}: the mutation target is gone")
            print(f"[STALE ] {spec['name']}: target text no longer present")
            continue
        MUTATIONS[str(path)] = edits
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
    brittle = []
    for spec in benign_probes():
        path = Path(spec["path"])
        edits = spec["edits"]
        source = path.read_text(encoding="utf-8", errors="replace")
        if any(old not in source for old, _ in edits):
            brittle.append(f"{spec['name']}: the probe target is gone (the gate hardened around a spelling)")
            print(f"[BRITTLE] {spec['name']}: probe target no longer present")
            continue
        MUTATIONS[str(path)] = edits
        try:
            failed = {name for name, ok, _ in run_checks() if not ok}
        finally:
            MUTATIONS.clear()
        if failed:
            brittle.append(f"{spec['name']}: red were {sorted(failed)}")
            print(f"[BRITTLE] {spec['name']} -> {sorted(failed)}")
        else:
            print(f"[benign ] {spec['name']} stayed green")
    print(f"reverse control: {len(reversals())} weakenings, {len(benign_probes())} benign probes, "
          f"blind={blind or 'none'}, misplaced={misplaced or 'none'}, brittle={brittle or 'none'}")
    return 1 if blind or misplaced or brittle else 0


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

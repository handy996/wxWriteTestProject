"""T08 round-4 reviewer: attack the round-3 F-02 remedy in memory (dispatch items 3 and 4).

Reuses verify.py's own MUTATIONS mechanism (read() applies it; nothing is written to disk, no cluster is
touched, no controlled source is modified). Part A asks whether "the binding evidence lives inside the
asserting method body" can be satisfied by DECORATION instead of data flow; part B adds weakenings the
shipped 44 do not contain. Each probe prints the gate's own detail, so the verdict comes from the gate.
"""
import importlib.util
import sys
from pathlib import Path

REPO = Path(r"E:/project/codex/wxAgent")
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("t08_verify", REPO / "tests/engineering/T08/verify.py")
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)

QUOTAS = "provider quota scopes are spelled one way and absence is a stated choice"
ANCHORS = "acceptance cases still assert what they claim"
UNIT = str(verify.COST_TEST / "CostPricingTest.java")
LIVE = str(verify.PG_TEST)
SERVICE = str(verify.COST_MAIN / "BudgetService.java")
CONFIG = str(verify.COST_MAIN / "BudgetPolicyConfig.java")
POLICY = str(verify.COST_MAIN / "BudgetPolicy.java")

# ---- shipped text the probes rewrite --------------------------------------------------------
UNIT_LOADER = """        MockEnvironment env = new MockEnvironment();
        for (PropertySource<?> source : new YamlPropertySourceLoader().load("t08-quota",
                new ByteArrayResource(document.getBytes(StandardCharsets.UTF_8)))) {
            env.getPropertySources().addLast(source);
        }
        BudgetPolicy policy = BudgetPolicyConfig.from(env);"""

LIVE_CALL = "        service(BudgetPolicyConfig.from(env));"

LIVE_LOADER_BLOCK = """        MockEnvironment env = new MockEnvironment();
        for (PropertySource<?> source : new YamlPropertySourceLoader().load("t08-quota",
                new ByteArrayResource(document.getBytes(java.nio.charset.StandardCharsets.UTF_8)))) {
            env.getPropertySources().addLast(source);
        }"""

LIVE_FIELDS = "    private BudgetPolicy activePolicy;"

AFTER_LIVE = ("    /** The reservation the quota cases place: one image unit on a model of the configured"
              " provider. */")

LIVE_DOCUMENT = """        String document = \"\"\"
                editorial:
                  cost:
                    max-calls-per-article: 1000
                    image-units-per-article: 100
                    reconciliation-stale-minutes: 30
                    provider-quota:
                      unconfigured: refuse
                      mock-provider:
                        max-concurrent: 4
                        calls-per-day: 26
                        mock-gpt:
                          max-concurrent: 1
                          calls-per-day: 9
                \"\"\";"""

HELPER_ANCHOR = """    @Test
    @DisplayName("A configured ceiling is honoured and a bad one is refused at boot")"""

UNIT_HELPER = """    private static MockEnvironment r4ReviewerHelper(String document) throws java.io.IOException {
        MockEnvironment env = new MockEnvironment();
        for (PropertySource<?> source : new YamlPropertySourceLoader().load("t08-quota",
                new ByteArrayResource(document.getBytes(StandardCharsets.UTF_8)))) {
            env.getPropertySources().addLast(source);
        }
        return env;
    }

"""

LIVE_HELPER = """    private static MockEnvironment r4LiveHelper(String document) throws Exception {
        MockEnvironment env = new MockEnvironment();
        for (PropertySource<?> source : new YamlPropertySourceLoader().load("t08-quota",
                new ByteArrayResource(document.getBytes(java.nio.charset.StandardCharsets.UTF_8)))) {
            env.getPropertySources().addLast(source);
        }
        return env;
    }

"""

NESTED_DOCUMENT = """                    provider-quota:
                      unconfigured: refuse
                      mock-provider:
                        max-concurrent: 4
                        calls-per-day: 26
                        mock-gpt:
                          max-concurrent: 1
                          calls-per-day: 9"""

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

PROBES = [
    ("A1 baseline, no mutation", []),
    # ---- the rule as shipped: does it actually bite? ----------------------------------------
    ("A2 unit: loader moved to a same-class helper, no brace skew",
     [(UNIT, UNIT_LOADER,
       "        MockEnvironment env = r4ReviewerHelper(document);\n"
       "        BudgetPolicy policy = BudgetPolicyConfig.from(env);"),
      (UNIT, HELPER_ANCHOR, UNIT_HELPER + HELPER_ANCHOR)]),
    ("A2b live: loader moved to a same-class helper, no brace skew",
     [(LIVE, LIVE_LOADER_BLOCK, "        MockEnvironment env = r4LiveHelper(document);"),
      (LIVE, LIVE_FIELDS, LIVE_FIELDS + "\n\n" + LIVE_HELPER.rstrip("\n"))]),
    # ---- can the body slice be widened so a helper's tokens count as "in the body"? ---------
    ("A3 unit: same extraction + ONE unmatched '{' in a String literal in the asserting body",
     [(UNIT, UNIT_LOADER,
       '        String r4Skew = "{";   // fixture-shaped text; perfectly legal Java\n'
       "        MockEnvironment env = r4ReviewerHelper(document);\n"
       "        BudgetPolicy policy = BudgetPolicyConfig.from(env);"),
      (UNIT, HELPER_ANCHOR, UNIT_HELPER + HELPER_ANCHOR)]),
    ("A4 live: same extraction + ONE unmatched '{' in a String literal (helper placed after the case)",
     [(LIVE, LIVE_LOADER_BLOCK,
       '        String r4Skew = "{";   // a JSON fragment this case used to keep around\n'
       '        MockEnvironment env = r4LiveHelper(document);'),
      (LIVE, AFTER_LIVE, LIVE_HELPER.rstrip("\n") + "\n\n" + AFTER_LIVE)]),
    # ---- can the required tokens be pure decoration? ----------------------------------------
    ("A5 decisive: live case fed by HAND-WRITTEN FLAT keys, loader tokens kept in a body COMMENT",
     [(LIVE, LIVE_LOADER_BLOCK + "\n" + LIVE_CALL,
       "        // (the binding evidence, decorative): new YamlPropertySourceLoader() and\n"
       "        // new ByteArrayResource(document.getBytes(...)) built the environment that\n"
       "        // BudgetPolicyConfig.from(env) reads, exactly as before\n" + FLAT_KEYS)]),
    ("A6 decoration + the nested document also removed from the body",
     [(LIVE, LIVE_LOADER_BLOCK + "\n" + LIVE_CALL,
       "        // new YamlPropertySourceLoader(); new ByteArrayResource(document.getBytes(...));"
       " BudgetPolicyConfig.from(env)\n" + FLAT_KEYS),
      (LIVE, NESTED_DOCUMENT, "                        r4MovedOutOfTheBody: true")]),
    # ---- benign equivalent rewrites that MUST stay green ------------------------------------
    ("A7 BENIGN: loader statement split over more lines (unit)",
     [(UNIT, UNIT_LOADER,
       "        MockEnvironment env = new MockEnvironment();\n"
       '        PropertySource<?>[] r4Loaded = new YamlPropertySourceLoader().load("t08-quota",\n'
       "                new ByteArrayResource(document.getBytes(StandardCharsets.UTF_8)))\n"
       "                        .toArray(new PropertySource<?>[0]);\n"
       "        for (PropertySource<?> source : r4Loaded) {\n"
       "            env.getPropertySources().addLast(source);\n        }\n"
       "        BudgetPolicy policy = BudgetPolicyConfig.from(env);")]),
    ("A8 BENIGN: live service fed through a local variable (loader untouched)",
     [(LIVE, LIVE_CALL,
       "        BudgetPolicy r4Bound = BudgetPolicyConfig.from(env);\n        service(r4Bound);")]),
    ("A9 BENIGN: assertEquals wrapped as assertTrue(Integer.valueOf(x).equals(y))",
     [(LIVE, '        assertEquals(26, activePolicy.providerWideQuota(PROVIDER).orElseThrow().callsPerDay());',
       '        assertTrue(Integer.valueOf(26).equals(activePolicy.providerWideQuota(PROVIDER)\n'
       '                .orElseThrow().callsPerDay()));')]),
    ("A10 BENIGN?: quota result written to a FIELD before service()",
     [(LIVE, LIVE_CALL,
       "        r4FieldPolicy = BudgetPolicyConfig.from(env);\n        service(r4FieldPolicy);"),
      (LIVE, LIVE_FIELDS, "    private BudgetPolicy r4FieldPolicy;\n" + LIVE_FIELDS)]),
    ("A11 FALSE-RED probe: one legal local String whose value is '}' at the top of the live body",
     [(LIVE, "    void nestedYamlQuotaIsEnforcedByTheService() throws Exception {",
       '    void nestedYamlQuotaIsEnforcedByTheService() throws Exception {\n'
       '        String r4Close = "}";   // nothing about the binding changed')]),
    # ---- part B: weakenings the shipped 44 do not contain -----------------------------------
    ("B1 lock ordering dropped (ceilings locked in insertion order, no sort)",
     [(SERVICE,
       "        ceilings.sort(Comparator.comparing(Ceiling::lockKey));\n"
       "        for (Ceiling ceiling : ceilings) ledger.lockScope(ceiling.lockKey());",
       "        for (Ceiling ceiling : ceilings) ledger.lockScope(ceiling.lockKey());")]),
    ("B2 the two quota windows' where-clauses swapped (both SQL strings stay in the file)",
     [(SERVICE, '"l.owner_id=? AND l.provider=? AND l.model=? AND l.bucket_day=?"', 'r4PLACEHOLDERr4'),
      (SERVICE, '"l.owner_id=? AND l.provider=? AND l.bucket_day=?"',
       '"l.owner_id=? AND l.provider=? AND l.model=? AND l.bucket_day=?"'),
      (SERVICE, 'r4PLACEHOLDERr4', '"l.owner_id=? AND l.provider=? AND l.bucket_day=?"')]),
    ("B3 env-shaped name with an unknown leaf skipped silently instead of refused",
     [(CONFIG, '            leafParts = 2;\n        } else {\n'
              '            throw new PublicFailure(503, "INVALID_PROVIDER_QUOTA_KEY");',
       '            leafParts = 2;\n        } else {\n            return;')]),
    ("B4 concurrency compares '>' so the (N+1)-th live hold is admitted",
     [(SERVICE, "if (used.holds() >= quota.maxConcurrent())", "if (used.holds() > quota.maxConcurrent())")]),
    ("B5 stored-key dotted refusal removed (a dotted scope becomes storable)",
     [(POLICY, 'stored.isBlank() || stored.contains(".")', 'stored.isBlank()')]),
    ("B6 live case gutted: numbers kept in comments, assertEquals(4, holds()) replaced by assertNotNull",
     [(LIVE, '        assertEquals(4, holds(), "the refusals booked nothing");',
       '        assertNotNull(activePolicy, "4, holds() live in this comment");'),
      (LIVE, '        assertEquals(26, activePolicy.providerWideQuota(PROVIDER).orElseThrow().callsPerDay());',
       '        // assertEquals(26, activePolicy.providerWideQuota(PROVIDER).orElseThrow().callsPerDay());')]),
    ("B7 day-window refusal silently becomes unlimited when calls-per-day is 0",
     [(SERVICE, "if (used.counter(BudgetPolicy.Counter.CALLS) + 1 > quota.callsPerDay())",
       "if (quota.callsPerDay() != 0 && used.counter(BudgetPolicy.Counter.CALLS) + 1 > quota.callsPerDay())")]),
]


def run(label: str, edits: list[tuple[str, str]]) -> None:
    grouped: dict[str, list[tuple[str, str]]] = {}
    for path, old, new in edits:
        grouped.setdefault(path, []).append((old, new))
    for path, pairs in grouped.items():
        text = Path(path).read_text(encoding="utf-8")
        for index, (old, new) in enumerate(pairs):
            if old not in text:
                print(f"  [{label}] STALE at edit {index + 1} of {Path(path).name}: {old[:70]!r}")
                return
            text = text.replace(old, new)
    verify.MUTATIONS.clear()
    for path, pairs in grouped.items():
        verify.MUTATIONS[path] = pairs
    failed = [(name, detail) for name, ok, detail in verify.run_checks() if not ok]
    verify.MUTATIONS.clear()
    if not failed:
        print(f"  [{label}]\n      red = NONE (every gate stayed green)")
        return
    for name, detail in failed:
        print(f"  [{label}]\n      RED -> {name}")
        if name == QUOTAS:
            false_parts = [part for part in detail.split(", ") if "=False" in part or "[False" in part
                           or "False," in part or "=['" in part or part.startswith("weakened")]
            print("        false sub-flags: " + (" | ".join(false_parts) or detail[-300:]))
            print("        full: " + detail)
        elif name == ANCHORS:
            print("        " + detail[:400])


print("baseline reds: " + str([name for name, ok, _ in verify.run_checks() if not ok]))
for label, edits in PROBES:
    run(label, edits)

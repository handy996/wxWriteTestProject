"""T08 round-4 reviewer, part 2 of the F-02 attack: read the gate's INNER flags, not its summary.

Same in-memory mechanism as r4_gate_probe.py. Here every probe prints, for the mutated text:
  bound_in(unit) / bound_in(live) / service_fed_from_bound(live) / nested(unit) / nested(live)
plus the plain-text claim of java_method_body (does a brace inside a string literal widen or narrow?).
Nothing is written to disk.
"""
import importlib.util
import re
import sys
from pathlib import Path

REPO = Path(r"E:/project/codex/wxAgent")
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("t08_verify", REPO / "tests/engineering/T08/verify.py")
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)

UNIT = verify.COST_TEST / "CostPricingTest.java"
LIVE = verify.PG_TEST
UNIT_CASE = "quotaWrittenAsNestedYamlBindsTheScopeTheLookupReads"
LIVE_CASE = "nestedYamlQuotaIsEnforcedByTheService"

UNIT_LOADER = """        MockEnvironment env = new MockEnvironment();
        for (PropertySource<?> source : new YamlPropertySourceLoader().load("t08-quota",
                new ByteArrayResource(document.getBytes(StandardCharsets.UTF_8)))) {
            env.getPropertySources().addLast(source);
        }
        BudgetPolicy policy = BudgetPolicyConfig.from(env);"""

LIVE_LOADER = """        MockEnvironment env = new MockEnvironment();
        for (PropertySource<?> source : new YamlPropertySourceLoader().load("t08-quota",
                new ByteArrayResource(document.getBytes(java.nio.charset.StandardCharsets.UTF_8)))) {
            env.getPropertySources().addLast(source);
        }
        service(BudgetPolicyConfig.from(env));"""

# The next member after the live case, so an inserted helper sits AFTER it (the brace walk goes forward).
AFTER_LIVE = ("    /** The reservation the quota cases place: one image unit on a model of the configured"
              " provider. */")

UNIT_HELPER = """    private static MockEnvironment r4Helper(String document) throws java.io.IOException {
        MockEnvironment env = new MockEnvironment();
        for (PropertySource<?> source : new YamlPropertySourceLoader().load("t08-quota",
                new ByteArrayResource(document.getBytes(StandardCharsets.UTF_8)))) {
            env.getPropertySources().addLast(source);
        }
        return env;
    }

"""
LIVE_HELPER = """    private MockEnvironment r4Helper(String document) throws Exception {
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

NESTED_RE = re.compile(
    r"provider-quota:\s*\n\s+unconfigured:\s*\w+\s*\n\s+[\w.-]+:\s*\n(?:\s+[\w.-]+:[^\n]*\n)+")


def flags(edits: list[tuple[Path, str, str]]) -> str:
    verify.MUTATIONS.clear()
    for path, old, new in edits:
        text = path.read_text(encoding="utf-8")
        if old not in text:
            return "STALE: " + old[:60]
    grouped: dict[str, list[tuple[str, str]]] = {}
    for path, old, new in edits:
        grouped.setdefault(str(path), []).append((old, new))
    for key, pairs in grouped.items():
        verify.MUTATIONS[key] = pairs
    unit = verify.read(UNIT)
    live = verify.read(LIVE)
    ub = verify.java_method_body(unit, UNIT_CASE)
    lb = verify.java_method_body(live, LIVE_CASE)
    out = ("bound_in(unit)=%s bound_in(live)=%s service_fed(live)=%s nested(unit)=%s nested(live)=%s "
           "unit_slice_len=%d live_slice_len=%d flat=%s"
           % (bool(ub) and all(part in ub for part in ("new YamlPropertySourceLoader()", "document.getBytes",
                                                       "new ByteArrayResource(", "BudgetPolicyConfig.from(env)")),
              bool(lb) and all(part in lb for part in ("new YamlPropertySourceLoader()", "document.getBytes",
                                                       "new ByteArrayResource(", "BudgetPolicyConfig.from(env)")),
              verify.check_quota_scope_spelling.__name__ and service_fed(lb),
              bool(NESTED_RE.search(ub)), bool(NESTED_RE.search(lb)), len(ub), len(lb),
              re.findall(r"\n\s+editorial\.cost\.provider-quota\.[\w-]+\.[\w-]+:", unit + live) or "none"))
    verify.MUTATIONS.clear()
    return out


def service_fed(live_body: str) -> bool:
    if not live_body or "new BudgetPolicy(" in live_body or live_body.count("service(") != 1:
        return False
    return bool(re.search(r"service\(\s*BudgetPolicyConfig\s*\.\s*from\s*\(\s*env\s*\)\s*\)", live_body)
                or re.search(r"(?:BudgetPolicy|var)\s+(\w+)\s*=\s*BudgetPolicyConfig\s*\.\s*from\s*\(\s*env"
                             r"\s*\)\s*;\s*[^;]*service\(\s*\1\s*\)", live_body))


CASES = [
    ("E0 baseline", []),
    ("E1 live loader -> helper placed AFTER the case, NO skew",
     [(LIVE, LIVE_LOADER, "        MockEnvironment env = r4Helper(document);\n        service(env == null ? "
       "BudgetPolicyConfig.from(env) : BudgetPolicyConfig.from(env));"),
      (LIVE, AFTER_LIVE, LIVE_HELPER + AFTER_LIVE)]),
    ("E2 live loader -> helper AFTER the case + ONE '{' in a String literal in the asserting body",
     [(LIVE, LIVE_LOADER, '        String r4Skew = "{";\n        MockEnvironment env = r4Helper(document);\n'
       "        service(BudgetPolicyConfig.from(env));"),
      (LIVE, AFTER_LIVE, LIVE_HELPER + AFTER_LIVE)]),
    ("E3 same but the skew lives in a // COMMENT",
     [(LIVE, LIVE_LOADER, "        // { comment-only skew\n        MockEnvironment env = r4Helper(document);\n"
       "        service(BudgetPolicyConfig.from(env));"),
      (LIVE, AFTER_LIVE, LIVE_HELPER + AFTER_LIVE)]),
    ("E4 flat keys + loader tokens only in a comment (no helper at all)",
     [(LIVE, LIVE_LOADER, "        // new YamlPropertySourceLoader(); new ByteArrayResource("
       "document.getBytes(...)); BudgetPolicyConfig.from(env)\n" + FLAT_KEYS)]),
    ("E5 flat keys, and the comment omits the tokens (control: must go red)",
     [(LIVE, LIVE_LOADER, "        // evidence removed entirely\n" + FLAT_KEYS)]),
    ("E6 unit: one '}' inside a String literal at the top of the case (benign text, must stay green)",
     [(UNIT, "    void " + UNIT_CASE + "() throws java.io.IOException {",
       '    void ' + UNIT_CASE + '() throws java.io.IOException {\n        String r4Fragment = "}";')]),
    ("E7 live: quota result written to a field before service()",
     [(LIVE, "        service(BudgetPolicyConfig.from(env));",
       "        r4Field = BudgetPolicyConfig.from(env);\n        service(r4Field);"),
      (LIVE, "    private BudgetPolicy activePolicy;",
       "    private BudgetPolicy r4Field;\n    private BudgetPolicy activePolicy;")]),
    ("E8 live: one '}' inside a String literal at the top of the case (benign text, must stay green)",
     [(LIVE, "    void " + LIVE_CASE + "() throws Exception {",
       '    void ' + LIVE_CASE + '() throws Exception {\n        String r4Fragment = "}";')]),
]

for label, edits in CASES:
    print(f"{label}\n    {flags(edits)}")

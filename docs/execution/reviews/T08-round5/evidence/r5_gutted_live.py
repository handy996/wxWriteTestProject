"""Round-5 reviewer: run the DELIVERED isolated live round against a gutted copy, outside the repository.

Purpose: the static gate probe showed my G1 rewrite (the nested document is really parsed by a real
YamlPropertySourceLoader, but into a DECOY environment nobody reads, while the environment handed to
``BudgetPolicyConfig.from(env)`` is built from flat keys assembled by string concatenation) keeps all 16 static
gates green. Whether that is a defect or a curiosity depends on the runtime: if the gutted case still passes its
own assertions, the in-body binding evidence is still decoration, and round-4's finding F-R4-06 is not closed.

Mechanics: copy the tracked ``backend/`` to a scratch root outside the repository, apply the rewrite to that
COPY ONLY, point ``run_pg.ROOT`` / ``HERE`` / ``MIGRATIONS`` at the copy, keep the read-only toolchain paths at
the real repository. No controlled file is written; no ``backend/target`` in the repository is touched — Surefire
runs inside the scratch copy.
"""
import json
import shutil
import sys
from pathlib import Path

REPO = Path(r"E:/project/codex/wxAgent")
SCRATCH = Path(sys.argv[1]) if len(sys.argv) > 1 else None
CASE = sys.argv[2] if len(sys.argv) > 2 else 'G1'
NAME = sys.argv[3] if len(sys.argv) > 3 else 'r5-gut-g1'
assert SCRATCH is not None, 'usage: r5_gutted_live.py <absolute-scratch-root> <G1|G2|CONTROL> <evidence-name>'
SCRATCH = SCRATCH.resolve()

LIVE_ORIGINAL = """        MockEnvironment env = new MockEnvironment();
        for (PropertySource<?> source : new YamlPropertySourceLoader().load("t08-quota",
                new ByteArrayResource(document.getBytes(java.nio.charset.StandardCharsets.UTF_8)))) {
            env.getPropertySources().addLast(source);
        }
        service(BudgetPolicyConfig.from(env));
"""

DECOY = """        java.util.List<PropertySource<?>> r5Parsed = new YamlPropertySourceLoader().load("t08-quota",
                new ByteArrayResource(document.getBytes(java.nio.charset.StandardCharsets.UTF_8)));
        MockEnvironment r5Decoy = new MockEnvironment();
        for (PropertySource<?> r5Source : r5Parsed) {
            r5Decoy.getPropertySources().addLast(r5Source);
        }
"""

G1 = DECOY + """        MockEnvironment env = new MockEnvironment();
        String r5Head = "editorial.cost.";
        String r5Quota = "provider-quota.";
        env.setProperty(r5Head + "max-calls-per-article", "1000");
        env.setProperty(r5Head + "image-units-per-article", "100");
        env.setProperty(r5Head + "reconciliation-stale-minutes", "30");
        env.setProperty(r5Head + r5Quota + "unconfigured", "refuse");
        env.setProperty(r5Head + r5Quota + "mock-provider.max-concurrent", "4");
        env.setProperty(r5Head + r5Quota + "mock-provider.calls-per-day", "26");
        env.setProperty(r5Head + r5Quota + "mock-provider.mock-gpt.max-concurrent", "1");
        env.setProperty(r5Head + r5Quota + "mock-provider.mock-gpt.calls-per-day", "9");
        service(BudgetPolicyConfig.from(env));
"""

G2 = DECOY + """        MockEnvironment env = new MockEnvironment();
        r5FlatQuotaKeys(env);
        service(BudgetPolicyConfig.from(env));
"""

G2_HELPER = """
    /** Reviewer probe G2: the same dotted keys the nested document spells, assembled outside the case body. */
    private void r5FlatQuotaKeys(MockEnvironment env) {
        String r5Prefix = "editorial" + ".cost" + ".provider-quota.";
        env.setProperty("editorial.cost.max-calls-per-article", "1000");
        env.setProperty("editorial.cost.image-units-per-article", "100");
        env.setProperty("editorial.cost.reconciliation-stale-minutes", "30");
        env.setProperty(r5Prefix + "unconfigured", "refuse");
        r5Set(env, r5Prefix, "mock-provider", "max-concurrent", "4");
        r5Set(env, r5Prefix, "mock-provider", "calls-per-day", "26");
        r5Set(env, r5Prefix, "mock-provider", "mock-gpt", "max-concurrent", "1");
        r5Set(env, r5Prefix, "mock-provider", "mock-gpt", "calls-per-day", "9");
    }

    private void r5Set(MockEnvironment env, String prefix, String provider, String leaf, String value) {
        env.setProperty(prefix + provider + "." + leaf, value);
    }

    private void r5Set(MockEnvironment env, String prefix, String provider, String model, String leaf,
                       String value) {
        env.setProperty(prefix + provider + "." + model + "." + leaf, value);
    }

    /** The reservation the quota cases place:"""

REWRITES = {'G1': [(LIVE_ORIGINAL, G1)], 'G2': [(LIVE_ORIGINAL, G2),
                                               ('    /** The reservation the quota cases place:', G2_HELPER)],
            'CONTROL': []}

if SCRATCH.exists():
    shutil.rmtree(SCRATCH)
SCRATCH.mkdir(parents=True)
shutil.copytree(REPO / 'backend', SCRATCH / 'backend', ignore=shutil.ignore_patterns('target'))
shutil.copytree(REPO / 'tests/engineering/T08', SCRATCH / 'tests/engineering/T08',
                ignore=shutil.ignore_patterns('.work', 'evidence'))
assert not (SCRATCH / 'backend/target').exists()

test_file = SCRATCH / 'backend/src/test/java/com/example/editorial/cost/T08PostgresTest.java'
text = test_file.read_text(encoding='utf-8')
applied = []
for old, new in REWRITES[CASE]:
    if old not in text:
        raise SystemExit(f'rewrite anchor missing: {old[:60]!r}')
    text = text.replace(old, new, 1)
    applied.append(old[:40])
test_file.write_text(text, encoding='utf-8', newline='\n')
print(json.dumps({'case': CASE, 'scratch': str(SCRATCH), 'rewrites': applied,
                  'changedFromOriginal': bool(REWRITES[CASE])}), flush=True)

sys.path.insert(0, str(REPO / 'tests/engineering/T08'))
import run_pg  # noqa: E402

run_pg.ROOT = SCRATCH
run_pg.MIGRATIONS = SCRATCH / 'backend/src/main/resources/db/migration'
run_pg.HERE = SCRATCH / 'tests/engineering/T08'
evidence_dir = REPO / 'docs/execution/reviews/T08-round5/evidence'
sys.argv = ['run_pg.py', '--pg-bin', str(REPO / '.tools/t02/postgresql-full/pgsql/bin'),
            '--java-home', str(REPO / '.tools/t02/jdk-21.0.12.1+1'),
            '--maven', str(REPO / '.tools/t02/apache-maven-3.9.11/bin/mvn.cmd'),
            '--m2', str(REPO / '.tools/t02/m2'),
            '--work-root', str(SCRATCH / '.work'),
            '--evidence-dir', str(evidence_dir), '--evidence-name', NAME,
            '--expect-tests', '65', '--timeout', '1800']
code = run_pg.main()
print(f'RUN_PG_EXIT={code}', flush=True)

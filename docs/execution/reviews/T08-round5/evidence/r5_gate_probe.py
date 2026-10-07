"""Round-5 reviewer gate probe: replay round-4's gutting shapes and my own new ones against the DELIVERED
gates, in memory only.

Mechanics: import ``verify`` as a module, install an in-memory rewrite through the same ``MUTATIONS`` channel
the delivered ``--reverse-control`` uses, run all 16 gates, print which went red together with the gate's own
detail text (so the verdict comes from the gate, not from my reading of it). Nothing here writes to the
repository, to a cluster, or to ``backend/target``. A missing anchor is reported as STALE, because
``verify.mutate`` raises on a missing anchor for the same reason: "nothing was mutated" must never print as
"the gate rejected it".

Cases (my own text, re-derived from the round-4 review's descriptions, not copied from its scripts):
  A5  round-4's repro on the LIVE case: hand-written flat dotted keys do the binding; the loader, the document
      and from(env) survive only as COMMENTS. Expected now: red (that was the requested fix).
  E4  the same gutting on the UNIT case. Expected now: red.
  A8  benign equivalent rewrite: the bound policy travels through a local variable to the service. Green.
  G1  third way #1: the document IS loaded by a real loader — into a decoy environment nobody uses — while the
      environment the service is fed comes from flat keys assembled by concatenation, so the forbidden literal
      never appears in the body as a substring.
  G2  third way #2: same decoy load, and the flat keys are assembled in a same-file HELPER, so the body holds
      no quota key text at all.
  B1  round-4 control B1: delete the lock-order sort. Expected now: red.
  B1b sort by the display label instead of the locked key. B1c: lock the label instead of the key.
"""
import json
import sys
from pathlib import Path

ROOT = Path(r"E:/project/codex/wxAgent")
sys.path.insert(0, str(ROOT / "tests/engineering/T08"))
import verify  # noqa: E402

PG = str(verify.PG_TEST)
UNIT = str(verify.COST_TEST / "CostPricingTest.java")
SERVICE = str(verify.COST_MAIN / "BudgetService.java")

LIVE_ORIGINAL = """        MockEnvironment env = new MockEnvironment();
        for (PropertySource<?> source : new YamlPropertySourceLoader().load("t08-quota",
                new ByteArrayResource(document.getBytes(java.nio.charset.StandardCharsets.UTF_8)))) {
            env.getPropertySources().addLast(source);
        }
        service(BudgetPolicyConfig.from(env));
"""

UNIT_ORIGINAL = """        MockEnvironment env = new MockEnvironment();
        for (PropertySource<?> source : new YamlPropertySourceLoader().load("t08-quota",
                new ByteArrayResource(document.getBytes(StandardCharsets.UTF_8)))) {
            env.getPropertySources().addLast(source);
        }
        BudgetPolicy policy = BudgetPolicyConfig.from(env);
"""

LIVE_A5 = """        // binding: new YamlPropertySourceLoader() + new ByteArrayResource(document.getBytes(...))
        // into env.getPropertySources().addLast(source), then BudgetPolicyConfig.from(env)
        MockEnvironment env = new MockEnvironment();
        env.setProperty("editorial.cost.max-calls-per-article", "1000");
        env.setProperty("editorial.cost.image-units-per-article", "100");
        env.setProperty("editorial.cost.reconciliation-stale-minutes", "30");
        env.setProperty("editorial.cost.provider-quota.unconfigured", "refuse");
        env.setProperty("editorial.cost.provider-quota.mock-provider.max-concurrent", "4");
        env.setProperty("editorial.cost.provider-quota.mock-provider.calls-per-day", "26");
        env.setProperty("editorial.cost.provider-quota.mock-provider.mock-gpt.max-concurrent", "1");
        env.setProperty("editorial.cost.provider-quota.mock-provider.mock-gpt.calls-per-day", "9");
        service(BudgetPolicyConfig.from(env));
"""

UNIT_E4 = """        // binding: new YamlPropertySourceLoader() + new ByteArrayResource(document.getBytes(...))
        // into env.getPropertySources().addLast(source), then BudgetPolicyConfig.from(env)
        MockEnvironment env = new MockEnvironment();
        env.setProperty("editorial.cost.max-calls-per-article", "64");
        env.setProperty("editorial.cost.reconciliation-stale-minutes", "30");
        env.setProperty("editorial.cost.provider-quota.unconfigured", "refuse");
        env.setProperty("editorial.cost.provider-quota.mock.max-concurrent", "3");
        env.setProperty("editorial.cost.provider-quota.mock.calls-per-day", "17");
        env.setProperty("editorial.cost.provider-quota.mock.mock-model.max-concurrent", "1");
        env.setProperty("editorial.cost.provider-quota.mock.mock-model.calls-per-day", "2");
        BudgetPolicy policy = BudgetPolicyConfig.from(env);
"""

LIVE_A8 = """        MockEnvironment env = new MockEnvironment();
        for (PropertySource<?> source : new YamlPropertySourceLoader().load("t08-quota",
                new ByteArrayResource(document.getBytes(java.nio.charset.StandardCharsets.UTF_8)))) {
            env.getPropertySources().addLast(source);
        }
        BudgetPolicy bound = BudgetPolicyConfig.from(env);
        service(bound);
"""

# The decoy: a real loader over the real document, added to a real environment — and then that environment is
# simply not the one the case feeds to the service.
DECOY = """        java.util.List<PropertySource<?>> r5Parsed = new YamlPropertySourceLoader().load("t08-quota",
                new ByteArrayResource(document.getBytes(java.nio.charset.StandardCharsets.UTF_8)));
        MockEnvironment r5Decoy = new MockEnvironment();
        for (PropertySource<?> r5Source : r5Parsed) {
            r5Decoy.getPropertySources().addLast(r5Source);
        }
"""

LIVE_G1 = DECOY + """        MockEnvironment env = new MockEnvironment();
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

LIVE_G2 = DECOY + """        MockEnvironment env = new MockEnvironment();
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
        env.setProperty(r5Prefix + "mock-provider.max-concurrent", "4");
        env.setProperty(r5Prefix + "mock-provider.calls-per-day", "26");
        env.setProperty(r5Prefix + "mock-provider.mock-gpt.max-concurrent", "1");
        env.setProperty(r5Prefix + "mock-provider.mock-gpt.calls-per-day", "9");
    }

    /** Reviewer probe G2 anchor. */
    private static final class R5DecoyAnchor {
    }

    /** The reservation the quota cases place:"""

B1 = (SERVICE, "        ceilings = inLockOrder(ceilings);\n",
      "        // reviewer probe B1: the sort call is deleted\n")
B1B = (SERVICE, "ordered.sort(Comparator.comparing(Ceiling::lockKey));",
       "ordered.sort(Comparator.comparing(Ceiling::label));")
B1C = (SERVICE, "for (Ceiling ceiling : ceilings) ledger.lockScope(ceiling.lockKey());",
       "for (Ceiling ceiling : ceilings) ledger.lockScope(ceiling.label());")
# F-R4-03/04/05/10/02 relit on the product path, one shape each.
SILENT = {
    "S1-prefix-neighbour-silently-skipped":
        (str(verify.COST_MAIN / "BudgetPolicyConfig.java"),
         """            if (lowered.startsWith(ENVIRONMENT_NAMESPACE) && lowered.contains(ENVIRONMENT_QUOTA_MARKER)) {
                throw new PublicFailure(503, "INVALID_PROVIDER_QUOTA_KEY");
            }
            return;""",
         "            return;"),
    "S2-canonical-name-in-env-source-dropped":
        (str(verify.COST_MAIN / "BudgetPolicyConfig.java"),
         """        if (name.startsWith(QUOTA_PREFIX)) {
            canonicalQuotaName(binder, name, concurrent, perDay);
            return;
        }
""", ""),
    "S3-unknown-leaf-falls-through":
        (str(verify.COST_MAIN / "BudgetPolicyConfig.java"),
         """        } else {
            throw new PublicFailure(503, "INVALID_PROVIDER_QUOTA_KEY");
        }
        // Exactly one unambiguous provider segment""",
         """        } else {
            return;
        }
        // Exactly one unambiguous provider segment"""),
    "S4-day-leaf-read-as-int":
        (str(verify.COST_MAIN / "BudgetPolicyConfig.java"),
         'case "calls-per-day" -> perDay.put(scope, dayCountLeaf(binder, canonical));',
         'case "calls-per-day" -> perDay.put(scope, (long) quotaLeaf(binder, canonical));'),
    "S5-unspellable-name-escapes":
        (str(verify.COST_MAIN / "BudgetPolicyConfig.java"),
         """        } catch (BindException | org.springframework.core.convert.ConversionFailedException
                | org.springframework.boot.context.properties.source.InvalidConfigurationPropertyNameException
                unreadable) {
            throw new PublicFailure(503, "INVALID_BUDGET_POLICY");
        }
        if (value == null || value < 0) throw new PublicFailure(503, "INVALID_BUDGET_POLICY");
        return value;
    }

    /**
     * The {@code calls-per-day} leaf""",
         """        } catch (BindException | org.springframework.core.convert.ConversionFailedException unreadable) {
            throw new PublicFailure(503, "INVALID_BUDGET_POLICY");
        }
        if (value == null || value < 0) throw new PublicFailure(503, "INVALID_BUDGET_POLICY");
        return value;
    }

    /**
     * The {@code calls-per-day} leaf"""),
}

CASES = {
    "A5-live-gutting": [(PG, LIVE_ORIGINAL, LIVE_A5)],
    "E4-unit-gutting": [(UNIT, UNIT_ORIGINAL, UNIT_E4)],
    "A8-benign-local": [(PG, LIVE_ORIGINAL, LIVE_A8)],
    "G1-concatenated-flat-keys": [(PG, LIVE_ORIGINAL, LIVE_G1)],
    "G2-helper-flat-keys": [(PG, LIVE_ORIGINAL, LIVE_G2),
                            (PG, "    /** The reservation the quota cases place:", G2_HELPER)],
    "B1-delete-sort": [B1],
    "B1b-sort-by-label": [B1B],
    "B1c-lock-taken-on-label": [B1C],
}
for name, (path, old, new) in SILENT.items():
    CASES[name] = [(path, old, new)]


def run(label, edits):
    verify.MUTATIONS.clear()
    for path, old, new in edits:
        verify.MUTATIONS.setdefault(path, []).append((old, new))
    stale, results = None, []
    try:
        missing = [old[:70] for path, old, _n in edits
                   if old not in Path(path).read_text(encoding="utf-8", errors="replace")]
        if missing:
            stale = missing
        else:
            results = verify.run_checks()
    except SystemExit as raised:
        stale = ["verify.mutate raised: " + str(raised)]
    finally:
        verify.MUTATIONS.clear()
    red = [{"gate": name, "detail": detail} for name, ok, detail in results if not ok]
    return {"case": label, "stale": stale, "redCount": len(red),
            "green": f"{len(results) - len(red)}/{len(results)}",
            "redGates": [x["gate"] for x in red],
            "details": [x["detail"][:1200] for x in red]}


if __name__ == "__main__":
    chosen = sys.argv[1:] or list(CASES)
    out = [run(label, CASES[label]) for label in chosen]
    print(json.dumps(out, ensure_ascii=False, indent=2), flush=True)

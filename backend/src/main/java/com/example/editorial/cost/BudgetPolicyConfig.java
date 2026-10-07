package com.example.editorial.cost;

import com.example.editorial.shared.PublicFailure;
import java.util.EnumMap;
import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.core.env.ConfigurableEnvironment;
import org.springframework.core.env.EnumerablePropertySource;
import org.springframework.core.env.Environment;
import org.springframework.core.env.PropertySource;

/**
 * Builds the {@link BudgetPolicy} from configuration, so a deployment that sets nothing still gets the ceilings
 * the SRS states instead of an accidental "unlimited".
 *
 * <p>Provenance, line by line in {@code docs/AI-Editorial-Agent-SRS-v1.0.md}: the six count ceilings
 * (30 search queries per article, 40000 billed output tokens per article, 3 queries per claim, 1 automatic
 * revision loop, 2 image units per slot, 4 image units per article) are the limits listed in SRS 32.2 (line
 * 1103); the 20 USD daily ceiling is the daily-budget example of SRS 32.2 (line 1099, alongside the 5 USD
 * per-article example, which is per-article data on {@code article_job.budget_limit}, not a deployment default);
 * the 80% alert line is the "预算 &gt;80%" trigger of SRS 32.3 (line 1143). Those eight numbers are the documented
 * defaults and nothing else is invented here.</p>
 *
 * <p>Two ceilings the SRS does not state carry <em>no</em> default: the per-article call cap
 * ({@code editorial.cost.max-calls-per-article}) and the reconciliation window
 * ({@code editorial.cost.reconciliation-stale-minutes}). Enabling cost without writing them fails closed with
 * 503 {@code QUOTA_NOT_CONFIGURED} — an unapproved number is not a reason to guess one.</p>
 *
 * <p>All of it remains 示例值, not approved limits: SRS 37 OQ-09 (line 1281) keeps "预算/次数上限的具体值" open
 * with owner 产品 and a due date of 真实 API 测试前. {@code verify.py} re-reads those SRS lines and rejects any
 * drift between the documented numbers and the fallbacks below.</p>
 *
 * <p>Keys are all under {@code editorial.cost.}. Amounts are configured as canonical strings, never floats.
 * Nothing here reads a rate card: prices live in published price versions, and a missing price is unknown,
 * not free.</p>
 *
 * <p>Provider ceilings are configured nested under
 * {@code editorial.cost.provider-quota.<provider>.<leaf>} for a provider-wide ceiling and
 * {@code editorial.cost.provider-quota.<provider>.<model>.<leaf>} for a per-model override, with exactly the two
 * leaves {@code max-concurrent} and {@code calls-per-day} — both required for any scope that is declared at all.
 * Those paths are translated into the one scope spelling {@link BudgetPolicy#scope} defines
 * ({@code provider} and {@code provider|model}; a provider or model segment may not contain a dot), because an
 * entry stored under any other spelling is an entry no lookup can find and a ceiling that silently never applies.
 * Whether a provider that has <em>no</em> entry is open or refused is not inferred either: it comes from the
 * required key {@code editorial.cost.provider-quota.unconfigured} ({@code unlimited} or {@code refuse}), with no
 * default, so "we forgot to write it" cannot turn into "no provider-side limit".</p>
 */
public final class BudgetPolicyConfig {
    private static final String QUOTA_PREFIX = "editorial.cost.provider-quota.";
    /**
     * The reserved leaf under the quota prefix that states what an unlisted provider means. It shares the namespace
     * with provider names, so the name is reserved: a provider actually called {@code unconfigured} — a path like
     * {@code provider-quota.unconfigured.max-concurrent} — is neither read as this switch nor dropped quietly, it
     * fails the boot with 503 {@code INVALID_PROVIDER_QUOTA_KEY}. Nested YAML flattens a model id containing a dot
     * the same way, into a segment count no scope can name, and that is refused too. Absence of this key is
     * likewise a failure, never a default.
     */
    private static final String UNCONFIGURED_LEAF = "unconfigured";

    private BudgetPolicyConfig() {}

    public static BudgetPolicy from(Environment env) {
        Map<BudgetPolicy.Counter, Long> caps = new EnumMap<>(BudgetPolicy.Counter.class);
        // No documented ceiling for the call cap: require it, do not invent 64.
        caps.put(BudgetPolicy.Counter.CALLS, (long) statedCeiling(env, "editorial.cost.max-calls-per-article"));
        caps.put(BudgetPolicy.Counter.SEARCH_QUERY, count(env, "editorial.cost.search-queries-per-article", 30));
        caps.put(BudgetPolicy.Counter.MODEL_OUTPUT_TOKENS,
                count(env, "editorial.cost.model-output-tokens-per-article", 40_000));
        caps.put(BudgetPolicy.Counter.CLAIM_QUERY, count(env, "editorial.cost.queries-per-claim", 3));
        caps.put(BudgetPolicy.Counter.AUTO_EDIT_LOOP, count(env, "editorial.cost.auto-edit-loops-per-article", 1));
        caps.put(BudgetPolicy.Counter.IMAGE_GENERATION_SLOT, count(env, "editorial.cost.image-units-per-slot", 2));
        caps.put(BudgetPolicy.Counter.IMAGE_GENERATION_ARTICLE, count(env, "editorial.cost.image-units-per-article", 4));
        return new BudgetPolicy(Money.of(env.getProperty("editorial.cost.daily-budget", "20.000000")), Map.copyOf(caps),
                quotas(env), env.getProperty("editorial.cost.alert-percent", Integer.class, 80),
                // No documented reconciliation window either: an operator has to state it.
                statedCeiling(env, "editorial.cost.reconciliation-stale-minutes"),
                // And so does the answer to "what about a provider nobody configured a quota for".
                BudgetPolicy.UnconfiguredQuota.of(statedValue(env, QUOTA_PREFIX + UNCONFIGURED_LEAF)));
    }

    /**
     * Provider ceilings, keyed exactly as {@link BudgetPolicy#scope} spells those keys. A path is either
     * {@code <provider>.<leaf>} or {@code <provider>.<model>.<leaf>}; anything longer is a typo that would put
     * the entry where no lookup can reach it, so it is refused rather than filed away. A declared scope must
     * state both leaves: the absent side is not silently treated as unlimited.
     */
    private static Map<String, BudgetPolicy.ProviderQuota> quotas(Environment env) {
        Map<String, Integer> concurrent = new LinkedHashMap<>();
        Map<String, Long> perDay = new LinkedHashMap<>();
        if (env instanceof ConfigurableEnvironment configurable) {
            for (PropertySource<?> source : configurable.getPropertySources()) {
                if (!(source instanceof EnumerablePropertySource<?> enumerable)) continue;
                for (String name : enumerable.getPropertyNames()) {
                    if (!name.startsWith(QUOTA_PREFIX)) continue;
                    String[] path = name.substring(QUOTA_PREFIX.length()).split("\\.");
                    if (path.length == 1 && UNCONFIGURED_LEAF.equals(path[0])) continue;
                    // A quota path without a leaf, or a provider named after the reserved switch, is a mistake
                    // that would otherwise park an entry where no lookup goes: refuse it out loud.
                    if (path.length < 2 || UNCONFIGURED_LEAF.equals(path[0])) {
                        throw new PublicFailure(503, "INVALID_PROVIDER_QUOTA_KEY");
                    }
                    String leaf = path[path.length - 1];
                    String scope = switch (path.length) {
                        case 2 -> BudgetPolicy.scope(path[0], null);
                        case 3 -> BudgetPolicy.scope(path[0], path[1]);
                        default -> throw new PublicFailure(503, "INVALID_PROVIDER_QUOTA_KEY");
                    };
                    switch (leaf) {
                        case "max-concurrent" -> concurrent.put(scope, required(env, name));
                        case "calls-per-day" -> perDay.put(scope, (long) required(env, name));
                        default -> throw new PublicFailure(503, "INVALID_PROVIDER_QUOTA_KEY");
                    }
                }
            }
        }
        Map<String, BudgetPolicy.ProviderQuota> quotas = new LinkedHashMap<>();
        for (String scope : new java.util.TreeSet<>(concatenate(concurrent.keySet(), perDay.keySet()))) {
            Integer held = concurrent.get(scope);
            Long calls = perDay.get(scope);
            if (held == null || calls == null) {
                throw new PublicFailure(503, "QUOTA_NOT_CONFIGURED");
            }
            quotas.put(scope, new BudgetPolicy.ProviderQuota(held, calls));
        }
        return Map.copyOf(quotas);
    }

    private static java.util.Set<String> concatenate(java.util.Set<String> a, java.util.Set<String> b) {
        java.util.Set<String> all = new java.util.LinkedHashSet<>(a);
        all.addAll(b);
        return all;
    }

    private static int required(Environment env, String name) {
        Integer value = env.getProperty(name, Integer.class);
        if (value == null || value < 0) throw new PublicFailure(503, "INVALID_BUDGET_POLICY");
        return value;
    }

    /**
     * A ceiling the SRS does not document, so there is no number to default to and no reason to guess one:
     * leaving it unset refuses the build with the same 503 QUOTA_NOT_CONFIGURED the policy raises when a
     * counter cap is missing, which keeps "absent is not unlimited" true on the configuration path too.
     */
    private static int statedCeiling(Environment env, String key) {
        Integer value = env.getProperty(key, Integer.class);
        if (value == null) throw new PublicFailure(503, "QUOTA_NOT_CONFIGURED");
        if (value < 0) throw new PublicFailure(503, "INVALID_BUDGET_POLICY");
        return value;
    }

    /**
     * A choice the SRS does not make for the deployment, read with no default: unset is 503 QUOTA_NOT_CONFIGURED,
     * the same refusal the count caps raise, so an unstated policy never becomes an inferred one.
     */
    private static String statedValue(Environment env, String key) {
        String value = env.getProperty(key);
        if (value == null || value.isBlank()) throw new PublicFailure(503, "QUOTA_NOT_CONFIGURED");
        return value;
    }

    private static long count(Environment env, String key, int fallback) {
        Integer value = env.getProperty(key, Integer.class, fallback);
        if (value == null || value < 0) throw new PublicFailure(503, "INVALID_BUDGET_POLICY");
        return value;
    }
}

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
 * Builds the {@link BudgetPolicy} from configuration with the SRS 32.2–32.3 defaults, so a deployment that sets
 * nothing still gets the documented ceilings (30 queries per article, 40000 billed output tokens per article,
 * 3 queries per claim, 1 automatic revision loop, 2 image units per slot, 4 per article, a 20 USD daily
 * ceiling, an 80% alert line) instead of an accidental "unlimited".
 *
 * <p>Keys are all under {@code editorial.cost.}. Amounts are configured as canonical strings, never floats.
 * Nothing here reads a rate card: prices live in published price versions, and a missing price is unknown,
 * not free. Provider quotas are optional and keyed {@code editorial.cost.provider-quota.<provider>[_<model>]}
 * with {@code .max-concurrent} and {@code .calls-per-day}.</p>
 */
public final class BudgetPolicyConfig {
    private static final String QUOTA_PREFIX = "editorial.cost.provider-quota.";

    private BudgetPolicyConfig() {}

    public static BudgetPolicy from(Environment env) {
        Map<BudgetPolicy.Counter, Long> caps = new EnumMap<>(BudgetPolicy.Counter.class);
        caps.put(BudgetPolicy.Counter.CALLS, count(env, "editorial.cost.max-calls-per-article", 64));
        caps.put(BudgetPolicy.Counter.SEARCH_QUERY, count(env, "editorial.cost.search-queries-per-article", 30));
        caps.put(BudgetPolicy.Counter.MODEL_OUTPUT_TOKENS,
                count(env, "editorial.cost.model-output-tokens-per-article", 40_000));
        caps.put(BudgetPolicy.Counter.CLAIM_QUERY, count(env, "editorial.cost.queries-per-claim", 3));
        caps.put(BudgetPolicy.Counter.AUTO_EDIT_LOOP, count(env, "editorial.cost.auto-edit-loops-per-article", 1));
        caps.put(BudgetPolicy.Counter.IMAGE_GENERATION_SLOT, count(env, "editorial.cost.image-units-per-slot", 2));
        caps.put(BudgetPolicy.Counter.IMAGE_GENERATION_ARTICLE, count(env, "editorial.cost.image-units-per-article", 4));
        return new BudgetPolicy(Money.of(env.getProperty("editorial.cost.daily-budget", "20.000000")), Map.copyOf(caps),
                quotas(env), env.getProperty("editorial.cost.alert-percent", Integer.class, 80),
                env.getProperty("editorial.cost.reconciliation-stale-minutes", Integer.class, 30));
    }

    /** Optional provider ceilings; a provider with no entry is limited only by the budgets above it. */
    private static Map<String, BudgetPolicy.ProviderQuota> quotas(Environment env) {
        Map<String, Integer> concurrent = new LinkedHashMap<>();
        Map<String, Long> perDay = new LinkedHashMap<>();
        if (env instanceof ConfigurableEnvironment configurable) {
            for (PropertySource<?> source : configurable.getPropertySources()) {
                if (!(source instanceof EnumerablePropertySource<?> enumerable)) continue;
                for (String name : enumerable.getPropertyNames()) {
                    if (!name.startsWith(QUOTA_PREFIX)) continue;
                    String key = name.substring(QUOTA_PREFIX.length());
                    int dot = key.lastIndexOf('.');
                    if (dot < 1) throw new PublicFailure(503, "INVALID_PROVIDER_QUOTA_KEY");
                    switch (key.substring(dot + 1)) {
                        case "max-concurrent" -> concurrent.put(key.substring(0, dot), required(env, name));
                        case "calls-per-day" -> perDay.put(key.substring(0, dot), (long) required(env, name));
                        default -> throw new PublicFailure(503, "INVALID_PROVIDER_QUOTA_KEY");
                    }
                }
            }
        }
        // A ceiling that was not configured is unlimited rather than zero, so only the metrics an operator wrote
        // apply; the record still refuses a negative value, which is why the absent side is the largest number.
        Map<String, BudgetPolicy.ProviderQuota> quotas = new LinkedHashMap<>();
        for (String scope : new java.util.TreeSet<>(concatenate(concurrent.keySet(), perDay.keySet()))) {
            quotas.put(scope, new BudgetPolicy.ProviderQuota(
                    concurrent.getOrDefault(scope, Integer.MAX_VALUE), perDay.getOrDefault(scope, Long.MAX_VALUE)));
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

    private static long count(Environment env, String key, int fallback) {
        Integer value = env.getProperty(key, Integer.class, fallback);
        if (value == null || value < 0) throw new PublicFailure(503, "INVALID_BUDGET_POLICY");
        return value;
    }
}

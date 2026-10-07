package com.example.editorial.cost;

import com.example.editorial.shared.PublicFailure;
import java.math.BigDecimal;
import java.util.Map;

/**
 * Configured budget, quota and count limits (SRS 32.2–32.3). A limit that is not configured fails closed:
 * the cost domain never treats "no configuration" as "unlimited" for a chargeable call, because the article
 * budget and the daily ceiling are what keep a paid provider from being called at all.
 *
 * <p>{@code caps} are the count ceilings measured per scope (search queries per article, model output tokens
 * per article, queries per claim, auto-edit loops, image units per slot and per article). Amount ceilings are
 * money, and the alert percent is the crossing point at which budget warning data is produced (SRS 34).</p>
 */
public record BudgetPolicy(Money dailyLimit, Map<BudgetPolicy.Counter, Long> caps, Map<String, ProviderQuota> providers,
                           int alertPercent, int staleReconciliationMinutes, UnconfiguredQuota unconfigured) {

    /**
     * What a provider/model with no configured quota means. There is deliberately no default: absence of a quota
     * is a decision the deployment has to state, because reading it as "unlimited" silently fail-opens every
     * provider that was forgotten.
     */
    public enum UnconfiguredQuota {
        /** The Owner accepts that an unlisted provider/model carries no provider-side ceiling. */
        UNLIMITED,
        /** Nothing is admitted for a provider/model without an entry: 503 PROVIDER_QUOTA_NOT_CONFIGURED. */
        REFUSE;

        public static UnconfiguredQuota of(String value) {
            try {
                return valueOf(value.trim().toUpperCase(java.util.Locale.ROOT));
            } catch (IllegalArgumentException | NullPointerException wrong) {
                throw new PublicFailure(503, "INVALID_BUDGET_POLICY");
            }
        }
    }

    /**
     * The one canonical spelling of a provider-side scope: {@code provider} for a provider-wide ceiling,
     * {@code provider|model} for a per-model override. Every producer and every reader of the {@code providers}
     * map goes through this method — a scope assembled any other way is a scope no lookup can ever find.
     */
    public static String scope(String provider, String model) {
        if (provider == null || provider.isBlank()) throw new PublicFailure(503, "INVALID_PROVIDER_QUOTA_KEY");
        return model == null || model.isBlank() ? provider : provider + "|" + model;
    }

    /** Counter families that carry a maximum. Every counter is checked while its scope lock is held. */
    public enum Counter {
        /** One chargeable call, counted per article and per provider window. */
        CALLS,
        /** Retrieval queries issued for the article. */
        SEARCH_QUERY,
        /** Model output tokens billed for the article. */
        MODEL_OUTPUT_TOKENS,
        /** Retrieval queries issued while verifying one claim. */
        CLAIM_QUERY,
        /** Automatic revision loops started for the article. */
        AUTO_EDIT_LOOP,
        /** Image units generated for one image slot. */
        IMAGE_GENERATION_SLOT,
        /** Image units generated for the article. */
        IMAGE_GENERATION_ARTICLE;

        public static Counter of(String raw) {
            try { return valueOf(raw); }
            catch (IllegalArgumentException | NullPointerException e) { throw new PublicFailure(422, "INVALID_QUOTA_COUNTER"); }
        }
    }

    /** Provider-side quota as SRS 32.2 requires it to be configured independently of the article budget. Both
     * sides are stated by {@code BudgetPolicyConfig}: an omitted side is a configuration gap, not "unlimited". */
    public record ProviderQuota(int maxConcurrent, long callsPerDay) {
        public ProviderQuota {
            if (maxConcurrent < 0 || callsPerDay < 0) throw new PublicFailure(503, "INVALID_BUDGET_POLICY");
        }
    }

    public BudgetPolicy {
        caps = Map.copyOf(caps);
        providers = Map.copyOf(providers);
        if (unconfigured == null) throw new PublicFailure(503, "INVALID_BUDGET_POLICY");
        // Every stored scope has to be spelled the way every lookup spells it, or the entry is unreachable and
        // the ceiling it was meant to impose silently never applies. A dot in a key is that bug, so it is refused.
        for (String scope : providers.keySet()) {
            if (scope.isBlank() || scope.contains(".") || scope.startsWith("|") || scope.endsWith("|")) {
                throw new PublicFailure(503, "INVALID_PROVIDER_QUOTA_KEY");
            }
        }
        if (alertPercent < 1 || alertPercent > 100) throw new PublicFailure(503, "INVALID_BUDGET_POLICY");
        if (staleReconciliationMinutes < 1) throw new PublicFailure(503, "INVALID_BUDGET_POLICY");
    }

    public long cap(Counter counter) {
        Long cap = caps.get(counter);
        if (cap == null) throw new PublicFailure(503, "QUOTA_NOT_CONFIGURED");
        return cap;
    }

    /** Quotas are keyed by {@link #scope}: the {@code provider|model} override first, then the provider-wide entry. */
    public java.util.Optional<ProviderQuota> providerQuota(String provider, String model) {
        String scope = quotaScope(provider, model);
        return scope == null ? java.util.Optional.empty() : java.util.Optional.of(providers.get(scope));
    }

    /**
     * The scope that actually answers for this provider/model, or {@code null} when nothing is configured for it.
     * Returning the key rather than only the value is what lets the service measure a provider-wide ceiling
     * across the provider's models instead of pretending the two levels share one window.
     */
    public String quotaScope(String provider, String model) {
        String exact = scope(provider, model);
        if (providers.containsKey(exact)) return exact;
        String wide = scope(provider, null);
        return providers.containsKey(wide) ? wide : null;
    }

    public boolean hasCap(Counter counter) { return caps.containsKey(counter); }

    /** True once spend plus live holds reach the configured warning line of the ceiling. */
    public boolean reachedAlert(Money occupied, Money limit) {
        if (limit.isZero()) return true;
        // Exact decimal comparison scaled by 100: no float, and no Money range limit on the intermediate.
        BigDecimal used = occupied.decimal().movePointRight(2);
        BigDecimal threshold = limit.decimal().multiply(BigDecimal.valueOf(alertPercent));
        return used.compareTo(threshold) >= 0;
    }
}

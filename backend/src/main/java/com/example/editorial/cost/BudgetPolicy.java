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
                           int alertPercent, int staleReconciliationMinutes) {

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

    /** Provider-side quota as SRS 32.2 requires it to be configured independently of the article budget. */
    public record ProviderQuota(int maxConcurrent, long callsPerDay) {
        public ProviderQuota {
            if (maxConcurrent < 0 || callsPerDay < 0) throw new PublicFailure(503, "INVALID_BUDGET_POLICY");
        }
    }

    public BudgetPolicy {
        caps = Map.copyOf(caps);
        providers = Map.copyOf(providers);
        if (alertPercent < 1 || alertPercent > 100) throw new PublicFailure(503, "INVALID_BUDGET_POLICY");
        if (staleReconciliationMinutes < 1) throw new PublicFailure(503, "INVALID_BUDGET_POLICY");
    }

    public long cap(Counter counter) {
        Long cap = caps.get(counter);
        if (cap == null) throw new PublicFailure(503, "QUOTA_NOT_CONFIGURED");
        return cap;
    }

    /** Quotas are keyed by {@code provider} first and by {@code provider|model} for a tighter override. */
    public java.util.Optional<ProviderQuota> providerQuota(String provider, String model) {
        ProviderQuota exact = providers.get(provider + "|" + model);
        return java.util.Optional.ofNullable(exact != null ? exact : providers.get(provider));
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

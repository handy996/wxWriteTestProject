package com.example.editorial.cost;

import com.example.editorial.shared.PublicFailure;
import java.math.BigDecimal;
import java.util.Map;
import java.util.Optional;
import java.util.regex.Pattern;

/**
 * Configured budget, quota and count limits (SRS 32.2–32.3). A limit that is not configured fails closed:
 * the cost domain never treats "no configuration" as "unlimited" for a chargeable call, because the article
 * budget and the daily ceiling are what keep a paid provider from being called at all.
 *
 * <p>{@code caps} are the count ceilings measured per scope (search queries per article, model output tokens
 * per article, queries per claim, auto-edit loops, image units per slot and per article). Amount ceilings are
 * money, and the alert percent is the crossing point at which budget warning data is produced (SRS 34).</p>
 *
 * <p>Provider ceilings are two-level and — this is the round-3 ruling, not an inference from the map —
 * <em>both levels are enforced</em>: a {@code provider|model} entry caps that one model's window, a
 * {@code provider} entry caps the provider summed across every model it serves, and a call has to fit every
 * window whose entry exists. A model entry looser than its provider entry therefore never lifts the
 * provider-wide ceiling above itself; the stricter answer wins. Which window each entry speaks about is
 * {@code BudgetService}'s job, measured through the scope this record exposes.</p>
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
     * The characters a provider or model id may use inside a scope. {@code |} is excluded on purpose: it is the
     * separator below, so an id containing it would make {@code p|q} (one provider) and {@code p}+{@code q}
     * (a model override) the same key — two entries that then silently overwrite each other, which the
     * round-3 reviewer demonstrated with a mixed {@code {p|q=[9,1]}} document. Dots are allowed for the
     * <em>lookup</em> of a dotted model id (the provider-level window meters those rows correctly, measured in
     * round 3), but a model-level entry for a dotted id cannot be spelled as a configuration key — see
     * {@code BudgetPolicyConfig} — so the dot boundary is a ruled capability limit, not an oversight, and an
     * {@code entries[]} list shape that would lift it is the Owner's open decision, not this record's.
     */
    private static final Pattern SEGMENT_SHAPE = Pattern.compile("[A-Za-z0-9._-]+");

    /**
     * The one canonical spelling of a provider-side scope: {@code provider} for a provider-wide ceiling,
     * {@code provider|model} for a per-model override. Every producer and every reader of the {@code providers}
     * map goes through this method — a scope assembled any other way is a scope no lookup can ever find.
     * A segment outside {@link #SEGMENT_SHAPE} (above all one containing {@code |}) is refused here, loudly, so
     * the collision the separator would enable cannot be built by the config path or walked into by a request.
     */
    public static String scope(String provider, String model) {
        if (provider == null || provider.isBlank()) throw new PublicFailure(503, "INVALID_PROVIDER_QUOTA_KEY");
        if (!SEGMENT_SHAPE.matcher(provider).matches()) throw new PublicFailure(503, "INVALID_PROVIDER_QUOTA_KEY");
        if (model == null || model.isBlank()) return provider;
        if (!SEGMENT_SHAPE.matcher(model).matches()) throw new PublicFailure(503, "INVALID_PROVIDER_QUOTA_KEY");
        return provider + "|" + model;
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
     * sides are stated by {@code BudgetPolicyConfig}: an omitted side is a configuration gap, not "unlimited".
     * {@code maxConcurrent} is at least one — a zero concurrency limit is not "closed" but "wedge", and a
     * document that says it means a misconfiguration (round-3 ruling F-08). {@code callsPerDay} may be zero,
     * and zero means the day is closed: no call is admitted, which is a stated operational choice. */
    public record ProviderQuota(int maxConcurrent, long callsPerDay) {
        public ProviderQuota {
            if (maxConcurrent < 1 || callsPerDay < 0) throw new PublicFailure(503, "INVALID_BUDGET_POLICY");
        }
    }

    public BudgetPolicy {
        caps = Map.copyOf(caps);
        providers = Map.copyOf(providers);
        if (unconfigured == null) throw new PublicFailure(503, "INVALID_BUDGET_POLICY");
        // Every stored scope has to be spelled the way every lookup spells it, or the entry is unreachable and
        // the ceiling it was meant to impose silently never applies. A dot in a key is that bug, so it is
        // refused; so is anything that would parse two ways with the separator ("p||q", "p|q|r").
        for (String stored : providers.keySet()) {
            if (stored.isBlank() || stored.contains(".") || stored.startsWith("|") || stored.endsWith("|")
                    || stored.contains("||") || stored.chars().filter(c -> c == '|').count() > 1) {
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

    /**
     * The model-level entry for this exact provider/model, if the deployment declared one. Equality only — a
     * prefix match would answer a model override written for {@code mock-model} to {@code mock-model-v2} and
     * silently widen a ceiling (round-3 variant probe V4). It caps the window of that one model; the service
     * still measures it together with {@link #providerWideQuota} whenever both exist.
     */
    public Optional<ProviderQuota> modelQuota(String provider, String model) {
        String exact = scope(provider, model);
        return providers.containsKey(exact) ? Optional.of(providers.get(exact)) : Optional.empty();
    }

    /**
     * The provider-wide entry, if declared. It caps the provider summed across every model it serves, so it
     * answers for a dotted model id as well (the key here is the provider alone and carries no dot), and both
     * levels are enforced side by side rather than one shadowing the other (round-3 ruling F-03).
     */
    public Optional<ProviderQuota> providerWideQuota(String provider) {
        String wide = scope(provider, null);
        return providers.containsKey(wide) ? Optional.of(providers.get(wide)) : Optional.empty();
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

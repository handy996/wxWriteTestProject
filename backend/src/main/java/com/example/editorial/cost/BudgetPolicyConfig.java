package com.example.editorial.cost;

import com.example.editorial.shared.PublicFailure;
import java.util.EnumMap;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import org.springframework.boot.context.properties.bind.BindException;
import org.springframework.boot.context.properties.bind.Binder;
import org.springframework.core.env.ConfigurableEnvironment;
import org.springframework.core.env.EnumerablePropertySource;
import org.springframework.core.env.Environment;
import org.springframework.core.env.PropertySource;
import org.springframework.core.env.SystemEnvironmentPropertySource;

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
 * leaves {@code max-concurrent} and {@code calls-per-day} — both required for any scope that is declared at all,
 * {@code max-concurrent} at least one (zero concurrency is a wedge, refused as misconfiguration) and
 * {@code calls-per-day} zero allowed with the meaning "the day is closed". Those paths are translated into the
 * one scope spelling {@link BudgetPolicy#scope} defines ({@code provider} and {@code provider|model}). Both
 * declared levels are enforced together — the layering is "each level binds its own window, the stricter wins",
 * decided in round 3, and it is {@code BudgetService} that measures each window. A segment outside
 * {@code [A-Za-z0-9._-]} (above all one containing the separator {@code |}, which would collide two different
 * entries onto the same key) fails the boot with 503 {@code INVALID_PROVIDER_QUOTA_KEY}, so a mixed
 * {@code p|q}-plus-{@code p.q} document cannot silently overwrite either side.</p>
 *
 * <p>Whether a provider that has <em>no</em> entry is open or refused is not inferred either: it comes from the
 * required key {@code editorial.cost.provider-quota.unconfigured} ({@code unlimited} or {@code refuse}), with no
 * default, so "we forgot to write it" cannot turn into "no provider-side limit".</p>
 *
 * <p>The quota subtree is enumerated through Spring's own relaxed binding (round-3 finding F-01): the literal
 * dotted names as written, plus — because {@code SystemEnvironmentPropertySource} answers a canonical name for
 * its {@code EDITORIAL_COST_…} keys — the OS-environment spelling of the same subtree. Before this, an operator
 * who set quotas through environment variables booted green with every provider silently unlimited: the switch
 * was read relaxed while the enumeration matched literal names only, and "configured but not in effect" was
 * alive again through a different channel. In the environment spelling {@code _} stands for both {@code .} and
 * {@code -}, so only readings with exactly one correct answer are accepted there (a single-segment provider id
 * plus one known leaf); a model-level entry or a dashed id arrives as {@code A_B_C} and cannot be recovered
 * unambiguously — Spring itself resolves both {@code open-ai.max-concurrent} and {@code open.ai.max-concurrent}
 * against the same key — so such names are refused at load, loudly, never guessed.</p>
 *
 * <p>Three boundaries of that same environment channel, each measured in round 4 rather than assumed. A
 * {@code EDITORIAL_COST_…} name that says {@code quota} but is not on the quota prefix is this subtree misspelled
 * ({@code …PROVIDER_QUOTAS_MOCK_MAX_CONCURRENT}, one letter) and now refuses the boot instead of enumerating
 * nothing (finding F-R4-02). A canonical dotted name found <em>inside</em> an environment-shaped source goes to
 * the canonical reader rather than being skipped, so one source cannot be half-visible to {@code getProperty()}
 * and invisible to the provider map (finding F-R4-05). And because the flattened name reaches us upper-cased and
 * is stored lower-cased, the environment addresses <strong>all-lowercase provider ids only</strong>:
 * {@code …QUOTA_MOCK_MAX_CONCURRENT} binds the key {@code mock}, and a real id spelled {@code MOCK} is not
 * reachable through this channel at all — under {@code unconfigured=refuse} that is a 503 at the call, under
 * {@code unlimited} it is a ceiling quietly not applying, which is why the shape is pinned by
 * {@code CostPricingTest#environmentChannelAddressesProvidersInLowerCaseOnly} rather than smoothed over
 * (finding F-R4-03). The measurement closed a sentence this class used to carry: capitals are not reachable
 * through the canonical channel either. {@code editorial.cost.provider-quota.MOCK.max-concurrent} is a name the
 * binder itself refuses ({@code InvalidConfigurationPropertyNameException}, raised before any value is read), so
 * the id charset {@link BudgetPolicy#scope} allows is wider than what configuration can address — an id carrying
 * capitals can be metered once something else hands it over, but it cannot be capped from a file. That refusal
 * reached us as a raw stack trace, outside the normalization round-3 finding F-08 established for unreadable
 * leaves, so {@link #quotaLeaf} and {@link #dayCountLeaf} take it in and answer the same structured 503
 * {@code INVALID_BUDGET_POLICY}: loud on both channels, and never a capital quietly becoming a lowercase key.</p>
 *
 * <p>The two leaves are read as the types the record stores them in (finding F-R4-04):
 * {@code max-concurrent} binds an {@code Integer} because {@link BudgetPolicy.ProviderQuota} declares one, and
 * {@code calls-per-day} binds a {@code Long} because that field is a {@code long} — reading it as an
 * {@code Integer} made the configuration surface narrower than the value it fills, so a legal
 * {@code 99999999999} was refused with 503. Either side normalizes a value it cannot read into the same
 * structured 503 {@code INVALID_BUDGET_POLICY}.</p>
 *
 * <p>Capability boundary, ruled in round 3 and deliberately not widened here: a model id containing a dot has
 * no model-level configuration key — nested YAML flattens the dot into a path segment the scope cannot name,
 * and the environment channel is ambiguous for it too — while provider-level configuration still meters those
 * rows correctly through the provider-wide window. An {@code entries[]} list shape that would let any id be
 * stated exactly is the Owner's open decision; this code introduces no escape syntax for it.</p>
 */
public final class BudgetPolicyConfig {
    private static final String QUOTA_PREFIX = "editorial.cost.provider-quota.";
    /** The OS-environment spelling of {@link #QUOTA_PREFIX} as {@code SystemEnvironmentPropertySource} names it. */
    private static final String ENVIRONMENT_QUOTA_PREFIX = "editorial_cost_provider_quota_";
    /**
     * Round-4 finding F-R4-02 measured what a silent miss costs here: {@code EDITORIAL_COST_PROVIDER_QUOTAS_…}
     * (this prefix with one letter added) is not an unrelated variable, it is the quota subtree misspelled, and it
     * booted green with {@code providers={}} — every provider uncapped, no warning anywhere. The typo of a prefix
     * always lands inside our own namespace and keeps the word that says what it configures, so the neighbourhood
     * is spelled that way: any {@code EDITORIAL_COST_…} name carrying "quota" that is not on
     * {@link #ENVIRONMENT_QUOTA_PREFIX} refuses assembly, the same way an unknown quota LEAF does. A name in the
     * namespace without that word ({@code EDITORIAL_COST_MAX_CALLS_PER_ARTICLE}) is a different ceiling and stays
     * none of this channel's business.
     */
    private static final String ENVIRONMENT_NAMESPACE = "editorial_cost_";
    private static final String ENVIRONMENT_QUOTA_MARKER = "quota";
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
     * Provider ceilings, keyed exactly as {@link BudgetPolicy#scope} spells those keys. A declared path is either
     * {@code <provider>.<leaf>} or {@code <provider>.<model>.<leaf>}; anything longer is a typo that would put
     * the entry where no lookup can reach it, so it is refused rather than filed away. A declared scope must
     * state both leaves: the absent side is not silently treated as unlimited.
     *
     * <p>Values are read through {@link Binder} — Spring's own relaxed binding — rather than by matching the
     * enumerated name literally, so the two channels that address one subtree (property names as written, and
     * the {@code EDITORIAL_COST_…} spelling of the same names on a {@link SystemEnvironmentPropertySource})
     * bind identically instead of the environment channel silently producing an empty provider map (round-3
     * finding F-01). The binder was probed before choosing this shape: {@code mapOf} enumeration does not see
     * environment-shaped keys under a dashed prefix at all, so the enumeration walks the names and every leaf
     * value goes through {@code Binder.bind} by its canonical name.</p>
     */
    private static Map<String, BudgetPolicy.ProviderQuota> quotas(Environment env) {
        Map<String, Integer> concurrent = new LinkedHashMap<>();
        Map<String, Long> perDay = new LinkedHashMap<>();
        if (env instanceof ConfigurableEnvironment configurable) {
            Binder binder = Binder.get(configurable);
            for (PropertySource<?> source : configurable.getPropertySources()) {
                if (!(source instanceof EnumerablePropertySource<?> enumerable)) continue;
                boolean environmentShaped = source instanceof SystemEnvironmentPropertySource;
                for (String name : enumerable.getPropertyNames()) {
                    if (environmentShaped) environmentQuotaName(binder, name, concurrent, perDay);
                    else canonicalQuotaName(binder, name, concurrent, perDay);
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

    /** Property names as written (files, YAML flattening, fixtures): the literal dotted paths, unchanged rules. */
    private static void canonicalQuotaName(Binder binder, String name, Map<String, Integer> concurrent,
                                           Map<String, Long> perDay) {
        if (!name.startsWith(QUOTA_PREFIX)) return;
        String[] path = name.substring(QUOTA_PREFIX.length()).split("\\.");
        if (path.length == 1 && UNCONFIGURED_LEAF.equals(path[0])) return;
        // A quota path without a leaf, or a provider named after the reserved switch, is a mistake that would
        // otherwise park an entry where no lookup goes: refuse it out loud.
        if (path.length < 2 || UNCONFIGURED_LEAF.equals(path[0])) {
            throw new PublicFailure(503, "INVALID_PROVIDER_QUOTA_KEY");
        }
        String leaf = path[path.length - 1];
        String scope = switch (path.length) {
            case 2 -> BudgetPolicy.scope(path[0], null);
            case 3 -> BudgetPolicy.scope(path[0], path[1]);
            default -> throw new PublicFailure(503, "INVALID_PROVIDER_QUOTA_KEY");
        };
        readQuotaLeaf(binder, name, scope, leaf, concurrent, perDay);
    }

    /**
     * The OS-environment spelling of the same subtree. Accepted only where the flattened name has one correct
     * reading (see the class comment): the reserved switch, or exactly one provider segment plus one known
     * leaf. Anything else under the prefix — a model level, a dashed or underscored id, an unknown leaf —
     * would be a guess, and a guess here is the round-3 defect rebuilt with the polarity flipped: refuse the
     * boot instead. Quotas that need those shapes belong in YAML or a properties file, where the name is the
     * value it claims to be.
     *
     * <p>One boundary this channel cannot cross, pinned by a case rather than fixed (round-4 finding F-R4-03):
     * the environment's own convention upper-cases names, and the provider segment is stored <em>lower-cased</em>,
     * so this channel addresses <strong>all-lowercase provider ids only</strong>. A provider whose real id
     * carries capitals ({@code MOCK}) configured as {@code EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MAX_CONCURRENT}
     * binds the key {@code mock} and {@code providerWideQuota("MOCK")} is then empty — under
     * {@code unconfigured=refuse} that surfaces as 503 {@code PROVIDER_QUOTA_NOT_CONFIGURED} rather than an
     * uncapped call, under {@code unlimited} it is the ceiling quietly not applying. Refusing every upper-cased
     * segment instead would refuse the convention itself, so the shape is documented and pinned by
     * {@code CostPricingTest#environmentChannelAddressesProvidersInLowerCaseOnly}. Capitals are not rescued by
     * the other channel either: {@code editorial.cost.provider-quota.MOCK.max-concurrent} is a name Spring's
     * binder refuses before reading it, and {@link #quotaLeaf} answers that refusal as the structured 503 too —
     * so an id carrying capitals can be metered but cannot be capped from configuration at all, which is the
     * boundary the round-4 review asked to have written down instead of discovered.
     */
    private static void environmentQuotaName(Binder binder, String name, Map<String, Integer> concurrent,
                                             Map<String, Long> perDay) {
        // Round-4 finding F-R4-05: an environment-shaped source answers canonical dotted names through
        // getProperty() like any other source, so this channel may not enumerate around them. Both spellings
        // inside one source now arrive at the same provider map; the class comment on the two channels holds.
        if (name.startsWith(QUOTA_PREFIX)) {
            canonicalQuotaName(binder, name, concurrent, perDay);
            return;
        }
        String lowered = name.toLowerCase(Locale.ROOT);
        if (!lowered.startsWith(ENVIRONMENT_QUOTA_PREFIX)) {
            // Round-4 finding F-R4-02: EDITORIAL_COST_PROVIDER_QUOTAS_… is this subtree misspelled by one letter,
            // and skipping it booted green with every provider uncapped. A name in our namespace that says "quota"
            // therefore refuses the boot unless it is on the exact prefix; a name without that word is a different
            // ceiling and stays none of this method's business.
            if (lowered.startsWith(ENVIRONMENT_NAMESPACE) && lowered.contains(ENVIRONMENT_QUOTA_MARKER)) {
                throw new PublicFailure(503, "INVALID_PROVIDER_QUOTA_KEY");
            }
            return;
        }
        String[] tail = lowered.substring(ENVIRONMENT_QUOTA_PREFIX.length()).split("_");
        if (tail.length == 1 && UNCONFIGURED_LEAF.equals(tail[0])) return;
        String leaf;
        int leafParts;
        if (tail.length >= 3 && "calls".equals(tail[tail.length - 3]) && "per".equals(tail[tail.length - 2])
                && "day".equals(tail[tail.length - 1])) {
            leaf = "calls-per-day";
            leafParts = 3;
        } else if (tail.length >= 2 && "max".equals(tail[tail.length - 2]) && "concurrent".equals(tail[tail.length - 1])) {
            leaf = "max-concurrent";
            leafParts = 2;
        } else {
            throw new PublicFailure(503, "INVALID_PROVIDER_QUOTA_KEY");
        }
        // Exactly one unambiguous provider segment: a model level or a dashed/underscored id would arrive as
        // A_B_C and have two readings, and a reading nobody can verify is refused here, not guessed (see the
        // class comment). Mirror the canonical channel's reserved-word rule as well.
        if (tail.length - leafParts != 1 || UNCONFIGURED_LEAF.equals(tail[0])) {
            throw new PublicFailure(503, "INVALID_PROVIDER_QUOTA_KEY");
        }
        String provider = tail[0];
        String scope = BudgetPolicy.scope(provider, null);
        readQuotaLeaf(binder, QUOTA_PREFIX + provider + "." + leaf, scope, leaf, concurrent, perDay);
    }

    private static void readQuotaLeaf(Binder binder, String canonical, String scope, String leaf,
                                      Map<String, Integer> concurrent, Map<String, Long> perDay) {
        switch (leaf) {
            case "max-concurrent" -> concurrent.put(scope, quotaLeaf(binder, canonical));
            // Round-4 finding F-R4-04: the day count is a long in the record, so it binds as one. Read as an
            // Integer it refused 99999999999 — a value BudgetPolicy.ProviderQuota carries — with 503, which is
            // loud but wrong: the configuration surface may not be narrower than the field it fills.
            case "calls-per-day" -> perDay.put(scope, dayCountLeaf(binder, canonical));
            default -> throw new PublicFailure(503, "INVALID_PROVIDER_QUOTA_KEY");
        }
    }

    /**
     * One quota leaf, read through the binder. An unreadable value is a configuration failure, not a stack
     * trace: a non-numeric leaf arrives from Spring as {@code BindException}/{@code ConversionFailedException}
     * and is normalized into the same structured 503 every other malformed quota raises (round-3 finding
     * F-08). The third shape that arrives as a stack trace is a NAME Spring cannot spell — an uppercase
     * segment in a canonical dotted key is refused by the binder before any value is read
     * ({@code InvalidConfigurationPropertyNameException}), which round-4 finding F-R4-03 pinned as the price of
     * the environment channel's lowercase convention: capitals are not addressable on either channel, and the
     * refusal is loud in both. A negative leaf is refused here; {@code max-concurrent: 0} is refused by
     * {@link BudgetPolicy.ProviderQuota} as the wedge it is, and {@code calls-per-day: 0} passes as the closed
     * day it means.
     */
    private static int quotaLeaf(Binder binder, String name) {
        Integer value;
        try {
            value = binder.bind(name, Integer.class).orElse(null);
        } catch (BindException | org.springframework.core.convert.ConversionFailedException
                | org.springframework.boot.context.properties.source.InvalidConfigurationPropertyNameException
                unreadable) {
            throw new PublicFailure(503, "INVALID_BUDGET_POLICY");
        }
        if (value == null || value < 0) throw new PublicFailure(503, "INVALID_BUDGET_POLICY");
        return value;
    }

    /**
     * The {@code calls-per-day} leaf, read as the {@code long} {@link BudgetPolicy.ProviderQuota} actually stores
     * it in (round-4 finding F-R4-04: this side went through {@link #quotaLeaf}, so a legal
     * {@code 99999999999} was refused with 503 by a surface narrower than its own field). Same normalization as
     * {@link #quotaLeaf} — an unreadable or negative value, or a name the binder cannot parse, is the structured
     * 503 and never a conversion stack — and the same boundary in the other direction: {@code max-concurrent}
     * stays an {@code int} because that field is an {@code int}, so a concurrency ceiling beyond
     * {@code 2147483647} is a refusal, not a truncation.
     */
    private static long dayCountLeaf(Binder binder, String name) {
        Long value;
        try {
            value = binder.bind(name, Long.class).orElse(null);
        } catch (BindException | org.springframework.core.convert.ConversionFailedException
                | org.springframework.boot.context.properties.source.InvalidConfigurationPropertyNameException
                unreadable) {
            throw new PublicFailure(503, "INVALID_BUDGET_POLICY");
        }
        if (value == null || value < 0) throw new PublicFailure(503, "INVALID_BUDGET_POLICY");
        return value;
    }

    private static java.util.Set<String> concatenate(java.util.Set<String> a, java.util.Set<String> b) {
        java.util.Set<String> all = new java.util.LinkedHashSet<>(a);
        all.addAll(b);
        return all;
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

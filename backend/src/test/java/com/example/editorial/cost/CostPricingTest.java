package com.example.editorial.cost;

import static org.junit.jupiter.api.Assertions.*;

import com.example.editorial.shared.CanonicalRequest;
import com.example.editorial.shared.PublicFailure;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.boot.env.YamlPropertySourceLoader;
import org.springframework.core.env.PropertySource;
import org.springframework.core.env.SystemEnvironmentPropertySource;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.mock.env.MockEnvironment;

/**
 * The pricing and ceiling rules that carry no database: fixed-decimal money, the versioned price table, the
 * estimate/actual split, the reasoning double-count guard, settlement shapes and the budget policy defaults.
 * Each case maps to one clause of T08 steps 1–2 plus the price rules on the acceptance card.
 */
class CostPricingTest {
    private static final ObjectMapper JSON = new ObjectMapper();
    private static final UUID PRICE = UUID.fromString("11111111-1111-4111-8111-111111111111");

    private static String entry(String capability, String input, String cached, String output, String reasoning,
                                String search, String image, String other, boolean separate) {
        return "{\"capability\":\"" + capability + "\",\"inputPerMillion\":\"" + input
                + "\",\"cachedInputPerMillion\":\"" + cached + "\",\"outputPerMillion\":\"" + output
                + "\",\"reasoningPerMillion\":\"" + reasoning + "\",\"searchPerCall\":\"" + search
                + "\",\"imagePerUnit\":\"" + image + "\",\"otherPerCall\":\"" + other
                + "\",\"reasoningBilledSeparately\":" + separate + "}";
    }

    private static String rules(String entries) {
        return "{\"schemaVersion\":\"editorial.pricing/1\",\"currency\":\"USD\",\"rounding\":\"CEILING\","
                + "\"entries\":[" + entries + "]}";
    }

    private static PriceVersion priced(String entries) {
        return PricingRules.parse(PRICE, "mock-provider", "mock-model", rules(entries));
    }

    /** Parsing a fixture string is never the point of an assertion, so the checked exception is unwrapped. */
    private static JsonNode tree(String json) {
        try {
            return JSON.readTree(json);
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    private static Usage usage(int input, int cached, int output, Integer reasoning, int images, int searches) {
        return new Usage(input, cached, output, reasoning, images, searches);
    }

    private static PublicFailure failure(Runnable action) {
        try {
            action.run();
        } catch (PublicFailure expected) {
            return expected;
        }
        throw new AssertionError("expected a PublicFailure");
    }

    @Test
    @DisplayName("Amounts are six-decimal strings and nothing else")
    void moneyWire() {
        assertEquals("0.000000", Money.of("0.000000").text());
        assertEquals("12.345678", Money.of("12.345678").text());
        assertEquals("0.000001", Money.of("0.000001").text());
        for (String bad : new String[]{"12.3456789", "0.12345", ".500000", "1E-6", "-1.000000", "01.000000",
                " 1.000000", "1.000000 ", null, "", "9999999999999.000000"}) {
            assertEquals(422, failure(() -> Money.of(bad)).status(), "accepted " + bad);
        }
        assertEquals("USD", Money.CURRENCY);
        assertEquals("UNSUPPORTED_CURRENCY", failure(() -> Money.currency("usd")).code());
        // The wire bound is twelve integer digits, which is what numeric(18,6) holds: the money field is a scaled
        // decimal string, not int32 cents. One digit more than the bound is refused above.
        assertEquals("999999999999.999999", Money.of("999999999999.999999").text());
        // No float path exists: the only ways in are the strict text parse and an already-exact decimal.
        assertEquals("AMOUNT_SCALE", failure(() -> Money.ofExact(new BigDecimal("0.0000001"))).code());
        assertEquals("NEGATIVE_AMOUNT", failure(() -> Money.ofExact(new BigDecimal("-1.000000"))).code());
        assertEquals("INVALID_AMOUNT", failure(() -> Money.ofExact(null)).code());
    }

    @Test
    @DisplayName("A release subtracts and never produces a negative balance")
    void moneyArithmetic() {
        assertEquals("0.300000", Money.of("1.000000").subtract(Money.of("0.700000")).text());
        assertEquals("1.700000", Money.of("1.000000").add(Money.of("0.700000")).text());
        assertEquals("NEGATIVE_AMOUNT", failure(() -> Money.of("0.700000").subtract(Money.of("1.000000"))).code());
        assertTrue(Money.ZERO.isZero());
        assertTrue(Money.of("0.000001").exceeds(Money.ZERO));
        assertEquals("0.000001", Money.of("0.000002").min(Money.of("0.000001")).text());
        assertEquals("0.000002", Money.of("0.000002").max(Money.of("0.000001")).text());
        assertEquals("1.000000", Money.ofExact(new BigDecimal("1")).text(), "an internal decimal scales up to six");
        assertEquals("AMOUNT_SCALE", failure(() -> Money.ofExact(new BigDecimal("0.0000004"))).code());
    }

    @Test
    @DisplayName("A price document refuses floats, duplicates, unknown fields and missing rates")
    void pricingDocumentIsStrict() {
        PublicFailure floatRate = failure(() -> priced(
                "{\"capability\":\"TEXT\",\"inputPerMillion\":2.5,\"cachedInputPerMillion\":\"0.000000000\","
                        + "\"outputPerMillion\":\"10.000000000\",\"reasoningPerMillion\":\"0.000000000\","
                        + "\"searchPerCall\":\"0.000000\",\"imagePerUnit\":\"0.000000\",\"otherPerCall\":\"0.000000\","
                        + "\"reasoningBilledSeparately\":false}"));
        assertEquals(503, floatRate.status());
        assertEquals("PRICING_FLOAT_RATE", floatRate.code());
        String text = entry("TEXT", "2.500000000", "0.000000000", "10.000000000", "0.000000000", "0.000000",
                "0.000000", "0.000000", false);
        assertEquals("PRICING_DUPLICATE_ENTRY", failure(() -> priced(text + "," + text)).code());
        assertEquals("PRICING_UNKNOWN_FIELD", failure(() -> priced(
                text.replace("\"capability\"", "\"capabiity\""))).code());
        assertEquals("PRICING_MISSING_RATE", failure(() -> priced(
                text.replace("\"searchPerCall\":\"0.000000\",", ""))).code());
        assertEquals("PRICING_MISSING_FLAG", failure(() -> priced(
                text.replace(",\"reasoningBilledSeparately\":false", ""))).code());
        assertEquals("PRICING_BAD_RATE", failure(() -> priced(entry("TEXT", "-2.500000000", "0.000000000",
                "10.000000000", "0.000000000", "0.000000", "0.000000", "0.000000", false))).code());
        PriceVersion base = priced(text);
        assertEquals(64, base.hash().length());
        assertEquals(base.hash(), priced(text).hash(), "identical rules must hash identically");
        assertNotEquals(base.hash(), priced(entry("TEXT", "2.500000001", "0.000000000", "10.000000000",
                "0.000000000", "0.000000", "0.000000", "0.000000", false)).hash());
        assertEquals("PRICING_SCHEMA_VERSION", failure(() -> PricingRules.parse(PRICE, "p", "m",
                rules(text).replace("editorial.pricing/1", "editorial.pricing/2"))).code());
        assertEquals("UNSUPPORTED_CURRENCY", failure(() -> PricingRules.parse(PRICE, "p", "m",
                rules(text).replace("\"USD\"", "\"EUR\""))).code());
        assertEquals("PRICING_ROUNDING", failure(() -> PricingRules.parse(PRICE, "p", "m",
                rules(text).replace("\"CEILING\"", "\"FLOOR\""))).code());
        assertEquals("PRICING_ENTRIES", failure(() -> priced("")).code());
        assertEquals("PRICING_UNREADABLE", failure(() -> priced("{not json")).code());
        assertEquals("PRICING_UNAVAILABLE", failure(() -> PricingRules.parse(PRICE, "p", "m", (JsonNode) null)).code());
    }

    @Test
    @DisplayName("Zero price is a published price; a missing price is unknown")
    void zeroIsNotUnknown() {
        PriceVersion free = priced(entry("TEXT", "0.000000000", "0.000000000", "0.000000000", "0.000000000",
                "0.000000", "0.000000", "0.000000", false));
        assertTrue(free.known(Capability.TEXT));
        assertTrue(free.find(Capability.TEXT).orElseThrow().isPublishedFree());
        assertEquals("0.000000", free.estimate(Capability.TEXT, usage(1000, 0, 1000, null, 0, 0), Money.ZERO).text());
        // The same version has no generation price at all: that is unknown, not free.
        assertFalse(free.known(Capability.GENERATION));
        PublicFailure refusal = failure(() -> free.requireGeneratable());
        assertEquals(409, refusal.status());
        assertEquals("GENERATION_PRICE_UNKNOWN", refusal.code());
        assertEquals("PRICING_UNKNOWN", failure(() -> free.estimate(Capability.SEARCH, Usage.zero(), Money.ZERO)).code());
        assertEquals("PRICING_UNKNOWN", failure(() -> free.actual(Capability.SEARCH, Usage.zero(), Money.ZERO)).code());
        // A published zero generation price does admit automatic generation, unlike a missing entry.
        PriceVersion withImage = priced(entry("GENERATION", "0.000000000", "0.000000000", "0.000000000",
                "0.000000000", "0.000000", "0.000000", "0.000000", false));
        assertTrue(withImage.requireGeneratable().isPublishedFree());
        // A priced generation capability with a real unit price costs per unit, and the unknown case never
        // silently falls back to it.
        PriceVersion metered = priced(entry("GENERATION", "0.000000000", "0.000000000", "0.000000000",
                "0.000000000", "0.000000", "0.120000", "0.000000", false));
        assertEquals("0.240000", metered.requireGeneratable().imageCost(2).text());
        assertEquals("0.240000", metered.estimate(Capability.GENERATION, usage(0, 0, 0, null, 2, 0), Money.ZERO).text());
    }

    @Test
    @DisplayName("Cost adds the SRS 32.3 components at six decimals, estimates rounding upward")
    void costFormula() {
        PriceVersion version = priced(entry("TEXT", "2.500000000", "1.000000000", "10.000000000", "0.000000000",
                "0.010000", "0.000000", "0.000000", false));
        PriceEntry text = version.find(Capability.TEXT).orElseThrow();
        Usage used = usage(1000, 400, 500, null, 0, 3);
        // 600 uncached * 2.5/M = 0.001500, 400 cached * 1.0/M = 0.000400, 500 out * 10/M = 0.005000,
        // 3 searches * 0.01 = 0.030000.
        assertEquals("0.001500", text.cost(usage(600, 0, 0, null, 0, 0), Money.ZERO).text());
        assertEquals("0.000400", text.cost(usage(400, 400, 0, null, 0, 0), Money.ZERO).text());
        assertEquals("0.036900", text.cost(used, Money.ZERO).text());
        assertEquals("0.036900", version.estimate(Capability.TEXT, used, Money.ZERO).text());
        // Other provider fees are their own addend and never folded into a token rate.
        assertEquals("0.086900", version.estimate(Capability.TEXT, used, Money.of("0.050000")).text());
        // A sub-minute remainder is never dropped: the estimate must not sit under the published rate.
        assertEquals("0.000003", text.cost(usage(1, 0, 0, null, 0, 0), Money.ZERO).text()); // 1 * 2.5 / 1M, up
        assertEquals("0.010000", text.cost(usage(0, 0, 0, null, 0, 1), Money.ZERO).text()); // 1 search * 0.01
        // Half-up is a legal published rounding and is honoured on settlement.
        PriceVersion halfUp = PricingRules.parse(PRICE, "p", "m", rules(
                entry("TEXT", "2.500000000", "0.000000000", "10.000000000", "0.000000000", "0.000000", "0.000000",
                        "0.000000", false)).replace("\"CEILING\"", "\"HALF_UP\""));
        assertEquals(RoundingMode.HALF_UP, halfUp.find(Capability.TEXT).orElseThrow().rounding());
        assertEquals("0.000500", halfUp.find(Capability.TEXT).orElseThrow().cost(usage(200, 0, 0, null, 0, 0), Money.ZERO).text());
        // Below half a minimum unit the two roundings part: settlement may round down, an estimate may not.
        PriceVersion tiny = PricingRules.parse(PRICE, "p", "m", rules(
                entry("TEXT", "0.400000000", "0.000000000", "0.000000000", "0.000000000", "0.000000", "0.000000",
                        "0.000000", false)).replace("\"CEILING\"", "\"HALF_UP\""));
        PriceEntry tinyText = tiny.find(Capability.TEXT).orElseThrow();
        assertEquals("0.000000", tinyText.cost(usage(1, 0, 0, null, 0, 0), Money.ZERO).text());
        assertEquals("0.000001", tinyText.cost(usage(1, 0, 0, null, 0, 0), Money.ZERO, RoundingMode.CEILING).text());
        assertEquals(RoundingMode.CEILING, PriceVersion.estimateRounding());
    }

    @Test
    @DisplayName("Reasoning tokens are billed exactly once, in either pricing shape")
    void reasoningNeverDoubleCounted() {
        Usage reported = usage(1000, 0, 1000, 400, 0, 0);
        // Shape 1: reasoning already inside the reported output total must not be priced again.
        PriceVersion included = priced(entry("TEXT", "0.000000000", "0.000000000", "10.000000000", "99.000000000",
                "0.000000", "0.000000", "0.000000", false));
        PriceEntry includedText = included.find(Capability.TEXT).orElseThrow();
        assertEquals(1000, includedText.standardOutputTokens(reported));
        assertEquals(0, includedText.reasoningTokens(reported));
        assertEquals(1000, includedText.billedOutputTokens(reported));
        assertEquals("0.010000", includedText.cost(reported, Money.ZERO).text());
        // Shape 2: reasoning billed separately prices only the remainder at the output rate.
        PriceVersion separate = priced(entry("TEXT", "0.000000000", "0.000000000", "10.000000000", "3.000000000",
                "0.000000", "0.000000", "0.000000", true));
        PriceEntry separateText = separate.find(Capability.TEXT).orElseThrow();
        assertEquals(600, separateText.standardOutputTokens(reported));
        assertEquals(400, separateText.reasoningTokens(reported));
        assertEquals(1000, separateText.billedOutputTokens(reported));
        assertEquals("0.007200", separateText.cost(reported, Money.ZERO).text());
        // A provider reporting more reasoning than output is a contract breach, not a bigger bill.
        assertEquals("REASONING_TOKENS_EXCEED_OUTPUT", failure(() -> separateText.cost(
                usage(0, 0, 100, 400, 0, 0), Money.ZERO)).code());
        // No reported reasoning count means no reasoning line, never a guessed one.
        assertEquals(0, separateText.reasoningTokens(usage(0, 0, 100, null, 0, 0)));
        assertEquals("0.001000", separateText.cost(usage(0, 0, 100, null, 0, 0), Money.ZERO).text());
    }

    @Test
    @DisplayName("Cached input is a separate rate and cannot exceed the input total")
    void cachedInputSplit() {
        PriceVersion version = priced(entry("VISION", "2.000000000", "0.500000000", "8.000000000", "0.000000000",
                "0.000000", "0.000000", "0.000000", false));
        PriceEntry vision = version.find(Capability.VISION).orElseThrow();
        assertEquals(700, usage(1000, 300, 0, null, 0, 0).uncachedInputTokens());
        assertEquals("0.001550", vision.cost(usage(1000, 300, 0, null, 0, 0), Money.ZERO).text());
        // All input cached: nothing bills at the uncached rate.
        assertEquals("0.000500", vision.cost(usage(1000, 1000, 0, null, 0, 0), Money.ZERO).text());
        assertEquals("CACHED_RATE_ABOVE_INPUT", failure(() -> PricingRules.parse(PRICE, "p", "m",
                rules(entry("VISION", "2.000000000", "3.000000000", "8.000000000", "0.000000000", "0.000000",
                        "0.000000", "0.000000", false)))).code());
        assertEquals("CACHED_TOKENS_EXCEED_INPUT", failure(() -> usage(100, 200, 0, null, 0, 0)).code());
    }

    @Test
    @DisplayName("Usage parsing accepts exactly the six rc.3 fields and only integers")
    void usageIsStrict() {
        Usage parsed = Usage.read(JSON.createObjectNode().put("inputTokens", 10).put("cachedInputTokens", 4)
                .put("outputTokens", 20).putNull("reasoningTokensIfProvided").put("imageUnits", 0).put("searchCalls", 1));
        assertEquals(Usage.zero().plus(parsed), parsed);
        assertEquals(6, parsed.write(JSON).size(), "usage must round-trip with all six declared fields");
        assertEquals("INVALID_USAGE_INTEGER", failure(() -> Usage.read(tree(
                "{\"inputTokens\":1.5,\"cachedInputTokens\":0,\"outputTokens\":0,"
                        + "\"reasoningTokensIfProvided\":null,\"imageUnits\":0,\"searchCalls\":0}"))).code());
        assertEquals("INVALID_USAGE_INTEGER", failure(() -> Usage.read(tree(
                "{\"inputTokens\":\"0\",\"cachedInputTokens\":0,\"outputTokens\":0,"
                        + "\"reasoningTokensIfProvided\":null,\"imageUnits\":0,\"searchCalls\":0}"))).code());
        assertEquals("UNKNOWN_USAGE_FIELD", failure(() -> Usage.read(tree(
                "{\"inputTokens\":0,\"cachedInputTokens\":0,\"outputTokens\":0,\"reasoningTokensIfProvided\":null,"
                        + "\"imageUnits\":0,\"searchCalls\":0,\"totalTokens\":0}"))).code());
        assertEquals("USAGE_FIELD_MISSING", failure(() -> Usage.read(tree(
                "{\"inputTokens\":0,\"cachedInputTokens\":0,\"outputTokens\":0,\"imageUnits\":0,\"searchCalls\":0}"
        ))).code());
        assertEquals("USAGE_OUT_OF_RANGE", failure(() -> Usage.read(tree(
                "{\"inputTokens\":2147483648,\"cachedInputTokens\":0,\"outputTokens\":0,"
                        + "\"reasoningTokensIfProvided\":null,\"imageUnits\":0,\"searchCalls\":0}"))).code());
        assertEquals("NEGATIVE_USAGE", failure(() -> usage(-1, 0, 0, null, 0, 0)).code());
        assertTrue(Usage.zero().isZero());
        assertEquals(1, Usage.zero().plus(usage(0, 0, 0, 1, 0, 0)).reasoningTokensIfProvided());
    }

    @Test
    @DisplayName("A settlement carries the frozen six fields and its result must fit the amounts")
    void settlementShape() {
        UUID reservation = UUID.fromString("22222222-2222-4222-8222-222222222222");
        UUID key = UUID.fromString("33333333-3333-4333-8333-333333333333");
        String settledJson = "{\"reservationId\":\"" + reservation + "\",\"providerRequestId\":\"req-1\","
                + "\"actualAmount\":\"0.010000\",\"currency\":\"USD\",\"result\":\"SETTLED\","
                + "\"settlementKey\":\"" + key + "\"}";
        // rc.3 declares additionalProperties:false, and its Settlement has no usage field.
        assertEquals("UNKNOWN_SETTLEMENT_FIELD", failure(() -> Settlement.read(JSON, tree(
                settledJson.substring(0, settledJson.length() - 1) + ",\"usage\":{}}"))).code());
        assertEquals("SETTLEMENT_FIELD_MISSING", failure(() -> Settlement.read(JSON, tree(
                settledJson.replace("\"providerRequestId\":\"req-1\",", "")))).code());
        assertEquals("UNSUPPORTED_CURRENCY", failure(() -> Settlement.read(JSON, tree(
                settledJson.replace("\"USD\"", "\"EUR\"")))).code());
        Settlement settled = Settlement.read(JSON, tree(settledJson));
        assertEquals(ReservationStatus.SETTLED, settled.result());
        assertEquals("0.010000", settled.actualAmount().text());
        assertNull(settled.actualUsage(), "rc.3 has no usage field, so usage cannot arrive over the wire");
        assertEquals(6, settled.wire(JSON).size());
        Settlement withUsage = settled.withUsage(JSON, usage(10, 0, 5, null, 0, 0));
        assertNotEquals(settled.requestHash(), withUsage.requestHash(), "attached usage must change the replay hash");
        Settlement replay = Settlement.of(JSON, reservation, "req-1", Money.of("0.010000"),
                ReservationStatus.SETTLED, key, usage(10, 0, 5, null, 0, 0));
        assertEquals(withUsage.requestHash(), replay.requestHash(), "the same facts must replay identically");
        assertNotEquals(withUsage.requestHash(), Settlement.of(JSON, reservation, "req-2", Money.of("0.010000"),
                ReservationStatus.SETTLED, key, usage(10, 0, 5, null, 0, 0)).requestHash());
        assertEquals("UNKNOWN_WITH_AMOUNT", failure(() -> new Settlement(reservation, null, Money.of("0.010000"),
                ReservationStatus.UNKNOWN, key, null, null)).code());
        assertEquals("RELEASE_WITH_AMOUNT", failure(() -> new Settlement(reservation, null, Money.of("0.010000"),
                ReservationStatus.RELEASED, key, null, null)).code());
        assertDoesNotThrow(() -> new Settlement(reservation, null, Money.ZERO, ReservationStatus.RELEASED, key,
                null, null), "releasing with a reported zero is legal");
        assertEquals("INVALID_SETTLEMENT", failure(() -> new Settlement(reservation, null, null,
                ReservationStatus.RESERVED, key, null, null)).code());
        assertEquals("SETTLEMENT_AMOUNT_REQUIRED", failure(() -> new Settlement(reservation, null, null,
                ReservationStatus.SETTLED, key, null, null)).code());
        assertEquals("INVALID_SETTLEMENT", failure(() -> new Settlement(null, null, null,
                ReservationStatus.SETTLED, key, null, null)).code());
        assertEquals("INVALID_PROVIDER_REQUEST_ID", failure(() -> new Settlement(reservation, " ", null,
                ReservationStatus.UNKNOWN, key, null, null)).code());
    }

    @Test
    @DisplayName("Only a held reservation may settle, and terminal rows never move again")
    void statusMachine() {
        assertTrue(ReservationStatus.RESERVED.holdsBudget());
        assertTrue(ReservationStatus.UNKNOWN.holdsBudget(), "an unresolved cost keeps its reservation");
        assertFalse(ReservationStatus.SETTLED.holdsBudget());
        assertFalse(ReservationStatus.RELEASED.holdsBudget());
        for (ReservationStatus next : new ReservationStatus[]{ReservationStatus.SETTLED,
                ReservationStatus.RELEASED, ReservationStatus.UNKNOWN})
            assertDoesNotThrow(() -> ReservationStatus.RESERVED.allowTransitionTo(next));
        assertDoesNotThrow(() -> ReservationStatus.UNKNOWN.allowTransitionTo(ReservationStatus.SETTLED));
        assertDoesNotThrow(() -> ReservationStatus.UNKNOWN.allowTransitionTo(ReservationStatus.RELEASED));
        assertEquals("SETTLEMENT_CONFLICT", failure(() -> ReservationStatus.UNKNOWN
                .allowTransitionTo(ReservationStatus.UNKNOWN)).code());
        assertEquals(409, failure(() -> ReservationStatus.SETTLED.allowTransitionTo(ReservationStatus.RELEASED)).status());
        assertEquals("SETTLEMENT_CONFLICT", failure(() -> ReservationStatus.RELEASED
                .allowTransitionTo(ReservationStatus.SETTLED)).code());
        assertEquals("SETTLEMENT_CONFLICT", failure(() -> ReservationStatus.RESERVED
                .allowTransitionTo(ReservationStatus.RESERVED)).code());
        assertEquals(ReservationStatus.SETTLED, ReservationStatus.of("SETTLED"));
        assertEquals("INVALID_STATUS", failure(() -> ReservationStatus.of("HELD")).code());
        assertEquals("INVALID_STATUS", failure(() -> ReservationStatus.of(null)).code());
        assertThrows(IllegalArgumentException.class, () -> CostType.valueOf("FORECAST"));
        assertEquals(2, CostType.values().length, "ESTIMATED and ACTUAL are the only cost types");
        assertThrows(IllegalArgumentException.class, () -> Capability.valueOf("OTHER"));
        assertEquals(4, Capability.values().length, "the frozen AIRequest capability list has no OTHER member");
    }

    @Test
    @DisplayName("The ceilings that fall back to a number are the ones the SRS documents")
    void budgetPolicyCeilings() {
        // The eight values below are the SRS-documented limits (docs/AI-Editorial-Agent-SRS-v1.0.md lines 1099,
        // 1103 and 1143). verify.py re-reads those lines and rejects any drift, so this is a transcription of the
        // requirement, not a fixture the code is free to invent. OQ-09 (line 1281) keeps them 示例值 pending
        // Owner approval and real API pricing tests.
        BudgetPolicy policy = BudgetPolicyConfig.from(statedBeyondSrs());
        assertEquals("20.000000", policy.dailyLimit().text());
        assertEquals(30, policy.cap(BudgetPolicy.Counter.SEARCH_QUERY));
        assertEquals(40_000, policy.cap(BudgetPolicy.Counter.MODEL_OUTPUT_TOKENS));
        assertEquals(3, policy.cap(BudgetPolicy.Counter.CLAIM_QUERY));
        assertEquals(1, policy.cap(BudgetPolicy.Counter.AUTO_EDIT_LOOP));
        assertEquals(2, policy.cap(BudgetPolicy.Counter.IMAGE_GENERATION_SLOT));
        assertEquals(4, policy.cap(BudgetPolicy.Counter.IMAGE_GENERATION_ARTICLE));
        assertEquals(80, policy.alertPercent());
        // A counter with no configured limit is a refusal, never an implicit "unlimited".
        BudgetPolicy bare = new BudgetPolicy(Money.of("20.000000"), Map.of(), Map.of(), 80, 30,
                BudgetPolicy.UnconfiguredQuota.REFUSE);
        assertFalse(bare.hasCap(BudgetPolicy.Counter.CALLS));
        assertEquals("QUOTA_NOT_CONFIGURED", failure(() -> bare.cap(BudgetPolicy.Counter.SEARCH_QUERY)).code());
        assertEquals(503, failure(() -> bare.cap(BudgetPolicy.Counter.SEARCH_QUERY)).status());
        // Provider quota is two-level and BOTH levels bind (round-3 ruling F-03): the model entry caps that
        // model's window, the provider entry caps the provider summed across its models. The map answers each
        // level on its own — an entry is never "resolved away" by a wider one; the service measures both windows
        // and the stricter answer wins.
        BudgetPolicy scoped = new BudgetPolicy(Money.of("20.000000"), Map.of(), Map.of(
                "mock", new BudgetPolicy.ProviderQuota(2, 40),
                "mock|mock-model", new BudgetPolicy.ProviderQuota(5, 9)), 80, 30,
                BudgetPolicy.UnconfiguredQuota.UNLIMITED);
        assertEquals(5, scoped.modelQuota("mock", "mock-model").orElseThrow().maxConcurrent());
        assertEquals(2, scoped.providerWideQuota("mock").orElseThrow().maxConcurrent(),
                "the provider entry keeps binding even while the model entry exists");
        assertTrue(scoped.modelQuota("mock", "other").isEmpty(), "sibling models have no model-level entry");
        assertTrue(scoped.providerWideQuota("other").isEmpty(), "an unlisted provider has no entry at all");
        assertEquals(BudgetPolicy.UnconfiguredQuota.UNLIMITED, scoped.unconfigured());
        // Finding F2-01: a scope spelled any other way is unreachable, so the type refuses it instead of storing
        // a ceiling that silently never applies. "mock.mock-model" is exactly what the config builder used to do.
        assertEquals("INVALID_PROVIDER_QUOTA_KEY", failure(() -> new BudgetPolicy(Money.of("20.000000"), Map.of(),
                Map.of("mock.mock-model", new BudgetPolicy.ProviderQuota(1, 1)), 80, 30,
                BudgetPolicy.UnconfiguredQuota.REFUSE)).code());
        // The single spelling both the builder and the lookup use, asserted as data so a second form cannot be
        // introduced quietly: provider-wide is the provider, model-level is provider|model.
        assertEquals("mock|mock-model", BudgetPolicy.scope("mock", "mock-model"));
        assertEquals("mock", BudgetPolicy.scope("mock", null));
        assertEquals("INVALID_BUDGET_POLICY", failure(() -> new BudgetPolicy(Money.of("20.000000"), Map.of(),
                Map.of(), 80, 30, null)).code());
        // The alert line is the configured percent of the ceiling, on exact decimals.
        assertTrue(policy.reachedAlert(Money.of("16.000000"), Money.of("20.000000")));
        assertFalse(policy.reachedAlert(Money.of("15.999999"), Money.of("20.000000")));
        assertTrue(new BudgetPolicy(Money.of("20.000000"), Map.of(), Map.of(), 99, 30,
                BudgetPolicy.UnconfiguredQuota.UNLIMITED)
                .reachedAlert(Money.of("19.999999"), Money.of("20.000000")));
        assertTrue(policy.reachedAlert(Money.ZERO, Money.ZERO), "a zero ceiling is already exhausted");
    }

    /**
     * Two ceilings appear in no SRS line: the per-article call cap and the reconciliation window. They have no
     * fallback, so leaving them unset refuses the build on the configuration path — which is also the only
     * production route to 503 QUOTA_NOT_CONFIGURED, and why that branch is reachable rather than decorative.
     */
    @Test
    @DisplayName("A ceiling the SRS does not state has no default and refuses the build")
    void undocumentedCeilingsHaveNoDefault() {
        PublicFailure nothing = failure(() -> BudgetPolicyConfig.from(new MockEnvironment()));
        assertEquals(503, nothing.status());
        assertEquals("QUOTA_NOT_CONFIGURED", nothing.code());
        // Stating one of the two still refuses: a call cap does not make the reconciliation window configured.
        assertEquals("QUOTA_NOT_CONFIGURED", failure(() -> BudgetPolicyConfig.from(new MockEnvironment()
                .withProperty("editorial.cost.max-calls-per-article", "64"))).code());
        BudgetPolicy stated = BudgetPolicyConfig.from(statedBeyondSrs());
        assertEquals(64, stated.cap(BudgetPolicy.Counter.CALLS));
        assertEquals(30, stated.staleReconciliationMinutes());
        // A stated but unusable ceiling is the other refusal, not a silent default.
        assertEquals("INVALID_BUDGET_POLICY", failure(() -> BudgetPolicyConfig.from(new MockEnvironment()
                .withProperty("editorial.cost.max-calls-per-article", "-1")
                .withProperty("editorial.cost.reconciliation-stale-minutes", "30"))).code());
    }

    /** An environment stating the ceilings and choices the SRS leaves open, so the defaults can be read. */
    private static MockEnvironment statedBeyondSrs() {
        return new MockEnvironment()
                .withProperty("editorial.cost.max-calls-per-article", "64")
                .withProperty("editorial.cost.reconciliation-stale-minutes", "30")
                .withProperty("editorial.cost.provider-quota.unconfigured", "refuse");
    }

    /**
     * Finding F2-01. The config builder used to key the scope map with the dotted property path
     * ({@code mock.mock-model}) while the lookup asked for {@code mock|mock-model}: a model-level quota could be
     * configured perfectly and still never apply, because the entry sat where nothing ever looked. So the whole
     * trip — property path, scope string, lookup, service — is asserted here from real configuration.
     */
    @Test
    @DisplayName("A model-level provider quota survives the trip through configuration")
    void modelLevelQuotaReachesTheLookupThatReadsIt() {
        BudgetPolicy policy = BudgetPolicyConfig.from(statedBeyondSrs()
                .withProperty("editorial.cost.provider-quota.mock.max-concurrent", "3")
                .withProperty("editorial.cost.provider-quota.mock.calls-per-day", "17")
                .withProperty("editorial.cost.provider-quota.mock.mock-model.max-concurrent", "1")
                .withProperty("editorial.cost.provider-quota.mock.mock-model.calls-per-day", "2"));
        assertEquals(1, policy.modelQuota("mock", "mock-model").orElseThrow().maxConcurrent());
        assertEquals(2, policy.modelQuota("mock", "mock-model").orElseThrow().callsPerDay());
        assertEquals(3, policy.providerWideQuota("mock").orElseThrow().maxConcurrent());
        assertEquals(17, policy.providerWideQuota("mock").orElseThrow().callsPerDay());
        assertTrue(policy.modelQuota("mock", "other-model").isEmpty(),
                "a sibling model is capped by the provider entry — the model entry answers its own model only");
        assertEquals(java.util.Set.of("mock", "mock|mock-model"), policy.providers().keySet());
        assertTrue(policy.providers().keySet().stream().noneMatch(key -> key.contains(".")),
                "a dotted scope is unreachable by definition: " + policy.providers().keySet());
        assertEquals(BudgetPolicy.UnconfiguredQuota.REFUSE, policy.unconfigured());
        // The switch has to be stated; an absent one would mean unlimited by accident.
        assertEquals("QUOTA_NOT_CONFIGURED", failure(() -> BudgetPolicyConfig.from(new MockEnvironment()
                .withProperty("editorial.cost.max-calls-per-article", "64")
                .withProperty("editorial.cost.reconciliation-stale-minutes", "30"))).code());
        assertEquals("INVALID_BUDGET_POLICY", failure(() -> BudgetPolicyConfig.from(statedBeyondSrs()
                .withProperty("editorial.cost.provider-quota.unconfigured", "sometimes"))).code());
        // Half a scope is a gap, not one open side: both leaves are required once a scope is declared.
        assertEquals("QUOTA_NOT_CONFIGURED", failure(() -> BudgetPolicyConfig.from(statedBeyondSrs()
                .withProperty("editorial.cost.provider-quota.mock.max-concurrent", "1"))).code());
        // And a path with nowhere to be looked up is refused rather than filed where nothing reads it.
        assertEquals("INVALID_PROVIDER_QUOTA_KEY", failure(() -> BudgetPolicyConfig.from(statedBeyondSrs()
                .withProperty("editorial.cost.provider-quota.mock.mock-model.beta.max-concurrent", "1")
                .withProperty("editorial.cost.provider-quota.mock.mock-model.beta.calls-per-day", "1"))).code());
    }

    /** A deployment environment built the way the application builds one: from a YAML document, by Spring. */
    private static MockEnvironment yaml(String document) {
        MockEnvironment env = new MockEnvironment();
        try {
            for (PropertySource<?> source : new YamlPropertySourceLoader().load("t08-quota",
                    new ByteArrayResource(document.getBytes(StandardCharsets.UTF_8)))) {
                env.getPropertySources().addLast(source);
            }
        } catch (java.io.IOException unreadable) {
            throw new IllegalStateException("the fixture document could not be read", unreadable);
        }
        return env;
    }

    /**
     * Finding F2-01, from the shape an operator actually writes, and finding F-02's evidence rule: the loader
     * runs inside this case body, on the document this case body carries, and the policy the assertions read
     * is the one {@code BudgetPolicyConfig.from(env)} returned from that environment — "the file mentions a
     * loader somewhere" is not binding evidence, because a hand-built flat-key environment can decorate a
     * document nobody loaded. The flat property names above could have been right while the nested YAML
     * document bound to something else entirely, and the test would still have been green: the whole point of
     * the defect was two spellings that never met. And the wrong shapes fail out loud instead of landing where
     * nothing reads them.
     */
    @Test
    @DisplayName("Nested YAML quota keys bind the scopes the quota lookup reads")
    void quotaWrittenAsNestedYamlBindsTheScopeTheLookupReads() throws java.io.IOException {
        String document = """
                editorial:
                  cost:
                    max-calls-per-article: 64
                    reconciliation-stale-minutes: 30
                    provider-quota:
                      unconfigured: refuse
                      mock:
                        max-concurrent: 3
                        calls-per-day: 17
                        mock-model:
                          max-concurrent: 1
                          calls-per-day: 2
                """;
        MockEnvironment env = new MockEnvironment();
        for (PropertySource<?> source : new YamlPropertySourceLoader().load("t08-quota",
                new ByteArrayResource(document.getBytes(StandardCharsets.UTF_8)))) {
            env.getPropertySources().addLast(source);
        }
        BudgetPolicy policy = BudgetPolicyConfig.from(env);
        assertEquals(java.util.Set.of("mock", "mock|mock-model"), policy.providers().keySet(),
                "the document nests a model under its provider; the map has to hold both scopes, not a path");
        assertEquals(1, policy.modelQuota("mock", "mock-model").orElseThrow().maxConcurrent());
        assertEquals(2, policy.modelQuota("mock", "mock-model").orElseThrow().callsPerDay());
        assertEquals(3, policy.providerWideQuota("mock").orElseThrow().maxConcurrent(),
                "both levels the document declares are enforced; neither shadows the other");
        assertEquals(BudgetPolicy.UnconfiguredQuota.REFUSE, policy.unconfigured());
        assertEquals(64L, policy.cap(BudgetPolicy.Counter.CALLS), "the stated non-default came from the document");

        // A camelCase leaf is a typo, not a key Spring relaxed-binds into max-concurrent for us to enumerate.
        assertEquals("INVALID_PROVIDER_QUOTA_KEY", failure(() -> BudgetPolicyConfig.from(yaml("""
                editorial:
                  cost:
                    max-calls-per-article: 64
                    reconciliation-stale-minutes: 30
                    provider-quota:
                      unconfigured: refuse
                      mock:
                        maxConcurrency: 3
                        calls-per-day: 17
                """))).code());
        // One nesting level too deep is the unreachable-key class of bug: refused at boot.
        assertEquals("INVALID_PROVIDER_QUOTA_KEY", failure(() -> BudgetPolicyConfig.from(yaml("""
                editorial:
                  cost:
                    max-calls-per-article: 64
                    reconciliation-stale-minutes: 30
                    provider-quota:
                      unconfigured: refuse
                      mock:
                        mock-model:
                          beta:
                            max-concurrent: 1
                            calls-per-day: 1
                """))).code());
        // A model id containing a dot flattens into an extra segment, so it cannot name a scope: loud failure.
        assertEquals("INVALID_PROVIDER_QUOTA_KEY", failure(() -> BudgetPolicyConfig.from(yaml("""
                editorial:
                  cost:
                    max-calls-per-article: 64
                    reconciliation-stale-minutes: 30
                    provider-quota:
                      unconfigured: refuse
                      mock:
                        gpt-5.1:
                          max-concurrent: 1
                          calls-per-day: 1
                """))).code());
        // Half a declared scope is a gap in the document, not one side left open.
        assertEquals("QUOTA_NOT_CONFIGURED", failure(() -> BudgetPolicyConfig.from(yaml("""
                editorial:
                  cost:
                    max-calls-per-article: 64
                    reconciliation-stale-minutes: 30
                    provider-quota:
                      unconfigured: refuse
                      mock:
                        max-concurrent: 3
                """))).code());
        // The reserved switch shares the namespace with provider names, so a provider called unconfigured has to
        // fail the boot rather than be quietly read as the switch or quietly dropped.
        assertEquals("INVALID_PROVIDER_QUOTA_KEY", failure(() -> BudgetPolicyConfig.from(yaml("""
                editorial:
                  cost:
                    max-calls-per-article: 64
                    reconciliation-stale-minutes: 30
                    provider-quota:
                      unconfigured:
                        max-concurrent: 2
                        calls-per-day: 5
                """))).code());
        // And a document that states no switch at all is refused: absence is not a policy.
        assertEquals("QUOTA_NOT_CONFIGURED", failure(() -> BudgetPolicyConfig.from(yaml("""
                editorial:
                  cost:
                    max-calls-per-article: 64
                    reconciliation-stale-minutes: 30
                    provider-quota:
                      mock:
                        max-concurrent: 3
                        calls-per-day: 17
                """))).code());
    }

    @Test
    @DisplayName("A configured ceiling is honoured and a bad one is refused at boot")
    void budgetPolicyOverrides() {        MockEnvironment env = statedBeyondSrs()
                .withProperty("editorial.cost.daily-budget", "12.500000")
                .withProperty("editorial.cost.search-queries-per-article", "5")
                .withProperty("editorial.cost.alert-percent", "70")
                .withProperty("editorial.cost.reconciliation-stale-minutes", "5")
                .withProperty("editorial.cost.provider-quota.mock.max-concurrent", "3")
                .withProperty("editorial.cost.provider-quota.mock.calls-per-day", "17");
        BudgetPolicy policy = BudgetPolicyConfig.from(env);
        assertEquals("12.500000", policy.dailyLimit().text());
        assertEquals(5, policy.cap(BudgetPolicy.Counter.SEARCH_QUERY));
        assertEquals(70, policy.alertPercent());
        assertEquals(5, policy.staleReconciliationMinutes());
        assertEquals(3, policy.providerWideQuota("mock").orElseThrow().maxConcurrent());
        assertEquals(17, policy.providerWideQuota("mock").orElseThrow().callsPerDay());
        assertEquals("INVALID_AMOUNT", failure(() -> BudgetPolicyConfig.from(statedBeyondSrs()
                .withProperty("editorial.cost.daily-budget", "12.5"))).code());
        assertEquals("INVALID_BUDGET_POLICY", failure(() -> BudgetPolicyConfig.from(statedBeyondSrs()
                .withProperty("editorial.cost.search-queries-per-article", "-1"))).code());
        assertEquals("INVALID_BUDGET_POLICY", failure(() -> BudgetPolicyConfig.from(statedBeyondSrs()
                .withProperty("editorial.cost.alert-percent", "0"))).code());
        assertEquals("INVALID_BUDGET_POLICY", failure(() -> BudgetPolicyConfig.from(statedBeyondSrs()
                .withProperty("editorial.cost.provider-quota.mock.calls-per-day", "-1"))).code());
        assertEquals("INVALID_PROVIDER_QUOTA_KEY", failure(() -> BudgetPolicyConfig.from(statedBeyondSrs()
                .withProperty("editorial.cost.provider-quota.max-concurrent", "1"))).code());
    }

    /** A property source shaped the way the OS environment reaches Spring: raw UPPER_SNAKE keys. */
    private static MockEnvironment environmentShaped(java.util.Map<String, Object> os) {
        MockEnvironment env = new MockEnvironment();
        env.getPropertySources().addFirst(new SystemEnvironmentPropertySource("systemEnv", os));
        return env;
    }

    /**
     * Round-3 finding F-01: {@code SystemEnvironmentPropertySource} answers the canonical
     * {@code editorial.cost.provider-quota.…} names for its {@code EDITORIAL_COST_…} keys, but the quota
     * enumeration matched literal dotted names only — so quotas configured through the environment booted
     * green with every provider silently unlimited ("配了不生效", new channel). The enumeration now walks the
     * subtree through Spring's own relaxed binding, and a shape the environment channel cannot read with ONE
     * answer (its {@code _} stands for both {@code .} and {@code -}) is refused at load instead of guessed.
     */
    @Test
    @DisplayName("A quota supplied through environment-style names binds instead of vanishing")
    void quotaSuppliedThroughEnvironmentStyleNamesBinds() {
        java.util.Map<String, Object> os = new java.util.LinkedHashMap<>();
        os.put("EDITORIAL_COST_MAX_CALLS_PER_ARTICLE", "64");
        os.put("EDITORIAL_COST_RECONCILIATION_STALE_MINUTES", "30");
        os.put("EDITORIAL_COST_PROVIDER_QUOTA_UNCONFIGURED", "unlimited");
        os.put("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MAX_CONCURRENT", "2");
        os.put("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_CALLS_PER_DAY", "30");
        BudgetPolicy policy = BudgetPolicyConfig.from(environmentShaped(os));
        assertEquals(2, policy.providerWideQuota("mock").orElseThrow().maxConcurrent(),
                "the env-shaped key configured the provider-wide ceiling instead of silently vanishing");
        assertEquals(30, policy.providerWideQuota("mock").orElseThrow().callsPerDay());
        assertEquals(BudgetPolicy.UnconfiguredQuota.UNLIMITED, policy.unconfigured());
        // Half a scope stated through the environment is still half a scope: refused, never read as unlimited.
        java.util.Map<String, Object> half = new java.util.LinkedHashMap<>(os);
        half.remove("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_CALLS_PER_DAY");
        assertEquals("QUOTA_NOT_CONFIGURED", failure(() -> BudgetPolicyConfig.from(environmentShaped(half))).code());
        // MOCK_MODEL_* is provider "mock" model "model" OR provider "mock-model": two readings, zero trust.
        java.util.Map<String, Object> ambiguous = new java.util.LinkedHashMap<>(os);
        ambiguous.put("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MODEL_MAX_CONCURRENT", "1");
        assertEquals("INVALID_PROVIDER_QUOTA_KEY",
                failure(() -> BudgetPolicyConfig.from(environmentShaped(ambiguous))).code());
    }

    /**
     * Round-3 finding F-08: every leaf value is normalized into the structured 503 — "three" used to escape as
     * a ConversionFailedException stack (loud to a terminal, not a PUBLIC_FAILURE code) — and the two zeros
     * mean different things: {@code max-concurrent: 0} is a permanent wedge (refused as misconfiguration) and
     * {@code calls-per-day: 0} is a stated closed day (accepted here;
     * {@code T08PostgresTest#zeroCallsPerDayClosesTheDayButNotTheBoot} pins what it refuses).
     */
    @Test
    @DisplayName("Quota leaves refuse the boot structurally; only a wedge is misconfiguration")
    void quotaLeavesAreNormalisedAtAssembly() {
        assertEquals("INVALID_BUDGET_POLICY", failure(() -> BudgetPolicyConfig.from(statedBeyondSrs()
                .withProperty("editorial.cost.provider-quota.mock.max-concurrent", "three")
                .withProperty("editorial.cost.provider-quota.mock.calls-per-day", "5"))).code());
        assertEquals("INVALID_BUDGET_POLICY", failure(() -> BudgetPolicyConfig.from(statedBeyondSrs()
                .withProperty("editorial.cost.provider-quota.mock.max-concurrent", "2")
                .withProperty("editorial.cost.provider-quota.mock.calls-per-day", "-1"))).code());
        assertEquals("INVALID_BUDGET_POLICY", failure(() -> BudgetPolicyConfig.from(statedBeyondSrs()
                .withProperty("editorial.cost.provider-quota.mock.max-concurrent", "0")
                .withProperty("editorial.cost.provider-quota.mock.calls-per-day", "5"))).code());
        assertEquals("INVALID_BUDGET_POLICY", failure(() -> new BudgetPolicy.ProviderQuota(0, 5)).code());
        BudgetPolicy closedDay = BudgetPolicyConfig.from(statedBeyondSrs()
                .withProperty("editorial.cost.provider-quota.mock.max-concurrent", "2")
                .withProperty("editorial.cost.provider-quota.mock.calls-per-day", "0"));
        assertEquals(0, closedDay.providerWideQuota("mock").orElseThrow().callsPerDay(),
                "a closed day is a stated choice, not a typo to refuse");
    }

    /**
     * Round-3 ruling F-03 as data: the two levels answer their own entries and neither erases the other —
     * the service measures both windows and the stricter binds. Model keys match by equality only (variant
     * probe V4: a prefix match would silently widen {@code mock-model} onto every {@code mock-model-*}), and
     * the ruled F-04 boundary is pinned here too: a dotted model id has no model-level entry while the
     * provider-wide entry still caps it.
     */
    @Test
    @DisplayName("Both quota levels answer their own entry, exact scope equality only")
    void bothQuotaLevelsAnswerTheirOwnEntries() {
        BudgetPolicy layered = new BudgetPolicy(Money.of("20.000000"), Map.of(), Map.of(
                "mock", new BudgetPolicy.ProviderQuota(2, 40),
                "mock|mock-model", new BudgetPolicy.ProviderQuota(5, 9)), 80, 30,
                BudgetPolicy.UnconfiguredQuota.UNLIMITED);
        assertEquals(5, layered.modelQuota("mock", "mock-model").orElseThrow().maxConcurrent());
        assertEquals(9, layered.modelQuota("mock", "mock-model").orElseThrow().callsPerDay());
        assertEquals(2, layered.providerWideQuota("mock").orElseThrow().maxConcurrent(),
                "the looser model entry erases the provider entry from nobody's window");
        assertTrue(layered.modelQuota("mock", "mock-model-v2").isEmpty(),
                "a prefix match would answer mock-model for a model that never declared it");
        assertTrue(layered.modelQuota("mock", "gpt-4.1").isEmpty(),
                "a dotted model id has no model-level key (ruled boundary), so nothing is guessed here");
        assertEquals(40, layered.providerWideQuota("mock").orElseThrow().callsPerDay(),
                "and the dotted model's rows are still capped by the provider entry");
    }

    /**
     * Round-3 finding F-05: the scope key joins provider and model with {@code |}, so an id containing the
     * separator makes {@code p|q} (one provider) and {@code p}+{@code q} (a model override) the same map key,
     * silently overwriting one another — the reviewer's mixed {@code {p|q, p.q}} document demonstrated it.
     * Ids are restricted to {@code [A-Za-z0-9._-]}; violations fail the same load-time refusal, and a stored
     * key that would parse two ways is refused by the record too.
     */
    @Test
    @DisplayName("An id containing the scope separator is refused at load, not collided")
    void separatorBearingIdsAreRefusedNotCollided() {
        assertEquals("INVALID_PROVIDER_QUOTA_KEY", failure(() -> BudgetPolicy.scope("p|q", null)).code());
        assertEquals("INVALID_PROVIDER_QUOTA_KEY", failure(() -> BudgetPolicy.scope("p", "q|r")).code());
        assertEquals("INVALID_PROVIDER_QUOTA_KEY", failure(() -> BudgetPolicy.scope("p", "q r")).code());
        assertEquals("INVALID_PROVIDER_QUOTA_KEY", failure(() -> BudgetPolicyConfig.from(statedBeyondSrs()
                .withProperty("editorial.cost.provider-quota.p|q.max-concurrent", "9")
                .withProperty("editorial.cost.provider-quota.p|q.calls-per-day", "9")
                .withProperty("editorial.cost.provider-quota.p.q.max-concurrent", "1")
                .withProperty("editorial.cost.provider-quota.p.q.calls-per-day", "1"))).code());
        assertEquals("INVALID_PROVIDER_QUOTA_KEY", failure(() -> new BudgetPolicy(Money.of("20.000000"), Map.of(),
                Map.of("p||q", new BudgetPolicy.ProviderQuota(1, 1)), 80, 30,
                BudgetPolicy.UnconfiguredQuota.REFUSE)).code());
    }

    @Test
    @DisplayName("An unbound execution scope refuses rather than inventing an execution")
    void executionScopeIsFailClosed() {
        // rc.3 requires an execution id, agent_execution/tool_execution arrive with T09/T10, and the only honest
        // answer until the composition root binds a resolver is a refusal that writes nothing.
        CostPorts.Executions unbound = CostPorts.unavailableExecutions();
        PublicFailure failure = failure(() -> unbound.resolve(
                com.example.editorial.shared.ActorContext.forWorker(UUID.randomUUID(), UUID.randomUUID(),
                        UUID.randomUUID()), UUID.randomUUID(), UUID.randomUUID()));
        assertEquals(503, failure.status());
        assertEquals("EXECUTION_SCOPE_NOT_READY", failure.code());
    }

    @Test
    @DisplayName("Alert percentages are whole numbers clamped into the reported range")
    void alertPercent() {
        assertEquals(80, BudgetAlert.percentOf(Money.of("4.000000"), Money.of("5.000000")));
        assertEquals(100, BudgetAlert.percentOf(Money.of("9.000000"), Money.of("5.000000")), "overrun clamps to 100");
        assertEquals(0, BudgetAlert.percentOf(Money.ZERO, Money.of("5.000000")));
        assertEquals(0, BudgetAlert.percentOf(Money.of("0.029999"), Money.of("5.000000")), "rounds down");
        assertEquals(100, BudgetAlert.percentOf(Money.of("0.000001"), Money.ZERO));
        assertEquals(100, BudgetAlert.percentOf(Money.ZERO, Money.ZERO));
        assertEquals("BUDGET_WARNING", BudgetAlert.Code.BUDGET_WARNING.name());
        BudgetAlert alert = new BudgetAlert(BudgetAlert.Code.BUDGET_WARNING, "ARTICLE", "scope", null, null, null,
                Money.of("5.000000"), 80, "mock", "mock-model", null, null);
        assertEquals(Money.ZERO, alert.spent());
        assertEquals(Money.ZERO, alert.reserved());
        assertEquals(Money.ZERO, alert.unknown());
    }

    @Test
    @DisplayName("An amount is written as canonical text, never as a float")
    void canonicalAmountIsText() {
        JsonNode node = JSON.createObjectNode().put("amount", Money.of("0.036900").text());
        assertEquals("{\"amount\":\"0.036900\"}",
                new String(CanonicalRequest.canonical(node), StandardCharsets.UTF_8));
        assertEquals(new BigDecimal("0.036900"), Money.of("0.036900").decimal());
        assertEquals(64, CanonicalRequest.digest(CanonicalRequest.canonical(node)).length());
    }

    /** The environment variables the quota cases share: two stated ceilings and the required switch. */
    private static java.util.Map<String, Object> environmentBase() {
        java.util.Map<String, Object> os = new java.util.LinkedHashMap<>();
        os.put("EDITORIAL_COST_MAX_CALLS_PER_ARTICLE", "64");
        os.put("EDITORIAL_COST_RECONCILIATION_STALE_MINUTES", "30");
        os.put("EDITORIAL_COST_PROVIDER_QUOTA_UNCONFIGURED", "unlimited");
        return os;
    }

    /**
     * Round-4 finding F-R4-02, measured as a silent path: {@code EDITORIAL_COST_PROVIDER_QUOTAS_…} — the quota
     * prefix with one letter added — is not an unrelated variable, it is this subtree misspelled, and the channel
     * used to return quietly on it. The deployment booted green with {@code providers={}}: every provider
     * uncapped, no warning in any log, exit code 0. A name in our own namespace that says "quota" and is not on
     * the exact prefix therefore stops the boot; a name in the namespace that does not say quota is a different
     * ceiling and stays untouched, which the last assertion pins from the other side.
     */
    @Test
    @DisplayName("An environment quota prefix misspelled by one letter refuses the boot")
    void environmentQuotaPrefixTypoRefusesTheBoot() {
        java.util.Map<String, Object> typo = environmentBase();
        typo.put("EDITORIAL_COST_PROVIDER_QUOTAS_MOCK_MAX_CONCURRENT", "2");
        typo.put("EDITORIAL_COST_PROVIDER_QUOTAS_MOCK_CALLS_PER_DAY", "30");
        assertEquals("INVALID_PROVIDER_QUOTA_KEY",
                failure(() -> BudgetPolicyConfig.from(environmentShaped(typo))).code(),
                "PROVIDER_QUOTAS_ is PROVIDER_QUOTA_ misspelled: it has to end the boot, not uncapp providers");
        java.util.Map<String, Object> adjacent = environmentBase();
        adjacent.put("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MAX_CONCURRENCY", "2");
        assertEquals("INVALID_PROVIDER_QUOTA_KEY",
                failure(() -> BudgetPolicyConfig.from(environmentShaped(adjacent))).code(),
                "on the exact prefix with a leaf nobody knows is the same class of mistake (finding F-R4-10)");
        java.util.Map<String, Object> unrelated = environmentBase();
        unrelated.put("EDITORIAL_COST_PROVIDER_CLUSTER_SHARDS", "4");
        assertEquals(64, BudgetPolicyConfig.from(environmentShaped(unrelated)).cap(BudgetPolicy.Counter.CALLS),
                "a name in the namespace without the word quota is not about provider ceilings and stays readable");
    }

    /**
     * Round-4 finding F-R4-03, pinned as real behavior rather than "fixed": the environment name reaches this
     * channel upper-cased — that is the environment's own convention, not a typo — and the provider segment is
     * stored lower-cased, which is exactly what made the delivered F-01 case bind. So the channel addresses
     * all-lowercase provider ids only, and a provider whose real id carries capitals is unreachable through it:
     * {@code providerWideQuota("MOCK")} is empty even though the operator believes they capped it. Refusing every
     * upper-cased segment would refuse the convention itself, so the boundary is written into the class comment
     * and pinned here, file channel included, to show which side of the two channels keeps capitals.
     */
    @Test
    @DisplayName("The environment channel addresses lowercase provider ids; capitals are refused, never guessed")
    void environmentChannelAddressesProvidersInLowerCaseOnly() {
        java.util.Map<String, Object> os = environmentBase();
        os.put("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MAX_CONCURRENT", "2");
        os.put("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_CALLS_PER_DAY", "30");
        BudgetPolicy bound = BudgetPolicyConfig.from(environmentShaped(os));
        assertEquals(2, bound.providerWideQuota("mock").orElseThrow().maxConcurrent(),
                "the lower-cased spelling is the one that binds — that is round-3 finding F-01 working");
        assertTrue(bound.providerWideQuota("MOCK").isEmpty(),
                "and the same name cannot address a provider whose id really carries capitals (F-R4-03)");
        assertEquals(java.util.Set.of("mock"), bound.providers().keySet(),
                "stored lower-cased, so an uppercase id is not merely invisible: the key it holds is mock");
        // The other half, measured rather than assumed: writing the capital down literally in the canonical
        // channel does not survive either. Spring's binder refuses a name it cannot spell, and the first draft
        // of this case asserted the opposite — that {@code provider-quota.MOCK.…} kept its capitals — which the
        // real PostgreSQL run disproved with InvalidConfigurationPropertyNameException escaping the assembly. So
        // the boundary is stated once, in one direction: a provider id carrying capitals has no channel that
        // addresses it, and the miss is a structured refusal (503 INVALID_BUDGET_POLICY), not a raw stack and
        // not a silently lower-cased key.
        PublicFailure capitals = assertThrows(PublicFailure.class, () -> BudgetPolicyConfig.from(statedBeyondSrs()
                .withProperty("editorial.cost.provider-quota.MOCK.max-concurrent", "2")
                .withProperty("editorial.cost.provider-quota.MOCK.calls-per-day", "30")));
        assertEquals(503, capitals.status());
        assertEquals("INVALID_BUDGET_POLICY", capitals.code(),
                "an unspellable canonical name is refused like any other unreadable leaf, and it is NOT folded "
                        + "to lowercase on this channel: no cap silently lands on mock instead of MOCK");
        java.util.Map<String, Object> strict = new java.util.LinkedHashMap<>(os);
        strict.put("EDITORIAL_COST_PROVIDER_QUOTA_UNCONFIGURED", "refuse");
        assertEquals(BudgetPolicy.UnconfiguredQuota.REFUSE,
                BudgetPolicyConfig.from(environmentShaped(strict)).unconfigured(),
                "under refuse the miss above surfaces as 503 PROVIDER_QUOTA_NOT_CONFIGURED at the call instead of "
                        + "an uncapped call: the loud half of this boundary is T08PostgresTest's case");
    }

    /**
     * Round-4 finding F-R4-04: {@link BudgetPolicy.ProviderQuota} stores {@code calls-per-day} as a {@code long}
     * while the configuration surface read it through the same {@code Integer} binding as {@code max-concurrent},
     * so a legal {@code 99999999999} was refused with 503 — a surface narrower than the field it fills. The day
     * leaf binds a {@code Long} now, on both channels; the other side of that boundary is stated in the same
     * breath, because {@code max-concurrent} <em>is</em> an {@code int} and a value past it stays a refusal rather
     * than becoming a wrapped ceiling.
     */
    @Test
    @DisplayName("The daily call leaf carries the long the record stores")
    void dayCountLeafCarriesTheLongTheRecordStores() {
        BudgetPolicy file = BudgetPolicyConfig.from(statedBeyondSrs()
                .withProperty("editorial.cost.provider-quota.mock.max-concurrent", "2")
                .withProperty("editorial.cost.provider-quota.mock.calls-per-day", "99999999999"));
        assertEquals(99999999999L, file.providerWideQuota("mock").orElseThrow().callsPerDay(),
                "the record holds a long, so the configuration surface may not stop at Integer's ceiling");
        java.util.Map<String, Object> os = environmentBase();
        os.put("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MAX_CONCURRENT", "2");
        os.put("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_CALLS_PER_DAY", "99999999999");
        assertEquals(99999999999L,
                BudgetPolicyConfig.from(environmentShaped(os)).providerWideQuota("mock").orElseThrow().callsPerDay(),
                "and the environment channel reads the same field with the same width");
        assertEquals("INVALID_BUDGET_POLICY", failure(() -> BudgetPolicyConfig.from(statedBeyondSrs()
                .withProperty("editorial.cost.provider-quota.mock.max-concurrent", "2147483648")
                .withProperty("editorial.cost.provider-quota.mock.calls-per-day", "9"))).code(),
                "the asymmetry is deliberate: an int field does not accept a wider number, and says so");
        assertEquals("INVALID_BUDGET_POLICY", failure(() -> BudgetPolicyConfig.from(statedBeyondSrs()
                .withProperty("editorial.cost.provider-quota.mock.max-concurrent", "2")
                .withProperty("editorial.cost.provider-quota.mock.calls-per-day", "-1"))).code());
    }

    /**
     * Round-4 finding F-R4-05: {@code SystemEnvironmentPropertySource} answers a canonical dotted name exactly
     * like any other source does — {@code getProperty()} saw the value while the enumeration only walked the
     * UPPER_SNAKE spelling of that source, so one source was half visible and the provider map stayed empty with
     * no complaint. A canonical name found in an environment-shaped source now goes to the canonical reader, and
     * the two spellings inside one source land on one entry instead of two readings of one leaf.
     */
    @Test
    @DisplayName("A canonical quota name inside an environment-shaped source binds like the flattened spelling")
    void canonicalQuotaNamesInsideAnEnvironmentShapedSourceAreBound() {
        java.util.Map<String, Object> os = environmentBase();
        os.put("editorial.cost.provider-quota.mock.max-concurrent", "3");
        os.put("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_CALLS_PER_DAY", "41");
        BudgetPolicy policy = BudgetPolicyConfig.from(environmentShaped(os));
        assertEquals(3, policy.providerWideQuota("mock").orElseThrow().maxConcurrent(),
                "getProperty() saw this name; the enumeration used to walk past it (finding F-R4-05)");
        assertEquals(41, policy.providerWideQuota("mock").orElseThrow().callsPerDay(),
                "the flattened spelling of the other leaf still binds, so one source feeds one entry");
        java.util.Map<String, Object> both = new java.util.LinkedHashMap<>(os);
        both.put("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MAX_CONCURRENT", "7");
        assertEquals(3, BudgetPolicyConfig.from(environmentShaped(both)).providerWideQuota("mock").orElseThrow()
                .maxConcurrent(), "two spellings of one leaf resolve to the value the binder resolves, not to "
                        + "whichever enumeration happened to reach the entry first");
        assertEquals(java.util.Set.of("mock"), BudgetPolicyConfig.from(environmentShaped(both)).providers().keySet(),
                "and they land in one provider map, not in two half-populated scopes");
    }

    /**
     * Round-4 finding F-R4-10, the fourth silent path: an unknown leaf under the quota prefix fell through the
     * leaf test into a bare {@code return}, so {@code …_MOCK_AVERAGE_LATENCY} — or a leaf glued wrong — left the
     * boot green with the provider uncapped. Both channels refuse it now, and the mirror mistake (one leaf of a
     * pair missing) is refused for the reason that fits it.
     */
    @Test
    @DisplayName("An unknown quota leaf refuses the boot on both channels, never a quiet skip")
    void everyUnknownQuotaLeafRefusesTheBoot() {
        java.util.Map<String, Object> unknownLeaf = environmentBase();
        unknownLeaf.put("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MAX_CONCURRENT", "2");
        unknownLeaf.put("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_AVERAGE_LATENCY", "250");
        assertEquals("INVALID_PROVIDER_QUOTA_KEY",
                failure(() -> BudgetPolicyConfig.from(environmentShaped(unknownLeaf))).code(),
                "a leaf this subtree does not have is a typo about provider ceilings, not an unrelated variable");
        java.util.Map<String, Object> glued = environmentBase();
        glued.put("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MAXCONCURRENT", "2");
        glued.put("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_CALLS_PER_DAY", "30");
        assertEquals("INVALID_PROVIDER_QUOTA_KEY",
                failure(() -> BudgetPolicyConfig.from(environmentShaped(glued))).code(),
                "and gluing the leaf's hyphen away is the same refusal, not a provider nobody capped");
        java.util.Map<String, Object> oneLeaf = environmentBase();
        oneLeaf.put("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MAX_CONCURRENT", "2");
        assertEquals("QUOTA_NOT_CONFIGURED",
                failure(() -> BudgetPolicyConfig.from(environmentShaped(oneLeaf))).code(),
                "a scope that states only half of itself is the other refusal, with the code that says so");
    }

    /**
     * Round-4 finding F-R4-09: the delivery claimed the advisory locks are taken in one fixed order so two
     * racing admissions cannot hold each other's keys in opposite hands, and nothing watched the claim — deleting
     * the sort in {@code BudgetService.reserveInTransaction} left all 14 static gates and all 57 delivered cases
     * green (the reviewer's B1, and the same measurement here before this case existed). No deadlock is being
     * claimed today and none is claimed by this case: what is pinned is that the sequence is decided in one
     * place, that it is the dictionary order of the key actually locked, and that it does not depend on which
     * windows a given request happens to shape.
     */
    @Test
    @DisplayName("Advisory locks are taken in the dictionary order of the key, whatever order they were built in")
    void advisoryLockOrderIsTheDictionaryOrderOfLockKeys() {
        java.util.List<BudgetService.Ceiling> articleFirst = java.util.List.of(
                window("ARTICLE", "T08|ARTICLE|" + ARTICLE),
                window("DAY", "T08|DAY|" + OWNER + "|2024-05-01"),
                window("PROVIDER", "T08|PROVIDER|" + OWNER + "|mock|2024-05-01"),
                window("PROVIDER-MODEL", "T08|PROVIDER-MODEL|" + OWNER + "|mock|gpt|2024-05-01"),
                window("CLAIM", "T08|CLAIM|" + CLAIM),
                window("SLOT", "T08|SLOT|" + SLOT));
        java.util.List<BudgetService.Ceiling> scrambled = java.util.List.of(
                window("SLOT", "T08|SLOT|" + SLOT),
                window("PROVIDER", "T08|PROVIDER|" + OWNER + "|mock|2024-05-01"),
                window("CLAIM", "T08|CLAIM|" + CLAIM),
                window("PROVIDER-MODEL", "T08|PROVIDER-MODEL|" + OWNER + "|mock|gpt|2024-05-01"),
                window("DAY", "T08|DAY|" + OWNER + "|2024-05-01"),
                window("ARTICLE", "T08|ARTICLE|" + ARTICLE));
        java.util.List<String> forward = keys(BudgetService.inLockOrder(articleFirst));
        assertEquals(forward, keys(BudgetService.inLockOrder(scrambled)),
                "two requests shaping their windows in different orders must reach the same lock sequence");
        assertEquals(forward.stream().sorted().toList(), forward, "and that sequence is the dictionary order of "
                + "the keys the transaction actually names in pg_advisory_xact_lock");
        assertTrue(forward.indexOf("T08|PROVIDER-MODEL|" + OWNER + "|mock|gpt|2024-05-01")
                        < forward.indexOf("T08|PROVIDER|" + OWNER + "|mock|2024-05-01"),
                "the model window precedes the provider window it adds up into — the ordering fact the round-3 "
                        + "review measured, now watched instead of asserted in prose");
        assertEquals(6, forward.size(), "one entry per ceiling, so a window cannot be dropped on the way to the lock");
        java.util.List<BudgetService.Ceiling> withANewWindow = new java.util.ArrayList<>(articleFirst);
        withANewWindow.add(window("SEARCH", "T08|SEARCH|" + OWNER + "|2024-05-01"));
        java.util.List<String> extended = keys(BudgetService.inLockOrder(withANewWindow.reversed()));
        assertEquals(extended.stream().sorted().toList(), extended,
                "a scope added later joins the same order: the invariant is the sort, not the six keys it knows");
    }

    private static final UUID ARTICLE = UUID.fromString("cccccccc-0000-4000-8000-000000000001");
    private static final UUID OWNER = UUID.fromString("aaaaaaaa-0000-4000-8000-000000000001");
    private static final UUID CLAIM = UUID.fromString("dddddddd-0000-4000-8000-000000000001");
    private static final UUID SLOT = UUID.fromString("eeeeeeee-0000-4000-8000-000000000001");

    /** One ceiling carrying only a lock key: enough to exercise the sequence the admission transaction takes. */
    private static BudgetService.Ceiling window(String scope, String lockKey) {
        return new BudgetService.Ceiling(scope, lockKey, lockKey, "l.owner_id=?", java.util.List.of(), null,
                BudgetAlert.Code.QUOTA_EXCEEDED, Map.of(), null);
    }

    private static java.util.List<String> keys(java.util.List<BudgetService.Ceiling> ceilings) {
        return ceilings.stream().map(BudgetService.Ceiling::lockKey).toList();
    }
}

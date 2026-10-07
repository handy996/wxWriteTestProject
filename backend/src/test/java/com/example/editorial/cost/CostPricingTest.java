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
    @DisplayName("Ceilings default to the documented SRS limits and an unconfigured cap refuses")
    void budgetPolicyCeilings() {
        BudgetPolicy policy = BudgetPolicyConfig.from(new MockEnvironment());
        assertEquals("20.000000", policy.dailyLimit().text());
        assertEquals(30, policy.cap(BudgetPolicy.Counter.SEARCH_QUERY));
        assertEquals(40_000, policy.cap(BudgetPolicy.Counter.MODEL_OUTPUT_TOKENS));
        assertEquals(3, policy.cap(BudgetPolicy.Counter.CLAIM_QUERY));
        assertEquals(1, policy.cap(BudgetPolicy.Counter.AUTO_EDIT_LOOP));
        assertEquals(2, policy.cap(BudgetPolicy.Counter.IMAGE_GENERATION_SLOT));
        assertEquals(4, policy.cap(BudgetPolicy.Counter.IMAGE_GENERATION_ARTICLE));
        assertEquals(80, policy.alertPercent());
        assertEquals(30, policy.staleReconciliationMinutes());
        // A counter with no configured limit is a refusal, never an implicit "unlimited".
        BudgetPolicy bare = new BudgetPolicy(Money.of("20.000000"), Map.of(), Map.of(), 80, 30);
        assertFalse(bare.hasCap(BudgetPolicy.Counter.CALLS));
        assertEquals("QUOTA_NOT_CONFIGURED", failure(() -> bare.cap(BudgetPolicy.Counter.SEARCH_QUERY)).code());
        assertEquals(503, failure(() -> bare.cap(BudgetPolicy.Counter.SEARCH_QUERY)).status());
        // Provider quota resolves "provider|model" first, then the provider, then no provider-side cap at all.
        BudgetPolicy scoped = new BudgetPolicy(Money.of("20.000000"), Map.of(), Map.of(
                "mock", new BudgetPolicy.ProviderQuota(2, 40),
                "mock|mock-model", new BudgetPolicy.ProviderQuota(5, 9)), 80, 30);
        assertEquals(5, scoped.providerQuota("mock", "mock-model").orElseThrow().maxConcurrent());
        assertEquals(2, scoped.providerQuota("mock", "other").orElseThrow().maxConcurrent());
        assertTrue(scoped.providerQuota("other", "x").isEmpty());
        // The alert line is the configured percent of the ceiling, on exact decimals.
        assertTrue(policy.reachedAlert(Money.of("16.000000"), Money.of("20.000000")));
        assertFalse(policy.reachedAlert(Money.of("15.999999"), Money.of("20.000000")));
        assertTrue(new BudgetPolicy(Money.of("20.000000"), Map.of(), Map.of(), 99, 30)
                .reachedAlert(Money.of("19.999999"), Money.of("20.000000")));
        assertTrue(policy.reachedAlert(Money.ZERO, Money.ZERO), "a zero ceiling is already exhausted");
    }

    @Test
    @DisplayName("A configured ceiling is honoured and a bad one is refused at boot")
    void budgetPolicyOverrides() {
        MockEnvironment env = new MockEnvironment()
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
        assertEquals(3, policy.providerQuota("mock", "any").orElseThrow().maxConcurrent());
        assertEquals(17, policy.providerQuota("mock", "any").orElseThrow().callsPerDay());
        assertEquals("INVALID_AMOUNT", failure(() -> BudgetPolicyConfig.from(
                new MockEnvironment().withProperty("editorial.cost.daily-budget", "12.5"))).code());
        assertEquals("INVALID_BUDGET_POLICY", failure(() -> BudgetPolicyConfig.from(new MockEnvironment()
                .withProperty("editorial.cost.search-queries-per-article", "-1"))).code());
        assertEquals("INVALID_BUDGET_POLICY", failure(() -> BudgetPolicyConfig.from(new MockEnvironment()
                .withProperty("editorial.cost.alert-percent", "0"))).code());
        assertEquals("INVALID_BUDGET_POLICY", failure(() -> BudgetPolicyConfig.from(new MockEnvironment()
                .withProperty("editorial.cost.provider-quota.mock.calls-per-day", "-1"))).code());
        assertEquals("INVALID_PROVIDER_QUOTA_KEY", failure(() -> BudgetPolicyConfig.from(new MockEnvironment()
                .withProperty("editorial.cost.provider-quota.max-concurrent", "1"))).code());
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
}

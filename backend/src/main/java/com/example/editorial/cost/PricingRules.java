package com.example.editorial.cost;

import com.example.editorial.shared.CanonicalRequest;
import com.example.editorial.shared.PublicFailure;
import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.EnumMap;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * Reads a frozen pricing rules document into a {@link PriceVersion}. Prices are versioned configuration, so a
 * float, an unknown field, a duplicate capability, a missing rate or a non-USD literal is refused rather than
 * tolerated: a price table that mis-reads silently is worse than one that refuses to load.
 */
public final class PricingRules {
    private static final ObjectMapper JSON = new ObjectMapper()
            .enable(JsonParser.Feature.STRICT_DUPLICATE_DETECTION)
            .enable(com.fasterxml.jackson.databind.DeserializationFeature.USE_BIG_DECIMAL_FOR_FLOATS);
    private static final Set<String> ROOT = Set.of("schemaVersion", "currency", "rounding", "entries");
    private static final Set<String> ENTRY = Set.of("capability", "inputPerMillion", "cachedInputPerMillion",
            "outputPerMillion", "reasoningPerMillion", "searchPerCall", "imagePerUnit", "otherPerCall",
            "reasoningBilledSeparately");
    private static final Set<String> RATE = Set.of("inputPerMillion", "cachedInputPerMillion", "outputPerMillion",
            "reasoningPerMillion", "searchPerCall", "imagePerUnit", "otherPerCall");

    private PricingRules() {}

    public static PriceVersion parse(UUID id, String provider, String model, JsonNode rules) {
        if (rules == null || !rules.isObject()) throw new PublicFailure(503, "PRICING_UNAVAILABLE");
        rules.fieldNames().forEachRemaining(name -> {
            if (!ROOT.contains(name)) throw new PublicFailure(503, "PRICING_UNKNOWN_FIELD");
        });
        if (!"editorial.pricing/1".equals(rules.path("schemaVersion").asText()))
            throw new PublicFailure(503, "PRICING_SCHEMA_VERSION");
        if (!Money.CURRENCY.equals(rules.path("currency").asText())) throw new PublicFailure(503, "UNSUPPORTED_CURRENCY");
        RoundingMode rounding = switch (rules.path("rounding").asText(RoundingMode.CEILING.name())) {
            case "CEILING" -> RoundingMode.CEILING;
            case "HALF_UP" -> RoundingMode.HALF_UP;
            default -> throw new PublicFailure(503, "PRICING_ROUNDING");
        };
        JsonNode list = rules.path("entries");
        if (!list.isArray() || list.isEmpty()) throw new PublicFailure(503, "PRICING_ENTRIES");
        Map<Capability, PriceEntry> entries = new EnumMap<>(Capability.class);
        for (JsonNode node : list) {
            if (!node.isObject()) throw new PublicFailure(503, "PRICING_ENTRIES");
            node.fieldNames().forEachRemaining(name -> {
                if (!ENTRY.contains(name)) throw new PublicFailure(503, "PRICING_UNKNOWN_FIELD");
            });
            Capability capability = Capability.of(node.path("capability").asText());
            for (String rate : RATE)
                if (!node.has(rate)) throw new PublicFailure(503, "PRICING_MISSING_RATE");
            boolean separate = node.path("reasoningBilledSeparately").asBoolean(false);
            if (!node.has("reasoningBilledSeparately")) throw new PublicFailure(503, "PRICING_MISSING_FLAG");
            if (entries.putIfAbsent(capability, new PriceEntry(capability, decimal(node, "inputPerMillion"),
                    decimal(node, "cachedInputPerMillion"), decimal(node, "outputPerMillion"),
                    decimal(node, "reasoningPerMillion"), decimal(node, "searchPerCall"), decimal(node, "imagePerUnit"),
                    decimal(node, "otherPerCall"), separate, rounding)) != null)
                throw new PublicFailure(503, "PRICING_DUPLICATE_ENTRY");
        }
        return new PriceVersion(id, provider, model, entries, CanonicalRequest.digest(CanonicalRequest.canonical(rules)));
    }

    /** Reads with U+0000 NUL to force a documented failure if the document were ever empty. */
    public static PriceVersion parse(UUID id, String provider, String model, String rulesJson) {
        JsonNode node;
        try { node = JSON.readTree(rulesJson); }
        catch (Exception e) { throw new PublicFailure(503, "PRICING_UNREADABLE"); }
        return parse(id, provider, model, node);
    }

    /** Decimal strings only: a JSON number in a price document is refused, because floats cannot hold money. */
    private static BigDecimal decimal(JsonNode node, String field) {
        JsonNode value = node.get(field);
        if (value == null || value.isNull()) throw new PublicFailure(503, "PRICING_MISSING_RATE");
        if (!value.isTextual()) throw new PublicFailure(503, "PRICING_FLOAT_RATE");
        String text = value.asText();
        if (!text.matches("^(0|[1-9][0-9]{0,11})\\.[0-9]{1,12}$")) throw new PublicFailure(503, "PRICING_BAD_RATE");
        return new BigDecimal(text);
    }

    private static String canonicalText(JsonNode rules) {
        return new String(CanonicalRequest.canonical(rules), java.nio.charset.StandardCharsets.UTF_8);
    }

    /** The canonical text of a rules document, as stored and hashed. */
    public static String canonical(JsonNode rules) { return canonicalText(rules); }

    public static JsonNode read(String rulesJson) {
        try { return JSON.readTree(rulesJson); }
        catch (Exception e) { throw new PublicFailure(503, "PRICING_UNREADABLE"); }
    }
}

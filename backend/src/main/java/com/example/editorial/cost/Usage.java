package com.example.editorial.cost;

import com.example.editorial.shared.PublicFailure;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;

/**
 * rc.3 {@code Usage}. Counts are integers, never floats. Reasoning tokens are reported separately by some
 * providers and folded into the output count by others, so the billable output is decided by the price entry
 * that actually produced the charge ({@link PriceEntry#billedOutputTokens(Usage)}) and this type deliberately
 * keeps no combined getter: there is no way to ask it for a number that double-counts reasoning.
 */
public record Usage(int inputTokens, int cachedInputTokens, int outputTokens,
                    Integer reasoningTokensIfProvided, int imageUnits, int searchCalls) {
    public Usage {
        if (inputTokens < 0 || outputTokens < 0 || imageUnits < 0 || searchCalls < 0) fail("NEGATIVE_USAGE");
        if (cachedInputTokens < 0) fail("NEGATIVE_USAGE");
        if (cachedInputTokens > inputTokens) fail("CACHED_TOKENS_EXCEED_INPUT");
        // A reported reasoning count is only a fact about the reply. Whether it bills, and beside what, is
        // decided by the price entry, because that is the only place that knows if the provider already
        // counted those tokens inside the output total.
        if (reasoningTokensIfProvided != null && reasoningTokensIfProvided < 0) fail("NEGATIVE_USAGE");
    }

    /** Tokens billed as ordinary input: the cached part is priced separately, so it must not also bill at full rate. */
    public int uncachedInputTokens() { return inputTokens - cachedInputTokens; }

    public boolean isZero() {
        return inputTokens == 0 && outputTokens == 0 && imageUnits == 0 && searchCalls == 0;
    }

    public Usage plus(Usage other) {
        try {
            return new Usage(Math.addExact(inputTokens, other.inputTokens),
                    Math.addExact(cachedInputTokens, other.cachedInputTokens),
                    Math.addExact(outputTokens, other.outputTokens),
                    reasoningTokensIfProvided == null && other.reasoningTokensIfProvided == null ? null
                            : Math.addExact(reasoningTokensIfProvided == null ? 0 : reasoningTokensIfProvided,
                                    other.reasoningTokensIfProvided == null ? 0 : other.reasoningTokensIfProvided),
                    Math.addExact(imageUnits, other.imageUnits),
                    Math.addExact(searchCalls, other.searchCalls));
        } catch (ArithmeticException e) { throw new PublicFailure(409, "USAGE_OVERFLOW"); }
    }

    public static Usage zero() { return new Usage(0, 0, 0, null, 0, 0); }

    /** Reads the rc.3 shape strictly: the six declared fields, integer types, and a null-only reasoning field. */
    public static Usage read(JsonNode node) {
        if (node == null || !node.isObject()) fail("INVALID_USAGE");
        for (String absent : new String[]{"inputTokens", "cachedInputTokens", "outputTokens",
                "reasoningTokensIfProvided", "imageUnits", "searchCalls"})
            if (!node.has(absent)) fail("USAGE_FIELD_MISSING");
        // All six declared fields present and nothing else: six required names plus size six rules out extras.
        if (node.size() != 6) fail("UNKNOWN_USAGE_FIELD");
        Integer reasoning = null;
        if (!node.get("reasoningTokensIfProvided").isNull()) {
            JsonNode r = node.get("reasoningTokensIfProvided");
            if (!r.isIntegralNumber()) fail("INVALID_USAGE_INTEGER");
            reasoning = checked(r);
        }
        return new Usage(checked(node.get("inputTokens")), checked(node.get("cachedInputTokens")),
                checked(node.get("outputTokens")), reasoning, checked(node.get("imageUnits")), checked(node.get("searchCalls")));
    }

    private static int checked(JsonNode n) {
        if (!n.isIntegralNumber()) fail("INVALID_USAGE_INTEGER");
        if (n.intValue() < 0 || n.longValue() > Integer.MAX_VALUE) fail("USAGE_OUT_OF_RANGE");
        return n.intValue();
    }

    public ObjectNode write(com.fasterxml.jackson.databind.ObjectMapper json) {
        ObjectNode n = json.createObjectNode();
        n.put("inputTokens", inputTokens);
        n.put("cachedInputTokens", cachedInputTokens);
        n.put("outputTokens", outputTokens);
        if (reasoningTokensIfProvided == null) n.putNull("reasoningTokensIfProvided"); else n.put("reasoningTokensIfProvided", reasoningTokensIfProvided);
        n.put("imageUnits", imageUnits);
        n.put("searchCalls", searchCalls);
        return n;
    }

    private static void fail(String code) { throw new PublicFailure(422, code); }
}

package com.example.editorial.settings.policy;

import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

/** Single shared Jackson mapper for T05 domain JSON (wire + stored content), strict on duplicates and trailing data. */
public final class JsonIO {
    public static final ObjectMapper MAPPER = new ObjectMapper()
            .enable(JsonParser.Feature.STRICT_DUPLICATE_DETECTION)
            .enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS);
    private JsonIO() {}

    public static JsonNode parse(String text) {
        try { return text == null ? null : MAPPER.readTree(text); }
        catch (Exception e) { throw new IllegalArgumentException("invalid JSON", e); }
    }

    public static byte[] bytes(JsonNode node) {
        try { return MAPPER.writeValueAsBytes(node); }
        catch (Exception e) { throw new IllegalStateException(e); }
    }

    /** String form for {@code ?::jsonb} binds (JDBC would otherwise treat byte[] as bytea). */
    public static String text(JsonNode node) {
        try { return MAPPER.writeValueAsString(node); }
        catch (Exception e) { throw new IllegalStateException(e); }
    }

    public static byte[] bytes(Object value) {
        try { return MAPPER.writeValueAsBytes(value); }
        catch (Exception e) { throw new IllegalStateException(e); }
    }
}

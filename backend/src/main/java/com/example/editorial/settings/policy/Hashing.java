package com.example.editorial.settings.policy;

import com.example.editorial.shared.CanonicalRequest;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.nio.charset.StandardCharsets;

/** Server-computed content hashes. Clients never declare these; they are recomputed from actual content. */
public final class Hashing {
    private static final ObjectMapper JSON = new ObjectMapper();
    private Hashing() {}

    /** SHA-256 over canonical-v1 JSON of the config/rules content. */
    public static String ofContent(JsonNode content) {
        return CanonicalRequest.digest(CanonicalRequest.canonical(content));
    }

    /** Prompt hash covers the normalized actual templates and the output schema, never client-declared. */
    public static String ofPrompt(String systemTemplate, String userTemplate, JsonNode outputSchema) {
        ObjectNode node = JSON.createObjectNode();
        node.put("systemTemplate", systemTemplate);
        node.put("userTemplate", userTemplate);
        node.set("outputSchema", outputSchema);
        return ofContent(node);
    }

    public static byte[] canonicalBytes(JsonNode content) {
        return CanonicalRequest.canonical(content);
    }

    public static long utf8Size(JsonNode content) {
        return CanonicalRequest.canonical(content).length;
    }

    public static long utf8Size(String text) {
        return text.getBytes(StandardCharsets.UTF_8).length;
    }
}

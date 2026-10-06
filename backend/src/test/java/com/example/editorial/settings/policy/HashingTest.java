package com.example.editorial.settings.policy;

import static org.junit.jupiter.api.Assertions.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.junit.jupiter.api.Test;

class HashingTest {
    @Test void contentHashIsDeterministicAndHex() {
        ObjectNode rules = JsonIO.MAPPER.createObjectNode().put("a", 1);
        String h1 = Hashing.ofContent(rules);
        String h2 = Hashing.ofContent(rules);
        assertEquals(h1, h2);
        assertTrue(h1.matches("[a-f0-9]{64}"));
    }

    @Test void promptHashCoversTemplatesAndSchema() {
        ObjectNode schema = JsonIO.MAPPER.createObjectNode().put("$ref", "#/$defs/AnalysisOutput");
        String base = Hashing.ofPrompt("system", "user", schema);
        assertEquals(base, Hashing.ofPrompt("system", "user", schema));
        assertNotEquals(base, Hashing.ofPrompt("system!", "user", schema));
        assertNotEquals(base, Hashing.ofPrompt("system", "user!", schema));
        ObjectNode other = schema.deepCopy();
        ((ObjectNode) other).put("$ref", "#/$defs/Other");
        assertNotEquals(base, Hashing.ofPrompt("system", "user", other));
    }
}

package com.example.editorial.editorial.skill;

import static org.junit.jupiter.api.Assertions.*;
import com.example.editorial.settings.policy.Hashing;
import com.example.editorial.settings.policy.JsonIO;
import com.example.editorial.settings.policy.PolicyType;
import com.fasterxml.jackson.databind.JsonNode;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.HashSet;
import java.util.Set;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;

/** Offline integrity checks of the built-in baseline resources, independent of any database. */
class BaselineResourcesTest {
    static JsonNode resource(String path) throws Exception {
        try (InputStream in = new ClassPathResource(path).getInputStream()) {
            return JsonIO.MAPPER.readTree(new String(in.readAllBytes(), StandardCharsets.UTF_8));
        }
    }

    @Test void fivePoliciesAllKindsAndRecomputableHashes() throws Exception {
        Set<PolicyType> seen = new HashSet<>();
        for (String file : new String[]{"fact.json", "license.json", "qa.json", "watermark.json", "cost.json"}) {
            JsonNode node = resource("skills/policies/" + file);
            PolicyType type = PolicyType.valueOf(node.path("policyType").asText());
            seen.add(type);
            assertEquals("1.0.0", node.path("version").asText());
            assertTrue(node.path("rules").isObject());
            // hash is recomputable from the rules alone
            assertTrue(Hashing.ofContent(node.path("rules")).matches("[a-f0-9]{64}"));
        }
        assertEquals(Set.of(PolicyType.values()), seen);
    }

    @Test void fourPromptsAllAgentsAndRecomputableHashes() throws Exception {
        Set<String> seen = new HashSet<>();
        for (String file : new String[]{"analyzer.json", "writer-v1.json", "editorial-reviewer.json", "writer-revision-v2.json"}) {
            JsonNode node = resource("prompts/" + file);
            seen.add(node.path("agentName").asText());
            assertTrue(node.path("systemTemplate").isTextual() && !node.path("systemTemplate").asText().isBlank());
            assertTrue(node.path("userTemplate").isTextual() && !node.path("userTemplate").asText().isBlank());
            assertTrue(node.path("outputSchema").isObject());
            assertTrue(Hashing.ofPrompt(node.path("systemTemplate").asText(), node.path("userTemplate").asText(),
                    node.path("outputSchema")).matches("[a-f0-9]{64}"));
            // no secrets or paid-provider calls in templates
            String all = node.path("systemTemplate").asText() + node.path("userTemplate").asText();
            assertFalse(all.toLowerCase().contains("api key"));
            assertFalse(all.toLowerCase().contains("api_key"));
        }
        assertEquals(new HashSet<>(BaselineAgents.ALL), seen);
    }

    @Test void skillManifestBindsAllFourAgentsAndSatisfiesInvariants() throws Exception {
        JsonNode manifest = resource("skills/wechat-editorial-skill.json");
        assertEquals("WechatEditorialSkill", manifest.path("code").asText());
        JsonNode config = manifest.path("config");
        assertEquals("zh-CN", config.path("locale").asText());
        assertEquals("WECHAT", config.path("channel").asText());
        Set<String> agents = new HashSet<>();
        config.path("promptBindings").forEach(b -> agents.add(b.path("agentName").asText()));
        assertEquals(new HashSet<>(BaselineAgents.ALL), agents);
        // readability invariants (the built-in baseline cases)
        JsonNode r = config.path("readabilityRules");
        assertTrue(r.path("recommendedMin").asLong() <= r.path("recommendedMax").asLong());
        assertTrue(r.path("longParagraphWarning").asLong() < r.path("veryLongParagraph").asLong());
        assertTrue(r.path("shortParagraphMax").asLong() < r.path("recommendedMin").asLong());
    }
}

package com.example.editorial.editorial.skill;

import com.example.editorial.settings.policy.PromptBinding;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/**
 * A frozen-valid SkillConfig, held as the authoritative JSON node plus typed accessors. The structural
 * shape is enforced by {@link JsonSchema} against the frozen editorial.schema.json {@code $defs/SkillConfig}
 * before a {@code SkillConfig} is ever accepted; schemaVersion/rulesHash/status are NOT part of this DTO and
 * are server-managed version-row fields.
 */
public record SkillConfig(JsonNode node) {
    public SkillConfig { if (node == null || !node.isObject()) throw new IllegalArgumentException("config must be an object"); }

    public UUID factPolicyRef() { return uuid(node, "factPolicyRef"); }
    public UUID licensePolicyRef() { return uuid(node, "licensePolicyRef"); }

    public List<PromptBinding> promptBindings() {
        List<PromptBinding> bindings = new ArrayList<>();
        for (JsonNode item : node.path("promptBindings")) {
            bindings.add(new PromptBinding(
                    item.path("agentName").asText(),
                    UUID.fromString(item.path("promptVersionId").asText()),
                    item.path("hash").asText(),
                    item.path("outputSchema").asText()));
        }
        return bindings;
    }

    private static UUID uuid(JsonNode node, String field) {
        return UUID.fromString(node.path(field).asText());
    }
}

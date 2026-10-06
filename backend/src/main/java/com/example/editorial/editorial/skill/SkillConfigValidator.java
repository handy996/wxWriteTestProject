package com.example.editorial.editorial.skill;

import com.example.editorial.settings.policy.PolicyService;
import com.example.editorial.settings.policy.PolicyType;
import com.example.editorial.settings.policy.PromptBinding;
import com.example.editorial.settings.policy.PromptService;
import com.example.editorial.settings.policy.PublicationStatus;
import com.example.editorial.shared.PublicFailure;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/**
 * Server-side validation on top of structural {@link JsonSchema} validation. A Skill can only tighten platform
 * hard policies, never relax them: the fact/license policy refs must exist, be of the correct kind and be usable
 * (PUBLISHED); the four baseline prompt bindings must each resolve to a published prompt version whose
 * server-computed hash matches the binding; and readability thresholds must satisfy the built-in baseline invariants.
 * examples/antiExamples are validated as inert string data and are never treated as executable instructions.
 */
public final class SkillConfigValidator {
    private final JsonSchema schema;
    private final PolicyService policies;
    private final PromptService prompts;

    public SkillConfigValidator(JsonSchema schema, PolicyService policies, PromptService prompts) {
        this.schema = schema; this.policies = policies; this.prompts = prompts;
    }

    /** Structural (frozen schema) + semantic validation. */
    public void validate(SkillConfig config) {
        validateStructure(config.node());
        validatePolicy(config.factPolicyRef(), PolicyType.FACT);
        validatePolicy(config.licensePolicyRef(), PolicyType.LICENSE);
        validateBindings(config.promptBindings());
        validateBaselineCases(config.node());
    }

    private void validateStructure(JsonNode config) {
        try { schema.validate(config, "SkillConfig"); }
        catch (IllegalArgumentException e) { throw new PublicFailure(422, "SKILL_CONFIG_INVALID"); }
    }

    private void validatePolicy(UUID policyId, PolicyType requiredType) {
        var policy = policies.getById(policyId); // POLICY_NOT_FOUND if missing
        if (policy.type() != requiredType) throw new PublicFailure(422, "POLICY_REF_INVALID");
        if (policy.status() != PublicationStatus.PUBLISHED) throw new PublicFailure(422, "POLICY_REF_INVALID");
    }

    private void validateBindings(List<PromptBinding> bindings) {
        Set<String> seen = new HashSet<>();
        for (PromptBinding binding : bindings) {
            if (!BaselineAgents.ALL.contains(binding.agentName()))
                throw new PublicFailure(422, "PROMPT_BINDING_INVALID");
            if (!seen.add(binding.agentName()))
                throw new PublicFailure(422, "PROMPT_BINDING_INVALID");
            var prompt = prompts.getById(binding.promptVersionId()); // PROMPT_NOT_FOUND if missing
            if (!prompt.agentName().equals(binding.agentName()))
                throw new PublicFailure(422, "PROMPT_BINDING_INVALID");
            if (prompt.status() != PublicationStatus.PUBLISHED)
                throw new PublicFailure(422, "PROMPT_BINDING_INVALID");
            if (!schema.hasDefinition(binding.outputSchema())
                    || !prompt.outputSchema().path("$ref").asText().equals("#/$defs/" + binding.outputSchema()))
                throw new PublicFailure(422, "PROMPT_OUTPUT_SCHEMA_INVALID");
            if (!prompt.hash().equals(binding.hash()))
                throw new PublicFailure(422, "PROMPT_HASH_MISMATCH");
        }
        if (!seen.equals(new HashSet<>(BaselineAgents.ALL)))
            throw new PublicFailure(422, "PROMPT_BINDING_INVALID");
    }

    private void validateBaselineCases(JsonNode config) {
        JsonNode readability = config.path("readabilityRules");
        long recommendedMin = readability.path("recommendedMin").asLong();
        long recommendedMax = readability.path("recommendedMax").asLong();
        long longWarning = readability.path("longParagraphWarning").asLong();
        long veryLong = readability.path("veryLongParagraph").asLong();
        long shortMax = readability.path("shortParagraphMax").asLong();
        if (recommendedMin > recommendedMax || longWarning >= veryLong || shortMax >= recommendedMin)
            throw new PublicFailure(422, "READABILITY_INVARIANT_VIOLATION");
    }
}

package com.example.editorial.editorial.skill;

import com.example.editorial.settings.policy.JsonIO;
import com.example.editorial.settings.policy.PolicyService;
import com.example.editorial.settings.policy.PolicyType;
import com.example.editorial.settings.policy.PromptService;
import com.example.editorial.settings.policy.PromptVersion;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import com.example.editorial.shared.ActorContext;

/**
 * Repeatable, audited baseline loader. Seeds the five hard policies, the four prompt baselines and the built-in
 * WechatEditorialSkill using the exact same service paths as normal skill/policy/prompt operations (no hardcoded
 * bypass). Idempotent: re-running on every startup never duplicates versions or rewrites published content.
 */
public final class SkillBaselineLoader {
    private static final String[] POLICY_FILES = {"fact.json", "license.json", "qa.json", "watermark.json", "cost.json"};
    private static final String[] PROMPT_FILES = {"analyzer.json", "writer-v1.json", "editorial-reviewer.json", "writer-revision-v2.json"};

    private final JdbcTemplate db;
    private final TransactionTemplate tx;
    private final PolicyService policies;
    private final PromptService prompts;
    private final SkillService skills;

    public SkillBaselineLoader(JdbcTemplate db, PlatformTransactionManager tx, PolicyService policies,
                               PromptService prompts, SkillService skills) {
        this.db = db; this.tx = new TransactionTemplate(tx); this.policies = policies; this.prompts = prompts; this.skills = skills;
    }

    public void load() {
        UUID ownerId = db.query("SELECT id FROM editorial.app_user WHERE bootstrap_key='OWNER'",
                (rs, n) -> rs.getObject(1, UUID.class)).stream().findFirst()
                .orElseThrow(() -> new IllegalStateException("T05_BASELINE: owner not initialized"));
        UUID systemId = db.query("SELECT id FROM editorial.app_user WHERE bootstrap_key='SYSTEM'",
                (rs, n) -> rs.getObject(1, UUID.class)).stream().findFirst()
                .orElseThrow(() -> new IllegalStateException("T05_BASELINE: system actor not initialized"));
        ActorContext actor = ActorContext.forWorker(systemId, ownerId, UUID.randomUUID());

        Map<PolicyType, UUID> policyIds = new HashMap<>();
        for (String file : POLICY_FILES) {
            JsonNode node = resource("skills/policies/" + file);
            var seeded = policies.seed(actor, PolicyType.valueOf(node.path("policyType").asText()),
                    node.path("version").asText(), node.path("rules"));
            policyIds.put(seeded.type(), seeded.id());
        }
        Map<String, PromptVersion> promptsById = new HashMap<>();
        for (String file : PROMPT_FILES) {
            JsonNode node = resource("prompts/" + file);
            var seeded = prompts.seed(actor, node.path("agentName").asText(), node.path("version").asText(),
                    node.path("systemTemplate").asText(), node.path("userTemplate").asText(), node.path("outputSchema"));
            promptsById.put(seeded.agentName(), seeded);
        }
        tx.executeWithoutResult(status -> {
            db.execute("SET LOCAL lock_timeout='2000ms'");
            db.queryForObject("SELECT pg_advisory_xact_lock(?)", Object.class,
                    com.example.editorial.shared.CanonicalRequest.lockKey("T05_BASELINE"));
            seedSkill(actor, policyIds, promptsById);
        });
    }

    private void seedSkill(ActorContext actor, Map<PolicyType, UUID> policyIds, Map<String, PromptVersion> promptsById) {
        JsonNode manifest = resource("skills/wechat-editorial-skill.json");
        String code = manifest.path("code").asText();
        List<UUID> existing = db.query("SELECT id FROM editorial.editorial_skill WHERE code=? AND owner_id=?",
                (rs, n) -> rs.getObject(1, UUID.class), code, actor.ownerId());
        UUID skillId;
        if (existing.isEmpty()) {
            SkillIdentity identity = skills.create(actor, code, manifest.path("name").asText());
            skillId = identity.id();
        } else {
            skillId = existing.getFirst();
        }
        Integer versions = db.queryForObject("SELECT count(*) FROM editorial.editorial_skill_version WHERE skill_id=?",
                Integer.class, skillId);
        if (versions > 0) return; // already seeded

        ObjectNode config = (ObjectNode) manifest.path("config").deepCopy();
        config.put("factPolicyRef", policyIds.get(PolicyType.FACT).toString());
        config.put("licensePolicyRef", policyIds.get(PolicyType.LICENSE).toString());
        ArrayNode bindings = JsonIO.MAPPER.createArrayNode();
        for (JsonNode binding : manifest.path("config").path("promptBindings")) {
            PromptVersion prompt = promptsById.get(binding.path("agentName").asText());
            ObjectNode resolved = JsonIO.MAPPER.createObjectNode();
            resolved.put("agentName", prompt.agentName());
            resolved.put("promptVersionId", prompt.id().toString());
            resolved.put("hash", prompt.hash());
            resolved.put("outputSchema", binding.path("outputSchema").asText());
            bindings.add(resolved);
        }
        config.set("promptBindings", bindings);

        SkillSnapshot draft = skills.createVersion(actor, skillId, null, new SkillConfig(config));
        skills.publish(actor, draft.id(), "内置公众号编辑规则基线 1.0.0");
    }

    private JsonNode resource(String path) {
        try (InputStream in = new ClassPathResource(path).getInputStream()) {
            return JsonIO.MAPPER.readTree(new String(in.readAllBytes(), StandardCharsets.UTF_8));
        } catch (Exception e) { throw new IllegalStateException("T05_BASELINE: missing resource " + path, e); }
    }
}

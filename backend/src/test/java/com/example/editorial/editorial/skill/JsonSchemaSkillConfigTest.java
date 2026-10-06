package com.example.editorial.editorial.skill;

import static org.junit.jupiter.api.Assertions.*;
import com.example.editorial.settings.policy.JsonIO;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;

class JsonSchemaSkillConfigTest {
    static JsonSchema schema;

    @BeforeAll static void load() throws Exception {
        try (InputStream in = new ClassPathResource("skills/editorial.schema.json").getInputStream()) {
            schema = new JsonSchema(JsonIO.MAPPER.readTree(new String(in.readAllBytes(), StandardCharsets.UTF_8)));
        }
    }

    static ObjectNode validConfig() {
        ObjectNode c = JsonIO.MAPPER.createObjectNode();
        c.put("name", "WechatEditorialSkill");
        c.put("description", "公众号内部编辑规则基线");
        c.put("locale", "zh-CN");
        c.put("channel", "WECHAT");
        c.set("audience", array("普通读者"));
        c.set("tone", array("真实", "克制"));
        c.set("structureRules", array("场景→异常→问题"));
        c.set("titleRules", array("提供 5 个候选"));
        c.set("openingRules", JsonIO.MAPPER.createObjectNode().put("problemWithinChars", 300));
        c.set("headingRules", array("概括本节"));
        c.set("readabilityRules", JsonIO.MAPPER.createObjectNode()
                .put("recommendedMin", 40).put("recommendedMax", 160)
                .put("longParagraphWarning", 220).put("veryLongParagraph", 320)
                .put("shortParagraphMax", 29).put("shortParagraphRun", 5));
        c.set("imageRules", JsonIO.MAPPER.createObjectNode().put("maxBodyImages", 5).put("optionalCover", true));
        c.put("factPolicyRef", UUID.randomUUID().toString());
        c.put("licensePolicyRef", UUID.randomUUID().toString());
        ArrayNode bindings = JsonIO.MAPPER.createArrayNode();
        for (String agent : BaselineAgents.ALL) {
            ObjectNode b = JsonIO.MAPPER.createObjectNode();
            b.put("agentName", agent);
            b.put("promptVersionId", UUID.randomUUID().toString());
            b.put("hash", "a".repeat(64));
            b.put("outputSchema", "AnalysisOutput");
            bindings.add(b);
        }
        c.set("promptBindings", bindings);
        c.set("examples", array("示例"));
        c.set("antiExamples", array("反例"));
        c.set("evaluationRubric", array("主题保真"));
        return c;
    }

    static ArrayNode array(String... values) {
        ArrayNode a = JsonIO.MAPPER.createArrayNode();
        for (String v : values) a.add(v);
        return a;
    }

    private static void reject(ObjectNode config) {
        assertThrows(IllegalArgumentException.class, () -> schema.validate(config, "SkillConfig"));
    }

    @Test void acceptsValidConfig() {
        schema.validate(validConfig(), "SkillConfig");
    }

    @Test void rejectsUnknownField() {
        ObjectNode c = validConfig();
        c.put("skipFactCheck", true);
        reject(c);
    }

    @Test void rejectsIllegalEnum() {
        ObjectNode a = validConfig(); a.put("locale", "en-US"); reject(a);
        ObjectNode b = validConfig(); b.put("channel", "OTHER"); reject(b);
    }

    @Test void rejectsWrongType() {
        ObjectNode c = validConfig(); c.put("name", 123); reject(c);
    }

    @Test void rejectsMissingRequiredAndEmptyBindings() {
        ObjectNode a = validConfig(); a.remove("factPolicyRef"); reject(a);
        ObjectNode b = validConfig(); b.set("promptBindings", JsonIO.MAPPER.createArrayNode()); reject(b);
    }

    @Test void rejectsBadUuidAndClientDeclaredFields() {
        ObjectNode a = validConfig(); a.put("factPolicyRef", "not-a-uuid"); reject(a);
        ObjectNode b = validConfig();
        b.put("status", "PUBLISHED");
        b.put("rulesHash", "a".repeat(64));
        b.put("publishedBy", UUID.randomUUID().toString());
        reject(b);
    }
}

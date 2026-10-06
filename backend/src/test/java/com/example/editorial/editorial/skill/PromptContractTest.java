package com.example.editorial.editorial.skill;

import static org.junit.jupiter.api.Assertions.*;
import com.example.editorial.settings.policy.JsonIO;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.util.Map;
import org.junit.jupiter.api.Test;

class PromptContractTest {
    private static final Map<String, String> OUTPUTS = Map.of("analyzer.json", "AnalysisOutput",
            "writer-v1.json", "WriterOutput", "editorial-reviewer.json", "ReviewOutput", "writer-revision-v2.json", "RevisionOutput");

    @Test void allTemplatesBindingsAndFixedOutputsMatchFrozenModelDtos() throws Exception {
        var document = BaselineResourcesTest.resource("skills/editorial.schema.json");
        var schema = new JsonSchema(document);
        var manifest = BaselineResourcesTest.resource("skills/wechat-editorial-skill.json");
        for (var entry : OUTPUTS.entrySet()) {
            var prompt = BaselineResourcesTest.resource("prompts/" + entry.getKey());
            String name = entry.getValue();
            assertEquals(name, prompt.path("outputSchemaName").asText());
            assertEquals("#/$defs/" + name, prompt.path("outputSchema").path("$ref").asText());
            assertTrue(schema.hasDefinition(name));
            assertTrue(prompt.path("userTemplate").asText().contains(name));
            for (var binding : manifest.path("config").path("promptBindings"))
                if (binding.path("agentName").equals(prompt.path("agentName")))
                    assertEquals(name, binding.path("outputSchema").asText());
            ObjectNode sample = sample(name);
            assertDoesNotThrow(() -> schema.validate(sample, name));
            // Every required output field is indispensable; server persistence fields must not leak into model DTOs.
            for (var field : document.path("$defs").path(name).path("required")) {
                ObjectNode missing = sample.deepCopy();
                missing.remove(field.asText());
                assertThrows(IllegalArgumentException.class, () -> schema.validate(missing, name));
            }
            ObjectNode wrapped = sample.deepCopy();
            wrapped.set("meta", JsonIO.MAPPER.createObjectNode());
            assertThrows(IllegalArgumentException.class, () -> schema.validate(wrapped, name));
        }
        var badReview = sample("ReviewOutput");
        badReview.put("inputHash", "0".repeat(64));
        assertThrows(IllegalArgumentException.class, () -> schema.validate(badReview, "ReviewOutput"));
        var badRevision = sample("RevisionOutput");
        ((ObjectNode) badRevision.path("itemDecisions").get(0)).put("reviewItemId", "not-the-frozen-field");
        assertThrows(IllegalArgumentException.class, () -> schema.validate(badRevision, "RevisionOutput"));
        var badWriter = sample("WriterOutput");
        ((ObjectNode) badWriter.path("contentAst")).remove("schemaVersion");
        assertThrows(IllegalArgumentException.class, () -> schema.validate(badWriter, "WriterOutput"));
    }

    @Test void unresolvedReferencesFailClosed() {
        var schema = new JsonSchema(JsonIO.parse("{\"$defs\":{\"Output\":{\"$ref\":\"#/$defs/Missing\"}}}"));
        assertThrows(IllegalArgumentException.class, () -> schema.validate(JsonIO.MAPPER.createObjectNode(), "Output"));
    }

    private static ObjectNode sample(String name) {
        if (name.equals("WriterOutput")) return (ObjectNode) JsonIO.parse("""
            {"title":"让表达更清楚","subtitle":null,"contentAst":{"schemaVersion":"1.0.0-rc.3","blocks":[
              {"sectionId":"s1","blockId":"b1","blockType":"paragraph","text":"可以先说明问题。",
               "marks":[],"claimRefs":[],"level":null,"items":[],"slotId":null}]},
             "changeSummary":"明确开篇问题。","usedClaimIds":[],"newClaimCandidates":[],"requiresReviewItems":[]}
            """);
        if (name.equals("RevisionOutput")) {
            ObjectNode node = JsonIO.MAPPER.createObjectNode();
            node.set("writer", sample("WriterOutput"));
            node.set("itemDecisions", JsonIO.parse("""
                [{"itemId":"00000000-0000-4000-8000-000000000001","disposition":"ACCEPTED","reason":"已明确开篇问题。"}]
                """));
            return node;
        }
        if (name.equals("ReviewOutput")) {
            ObjectNode node = (ObjectNode) JsonIO.parse("""
                {"summary":"开篇可更直接。","overallDecision":"REVISE","items":[{
                "localKey":"review-1","sectionId":"s1","blockId":"b1",
                "span":{"blockId":"b1","start":0,"end":1,"quote":"可","blockHash":"0000000000000000000000000000000000000000000000000000000000000000"},
                "problemType":"MOBILE_READABILITY","severity":"INFO","reason":"建议先说明问题。",
                "recommendedAction":"明确开篇问题。","suggestedReduction":0,"suggestedHeading":null,
                "rewriteSuggestion":null,"relatedClaimIds":[]}]}
                """);
            var scores = node.putArray("scores");
            for (String dimension : java.util.List.of("THESIS", "STRUCTURE", "LOGIC", "READABILITY", "TITLE", "TONE", "FACT_FIDELITY"))
                scores.addObject().put("dimension", dimension).put("score", 4).put("reason", "表达清晰，仍可改进。");
            return node;
        }
        ObjectNode node = (ObjectNode) JsonIO.parse("""
            {"coreThesis":"清楚地说明问题有助于阅读。","targetReader":{"persona":"普通读者","priorKnowledge":"无需背景知识","readerQuestion":"如何表达得更清楚？"},"articleType":"OTHER"}
            """);
        for (String field : java.util.List.of("outline", "strongSections", "weakSections", "repeatedArguments", "sectionsToDelete",
                "sectionsToCompress", "sectionsToExpand", "logicProblems", "factClaims", "recommendedStructure", "recommendedHeadings", "imageOpportunities", "risks", "uncertainties"))
            node.putArray(field);
        var titles = node.putArray("recommendedTitles");
        for (String title : java.util.List.of("让表达更清楚", "先说明问题", "开篇可以这样写", "如何让读者读懂", "从问题开始")) {
            var candidate = titles.addObject().put("text", title).put("angle", "表达建议").put("rationale", "保持原文主题。").put("risk", "无事实断言。");
            candidate.putArray("supportedClaimLocalKeys");
        }
        return node;
    }
}

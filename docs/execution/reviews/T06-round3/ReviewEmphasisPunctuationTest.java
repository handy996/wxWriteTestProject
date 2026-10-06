package com.example.editorial.article.ast;

import static org.junit.jupiter.api.Assertions.*;
import org.junit.jupiter.api.Test;

class ReviewEmphasisPunctuationTest {
    @Test void tripleEmphasisMayEndBeforeChinesePunctuation() {
        var ast = assertDoesNotThrow(() -> ArticleAst.parse("MARKDOWN", "***强调***。\n" + "字".repeat(100)));
        var block = ast.path("blocks").get(0);
        assertEquals("强调。", block.path("text").asText());
        assertEquals(2, block.path("marks").size());
        for (var mark : block.path("marks")) assertEquals(2, mark.path("end").asInt());
    }
    @Test void nestedSharedCloserMayEndBeforeComma() {
        var ast = assertDoesNotThrow(() -> ArticleAst.parse("MARKDOWN", "*a **b***，后文\n" + "字".repeat(100)));
        var block = ast.path("blocks").get(0);
        assertEquals("a b，后文", block.path("text").asText());
        assertEquals(2, block.path("marks").size());
    }
    @Test void singleAndDoubleEmphasisPunctuationControls() {
        for (String input : new String[]{"*强调*。", "**强调**。"}) {
            var ast = ArticleAst.parse("MARKDOWN", input + "\n" + "字".repeat(100));
            assertEquals("强调。", ast.path("blocks").get(0).path("text").asText());
        }
    }
}

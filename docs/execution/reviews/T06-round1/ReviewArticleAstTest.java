package com.example.editorial.article.ast;

import static org.junit.jupiter.api.Assertions.*;
import org.junit.jupiter.api.Test;
import com.example.editorial.shared.PublicFailure;

class ReviewArticleAstTest {
    @Test void nestedEmphasisMustPreserveVisibleText() {
        var ast = ArticleAst.parse("MARKDOWN", "*a **b** c*\n" + "字".repeat(100));
        assertEquals("a b c", ast.path("blocks").get(0).path("text").asText());
        assertTrue(ast.path("blocks").get(0).path("marks").toString().contains("bold"));
    }
    @Test void tripleEmphasisMustNotCountAsReadableText() {
        assertThrows(PublicFailure.class, () -> ArticleAst.parse("MARKDOWN", "***" + "字".repeat(98) + "***"));
    }
    @Test void tripleEmphasisAtMaximumMustRemainAccepted() {
        var ast = assertDoesNotThrow(() -> ArticleAst.parse("MARKDOWN", "***" + "字".repeat(30000) + "***"));
        assertEquals("字".repeat(30000), ArticleAst.plainText(ast));
    }
}

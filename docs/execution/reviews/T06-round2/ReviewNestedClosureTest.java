package com.example.editorial.article.ast;

import static org.junit.jupiter.api.Assertions.*;
import org.junit.jupiter.api.Test;
import com.example.editorial.shared.PublicFailure;

class ReviewNestedClosureTest {
    @Test void adjacentNestedClosersMustNotBecomeOriginalText() {
        for (String input : new String[]{"*a **b***", "**a *b***", "***a* b**", "_a __b___"}) {
            var ast = ArticleAst.parse("MARKDOWN", input + "\n" + "字".repeat(100));
            assertEquals("a b", ast.path("blocks").get(0).path("text").asText(), input);
        }
    }
    @Test void adjacentNestedClosersMustNotSatisfyMinimum() {
        assertThrows(PublicFailure.class, () -> ArticleAst.parse("MARKDOWN", "*" + "字".repeat(97) + " **字***"));
    }
    @Test void adjacentNestedClosersMustNotExceedMaximum() {
        var ast = assertDoesNotThrow(() -> ArticleAst.parse("MARKDOWN", "*" + "字".repeat(29999) + "**字***"));
        assertEquals("字".repeat(30000), ArticleAst.plainText(ast));
    }
}

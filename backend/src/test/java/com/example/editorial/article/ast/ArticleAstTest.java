package com.example.editorial.article.ast;

import static org.junit.jupiter.api.Assertions.*;
import com.example.editorial.shared.*;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.Test;
import static com.example.editorial.article.ast.ArticleAst.*;

class ArticleAstTest {
    static Path root() {String configured=System.getProperty("t06.root");if(configured!=null)return Path.of(configured);
        for(Path p=Path.of("").toAbsolutePath();p!=null;p=p.getParent())if(Files.isRegularFile(p.resolve("docs/schemas/editorial.schema.json")))return p;
        throw new IllegalStateException("Repository root unavailable");}
    @Test void readableCodePointBoundaries() {
        for(int n:new int[]{100,30000}) assertDoesNotThrow(()->parse("TEXT","😀".repeat(n)));
        for(int n:new int[]{99,30001}) assertThrows(PublicFailure.class,()->parse("TEXT","😀".repeat(n)));
        assertThrows(PublicFailure.class,()->parse("TEXT","字".repeat(99)+" \n\t\u00a0\u2003\u0085"));
        assertDoesNotThrow(()->parse("MARKDOWN","**"+"字".repeat(100)+"**"));
        assertThrows(PublicFailure.class,()->parse("MARKDOWN","**"+"字".repeat(99)+"**"));
    }
    @Test void bytesAndEncoding() {
        assertEquals(1048576,decode(new byte[1048576]).length());
        assertThrows(PublicFailure.class,()->decode(new byte[1048577]));
        assertThrows(PublicFailure.class,()->decode(new byte[]{(byte)0xc3,0x28}));
        assertThrows(PublicFailure.class,()->parse("TEXT","x".repeat(100)+"\ud800"));
        assertThrows(PublicFailure.class,()->parse("DOCX","x".repeat(100)));
    }
    @Test void markdownMarksAndLists() {
        var ast=parse("MARKDOWN","# 标题\n- **😀甲**\n- [乙](https://example.org/x)\n\n> "+"引文".repeat(60));
        var list=ast.path("blocks").get(1); assertEquals("😀甲\n乙",list.path("text").asText());
        assertEquals(2,list.path("marks").get(0).path("end").intValue());
        assertEquals(3,list.path("marks").get(1).path("start").intValue());
        var persisted=CanonicalRequest.parse(CanonicalRequest.canonical(ast)); assertEquals(ast,persisted);
        assertEquals(contentHash("题",null,ast),contentHash("题",null,persisted));
    }
    @Test void nestedEmphasisKeepsMarksAndCodePointOffsets() {
        var outerItalic=parse("MARKDOWN","*a **😀b** c*\n"+"字".repeat(100)).path("blocks").get(0);
        assertEquals("a 😀b c",outerItalic.path("text").asText());
        assertEquals("italic",outerItalic.path("marks").get(0).path("type").asText());
        assertEquals(0,outerItalic.path("marks").get(0).path("start").asInt());
        assertEquals(6,outerItalic.path("marks").get(0).path("end").asInt());
        assertEquals("bold",outerItalic.path("marks").get(1).path("type").asText());
        assertEquals(2,outerItalic.path("marks").get(1).path("start").asInt());
        assertEquals(4,outerItalic.path("marks").get(1).path("end").asInt());
        var outerBold=parse("MARKDOWN","**a *b* c**\n"+"字".repeat(100)).path("blocks").get(0);
        assertEquals("a b c",outerBold.path("text").asText());
        assertEquals("bold",outerBold.path("marks").get(0).path("type").asText());
        assertEquals("italic",outerBold.path("marks").get(1).path("type").asText());
    }
    @Test void tripleEmphasisUsesReadableTextForBothBoundaries() {
        assertThrows(PublicFailure.class,()->parse("MARKDOWN","***"+"字".repeat(98)+"***"));
        var ast=parse("MARKDOWN","***"+"字".repeat(30000)+"***");
        assertEquals("字".repeat(30000),plainText(ast));
        var marks=ast.path("blocks").get(0).path("marks");
        assertEquals(2,marks.size());
        assertEquals("bold",marks.get(0).path("type").asText());
        assertEquals("italic",marks.get(1).path("type").asText());
        assertEquals(30000,marks.get(0).path("end").asInt());
        assertThrows(PublicFailure.class,()->parse("MARKDOWN","***"+"字".repeat(30001)+"***"));
    }
    @Test void adjacentNestedClosersConsumeOnlyTheirOwnDelimiters() {
        for (String source : new String[]{"*a **b***", "**a *b***", "***a* b**", "***a** b*", "_a __b___"}) {
            var block=parse("MARKDOWN",source+"\n"+"字".repeat(100)).path("blocks").get(0);
            assertEquals("a b",block.path("text").asText(),source);
            assertEquals(2,block.path("marks").size(),source);
            assertEquals(0,block.path("marks").get(0).path("start").asInt(),source);
            assertEquals(3,block.path("marks").get(0).path("end").asInt(),source);
        }
        var block=parse("MARKDOWN","*😀 **字***\n"+"字".repeat(100)).path("blocks").get(0);
        assertEquals("😀 字",block.path("text").asText());
        assertEquals(2,block.path("marks").get(1).path("start").asInt());
        assertEquals(3,block.path("marks").get(1).path("end").asInt());
        assertThrows(PublicFailure.class,()->parse("MARKDOWN","*"+"字".repeat(97)+" **字***"));
        assertEquals("字".repeat(30000),plainText(parse("MARKDOWN","*"+"字".repeat(29999)+"**字***")));
    }
    @Test void adjacentClosersRespectEscapesAndLiteralStars() {
        var block=parse("MARKDOWN","*a **b\\**** and \\*literal\\*\n"+"字".repeat(100)).path("blocks").get(0);
        assertEquals("a b* and *literal*",block.path("text").asText());
        assertEquals(2,block.path("marks").size());
        assertThrows(PublicFailure.class,()->parse("MARKDOWN","***unclosed\n"+"字".repeat(100)));
    }
    @Test void emphasisClosersAcrossPunctuationWhitespaceAndAdjacentText() {
        record Case(String source,String visible,String[] types,int[] starts,int[] ends) {}
        var cases=java.util.List.of(
                new Case("*强调*","强调",new String[]{"italic"},new int[]{0},new int[]{2}),
                new Case("**强调**","强调",new String[]{"bold"},new int[]{0},new int[]{2}),
                new Case("***强调***","强调",new String[]{"bold","italic"},new int[]{0,0},new int[]{2,2}),
                new Case("*a **b***","a b",new String[]{"italic","bold"},new int[]{0,2},new int[]{3,3}),
                new Case("**a *b***","a b",new String[]{"bold","italic"},new int[]{0,2},new int[]{3,3}),
                new Case("***a* b**","a b",new String[]{"bold","italic"},new int[]{0,0},new int[]{3,1}),
                new Case("***a** b*","a b",new String[]{"italic","bold"},new int[]{0,0},new int[]{3,1}),
                new Case("_a __b___","a b",new String[]{"italic","bold"},new int[]{0,2},new int[]{3,3}));
        for(var sample:cases) for(String suffix:java.util.List.of(""," 后文","。后文","，后文","后文")) {
            var block=parse("MARKDOWN",sample.source()+suffix+"\n"+"字".repeat(100)).path("blocks").get(0);
            assertEquals(sample.visible()+suffix,block.path("text").asText(),sample.source()+suffix);
            assertEquals(sample.types().length,block.path("marks").size(),sample.source()+suffix);
            for(int i=0;i<sample.types().length;i++) {
                var mark=block.path("marks").get(i);
                assertEquals(sample.types()[i],mark.path("type").asText(),sample.source()+suffix);
                assertEquals(sample.starts()[i],mark.path("start").asInt(),sample.source()+suffix);
                assertEquals(sample.ends()[i],mark.path("end").asInt(),sample.source()+suffix);
            }
        }
        var unicode=parse("MARKDOWN","*😀 **字***，后文\n"+"字".repeat(100)).path("blocks").get(0);
        assertEquals("😀 字，后文",unicode.path("text").asText());
        assertEquals(2,unicode.path("marks").get(1).path("start").asInt());
        assertEquals(3,unicode.path("marks").get(1).path("end").asInt());
        var escaped=parse("MARKDOWN","\\*\\*\\*字\\*\\*\\*。\n"+"字".repeat(100)).path("blocks").get(0);
        assertEquals("***字***。",escaped.path("text").asText());
        assertEquals(0,escaped.path("marks").size());
    }
    @Test void escapedAndLiteralStarsRemainReadable() {
        var block=parse("MARKDOWN","\\*bold\\* costs * tax and a*b plus **real**\n"+"字".repeat(100)).path("blocks").get(0);
        assertEquals("*bold* costs * tax and a*b plus real",block.path("text").asText());
        assertEquals(1,block.path("marks").size());
        assertEquals("bold",block.path("marks").get(0).path("type").asText());
        assertThrows(PublicFailure.class,()->parse("MARKDOWN","****"+"字".repeat(100)+"****"));
    }
    @Test void maliciousInputsAndReferences() {
        for(String extra:new String[]{"<script>x</script>","<img src=x>","<!-- x -->","[x](javascript:alert)","[x](http://example.org)","![x](https://example.org/a)","[x][missing]"})
            assertThrows(PublicFailure.class,()->parse("MARKDOWN","字".repeat(100)+extra));
        var ast=parse("TEXT","字".repeat(100)); var blocks=(ArrayNode)ast.path("blocks");blocks.add(blocks.get(0).deepCopy());
        assertThrows(PublicFailure.class,()->validate(ast,(k,id)->{})); blocks.remove(1);
        ((ObjectNode)blocks.get(0)).put("blockType","html"); assertThrows(PublicFailure.class,()->validate(ast,(k,id)->{}));
    }
    @Test void unicodeSpanAndHashAreAuthoritative() {
        var ast=parse("TEXT","😀"+"字".repeat(100)); var b=ast.path("blocks").get(0);
        var span=JSON.createObjectNode().put("blockId",b.path("blockId").asText()).put("start",0).put("end",1).put("quote","😀").put("blockHash",blockHash(b.path("text").asText()));
        assertDoesNotThrow(()->span(ast,span)); span.put("end",2); assertThrows(PublicFailure.class,()->span(ast,span));
        span.put("end",1).put("blockHash","0".repeat(64)); assertThrows(PublicFailure.class,()->span(ast,span));
        span.put("blockId","other"); assertThrows(PublicFailure.class,()->span(ast,span));
    }
    @Test void frozenCanonicalVectors() throws Exception {
        JsonNode vectors=JSON.readTree(Files.readString(root().resolve("tests/fixtures/contracts/T00/rc3/hash-vectors.json")));
        assertEquals(vectors.path("expectedVersionHash").asText(),hash(vectors.path("version")));
        assertEquals(vectors.path("expectedManifestHash").asText(),hash(vectors.path("manifest")));
        var v=vectors.path("version");
        assertEquals(vectors.path("expectedVersionHash").asText(),contentHash(v.path("title").asText(),null,v.path("contentAst")));
        assertThrows(PublicFailure.class,()->CanonicalRequest.parse("{\"a\":1,\"a\":2}".getBytes(StandardCharsets.UTF_8)));
        assertThrows(PublicFailure.class,()->hash(JSON.createObjectNode().put("x",1.1)));
        assertThrows(PublicFailure.class,()->hash(JSON.createObjectNode().put("x",9007199254740992L)));
        assertNotEquals(blockHash("é"),blockHash("é"));
        assertEquals("\"\\u001f\"",new String(CanonicalRequest.canonical(TextNode.valueOf("\u001f")),StandardCharsets.UTF_8));
    }
    @Test void cloneAllocatesNewIdsAndClearsDomainReferences() {
        var original=parse("MARKDOWN","# title\n"+"字".repeat(100)); var clone=cloneAst(original);
        assertNotEquals(original.path("blocks").get(0).path("blockId"),clone.path("blocks").get(0).path("blockId"));
        assertEquals(plainText(original),plainText(clone));
    }
    @Test void frozenRealVersionAndTitleAnchor()throws Exception {
        JsonNode vector=JSON.readTree(Files.readString(root().resolve("tests/fixtures/contracts/T00/rc3/anchor-vectors.json")));
        var v=vector.path("version");assertFalse(v.isMissingNode());assertEquals(v.path("meta").path("contentHash").asText(),contentHash(v.path("title").asText(),v.path("subtitle").isNull()?null:v.path("subtitle").asText(),v.path("contentAst")));
        var title=JSON.createObjectNode().put("title","😀标题");var span=JSON.createObjectNode().put("blockId","title").put("start",0).put("end",1).put("quote","😀").put("blockHash",blockHash("😀标题"));
        assertDoesNotThrow(()->versionSpan(title,span));
        var ast=parse("TEXT","字".repeat(100));((ObjectNode)ast.path("blocks").get(0)).put("blockId","title");assertThrows(PublicFailure.class,()->validate(ast,(k,id)->{}));
    }
}

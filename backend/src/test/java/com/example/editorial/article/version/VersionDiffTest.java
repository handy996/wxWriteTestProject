package com.example.editorial.article.version;

import static org.junit.jupiter.api.Assertions.*;
import static com.example.editorial.article.ast.ArticleAst.*;
import com.example.editorial.shared.PublicFailure;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.*;
import java.util.*;
import org.junit.jupiter.api.Test;

class VersionDiffTest {
    ObjectNode doc(JsonNode ast) {var d=JSON.createObjectNode().put("title","title").putNull("subtitle");d.set("contentAst",ast);d.set("meta",JSON.createObjectNode().put("id",UUID.randomUUID().toString()));return d;}
    ObjectNode ast(int count,String prefix) {
        var ast=JSON.createObjectNode().put("schemaVersion",SCHEMA);var blocks=ast.putArray("blocks");
        for(int i=0;i<count;i++){
            var b=JSON.createObjectNode().put("sectionId","section").put("blockId",prefix+i)
                .put("blockType","paragraph").put("text","x").putNull("level").putNull("slotId");
            b.putArray("marks");b.putArray("claimRefs");b.putArray("items");blocks.add(b);
        }
        validate(ast,(k,id)->com.example.editorial.article.ast.ArticleAst.fail("UNEXPECTED_REFERENCE"));capacity(ast);return ast;
    }
    @Test void marksOrderAndUnicodeAreDetectedWithoutUtf16Offsets() {
        var ast=parse("TEXT","😀"+"字".repeat(100)+"\nsecond");var from=doc(ast);var next=ast.deepCopy();var b=(ObjectNode)next.path("blocks").get(0);
        b.withArray("marks").add(JSON.createObjectNode().put("type","bold").put("start",0).put("end",1).putNull("href"));
        validate(next,(k,id)->com.example.editorial.article.ast.ArticleAst.fail("NO_REFERENCE"));var to=doc(next);var diff=VersionDiff.between(UUID.randomUUID(),from,to);
        assertEquals("CHANGE",diff.path("blocks").get(2).path("kind").asText());assertEquals(diff.path("blocks").get(2).path("before"),diff.path("blocks").get(2).path("after"));
        span(next,JSON.createObjectNode().put("blockId",b.path("blockId").asText()).put("start",0).put("end",1).put("quote","😀").put("blockHash",blockHash(b.path("text").asText())));
        var blocks=(ArrayNode)next.path("blocks");JsonNode first=blocks.remove(0);blocks.add(first);to=doc(next);diff=VersionDiff.between(UUID.randomUUID(),from,to);assertEquals("CHANGE",diff.path("blocks").get(2).path("kind").asText());assertEquals("CHANGE",diff.path("blocks").get(3).path("kind").asText());
    }
    @Test void splitMergeMappingsRequireNewIdsAndActualScope() {
        var old=parse("TEXT","字".repeat(100));var next=old.deepCopy();var first=(ObjectNode)next.path("blocks").get(0);String oldId=first.path("blockId").asText();first.put("blockId",UUID.randomUUID().toString()).put("text","字".repeat(50));var second=first.deepCopy().put("blockId",UUID.randomUUID().toString());((ArrayNode)next.path("blocks")).add(second);
        var m=JSON.createObjectNode().put("reason","SPLIT");m.putArray("fromBlockIds").add(oldId);m.putArray("toBlockIds").add(first.path("blockId")).add(second.path("blockId"));var mappings=JSON.createArrayNode().add(m);
        VersionDiff.mappings(old,next,mappings);m.put("reason","MERGE");assertThrows(PublicFailure.class,()->VersionDiff.mappings(old,next,mappings));
        m.put("reason","SPLIT");first.put("blockId",oldId);assertThrows(PublicFailure.class,()->VersionDiff.mappings(old,next,mappings));
        var renamed=old.deepCopy();((ObjectNode)renamed.path("blocks").get(0)).put("blockId",UUID.randomUUID().toString());assertThrows(PublicFailure.class,()->VersionDiff.mappings(old,renamed,JSON.createArrayNode()));
    }
    @Test void cursorOwnerArticleAndFilterCannotBeRebound(){var c=new PageCursor("test-cursor-key-with-at-least-32-chars");String token=c.write("1","owner-article-filter");assertEquals("1",c.read(token,"owner-article-filter"));assertThrows(PublicFailure.class,()->c.read(token,"different-filter"));}
    @Test void legalMaximumAstCanBeReadFromFirstThroughLastDiffPage() {
        var from=doc(ast(30000,"old"));var to=doc(ast(30000,"new"));var article=UUID.randomUUID();
        assertEquals("DIFF_TOO_LARGE",assertThrows(PublicFailure.class,()->VersionDiff.between(article,from,to)).code());
        var first=VersionDiff.page(article,from,to,0,100);
        assertEquals(60002,first.path("totalBlocks").asInt());assertEquals(100,first.path("blocks").size());
        assertEquals("title",first.path("blocks").get(0).path("blockId").asText());
        assertEquals("new0",first.path("blocks").get(2).path("blockId").asText());
        var middle=VersionDiff.page(article,from,to,30000,100);
        assertEquals("new29998",middle.path("blocks").get(0).path("blockId").asText());
        assertEquals("old0",middle.path("blocks").get(2).path("blockId").asText());
        var last=VersionDiff.page(article,from,to,60000,100);
        assertEquals(2,last.path("blocks").size());
        assertEquals("old29998",last.path("blocks").get(0).path("blockId").asText());
        assertEquals("old29999",last.path("blocks").get(1).path("blockId").asText());
        assertEquals("DELETE",last.path("blocks").get(1).path("kind").asText());
    }
}

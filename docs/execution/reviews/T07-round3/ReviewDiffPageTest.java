package com.example.editorial.article.version;

import static org.junit.jupiter.api.Assertions.*;
import static com.example.editorial.article.ast.ArticleAst.*;
import com.fasterxml.jackson.databind.node.*;
import java.util.*;
import org.junit.jupiter.api.Test;

class ReviewDiffPageTest extends VersionDiffTest {
    @Test void reviewEveryRowOfMaximumDiffHasExpectedPositionKindAndText() {
        var from=doc(ast(30000,"old"));var to=doc(ast(30000,"new"));var article=UUID.randomUUID();
        int seen=0,pages=0;
        for(int offset=0;offset<60002;offset+=100){
            var page=VersionDiff.page(article,from,to,offset,100);
            assertEquals(60002,page.path("totalBlocks").asInt());assertEquals(offset,page.path("offset").asInt());
            assertEquals(Math.min(100,60002-offset),page.path("blocks").size());
            for(var row:page.path("blocks")){
                String id=seen==0?"title":seen==1?"subtitle":seen<30002?"new"+(seen-2):"old"+(seen-30002);
                String kind=seen<2?"UNCHANGED":seen<30002?"ADD":"DELETE";
                assertEquals(id,row.path("blockId").asText());assertEquals(kind,row.path("kind").asText());
                if(seen>=2){assertEquals(seen<30002?"":"x",row.path("before").asText());assertEquals(seen<30002?"x":"",row.path("after").asText());}
                seen++;
            }
            pages++;
        }
        assertEquals(60002,seen);assertEquals(601,pages);
    }
    @Test void reviewSmallMixedDiffPagesEqualFrozenResultAcrossAllPageSizes() {
        var before=ast(100,"b");var initial=(ArrayNode)before.path("blocks");
        while(initial.size()>4)initial.remove(initial.size()-1);
        ((ObjectNode)initial.get(0)).put("text","字".repeat(100));capacity(before);
        var after=before.deepCopy();var blocks=(ArrayNode)after.path("blocks");
        blocks.remove(1);var last=blocks.remove(2);blocks.insert(0,last);
        ((ObjectNode)blocks.get(1)).put("text","😀更新".repeat(100));
        blocks.add(blocks.get(2).deepCopy().deepCopy());((ObjectNode)blocks.get(3)).put("blockId","added");
        var from=doc(before);var to=doc(after).put("title","新标题");var article=UUID.randomUUID();
        var expected=VersionDiff.between(article,from,to).path("blocks");
        assertEquals(7,expected.size());assertEquals("DELETE",expected.get(6).path("kind").asText());
        for(int size:List.of(1,2,3,7,100)){
            var actual=JSON.createArrayNode();
            for(int offset=0;offset<expected.size();offset+=size)for(var row:VersionDiff.page(article,from,to,offset,size).path("blocks"))actual.add(row);
            assertEquals(expected,actual);
        }
    }
}

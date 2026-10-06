package com.example.editorial.article.version;

import static org.junit.jupiter.api.Assertions.*;
import java.util.*;
import org.junit.jupiter.api.Test;

class ReviewDiffHttpTest extends T07PostgresTest {
    @Test void reviewDiffPagesRequireSessionAndHideCrossArticleBeforeCursorCheck() throws Exception {
        var c=signed();var a=tracked(c);var b=tracked(c);
        String route=path(a)+"/diff/pages?from="+head(a)+"&to="+head(a);
        assertEquals(401,new Client().get(route).statusCode());
        var first=ok(c.get(route+"&limit=1"),200);String token=first.path("nextCursor").asText();
        String other=path(b)+"/diff/pages?from="+head(b)+"&to="+head(b)+"&limit=1&cursor="+token;
        error(c.get(other),422,"INVALID_CURSOR");
        error(c.get(path(a)+"/diff/pages?from="+head(a)+"&to="+head(b)+"&cursor=bad"),404,"NOT_FOUND");
        assertEquals(422,c.get(route+"&limit=0").statusCode());assertEquals(422,c.get(route+"&limit=101").statusCode());
    }
}

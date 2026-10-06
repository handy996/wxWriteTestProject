package com.example.editorial.article.version;

import static org.junit.jupiter.api.Assertions.*;
import static com.example.editorial.article.ast.ArticleAst.*;
import com.example.editorial.EditorialApplication;
import com.example.editorial.shared.PublicFailure;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;

@SpringBootTest(classes=EditorialApplication.class,webEnvironment=SpringBootTest.WebEnvironment.RANDOM_PORT)
class T07UnavailableTest extends T07Support {
    @Test void realQueriesWorkButMissingProductionParticipantsRefuseHeadWrites()throws Exception {
        var c=signed();var a=create(c);
        assertEquals(200,c.get(path(a)+"/versions").statusCode());assertEquals(200,c.get(path(a)+"/versions/"+head(a)).statusCode());assertEquals(200,c.get(path(a)+"/diff?from="+head(a)+"&to="+head(a)).statusCode());assertEquals(200,c.get(path(a)+"/proposals").statusCode());
        error(c.write("POST",path(a)+"/versions",edit(a),UUID.randomUUID().toString(),etag(a)),503,"FEATURE_NOT_READY");
        error(c.write("POST",path(a)+"/restore",JSON.createObjectNode().put("versionId",head(a).toString()).put("reason","restore"),UUID.randomUUID().toString(),etag(a)),503,"FEATURE_NOT_READY");assertEquals(1,count(a));
        assertEquals("FEATURE_NOT_READY",assertThrows(PublicFailure.class,()->VersionPorts.unavailableExecutions().inspect(actor(),JSON.createObjectNode(),JSON.createObjectNode())).code());
    }
}

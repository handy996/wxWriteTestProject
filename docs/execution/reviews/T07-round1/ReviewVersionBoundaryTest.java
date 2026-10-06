package com.example.editorial.article.version;

import static org.junit.jupiter.api.Assertions.*;
import static com.example.editorial.article.ast.ArticleAst.*;
import com.example.editorial.article.job.ArticleService;
import com.example.editorial.shared.*;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.Test;

class ReviewVersionBoundaryTest extends T07PostgresTest {
    @Test void reviewRetainedVersionMustBeStaleForNewCommit() throws Exception {
        var c=signed(); var a=tracked(c); var o=output(a); var step=execution(a,o,true);
        var v=versions.commit(actor(),step,o,etag(a));
        assertTrue(v.path("meta").path("stale").asBoolean());
        UUID id=uuid(v.path("meta").path("id").asText());
        var supplied=new Ownership.ArtifactRef(id,articleId(a),id,"VERSION",v.path("meta").path("contentHash").asText(),false);
        var ownership=new Ownership(List.of(articles));
        assertEquals(id,ownership.require(actor(),articleId(a),supplied,false).id());
        var error=assertThrows(PublicFailure.class,()->ownership.require(actor(),articleId(a),supplied,true));
        assertEquals(409,error.status()); assertEquals("STALE_INPUT",error.code());
    }
    @Test void reviewUsedClaimMustBeRecheckedAfterStaging() throws Exception {
        var c=signed(); var a=tracked(c); var o=output(a); UUID claim=UUID.randomUUID();
        o.withArray("usedClaimIds").add(claim.toString());
        var step=execution(a,o,false); var applicable=new AtomicBoolean(true);
        // Explicit references substitute: valid before staging, revoked at the staging barrier.
        VersionPorts.References refs=(ac,j,b,k,id,content)->{
            assertEquals(claim,id);
            if(!applicable.get()) throw new PublicFailure(409,"STALE_INPUT");
        };
        VersionPorts.Store racingStore=new VersionPorts.Store(){
            public ArticleService.PreparedVersion prepare(ActorContext ac,UUID j,VersionPorts.Draft d,com.example.editorial.article.ast.ArticleAst.References r){
                var p=versionStore.prepare(ac,j,d,r); applicable.set(false); return p;
            }
            public UUID append(ActorContext ac,ArticleService.PreparedVersion p,boolean retained,JsonNode style){return versionStore.append(ac,p,retained,style);}
            public List<JsonNode> page(ActorContext ac,UUID j,long before,int limit){return versionStore.page(ac,j,before,limit);}
        };
        var service=new VersionService(articles,racingStore,refs,participants,participants,new PageCursor(System.getenv("AUDIT_CURSOR_KEY")),manager,proposals::staleOther);
        var failure=assertThrows(PublicFailure.class,()->service.commit(actor(),step,o,etag(a)));
        assertEquals("STALE_INPUT",failure.code()); assertEquals(1,count(a)); assertEquals(head(a),head(current(c,a)));
    }
}

package com.example.editorial.article.version;

import static org.junit.jupiter.api.Assertions.*;
import static com.example.editorial.article.ast.ArticleAst.*;
import com.example.editorial.article.job.ArticleService;
import com.example.editorial.shared.*;
import com.example.editorial.storage.*;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.springframework.transaction.support.TransactionSynchronizationManager;

/** Real PG/Local/Ownership regressions; reference applicability and orchestration remain explicit substitutes. */
class T07RevisionBoundaryTest extends T07PostgresTest {
    private Ownership.ArtifactRef ref(JsonNode a,JsonNode v,String kind) {
        UUID id=uuid(v.path("meta").path("id").asText());
        String h=kind.equals("VERSION")?v.path("meta").path("contentHash").asText():db.queryForObject("SELECT object_ref->>'hash' FROM editorial.article_version WHERE id=?",String.class,id);
        return new Ownership.ArtifactRef(id,articleId(a),id,kind,h,false);
    }
    @Test void revisionResolverSeparatesSemanticStaleFromPhysicalRetentionAndPreservesDeletion()throws Exception {
        var c=signed();var a=tracked(c);var original=version(a);var ownership=new Ownership(List.of(articles));
        for(String kind:List.of("VERSION","VERSION_OBJECT"))assertFalse(ownership.require(actor(),articleId(a),ref(a,original,kind),true).stale());
        var o=output(a);var step=execution(a,o,true);var candidate=versions.commit(actor(),step,o,etag(a));UUID id=uuid(candidate.path("meta").path("id").asText());
        assertTrue(candidate.path("meta").path("stale").asBoolean());
        assertTrue(ownership.require(actor(),articleId(a),ref(a,candidate,"VERSION"),false).stale());
        var rejected=assertThrows(PublicFailure.class,()->ownership.require(actor(),articleId(a),ref(a,candidate,"VERSION"),true));assertEquals(409,rejected.status());assertEquals("STALE_INPUT",rejected.code());
        assertFalse(ownership.require(actor(),articleId(a),ref(a,candidate,"VERSION_OBJECT"),true).stale());
        var object=JSON.treeToValue(JSON.readTree(db.queryForObject("SELECT object_ref::text FROM editorial.article_version WHERE id=?",String.class,id)),ObjectRef.class);
        assertEquals(ObjectStatus.COMMITTED,backend.head(object).status());assertArrayEquals(CanonicalRequest.canonical(candidate),backend.get(object));
        assertEquals(candidate,articles.readVersion(actor(),articleId(a),id));
        sql("UPDATE editorial.article_job SET deletion_pending=true,lock_version=lock_version+1,summary=jsonb_set(summary,'{lockVersion}',to_jsonb(lock_version+1)) WHERE id='"+articleId(a)+"'");
        for(var v:List.of(original,candidate))for(String kind:List.of("VERSION","VERSION_OBJECT")) {
            assertTrue(ownership.require(actor(),articleId(a),ref(a,v,kind),false).stale());
            assertEquals("STALE_INPUT",assertThrows(PublicFailure.class,()->ownership.require(actor(),articleId(a),ref(a,v,kind),true)).code());
        }
    }
    private VersionPorts.Store stageHook(Runnable afterStage,AtomicInteger restages) {
        return new VersionPorts.Store() {
            public ArticleService.PreparedVersion prepare(ActorContext a,UUID j,VersionPorts.Draft d,com.example.editorial.article.ast.ArticleAst.References r) {
                assertFalse(TransactionSynchronizationManager.isActualTransactionActive());
                var p=versionStore.prepare(a,j,d,r);afterStage.run();return p;
            }
            public UUID append(ActorContext a,ArticleService.PreparedVersion p,boolean retained,JsonNode style) {
                if(restages!=null&&restages.getAndDecrement()>0)throw new PublicFailure(409,"RESTAGE_REQUIRED");
                return versionStore.append(a,p,retained,style);
            }
            public List<JsonNode> page(ActorContext a,UUID j,long before,int limit){return versionStore.page(a,j,before,limit);}
        };
    }
    private VersionService service(VersionPorts.Store store,VersionPorts.References refs) {
        return new VersionService(articles,store,refs,participants,participants,new PageCursor(System.getenv("AUDIT_CURSOR_KEY")),manager,proposals::staleOther);
    }
    private String businessSnapshot(JsonNode a) {
        return db.queryForObject("SELECT jsonb_build_object('job',to_jsonb(j),'versions',(SELECT jsonb_agg(to_jsonb(v) ORDER BY version_no) FROM editorial.article_version v WHERE v.article_id=j.id),'proposals',(SELECT jsonb_agg(to_jsonb(p) ORDER BY id) FROM editorial.change_proposal p WHERE p.article_id=j.id),'audit',(SELECT jsonb_agg(to_jsonb(a) ORDER BY id) FROM editorial.audit_log a WHERE a.article_id=j.id),'executions',(SELECT jsonb_agg(to_jsonb(e) ORDER BY id) FROM editorial.t07_test_execution e WHERE e.context->>'jobId'=j.id::text),'invalidation',(SELECT to_jsonb(s) FROM editorial.t07_test_state s WHERE s.article_id=j.id))::text FROM editorial.article_job j WHERE j.id=?",String.class,articleId(a));
    }
    @Test void revisionTitleOnlyClaimInvalidatedAfterStagingRollsBackEveryBusinessParticipant()throws Exception {
        var c=signed();var a=tracked(c);var pending=proposal(a);var output=output(a);UUID claim=UUID.randomUUID();output.withArray("usedClaimIds").add(claim.toString());
        var step=execution(a,output,false);var valid=new AtomicBoolean(true);var lockedChecks=new AtomicInteger();
        VersionPorts.References refs=(actor,j,b,k,id,content)->{
            assertEquals(claim,id);assertEquals("CLAIM",k);assertEquals(articleId(a),j);assertEquals(head(a),b);assertEquals(output,content);
            if(TransactionSynchronizationManager.isActualTransactionActive())lockedChecks.incrementAndGet();
            if(!valid.get())throw new PublicFailure(409,"STALE_INPUT");
        };
        String before=businessSnapshot(a);
        var failure=assertThrows(PublicFailure.class,()->service(stageHook(()->valid.set(false),null),refs).commit(actor(),step,output,etag(a)));
        assertEquals("STALE_INPUT",failure.code());assertEquals(1,lockedChecks.get());assertEquals(before,businessSnapshot(a));
        assertEquals("PENDING",proposals.read(actor(),uuid(pending.path("meta").path("id").asText()),false).path("status").asText());
        // Same persisted execution can finish once the reference is applicable again.
        valid.set(true);var committed=service(versionStore,refs).commit(actor(),step,output,etag(a));assertEquals(2,lockedChecks.get());
        assertEquals(committed.path("meta").path("id").asText(),head(current(c,a)).toString());
        assertEquals("STALE",proposals.read(actor(),uuid(pending.path("meta").path("id").asText()),false).path("status").asText());
        assertEquals(uuid(committed.path("meta").path("id").asText()),db.queryForObject("SELECT result_id FROM editorial.t07_test_execution WHERE id=?",UUID.class,uuid(step.path("stepExecutionId").asText())));
    }
    @Test void revisionRechecksTitleClaimOnEachRestagedAttempt()throws Exception {
        var c=signed();var a=tracked(c);var output=output(a);UUID claim=UUID.randomUUID();output.withArray("usedClaimIds").add(claim.toString());var step=execution(a,output,false);
        var stages=new AtomicInteger();var lockedChecks=new AtomicInteger();
        VersionPorts.References refs=(actor,j,b,k,id,content)->{
            assertEquals(claim,id);if(TransactionSynchronizationManager.isActualTransactionActive())lockedChecks.incrementAndGet();
            if(stages.get()>=2)throw new PublicFailure(409,"STALE_INPUT");
        };
        String before=businessSnapshot(a);
        var failure=assertThrows(PublicFailure.class,()->service(stageHook(stages::incrementAndGet,new AtomicInteger(1)),refs).commit(actor(),step,output,etag(a)));
        assertEquals("STALE_INPUT",failure.code());assertEquals(2,stages.get());assertEquals(2,lockedChecks.get());assertEquals(before,businessSnapshot(a));
    }
    @Test void revisionCompletedExecutionReplayPrecedesPostStageClaimRevalidation()throws Exception {
        var c=signed();var a=tracked(c);var output=output(a);UUID claim=UUID.randomUUID();output.withArray("usedClaimIds").add(claim.toString());var step=execution(a,output,false);
        var valid=new AtomicBoolean(true);var lockedChecks=new AtomicInteger();var winner=new AtomicReference<JsonNode>();
        VersionPorts.References refs=(actor,j,b,k,id,content)->{
            if(TransactionSynchronizationManager.isActualTransactionActive())lockedChecks.incrementAndGet();
            if(!valid.get())throw new PublicFailure(409,"STALE_INPUT");
        };
        var competing=stageHook(()->{winner.set(service(versionStore,refs).commit(actor(),step,output,etag(a)));valid.set(false);},null);
        var replay=service(competing,refs).commit(actor(),step,output,etag(a));
        assertEquals(winner.get(),replay);assertEquals(1,lockedChecks.get());assertEquals(2,count(a));assertEquals(replay.path("meta").path("id").asText(),head(current(c,a)).toString());
    }
}

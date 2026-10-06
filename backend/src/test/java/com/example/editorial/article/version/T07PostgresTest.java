package com.example.editorial.article.version;

import static org.junit.jupiter.api.Assertions.*;
import static com.example.editorial.article.ast.ArticleAst.*;
import com.example.editorial.EditorialApplication;
import com.example.editorial.shared.*;
import com.example.editorial.storage.*;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.*;
import java.net.http.HttpResponse;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.transaction.support.TransactionTemplate;

@SpringBootTest(classes=EditorialApplication.class,webEnvironment=SpringBootTest.WebEnvironment.RANDOM_PORT)
@Import(TestParticipants.Config.class)
@org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable(named="T06_REAL_PG",matches="true")
class T07PostgresTest extends T07Support {
    @Autowired TestParticipants participants;
    @BeforeEach void fixture()throws Exception {
        participants.failure="";
        participants.staged=null;participants.release=null;
        sql("CREATE TABLE IF NOT EXISTS editorial.t07_test_state(article_id uuid PRIMARY KEY,fence integer NOT NULL DEFAULT 1,qa_valid boolean DEFAULT true,approval_valid boolean DEFAULT true,invalidations integer DEFAULT 0); GRANT ALL ON editorial.t07_test_state TO editorial_runtime; CREATE TABLE IF NOT EXISTS editorial.t07_test_execution(id uuid PRIMARY KEY,context jsonb,style jsonb,output_hash text,result_id uuid UNIQUE,agent_id uuid,conflict boolean); GRANT ALL ON editorial.t07_test_execution TO editorial_runtime");
    }
    JsonNode tracked(Client c)throws Exception {var a=create(c);db.update("INSERT INTO editorial.t07_test_state(article_id) VALUES(?)",articleId(a));return a;}
    ObjectNode output(JsonNode a){var v=version(a);var n=JSON.createObjectNode().put("title","AI title").putNull("subtitle").put("changeSummary","Generated candidate");n.set("contentAst",v.path("contentAst").deepCopy());n.putArray("usedClaimIds");n.putArray("newClaimCandidates");n.putArray("requiresReviewItems");return n;}
    ObjectNode execution(JsonNode a,JsonNode output,boolean proposal) {
        var worker=actor();var c=JSON.createObjectNode().put("jobId",articleId(a).toString()).put("workflowId",UUID.randomUUID().toString()).put("stepExecutionId",UUID.randomUUID().toString()).put("stepCode",proposal?"REVISE":"WRITE").put("attempt",1).put("scopeId",articleId(a).toString()).put("workflowGeneration",1).put("logicalKey","a".repeat(64)).put("baseVersionId",head(a).toString()).put("inputHash",hash(output)).put("skillVersionId",skill().toString()).put("deadline","2030-01-01T00:00:00Z").put("traceId",worker.traceId().toString()).put("fencingToken",1).putNull("budgetReservationId");
        c.putArray("policyVersions");c.set("actor",JSON.createObjectNode().put("actorId",worker.actorId().toString()).put("ownerId",worker.ownerId().toString()).put("actorType","SYSTEM_WORKER").put("traceId",worker.traceId().toString()).put("authenticatedAt",worker.authenticatedAt().toString()));
        String style=db.queryForObject("SELECT style_snapshot::text FROM editorial.article_job WHERE id=?",String.class,articleId(a));
        db.update("INSERT INTO editorial.t07_test_execution(id,context,style,output_hash,agent_id) VALUES(?,?::jsonb,?::jsonb,?,?)",uuid(c.path("stepExecutionId").asText()),c.toString(),style,hash(output),UUID.randomUUID());return c;
    }
    JsonNode proposal(JsonNode a)throws Exception {
        var o=output(a);var step=execution(a,o,true);var candidate=versions.commit(actor(),step,o,etag(a));
        return new TransactionTemplate(manager).execute(s->proposals.create(actor(),articleId(a),head(a),uuid(candidate.path("meta").path("id").asText()),JSON.createArrayNode().add(version(a).path("contentAst").path("blocks").get(0).path("blockId").asText())));
    }
    @Test void manualRestoreDiffAndImmutableObjects()throws Exception {
        var c=signed();var a=tracked(c);var original=version(a);var request=edit(a);
        ((ObjectNode)request.path("contentAst").path("blocks").get(0)).put("text","😀修改"+"字".repeat(100));
        var r=c.write("POST",path(a)+"/versions",request,UUID.randomUUID().toString(),etag(a));var saved=ok(r,201);assertEquals("\"job-2\"",r.headers().firstValue("ETag").orElseThrow());
        assertEquals("MANUAL",saved.path("kind").asText());assertEquals(original.path("meta").path("id"),saved.path("parentVersionId"));assertEquals(original,articles.readVersion(actor(),articleId(a),head(a)));
        assertEquals(saved.path("contentAst").path("blocks").get(0).path("blockId"),original.path("contentAst").path("blocks").get(0).path("blockId"));
        var restore=JSON.createObjectNode().put("versionId",head(a).toString()).put("reason","Restore old draft");
        var restored=ok(c.write("POST",path(a)+"/restore",restore,UUID.randomUUID().toString(),"\"job-2\""),201);
        assertEquals("RESTORE",restored.path("kind").asText());assertEquals(3,restored.path("versionNo").asInt());assertEquals(saved.path("meta").path("id"),restored.path("parentVersionId"));assertEquals(original.path("meta").path("id"),restored.path("restoredFromVersionId"));assertEquals(original.path("meta").path("contentHash"),restored.path("meta").path("contentHash"));
        var diff=ok(c.get(path(a)+"/diff?from="+head(a)+"&to="+saved.path("meta").path("id").asText()),200);assertEquals("CHANGE",diff.path("blocks").get(0).path("kind").asText());assertEquals(diff,versions.diff(actor(),articleId(a),head(a),uuid(saved.path("meta").path("id").asText())));
        assertEquals("UNKNOWN",current(c,a).path("rightsSnapshot").path("basis").asText());assertFalse(db.queryForObject("SELECT qa_valid OR approval_valid FROM editorial.t07_test_state WHERE article_id=?",Boolean.class,articleId(a)));
        for(var v:List.of(saved,restored)) {var object=JSON.readTree(db.queryForObject("SELECT object_ref::text FROM editorial.article_version WHERE id=?",String.class,uuid(v.path("meta").path("id").asText())));var ref=JSON.treeToValue(object,ObjectRef.class);assertArrayEquals(CanonicalRequest.canonical(v),backend.get(ref));assertEquals(ObjectStatus.COMMITTED,backend.head(ref).status());}
        sample("ArticleVersion",saved);sample("RestoreVersion",restored);sample("Diff",diff);sample("ArticleVersionPage",ok(c.get(path(a)+"/versions"),200));
        var get=c.get(path(a)+"/versions/"+saved.path("meta").path("id").asText());assertEquals("\"job-3\"",get.headers().firstValue("ETag").orElseThrow());assertEquals(saved,ok(get,200));
    }
    @Test void pagedDiffReadsEveryLargeVersionRowWithBoundCursor()throws Exception {
        var c=signed();var article=tracked(c);var request=edit(article);
        var blocks=(ArrayNode)request.path("contentAst").path("blocks");var template=(ObjectNode)blocks.get(0);
        for(int i=0;i<1001;i++){var added=template.deepCopy().put("blockId","paged"+i).put("text","字");blocks.add(added);}
        var saved=ok(c.write("POST",path(article)+"/versions",request,UUID.randomUUID().toString(),etag(article)),201);
        String base=path(article)+"/diff?from="+head(article)+"&to="+saved.path("meta").path("id").asText();
        error(c.get(base),422,"DIFF_TOO_LARGE");
        String pages=path(article)+"/diff/pages?from="+head(article)+"&to="+saved.path("meta").path("id").asText()+"&limit=100";
        var first=ok(c.get(pages),200);sample("DiffPage",first);
        assertEquals(100,first.path("blocks").size());assertEquals(1004,first.path("totalBlocks").asInt());
        String token=first.path("nextCursor").asText();
        error(c.get(pages+"&cursor="+token+"x"),422,"INVALID_CURSOR");
        error(c.get(pages.replace("limit=100","limit=99")+"&cursor="+token),422,"INVALID_CURSOR");
        error(c.get(pages.replace("from="+head(article),"from="+saved.path("meta").path("id").asText())+"&cursor="+token),422,"INVALID_CURSOR");
        var hidden=ActorContext.forWorker(UUID.randomUUID(),UUID.randomUUID(),UUID.randomUUID());
        assertEquals(404,assertThrows(PublicFailure.class,()->versions.diffPage(hidden,articleId(article),head(article),uuid(saved.path("meta").path("id").asText()),null,100)).status());
        var ids=new ArrayList<String>();String cursor=null;int pagesRead=0;
        do {
            var page=ok(c.get(pages+(cursor==null?"":"&cursor="+cursor)),200);
            assertEquals(ids.size(),page.path("offset").asInt());
            for(var row:page.path("blocks"))ids.add(row.path("blockId").asText());
            cursor=page.path("nextCursor").isNull()?null:page.path("nextCursor").asText();pagesRead++;
        }while(cursor!=null);
        assertEquals(11,pagesRead);assertEquals(first.path("totalBlocks").asInt(),ids.size());
        assertEquals(ids.size(),new HashSet<>(ids).size());assertEquals("paged1000",ids.getLast());
    }
    @Test void preconditionsAuthorizationReplayAndConcurrentSameKey()throws Exception {
        var c=signed();var a=tracked(c);var body=edit(a);String path=path(a)+"/versions",key=UUID.randomUUID().toString();
        error(c.write("POST",path,body,key,null),428,"IF_MATCH_REQUIRED");error(c.write("POST",path,body,key,"\"job-0\""),412,"ETAG_MISMATCH");
        var wrong=body.deepCopy().put("baseVersionId",UUID.randomUUID().toString());error(c.write("POST",path,wrong,key,etag(a)),409,"STALE_INPUT");
        try(var pool=Executors.newFixedThreadPool(4)) {var fs=new ArrayList<Future<HttpResponse<String>>>();for(int i=0;i<4;i++)fs.add(pool.submit(()->c.write("POST",path,body,key,etag(a))));var first=fs.getFirst().get();assertEquals(201,first.statusCode(),first.body());for(var f:fs)assertEquals(first.body(),f.get().body());}
        assertEquals(2,count(a));assertEquals(201,c.write("POST",path,body,key,null).statusCode()); // replay before ETag
        body.put("reason","different");error(c.write("POST",path,body,key,null),409,"IDEMPOTENCY_CONFLICT");
        assertEquals(401,new Client().get(path).statusCode());
        var other=ActorContext.forWorker(UUID.randomUUID(),UUID.randomUUID(),UUID.randomUUID());
        assertEquals(404,assertThrows(PublicFailure.class,()->versions.list(other,articleId(a),null,20)).status());
        assertEquals(404,assertThrows(PublicFailure.class,()->idem.execute(other,"POST",path,null,key,CanonicalRequest.hash("POST",path,CanonicalRequest.canonical(body)),CanonicalRequest.canonical(body),()->articles.job(other,articleId(a),true),()->{},Idempotency.Response::empty)).status());
    }
    @Test void signedCursorStableOrderAndHiddenCrossArticle()throws Exception {
        var c=signed();var a=tracked(c);ok(c.write("POST",path(a)+"/versions",edit(a),UUID.randomUUID().toString(),etag(a)),201);
        var first=ok(c.get(path(a)+"/versions?limit=1"),200);String cursor=first.path("nextCursor").asText();assertEquals(2,first.path("items").get(0).path("versionNo").asInt());
        var now=current(c,a);ok(c.write("POST",path(a)+"/versions",edit(now),UUID.randomUUID().toString(),etag(now)),201);
        assertEquals(1,ok(c.get(path(a)+"/versions?limit=1&cursor="+cursor),200).path("items").get(0).path("versionNo").asInt());
        error(c.get(path(a)+"/versions?cursor="+cursor+"x"),422,"INVALID_CURSOR");var b=tracked(c);error(c.get(path(b)+"/versions?cursor="+cursor),422,"INVALID_CURSOR");
        error(c.get(path(b)+"/versions/"+head(a)),404,"NOT_FOUND");error(c.get(path(a)+"/diff?from="+head(a)+"&to="+head(b)),404,"NOT_FOUND");
        error(c.write("POST",path(a)+"/restore",JSON.createObjectNode().put("versionId",head(b).toString()).put("reason","bad source"),UUID.randomUUID().toString(),etag(now).replace("2","3")),404,"NOT_FOUND");
    }
    @Test void proposalAcceptBusinessUniquenessRejectAndStale()throws Exception {
        var c=signed();var a=tracked(c);var p=proposal(a);assertEquals(head(a),head(current(c,a)));String id=p.path("meta").path("id").asText();var body=JSON.createObjectNode().put("baseVersionId",head(a).toString());
        error(c.write("POST","/api/v1/proposals/"+id+"/accept",body,UUID.randomUUID().toString(),null),428,"IF_MATCH_REQUIRED");
        sample("ProposalPage",ok(c.get(path(a)+"/proposals?status=PENDING"),200));
        try(var pool=Executors.newFixedThreadPool(2)) {
            var f1=pool.submit(()->c.write("POST","/api/v1/proposals/"+id+"/accept",body,UUID.randomUUID().toString(),etag(a)));
            var f2=pool.submit(()->c.write("POST","/api/v1/proposals/"+id+"/accept",body,UUID.randomUUID().toString(),etag(a)));
            var statuses=new ArrayList<>(List.of(f1.get().statusCode(),f2.get().statusCode()));Collections.sort(statuses);assertEquals(List.of(201,412),statuses);
        }
        assertEquals(3,count(a));assertEquals("ACCEPTED",proposals.read(actor(),uuid(id),false).path("status").asText());
        error(c.write("POST","/api/v1/proposals/"+id+"/accept",body,UUID.randomUUID().toString(),etag(current(c,a))),409,"STALE_INPUT");
        var b=tracked(c);var rejected=proposal(b);String rejectPath="/api/v1/proposals/"+rejected.path("meta").path("id").asText()+"/reject";
        error(c.write("POST",rejectPath,JSON.createObjectNode().put("reason","  "),UUID.randomUUID().toString(),null),422,"REASON_REQUIRED");
        var disposition=ok(c.write("POST",rejectPath,JSON.createObjectNode().put("reason","Keep current text"),UUID.randomUUID().toString(),null),200);sample("DispositionResult",disposition);assertEquals(head(b),head(current(c,b)));assertEquals(2,count(b));
        assertEquals(1,db.queryForObject("SELECT count(*) FROM editorial.audit_log WHERE id=?",Integer.class,uuid(disposition.path("auditId").asText())));
        error(c.write("POST",rejectPath,JSON.createObjectNode().put("reason","Again"),UUID.randomUUID().toString(),null),409,"PROPOSAL_CONFLICT");
        var stale=proposal(b);ok(c.write("POST",path(b)+"/versions",edit(b),UUID.randomUUID().toString(),etag(b)),201);
        assertEquals("STALE",proposals.read(actor(),uuid(stale.path("meta").path("id").asText()),false).path("status").asText());
    }
    @Test void lateAiPreservesOriginalSnapshotAndRejectsForgedFence()throws Exception {
        var c=signed();var a=tracked(c);var output=output(a);var step=execution(a,output,false);String originalStyle=db.queryForObject("SELECT style::text FROM editorial.t07_test_execution WHERE id=?",String.class,uuid(step.path("stepExecutionId").asText()));
        var saved=ok(c.write("POST",path(a)+"/versions",edit(a),UUID.randomUUID().toString(),etag(a)),201);
        var late=versions.commit(actor(),step,output,etag(a));assertTrue(late.path("meta").path("stale").asBoolean());assertEquals(head(a).toString(),late.path("parentVersionId").asText());assertEquals(3,late.path("versionNo").asInt());assertEquals(saved.path("meta").path("id").asText(),head(current(c,a)).toString());
        assertEquals(originalStyle,db.queryForObject("SELECT style_snapshot::text FROM editorial.article_version WHERE id=?",String.class,uuid(late.path("meta").path("id").asText())));assertEquals(late,versions.commit(actor(),step,output,etag(a)));assertEquals(3,count(a));
        var forged=step.deepCopy().put("fencingToken",999);assertEquals("STALE_FENCE",assertThrows(PublicFailure.class,()->versions.commit(actor(),forged,output,etag(a))).code());
        sample("LateVersion",late);sample("StepContext",step);sample("WriterOutput",output);
    }
    @Test void provisionalNumberRaceRestagesWithoutRewritingObject()throws Exception {
        var c=signed();var a=tracked(c);var o=output(a);var step=execution(a,o,true);
        var d=new VersionPorts.Draft(head(a),null,etag(a),"DRAFT","AI","candidate",null,version(a).path("contentAst"),"candidate",JSON.createArrayNode(),UUID.randomUUID(),hash(o),true);
        var p1=versionStore.prepare(actor(),articleId(a),d,(k,id)->com.example.editorial.article.ast.ArticleAst.fail("NO_REFERENCE"));var p2=versionStore.prepare(actor(),articleId(a),d,(k,id)->com.example.editorial.article.ast.ArticleAst.fail("NO_REFERENCE"));
        var style=JSON.readTree(db.queryForObject("SELECT style_snapshot::text FROM editorial.article_job WHERE id=?",String.class,articleId(a)));
        new TransactionTemplate(manager).execute(s->versionStore.append(actor(),p1,true,style));
        assertEquals("RESTAGE_REQUIRED",assertThrows(PublicFailure.class,()->new TransactionTemplate(manager).execute(s->versionStore.append(actor(),p2,true,style))).code());
        var late=versions.commit(actor(),step,o,etag(a));assertEquals(3,late.path("versionNo").asInt());assertEquals(head(a),head(current(c,a)));assertEquals(3,count(a));
    }
    @Test void transactionalFailuresRollbackHeadVersionDispositionFencesAndRights()throws Exception {
        var c=signed();var a=tracked(c);var p=proposal(a);String route="/api/v1/proposals/"+p.path("meta").path("id").asText()+"/accept";var body=JSON.createObjectNode().put("baseVersionId",head(a).toString());
        for(String point:List.of("fence","changes","audit","idempotency","reference")) {
            participants.failure=point;String table=switch(point){case "audit"->"audit_log";case "idempotency"->"idempotency_record";default->null;};
            if(table!=null)sql("CREATE FUNCTION editorial.t07_inject() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'injected'; END $$; CREATE TRIGGER t07_inject BEFORE INSERT ON editorial."+table+" FOR EACH ROW "+(point.equals("audit")?"WHEN (NEW.action='VERSION_HEAD_CHANGED') ":"")+"EXECUTE FUNCTION editorial.t07_inject()");
            try {var r=c.write("POST",route,body,UUID.randomUUID().toString(),etag(a));assertTrue(r.statusCode()>=400,r.body());assertEquals(head(a),head(current(c,a)));assertEquals(2,count(a));assertEquals("PENDING",proposals.read(actor(),uuid(p.path("meta").path("id").asText()),false).path("status").asText());assertEquals(1,db.queryForObject("SELECT fence FROM editorial.t07_test_state WHERE article_id=?",Integer.class,articleId(a)));assertTrue(db.queryForObject("SELECT qa_valid AND approval_valid FROM editorial.t07_test_state WHERE article_id=?",Boolean.class,articleId(a)));}
            finally {if(table!=null)sql("DROP TRIGGER t07_inject ON editorial."+table+"; DROP FUNCTION editorial.t07_inject()");}
        }
        participants.failure="";assertEquals(201,c.write("POST",route,body,UUID.randomUUID().toString(),etag(a)).statusCode());
    }
    @Test void cancelledDeletionAndReferenceValidation()throws Exception {
        var c=signed();var a=tracked(c);var edit=edit(a);((ArrayNode)edit.path("contentAst").path("blocks").get(0).path("claimRefs")).add(UUID.randomUUID().toString());
        error(c.write("POST",path(a)+"/versions",edit,UUID.randomUUID().toString(),etag(a)),503,"REFERENCE_VALIDATION_NOT_READY");assertEquals(1,count(a));
        for(String state:List.of("CANCELLED","DELETION")) {
            var b=tracked(c);var p=proposal(b);var o=output(b);var step=execution(b,o,false);
            sql("UPDATE editorial.article_job SET "+(state.equals("CANCELLED")?"status='CANCELLED', summary=jsonb_set(jsonb_set(summary,'{status}','\"CANCELLED\"'),'{lockVersion}',to_jsonb(lock_version+1))":"deletion_pending=true,summary=jsonb_set(summary,'{lockVersion}',to_jsonb(lock_version+1))")+",lock_version=lock_version+1 WHERE id='"+articleId(b)+"'");
            String code=state.equals("CANCELLED")?"CANCELLED":"DELETION_PENDING";
            error(c.write("POST",path(b)+"/versions",edit(b),UUID.randomUUID().toString(),"\"job-2\""),409,code);
            assertEquals(code,assertThrows(PublicFailure.class,()->versions.commit(actor(),step,o,etag(b))).code());assertEquals(2,count(b));
            error(c.write("POST","/api/v1/proposals/"+p.path("meta").path("id").asText()+"/reject",JSON.createObjectNode().put("reason","reject"),UUID.randomUUID().toString(),null),409,code);
        }
    }
    @Test void stagedAiAndManualSaveRaceRetainsCandidateAndNeverOverwritesHead()throws Exception {
        var c=signed();var a=tracked(c);var o=output(a);var step=execution(a,o,false);
        participants.staged=new CountDownLatch(1);participants.release=new CountDownLatch(1);
        try(var pool=Executors.newSingleThreadExecutor()) {
            var ai=pool.submit(()->versions.commit(actor(),step,o,etag(a)));
            try {assertTrue(participants.staged.await(10,TimeUnit.SECONDS));var manual=ok(c.write("POST",path(a)+"/versions",edit(a),UUID.randomUUID().toString(),etag(a)),201);participants.release.countDown();
                var result=ai.get(15,TimeUnit.SECONDS);assertTrue(result.path("meta").path("stale").asBoolean());assertEquals(3,result.path("versionNo").asInt());assertEquals(manual.path("meta").path("id").asText(),head(current(c,a)).toString());assertEquals(head(a).toString(),result.path("parentVersionId").asText());assertEquals(3,count(a));
            }finally{participants.release.countDown();}
        }
    }
    @Test void concurrentCandidatesUseUniqueMonotonicNumbersAndCurrentAiCommitsOnce()throws Exception {
        var c=signed();var a=tracked(c);var o=output(a);var first=execution(a,o,false);var result=versions.commit(actor(),first,o,etag(a));assertFalse(result.path("meta").path("stale").asBoolean());assertEquals(result.path("meta").path("id").asText(),head(current(c,a)).toString());assertEquals(result,versions.commit(actor(),first,o,etag(a)));
        var b=tracked(c);var output=output(b);var steps=new ArrayList<JsonNode>();for(int i=0;i<4;i++)steps.add(execution(b,output,true));
        try(var pool=Executors.newFixedThreadPool(4)){var futures=new ArrayList<Future<JsonNode>>();for(var step:steps)futures.add(pool.submit(()->versions.commit(actor(),step,output,etag(b))));var numbers=new TreeSet<Integer>();for(var f:futures)numbers.add(f.get().path("versionNo").asInt());assertEquals(new TreeSet<>(List.of(2,3,4,5)),numbers);}
        assertEquals(5,count(b));assertEquals(head(b),head(current(c,b)));
    }
    @Test void actualSecondOwnerCannotReadDiffReplayOrDisposeAndCsrfIsRequired()throws Exception {
        var c=signed();var a=tracked(c);var p=proposal(a);String user="t07-other-"+UUID.randomUUID();UUID other=UUID.randomUUID();
        sql("INSERT INTO editorial.app_user(id,username,display_name,actor_type,password_hash) SELECT '"+other+"','"+user+"','Other','OWNER',password_hash FROM editorial.app_user WHERE bootstrap_key='OWNER'");
        var d=new Client();var login=d.call("POST","/api/v1/auth/login",JSON.writeValueAsString(Map.of("username",user,"password",System.getenv("INITIAL_OWNER_PASSWORD"))),Map.of("Origin","http://localhost:3000"));d.csrf=ok(login,200).path("csrfToken").asText();
        for(String route:List.of(path(a)+"/versions",path(a)+"/versions/"+head(a),path(a)+"/diff?from="+head(a)+"&to="+head(a),path(a)+"/proposals"))error(d.get(route),404,"NOT_FOUND");
        String reject="/api/v1/proposals/"+p.path("meta").path("id").asText()+"/reject",key=UUID.randomUUID().toString();var reason=JSON.createObjectNode().put("reason","declined");ok(c.write("POST",reject,reason,key,null),200);error(d.write("POST",reject,reason,key,null),404,"NOT_FOUND");
        assertEquals(403,c.call("POST",path(a)+"/versions",edit(a).toString(),Map.of("Origin","http://localhost:3000")).statusCode());
        assertEquals(2,count(a));
    }
    @Test void proposalCursorFiltersAndSameArticleForeignKeys()throws Exception {
        var c=signed();var a=tracked(c);var b=tracked(c);var p=proposal(a);proposal(a);
        var page=ok(c.get(path(a)+"/proposals?status=PENDING&limit=1"),200);String cursor=page.path("nextCursor").asText();assertFalse(cursor.equals("null"));
        assertEquals(1,ok(c.get(path(a)+"/proposals?status=PENDING&limit=1&cursor="+cursor),200).path("items").size());
        error(c.get(path(a)+"/proposals?status=REJECTED&cursor="+cursor),422,"INVALID_CURSOR");
        error(c.get(path(b)+"/proposals?status=PENDING&cursor="+cursor),422,"INVALID_CURSOR");
        try(var conn=admin()) {conn.setAutoCommit(false);try(var stmt=conn.createStatement()) {
            // Disable only the proposal semantic trigger in this rolled-back transaction to exercise its composite FK independently.
            stmt.execute("ALTER TABLE editorial.change_proposal DISABLE TRIGGER proposal_guard");
            var error=assertThrows(java.sql.SQLException.class,()->stmt.execute("UPDATE editorial.change_proposal SET base_version_id='"+head(b)+"' WHERE id='"+p.path("meta").path("id").asText()+"'"));assertEquals("23503",error.getSQLState());conn.rollback();
        }}
        assertThrows(org.springframework.dao.DataAccessException.class,()->db.update("UPDATE editorial.article_version SET content_hash=? WHERE article_id=?","f".repeat(64),articleId(a)));
    }
    @Test void executionCompletionAndStageAuditFailureLeaveNoPartialBusinessRows()throws Exception {
        var c=signed();var a=tracked(c);var o=output(a);var step=execution(a,o,false);participants.failure="complete";
        assertEquals("TEST_EXECUTION_FAILURE",assertThrows(PublicFailure.class,()->versions.commit(actor(),step,o,etag(a))).code());assertEquals(1,count(a));assertEquals(head(a),head(current(c,a)));assertNull(db.queryForObject("SELECT result_id FROM editorial.t07_test_execution WHERE id=?",UUID.class,uuid(step.path("stepExecutionId").asText())));
        participants.failure="";sql("CREATE FUNCTION editorial.t07_stage_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'injected'; END $$; CREATE TRIGGER t07_stage_fail BEFORE INSERT ON editorial.audit_log FOR EACH ROW WHEN (NEW.action='OBJECT_STAGED') EXECUTE FUNCTION editorial.t07_stage_fail()");
        try {error(c.write("POST",path(a)+"/versions",edit(a),UUID.randomUUID().toString(),etag(a)),503,"AUDIT_WRITE_FAILED");assertEquals(1,count(a));assertEquals(head(a),head(current(c,a)));}
        finally {sql("DROP TRIGGER t07_stage_fail ON editorial.audit_log; DROP FUNCTION editorial.t07_stage_fail()");}
    }
    @Test void realSkillSwitchDoesNotRewriteOldAiExecutionSnapshot()throws Exception {
        var c=signed();var a=tracked(c);var o=output(a);var step=execution(a,o,false);
        String oldStyle=db.queryForObject("SELECT style_snapshot::text FROM editorial.article_job WHERE id=?",String.class,articleId(a));
        UUID newSkill;
        try(var trace=TraceContext.open(UUID.randomUUID())) {
            var principal=new com.example.editorial.identity.SessionIdentity(owner(),"Owner",java.time.Instant.now());
            org.springframework.security.core.context.SecurityContextHolder.getContext().setAuthentication(org.springframework.security.authentication.UsernamePasswordAuthenticationToken.authenticated(principal,null,List.of(new org.springframework.security.core.authority.SimpleGrantedAuthority("ROLE_OWNER"))));
            var human=ActorContext.current();var current=skills.read(human,skill());var tx=new TransactionTemplate(manager);
            var draft=tx.execute(s->skillService.createVersion(human,current.skillId(),current.id(),new com.example.editorial.editorial.skill.SkillConfig(current.config())));
            tx.execute(s->skillService.publish(human,draft.id(),"T07 execution snapshot test"));newSkill=draft.id();
        }finally{org.springframework.security.core.context.SecurityContextHolder.clearContext();}
        ok(c.write("PATCH",path(a),JSON.createObjectNode().put("skillVersionId",newSkill.toString()),UUID.randomUUID().toString(),etag(a)),200);
        assertNotEquals(oldStyle,db.queryForObject("SELECT style_snapshot::text FROM editorial.article_job WHERE id=?",String.class,articleId(a)));
        var late=versions.commit(actor(),step,o,etag(a));assertTrue(late.path("meta").path("stale").asBoolean());assertEquals(oldStyle,db.queryForObject("SELECT style_snapshot::text FROM editorial.article_version WHERE id=?",String.class,uuid(late.path("meta").path("id").asText())));assertEquals(step.path("inputHash"),late.path("meta").path("inputHash"));
    }
    @Test void splitMergeAndInvalidMappingAreVerifiedThroughHttp()throws Exception {
        var c=signed();var a=tracked(c);var edit=edit(a);var blocks=(ArrayNode)edit.path("contentAst").path("blocks");var old=(ObjectNode)blocks.get(0);String from=old.path("blockId").asText();
        old.put("blockId",UUID.randomUUID().toString()).put("text","😀"+"字".repeat(50));var second=old.deepCopy().put("blockId",UUID.randomUUID().toString());blocks.add(second);
        error(c.write("POST",path(a)+"/versions",edit,UUID.randomUUID().toString(),etag(a)),422,"BLOCK_MAPPING_REQUIRED");assertEquals(1,count(a));
        var mapping=JSON.createObjectNode().put("reason","SPLIT");mapping.putArray("fromBlockIds").add(from);mapping.putArray("toBlockIds").add(old.path("blockId")).add(second.path("blockId"));((ArrayNode)edit.path("blockMappings")).add(mapping);
        var split=ok(c.write("POST",path(a)+"/versions",edit,UUID.randomUUID().toString(),etag(a)),201);assertEquals(mapping,split.path("blockMappings").get(0));
        var now=current(c,a);var merge=edit(now);var merged=(ObjectNode)merge.path("contentAst").path("blocks").get(0);String id1=merged.path("blockId").asText();merged.put("blockId",UUID.randomUUID().toString()).put("text","😀"+"字".repeat(110));((ArrayNode)merge.path("contentAst").path("blocks")).remove(1);
        var m=JSON.createObjectNode().put("reason","MERGE");m.putArray("fromBlockIds").add(id1).add(second.path("blockId"));m.putArray("toBlockIds").add(merged.path("blockId"));((ArrayNode)merge.path("blockMappings")).add(m);
        var result=ok(c.write("POST",path(a)+"/versions",merge,UUID.randomUUID().toString(),etag(now)),201);assertEquals(3,result.path("versionNo").asInt());
        var diff=versions.diff(actor(),articleId(a),head(a),uuid(result.path("meta").path("id").asText()));assertEquals("ADD",diff.path("blocks").get(2).path("kind").asText());assertEquals("DELETE",diff.path("blocks").get(3).path("kind").asText());
    }
}

package com.example.editorial.article.job;

import static org.junit.jupiter.api.Assertions.*;
import com.example.editorial.EditorialApplication;
import com.example.editorial.article.ast.ArticleAst;
import com.example.editorial.shared.*;
import com.example.editorial.storage.*;
import com.example.editorial.editorial.skill.SkillSnapshotPort;
import com.example.editorial.editorial.skill.JsonSchema;
import com.example.editorial.audit.AuditSink;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.net.*;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.sql.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import static com.example.editorial.article.ast.ArticleAst.*;

@SpringBootTest(classes=EditorialApplication.class,webEnvironment=SpringBootTest.WebEnvironment.RANDOM_PORT)
@EnabledIfEnvironmentVariable(named="T06_REAL_PG",matches="true")
class T06PostgresTest {
    @LocalServerPort int port;
    @Autowired JdbcTemplate db;
    @Autowired ArticleService articles;
    @Autowired PlatformTransactionManager manager;
    @Autowired ObjectStore store;
    @Autowired StorageBackend backend;
    @Autowired SkillSnapshotPort skills;
    @Autowired com.example.editorial.editorial.skill.SkillService skillService;
    @Autowired JsonSchema schema;
    @Autowired AuditSink audit;
    @Autowired Idempotency idem;
    UUID owner(){return db.queryForObject("SELECT id FROM editorial.app_user WHERE bootstrap_key='OWNER'",UUID.class);}
    UUID skill(){return db.queryForObject("SELECT id FROM editorial.editorial_skill_version WHERE status='PUBLISHED' LIMIT 1",UUID.class);}
    ActorContext actor(){return ActorContext.forWorker(owner(),owner(),UUID.randomUUID());}
    Connection admin()throws Exception {return DriverManager.getConnection(System.getenv("DB_URL"),"editorial_admin",System.getenv("T06_ADMIN_PASSWORD"));}
    void sql(String sql)throws Exception {try(var c=admin();var s=c.createStatement()){s.execute(sql);}}
    @BeforeEach void clearLoginRate()throws Exception {sql("DELETE FROM editorial.audit_log WHERE action='AUTH_ATTEMPT'");}
    class Client {
        CookieManager cookies=new CookieManager(null,CookiePolicy.ACCEPT_ALL);
        HttpClient http=HttpClient.newBuilder().cookieHandler(cookies).build(); String csrf;
        HttpResponse<String> call(String method,String path,String body,Map<String,String> headers)throws Exception {
            var b=HttpRequest.newBuilder(URI.create("http://127.0.0.1:"+port+path)).method(method,body==null?HttpRequest.BodyPublishers.noBody():HttpRequest.BodyPublishers.ofString(body));
            if(body!=null)b.header("Content-Type","application/json");headers.forEach(b::header);return http.send(b.build(),HttpResponse.BodyHandlers.ofString());
        }
        HttpResponse<String> write(String method,String path,JsonNode body,String key,String etag)throws Exception {
            byte[] bytes=CanonicalRequest.canonical(body);var h=new HashMap<>(Map.of("Origin","http://localhost:3000","X-CSRF-Token",csrf,"Idempotency-Key",key,"X-Request-Hash",CanonicalRequest.hash(method,path,bytes)));
            if(etag!=null)h.put("If-Match",etag);return call(method,path,new String(bytes,StandardCharsets.UTF_8),h);
        }
        HttpResponse<String> get(String path)throws Exception{return call("GET",path,null,Map.of());}
    }
    Client signed()throws Exception {
        var c=new Client();var r=c.call("POST","/api/v1/auth/login",JSON.writeValueAsString(Map.of("username",System.getenv("INITIAL_OWNER_USERNAME"),"password",System.getenv("INITIAL_OWNER_PASSWORD"))),Map.of("Origin","http://localhost:3000"));
        assertEquals(200,r.statusCode(),r.body()); c.csrf=JSON.readTree(r.body()).path("csrfToken").asText(); return c;
    }
    ObjectNode request(String basis) {
        var r=JSON.createObjectNode().put("skillVersionId",skill().toString()).put("targetLength",2500).put("rightsBasis",basis);
        r.set("original",JSON.createObjectNode().put("format","TEXT").put("title","原文标题").put("content","原文测试材料".repeat(500)));
        r.set("budget",JSON.createObjectNode().put("limit","10.000000").put("currency","USD"));return r;
    }
    JsonNode create(Client c)throws Exception {var r=c.write("POST","/api/v1/articles",request("OWNED"),UUID.randomUUID().toString(),null);assertEquals(201,r.statusCode(),r.body());return JSON.readTree(r.body());}
    String path(JsonNode a){return "/api/v1/articles/"+a.path("job").path("id").asText();}
    String etag(JsonNode a){return "\"job-"+a.path("job").path("lockVersion").asLong()+"\"";}
    void error(HttpResponse<String> r,int status,String code)throws Exception {assertEquals(status,r.statusCode(),r.body());assertEquals(code,JSON.readTree(r.body()).path("code").asText());assertFalse(r.body().contains("原文测试材料"));assertFalse(r.body().contains("Exception"));assertFalse(r.body().contains(System.getenv("INITIAL_OWNER_PASSWORD")));}
    @Test void atomicCreateAndConcurrentReplay()throws Exception {
        var c=signed();String key=UUID.randomUUID().toString(); var input=request("OWNED");
        try(var pool=Executors.newFixedThreadPool(4)) {
            var futures=new ArrayList<Future<HttpResponse<String>>>();for(int i=0;i<4;i++) futures.add(pool.submit(()->c.write("POST","/api/v1/articles",input,key,null)));
            var first=futures.getFirst().get();assertEquals(201,first.statusCode(),first.body());
            for(var f:futures) {var r=f.get();assertEquals(first.body(),r.body());assertEquals(first.headers().firstValue("ETag"),r.headers().firstValue("ETag"));}
            var a=JSON.readTree(first.body()); UUID id=uuid(a.path("job").path("id").asText());
            assertEquals(1,db.queryForObject("SELECT count(*) FROM editorial.article_version WHERE article_id=?",Integer.class,id));
            assertEquals(1,db.queryForObject("SELECT count(*) FROM editorial.article_job WHERE id=?",Integer.class,id));
            var doc=articles.readVersion(actor(),id,uuid(a.path("job").path("currentVersionId").asText()));
            java.nio.file.Files.writeString(java.nio.file.Path.of(System.getProperty("t06.root"),"docs/execution/reviews/T06-round1/evidence/article-version-sample.json"),doc.toString());
            assertEquals(3000,ArticleAst.length(doc.path("plainText").asText()));assertEquals(doc,articles.readVersion(actor(),id,uuid(doc.path("meta").path("id").asText())));
            var ref=JSON.treeToValue(JSON.readTree(db.queryForObject("SELECT object_ref::text FROM editorial.article_version WHERE article_id=?",String.class,id)),ObjectRef.class);
            assertArrayEquals(CanonicalRequest.canonical(doc),backend.get(ref));assertEquals(ObjectStatus.COMMITTED,backend.head(ref).status());
            input.put("targetLength",3000);error(c.write("POST","/api/v1/articles",input,key,null),409,"IDEMPOTENCY_CONFLICT");
        }
    }
    @Test void fourRightsAndInputValidation()throws Exception {
        var c=signed(); for(String basis:List.of("OWNED","AUTHORIZED","REFERENCE_ONLY","UNKNOWN")) {
            var r=c.write("POST","/api/v1/articles",request(basis),UUID.randomUUID().toString(),null);assertEquals(201,r.statusCode(),r.body());assertEquals(basis,JSON.readTree(r.body()).path("rightsSnapshot").path("basis").asText());
        }
        var req=request("OWNED");req.remove("rightsBasis");error(c.write("POST","/api/v1/articles",req,UUID.randomUUID().toString(),null),422,"VALIDATION_FAILED");
        req=request("OWNED");req.put("ownerId",owner().toString());error(c.write("POST","/api/v1/articles",req,UUID.randomUUID().toString(),null),422,"VALIDATION_FAILED");
        req=request("OWNED");req.putArray("rightsEvidenceIds").add(UUID.randomUUID().toString());error(c.write("POST","/api/v1/articles",req,UUID.randomUUID().toString(),null),503,"RIGHTS_EVIDENCE_NOT_READY");
        for(int n:new int[]{99,100,30000,30001}) {req=request("OWNED");((ObjectNode)req.path("original")).put("content","😀".repeat(n));var r=c.write("POST","/api/v1/articles",req,UUID.randomUUID().toString(),null);assertEquals(n==100||n==30000?201:422,r.statusCode(),r.body());}
    }
    @Test void schemaSkillOwnershipAndSnapshotImmutability()throws Exception {
        var c=signed();var input=request("OWNED");input.put("skillVersionId",UUID.randomUUID().toString());assertEquals(404,c.write("POST","/api/v1/articles",input,UUID.randomUUID().toString(),null).statusCode());
        var a=create(c);UUID id=uuid(a.path("job").path("id").asText());var snapshot=db.queryForObject("SELECT style_snapshot::text FROM editorial.article_job WHERE id=?",String.class,id);
        assertTrue(snapshot.contains("systemTemplate"));assertTrue(snapshot.contains("policySnapshots"));
        UUID sid=skill();sql("UPDATE editorial.editorial_skill_version SET status='RETIRED' WHERE id='"+sid+"'");
        try {assertEquals(snapshot,db.queryForObject("SELECT style_snapshot::text FROM editorial.article_job WHERE id=?",String.class,id));input=requestWithSkill(sid);assertEquals(409,c.write("POST","/api/v1/articles",input,UUID.randomUUID().toString(),null).statusCode());}
        finally {sql("ALTER TABLE editorial.editorial_skill_version DISABLE TRIGGER USER; UPDATE editorial.editorial_skill_version SET status='PUBLISHED' WHERE id='"+sid+"'; ALTER TABLE editorial.editorial_skill_version ENABLE TRIGGER USER");}
    }
    ObjectNode requestWithSkill(UUID id){var r=requestFallback();r.put("skillVersionId",id.toString());return r;}
    ObjectNode requestFallback(){var r=JSON.createObjectNode().put("targetLength",2500).put("rightsBasis","OWNED");r.set("original",JSON.createObjectNode().put("format","TEXT").put("title","test").put("content","x".repeat(100)));r.set("budget",JSON.createObjectNode().put("limit","10.000000").put("currency","USD"));return r;}
    @Test void etagReplayArchiveBudgetAndClone()throws Exception {
        var c=signed();var a=create(c);var patch=JSON.createObjectNode().put("name","展示名称").put("archived",true);String key=UUID.randomUUID().toString();
        error(c.write("PATCH",path(a),patch,key,null),428,"IF_MATCH_REQUIRED");
        var r=c.write("PATCH",path(a),patch,key,etag(a));assertEquals(200,r.statusCode(),r.body());assertEquals(r.body(),c.write("PATCH",path(a),patch,key,etag(a)).body());
        error(c.write("PATCH",path(a),patch,UUID.randomUUID().toString(),etag(a)),412,"ETAG_MISMATCH");
        a=JSON.readTree(r.body());assertEquals("展示名称",a.path("job").path("name").asText());assertTrue(a.path("job").path("archived").asBoolean());
        var p=JSON.createObjectNode().put("archived",false);p.set("budget",JSON.createObjectNode().put("limit","11.000000").put("currency","USD"));
        r=c.write("PATCH",path(a),p,UUID.randomUUID().toString(),etag(a));assertEquals(200,r.statusCode(),r.body());assertEquals(a.path("artifacts"),JSON.readTree(r.body()).path("artifacts"));
        var clone=JSON.createObjectNode().put("fromVersionId",a.path("job").path("currentVersionId").asText()).put("skillVersionId",skill().toString());
        r=c.write("POST",path(a)+"/clone",clone,UUID.randomUUID().toString(),null);assertEquals(201,r.statusCode(),r.body());var copied=JSON.readTree(r.body());
        assertEquals("UNKNOWN",copied.path("rightsSnapshot").path("basis").asText());assertEquals("CREATED",copied.path("job").path("status").asText());assertEquals("0.000000",copied.path("job").path("spentAmount").asText());assertNotEquals(a.path("job").path("id"),copied.path("job").path("id"));
        var original=articles.readVersion(actor(),uuid(a.path("job").path("id").asText()),uuid(a.path("job").path("currentVersionId").asText()));
        var copy=articles.readVersion(actor(),uuid(copied.path("job").path("id").asText()),uuid(copied.path("job").path("currentVersionId").asText()));
        assertEquals("原文标题",original.path("title").asText());assertEquals(original.path("plainText"),copy.path("plainText"));assertNotEquals(original.path("contentAst"),copy.path("contentAst"));
    }
    @Test void unreadyGenerationRightsAndDeletionNeverSucceed()throws Exception {
        var c=signed();var a=create(c);String before=c.get(path(a)).body();
        var p=JSON.createObjectNode().put("targetLength",3000);error(c.write("PATCH",path(a),p,UUID.randomUUID().toString(),etag(a)),503,"FEATURE_NOT_READY");assertEquals(before,c.get(path(a)).body());
        var u=JSON.createObjectNode().put("versionId",UUID.randomUUID().toString()).put("contentHash",a.path("rightsSnapshot").path("contentHash").asText()).put("basis","OWNED").put("notes","补充依据");u.putArray("evidenceIds");p=JSON.createObjectNode();p.set("rightsUpdate",u);
        error(c.write("PATCH",path(a),p,UUID.randomUUID().toString(),etag(a)),409,"RIGHTS_VERSION_MISMATCH");
        u.put("versionId",a.path("job").path("currentVersionId").asText());error(c.write("PATCH",path(a),p,UUID.randomUUID().toString(),etag(a)),503,"FEATURE_NOT_READY");assertEquals(before,c.get(path(a)).body());
        error(c.get(path(a)+"/deletion-impact"),503,"FEATURE_NOT_READY");p=JSON.createObjectNode().put("impactHash","0".repeat(64)).put("reason","删除测试");
        String key=UUID.randomUUID().toString();for(int i=0;i<2;i++)error(c.write("POST",path(a)+"/deletion",p,key,etag(a)),503,"FEATURE_NOT_READY");assertEquals(before,c.get(path(a)).body());
    }
    @Test void databaseConstraintsAndOriginalPrivileges()throws Exception {
        var c=signed();var a=create(c);var b=create(c);String id=a.path("job").path("id").asText(),vid=a.path("job").path("currentVersionId").asText();
        assertThrows(org.springframework.dao.DataAccessException.class,()->db.update("UPDATE editorial.article_version SET content_hash=? WHERE id=?","0".repeat(64),uuid(vid)));
        assertThrows(org.springframework.dao.DataAccessException.class,()->db.update("DELETE FROM editorial.article_version WHERE id=?",uuid(vid)));
        for(String assignment:List.of("original_version_id=NULL","current_version_id=NULL","current_version_id='"+b.path("job").path("currentVersionId").asText()+"'")) {
            try(var conn=admin()) {conn.setAutoCommit(false);try(var s=conn.createStatement()) {s.execute("UPDATE editorial.article_job SET "+assignment+",lock_version=lock_version+1 WHERE id='"+id+"'");assertThrows(SQLException.class,conn::commit);conn.rollback();} catch(SQLException e){conn.rollback();assertTrue(e.getMessage().contains("original pointer immutable"));}}
        }
        assertEquals(vid,db.queryForObject("SELECT original_version_id::text FROM editorial.article_job WHERE id=?",String.class,uuid(id)));
    }
    @Test void cursorAndCrossOwnerConcealment()throws Exception {
        var c=signed();create(c);create(c);var first=JSON.readTree(c.get("/api/v1/articles?limit=1").body());String cursor=first.path("nextCursor").asText();assertFalse(cursor.isBlank());
        var next=c.get("/api/v1/articles?limit=1&cursor="+cursor);assertEquals(200,next.statusCode(),next.body());assertNotEquals(first.path("items").get(0).path("id"),JSON.readTree(next.body()).path("items").get(0).path("id"));
        error(c.get("/api/v1/articles?cursor="+cursor+"x"),422,"INVALID_CURSOR");error(c.get("/api/v1/articles?status=CREATED&cursor="+cursor),422,"INVALID_CURSOR");
        var foreign=ActorContext.forWorker(owner(),UUID.randomUUID(),UUID.randomUUID());UUID id=uuid(first.path("items").get(0).path("id").asText());
        var denied=assertThrows(PublicFailure.class,()->articles.job(foreign,id,false));assertEquals(404,denied.status());
        assertEquals(0,articles.list(foreign,null,null,null,20).path("items").size());assertThrows(PublicFailure.class,()->articles.list(foreign,null,null,cursor,20));
        byte[] body=CanonicalRequest.canonical(JSON.createObjectNode().put("name","x"));
        var replay=assertThrows(PublicFailure.class,()->idem.execute(foreign,"PATCH","/api/v1/articles/"+id,null,UUID.randomUUID().toString(),CanonicalRequest.hash("PATCH","/api/v1/articles/"+id,body),body,()->articles.job(foreign,id,true),()->{},Idempotency.Response::empty));assertEquals(404,replay.status());
    }
    @Test void auditIdempotencyAndObjectCommitFailureRollBack()throws Exception {
        var c=signed();
        for(String trigger:List.of("audit_log","idempotency_record")) {
            int count=db.queryForObject("SELECT count(*) FROM editorial.article_job",Integer.class);
            sql("CREATE FUNCTION editorial.t06_test_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'test injected'; END $$; CREATE TRIGGER t06_fail BEFORE INSERT ON editorial."+trigger+" FOR EACH ROW EXECUTE FUNCTION editorial.t06_test_fail()");
            try {var r=c.write("POST","/api/v1/articles",request("OWNED"),UUID.randomUUID().toString(),null);assertEquals(503,r.statusCode(),r.body());assertEquals(count,db.queryForObject("SELECT count(*) FROM editorial.article_job",Integer.class));}
            finally {sql("DROP TRIGGER t06_fail ON editorial."+trigger+"; DROP FUNCTION editorial.t06_test_fail()");}
        }
    }
    ActorContext human() {
        var principal=new com.example.editorial.identity.SessionIdentity(owner(),"Owner",java.time.Instant.now());
        org.springframework.security.core.context.SecurityContextHolder.getContext().setAuthentication(
            org.springframework.security.authentication.UsernamePasswordAuthenticationToken.authenticated(principal,null,List.of(new org.springframework.security.core.authority.SimpleGrantedAuthority("ROLE_OWNER"))));
        return ActorContext.current();
    }
    ArticleService participant(ArticlePorts.Changes change,boolean failObjectCommit) {
        ArticlePorts.Objects objects=new ArticlePorts.Objects() {
            public JsonNode stage(ActorContext a,byte[] b) {return JSON.valueToTree(store.stage(a,b,CanonicalRequest.digest(b),b.length));}
            public void commit(ActorContext a,JsonNode o,Ownership.ArtifactRef ref) {
                if(failObjectCommit) throw new PublicFailure(503,"TEST_OBJECT_COMMIT_FAILED");
                store.commitReference(a,new ObjectRef(o.path("key").asText(),o.path("hash").asText(),o.path("size").asLong(),o.path("mime").asText(),o.path("encrypted").asBoolean()),ref);
            }
        };
        return new ArticleService(db,(a,id)->{var out=JSON.createObjectNode();out.set("skill",JSON.valueToTree(skills.read(a,id)));return out;},objects,
            (a,action,article,entity,before,after)->audit.append(a,new AuditSink.Event(action,article,"ARTICLE",entity,before,after)),
            ArticlePorts.unavailableEvidence(),change,(n,d)->schema.validate(n,d),System.getenv("AUDIT_CURSOR_KEY"));
    }
    @Test void changesParticipantAndRightsHistoryAreAtomic()throws Exception {
        var c=signed();var a=create(c);UUID id=uuid(a.path("job").path("id").asText());String oldStyle=db.queryForObject("SELECT style_snapshot::text FROM editorial.article_version WHERE article_id=?",String.class,id);
        // Explicit T10/T11 stand-in: persists ONLY an audit marker in the caller's transaction, not a real generation/fence.
        var participant=participant((actor,article,before,after,g,r)-> {
            assertTrue(org.springframework.transaction.support.TransactionSynchronizationManager.isActualTransactionActive());
            audit.append(actor,new AuditSink.Event("TEST_FENCE_PARTICIPANT",article,"ARTICLE",article,null,null));
        },false);
        try(var trace=TraceContext.open(UUID.randomUUID())) {
            var actor=human();var tx=new TransactionTemplate(manager);var update=JSON.createObjectNode().put("targetLength",3000);
            String baseline=c.get(path(a)).body();
            assertThrows(IllegalStateException.class,()->tx.executeWithoutResult(s->{participant.patch(actor,id,update);throw new IllegalStateException("test rollback");}));
            assertEquals(baseline,c.get(path(a)).body());assertEquals(0,db.queryForObject("SELECT count(*) FROM editorial.audit_log WHERE article_id=? AND action='TEST_FENCE_PARTICIPANT'",Integer.class,id));
            tx.executeWithoutResult(s->participant.patch(actor,id,update));assertEquals(3000,articles.job(actor,id,false).path("targetLength").asInt());
            assertEquals(oldStyle,db.queryForObject("SELECT style_snapshot::text FROM editorial.article_version WHERE article_id=?",String.class,id));
            var originalRights=JSON.readTree(db.queryForObject("SELECT original_rights_basis::text FROM editorial.article_job WHERE id=?",String.class,id)).get(0);
            var u=JSON.createObjectNode().put("versionId",a.path("job").path("currentVersionId").asText()).put("contentHash",a.path("rightsSnapshot").path("contentHash").asText()).put("basis","AUTHORIZED").put("notes","补充材料待下游核验");u.putArray("evidenceIds");var patch=JSON.createObjectNode();patch.set("rightsUpdate",u);
            tx.executeWithoutResult(s->participant.patch(actor,id,patch));
            var history=JSON.readTree(db.queryForObject("SELECT original_rights_basis::text FROM editorial.article_job WHERE id=?",String.class,id));assertEquals(2,history.size());assertEquals(originalRights,history.get(0));assertEquals("AUTHORIZED",history.get(1).path("basis").asText());
            assertEquals("NEEDS_REVISION",articles.job(actor,id,false).path("status").asText());
            assertThrows(org.springframework.dao.DataAccessException.class,()->db.update("UPDATE editorial.article_job SET original_rights_basis='[]',lock_version=lock_version+1 WHERE id=?",id));
        } finally {org.springframework.security.core.context.SecurityContextHolder.clearContext();}
    }
    @Test void realStagingAndReferenceFailuresLeaveNoBusinessRows()throws Exception {
        var participant=participant(ArticlePorts.unavailableChanges(),true);
        try(var trace=TraceContext.open(UUID.randomUUID())) {
            var a=human();var input=request("OWNED");var prepared=participant.prepareCreate(a,input);String key=prepared.object().path("key").asText();
            var tx=new TransactionTemplate(manager);
            assertThrows(PublicFailure.class,()->tx.executeWithoutResult(s->participant.create(a,input,prepared)));
            assertEquals(0,db.queryForObject("SELECT count(*) FROM editorial.article_job WHERE id=?",Integer.class,prepared.article()));
            assertEquals(0,db.queryForObject("SELECT count(*) FROM editorial.article_version WHERE article_id=?",Integer.class,prepared.article()));
            assertNull(articles.objectOwner(key));assertEquals(ObjectStatus.STAGING,backend.head(JSON.treeToValue(prepared.object(),ObjectRef.class)).status());
        } finally {org.springframework.security.core.context.SecurityContextHolder.clearContext();}
    }
    @Test void versionAppendAndHeadAreControlledAndDoNotInheritRights()throws Exception {
        var c=signed();var a=create(c);UUID article=uuid(a.path("job").path("id").asText()),base=uuid(a.path("job").path("currentVersionId").asText());
        try(var trace=TraceContext.open(UUID.randomUUID())) {
            var actor=human();var ast=ArticleAst.parse("TEXT","新内容".repeat(100));
            var p=articles.prepareVersion(actor,article,base,etag(a),"MANUAL","USER","新标题",null,ast,"T07 port test",JSON.createArrayNode(),null,"a".repeat(64),(k,id)->{throw new PublicFailure(404,"NOT_FOUND");});
            var tx=new TransactionTemplate(manager);UUID version=tx.execute(s->articles.appendVersion(actor,p));
            assertEquals(base.toString(),articles.job(actor,article,false).path("currentVersionId").asText());
            assertThrows(PublicFailure.class,()->tx.executeWithoutResult(s->articles.moveHead(actor,article,version,etag(a))));
            var participant=participant((ac,id,b,n,g,r)->audit.append(ac,new AuditSink.Event("TEST_HEAD_INVALIDATION",id,"ARTICLE",id,null,null)),false);
            tx.executeWithoutResult(s->participant.moveHead(actor,article,version,etag(a)));
            var current=articles.artifact(actor,article);assertEquals(version.toString(),current.path("job").path("currentVersionId").asText());assertEquals("UNKNOWN",current.path("rightsSnapshot").path("basis").asText());
            assertEquals(base.toString(),current.path("job").path("originalVersionId").asText());
            assertThrows(PublicFailure.class,()->tx.executeWithoutResult(s->articles.appendVersion(actor,p)));
            var foreign=create(c);var denied=assertThrows(PublicFailure.class,()->articles.readVersion(actor,article,uuid(foreign.path("job").path("currentVersionId").asText())));assertEquals(404,denied.status());
        } finally {org.springframework.security.core.context.SecurityContextHolder.clearContext();}
    }
    @Test void cancelledJobCannotRestartButMayClone()throws Exception {
        var c=signed();var a=create(c);UUID id=uuid(a.path("job").path("id").asText());
        sql("UPDATE editorial.article_job SET status='CANCELLED',lock_version=2,summary=jsonb_set(jsonb_set(summary,'{status}','\"CANCELLED\"'),'{lockVersion}','2') WHERE id='"+id+"'");
        a=JSON.readTree(c.get(path(a)).body());error(c.write("PATCH",path(a),JSON.createObjectNode().put("targetLength",3000),UUID.randomUUID().toString(),etag(a)),409,"CANCELLED");
        var p=JSON.createObjectNode().put("fromVersionId",a.path("job").path("currentVersionId").asText()).put("skillVersionId",skill().toString());assertEquals(201,c.write("POST",path(a)+"/clone",p,UUID.randomUUID().toString(),null).statusCode());
        assertThrows(org.springframework.dao.DataAccessException.class,()->db.update("UPDATE editorial.article_job SET status='CREATED',lock_version=3 WHERE id=?",id));
    }
    @Test void actualUtf8ByteLimitIsIndependentOfJsonEnvelope()throws Exception {
        var c=signed();var r=request("UNKNOWN");String content="x".repeat(100)+"\n"+" ".repeat(1048576-101);((ObjectNode)r.path("original")).put("content",content);
        var good=c.write("POST","/api/v1/articles",r,UUID.randomUUID().toString(),null);assertEquals(201,good.statusCode(),good.body());
        // Four-byte emoji crosses actual byte cap while remaining under schema's code point cap.
        ((ObjectNode)r.path("original")).put("content","😀"+content.substring(2));error(c.write("POST","/api/v1/articles",r,UUID.randomUUID().toString(),null),422,"TEXT_TOO_LARGE");
        java.nio.file.Files.writeString(java.nio.file.Path.of(System.getProperty("t06.root"),"docs/execution/reviews/T06-round1/evidence/article-artifact-sample.json"),good.body());
    }
    @Test void existingOtherOwnerCannotReplayReadOrUseSkill()throws Exception {
        var c=signed();var a=create(c);String user="other-"+UUID.randomUUID();UUID other=UUID.randomUUID();
        sql("INSERT INTO editorial.app_user(id,username,display_name,actor_type,password_hash) SELECT '"+other+"','"+user+"','Other','OWNER',password_hash FROM editorial.app_user WHERE bootstrap_key='OWNER'");
        var d=new Client();var login=d.call("POST","/api/v1/auth/login",JSON.writeValueAsString(Map.of("username",user,"password",System.getenv("INITIAL_OWNER_PASSWORD"))),Map.of("Origin","http://localhost:3000"));assertEquals(200,login.statusCode());d.csrf=JSON.readTree(login.body()).path("csrfToken").asText();
        String key=UUID.randomUUID().toString();var patch=JSON.createObjectNode().put("name","Private");assertEquals(200,c.write("PATCH",path(a),patch,key,etag(a)).statusCode());
        error(d.write("PATCH",path(a),patch,key,etag(a)),404,"NOT_FOUND");error(d.get(path(a)),404,"NOT_FOUND");
        assertEquals(0,JSON.readTree(d.get("/api/v1/articles").body()).path("items").size());
        assertEquals(404,d.write("POST","/api/v1/articles",request("OWNED"),UUID.randomUUID().toString(),null).statusCode());
    }
    @Test void insertCommitRequiresPointersAndOriginalKind()throws Exception {
        var c=signed();var a=create(c);String template=a.path("job").path("id").asText();
        for(boolean wrongKind:List.of(false,true)) {
            UUID article=UUID.randomUUID(),original=UUID.randomUUID(),draft=UUID.randomUUID();
            try(var conn=admin()) {conn.setAutoCommit(false);try(var s=conn.createStatement()) {
                s.execute("INSERT INTO editorial.article_job(id,owner_id,name,skill_version_id,target_length,budget_limit,currency,summary,style_snapshot,original_rights_basis,created_by,updated_by) SELECT '"+article+"',owner_id,name,skill_version_id,target_length,budget_limit,currency,jsonb_set(jsonb_set(jsonb_set(summary,'{id}',to_jsonb('"+article+"'::text)),'{originalVersionId}',to_jsonb('"+draft+"'::text)),'{currentVersionId}',to_jsonb('"+draft+"'::text)),style_snapshot,jsonb_build_array(jsonb_set(jsonb_set(original_rights_basis->0,'{articleId}',to_jsonb('"+article+"'::text)),'{versionId}',to_jsonb('"+draft+"'::text))),created_by,updated_by FROM editorial.article_job WHERE id='"+template+"'");
                if(wrongKind) {
                    for(int no=1;no<=2;no++) {
                        UUID version=no==1?original:draft;String kind=no==1?"ORIGINAL":"DRAFT";
                        String document="jsonb_set(jsonb_set(jsonb_set(jsonb_set(jsonb_set(document,'{meta,id}',to_jsonb('"+version+"'::text)),'{meta,versionId}',to_jsonb('"+version+"'::text)),'{meta,articleId}',to_jsonb('"+article+"'::text)),'{kind}',to_jsonb('"+kind+"'::text)),'{versionNo}',to_jsonb("+no+"))";
                        s.execute("INSERT INTO editorial.article_version(id,article_id,version_no,parent_version_id,kind,document,content_hash,input_hash,style_snapshot,object_ref,created_by) SELECT '"+version+"','"+article+"',"+no+","+(no==1?"NULL":"'"+original+"'::uuid")+",'"+kind+"',"+document+",content_hash,input_hash,style_snapshot,jsonb_set(object_ref,'{key}',to_jsonb('"+UUID.randomUUID()+"'::text)),created_by FROM editorial.article_version WHERE article_id='"+template+"'");
                    }
                    s.execute("UPDATE editorial.article_job SET original_version_id='"+draft+"',current_version_id='"+draft+"' WHERE id='"+article+"'");
                }
                var ex=assertThrows(SQLException.class,conn::commit);assertEquals("23514",ex.getSQLState());assertTrue(ex.getMessage().contains(wrongKind?"invalid original pointer":"incomplete article job"));conn.rollback();
            }}
            assertEquals(0,db.queryForObject("SELECT count(*) FROM editorial.article_job WHERE id=?",Integer.class,article));
        }
    }
    @Test void newSkillPublicationDoesNotChangeExistingArticleSnapshot()throws Exception {
        var c=signed();var a=create(c);UUID id=uuid(a.path("job").path("id").asText()),oldSkill=uuid(a.path("job").path("skillVersionId").asText());
        String oldStyle=db.queryForObject("SELECT style_snapshot::text FROM editorial.article_job WHERE id=?",String.class,id);
        try(var trace=TraceContext.open(UUID.randomUUID())) {
            var actor=human();var current=skills.read(actor,oldSkill);var tx=new TransactionTemplate(manager);
            var draft=tx.execute(s->skillService.createVersion(actor,current.skillId(),oldSkill,new com.example.editorial.editorial.skill.SkillConfig(current.config())));
            var input=requestWithSkill(draft.id());error(c.write("POST","/api/v1/articles",input,UUID.randomUUID().toString(),null),409,"SKILL_NOT_PUBLISHED");
            tx.execute(s->skillService.publish(actor,draft.id(),"New version for snapshot isolation test"));
            assertEquals(oldStyle,db.queryForObject("SELECT style_snapshot::text FROM editorial.article_job WHERE id=?",String.class,id));
            assertEquals(oldSkill.toString(),JSON.readTree(c.get(path(a)).body()).path("job").path("skillVersionId").asText());
            error(c.write("PATCH",path(a),JSON.createObjectNode().put("skillVersionId",draft.id().toString()),UUID.randomUUID().toString(),etag(a)),503,"FEATURE_NOT_READY");
            assertEquals(oldStyle,db.queryForObject("SELECT style_snapshot::text FROM editorial.article_job WHERE id=?",String.class,id));
        } finally {org.springframework.security.core.context.SecurityContextHolder.clearContext();}
    }
}

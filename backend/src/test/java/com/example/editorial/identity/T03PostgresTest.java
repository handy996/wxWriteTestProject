package com.example.editorial.identity;

import com.example.editorial.EditorialApplication;
import com.example.editorial.audit.*;
import com.example.editorial.shared.*;
import com.fasterxml.jackson.databind.*;
import jakarta.servlet.http.*;
import java.net.*;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.sql.*;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.*;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.context.annotation.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.bind.annotation.*;
import static org.junit.jupiter.api.Assertions.*;

/** Real TCP HTTP + servlet sessions + PostgreSQL. Only article metadata is a fixture. */
@SpringBootTest(classes=EditorialApplication.class,webEnvironment=SpringBootTest.WebEnvironment.RANDOM_PORT)
@Import(T03PostgresTest.Fixture.class)
@EnabledIfEnvironmentVariable(named="T03_REAL_PG",matches="true")
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class T03PostgresTest {
    static final String ORIGIN="http://localhost:3000";
    static final UUID ARTICLE=UUID.fromString("10000000-0000-4000-8000-000000000001"), OTHER=UUID.fromString("10000000-0000-4000-8000-000000000002"), FOREIGN=UUID.fromString("10000000-0000-4000-8000-000000000003");
    static final ObjectMapper JSON=new ObjectMapper();
    @LocalServerPort int port;
    @Autowired JdbcTemplate db;
    @Autowired IdentityService identity;
    @Autowired AuditSink audit;
    @Autowired Idempotency idem;
    @Autowired PlatformTransactionManager manager;
    @Autowired List<SecurityFilterChain> chains;
    @Autowired org.springframework.security.crypto.password.PasswordEncoder encoder;
    @Autowired Ownership ownership;
    UUID owner(){return db.queryForObject("SELECT id FROM editorial.app_user WHERE bootstrap_key='OWNER'",UUID.class);}
    UUID system(){return db.queryForObject("SELECT id FROM editorial.app_user WHERE bootstrap_key='SYSTEM'",UUID.class);}
    ActorContext worker(){return ActorContext.forWorker(system(),owner(),UUID.randomUUID());}
    String password(){return System.getenv("INITIAL_OWNER_PASSWORD");}
    String username(){return System.getenv("INITIAL_OWNER_USERNAME");}
    void admin(String sql)throws Exception {try(var c=DriverManager.getConnection(System.getenv("DB_URL"),"editorial_admin",System.getenv("T03_ADMIN_PASSWORD"));var s=c.createStatement()){s.execute(sql);}}
    @BeforeEach void clearRateWindow()throws Exception {admin("DELETE FROM editorial.audit_log WHERE action='AUTH_ATTEMPT'");}
    class Client {
        CookieManager cookies=new CookieManager(null,CookiePolicy.ACCEPT_ALL);
        HttpClient client=HttpClient.newBuilder().cookieHandler(cookies).build();
        String csrf;
        HttpResponse<String> call(String method,String path,String body,Map<String,String> headers)throws Exception {
            var r=HttpRequest.newBuilder(URI.create("http://127.0.0.1:"+port+path)).method(method,body==null?HttpRequest.BodyPublishers.noBody():HttpRequest.BodyPublishers.ofString(body));
            if(body!=null)r.header("Content-Type","application/json");headers.forEach(r::header);
            return client.send(r.build(),HttpResponse.BodyHandlers.ofString());
        }
        HttpResponse<String> login(String user,String pass)throws Exception {
            var r=call("POST","/api/v1/auth/login",JSON.writeValueAsString(Map.of("username",user,"password",pass)),Map.of("Origin",ORIGIN));
            if(r.statusCode()==200)csrf=JSON.readTree(r.body()).get("csrfToken").asText();return r;
        }
        HttpResponse<String> command(UUID article,String key,String body,String etag)throws Exception {
            String path="/api/v1/t03-test/command/"+article;
            Map<String,String> h=new HashMap<>(Map.of("Origin",ORIGIN,"X-CSRF-Token",csrf,"Idempotency-Key",key,"X-Request-Hash",CanonicalRequest.hash("POST",path,body.getBytes(StandardCharsets.UTF_8))));
            if(etag!=null)h.put("If-Match",etag);return call("POST",path,body,h);
        }
    }
    Client signed()throws Exception {var c=new Client();assertEquals(200,c.login(username(),password()).statusCode());return c;}
    void error(HttpResponse<String> r,int status)throws Exception {
        assertEquals(status,r.statusCode(),r.body());var n=JSON.readTree(r.body());
        assertEquals(Set.of("code","message","traceId","details","retryable"),new HashSet<String>(){{n.fieldNames().forEachRemaining(this::add);}});
        UUID.fromString(n.get("traceId").asText());assertEquals(r.headers().firstValue("X-Trace-Id").orElseThrow(),n.get("traceId").asText());
        assertTrue(n.get("details").isArray());assertFalse(r.body().contains(password()));assertFalse(r.body().contains("Exception"));
    }
    @Test @Order(1) void emptyInitializationAndRepeatNeverReset()throws Exception {
        assertEquals(1,chains.size());assertEquals(2,db.queryForObject("SELECT count(*) FROM editorial.app_user",Integer.class));
        String hash=db.queryForObject("SELECT password_hash FROM editorial.app_user WHERE bootstrap_key='OWNER'",String.class);
        assertNotEquals(password(),hash);assertTrue(encoder.matches(password(),hash));
        identity.initialize("ignored","ignored",UUID.randomUUID().toString());
        assertEquals(hash,db.queryForObject("SELECT password_hash FROM editorial.app_user WHERE bootstrap_key='OWNER'",String.class));
        assertEquals(200,signed().call("GET","/api/v1/me",null,Map.of()).statusCode());
    }
    @Test void passwordsDisabledAndSystem()throws Exception {
        error(new Client().login(username(),UUID.randomUUID().toString()),401);
        error(new Client().login("__system__",password()),401);
        admin("UPDATE editorial.app_user SET enabled=false WHERE bootstrap_key='OWNER'");
        try{error(new Client().login(username(),password()),401);}finally{admin("UPDATE editorial.app_user SET enabled=true WHERE bootstrap_key='OWNER'");}
    }
    @Test void limitUsesTcpPeerIgnoresForwarding()throws Exception {
        var c=new Client();String body=JSON.writeValueAsString(Map.of("username",username(),"password",UUID.randomUUID().toString()));
        for(int i=0;i<5;i++)error(c.call("POST","/api/v1/auth/login",body,Map.of("Origin",ORIGIN,"X-Forwarded-For","192.0.2."+i)),401);
        error(c.call("POST","/api/v1/auth/login",body,Map.of("Origin",ORIGIN,"Forwarded","for=192.0.2.99","X-Forwarded-For","192.0.2.99")),429);
    }
    @Test void fixationRotationAndLogout()throws Exception {
        var c=signed();String old=c.cookies.getCookieStore().getCookies().stream().filter(x->x.getName().equals("JSESSIONID")).findFirst().orElseThrow().getValue();String first=c.csrf;
        var r=c.login(username(),password());assertEquals(200,r.statusCode());assertNotEquals(first,c.csrf);
        String current=c.cookies.getCookieStore().getCookies().stream().filter(x->x.getName().equals("JSESSIONID")).findFirst().orElseThrow().getValue();assertNotEquals(old,current);
        assertTrue(r.headers().allValues("Set-Cookie").stream().anyMatch(x->x.contains("HttpOnly") && x.contains("SameSite=Strict")));
        var noCookies=HttpClient.newHttpClient();var oldResponse=noCookies.send(HttpRequest.newBuilder(URI.create("http://127.0.0.1:"+port+"/api/v1/me")).header("Cookie","JSESSIONID="+old).build(),HttpResponse.BodyHandlers.ofString());error(oldResponse,401);
        String path="/api/v1/auth/logout";error(c.call("POST",path,null,Map.of("Origin",ORIGIN,"X-CSRF-Token",c.csrf)),428);
        assertEquals(204,c.call("POST",path,null,Map.of("Origin",ORIGIN,"X-CSRF-Token",c.csrf,"Idempotency-Key",UUID.randomUUID().toString(),"X-Request-Hash",CanonicalRequest.hash("POST",path,new byte[0]))).statusCode());
        error(c.call("GET","/api/v1/me",null,Map.of()),401);
    }
    @Test void csrfOriginAndFilterErrorEnvelope()throws Exception {
        var c=signed();var other=signed();String path="/api/v1/auth/logout";
        error(c.call("POST",path,null,Map.of("Origin",ORIGIN)),403);
        error(c.call("POST",path,null,Map.of("Origin",ORIGIN,"X-CSRF-Token","bad")),403);
        error(c.call("POST",path,null,Map.of("Origin",ORIGIN,"X-CSRF-Token",other.csrf)),403);
        error(c.call("POST",path,null,Map.of("Origin","https://evil.invalid","X-CSRF-Token",c.csrf)),403);
        error(c.call("POST","/api/v1/auth/login","{}",Map.of("Origin","https://evil.invalid")),403);
        error(c.call("POST","/api/v1/auth/login","{}",Map.of()),403);
        error(new Client().call("GET","/api/v1/me",null,Map.of("actorId",owner().toString(),"actorType","OWNER")),401);
    }
    @Test void forgedLoginFieldsAndValidation()throws Exception {
        var c=new Client();error(c.call("POST","/api/v1/auth/login",JSON.writeValueAsString(Map.of("username",username(),"password",password(),"actorId",owner().toString())),Map.of("Origin",ORIGIN)),422);
        error(c.call("POST","/api/v1/auth/login","{",Map.of("Origin",ORIGIN)),400);
    }
    @Test void auditIsolationPagingAndTrace()throws Exception {
        var c=signed();for(int i=0;i<3;i++)assertEquals(201,c.command(ARTICLE,UUID.randomUUID().toString(),"{\"n\":1}","\"job-1\"").statusCode());
        var r=c.call("GET","/api/v1/articles/"+ARTICLE+"/audit-logs?limit=1",null,Map.of());assertEquals(200,r.statusCode());
        var n=JSON.readTree(r.body());assertEquals(1,n.get("items").size());String cursor=n.get("nextCursor").asText();assertFalse(cursor.equals("null"));
        assertEquals(200,c.call("GET","/api/v1/articles/"+ARTICLE+"/audit-logs?limit=1&cursor="+cursor,null,Map.of()).statusCode());
        error(c.call("GET","/api/v1/articles/"+OTHER+"/audit-logs?cursor="+cursor,null,Map.of()),422);
        error(c.call("GET","/api/v1/articles/"+ARTICLE+"/audit-logs?cursor="+cursor+"x",null,Map.of()),422);
        error(c.call("GET","/api/v1/articles/"+FOREIGN+"/audit-logs",null,Map.of()),404);
        error(c.call("GET","/api/v1/articles/"+ARTICLE+"/audit-logs?limit=101",null,Map.of()),422);
        error(new Client().call("GET","/api/v1/articles/"+ARTICLE+"/audit-logs",null,Map.of()),401);
        assertEquals(0,db.queryForObject("SELECT count(*) FROM editorial.audit_log WHERE trace_id IS NULL",Integer.class));
    }
    @Test void secondOwnerCannotReadOrReplay()throws Exception {
        UUID second=UUID.randomUUID();String encoded=encoder.encode(password());
        try(var connection=DriverManager.getConnection(System.getenv("DB_URL"),"editorial_admin",System.getenv("T03_ADMIN_PASSWORD"));var s=connection.prepareStatement("INSERT INTO editorial.app_user(id,username,display_name,actor_type,password_hash) VALUES (?,'isolation-only','Isolation','OWNER',?)")){s.setObject(1,second);s.setString(2,encoded);s.executeUpdate();}
        try {var c=new Client();assertEquals(200,c.login("isolation-only",password()).statusCode());error(c.call("GET","/api/v1/articles/"+ARTICLE+"/audit-logs",null,Map.of()),404);error(c.command(ARTICLE,UUID.randomUUID().toString(),"{\"n\":1}","\"job-1\""),404);}
        finally {admin("UPDATE editorial.app_user SET enabled=false WHERE username='isolation-only'");}
    }
    @Test void crossArticleRefsWorkerAndMissingResolver() {
        var a=worker();assertEquals(403,assertThrows(PublicFailure.class,a::requireHuman).status());
        var ref=new Ownership.ArtifactRef(ARTICLE,OTHER,null,"ARTICLE","0".repeat(64),false);
        assertEquals(404,assertThrows(PublicFailure.class,()->ownership.require(a,ARTICLE,ref,false)).status());
        assertEquals(503,assertThrows(PublicFailure.class,()->new Ownership(List.of()).requireArticle(a,ARTICLE)).status());
        assertEquals(503,assertThrows(PublicFailure.class,()->ownership.require(a,ARTICLE,new Ownership.ArtifactRef(UUID.randomUUID(),ARTICLE,null,"VERSION","0".repeat(64),false),false)).status());
    }
    @Test void replayConflictHashAndEtagOrder()throws Exception {
        var c=signed();String key=UUID.randomUUID().toString();String body="{\"n\":1}";
        var first=c.command(ARTICLE,key,body,"\"job-1\"");assertEquals(201,first.statusCode());
        var replay=c.command(ARTICLE,key,body,"\"job-0\"");assertEquals(201,replay.statusCode());assertEquals(first.body(),replay.body());
        for(String h:List.of("Location","ETag"))assertEquals(first.headers().firstValue(h),replay.headers().firstValue(h));
        error(c.command(ARTICLE,key,"{\"n\":2}","\"job-1\""),409);
        error(c.command(ARTICLE,UUID.randomUUID().toString(),body,null),428);
        error(c.command(ARTICLE,UUID.randomUUID().toString(),body,"\"job-0\""),412);
        String path="/api/v1/t03-test/command/"+ARTICLE;
        error(c.call("POST",path,body,Map.of("Origin",ORIGIN,"X-CSRF-Token",c.csrf,"Idempotency-Key",key,"X-Request-Hash","0".repeat(64))),422);
        error(c.command(ARTICLE,UUID.randomUUID().toString(),"{\"actorType\":\"OWNER\"}","\"job-1\""),422);
    }
    @Test void concurrentIdenticalHttpOnlyOneEffect()throws Exception {
        var c=signed();String key=UUID.randomUUID().toString();int before=db.queryForObject("SELECT count(*) FROM editorial.audit_log WHERE action='TEST_COMMAND'",Integer.class);
        try(var pool=Executors.newFixedThreadPool(6)){
            var jobs=new ArrayList<Future<HttpResponse<String>>>();for(int i=0;i<6;i++)jobs.add(pool.submit(()->c.command(ARTICLE,key,"{\"n\":1}","\"job-1\"")));
            Set<String> bodies=new HashSet<>();for(var job:jobs){var r=job.get(10,TimeUnit.SECONDS);assertEquals(201,r.statusCode());bodies.add(r.body());}assertEquals(1,bodies.size());
        }
        assertEquals(before+1,db.queryForObject("SELECT count(*) FROM editorial.audit_log WHERE action='TEST_COMMAND'",Integer.class));
    }
    @Test void rollbackBusinessAuditAndRetryNoFalseSuccess() {
        ActorContext actor=worker();String key=UUID.randomUUID().toString(),hash=CanonicalRequest.hash("POST","/rollback",new byte[0]);
        AtomicInteger calls=new AtomicInteger();
        for(boolean auditFailure:new boolean[]{false,true}) {
            assertThrows(RuntimeException.class,()->idem.execute(actor,"POST","/rollback",null,key,hash,new byte[0],()->{},()->{},()->{
                calls.incrementAndGet();audit.append(actor,new AuditSink.Event("ROLLBACK_PROBE",ARTICLE,"ARTICLE",ARTICLE,null,null));
                if(auditFailure)audit.append(actor,new AuditSink.Event("FAIL",ARTICLE,"ARTICLE",ARTICLE,"invalid",null));
                throw new PublicFailure(409,"BUSINESS_REJECTED");
            }));
            assertEquals(0,db.queryForObject("SELECT count(*) FROM editorial.audit_log WHERE action='ROLLBACK_PROBE'",Integer.class));
            assertEquals(0,db.queryForObject("SELECT count(*) FROM editorial.idempotency_record WHERE key=?",Integer.class,UUID.fromString(key)));
        }
        assertEquals(204,idem.execute(actor,"POST","/rollback",null,key,hash,new byte[0],()->{},()->{},()->{calls.incrementAndGet();return Idempotency.Response.empty();}).status());assertEquals(3,calls.get());
    }
    @Test void auditRequiresTransactionAndCaughtFailureStillRollsBack() {
        assertThrows(org.springframework.transaction.IllegalTransactionStateException.class,()->audit.append(worker(),new AuditSink.Event("TEST",null,"USER",owner(),null,null)));
        assertThrows(RuntimeException.class,()->new TransactionTemplate(manager).executeWithoutResult(s->{
            try{audit.append(worker(),new AuditSink.Event("BAD",null,"USER",owner(),"invalid",null));}catch(PublicFailure ignored){}
        }));
    }
    @Test void runtimePrivilegesAndMigrationIsolation() {
        for(String sql:List.of("UPDATE editorial.audit_log SET action='BAD'","DELETE FROM editorial.audit_log","TRUNCATE editorial.audit_log","CREATE TABLE editorial.illegal(id int)","SELECT * FROM editorial_migrations.flyway_schema_history","SET ROLE editorial_migrator"))assertThrows(org.springframework.dao.DataAccessException.class,()->db.execute(sql));
    }
    @Test void scopeIsolationAndAuthorizationBeforeReplay() {
        var actor=worker();String key=UUID.randomUUID().toString();AtomicInteger count=new AtomicInteger();
        for(String route:List.of("/one","/two"))idem.execute(actor,"POST",route,null,key,CanonicalRequest.hash("POST",route,new byte[0]),new byte[0],()->{},()->{},()->{count.incrementAndGet();return Idempotency.Response.empty();});
        var other=ActorContext.forWorker(system(),system(),UUID.randomUUID());
        idem.execute(other,"POST","/one",null,key,CanonicalRequest.hash("POST","/one",new byte[0]),new byte[0],()->{},()->{},()->{count.incrementAndGet();return Idempotency.Response.empty();});assertEquals(3,count.get());
        assertEquals(404,assertThrows(PublicFailure.class,()->idem.execute(actor,"POST","/one",null,key,CanonicalRequest.hash("POST","/one",new byte[0]),new byte[0],()->{throw new PublicFailure(404,"OWNER_MISMATCH");},()->{},Idempotency.Response::empty)).status());
    }
    @TestConfiguration(proxyBeanMethods=false) static class Fixture {
        @Bean Ownership.Resolver articleFixture(JdbcTemplate db){return new Ownership.Resolver(){
            public boolean supports(String kind){return kind.equals("ARTICLE");}
            public Ownership.Resolved resolve(String kind,UUID id){
                if(!List.of(ARTICLE,OTHER,FOREIGN).contains(id))return null;
                UUID owner=db.queryForObject("SELECT id FROM editorial.app_user WHERE bootstrap_key=?",UUID.class,id.equals(FOREIGN)?"SYSTEM":"OWNER");
                return new Ownership.Resolved(owner,new Ownership.ArtifactRef(id,id,null,kind,"0".repeat(64),false));
            }
        };}
        @Bean ProbeController probe(Ownership o,Idempotency i,AuditSink a){return new ProbeController(o,i,a);}
    }
    @RestController static class ProbeController {
        final Ownership ownership;final Idempotency idem;final AuditSink audit;
        ProbeController(Ownership o,Idempotency i,AuditSink a){ownership=o;idem=i;audit=a;}
        @PostMapping("/api/v1/t03-test/command/{id}") void command(@PathVariable UUID id,HttpServletRequest req,HttpServletResponse res)throws Exception {
            var actor=ActorContext.current();byte[] body=req.getInputStream().readNBytes(1_048_577);
            var result=idem.execute(actor,req.getMethod(),req.getRequestURI(),req.getQueryString(),req.getHeader("Idempotency-Key"),req.getHeader("X-Request-Hash"),body,
                ()->ownership.requireArticle(actor,id),()->{Idempotency.requireEtag(req.getHeader("If-Match"),1);var n=CanonicalRequest.parse(body);if(n.size()!=1 || !n.path("n").isIntegralNumber())throw new PublicFailure(422,"VALIDATION_FAILED");},
                ()->{var record=audit.append(actor,new AuditSink.Event("TEST_COMMAND",id,"ARTICLE",id,null,null));return new Idempotency.Response(201,("{\"id\":\""+record.id()+"\"}").getBytes(StandardCharsets.UTF_8),Map.of("Location","/api/v1/articles/"+id,"ETag","\"job-2\"","Content-Type","application/json"));});
            res.setStatus(result.status());result.headers().forEach(res::setHeader);res.getOutputStream().write(result.body());
        }
    }
}

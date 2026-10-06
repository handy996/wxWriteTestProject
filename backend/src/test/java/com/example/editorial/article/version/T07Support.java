package com.example.editorial.article.version;
import com.example.editorial.article.job.*;
import com.example.editorial.article.proposal.*;

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

@EnabledIfEnvironmentVariable(named="T06_REAL_PG",matches="true")
abstract class T07Support {
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
    ActorContext actor(){return ActorContext.forWorker(db.queryForObject("SELECT id FROM editorial.app_user WHERE bootstrap_key='SYSTEM'",UUID.class),owner(),UUID.randomUUID());}
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
    @Autowired VersionService versions;
    @Autowired ProposalService proposals;
    @Autowired VersionPorts.Store versionStore;
    UUID articleId(JsonNode a){return uuid(a.path("job").path("id").asText());}
    UUID head(JsonNode a){return uuid(a.path("job").path("currentVersionId").asText());}
    JsonNode version(JsonNode a){return articles.readVersion(actor(),articleId(a),head(a));}
    ObjectNode edit(JsonNode a){var v=version(a);var r=JSON.createObjectNode().put("baseVersionId",head(a).toString()).put("title","Changed 😀 title").putNull("subtitle").put("reason","User edit");r.set("contentAst",v.path("contentAst").deepCopy());r.putArray("blockMappings");return r;}
    JsonNode ok(HttpResponse<String> r,int code)throws Exception{assertEquals(code,r.statusCode(),r.body());return JSON.readTree(r.body());}
    void sample(String name,JsonNode n)throws Exception{java.nio.file.Files.writeString(java.nio.file.Path.of(System.getProperty("t07.samples"),name+".json"),n.toString());}
    long count(JsonNode a){return db.queryForObject("SELECT count(*) FROM editorial.article_version WHERE article_id=?",Long.class,articleId(a));}
    JsonNode current(Client c,JsonNode a)throws Exception{return ok(c.get(path(a)),200);}
}

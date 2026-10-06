package com.example.editorial.article.version;

import static com.example.editorial.article.ast.ArticleAst.*;
import com.example.editorial.article.job.*;
import com.example.editorial.shared.*;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.*;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.*;
import org.springframework.jdbc.core.JdbcTemplate;

/** Explicit transaction substitutes for T10/T11. Real PG rows, NOT the real scheduler/outbox. */
public class TestParticipants implements VersionPorts.HumanFence,VersionPorts.Executions,ArticlePorts.Changes {
    final JdbcTemplate db;final ArticleService articles;volatile String failure="";
    volatile java.util.concurrent.CountDownLatch staged,release;
    TestParticipants(JdbcTemplate db,ArticleService articles){this.db=db;this.articles=articles;}
    @TestConfiguration(proxyBeanMethods=false) public static class Config {
        @Bean @Primary TestParticipants t07Participants(JdbcTemplate db,org.springframework.beans.factory.ObjectProvider<ArticleService> provider){return new TestParticipants(db,null){
            @Override ArticleService service(){return provider.getObject();}
        };}
        @Bean @Primary VersionPorts.Store faultStore(@org.springframework.beans.factory.annotation.Qualifier("versionStore") VersionPorts.Store delegate,TestParticipants participants,com.example.editorial.storage.StorageBackend backend){return new VersionPorts.Store(){
            public ArticleService.PreparedVersion prepare(ActorContext a,UUID j,VersionPorts.Draft d,com.example.editorial.article.ast.ArticleAst.References r){
                var p=delegate.prepare(a,j,d,r);
                if(d.source().equals("AI")&&participants.staged!=null) {
                    participants.staged.countDown();try{if(!participants.release.await(15,java.util.concurrent.TimeUnit.SECONDS))throw new IllegalStateException("stage barrier timeout");}catch(InterruptedException e){Thread.currentThread().interrupt();throw new IllegalStateException(e);}
                }
                if(participants.failure.equals("reference")) {var n=p.object();backend.delete(new com.example.editorial.storage.ObjectRef(n.path("key").asText(),n.path("hash").asText(),n.path("size").asLong(),n.path("mime").asText(),n.path("encrypted").asBoolean()));}
                return p;
            }
            public UUID append(ActorContext a,ArticleService.PreparedVersion p,boolean retained,JsonNode style){return delegate.append(a,p,retained,style);}
            public List<JsonNode> page(ActorContext a,UUID j,long before,int limit){return delegate.page(a,j,before,limit);}
        };}
    }
    ArticleService service(){return articles;}
    public void invalidate(ActorContext a,UUID j,UUID base) {
        VersionService.requireTransaction();db.update("UPDATE editorial.t07_test_state SET fence=fence+1 WHERE article_id=?",j);
        if(failure.equals("fence"))throw new PublicFailure(503,"TEST_FENCE_FAILURE");
    }
    public void apply(ActorContext a,UUID j,JsonNode before,JsonNode after,boolean gen,boolean rights) {
        VersionService.requireTransaction();db.update("UPDATE editorial.t07_test_state SET qa_valid=false,approval_valid=false,invalidations=invalidations+1 WHERE article_id=?",j);
        if(gen&&before.path("currentVersionId").equals(after.path("currentVersionId")))db.update("UPDATE editorial.t07_test_state SET fence=fence+1 WHERE article_id=?",j);
        if(failure.equals("changes"))throw new PublicFailure(503,"TEST_INVALIDATION_FAILURE");
    }
    private JsonNode node(String s){try{return JSON.readTree(s);}catch(Exception e){throw new IllegalStateException(e);}}
    public VersionPorts.Execution inspect(ActorContext a,JsonNode context,JsonNode output) {
        VersionService.requireTransaction();UUID step=uuid(context.path("stepExecutionId").asText());
        var rows=db.query("SELECT context::text,style::text,output_hash,result_id,agent_id FROM editorial.t07_test_execution WHERE id=? FOR UPDATE",(rs,n)->new Object[]{node(rs.getString(1)),node(rs.getString(2)),rs.getString(3),rs.getObject(4,UUID.class),rs.getObject(5,UUID.class)},step);
        if(rows.isEmpty())throw new PublicFailure(409,"STALE_FENCE");var row=rows.getFirst();
        if(!row[0].equals(context)||!row[2].equals(hash(output)))throw new PublicFailure(409,"STALE_FENCE");
        UUID j=uuid(context.path("jobId").asText());service().job(a,j,true);
        int fence=db.queryForObject("SELECT fence FROM editorial.t07_test_state WHERE article_id=?",Integer.class,j);
        boolean retained=fence>context.path("fencingToken").asInt()||context.path("stepCode").asText().equals("REVISE");
        if(row[3]==null&&!retained&&!service().job(a,j,false).path("currentVersionId").equals(context.path("baseVersionId")))throw new PublicFailure(409,"STALE_FENCE");
        return new VersionPorts.Execution((UUID)row[4],(JsonNode)row[1],retained,(UUID)row[3]);
    }
    public void complete(ActorContext a,JsonNode c,JsonNode o,UUID result,boolean conflict) {
        VersionService.requireTransaction();db.update("UPDATE editorial.t07_test_execution SET result_id=?,conflict=? WHERE id=? AND result_id IS NULL",result,conflict,uuid(c.path("stepExecutionId").asText()));
        if(failure.equals("complete"))throw new PublicFailure(503,"TEST_EXECUTION_FAILURE");
    }
}

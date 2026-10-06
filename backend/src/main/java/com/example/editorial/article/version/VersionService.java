package com.example.editorial.article.version;

import static com.example.editorial.article.ast.ArticleAst.*;
import com.example.editorial.article.job.ArticleService;
import com.example.editorial.shared.*;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.*;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.*;

public final class VersionService {
    private final ArticleService articles;
    private final VersionPorts.Store store;
    private final VersionPorts.References refs;
    private final VersionPorts.HumanFence fence;
    private final VersionPorts.Executions executions;
    private final PageCursor cursors;
    private final TransactionTemplate tx;
    private final VersionPorts.HeadChanged localChanges;
    public VersionService(ArticleService articles,VersionPorts.Store store,VersionPorts.References refs,
            VersionPorts.HumanFence fence,VersionPorts.Executions executions,PageCursor cursors,PlatformTransactionManager manager,VersionPorts.HeadChanged localChanges) {
        this.articles=articles;this.store=store;this.refs=refs;this.fence=fence;this.executions=executions;this.cursors=cursors;tx=new TransactionTemplate(manager);this.localChanges=localChanges;
    }
    public JsonNode list(ActorContext a,UUID article,String cursor,int limit) {
        articles.job(a,article,false);PageCursor.limit(limit);String scope=cursors.scope(a,article,"versions",null),last=cursors.read(cursor,scope);long before=(long)Integer.MAX_VALUE+1;
        if(last!=null)try {before=Long.parseLong(last);if(before<1||before>Integer.MAX_VALUE)throw new IllegalArgumentException();}catch(Exception e){fail("INVALID_CURSOR");}
        var rows=store.page(a,article,before,limit+1);var page=JSON.createObjectNode();var items=page.putArray("items");rows.stream().limit(limit).forEach(items::add);
        page.put("nextCursor",rows.size()>limit?cursors.write(rows.get(limit-1).path("versionNo").asText(),scope):null);return page;
    }
    public JsonNode diff(ActorContext a,UUID article,UUID from,UUID to) {return VersionDiff.between(article,articles.readVersion(a,article,from),articles.readVersion(a,article,to));}
    public void guard(ActorContext a,UUID article,String etag,UUID base) {
        var job=articles.job(a,article,true);articles.writable(article);Idempotency.requireEtag(etag,job.path("lockVersion").asLong());
        if(job.path("status").asText().equals("CANCELLED"))throw new PublicFailure(409,"CANCELLED");
        if(base!=null&&!job.path("currentVersionId").asText().equals(base.toString()))throw new PublicFailure(409,"STALE_INPUT");
    }
    public ArticleService.PreparedVersion prepare(ActorContext a,UUID article,JsonNode request,String etag,boolean restore) {
        a.requireHuman();articles.validate(request,restore?"RestoreRequest":"SaveVersionRequest");
        if(request.path("reason").asText().isBlank())fail("REASON_REQUIRED");
        var j=articles.job(a,article,false);UUID base=restore?uuid(j.path("currentVersionId").asText()):uuid(request.path("baseVersionId").asText());
        UUID source=restore?uuid(request.path("versionId").asText()):null;JsonNode content=restore?articles.readVersion(a,article,source):request;
        JsonNode mappings=restore?JSON.createArrayNode():request.path("blockMappings");
        if(!restore)VersionDiff.mappings(articles.readVersion(a,article,base).path("contentAst"),content.path("contentAst"),mappings);
        return store.prepare(a,article,new VersionPorts.Draft(base,source,etag,restore?"RESTORE":"MANUAL","USER",content.path("title").asText(),content.path("subtitle").isNull()?null:content.path("subtitle").asText(),content.path("contentAst"),request.path("reason").asText(),mappings,null,hash(request),false),(k,id)->refs.require(a,article,restore?source:base,k,id,content));
    }
    public ArticleService.PreparedVersion prepareAcceptance(ActorContext a,UUID article,UUID base,JsonNode candidate,String etag) {
        a.requireHuman();VersionDiff.mappings(articles.readVersion(a,article,base).path("contentAst"),candidate.path("contentAst"),candidate.path("blockMappings"));
        return store.prepare(a,article,new VersionPorts.Draft(base,null,etag,"REVISION","USER",candidate.path("title").asText(),candidate.path("subtitle").isNull()?null:candidate.path("subtitle").asText(),candidate.path("contentAst"),"Accepted proposal",candidate.path("blockMappings"),null,candidate.path("meta").path("inputHash").asText(),false),(k,id)->refs.require(a,article,base,k,id,candidate));
    }
    public UUID save(ActorContext a,ArticleService.PreparedVersion p) {
        requireTransaction();a.requireHuman();guard(a,p.article(),p.etag(),p.base());
        validate(p.document().path("contentAst"),(k,id)->refs.require(a,p.article(),p.document().path("restoredFromVersionId").isNull()?p.base():uuid(p.document().path("restoredFromVersionId").asText()),k,id,p.document()));
        fence.invalidate(a,p.article(),p.base()); // persisted BEFORE append/move; failure rolls back entire command
        UUID id=store.append(a,p,false,null);articles.moveHead(a,p.article(),id,p.etag());return id;
    }
    /** Frozen VersionCommand.commit boundary. All provider IO has completed before entry.
     * A proven late result returns a stale immutable version and never moves the working head. */
    public JsonNode commit(ActorContext actor,JsonNode stepContext,JsonNode writerOutput,String etag) {
        if(TransactionSynchronizationManager.isActualTransactionActive())throw new IllegalStateException("Commit must own staging boundary");
        JsonNode context=stepContext.deepCopy(),output=writerOutput.deepCopy();
        articles.validate(output,"WriterOutput");UUID article=uuid(context.path("jobId").asText()),base=uuid(context.path("baseVersionId").asText());
        if(!actor.actorType().equals("SYSTEM_WORKER"))throw new PublicFailure(403,"WORKER_REQUIRED");
        validateContext(actor,context);
        var mappings=VersionDiff.replacement(articles.readVersion(actor,article,base).path("contentAst"),output.path("contentAst"));
        var used=new HashSet<String>();for(var id:output.path("usedClaimIds")){if(!used.add(id.asText()))fail("DUPLICATE_REFERENCE");refs.require(actor,article,base,"CLAIM",uuid(id.asText()),output);}
        for(var b:output.path("contentAst").path("blocks"))for(var id:b.path("claimRefs"))if(!used.contains(id.asText()))fail("CLAIM_SET_MISMATCH");
        var localKeys=new HashSet<String>();for(var claim:output.path("newClaimCandidates")) {
            if(!localKeys.add(claim.path("localKey").asText()))fail("DUPLICATE_CLAIM_KEY");
            for(var span:claim.path("spans"))versionSpan(output,span);
        }
        for(int retry=0;retry<8;retry++) {
            var execution=tx.execute(s->{articles.job(actor,article,true);active(actor,article);return executions.inspect(actor,context,output);});
            if(execution.resultVersionId()!=null)return articles.readVersion(actor,article,execution.resultVersionId());
            boolean retained=execution.retained();
            try {
            var p=store.prepare(actor,article,new VersionPorts.Draft(base,null,etag,context.path("stepCode").asText().equals("WRITE")?"DRAFT":"REVISION","AI",output.path("title").asText(),output.path("subtitle").isNull()?null:output.path("subtitle").asText(),output.path("contentAst"),output.path("changeSummary").asText(),mappings,execution.agentExecutionId(),context.path("inputHash").asText(),retained),(k,id)->refs.require(actor,article,base,k,id,output));
            return tx.execute(s->{
                articles.job(actor,article,true);active(actor,article);var current=executions.inspect(actor,context,output);
                if(current.resultVersionId()!=null)return articles.readVersion(actor,article,current.resultVersionId());
                if(current.retained()!=retained)throw new PublicFailure(409,"RESTAGE_REQUIRED");
                if(!current.agentExecutionId().equals(execution.agentExecutionId())||!current.style().equals(execution.style()))throw new PublicFailure(409,"STALE_FENCE");
                // usedClaimIds includes title-only facts, not just the AST claimRefs subset.
                // Recheck on every staged attempt, after result replay and before any business writes.
                for(var id:output.path("usedClaimIds"))refs.require(actor,article,base,"CLAIM",uuid(id.asText()),output);
                validate(p.document().path("contentAst"),(k,id)->refs.require(actor,article,base,k,id,output));
                UUID id=store.append(actor,p,retained,current.style());
                if(!retained){articles.moveHead(actor,article,id,etag);localChanges.apply(actor,article,id);}
                executions.complete(actor,context,output,id,retained);return articles.readVersion(actor,article,id);
            });}catch(PublicFailure e){
                if(e.code().equals("RESTAGE_REQUIRED"))continue;
                if(!retained&&(e.code().equals("ETAG_MISMATCH")||e.code().equals("STALE_INPUT"))) {
                    var next=tx.execute(s->{articles.job(actor,article,true);active(actor,article);return executions.inspect(actor,context,output);});
                    if(next.retained())continue;
                }
                throw e;
            }
        }
        throw new PublicFailure(503,"VERSION_CONTENTION");
    }
    private static void validateContext(ActorContext actor,JsonNode c) {
        fields(c,"actor","jobId","workflowId","stepExecutionId","stepCode","attempt","scopeId","workflowGeneration","logicalKey","baseVersionId","inputHash","skillVersionId","policyVersions","deadline","traceId","fencingToken","budgetReservationId");
        for(String k:List.of("jobId","workflowId","stepExecutionId","scopeId","baseVersionId","skillVersionId","traceId"))uuid(c.path(k).asText());
        for(String k:List.of("attempt","workflowGeneration","fencingToken"))if(!c.path(k).isIntegralNumber()||c.path(k).asLong()<1||c.path(k).asLong()>Integer.MAX_VALUE)fail("INVALID_STEP_CONTEXT");
        for(String k:List.of("inputHash","logicalKey"))if(!c.path(k).asText().matches("[a-f0-9]{64}"))fail("INVALID_STEP_CONTEXT");
        if(!Set.of("WRITE","REVISE").contains(c.path("stepCode").asText()))fail("INVALID_STEP_CONTEXT");
        if(!c.path("policyVersions").isArray()||c.path("policyVersions").size()>1000)fail("INVALID_STEP_CONTEXT");for(var id:c.path("policyVersions"))uuid(id.asText());
        if(!c.path("budgetReservationId").isNull())uuid(c.path("budgetReservationId").asText());
        var a=c.path("actor");fields(a,"actorId","ownerId","actorType","traceId","authenticatedAt");uuid(a.path("traceId").asText());
        if(!a.path("actorId").asText().equals(actor.actorId().toString())||!a.path("ownerId").asText().equals(actor.ownerId().toString())||!a.path("actorType").asText().equals(actor.actorType()))throw new PublicFailure(403,"EXECUTION_ACTOR_MISMATCH");
        for(String time:List.of(c.path("deadline").asText(),a.path("authenticatedAt").asText()))try {if(!time.endsWith("Z"))throw new IllegalArgumentException();java.time.Instant.parse(time);}catch(Exception e){fail("INVALID_STEP_CONTEXT");}
    }
    private void active(ActorContext a,UUID id) {articles.writable(id);if(articles.job(a,id,false).path("status").asText().equals("CANCELLED"))throw new PublicFailure(409,"CANCELLED");}
    public static void requireTransaction() {if(!TransactionSynchronizationManager.isActualTransactionActive())throw new IllegalStateException("Transaction required");}
}

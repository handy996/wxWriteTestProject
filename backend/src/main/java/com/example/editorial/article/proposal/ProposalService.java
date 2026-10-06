package com.example.editorial.article.proposal;

import static com.example.editorial.article.ast.ArticleAst.*;
import com.example.editorial.article.job.ArticleService;
import com.example.editorial.article.version.*;
import com.example.editorial.shared.*;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;

/** Owns only change_proposal. Producer calls create in its result transaction; no public create route. */
public final class ProposalService {
    private final JdbcTemplate db;private final ArticleService articles;private final VersionPorts.Audit audit;private final PageCursor cursor;
    public ProposalService(JdbcTemplate db,ArticleService articles,VersionPorts.Audit audit,PageCursor cursor) {this.db=db;this.articles=articles;this.audit=audit;this.cursor=cursor;}
    private static JsonNode parse(String s) {try{return JSON.readTree(s);}catch(Exception e){throw new IllegalStateException(e);}}
    private static String wire(JsonNode n) {return new String(CanonicalRequest.canonical(n),java.nio.charset.StandardCharsets.UTF_8);}
    public UUID article(ActorContext a,UUID id) {
        var ids=db.query("SELECT article_id FROM editorial.change_proposal WHERE id=? AND owner_id=?",(rs,n)->rs.getObject(1,UUID.class),id,a.ownerId());
        if(ids.isEmpty())throw new PublicFailure(404,"NOT_FOUND");articles.job(a,ids.getFirst(),false);return ids.getFirst();
    }
    public JsonNode read(ActorContext a,UUID id,boolean lock) {
        UUID article=article(a,id);if(lock)articles.job(a,article,true);
        return db.queryForObject("SELECT document::text FROM editorial.change_proposal WHERE id=?"+(lock?" FOR UPDATE":""),(rs,n)->parse(rs.getString(1)),id);
    }
    public void pending(ActorContext a,UUID id,UUID requestedBase) {
        var p=read(a,id,true);UUID article=uuid(p.path("meta").path("articleId").asText());articles.writable(article);var j=articles.job(a,article,true);
        if(j.path("status").asText().equals("CANCELLED"))throw new PublicFailure(409,"CANCELLED");
        if(!p.path("status").asText().equals("PENDING") || !p.path("baseVersionId").equals(j.path("currentVersionId")) || requestedBase!=null&&!requestedBase.toString().equals(p.path("baseVersionId").asText()))throw new PublicFailure(409,"PROPOSAL_CONFLICT");
    }
    public JsonNode candidate(ActorContext a,UUID id) {var p=read(a,id,false);return articles.readVersion(a,uuid(p.path("meta").path("articleId").asText()),uuid(p.path("proposedVersionId").asText()));}
    /** Candidate is an immutable, already committed AI version, with execution provenance preserved.
     * Producer identity and source association are validated against that server-owned version. */
    public JsonNode create(ActorContext a,UUID article,UUID base,UUID proposed,JsonNode scope) {
        VersionService.requireTransaction();if(!a.actorType().equals("SYSTEM_WORKER"))throw new PublicFailure(403,"WORKER_REQUIRED");
        var j=articles.job(a,article,true);articles.writable(article);if(j.path("status").asText().equals("CANCELLED"))throw new PublicFailure(409,"CANCELLED");
        var before=articles.readVersion(a,article,base);var v=articles.readVersion(a,article,proposed);
        if(!v.path("parentVersionId").asText().equals(base.toString())||!v.path("changeSource").asText().equals("AI")||v.path("meta").path("executionId").isNull()
            ||!v.path("meta").path("createdBy").asText().equals(a.actorId().toString()))fail("INVALID_PROPOSAL_SOURCE");
        var blocks=VersionDiff.blocks(before.path("contentAst"));var seen=new HashSet<String>();
        if(!scope.isArray()||scope.size()>1000)fail("INVALID_PROPOSAL_SCOPE");
        for(var id:scope)if(!id.isTextual()||!blocks.containsKey(id.asText())||!seen.add(id.asText()))fail("INVALID_PROPOSAL_SCOPE");
        var old=db.query("SELECT document::text FROM editorial.change_proposal WHERE article_id=? AND proposed_version_id=?",(rs,n)->parse(rs.getString(1)),article,proposed);
        if(!old.isEmpty()) {if(!old.getFirst().path("scopeBlockIds").equals(scope))throw new PublicFailure(409,"PROPOSAL_SOURCE_CONFLICT");return old.getFirst();}
        UUID id=UUID.randomUUID();var meta=(ObjectNode)v.path("meta").deepCopy();meta.put("id",id.toString()).put("versionId",base.toString()).put("createdAt",java.time.Instant.now().toString()).put("traceId",a.traceId().toString());
        boolean stale=!j.path("currentVersionId").asText().equals(base.toString());meta.put("stale",stale);
        var p=JSON.createObjectNode().put("baseVersionId",base.toString()).put("proposedVersionId",proposed.toString()).put("status",stale?"STALE":"PENDING").putNull("acceptedVersionId");p.set("scopeBlockIds",scope.deepCopy());
        // Disposition is mutable metadata; the proposal's immutable content hash never includes it.
        var immutable=p.deepCopy();immutable.remove(List.of("status","acceptedVersionId"));
        meta.put("contentHash",hash(immutable));p.set("meta",meta);
        db.update("INSERT INTO editorial.change_proposal(id,article_id,owner_id,base_version_id,proposed_version_id,status,document) VALUES(?,?,?,?,?,?,?::jsonb)",id,article,a.ownerId(),base,proposed,p.path("status").asText(),wire(p));
        audit.append(a,"PROPOSAL_CREATED",article,id,null,hash(p));return p;
    }
    public void accepted(ActorContext a,UUID id,UUID version) {
        VersionService.requireTransaction();a.requireHuman();var p=read(a,id,true);UUID article=uuid(p.path("meta").path("articleId").asText());var result=articles.readVersion(a,article,version);
        if(!articles.job(a,article,true).path("currentVersionId").asText().equals(version.toString())||!result.path("parentVersionId").equals(p.path("baseVersionId")))throw new PublicFailure(409,"PROPOSAL_CONFLICT");
        dispose(a,id,"ACCEPTED",null,version);
    }
    public JsonNode reject(ActorContext a,UUID id,JsonNode request) {
        a.requireHuman();articles.validate(request,"ReasonRequest");if(request.path("reason").asText().isBlank())fail("REASON_REQUIRED");pending(a,id,null);
        UUID auditId=dispose(a,id,"REJECTED",request.path("reason").asText(),null);
        return JSON.createObjectNode().put("entityId",id.toString()).put("status","REJECTED").put("auditId",auditId.toString());
    }
    private UUID dispose(ActorContext a,UUID id,String status,String reason,UUID result) {
        VersionService.requireTransaction();var p=(ObjectNode)read(a,id,true);String before=hash(p);p.put("status",status).put("acceptedVersionId",result==null?null:result.toString());
        int count=db.update("UPDATE editorial.change_proposal SET status=?,accepted_version_id=?,reason=?,document=?::jsonb,lock_version=lock_version+1 WHERE id=? AND status='PENDING'",status,result,reason,wire(p),id);
        if(count!=1)throw new PublicFailure(409,"PROPOSAL_CONFLICT");return audit.append(a,"PROPOSAL_"+status,uuid(p.path("meta").path("articleId").asText()),id,before,hash(p));
    }
    /** T07's local invalidation joins the head transaction; T11 still owns other domains/outbox. */
    public void staleOther(ActorContext a,UUID article,UUID current) {
        VersionService.requireTransaction();
        var ids=db.query("SELECT id FROM editorial.change_proposal WHERE article_id=? AND status='PENDING' AND base_version_id<>? FOR UPDATE",(rs,n)->rs.getObject(1,UUID.class),article,current);
        for(var id:ids) {var p=(ObjectNode)read(a,id,false);String before=hash(p);p.put("status","STALE");((ObjectNode)p.path("meta")).put("stale",true);
            db.update("UPDATE editorial.change_proposal SET status='STALE',document=?::jsonb,lock_version=lock_version+1 WHERE id=?",wire(p),id);audit.append(a,"PROPOSAL_STALE",article,id,before,hash(p));}
    }
    public JsonNode list(ActorContext a,UUID article,String status,String token,int limit) {
        articles.job(a,article,false);PageCursor.limit(limit);if(status!=null&&!Set.of("PENDING","ACCEPTED","REJECTED","STALE").contains(status))fail("INVALID_STATUS");
        String binding=cursor.scope(a,article,"proposals",status),last=cursor.read(token,binding);
        var args=new ArrayList<Object>();args.add(article);args.add(a.ownerId());String sql="SELECT document::text FROM editorial.change_proposal WHERE article_id=? AND owner_id=?";
        if(status!=null){sql+=" AND status=?";args.add(status);}if(last!=null){sql+=" AND id<?";args.add(uuid(last));}sql+=" ORDER BY id DESC LIMIT ?";args.add(limit+1);
        var rows=db.query(sql,(rs,n)->parse(rs.getString(1)),args.toArray());var page=JSON.createObjectNode();var items=page.putArray("items");rows.stream().limit(limit).forEach(items::add);
        page.put("nextCursor",rows.size()>limit?cursor.write(rows.get(limit-1).path("meta").path("id").asText(),binding):null);return page;
    }
}

package com.example.editorial.article.job;

import com.example.editorial.article.ast.ArticleAst;
import com.example.editorial.shared.*;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.*;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.*;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.security.MessageDigest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import static com.example.editorial.article.ast.ArticleAst.*;

/** All writes join T03's transaction; no public method starts a nested independent business transaction. */
public final class ArticleService implements Ownership.Resolver {
    private final JdbcTemplate db;
    private final ArticlePorts.Snapshots snapshots;
    private final ArticlePorts.Objects objects;
    private final ArticlePorts.Audit audit;
    private final ArticlePorts.Evidence evidence;
    private final ArticlePorts.Changes changes;
    private final ArticlePorts.Schema schema;
    private final byte[] cursorKey;
    public ArticleService(JdbcTemplate db, ArticlePorts.Snapshots snapshots, ArticlePorts.Objects objects,
            ArticlePorts.Audit audit, ArticlePorts.Evidence evidence, ArticlePorts.Changes changes, ArticlePorts.Schema schema, String cursorKey) {
        this.db=db; this.snapshots=snapshots; this.objects=objects; this.audit=audit; this.evidence=evidence; this.changes=changes; this.schema=schema;
        if (cursorKey == null || cursorKey.length() < 32) throw new IllegalArgumentException("Article cursor key required");
        this.cursorKey=cursorKey.getBytes(StandardCharsets.UTF_8);
    }
    static void transaction() { if (!TransactionSynchronizationManager.isActualTransactionActive()) throw new IllegalStateException("Article write requires transaction"); }
    public void validate(JsonNode body, String definition) {
        try { schema.validate(body, definition); } catch (IllegalArgumentException e) { throw new PublicFailure(422,"VALIDATION_FAILED"); }
        if (!body.isObject() || body.isEmpty()) fail("VALIDATION_FAILED");
    }
    private static JsonNode node(String s) { try { return JSON.readTree(s); } catch(Exception e) { throw new IllegalStateException("Stored article is invalid"); } }
    private static String wire(JsonNode n) { return new String(CanonicalRequest.canonical(n), StandardCharsets.UTF_8); }
    public ObjectNode job(ActorContext actor, UUID id, boolean lock) {
        var rows=db.query("SELECT summary::text FROM editorial.article_job WHERE id=? AND owner_id=?" + (lock ? " FOR UPDATE" : ""),
                (rs,n)->(ObjectNode)node(rs.getString(1)), id,actor.ownerId());
        if (rows.isEmpty()) throw new PublicFailure(404,"NOT_FOUND"); return rows.getFirst();
    }
    public void writable(UUID id) { if (Boolean.TRUE.equals(db.queryForObject("SELECT deletion_pending FROM editorial.article_job WHERE id=?",Boolean.class,id))) throw new PublicFailure(409,"DELETION_PENDING"); }
    public JsonNode readVersion(ActorContext actor, UUID article, UUID version) {
        job(actor,article,false);
        var rows=db.query("SELECT document::text FROM editorial.article_version WHERE article_id=? AND id=?",(rs,n)->node(rs.getString(1)),article,version);
        if(rows.isEmpty()) throw new PublicFailure(404,"NOT_FOUND"); return rows.getFirst();
    }
    public void validateSpan(ActorContext actor,UUID article,UUID version,JsonNode span) {ArticleAst.versionSpan(readVersion(actor,article,version),span);}
    public ObjectNode artifact(ActorContext actor, UUID id) {
        // One statement gives a coherent head/rights/version snapshot even while another request patches the job.
        var rows=db.query("SELECT j.summary::text,j.original_rights_basis::text,v.document::text FROM editorial.article_job j JOIN editorial.article_version v ON v.article_id=j.id AND v.id=j.current_version_id WHERE j.id=? AND j.owner_id=?",
            (rs,n)-> {
                var summary=node(rs.getString(1)); var history=node(rs.getString(2)); var v=node(rs.getString(3)); JsonNode rights=null;
                for(var r:history) if(r.path("versionId").equals(summary.path("currentVersionId")) && r.path("contentHash").equals(v.path("meta").path("contentHash"))) rights=r;
                if(rights==null) throw new PublicFailure(503,"RIGHTS_SNAPSHOT_NOT_READY");
                var out=JSON.createObjectNode(); out.set("job",summary); out.set("rightsSnapshot",rights);
                out.putArray("artifacts").add(refJson(v)); return out;
            },id,actor.ownerId());
        if(rows.isEmpty()) throw new PublicFailure(404,"NOT_FOUND"); return rows.getFirst();
    }
    private static ObjectNode refJson(JsonNode v) { var m=v.path("meta"); return JSON.createObjectNode().put("id",m.path("id").asText()).put("articleId",m.path("articleId").asText()).put("versionId",m.path("id").asText()).put("kind","VERSION").put("hash",m.path("contentHash").asText()).put("stale",false); }
    /** Staging is deliberately outside the business transaction. A losing replay leaves only a TTL orphan. */
    public record PreparedOriginal(UUID article, UUID version, String title, String subtitle, JsonNode ast, JsonNode document, JsonNode object) {}
    public PreparedOriginal prepareCreate(ActorContext actor, JsonNode request) {
        actor.requireHuman(); validate(request,"CreateArticleRequest");
        var original=request.path("original"); String title=original.path("title").asText(); text(title);
        var ast=ArticleAst.parse(original.path("format").asText(),original.path("content").asText());
        return prepareOriginal(actor,title,null,ast,hash(request));
    }
    private PreparedOriginal prepareOriginal(ActorContext actor,String title,String subtitle,JsonNode ast,String inputHash) {
        if(TransactionSynchronizationManager.isActualTransactionActive()) throw new IllegalStateException("Stage outside the business transaction");
        UUID id=UUID.randomUUID(),version=UUID.randomUUID();
        var doc=document(actor,id,version,1,null,null,"ORIGINAL","USER",title,subtitle,ast,"Original imported",JSON.createArrayNode(),null,inputHash);
        var object=objects.stage(actor,CanonicalRequest.canonical(doc));return new PreparedOriginal(id,version,title,subtitle,ast,doc,object);
    }
    public UUID create(ActorContext actor,JsonNode request,PreparedOriginal prepared) {
        transaction(); actor.requireHuman(); validate(request,"CreateArticleRequest");
        return insert(actor,prepared,request.path("skillVersionId").asText(),request.path("targetLength").asInt(),request.path("budget"),
            request.path("rightsBasis").asText(),request.path("rightsNotes").asText("未提供补充说明"),request.path("rightsEvidenceIds").isMissingNode()?JSON.createArrayNode():request.path("rightsEvidenceIds"));
    }
    private UUID insert(ActorContext actor,PreparedOriginal prepared,String skill,int target,JsonNode budget,String basis,String notes,JsonNode ids) {
        UUID id=prepared.article(),version=prepared.version(); String title=prepared.title(),subtitle=prepared.subtitle(); JsonNode ast=prepared.ast(); String now=Instant.now().toString();
        JsonNode style=snapshots.read(actor,uuid(skill));
        String contentHash=contentHash(title,subtitle,ast);
        JsonNode rights=rights(actor,id,version,contentHash,basis,notes,ids);
        var history=JSON.createArrayNode().add(rights);
        var summary=JSON.createObjectNode().put("id",id.toString()).put("ownerId",actor.ownerId().toString()).put("name",title)
                .put("originalVersionId",version.toString()).put("currentVersionId",version.toString()).put("skillVersionId",skill)
                .put("targetLength",target).put("budget",budget.path("limit").asText()).put("currency","USD")
                .put("spentAmount","0.000000").put("reservedAmount","0.000000").put("status","CREATED").put("lockVersion",1).put("archived",false).put("updatedAt",now);
        db.update("INSERT INTO editorial.article_job(id,owner_id,name,skill_version_id,target_length,budget_limit,currency,summary,style_snapshot,original_rights_basis,created_by,updated_by) VALUES(?,?,?,?,?,?,'USD',?::jsonb,?::jsonb,?::jsonb,?,?)",
                id,actor.ownerId(),title,uuid(skill),target,new BigDecimal(budget.path("limit").asText()),wire(summary),wire(style),wire(history),actor.actorId(),actor.actorId());
        insertVersion(actor,prepared.document(),prepared.object(),style);
        db.update("UPDATE editorial.article_job SET original_version_id=?,current_version_id=? WHERE id=?",version,version,id);
        audit.append(actor,"ARTICLE_CREATED",id,version,null,contentHash); return id;
    }
    private JsonNode rights(ActorContext actor,UUID article,UUID version,String contentHash,String basis,String notes,JsonNode ids) {
        evidence.require(actor,article,version,contentHash,ids);
        var r=JSON.createObjectNode().put("id",UUID.randomUUID().toString()).put("articleId",article.toString()).put("versionId",version.toString())
            .put("contentHash",contentHash).put("basis",basis).put("notes",notes).put("recordedBy",actor.actorId().toString()).put("recordedAt",Instant.now().toString());
        r.set("evidenceIds",ids.deepCopy()); r.put("hash",hash(r)); return r;
    }
    private JsonNode document(ActorContext actor,UUID article,UUID id,int no,UUID parent,UUID restored,String kind,String source,String title,String subtitle,JsonNode ast,String summary,JsonNode mappings,UUID execution,String inputHash) {
        var meta=JSON.createObjectNode().put("id",id.toString()).put("articleId",article.toString()).put("ownerId",actor.ownerId().toString()).put("versionId",id.toString())
            .put("executionId",execution==null?null:execution.toString()).put("schemaVersion",SCHEMA).put("inputHash",inputHash).put("contentHash",contentHash(title,subtitle,ast))
            .put("stale",false).put("createdBy",actor.actorId().toString()).put("createdAt",Instant.now().toString()).put("traceId",actor.traceId().toString()).put("mode","REAL");
        var doc=JSON.createObjectNode().put("versionNo",no).put("parentVersionId",parent==null?null:parent.toString()).put("restoredFromVersionId",restored==null?null:restored.toString())
            .put("kind",kind).put("changeSource",source).put("title",title).put("subtitle",subtitle).put("plainText",plainText(ast)).put("changeSummary",summary);
        doc.set("meta",meta); doc.set("contentAst",ast); doc.set("blockMappings",mappings);
        if(length(title)<1 || length(title)>300 || subtitle!=null&&(length(subtitle)<1||length(subtitle)>500)
                || length(plainText(ast))>200000 || length(summary)<1 || length(summary)>1000
                || !Set.of("AI","USER","SYSTEM").contains(source) || !inputHash.matches("[a-f0-9]{64}")
                || !mappings.isArray() || mappings.size()>1000) fail("INVALID_VERSION");
        for(var mapping:mappings) validate(mapping,"BlockMapping");
        return doc;
    }
    private void insertVersion(ActorContext actor,JsonNode doc,JsonNode object,JsonNode style) {
        var meta=doc.path("meta"); UUID id=uuid(meta.path("id").asText()),article=uuid(meta.path("articleId").asText());
        if(!meta.path("ownerId").asText().equals(actor.ownerId().toString())) throw new PublicFailure(404,"OWNER_MISMATCH");
        if(!hash(doc).equals(object.path("hash").asText()) || !contentHash(doc.path("title").asText(),doc.path("subtitle").isNull()?null:doc.path("subtitle").asText(),doc.path("contentAst")).equals(meta.path("contentHash").asText())
                || !plainText(doc.path("contentAst")).equals(doc.path("plainText").asText())) fail("VERSION_HASH_MISMATCH");
        db.update("INSERT INTO editorial.article_version(id,article_id,version_no,parent_version_id,restored_from_version_id,kind,document,content_hash,input_hash,style_snapshot,object_ref,created_by) VALUES(?,?,?,?,?,?,?::jsonb,?,?,?::jsonb,?::jsonb,?)",
                id,article,doc.path("versionNo").asInt(),doc.path("parentVersionId").isNull()?null:uuid(doc.path("parentVersionId").asText()),doc.path("restoredFromVersionId").isNull()?null:uuid(doc.path("restoredFromVersionId").asText()),doc.path("kind").asText(),wire(doc),meta.path("contentHash").asText(),meta.path("inputHash").asText(),wire(style),wire(object),actor.actorId());
        objects.commit(actor,object,new Ownership.ArtifactRef(id,article,id,"VERSION_OBJECT",object.path("hash").asText(),false));
    }
    public void patch(ActorContext actor,UUID id,JsonNode request) {
        transaction(); actor.requireHuman(); validate(request,"PatchArticleRequest"); var before=job(actor,id,true); writable(id); var after=before.deepCopy();
        boolean gen=(request.has("skillVersionId")&&!request.path("skillVersionId").equals(before.path("skillVersionId"))) || (request.has("targetLength")&&!request.path("targetLength").equals(before.path("targetLength")));
        boolean right=request.has("rightsUpdate");
        if ((gen||right) && before.path("status").asText().equals("CANCELLED")) throw new PublicFailure(409,"CANCELLED");
        JsonNode style=node(db.queryForObject("SELECT style_snapshot::text FROM editorial.article_job WHERE id=?",String.class,id));
        if(request.has("skillVersionId") && !request.path("skillVersionId").equals(before.path("skillVersionId"))) style=snapshots.read(actor,uuid(request.path("skillVersionId").asText()));
        for(String field:List.of("name","targetLength","skillVersionId","archived")) if(request.has(field)) after.set(field,request.path(field));
        if(request.has("name")) text(request.path("name").asText());
        if(request.has("budget")) {
            var amount=new BigDecimal(request.path("budget").path("limit").asText());
            if(amount.compareTo(new BigDecimal(before.path("budget").asText()))<0) throw new PublicFailure(409,"BUDGET_DECREASE_NOT_SUPPORTED");
            after.put("budget",amount.toPlainString());
        }
        var history=(ArrayNode)node(db.queryForObject("SELECT original_rights_basis::text FROM editorial.article_job WHERE id=?",String.class,id));
        if(right) {
            var u=request.path("rightsUpdate"); var current=readVersion(actor,id,uuid(before.path("currentVersionId").asText()));
            if(!u.path("versionId").equals(before.path("currentVersionId")) || !u.path("contentHash").equals(current.path("meta").path("contentHash"))) throw new PublicFailure(409,"RIGHTS_VERSION_MISMATCH");
            history.add(rights(actor,id,uuid(u.path("versionId").asText()),u.path("contentHash").asText(),u.path("basis").asText(),u.path("notes").asText(),u.path("evidenceIds")));
        }
        if(gen||right) {
            var oldInputs=JSON.createObjectNode(); oldInputs.set("job",before.deepCopy()); oldInputs.set("style",node(db.queryForObject("SELECT style_snapshot::text FROM editorial.article_job WHERE id=?",String.class,id)));
            var newInputs=JSON.createObjectNode(); newInputs.set("job",after.deepCopy()); newInputs.set("style",style.deepCopy()); newInputs.set("rights",history.get(history.size()-1).deepCopy());
            changes.apply(actor,id,oldInputs,newInputs,gen,right); after.put("status","NEEDS_REVISION");
        }
        after.put("lockVersion",before.path("lockVersion").asLong()+1).put("updatedAt",Instant.now().toString());
        save(actor,id,after,style,history);
        audit.append(actor,right?"RIGHTS_UPDATED":gen?"GENERATION_INPUT_CHANGED":"ARTICLE_SETTINGS_CHANGED",id,id,hash(before),hash(after));
    }
    private void save(ActorContext actor,UUID id,JsonNode summary,JsonNode style,JsonNode rights) {
        db.update("UPDATE editorial.article_job SET name=?,skill_version_id=?,target_length=?,budget_limit=?,status=?,lock_version=?,summary=?::jsonb,style_snapshot=?::jsonb,original_rights_basis=?::jsonb,archived_at=?,updated_at=clock_timestamp(),updated_by=?,current_version_id=? WHERE id=?",
            summary.path("name").asText(),uuid(summary.path("skillVersionId").asText()),summary.path("targetLength").asInt(),new BigDecimal(summary.path("budget").asText()),summary.path("status").asText(),summary.path("lockVersion").asLong(),wire(summary),wire(style),wire(rights),summary.path("archived").asBoolean()?java.sql.Timestamp.from(Instant.now()):null,actor.actorId(),uuid(summary.path("currentVersionId").asText()),id);
    }
    public PreparedOriginal prepareClone(ActorContext actor,UUID source,JsonNode body) {
        actor.requireHuman(); validate(body,"CloneRequest"); job(actor,source,false); writable(source);
        var v=readVersion(actor,source,uuid(body.path("fromVersionId").asText()));
        return prepareOriginal(actor,v.path("title").asText(),v.path("subtitle").isNull()?null:v.path("subtitle").asText(),cloneAst(v.path("contentAst")),hash(body));
    }
    public UUID cloneArticle(ActorContext actor,UUID source,JsonNode body,PreparedOriginal prepared) {
        transaction(); actor.requireHuman(); validate(body,"CloneRequest"); var j=job(actor,source,true); writable(source); readVersion(actor,source,uuid(body.path("fromVersionId").asText()));
        var budget=JSON.createObjectNode().put("limit",j.path("budget").asText()).put("currency","USD");
        return insert(actor,prepared,body.path("skillVersionId").asText(),j.path("targetLength").asInt(),budget,"UNKNOWN","克隆稿需重新确认使用依据",JSON.createArrayNode());
    }
    public record PreparedVersion(UUID article,UUID base,String etag,JsonNode document,JsonNode object) {}
    /** T07 stages immutable bytes outside the transaction, then commits under ETag/base/fencing. */
    public PreparedVersion prepareVersion(ActorContext actor,UUID article,UUID base,String etag,String kind,String source,String title,String subtitle,JsonNode ast,String summary,JsonNode mappings,UUID execution,String inputHash,ArticleAst.References references) {
        return prepareVersionExtended(actor,article,base,etag,kind,source,title,subtitle,ast,summary,mappings,execution,inputHash,references,null,false);
    }
    /** Extended T07 entry: restored provenance and retained historical base are fixed BEFORE staging.
     * Number is provisional until locked append; RESTAGE_REQUIRED means rollback and stage new bytes. */
    public PreparedVersion prepareVersionExtended(ActorContext actor,UUID article,UUID base,String etag,String kind,String source,String title,String subtitle,JsonNode ast,String summary,JsonNode mappings,UUID execution,String inputHash,ArticleAst.References references,UUID restored,boolean retained) {
        if(TransactionSynchronizationManager.isActualTransactionActive()) throw new IllegalStateException("Stage outside the business transaction");
        var j=job(actor,article,false); writable(article); readVersion(actor,article,base);
        if(!retained) {
            Idempotency.requireEtag(etag,j.path("lockVersion").asLong());
            if(!uuid(j.path("currentVersionId").asText()).equals(base)) throw new PublicFailure(409,"STALE_INPUT");
        } else if(!source.equals("AI") || execution==null) fail("INVALID_RETAINED_VERSION");
        if(j.path("status").asText().equals("CANCELLED")) throw new PublicFailure(409,"CANCELLED");
        if(!Set.of("DRAFT","REVISION","MANUAL","RESTORE").contains(kind)) fail("INVALID_VERSION_KIND");
        if(kind.equals("RESTORE")!=(restored!=null)) fail("INVALID_RESTORE_SOURCE");
        if(restored!=null) readVersion(actor,article,restored);
        text(title); if(subtitle!=null) text(subtitle); ArticleAst.validate(ast,references); capacity(ast);
        UUID id=UUID.randomUUID(); int no=nextVersionNumber(article);
        var doc=document(actor,article,id,no,base,restored,kind,source,title,subtitle,ast.deepCopy(),summary,mappings.deepCopy(),execution,inputHash);
        ((ObjectNode)doc.path("meta")).put("stale",retained);
        return new PreparedVersion(article,base,etag,doc,objects.stage(actor,CanonicalRequest.canonical(doc)));
    }
    private int nextVersionNumber(UUID article) {
        long no=db.queryForObject("SELECT coalesce(max(version_no),0)::bigint+1 FROM editorial.article_version WHERE article_id=?",Long.class,article);
        if(no>Integer.MAX_VALUE) throw new PublicFailure(409,"VERSION_LIMIT");return (int)no;
    }
    public List<JsonNode> versionPage(ActorContext actor,UUID article,long before,int limit) {
        job(actor,article,false);
        return db.query("SELECT document::text FROM editorial.article_version WHERE article_id=? AND version_no<? ORDER BY version_no DESC LIMIT ?",(rs,n)->node(rs.getString(1)),article,before,limit);
    }
    public UUID appendVersion(ActorContext actor,PreparedVersion prepared) {return appendVersionExtended(actor,prepared,false,null);}
    /** Caller has validated execution fencing in THIS transaction. Retained results never call moveHead.
     * executionStyle is the original persisted execution snapshot supplied by the authenticated T10 port. */
    public UUID appendVersionExtended(ActorContext actor,PreparedVersion prepared,boolean retained,JsonNode executionStyle) {
        transaction(); UUID article=prepared.article(); var j=job(actor,article,true); writable(article);
        if(j.path("status").asText().equals("CANCELLED")) throw new PublicFailure(409,"CANCELLED");
        readVersion(actor,article,prepared.base());
        if(!retained) {
            Idempotency.requireEtag(prepared.etag(),j.path("lockVersion").asLong());
            if(!j.path("currentVersionId").asText().equals(prepared.base().toString())) throw new PublicFailure(409,"STALE_INPUT");
        } else if(!prepared.document().path("changeSource").asText().equals("AI") || prepared.document().path("meta").path("executionId").isNull() || executionStyle==null) fail("INVALID_RETAINED_VERSION");
        if(prepared.document().path("meta").path("stale").asBoolean()!=retained) fail("INVALID_RETAINED_VERSION");
        if(prepared.document().path("versionNo").asInt()!=nextVersionNumber(article)) throw new PublicFailure(409,"RESTAGE_REQUIRED");
        JsonNode style=executionStyle==null?node(db.queryForObject("SELECT style_snapshot::text FROM editorial.article_job WHERE id=?",String.class,article)):executionStyle;
        insertVersion(actor,prepared.document(),prepared.object(),style); UUID id=uuid(prepared.document().path("meta").path("id").asText());
        audit.append(actor,retained?"VERSION_CONFLICT_RETAINED":"VERSION_APPENDED",article,id,null,prepared.document().path("meta").path("contentHash").asText()); return id;
    }
    public void moveHead(ActorContext actor,UUID article,UUID version,String etag) {
        transaction(); var j=job(actor,article,true); writable(article); Idempotency.requireEtag(etag,j.path("lockVersion").asLong());
        if(j.path("status").asText().equals("CANCELLED")) throw new PublicFailure(409,"CANCELLED");
        var v=readVersion(actor,article,version); var before=j.deepCopy();
        j.put("currentVersionId",version.toString()).put("lockVersion",j.path("lockVersion").asLong()+1).put("updatedAt",Instant.now().toString());
        changes.apply(actor,article,before,j.deepCopy(),true,true); j.put("status","NEEDS_REVISION");
        var history=(ArrayNode)node(db.queryForObject("SELECT original_rights_basis::text FROM editorial.article_job WHERE id=?",String.class,article));
        history.add(rights(actor,article,version,v.path("meta").path("contentHash").asText(),"UNKNOWN","新版本需重新确认使用依据",JSON.createArrayNode()));
        save(actor,article,j,node(db.queryForObject("SELECT style_snapshot::text FROM editorial.article_job WHERE id=?",String.class,article)),history);
        audit.append(actor,"VERSION_HEAD_CHANGED",article,version,hash(before),hash(j));
    }
    public JsonNode list(ActorContext actor,String status,String query,String cursor,int limit) {
        if(limit<1||limit>100||query!=null&&(length(query)<1||length(query)>300)) fail("INVALID_PAGE");
        if(status!=null) { var check=JSON.createObjectNode(); check.put("status",status); /* status validated against frozen enum by projection below */
            if(!Set.of("CREATED","ANALYZING","ANALYZED","FACT_CHECKING","FACT_VERIFIED","WRITING","DRAFTED","REVIEWING","REVIEWED","REVISING","REVISED","FACT_RECHECKING","FACT_RECHECKED","IMAGE_PLANNING","IMAGE_SEARCHING","IMAGE_GENERATING","WAITING_IMAGE_SELECTION","IMAGES_READY","FINAL_QA","READY_FOR_REVIEW","HUMAN_REVIEW","APPROVED","REJECTED","NEEDS_REVISION","WAITING_MANUAL","PAUSED","FAILED","CANCELLED").contains(status)) fail("INVALID_STATUS"); }
        String filter=hash(JSON.createObjectNode().put("owner",actor.ownerId().toString()).put("status",status).put("query",query));
        String last=null;
        if(cursor!=null) {
            try { var parts=cursor.split("\\.",-1); if(parts.length!=2 || !MessageDigest.isEqual(sign(parts[0]),Base64.getUrlDecoder().decode(parts[1]))) fail("INVALID_CURSOR");
                var c=node(new String(Base64.getUrlDecoder().decode(parts[0]),StandardCharsets.UTF_8)); if(!filter.equals(c.path("filter").asText())) fail("INVALID_CURSOR"); last=uuid(c.path("last").asText()).toString(); }
            catch(Exception e) { throw new PublicFailure(422,"INVALID_CURSOR"); }
        }
        // UUID order is immutable. Renaming/updating an article cannot move it between pages.
        var args=new ArrayList<Object>(); args.add(actor.ownerId()); String sql="SELECT summary::text FROM editorial.article_job WHERE owner_id=?";
        if(status!=null) {sql+=" AND status=?";args.add(status);} if(query!=null) {sql+=" AND position(lower(?) in lower(name))>0";args.add(query);}
        if(last!=null) {sql+=" AND id<?";args.add(uuid(last));} sql+=" ORDER BY id DESC LIMIT ?";args.add(limit+1);
        var rows=db.query(sql,(rs,n)->node(rs.getString(1)),args.toArray()); var page=JSON.createObjectNode(); var items=page.putArray("items"); rows.stream().limit(limit).forEach(items::add);
        if(rows.size()>limit) {String payload=Base64.getUrlEncoder().withoutPadding().encodeToString(CanonicalRequest.canonical(JSON.createObjectNode().put("filter",filter).put("last",rows.get(limit-1).path("id").asText())));page.put("nextCursor",payload+"."+Base64.getUrlEncoder().withoutPadding().encodeToString(sign(payload)));} else page.putNull("nextCursor"); return page;
    }
    private byte[] sign(String value) { try { var mac=Mac.getInstance("HmacSHA256");mac.init(new SecretKeySpec(cursorKey,"HmacSHA256"));return mac.doFinal(value.getBytes(StandardCharsets.UTF_8)); } catch(Exception e){throw new IllegalStateException(e);} }
    public boolean supports(String kind) {return Set.of("ARTICLE","VERSION","VERSION_OBJECT").contains(kind);}
    public Ownership.Resolved resolve(String kind,UUID id) {
        String sql=kind.equals("ARTICLE")?"SELECT owner_id,id,id,NULL::text,deletion_pending FROM editorial.article_job WHERE id=?":
            // VERSION gates semantic reuse. VERSION_OBJECT authorizes physical retention of even
            // stale candidates, so committing their historical bytes does not imply a fresh input.
            // Deletion blocks new references of BOTH kinds; historical VERSION reads remain possible.
            "SELECT j.owner_id,j.id,v.id,"+(kind.equals("VERSION_OBJECT")?"v.object_ref->>'hash',j.deletion_pending":"v.content_hash,(j.deletion_pending OR coalesce((v.document->'meta'->>'stale')::boolean,false))")+" FROM editorial.article_version v JOIN editorial.article_job j ON j.id=v.article_id WHERE v.id=?";
        var rows=db.query(sql,(rs,n)->new Ownership.Resolved(rs.getObject(1,UUID.class),new Ownership.ArtifactRef(id,rs.getObject(2,UUID.class),kind.equals("ARTICLE")?null:rs.getObject(3,UUID.class),kind,rs.getString(4),rs.getBoolean(5))),id);return rows.isEmpty()?null:rows.getFirst();
    }
    public record ObjectOwner(UUID article,boolean revoked) {}
    public ObjectOwner objectOwner(String key) { var rows=db.query("SELECT j.id,j.deletion_pending FROM editorial.article_version v JOIN editorial.article_job j ON j.id=v.article_id WHERE v.object_ref->>'key'=?",(rs,n)->new ObjectOwner(rs.getObject(1,UUID.class),rs.getBoolean(2)),key);return rows.isEmpty()?null:rows.getFirst(); }
}

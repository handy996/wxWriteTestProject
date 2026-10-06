"""Produce a minimal reviewable T06 patch, never edit the approved shared source."""
from pathlib import Path
import difflib
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
PATH='backend/src/main/java/com/example/editorial/article/job/ArticleService.java'
def extend(source):
    start=source.index('        if(TransactionSynchronizationManager.isActualTransactionActive())',source.index('    public PreparedVersion prepareVersion('))
    end=source.index('    public void moveHead(',start)
    replacement='''        return prepareVersionExtended(actor,article,base,etag,kind,source,title,subtitle,ast,summary,mappings,execution,inputHash,references,null,false);
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
'''
    extended=source[:start]+replacement+source[end:]
    old='''            "SELECT j.owner_id,j.id,v.id,"+(kind.equals("VERSION_OBJECT")?"v.object_ref->>'hash'":"v.content_hash")+",j.deletion_pending FROM editorial.article_version v JOIN editorial.article_job j ON j.id=v.article_id WHERE v.id=?";'''
    new='''            // VERSION gates semantic reuse. VERSION_OBJECT authorizes physical retention of even
            // stale candidates, so committing their historical bytes does not imply a fresh input.
            // Deletion blocks new references of BOTH kinds; historical VERSION reads remain possible.
            "SELECT j.owner_id,j.id,v.id,"+(kind.equals("VERSION_OBJECT")?"v.object_ref->>'hash',j.deletion_pending":"v.content_hash,(j.deletion_pending OR coalesce((v.document->'meta'->>'stale')::boolean,false))")+" FROM editorial.article_version v JOIN editorial.article_job j ON j.id=v.article_id WHERE v.id=?";'''
    assert extended.count(old)==1, 'T06 resolver input changed; review required'
    return extended.replace(old,new)
if __name__=='__main__':
    before=(ROOT/PATH).read_text(encoding='utf-8');after=extend(before)
    (HERE/'t06-extension.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/'+PATH,tofile='b/'+PATH)),encoding='utf-8',newline='\n')

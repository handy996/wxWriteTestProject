package com.example.editorial.shared;

import java.util.List;
import java.util.Objects;
import java.util.UUID;

public final class Ownership {
    public record ArtifactRef(UUID id, UUID articleId, UUID versionId, String kind, String hash, boolean stale) {}
    public record Resolved(UUID ownerId, ArtifactRef ref) {}
    /** Resolve only metadata, before private content IO. null means absent; no adapter means 503. */
    public interface Resolver { boolean supports(String kind); Resolved resolve(String kind, UUID id); }
    private final List<Resolver> resolvers;
    public Ownership(List<Resolver> resolvers) { this.resolvers=List.copyOf(resolvers); }
    public ArtifactRef requireArticle(ActorContext actor, UUID article) { return resolve(actor,"ARTICLE",article,article).ref(); }
    private Resolved resolve(ActorContext actor,String kind,UUID id,UUID article) {
        var supported=resolvers.stream().filter(r->r.supports(kind)).toList();
        if(supported.size()!=1) throw new PublicFailure(503,"OWNERSHIP_NOT_READY");
        var result=supported.getFirst().resolve(kind,id);
        if(result==null || !actor.ownerId().equals(result.ownerId()) || !article.equals(result.ref().articleId())
                || !id.equals(result.ref().id()) || !kind.equals(result.ref().kind())) throw new PublicFailure(404,"OWNER_MISMATCH");
        return result;
    }
    public ArtifactRef require(ActorContext actor, UUID article, ArtifactRef supplied, boolean newCommit) {
        requireArticle(actor,article);
        var ref=resolve(actor,supplied.kind(),supplied.id(),article).ref();
        if(!article.equals(supplied.articleId()) || !Objects.equals(ref.versionId(),supplied.versionId())
                || !Objects.equals(ref.hash(),supplied.hash())) throw new PublicFailure(404,"OWNER_MISMATCH");
        if(newCommit && ref.stale()) throw new PublicFailure(409,"STALE_INPUT");
        return ref;
    }
}

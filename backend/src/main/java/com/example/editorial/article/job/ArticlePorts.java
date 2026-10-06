package com.example.editorial.article.job;

import com.example.editorial.shared.ActorContext;
import com.example.editorial.shared.Ownership;
import com.example.editorial.shared.PublicFailure;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.UUID;

/** Consumer-owned adapters; composition root alone imports other domains. No repositories cross this boundary. */
public final class ArticlePorts {
    private ArticlePorts() {}
    public interface Schema { void validate(JsonNode body, String definition); }
    /** Includes immutable Skill, full Prompt versions and policies; verifies owner/PUBLISHED before returning. */
    public interface Snapshots { JsonNode read(ActorContext actor, UUID skillVersionId); }
    public interface Objects {
        JsonNode stage(ActorContext actor, byte[] bytes);
        void commit(ActorContext actor, JsonNode object, Ownership.ArtifactRef ref);
    }
    public interface Audit { void append(ActorContext actor, String action, UUID article, UUID entity, String before, String after); }
    public interface Evidence { void require(ActorContext actor, UUID article, UUID version, String contentHash, JsonNode ids); }
    /** Mandatory transaction participant. Must fence old work and persist new generation/outbox before returning.
     * Receives deep snapshots; may not commit its own transaction or perform external IO. Any failure rolls back all participants. */
    public interface Changes { void apply(ActorContext actor, UUID article, JsonNode before, JsonNode after, boolean generationChanged, boolean rightsChanged); }
    /** T10 owns command persistence, replay and journal acknowledgement. Never wrap submit in sync Idempotency's DB transaction. */
    public interface Deletion {
        JsonNode preview(ActorContext actor, UUID article);
        com.example.editorial.shared.Idempotency.Response submit(ActorContext actor, UUID article, String path,
                String query, String key, String requestHash, String etag, byte[] body);
    }
    public static Changes unavailableChanges() { return (a,id,b,n,g,r) -> { throw new PublicFailure(503,"FEATURE_NOT_READY"); }; }
    public static Evidence unavailableEvidence() { return (a,id,v,h,ids) -> { if (!ids.isEmpty()) throw new PublicFailure(503,"RIGHTS_EVIDENCE_NOT_READY"); }; }
    public static Deletion unavailableDeletion() { return new Deletion() {
        public JsonNode preview(ActorContext a, UUID id) { throw new PublicFailure(503,"FEATURE_NOT_READY"); }
        public com.example.editorial.shared.Idempotency.Response submit(ActorContext a, UUID id, String p, String q, String k, String h, String e, byte[] b) { throw new PublicFailure(503,"FEATURE_NOT_READY"); }
    }; }
}

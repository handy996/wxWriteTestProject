package com.example.editorial.article.version;

import com.example.editorial.article.ast.ArticleAst;
import com.example.editorial.article.job.ArticleService;
import com.example.editorial.shared.*;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.*;

/** Consumer contracts, wired only in the composition root. No network IO inside a participant. */
public final class VersionPorts {
    private VersionPorts() {}
    public record Draft(UUID base, UUID restoredFrom, String etag, String kind, String source,
            String title, String subtitle, JsonNode ast, String summary, JsonNode mappings,
            UUID execution, String inputHash, boolean retained) {}
    /** T06 owns every version row and head write. A raced provisional number must be restaged. */
    public interface Store {
        ArticleService.PreparedVersion prepare(ActorContext a, UUID article, Draft draft, ArticleAst.References refs);
        UUID append(ActorContext a, ArticleService.PreparedVersion p, boolean retained, JsonNode executionStyle);
        List<JsonNode> page(ActorContext a, UUID article, long before, int limit);
    }
    /** Verify owner/article/base association AND candidate content applicability (claim quotes, Unicode
     * spans/block hashes and slot anchors). Called again under the commit lock; only transactional reads,
     * no remote IO. A UUID existence check is not sufficient. */
    public interface References { void require(ActorContext a, UUID article, UUID base, String kind, UUID id, JsonNode content); }
    public interface Audit { UUID append(ActorContext a, String action, UUID article, UUID entity, String before, String after); }
    /** MUST run under the article lock, BEFORE version insertion; persist fencing in caller transaction. */
    public interface HumanFence { void invalidate(ActorContext a, UUID article, UUID base); }
    public interface HeadChanged { void apply(ActorContext a,UUID article,UUID version); }
    public record Execution(UUID agentExecutionId, JsonNode style, boolean retained, UUID resultVersionId) {}
    /** T10 authenticates persisted execution/context/output binding, actual token, deletion/cancel and original
     * immutable configuration. Retention is permitted only for a proven superseded generation, never an
     * arbitrary stale/forged token. complete persists result uniqueness and conflict in the SAME transaction.
     * T16/T17 persist WriterOutput fact/review obligations there; incomplete adapters MUST throw 503. */
    public interface Executions {
        Execution inspect(ActorContext a, JsonNode context, JsonNode output);
        void complete(ActorContext a, JsonNode context, JsonNode output, UUID result, boolean conflict);
    }
    public static References unavailableReferences() { return (a,j,b,k,id,content)->{throw new PublicFailure(503,"REFERENCE_VALIDATION_NOT_READY");}; }
    public static HumanFence unavailableFence() { return (a,j,b)->{throw new PublicFailure(503,"FEATURE_NOT_READY");}; }
    public static Executions unavailableExecutions() { return new Executions() {
        public Execution inspect(ActorContext a, JsonNode c, JsonNode o) {throw new PublicFailure(503,"FEATURE_NOT_READY");}
        public void complete(ActorContext a, JsonNode c, JsonNode o, UUID v, boolean conflict) {throw new PublicFailure(503,"FEATURE_NOT_READY");}
    }; }
}

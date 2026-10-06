package com.example.editorial.article.job;

import com.example.editorial.shared.*;
import com.example.editorial.article.ast.ArticleAst;
import com.fasterxml.jackson.databind.JsonNode;
import java.time.*;
import java.util.*;
import org.springframework.transaction.support.TransactionSynchronizationManager;

/** ADR-006 handoff protocol, no scheduler/operations table. Not wired until T10/T37 supply durable adapters. */
public final class DeletionHandoff implements ArticlePorts.Deletion {
    public record Impact(UUID article,UUID owner,long lockVersion,int versions,int approvals,int objects,
                         List<String> retained,List<String> holds,boolean complete,boolean retentionKnown,Instant expiresAt) {
        public Impact {retained=List.copyOf(retained);holds=List.copyOf(holds);}
    }
    public record Command(UUID article,UUID deletion,UUID owner,Idempotency.Response accepted,boolean journalAcknowledged) {}
    /** Implements durable preview lookup and command scope=(owner,method+route,key). prepare must authorize,
     * then replay, then invoke Guard for NEW commands under job lock; it persists fence+command atomically.
     * All methods return after transaction completion. No physical purge until receipt is durable. */
    public interface Commands {
        Impact preview(ActorContext actor,UUID article,Instant expiresAt);
        Command prepare(ActorContext actor,UUID article,String path,String query,String key,String requestHash,byte[] body,Guard guard);
        void acknowledge(Command command,Receipt receipt);
    }
    @FunctionalInterface public interface Guard {void check(Impact savedPreview,long currentLock);}
    /** Independent recovery domain; implementation verifies signatures/chain and idempotently returns same receipt. */
    public interface Journal {Receipt requested(UUID article,UUID deletion);}
    public record Receipt(UUID article,UUID deletion,String signedHead) {}
    private final Commands commands;private final Journal journal;private final Clock clock;
    public DeletionHandoff(Commands commands,Journal journal,Clock clock) {this.commands=commands;this.journal=journal;this.clock=clock;}
    public JsonNode preview(ActorContext actor,UUID article) {
        Impact impact=commands.preview(actor,article,clock.instant().plus(Duration.ofMinutes(15)));
        scope(actor,article,impact);if(!impact.complete())throw new PublicFailure(503,"DELETION_IMPACT_NOT_READY");return dto(impact);
    }
    static JsonNode dto(Impact i) {
        var n=ArticleAst.JSON.createObjectNode().put("articleId",i.article().toString()).put("lockVersion",i.lockVersion())
            .put("versionCount",i.versions()).put("approvalCount",i.approvals()).put("objectCount",i.objects()).put("backupRetentionDays",30).put("expiresAt",i.expiresAt().toString());
        n.set("retainedAuditFields",ArticleAst.JSON.valueToTree(i.retained()));n.set("holds",ArticleAst.JSON.valueToTree(i.holds()));
        n.put("impactHash",ArticleAst.hash(n));return n;
    }
    private static void scope(ActorContext a,UUID article,Impact i) {if(!a.ownerId().equals(i.owner())||!article.equals(i.article()))throw new PublicFailure(404,"NOT_FOUND");}
    public Idempotency.Response submit(ActorContext actor,UUID article,String path,String query,String key,String requestHash,String etag,byte[] bytes) {
        outsideTransaction();var body=CanonicalRequest.parse(bytes);
        if(key==null||requestHash==null)throw new PublicFailure(428,"IDEMPOTENCY_REQUIRED");ArticleAst.uuid(key);
        if(!CanonicalRequest.hash("POST",CanonicalRequest.route(path,query),bytes).equals(requestHash))throw new PublicFailure(422,"REQUEST_HASH_MISMATCH");
        Command command=commands.prepare(actor,article,path,query,key,requestHash,bytes,(impact,currentLock)-> {
            scope(actor,article,impact); Idempotency.requireEtag(etag,currentLock);
            if(!impact.complete())throw new PublicFailure(503,"DELETION_IMPACT_NOT_READY");
            if(!impact.retentionKnown()||!impact.holds().isEmpty())throw new PublicFailure(409,"DELETION_HOLD");
            if(impact.lockVersion()!=currentLock)throw new PublicFailure(412,"ETAG_MISMATCH");
            if(!clock.instant().isBefore(impact.expiresAt())||!dto(impact).path("impactHash").equals(body.path("impactHash")))throw new PublicFailure(409,"DELETION_IMPACT_EXPIRED");
        });
        if(!command.article().equals(article)||!command.owner().equals(actor.ownerId()))throw new PublicFailure(404,"NOT_FOUND");
        outsideTransaction();
        if(!command.journalAcknowledged()) {
            Receipt receipt;
            try {receipt=journal.requested(article,command.deletion());}
            catch(RuntimeException e) {throw new PublicFailure(503,"DELETION_JOURNAL_UNAVAILABLE");}
            if(receipt==null||!article.equals(receipt.article())||!command.deletion().equals(receipt.deletion())||receipt.signedHead()==null||receipt.signedHead().isBlank())throw new PublicFailure(503,"DELETION_JOURNAL_UNAVAILABLE");
            commands.acknowledge(command,receipt); // Failure leaves durable command + external REQUESTED, never a 202.
        }
        outsideTransaction();
        if(command.accepted().status()!=202)throw new PublicFailure(503,"DELETION_COMMAND_INVALID");return command.accepted();
    }
    private static void outsideTransaction() {if(TransactionSynchronizationManager.isActualTransactionActive())throw new IllegalStateException("External journal must not hold a database transaction");}
}

package com.example.editorial.audit;

import com.example.editorial.shared.ActorContext;
import java.time.Instant;
import java.util.UUID;

public interface AuditSink {
    record Event(String action,UUID articleId,String entityType,UUID entityId,String beforeHash,String afterHash) {}
    record AuditRecord(UUID id,UUID actorId,String actorType,String action,UUID articleId,String entityType,
                       UUID entityId,String beforeHash,String afterHash,UUID traceId,Instant createdAt) {}
    /** Requires caller's transaction. Failure marks it rollback-only, even if caller catches the error. */
    AuditRecord append(ActorContext actor,Event event);
}

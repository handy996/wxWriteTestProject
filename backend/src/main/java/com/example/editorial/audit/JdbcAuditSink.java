package com.example.editorial.audit;

import com.example.editorial.shared.*;
import java.util.UUID;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.*;
import org.springframework.transaction.support.TransactionTemplate;

public final class JdbcAuditSink implements AuditSink {
    private final JdbcTemplate db; private final TransactionTemplate mandatory;
    public JdbcAuditSink(JdbcTemplate db,PlatformTransactionManager manager) {
        this.db=db; mandatory=new TransactionTemplate(manager); mandatory.setPropagationBehavior(TransactionDefinition.PROPAGATION_MANDATORY);
    }
    @Override public AuditRecord append(ActorContext actor,Event e) {
        return mandatory.execute(status->{
            try {
                // Metadata only: no arbitrary detail/message/body fields are accepted by this interface.
                if(!e.action().matches("[A-Z][A-Z0-9_]{0,79}") || !e.entityType().matches("[A-Z][A-Z0-9_]{0,79}"))
                    throw new IllegalArgumentException();
                UUID id=UUID.randomUUID();
                return db.queryForObject("INSERT INTO editorial.audit_log(id,actor_id,actor_type,action,article_id,entity_type,entity_id,before_hash,after_hash,trace_id) VALUES (?,?,?,?,?,?,?,?,?,?) RETURNING created_at",
                    (rs,n)->new AuditRecord(id,actor.actorId(),actor.actorType(),e.action(),e.articleId(),e.entityType(),e.entityId(),e.beforeHash(),e.afterHash(),actor.traceId(),rs.getTimestamp(1).toInstant()),
                    id,actor.actorId(),actor.actorType(),e.action(),e.articleId(),e.entityType(),e.entityId(),e.beforeHash(),e.afterHash(),actor.traceId());
            } catch(RuntimeException failure){throw new PublicFailure(503,"AUDIT_WRITE_FAILED");}
        });
    }
}

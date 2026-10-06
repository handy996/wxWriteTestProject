package com.example.editorial.settings.policy;

import com.example.editorial.audit.AuditSink;
import com.example.editorial.shared.ActorContext;
import com.example.editorial.shared.CanonicalRequest;
import com.example.editorial.shared.PublicFailure;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.List;
import java.util.UUID;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

/** Immutable published prompt baselines. Published templates are never overwritten; edits produce a new version. */
public final class PromptService {
    private final JdbcTemplate db;
    private final TransactionTemplate tx;
    private final AuditSink audit;

    public PromptService(JdbcTemplate db, PlatformTransactionManager tx, AuditSink audit) {
        this.db = db; this.tx = new TransactionTemplate(tx); this.audit = audit;
    }

    public PromptVersion getById(UUID id) {
        List<PromptVersion> rows = db.query(
            "SELECT id, agent_name, version, system_template, user_template, output_schema::text, hash, status, created_by, created_at, lock_version FROM editorial.prompt_version WHERE id=?",
            (rs, n) -> new PromptVersion(
                rs.getObject(1, UUID.class), rs.getString(2), rs.getString(3), rs.getString(4), rs.getString(5),
                JsonIO.parse(rs.getString(6)), rs.getString(7), PublicationStatus.valueOf(rs.getString(8)),
                rs.getObject(9, UUID.class), rs.getTimestamp(10).toInstant(), rs.getLong(11)), id);
        if (rows.isEmpty()) throw new PublicFailure(404, "PROMPT_NOT_FOUND");
        return rows.getFirst();
    }

    /** Idempotent baseline seed keyed by (agentName, version). Hash is server-computed from templates + schema. */
    public PromptVersion seed(ActorContext actor, String agentName, String version,
                              String systemTemplate, String userTemplate, JsonNode outputSchema) {
        if (outputSchema == null || !outputSchema.isObject())
            throw new IllegalArgumentException("prompt output schema must be an object");
        String hash = Hashing.ofPrompt(systemTemplate, userTemplate, outputSchema);
        return tx.execute(status -> {
            db.execute("SET LOCAL lock_timeout='2000ms'");
            db.queryForObject("SELECT pg_advisory_xact_lock(?)", Object.class,
                    CanonicalRequest.lockKey("T05_PROMPT|" + agentName + "|" + version));
            List<UUID> existing = db.query("SELECT id FROM editorial.prompt_version WHERE agent_name=? AND version=?",
                    (rs, n) -> rs.getObject(1, UUID.class), agentName, version);
            if (!existing.isEmpty()) return getById(existing.getFirst());
            UUID id = UUID.randomUUID();
            db.update("INSERT INTO editorial.prompt_version(id, agent_name, version, system_template, user_template, output_schema, hash, status, created_by) "
                    + "VALUES (?::uuid, ?, ?, ?, ?, ?::jsonb, ?, 'PUBLISHED', ?)",
                    id, agentName, version, systemTemplate, userTemplate, JsonIO.text(outputSchema), hash, actor.actorId());
            audit.append(actor, new AuditSink.Event("PROMPT_LOADED", null, "PROMPT_VERSION", id, null, hash));
            return getById(id);
        });
    }

    public PromptVersion getPublished(String agentName) {
        List<PromptVersion> rows = db.query(
            "SELECT id, agent_name, version, system_template, user_template, output_schema::text, hash, status, created_by, created_at, lock_version FROM editorial.prompt_version WHERE agent_name=? AND status='PUBLISHED' ORDER BY split_part(version,'.',1)::numeric DESC, split_part(version,'.',2)::numeric DESC, split_part(version,'.',3)::numeric DESC LIMIT 1",
            (rs, n) -> new PromptVersion(
                rs.getObject(1, UUID.class), rs.getString(2), rs.getString(3), rs.getString(4), rs.getString(5),
                JsonIO.parse(rs.getString(6)), rs.getString(7), PublicationStatus.valueOf(rs.getString(8)),
                rs.getObject(9, UUID.class), rs.getTimestamp(10).toInstant(), rs.getLong(11)), agentName);
        if (rows.isEmpty()) throw new PublicFailure(404, "PROMPT_NOT_FOUND");
        return rows.getFirst();
    }
}

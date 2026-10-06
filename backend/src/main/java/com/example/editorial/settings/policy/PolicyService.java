package com.example.editorial.settings.policy;

import com.example.editorial.audit.AuditSink;
import com.example.editorial.shared.ActorContext;
import com.example.editorial.shared.CanonicalRequest;
import com.example.editorial.shared.PublicFailure;
import com.example.editorial.storage.ObjectRef;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.List;
import java.util.UUID;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * Versioned platform hard policies. Rules are held inline in {@code policy_version.rules} (JSONB); the
 * {@link PolicySnapshot} exposes a content-addressed {@link ObjectRef} whose hash/size are recomputed from
 * the actual rules so consumers can verify they hold the exact frozen content without T05 maintaining a
 * separate global object store (policy rules are small, fixed, and not article-scoped).
 */
public final class PolicyService {
    private final JdbcTemplate db;
    private final TransactionTemplate tx;
    private final AuditSink audit;

    public PolicyService(JdbcTemplate db, PlatformTransactionManager tx, AuditSink audit) {
        this.db = db; this.tx = new TransactionTemplate(tx); this.audit = audit;
    }

    public PolicyVersion getById(UUID id) {
        List<PolicyVersion> rows = db.query(
            "SELECT id, policy_type, version, rules::text, hash, status, created_by, published_by, published_at, created_at, lock_version FROM editorial.policy_version WHERE id=?",
            (rs, n) -> new PolicyVersion(
                rs.getObject(1, UUID.class), PolicyType.valueOf(rs.getString(2)), rs.getString(3),
                JsonIO.parse(rs.getString(4)), rs.getString(5), PublicationStatus.valueOf(rs.getString(6)),
                rs.getObject(7, UUID.class), rs.getObject(8, UUID.class),
                rs.getTimestamp(9) == null ? null : rs.getTimestamp(9).toInstant(),
                rs.getTimestamp(10).toInstant(), rs.getLong(11)), id);
        if (rows.isEmpty()) throw new PublicFailure(404, "POLICY_NOT_FOUND");
        return rows.getFirst();
    }

    public PolicyVersion getPublished(PolicyType type) {
        List<PolicyVersion> rows = db.query(
            "SELECT id, policy_type, version, rules::text, hash, status, created_by, published_by, published_at, created_at, lock_version FROM editorial.policy_version WHERE policy_type=? AND status='PUBLISHED' ORDER BY split_part(version,'.',1)::numeric DESC, split_part(version,'.',2)::numeric DESC, split_part(version,'.',3)::numeric DESC LIMIT 1",
            (rs, n) -> new PolicyVersion(
                rs.getObject(1, UUID.class), PolicyType.valueOf(rs.getString(2)), rs.getString(3),
                JsonIO.parse(rs.getString(4)), rs.getString(5), PublicationStatus.valueOf(rs.getString(6)),
                rs.getObject(7, UUID.class), rs.getObject(8, UUID.class),
                rs.getTimestamp(9) == null ? null : rs.getTimestamp(9).toInstant(),
                rs.getTimestamp(10).toInstant(), rs.getLong(11)), type.name());
        if (rows.isEmpty()) throw new PublicFailure(404, "POLICY_NOT_FOUND");
        return rows.getFirst();
    }

    public PolicySnapshot snapshot(UUID id) {
        PolicyVersion p = getById(id);
        byte[] canonical = Hashing.canonicalBytes(p.rules());
        ObjectRef rules = new ObjectRef("policy-rules/" + p.type() + "/" + p.version(), p.hash(), canonical.length,
                "application/json", false);
        return new PolicySnapshot(p.id(), p.type(), p.version(), p.hash(), rules);
    }

    /** Idempotent baseline seed: (type,version) is the natural key; re-running never duplicates or rewrites. */
    public PolicyVersion seed(ActorContext actor, PolicyType type, String version, JsonNode rules) {
        if (rules == null || !rules.isObject()) throw new IllegalArgumentException("policy rules must be an object");
        String hash = Hashing.ofContent(rules);
        return tx.execute(status -> {
            db.execute("SET LOCAL lock_timeout='2000ms'");
            db.queryForObject("SELECT pg_advisory_xact_lock(?)", Object.class,
                    CanonicalRequest.lockKey("T05_POLICY|" + type + "|" + version));
            List<UUID> existing = db.query("SELECT id FROM editorial.policy_version WHERE policy_type=? AND version=?",
                    (rs, n) -> rs.getObject(1, UUID.class), type.name(), version);
            if (!existing.isEmpty()) return getById(existing.getFirst());
            UUID id = UUID.randomUUID();
            db.update("INSERT INTO editorial.policy_version(id, policy_type, version, rules, hash, status, created_by, published_by, published_at) "
                    + "VALUES (?::uuid, ?, ?, ?::jsonb, ?, 'PUBLISHED', ?, ?, clock_timestamp())",
                    id, type.name(), version, JsonIO.text(rules), hash, actor.actorId(), actor.actorId());
            audit.append(actor, new AuditSink.Event("POLICY_LOADED", null, "POLICY_VERSION", id, null, hash));
            return getById(id);
        });
    }
}

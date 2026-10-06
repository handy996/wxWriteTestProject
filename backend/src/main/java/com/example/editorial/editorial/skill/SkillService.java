package com.example.editorial.editorial.skill;

import com.example.editorial.audit.AuditSink;
import com.example.editorial.settings.policy.Hashing;
import com.example.editorial.settings.policy.JsonIO;
import com.example.editorial.settings.policy.PolicyService;
import com.example.editorial.settings.policy.PolicySnapshot;
import com.example.editorial.settings.policy.PublicationStatus;
import com.example.editorial.shared.ActorContext;
import com.example.editorial.shared.CanonicalRequest;
import com.example.editorial.shared.PublicFailure;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import org.springframework.jdbc.core.JdbcTemplate;

/**
 * Skill identity + version lifecycle. Write methods run inside the caller's transaction (the HTTP path uses the
 * T03 {@code Idempotency} transaction; the baseline loader uses its own transaction). Version numbers are allocated
 * server-side by locking the skill identity row, then reading the maximum existing semver across DRAFT/PUBLISHED/RETIRED
 * and incrementing the patch; the UNIQUE(skillId,version) constraint is the final concurrency defense. Published content
 * is immutable (service + DB trigger). A SkillSnapshot is a projection of a specific immutable version row, so
 * publishing a new version or retiring never rewrites historical snapshots.
 */
public final class SkillService {
    static final String SCHEMA_VERSION = "1.0.0-rc.3";

    private final JdbcTemplate db;
    private final AuditSink audit;
    private final PolicyService policies;
    private final SkillConfigValidator validator;
    private final ConfigChangeSink changes;
    private final CursorCodec cursors;

    public SkillService(JdbcTemplate db, AuditSink audit, PolicyService policies, SkillConfigValidator validator,
                        ConfigChangeSink changes, String cursorKey) {
        this.db = db; this.audit = audit; this.policies = policies; this.validator = validator;
        this.changes = changes; this.cursors = new CursorCodec(cursorKey);
    }

    // ------------------------------------------------------------------ identity
    public SkillIdentity create(ActorContext actor, String code, String name) {
        if (code == null || !code.matches("[A-Za-z0-9._-]{1,100}")) throw new PublicFailure(422, "INVALID_SKILL_CODE");
        if (name == null || name.isBlank() || name.length() > 100) throw new PublicFailure(422, "INVALID_SKILL_NAME");
        db.execute("SET LOCAL lock_timeout='2000ms'");
        db.queryForObject("SELECT pg_advisory_xact_lock(?)", Object.class, CanonicalRequest.lockKey("T05_SKILL_CODE|" + code));
        if (db.queryForObject("SELECT count(*) FROM editorial.editorial_skill WHERE code=?", Integer.class, code) > 0)
            throw new PublicFailure(409, "SKILL_CODE_CONFLICT");
        UUID id = UUID.randomUUID();
        db.update("INSERT INTO editorial.editorial_skill(id, code, name, owner_id, created_by) VALUES (?::uuid, ?, ?, ?, ?)",
                id, code, name, actor.ownerId(), actor.actorId());
        audit.append(actor, new AuditSink.Event("SKILL_CREATED", null, "SKILL", id, null, null));
        return new SkillIdentity(id, code, name, null);
    }

    // ------------------------------------------------------------------ versions
    public SkillSnapshot createVersion(ActorContext actor, UUID skillId, UUID baseVersionId, SkillConfig config) {
        db.execute("SET LOCAL lock_timeout='2000ms'");
        db.queryForObject("SELECT pg_advisory_xact_lock(?)", Object.class, CanonicalRequest.lockKey("T05_SKILL|" + skillId));
        requireSkillOwned(actor, skillId);
        validator.validate(config);
        String newVersion = allocateVersion(skillId, baseVersionId);
        String rulesHash = Hashing.ofContent(config.node());
        UUID id = UUID.randomUUID();
        db.update("INSERT INTO editorial.editorial_skill_version(id, skill_id, version, config, rules_hash, schema_version, status, parent_version_id, created_by) "
                + "VALUES (?::uuid, ?::uuid, ?, ?::jsonb, ?, ?, 'DRAFT', ?::uuid, ?)",
                id, skillId, newVersion, JsonIO.text(config.node()), rulesHash, SCHEMA_VERSION, baseVersionId, actor.actorId());
        audit.append(actor, new AuditSink.Event("SKILL_VERSION_CREATED", null, "SKILL_VERSION", id, null, rulesHash));
        return snapshotOf(getVersion(id));
    }

    public SkillSnapshot edit(ActorContext actor, UUID versionId, SkillConfig config) {
        db.execute("SET LOCAL lock_timeout='2000ms'");
        db.queryForObject("SELECT pg_advisory_xact_lock(?)", Object.class, CanonicalRequest.lockKey("T05_SKILL_VERSION|" + versionId));
        SkillVersion existing = requireOwnedVersion(actor, versionId);
        if (existing.status() != PublicationStatus.DRAFT)
            throw new PublicFailure(409, "SKILL_VERSION_IMMUTABLE");
        validator.validate(config);
        String rulesHash = Hashing.ofContent(config.node());
        int updated = db.update("UPDATE editorial.editorial_skill_version SET config=?::jsonb, rules_hash=?, lock_version=lock_version+1, updated_at=clock_timestamp() WHERE id=? AND status='DRAFT'",
                JsonIO.text(config.node()), rulesHash, versionId);
        if (updated != 1) throw new PublicFailure(409, "SKILL_VERSION_IMMUTABLE");
        audit.append(actor, new AuditSink.Event("SKILL_VERSION_EDITED", null, "SKILL_VERSION", versionId, existing.rulesHash(), rulesHash));
        return snapshotOf(getVersion(versionId));
    }

    public SkillSnapshot publish(ActorContext actor, UUID versionId, String changeLog) {
        db.execute("SET LOCAL lock_timeout='2000ms'");
        db.queryForObject("SELECT pg_advisory_xact_lock(?)", Object.class, CanonicalRequest.lockKey("T05_SKILL_VERSION|" + versionId));
        SkillVersion existing = requireOwnedVersion(actor, versionId);
        if (existing.status() != PublicationStatus.DRAFT)
            throw new PublicFailure(409, "SKILL_VERSION_IMMUTABLE");
        if (changeLog == null || changeLog.isBlank() || changeLog.length() > 1000)
            throw new PublicFailure(422, "INVALID_CHANGE_LOG");
        // Re-validate the whole publish contract in this same business transaction.
        SkillConfig config = new SkillConfig(existing.config());
        String recomputed = Hashing.ofContent(config.node());
        if (!recomputed.equals(existing.rulesHash())) throw new PublicFailure(409, "RULES_HASH_MISMATCH");
        validator.validate(config);
        int updated = db.update("UPDATE editorial.editorial_skill_version SET status='PUBLISHED', published_by=?, published_at=clock_timestamp(), change_log=?, lock_version=lock_version+1, updated_at=clock_timestamp() WHERE id=? AND status='DRAFT'",
                actor.actorId(), changeLog, versionId);
        if (updated != 1) throw new PublicFailure(409, "SKILL_VERSION_IMMUTABLE");
        db.update("UPDATE editorial.editorial_skill SET active_version_id=?::uuid, lock_version=lock_version+1, updated_at=clock_timestamp() WHERE id=?",
                versionId, existing.skillId());
        audit.append(actor, new AuditSink.Event("SKILL_VERSION_PUBLISHED", null, "SKILL_VERSION", versionId, existing.rulesHash(), existing.rulesHash()));
        changes.publish(new ConfigChangeEvent(UUID.randomUUID(), existing.skillId(), versionId, "PUBLISH",
                Instant.now(), ConfigChangeEvent.key(versionId, "PUBLISH")));
        return snapshotOf(getVersion(versionId));
    }

    public SkillSnapshot retire(ActorContext actor, UUID versionId, String reason) {
        if (reason == null || reason.isBlank() || reason.length() > 1000) throw new PublicFailure(422, "INVALID_REASON");
        db.execute("SET LOCAL lock_timeout='2000ms'");
        db.queryForObject("SELECT pg_advisory_xact_lock(?)", Object.class, CanonicalRequest.lockKey("T05_SKILL_VERSION|" + versionId));
        SkillVersion existing = requireOwnedVersion(actor, versionId);
        if (existing.status() != PublicationStatus.PUBLISHED)
            throw new PublicFailure(409, "SKILL_VERSION_IMMUTABLE");
        int updated = db.update("UPDATE editorial.editorial_skill_version SET status='RETIRED', lock_version=lock_version+1, updated_at=clock_timestamp() WHERE id=? AND status='PUBLISHED'",
                versionId);
        if (updated != 1) throw new PublicFailure(409, "SKILL_VERSION_IMMUTABLE");
        db.update("UPDATE editorial.editorial_skill SET active_version_id=NULL, lock_version=lock_version+1, updated_at=clock_timestamp() WHERE id=? AND active_version_id=?",
                existing.skillId(), versionId);
        audit.append(actor, new AuditSink.Event("SKILL_VERSION_RETIRED", null, "SKILL_VERSION", versionId, existing.rulesHash(), existing.rulesHash()));
        changes.publish(new ConfigChangeEvent(UUID.randomUUID(), existing.skillId(), versionId, "RETIRE",
                Instant.now(), ConfigChangeEvent.key(versionId, "RETIRE")));
        return snapshotOf(getVersion(versionId));
    }

    public void authorizeSkill(ActorContext actor, UUID skillId) { requireSkillOwned(actor, skillId); }
    public void authorizeVersion(ActorContext actor, UUID versionId) { requireOwnedVersion(actor, versionId); }

    // ------------------------------------------------------------------ reads
    public SkillIdentityPage list(ActorContext actor, String status, String cursor, int limit) {
        if (limit < 1 || limit > 100) throw new PublicFailure(422, "INVALID_LIMIT");
        List<Object> args = new ArrayList<>(); args.add(actor.ownerId());
        String filter = status == null || status.isBlank() ? "" : status;
        String where = "";
        if (status != null && !status.isBlank()) {
            if (!List.of("DRAFT", "PUBLISHED", "RETIRED").contains(status)) throw new PublicFailure(422, "INVALID_STATUS");
            where += " AND EXISTS (SELECT 1 FROM editorial.editorial_skill_version v WHERE v.skill_id=s.id AND v.status=?)";
            args.add(status);
        }
        String decoded = cursors.decode(cursor);
        if (decoded != null) {
            String[] v = decoded.split("\\|", -1);
            if (v.length != 5 || !v[0].equals("skill-list-v2") || !v[1].equals(actor.ownerId().toString()) || !v[2].equals(filter))
                throw new PublicFailure(422, "INVALID_CURSOR");
            where += " AND (s.created_at, s.id) < (?, ?::uuid)";
            args.add(Timestamp.from(Instant.parse(v[3]))); args.add(v[4]);
        }
        args.add(limit + 1);
        List<SkillIdentity> items = db.query(
            "SELECT s.id, s.code, s.name, s.active_version_id FROM editorial.editorial_skill s"
            + " WHERE s.owner_id = ?" + where + " ORDER BY s.created_at DESC, s.id DESC LIMIT ?",
            (rs, n) -> new SkillIdentity(rs.getObject(1, UUID.class), rs.getString(2), rs.getString(3), rs.getObject(4, UUID.class)),
            args.toArray());
        boolean more = items.size() > limit;
        List<SkillIdentity> page = List.copyOf(items.subList(0, Math.min(items.size(), limit)));
        String next = null;
        if (more) {
            var last = page.getLast();
            String payload = "skill-list-v2|" + actor.ownerId() + "|" + filter + "|" + skillCreatedAt(last.id()) + "|" + last.id();
            next = cursors.encode(payload);
        }
        return new SkillIdentityPage(page, next);
    }

    public SkillSnapshotPage listVersions(ActorContext actor, UUID skillId, String cursor, int limit) {
        if (limit < 1 || limit > 100) throw new PublicFailure(422, "INVALID_LIMIT");
        requireSkillOwned(actor, skillId);
        List<Object> args = new ArrayList<>(); args.add(skillId);
        String where = "";
        String decoded = cursors.decode(cursor);
        if (decoded != null) {
            String[] v = decoded.split("\\|", -1);
            if (v.length != 5 || !v[0].equals("skill-version-list-v1") || !v[1].equals(actor.ownerId().toString()) || !v[2].equals(skillId.toString()))
                throw new PublicFailure(422, "INVALID_CURSOR");
            where += " AND (created_at, id) < (?, ?::uuid)";
            args.add(Timestamp.from(Instant.parse(v[3]))); args.add(v[4]);
        }
        args.add(limit + 1);
        List<SkillSnapshot> items = db.query(
            "SELECT id, skill_id, version, config::text, rules_hash, schema_version, status, parent_version_id, change_log, created_by, published_by, published_at, created_at, lock_version FROM editorial.editorial_skill_version WHERE skill_id=?" + where + " ORDER BY created_at DESC, id DESC LIMIT ?",
            (rs, n) -> snapshotOf(row(rs)), args.toArray());
        boolean more = items.size() > limit;
        List<SkillSnapshot> page = List.copyOf(items.subList(0, Math.min(items.size(), limit)));
        String next = null;
        if (more) {
            var last = page.getLast();
            String payload = "skill-version-list-v1|" + actor.ownerId() + "|" + skillId + "|" + createdAt(last.id()) + "|" + last.id();
            next = cursors.encode(payload);
        }
        return new SkillSnapshotPage(page, next);
    }

    /** Internal comparison for the management UI; both exact versions must belong to this owner and skill. */
    public SkillConfigDiff.Result diff(ActorContext actor, UUID fromVersionId, UUID toVersionId) {
        SkillVersion from = requireOwnedVersion(actor, fromVersionId);
        SkillVersion to = requireOwnedVersion(actor, toVersionId);
        if (!from.skillId().equals(to.skillId())) throw new PublicFailure(422, "CROSS_SKILL_DIFF");
        return new SkillConfigDiff.Result(fromVersionId, toVersionId, SkillConfigDiff.compare(from.config(), to.config()));
    }

    public SkillSnapshot snapshotOf(SkillVersion v) {
        SkillConfig config = new SkillConfig(v.config());
        PolicySnapshot fact = policies.snapshot(config.factPolicyRef());
        PolicySnapshot license = policies.snapshot(config.licensePolicyRef());
        return new SkillSnapshot(v.id(), v.skillId(), v.version(), v.rulesHash(), v.schemaVersion(), v.config(),
                List.of(fact, license), v.status());
    }

    /** Frozen port read: PUBLISHED or RETIRED versions remain readable; DRAFT/missing are not published. */
    public SkillSnapshot readPublished(ActorContext actor, UUID versionId) {
        SkillVersion v = requireOwnedVersion(actor, versionId);
        if (v.status() == PublicationStatus.DRAFT) throw new PublicFailure(409, "SKILL_NOT_PUBLISHED");
        return snapshotOf(v);
    }

    // ------------------------------------------------------------------ internals
    record SkillRow(UUID id, String code, String name, UUID ownerId, UUID activeVersionId, long lockVersion) {}

    private SkillRow requireSkillOwned(ActorContext actor, UUID skillId) {
        List<SkillRow> rows = db.query("SELECT id, code, name, owner_id, active_version_id, lock_version FROM editorial.editorial_skill WHERE id=?",
                (rs, n) -> new SkillRow(rs.getObject(1, UUID.class), rs.getString(2), rs.getString(3), rs.getObject(4, UUID.class),
                        rs.getObject(5, UUID.class), rs.getLong(6)), skillId);
        if (rows.isEmpty() || !rows.getFirst().ownerId().equals(actor.ownerId())) throw new PublicFailure(404, "SKILL_NOT_FOUND");
        return rows.getFirst();
    }

    private SkillVersion requireOwnedVersion(ActorContext actor, UUID versionId) {
        List<SkillVersion> rows = db.query(
            "SELECT v.id, v.skill_id, v.version, v.config::text, v.rules_hash, v.schema_version, v.status, v.parent_version_id, v.change_log, v.created_by, v.published_by, v.published_at, v.created_at, v.lock_version "
            + "FROM editorial.editorial_skill_version v JOIN editorial.editorial_skill s ON s.id = v.skill_id WHERE v.id=? AND s.owner_id=?",
            (rs, n) -> row(rs), versionId, actor.ownerId());
        if (rows.isEmpty()) throw new PublicFailure(404, "SKILL_NOT_FOUND");
        return rows.getFirst();
    }

    private SkillVersion getVersion(UUID versionId) {
        List<SkillVersion> rows = db.query(
            "SELECT id, skill_id, version, config::text, rules_hash, schema_version, status, parent_version_id, change_log, created_by, published_by, published_at, created_at, lock_version FROM editorial.editorial_skill_version WHERE id=?",
            (rs, n) -> row(rs), versionId);
        if (rows.isEmpty()) throw new PublicFailure(404, "SKILL_NOT_FOUND");
        return rows.getFirst();
    }

    private static SkillVersion row(java.sql.ResultSet rs) throws java.sql.SQLException {
        return new SkillVersion(
                rs.getObject(1, UUID.class), rs.getObject(2, UUID.class), rs.getString(3),
                JsonIO.parse(rs.getString(4)), rs.getString(5), rs.getString(6),
                PublicationStatus.valueOf(rs.getString(7)), rs.getObject(8, UUID.class), rs.getString(9),
                rs.getObject(10, UUID.class), rs.getObject(11, UUID.class),
                rs.getTimestamp(12) == null ? null : rs.getTimestamp(12).toInstant(),
                rs.getTimestamp(13).toInstant(), rs.getLong(14));
    }

    private String allocateVersion(UUID skillId, UUID baseVersionId) {
        List<String> versions = db.query("SELECT version FROM editorial.editorial_skill_version WHERE skill_id=?",
                (rs, n) -> rs.getString(1), skillId);
        if (versions.isEmpty()) {
            if (baseVersionId != null) throw new PublicFailure(422, "BASE_VERSION_NOT_ALLOWED");
            return SemVer.FIRST.toString();
        }
        if (baseVersionId == null) throw new PublicFailure(409, "BASE_VERSION_REQUIRED");
        List<UUID> base = db.query("SELECT skill_id FROM editorial.editorial_skill_version WHERE id=?",
                (rs, n) -> rs.getObject(1, UUID.class), baseVersionId);
        if (base.isEmpty() || !base.getFirst().equals(skillId)) throw new PublicFailure(422, "CROSS_SKILL_BASE_VERSION");
        SemVer max = versions.stream().map(SemVer::parse).max(SemVer::compareTo).orElseThrow();
        return max.nextPatch().toString();
    }

    private Instant createdAt(UUID versionId) {
        return db.queryForObject("SELECT created_at FROM editorial.editorial_skill_version WHERE id=?", Timestamp.class, versionId).toInstant();
    }

    private Instant skillCreatedAt(UUID skillId) {
        return db.queryForObject("SELECT created_at FROM editorial.editorial_skill WHERE id=?", Timestamp.class, skillId).toInstant();
    }
}

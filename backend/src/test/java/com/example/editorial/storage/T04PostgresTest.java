package com.example.editorial.storage;

import static org.junit.jupiter.api.Assertions.*;

import com.example.editorial.audit.AuditSink;
import com.example.editorial.audit.JdbcAuditSink;
import com.example.editorial.shared.ActorContext;
import com.example.editorial.shared.CanonicalRequest;
import com.example.editorial.shared.Ownership;
import com.example.editorial.shared.PublicFailure;
import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import javax.sql.DataSource;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * Real PostgreSQL transaction boundaries for the object-store protocol. Hand-wired
 * (not a Spring context) so it runs independently of the T03 identity wiring: it
 * creates the minimal app_user/audit_log schema, then exercises stage -> verify ->
 * DB commit -> mark complete with a real DataSourceTransactionManager, real
 * JdbcAuditSink, real filesystem and a test-double Ownership.Resolver +
 * ObjectRefRegistry (the only permitted substitutes for not-yet-built domains).
 */
@EnabledIfEnvironmentVariable(named = "T04_REAL_PG", matches = "true")
class T04PostgresTest {
    static final UUID OWNER = UUID.fromString("10000000-0000-4000-8000-000000000001");
    static final UUID OTHER = UUID.fromString("10000000-0000-4000-8000-000000000002");
    static final UUID SYSTEM = UUID.fromString("10000000-0000-4000-8000-000000000003");
    static final UUID ARTICLE = UUID.fromString("20000000-0000-4000-8000-000000000001");
    static final UUID FOREIGN = UUID.fromString("20000000-0000-4000-8000-000000000002");

    static DataSource runtime;
    static PlatformTransactionManager txManager;
    static AuditSink audit;

    Path dir;
    LocalStorageBackend backend;
    Ownership ownership;
    TestResolver resolver;
    TestRegistry registry;
    DefaultObjectStore store;
    ActorContext owner, other;

    @BeforeAll static void createSchema() throws Exception {
        try (Connection c = adminConnection()) {
            for (String sql : new String[]{
                "CREATE TABLE IF NOT EXISTS editorial.app_user (" +
                    "id uuid PRIMARY KEY, username varchar(100) NOT NULL UNIQUE, display_name varchar(1000) NOT NULL," +
                    "actor_type varchar(20) NOT NULL CHECK (actor_type IN ('OWNER','SYSTEM_WORKER'))," +
                    "password_hash varchar(500), enabled boolean NOT NULL DEFAULT true, bootstrap_key varchar(20) UNIQUE," +
                    "created_at timestamptz NOT NULL DEFAULT clock_timestamp())",
                "CREATE TABLE IF NOT EXISTS editorial.audit_log (" +
                    "id uuid PRIMARY KEY, actor_id uuid NOT NULL REFERENCES editorial.app_user(id)," +
                    "actor_type varchar(20) NOT NULL, action varchar(80) NOT NULL, article_id uuid," +
                    "entity_type varchar(80) NOT NULL, entity_id uuid NOT NULL, before_hash char(64), after_hash char(64)," +
                    "detail jsonb NOT NULL DEFAULT '{}'::jsonb, trace_id uuid NOT NULL," +
                    "created_at timestamptz NOT NULL DEFAULT clock_timestamp())",
                "INSERT INTO editorial.app_user(id,username,display_name,actor_type,password_hash,bootstrap_key) VALUES " +
                    "('" + OWNER + "','t04-owner','Owner','OWNER','" + "x".repeat(60) + "','OWNER')," +
                    "('" + OTHER + "','t04-other','Other','OWNER','" + "x".repeat(60) + "',NULL)," +
                    "('" + SYSTEM + "','__system__','System','SYSTEM_WORKER',NULL,'SYSTEM') ON CONFLICT DO NOTHING",
                "GRANT SELECT,INSERT ON editorial.app_user, editorial.audit_log TO editorial_runtime",
            }) c.createStatement().execute(sql);
        }
        HikariConfig config = new HikariConfig();
        config.setJdbcUrl(System.getenv("DB_URL"));
        config.setUsername("editorial_runtime");
        config.setPassword(System.getenv("DB_RUNTIME_PASSWORD"));
        config.setMaximumPoolSize(4);
        runtime = new HikariDataSource(config);
        txManager = new DataSourceTransactionManager(runtime);
        audit = new JdbcAuditSink(new JdbcTemplate(runtime), txManager);
    }

    @BeforeEach void setUp() throws Exception {
        try (Connection c = adminConnection(); var s = c.createStatement()) {
            s.execute("DELETE FROM editorial.audit_log");
        }
        dir = Files.createTempDirectory("t04-storage");
        backend = new LocalStorageBackend(dir, "http://127.0.0.1:8080", "download-secret-0123456789abcdef");
        resolver = new TestResolver();
        ownership = new Ownership(List.of(resolver));
        registry = new TestRegistry();
        store = new DefaultObjectStore(backend, ownership, audit, txManager, List.of(registry),
            Clock.systemUTC(), 64L * 1024 * 1024, Duration.ofHours(24));
        owner = ActorContext.forWorker(SYSTEM, OWNER, UUID.randomUUID());
        other = ActorContext.forWorker(SYSTEM, OTHER, UUID.randomUUID());
    }

    static Connection adminConnection() throws Exception {
        return DriverManager.getConnection(System.getenv("DB_URL"), "editorial_admin", System.getenv("T04_ADMIN_PASSWORD"));
    }

    static long auditCount(String action) throws Exception {
        try (Connection c = adminConnection(); var s = c.prepareStatement("SELECT count(*) FROM editorial.audit_log WHERE action=?")) {
            s.setString(1, action); try (ResultSet r = s.executeQuery()) { r.next(); return r.getLong(1); }
        }
    }

    static String auditAfterHash(String key) throws Exception {
        try (Connection c = adminConnection(); var s = c.prepareStatement("SELECT after_hash FROM editorial.audit_log WHERE entity_id=? AND action='OBJECT_DOWNLOADED'")) {
            s.setObject(1, UUID.fromString(key)); try (ResultSet r = s.executeQuery()) { return r.next() ? r.getString(1) : null; }
        }
    }

    class TestResolver implements Ownership.Resolver {
        final Map<UUID, String> artifactHashes = new HashMap<>();
        public boolean supports(String kind) { return kind.equals("ARTICLE") || kind.equals("IMAGE_VARIANT"); }
        public Ownership.Resolved resolve(String kind, UUID id) {
            if (kind.equals("ARTICLE")) {
                if (id.equals(ARTICLE)) return new Ownership.Resolved(OWNER, new Ownership.ArtifactRef(id, id, null, "ARTICLE", "0".repeat(64), false));
                if (id.equals(FOREIGN)) return new Ownership.Resolved(OTHER, new Ownership.ArtifactRef(id, id, null, "ARTICLE", "0".repeat(64), false));
                return null;
            }
            UUID article = id.equals(ARTICLE) ? ARTICLE : id.equals(FOREIGN) ? FOREIGN : null;
            if (article == null) return null;
            UUID ow = article.equals(ARTICLE) ? OWNER : OTHER;
            String hash = artifactHashes.getOrDefault(article, "0".repeat(64));
            return new Ownership.Resolved(ow, new Ownership.ArtifactRef(id, article, null, "IMAGE_VARIANT", hash, false));
        }
    }

    class TestRegistry implements ObjectRefRegistry {
        final Map<String, ObjectRefRegistry.Resolution> resolutions = new HashMap<>();
        final Set<String> referenced = new HashSet<>();
        final Set<String> held = new HashSet<>();
        public ObjectRefRegistry.Resolution resolve(String key) { return resolutions.get(key); }
        public boolean referenced(String key) { return referenced.contains(key); }
        public boolean held(String key) { return held.contains(key); }
    }

    Ownership.ArtifactRef artifact(UUID article, String hash) {
        resolver.artifactHashes.put(article, hash);
        return new Ownership.ArtifactRef(article, article, null, "IMAGE_VARIANT", hash, false);
    }

    @Test void stageRecomputesHashAndSize() {
        byte[] bytes = "hello object".getBytes(StandardCharsets.UTF_8);
        String hash = CanonicalRequest.digest(bytes);
        ObjectRef ref = store.stage(owner, bytes, hash, bytes.length);
        assertEquals(hash, ref.hash());
        assertEquals(bytes.length, ref.size());
        assertEquals("text/plain", ref.mime());
        assertEquals(422, assertThrows(PublicFailure.class, () -> store.stage(owner, bytes, "0".repeat(64), bytes.length)).status());
        assertEquals(422, assertThrows(PublicFailure.class, () -> store.stage(owner, bytes, hash, bytes.length + 1)).status());
        assertEquals(422, assertThrows(PublicFailure.class, () -> store.stage(owner, new byte[0], null, -1)).status());
    }

    @Test void objectWrittenButTransactionFailsProducesNoSuccess() throws Exception {
        byte[] bytes = "orphan".getBytes(StandardCharsets.UTF_8);
        String hash = CanonicalRequest.digest(bytes);
        ObjectRef ref = store.stage(owner, bytes, hash, bytes.length);
        assertEquals(ObjectStatus.STAGING, backend.head(ref).status());
        TransactionTemplate outer = new TransactionTemplate(txManager);
        assertThrows(RuntimeException.class, () -> outer.execute(s -> {
            store.commitReference(owner, ref, artifact(ARTICLE, hash));
            throw new RuntimeException("forced rollback");
        }));
        assertEquals(ObjectStatus.STAGING, backend.head(ref).status()); // no false success
        assertEquals(0, auditCount("OBJECT_COMMITTED"));
    }

    @Test void commitMarksCompleteAfterCommit() throws Exception {
        byte[] bytes = "committed".getBytes(StandardCharsets.UTF_8);
        String hash = CanonicalRequest.digest(bytes);
        ObjectRef ref = store.stage(owner, bytes, hash, bytes.length);
        TransactionTemplate outer = new TransactionTemplate(txManager);
        outer.executeWithoutResult(s -> store.commitReference(owner, ref, artifact(ARTICLE, hash)));
        assertEquals(ObjectStatus.COMMITTED, backend.head(ref).status());
        assertEquals(1, auditCount("OBJECT_COMMITTED"));
    }

    @Test void crossArticleAndOtherOwnerRejected() {
        byte[] bytes = "x".getBytes(StandardCharsets.UTF_8);
        String hash = CanonicalRequest.digest(bytes);
        ObjectRef ref = store.stage(owner, bytes, hash, bytes.length);
        assertEquals(404, assertThrows(PublicFailure.class, () ->
            store.commitReference(owner, ref, artifact(FOREIGN, hash))).status());
        assertEquals(404, assertThrows(PublicFailure.class, () ->
            store.commitReference(other, ref, artifact(ARTICLE, hash))).status());
        assertEquals(404, assertThrows(PublicFailure.class, () ->
            store.commitReference(owner, ref, artifact(ARTICLE, "0".repeat(64)))).status());
    }

    @Test void authorizeDownloadRejectsAndGrants() throws Exception {
        byte[] bytes = "download me".getBytes(StandardCharsets.UTF_8);
        String hash = CanonicalRequest.digest(bytes);
        ObjectRef ref = store.stage(owner, bytes, hash, bytes.length);
        new TransactionTemplate(txManager).executeWithoutResult(s -> store.commitReference(owner, ref, artifact(ARTICLE, hash)));
        registry.resolutions.put(ref.key(), new ObjectRefRegistry.Resolution(ARTICLE, "IMAGE_VARIANT", false));

        // unknown key -> 404, never a URL
        assertEquals(404, assertThrows(PublicFailure.class, () -> store.authorizeDownload(owner, new ObjectRef(ObjectKeys.generate(), "0".repeat(64), 1, "text/plain", false))).status());

        // staged but not committed -> not ready
        byte[] stagedBytes = "still staging".getBytes(StandardCharsets.UTF_8);
        ObjectRef staging = store.stage(owner, stagedBytes, CanonicalRequest.digest(stagedBytes), stagedBytes.length);
        registry.resolutions.put(staging.key(), new ObjectRefRegistry.Resolution(ARTICLE, "IMAGE_VARIANT", false));
        assertEquals(409, assertThrows(PublicFailure.class, () -> store.authorizeDownload(owner, staging)).status());

        String url = store.authorizeDownload(owner, ref);
        assertTrue(url.startsWith("http://127.0.0.1:8080/api/v1/storage/objects/" + ref.key() + "?"));

        // other owner rejected
        assertEquals(404, assertThrows(PublicFailure.class, () -> store.authorizeDownload(other, ref)).status());

        // revoked rejected
        registry.resolutions.put(ref.key(), new ObjectRefRegistry.Resolution(ARTICLE, "IMAGE_VARIANT", true));
        assertEquals(404, assertThrows(PublicFailure.class, () -> store.authorizeDownload(owner, ref)).status());
        registry.resolutions.put(ref.key(), new ObjectRefRegistry.Resolution(ARTICLE, "IMAGE_VARIANT", false));

        String downloaded = store.authorizeDownload(owner, ref);
        assertEquals(ref.hash(), auditAfterHash(ref.key()).trim());
        assertFalse(downloaded.contains("download-secret"));
    }

    @Test void cleanupDeletesOnlyTtlOrphansNotReferencedOrHeld() throws Exception {
        // backdated staging orphan
        byte[] orphanBytes = "orphan".getBytes(StandardCharsets.UTF_8);
        ObjectRef orphan = new ObjectRef(ObjectKeys.generate(), CanonicalRequest.digest(orphanBytes), orphanBytes.length, "text/plain", false);
        StoredObject orphanStored = new StoredObject(orphan, ObjectStatus.STAGING, StoredObject.SCHEMA_VERSION,
            Instant.now().minus(Duration.ofHours(25)), null);
        backend.put(orphanStored, orphanBytes);

        // backdated staging but referenced
        byte[] refBytes = "referenced".getBytes(StandardCharsets.UTF_8);
        ObjectRef refd = new ObjectRef(ObjectKeys.generate(), CanonicalRequest.digest(refBytes), refBytes.length, "text/plain", false);
        backend.put(new StoredObject(refd, ObjectStatus.STAGING, StoredObject.SCHEMA_VERSION, Instant.now().minus(Duration.ofHours(25)), null), refBytes);
        registry.referenced.add(refd.key());

        // backdated staging but held
        byte[] heldBytes = "held".getBytes(StandardCharsets.UTF_8);
        ObjectRef heldRef = new ObjectRef(ObjectKeys.generate(), CanonicalRequest.digest(heldBytes), heldBytes.length, "text/plain", false);
        backend.put(new StoredObject(heldRef, ObjectStatus.STAGING, StoredObject.SCHEMA_VERSION, Instant.now().minus(Duration.ofHours(25)), null), heldBytes);
        registry.held.add(heldRef.key());

        // recent staging (not yet past TTL)
        byte[] recentBytes = "recent".getBytes(StandardCharsets.UTF_8);
        ObjectRef recent = new ObjectRef(ObjectKeys.generate(), CanonicalRequest.digest(recentBytes), recentBytes.length, "text/plain", false);
        backend.put(new StoredObject(recent, ObjectStatus.STAGING, StoredObject.SCHEMA_VERSION, Instant.now(), null), recentBytes);

        ObjectRetention.CleanupReport dry = store.cleanupOrphans(ObjectRetention.CleanupOptions.preview());
        assertEquals(4, dry.scanned());
        assertEquals(1, dry.deleted().size());
        assertTrue(dry.dryRun());
        // dry-run did not actually delete
        assertEquals(ObjectStatus.STAGING, backend.head(orphan).status());

        ObjectRetention.CleanupReport live = store.cleanupOrphans(ObjectRetention.CleanupOptions.live());
        assertEquals(1, live.deleted().size());
        assertEquals(orphan.key(), live.deleted().get(0).key());
        assertTrue(live.healed().contains(refd.key()));
        assertTrue(live.retained().contains(heldRef.key()));
        assertTrue(live.retained().contains(recent.key()));
        assertEquals(404, assertThrows(PublicFailure.class, () -> backend.head(orphan)).status());

        // second run is idempotent: no extra deletions
        ObjectRetention.CleanupReport again = store.cleanupOrphans(ObjectRetention.CleanupOptions.live());
        assertEquals(0, again.deleted().size());
    }

    @Test void noRegistryFailsClosedOnCleanup() throws Exception {
        DefaultObjectStore noRegistry = new DefaultObjectStore(backend, ownership, audit, txManager, List.of(),
            Clock.systemUTC(), 1024, Duration.ofHours(24));
        byte[] bytes = "x".getBytes(StandardCharsets.UTF_8);
        ObjectRef ref = new ObjectRef(ObjectKeys.generate(), CanonicalRequest.digest(bytes), bytes.length, "text/plain", false);
        backend.put(new StoredObject(ref, ObjectStatus.STAGING, StoredObject.SCHEMA_VERSION, Instant.now().minus(Duration.ofHours(25)), null), bytes);
        ObjectRetention.CleanupReport report = noRegistry.cleanupOrphans(ObjectRetention.CleanupOptions.live());
        assertEquals(0, report.deleted().size());
        assertTrue(report.retained().contains(ref.key()));
    }

    @Test void auditNeverLogsContentOrSecrets() throws Exception {
        byte[] bytes = "SECRET-CONTENT-SHOULD-NEVER-APPEAR".getBytes(StandardCharsets.UTF_8);
        String hash = CanonicalRequest.digest(bytes);
        ObjectRef ref = store.stage(owner, bytes, hash, bytes.length);
        new TransactionTemplate(txManager).executeWithoutResult(s -> store.commitReference(owner, ref, artifact(ARTICLE, hash)));
        registry.resolutions.put(ref.key(), new ObjectRefRegistry.Resolution(ARTICLE, "IMAGE_VARIANT", false));
        store.authorizeDownload(owner, ref);
        try (Connection c = adminConnection(); var s = c.prepareStatement(
                "SELECT string_agg(coalesce(action,'')||coalesce(after_hash::text,'')||coalesce(before_hash::text,''), ' ') FROM editorial.audit_log WHERE entity_id=?")) {
            s.setObject(1, UUID.fromString(ref.key()));
            try (ResultSet r = s.executeQuery()) { r.next();
                assertFalse(r.getString(1).contains("SECRET-CONTENT"));
                assertFalse(r.getString(1).contains("download-secret"));
            }
        }
    }
}

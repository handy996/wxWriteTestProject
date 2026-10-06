package com.example.editorial.storage;

import static org.junit.jupiter.api.Assertions.*;
import com.example.editorial.shared.CanonicalRequest;
import com.example.editorial.shared.PublicFailure;
import java.nio.file.*;
import java.nio.file.attribute.FileTime;
import java.time.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

@EnabledIfEnvironmentVariable(named = "T04_REAL_PG", matches = "true")
class T04RevisionPostgresTest {
    T04PostgresTest f;
    JdbcTemplate db;
    static final Instant OLD = Instant.now().minus(Duration.ofHours(25));

    @BeforeAll static void schema() throws Exception {
        T04PostgresTest.createSchema();
        try (var connection = T04PostgresTest.adminConnection(); var statement = connection.createStatement()) {
            statement.execute("CREATE TABLE editorial.t04_revision_ref (object_id text PRIMARY KEY)");
            statement.execute("GRANT SELECT,INSERT ON editorial.t04_revision_ref TO editorial_runtime");
        }
    }
    @BeforeEach void setup() throws Exception {
        f = new T04PostgresTest(); f.setUp();
        db = new JdbcTemplate(T04PostgresTest.runtime);
    }

    ObjectRef oldObject(String text) {
        byte[] bytes = text.getBytes(java.nio.charset.StandardCharsets.UTF_8);
        ObjectRef ref = new ObjectRef(ObjectKeys.generate(), CanonicalRequest.digest(bytes), bytes.length, "text/plain", false);
        f.backend.put(new StoredObject(ref, ObjectStatus.STAGING, 1, OLD, null), bytes);
        return ref;
    }

    static void await(CountDownLatch latch) {
        try { assertTrue(latch.await(10, TimeUnit.SECONDS)); }
        catch (InterruptedException e) { Thread.currentThread().interrupt(); throw new AssertionError(e); }
    }

    void awaitDatabaseLockWait() throws Exception {
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(10);
        try (var connection = T04PostgresTest.adminConnection(); var statement = connection.createStatement()) {
            while (System.nanoTime() < deadline) {
                try (var rows = statement.executeQuery("SELECT count(*) FROM pg_locks WHERE locktype='advisory' AND NOT granted")) {
                    rows.next(); if (rows.getInt(1) > 0) return;
                }
                Thread.sleep(20);
            }
        }
        fail("the competing operation never waited on the database object lock");
    }

    ObjectRefRegistry registry(CountDownLatch queried, CountDownLatch proceed) {
        return new ObjectRefRegistry() {
            public Resolution resolve(String id) { return null; }
            public boolean referenced(String id) {
                boolean result = Boolean.TRUE.equals(db.queryForObject(
                    "SELECT EXISTS(SELECT 1 FROM editorial.t04_revision_ref WHERE object_id=?)", Boolean.class, id));
                if (queried != null) { queried.countDown(); await(proceed); }
                return result;
            }
        };
    }

    DefaultObjectStore store(ObjectRefRegistry registry) {
        // Independent service and transaction-manager instances, sharing only PostgreSQL and the object backend.
        return new DefaultObjectStore(f.backend, f.ownership, T04PostgresTest.audit,
            new DataSourceTransactionManager(T04PostgresTest.runtime), List.of(registry), Clock.systemUTC(), 1024, Duration.ofHours(24));
    }

    @Test void cleanupWinsAndCompetingReferenceRollsBack() throws Exception {
        ObjectRef ref = oldObject("cleanup wins");
        var artifact = f.artifact(T04PostgresTest.ARTICLE, ref.hash());
        var queried = new CountDownLatch(1); var proceed = new CountDownLatch(1);
        var cleaner = store(registry(queried, proceed));
        try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
            var cleanup = executor.submit(() -> cleaner.cleanupOrphans(ObjectRetention.CleanupOptions.live()));
            await(queried);
            var commit = executor.submit(() -> new TransactionTemplate(T04PostgresTest.txManager).execute(status -> {
                db.update("INSERT INTO editorial.t04_revision_ref VALUES (?)", ref.key());
                return f.store.commitReference(f.owner, ref, artifact);
            }));
            try { awaitDatabaseLockWait(); } finally { proceed.countDown(); }
            assertEquals(1, cleanup.get(10, TimeUnit.SECONDS).deleted().size());
            assertInstanceOf(PublicFailure.class, assertThrows(ExecutionException.class, () -> commit.get(10, TimeUnit.SECONDS)).getCause());
            assertEquals(0, db.queryForObject("SELECT count(*) FROM editorial.t04_revision_ref WHERE object_id=?", Integer.class, ref.key()));
            assertEquals(0, T04PostgresTest.auditCount("OBJECT_COMMITTED"));
        } finally { proceed.countDown(); }
    }

    @Test void referenceWinsAndLockCoversOuterTransactionCommit() throws Exception {
        ObjectRef ref = oldObject("reference wins");
        var artifact = f.artifact(T04PostgresTest.ARTICLE, ref.hash());
        var ready = new CountDownLatch(1); var proceed = new CountDownLatch(1);
        var cleaner = store(registry(null, null));
        try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
            var commit = executor.submit(() -> new TransactionTemplate(T04PostgresTest.txManager).execute(status -> {
                db.update("INSERT INTO editorial.t04_revision_ref VALUES (?)", ref.key());
                f.store.commitReference(f.owner, ref, artifact);
                ready.countDown(); await(proceed); // commitReference returned, but the domain transaction is still open.
                return ref;
            }));
            await(ready);
            var cleanup = executor.submit(() -> cleaner.cleanupOrphans(ObjectRetention.CleanupOptions.live()));
            try { awaitDatabaseLockWait(); } finally { proceed.countDown(); }
            commit.get(10, TimeUnit.SECONDS);
            assertEquals(0, cleanup.get(10, TimeUnit.SECONDS).deleted().size());
            assertArrayEquals("reference wins".getBytes(), f.backend.get(ref));
            assertEquals(1, db.queryForObject("SELECT count(*) FROM editorial.t04_revision_ref WHERE object_id=?", Integer.class, ref.key()));
        } finally { proceed.countDown(); }
    }

    @ParameterizedTest @ValueSource(strings = {"missing", "truncated", "same-size"})
    void damagedBodyCannotCommitOrIssueDownload(String damage) throws Exception {
        ObjectRef ref = oldObject("good");
        Path body = f.dir.resolve("objects").resolve(ref.key());
        if (damage.equals("missing")) Files.delete(body);
        else Files.writeString(body, damage.equals("truncated") ? "g" : "evil");
        assertThrows(PublicFailure.class, () -> f.store.commitReference(f.owner, ref, f.artifact(T04PostgresTest.ARTICLE, ref.hash())));
        assertEquals(0, T04PostgresTest.auditCount("OBJECT_COMMITTED"));
        assertTrue(Files.readString(body.resolveSibling(ref.key() + ".meta")).contains("STAGING"));
        f.registry.resolutions.put(ref.key(), new ObjectRefRegistry.Resolution(T04PostgresTest.ARTICLE, "IMAGE_VARIANT", false));
        assertThrows(PublicFailure.class, () -> f.store.authorizeDownload(f.owner, ref));
    }

    @Test void interruptedPublicationRespectsTtlReferencesAndHolds() throws Exception {
        ObjectRef orphan = oldObject("body only orphan"), referenced = oldObject("body only historical reference"), held = oldObject("body only hold");
        ObjectRef recent = oldObject("recent interrupted upload"), metaOnly = oldObject("metadata only after interrupted delete");
        for (ObjectRef ref : List.of(orphan, referenced, held, recent)) {
            Files.delete(f.dir.resolve("objects").resolve(ref.key() + ".meta"));
            Files.setLastModifiedTime(f.dir.resolve("objects").resolve(ref.key()), FileTime.from(ref == recent ? Instant.now() : OLD));
        }
        Files.delete(f.dir.resolve("objects").resolve(metaOnly.key()));
        f.registry.referenced.add(referenced.key()); f.registry.held.add(held.key());
        var report = f.store.cleanupOrphans(ObjectRetention.CleanupOptions.live());
        assertEquals(Set.of(orphan.key(), metaOnly.key()), new HashSet<>(report.deleted().stream().map(ObjectRetention.DeletedObject::key).toList()));
        assertEquals(List.of(referenced.key()), report.healed());
        assertTrue(report.retained().containsAll(List.of(held.key(), recent.key())));
        assertEquals(ObjectStatus.COMMITTED, f.backend.head(referenced).status());
        assertArrayEquals("body only hold".getBytes(), f.backend.get(held));
    }

    @Test void previewDoesNotDeleteTempOrRepairSidecars() throws Exception {
        ObjectRef ref = oldObject("interrupted");
        Files.delete(f.dir.resolve("objects").resolve(ref.key() + ".meta"));
        Files.setLastModifiedTime(f.dir.resolve("objects").resolve(ref.key()), FileTime.from(OLD));
        Path part = f.dir.resolve(".tmp/crash.part"); Files.writeString(part, "partial"); Files.setLastModifiedTime(part, FileTime.from(OLD));
        assertEquals(1, f.store.cleanupOrphans(ObjectRetention.CleanupOptions.preview()).deleted().size());
        assertEquals("partial", Files.readString(part));
        assertFalse(Files.exists(f.dir.resolve("objects").resolve(ref.key() + ".meta")));
        assertEquals("interrupted", Files.readString(f.dir.resolve("objects").resolve(ref.key())));
        f.store.cleanupOrphans(ObjectRetention.CleanupOptions.live());
        assertFalse(Files.exists(part));
    }

    @Test void snapshotIsolationCannotBypassCoordination() {
        ObjectRef ref = oldObject("snapshot transaction");
        var transaction = new TransactionTemplate(T04PostgresTest.txManager);
        transaction.setIsolationLevel(org.springframework.transaction.TransactionDefinition.ISOLATION_REPEATABLE_READ);
        assertThrows(org.springframework.dao.DataAccessException.class, () -> transaction.execute(status ->
            f.store.commitReference(f.owner, ref, f.artifact(T04PostgresTest.ARTICLE, ref.hash()))));
        assertEquals(ObjectStatus.STAGING, f.backend.head(ref).status());
    }

    @Test void ownerAuthorizedUrlWorksOverRealHttpAndOtherOwnerCannotObtainOne() throws Exception {
        LocalDownloadHttpTest.start();
        try {
            var local = new LocalStorageBackend(LocalDownloadHttpTest.directory, LocalDownloadHttpTest.base, LocalDownloadHttpTest.SECRET);
            var service = new DefaultObjectStore(local, f.ownership, T04PostgresTest.audit, T04PostgresTest.txManager,
                List.of(f.registry), Clock.systemUTC(), 1024, Duration.ofHours(24));
            byte[] bytes = "owner-authorized download".getBytes();
            var ref = service.stage(f.owner, bytes, null, bytes.length);
            service.commitReference(f.owner, ref, f.artifact(T04PostgresTest.ARTICLE, ref.hash()));
            var resolution = new ObjectRefRegistry.Resolution(T04PostgresTest.ARTICLE, "IMAGE_VARIANT", false);
            f.registry.resolutions.put(ref.key(), resolution);
            LocalDownloadHttpTest.REFERENCES.put(ref.key(), resolution);
            String url = service.authorizeDownload(f.owner, ref);
            var response = LocalDownloadHttpTest.CLIENT.send(java.net.http.HttpRequest.newBuilder(java.net.URI.create(url)).GET().build(),
                java.net.http.HttpResponse.BodyHandlers.ofByteArray());
            assertEquals(200, response.statusCode()); assertArrayEquals(bytes, response.body());
            assertThrows(PublicFailure.class, () -> service.authorizeDownload(f.other, ref));
            assertThrows(PublicFailure.class, () -> service.authorizeDownload(null, ref));
        } finally { LocalDownloadHttpTest.stop(); }
    }
}

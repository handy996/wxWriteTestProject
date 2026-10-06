package com.example.editorial.storage;

import static org.junit.jupiter.api.Assertions.*;
import com.example.editorial.shared.PublicFailure;
import com.example.editorial.shared.CanonicalRequest;
import com.example.editorial.shared.Ownership;
import java.nio.file.*;
import java.time.*;
import java.util.*;
import java.util.concurrent.*;
import java.sql.*;
import org.junit.jupiter.api.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.support.TransactionTemplate;

/** Counterexamples assert the OBSERVED broken behavior, not acceptance success. */
class ReviewCounterexamplesTest {
    T04PostgresTest f;
    @BeforeAll static void schema() throws Exception { T04PostgresTest.createSchema(); }
    @BeforeEach void setup() throws Exception { f=new T04PostgresTest(); f.setUp(); }

    @Test void missingBodyStillCommitsAndGetsDownloadUrl() throws Exception {
        byte[] bytes="review missing body".getBytes(java.nio.charset.StandardCharsets.UTF_8);
        ObjectRef ref=f.store.stage(f.owner,bytes,CanonicalRequest.digest(bytes),bytes.length);
        Files.delete(f.dir.resolve("objects").resolve(ref.key()));
        f.store.commitReference(f.owner,ref,f.artifact(T04PostgresTest.ARTICLE,ref.hash()));
        f.registry.resolutions.put(ref.key(),new ObjectRefRegistry.Resolution(T04PostgresTest.ARTICLE,"IMAGE_VARIANT",false));
        assertEquals(ObjectStatus.COMMITTED,f.backend.head(ref).status());
        assertNotNull(f.store.authorizeDownload(f.owner,ref));
        PublicFailure failure=assertThrows(PublicFailure.class,()->f.backend.get(ref));
        assertEquals("OBJECT_MISSING",failure.code());
        System.out.println("COUNTEREXAMPLE missing bytes -> commit COMMITTED + download URL; actual GET OBJECT_MISSING");
    }

    @Test void corruptedBytesStillCommit() throws Exception {
        byte[] bytes="good".getBytes();
        ObjectRef ref=f.store.stage(f.owner,bytes,CanonicalRequest.digest(bytes),bytes.length);
        Files.write(f.dir.resolve("objects").resolve(ref.key()),"evil".getBytes());
        f.store.commitReference(f.owner,ref,f.artifact(T04PostgresTest.ARTICLE,ref.hash()));
        assertEquals(ObjectStatus.COMMITTED,f.backend.head(ref).status());
        assertEquals("OBJECT_CORRUPT",assertThrows(PublicFailure.class,()->f.backend.get(ref)).code());
        System.out.println("COUNTEREXAMPLE modified same-size bytes -> COMMITTED without verifying actual hash");
    }

    @Test void concurrentRealDatabaseReferenceIsDeletedByCleanup() throws Exception {
        JdbcTemplate db=new JdbcTemplate(T04PostgresTest.runtime);
        try(Connection c=T04PostgresTest.adminConnection()) {
            c.createStatement().execute("CREATE TABLE IF NOT EXISTS editorial.review_object_ref (key text PRIMARY KEY)");
            c.createStatement().execute("GRANT SELECT,INSERT ON editorial.review_object_ref TO editorial_runtime");
        }
        byte[] bytes="concurrent commit".getBytes();
        ObjectRef ref=new ObjectRef(ObjectKeys.generate(),CanonicalRequest.digest(bytes),bytes.length,"text/plain",false);
        f.backend.put(new StoredObject(ref,ObjectStatus.STAGING,1,Instant.now().minus(Duration.ofHours(25)),null),bytes);
        CountDownLatch readCompleted=new CountDownLatch(1), proceed=new CountDownLatch(1);
        ObjectRefRegistry registry=new ObjectRefRegistry() {
            public Resolution resolve(String k){return null;}
            public boolean referenced(String k) {
                boolean found=Boolean.TRUE.equals(db.queryForObject("SELECT EXISTS(SELECT 1 FROM editorial.review_object_ref WHERE key=?)",Boolean.class,k));
                readCompleted.countDown();
                try { if(!proceed.await(10,TimeUnit.SECONDS))throw new AssertionError("commit did not finish"); }
                catch(InterruptedException e){throw new RuntimeException(e);}
                return found;
            }
        };
        DefaultObjectStore store=new DefaultObjectStore(f.backend,f.ownership,T04PostgresTest.audit,
            T04PostgresTest.txManager,List.of(registry),Clock.systemUTC(),1024,Duration.ofHours(24));
        ExecutorService executor=Executors.newSingleThreadExecutor();
        try {
            Future<ObjectRetention.CleanupReport> cleanup=executor.submit(()->store.cleanupOrphans(ObjectRetention.CleanupOptions.live()));
            assertTrue(readCompleted.await(10,TimeUnit.SECONDS));
            new TransactionTemplate(T04PostgresTest.txManager).executeWithoutResult(s->{
                db.update("INSERT INTO editorial.review_object_ref(key) VALUES (?)",ref.key());
                store.commitReference(f.owner,ref,f.artifact(T04PostgresTest.ARTICLE,ref.hash()));
            });
            assertEquals(ObjectStatus.COMMITTED,f.backend.head(ref).status());
            proceed.countDown();
            assertEquals(1,cleanup.get(10,TimeUnit.SECONDS).deleted().size());
            assertEquals(1,db.queryForObject("SELECT count(*) FROM editorial.review_object_ref WHERE key=?",Integer.class,ref.key()));
            assertEquals("OBJECT_MISSING",assertThrows(PublicFailure.class,()->f.backend.get(ref)).code());
            System.out.println("COUNTEREXAMPLE real PG reference committed; cleanup deleted COMMITTED file; DB reference remains=1");
        } finally { proceed.countDown();executor.shutdownNow(); }
    }

    @Test void previewDeletesStaleTemporaryFile() throws Exception {
        Path partial=f.dir.resolve(".tmp").resolve("review.part");
        Files.writeString(partial,"pending");
        Files.setLastModifiedTime(partial,java.nio.file.attribute.FileTime.from(Instant.now().minus(Duration.ofHours(25))));
        f.store.cleanupOrphans(ObjectRetention.CleanupOptions.preview());
        assertFalse(Files.exists(partial));
        System.out.println("COUNTEREXAMPLE dryRun=true deletes stale .part before classification");
    }

    @Test void twoFileWriteCrashLeavesUnenumeratedOrphan() throws Exception {
        byte[] bytes="review interrupted upload".getBytes();
        String key=ObjectKeys.generate();
        // Exact on-disk state if the process stops after the first atomicWrite in put.
        Files.write(f.dir.resolve("objects").resolve(key),bytes);
        Files.setLastModifiedTime(f.dir.resolve("objects").resolve(key),java.nio.file.attribute.FileTime.from(Instant.now().minus(Duration.ofHours(25))));
        assertEquals(0,f.store.cleanupOrphans(ObjectRetention.CleanupOptions.live()).scanned());
        assertTrue(Files.exists(f.dir.resolve("objects").resolve(key)));
        System.out.println("COUNTEREXAMPLE body without sidecar survives TTL cleanup and is not enumerated");
    }
}

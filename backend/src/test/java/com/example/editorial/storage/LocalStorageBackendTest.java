package com.example.editorial.storage;

import static org.junit.jupiter.api.Assertions.*;

import com.example.editorial.shared.CanonicalRequest;
import com.example.editorial.shared.PublicFailure;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class LocalStorageBackendTest {
    @TempDir Path dir;

    StoredObject staged(byte[] bytes) {
        String key = ObjectKeys.generate();
        String hash = CanonicalRequest.digest(bytes);
        ObjectRef ref = new ObjectRef(key, hash, bytes.length, ObjectKeys.detectMime(bytes), false);
        return new StoredObject(ref, ObjectStatus.STAGING, StoredObject.SCHEMA_VERSION, Instant.now(), null);
    }

    @Test void putHeadGetRoundTrip() {
        LocalStorageBackend backend = new LocalStorageBackend(dir);
        byte[] bytes = "hello private object".getBytes(StandardCharsets.UTF_8);
        StoredObject staged = staged(bytes);
        backend.put(staged, bytes);
        StoredObject head = backend.head(staged.ref());
        assertEquals(staged.ref(), head.ref());
        assertEquals(ObjectStatus.STAGING, head.status());
        assertArrayEquals(bytes, backend.get(staged.ref()));
    }

    @Test void getRecomputesHashAndRejectsCorruption() throws Exception {
        LocalStorageBackend backend = new LocalStorageBackend(dir);
        byte[] bytes = "original".getBytes(StandardCharsets.UTF_8);
        StoredObject staged = staged(bytes);
        backend.put(staged, bytes);
        Files.write(dir.resolve("objects").resolve(staged.ref().key()), "tampered!".getBytes(StandardCharsets.UTF_8));
        PublicFailure e = assertThrows(PublicFailure.class, () -> backend.get(staged.ref()));
        assertEquals(503, e.status());
    }

    @Test void headRejectsWrongHashAndUnknownKey() {
        LocalStorageBackend backend = new LocalStorageBackend(dir);
        byte[] bytes = "content".getBytes(StandardCharsets.UTF_8);
        StoredObject staged = staged(bytes);
        backend.put(staged, bytes);
        ObjectRef wrong = new ObjectRef(staged.ref().key(), "0".repeat(64), bytes.length, "text/plain", false);
        assertEquals(404, assertThrows(PublicFailure.class, () -> backend.head(wrong)).status());
        ObjectRef unknown = new ObjectRef(ObjectKeys.generate(), staged.ref().hash(), bytes.length, "text/plain", false);
        assertEquals(404, assertThrows(PublicFailure.class, () -> backend.head(unknown)).status());
    }

    @Test void markCommittedIsIdempotent() {
        LocalStorageBackend backend = new LocalStorageBackend(dir);
        byte[] bytes = "content".getBytes(StandardCharsets.UTF_8);
        StoredObject staged = staged(bytes);
        backend.put(staged, bytes);
        StoredObject committed = backend.markCommitted(staged.ref());
        assertEquals(ObjectStatus.COMMITTED, committed.status());
        assertNotNull(committed.committedAt());
        StoredObject again = backend.markCommitted(staged.ref());
        assertEquals(ObjectStatus.COMMITTED, again.status());
        assertEquals(committed.committedAt(), again.committedAt());
    }

    @Test void deleteIsIdempotent() {
        LocalStorageBackend backend = new LocalStorageBackend(dir);
        byte[] bytes = "content".getBytes(StandardCharsets.UTF_8);
        StoredObject staged = staged(bytes);
        backend.put(staged, bytes);
        backend.delete(staged.ref());
        backend.delete(staged.ref());
        assertEquals(404, assertThrows(PublicFailure.class, () -> backend.head(staged.ref())).status());
    }

    @Test void listStagingOnlyReturnsUncommitted() {
        LocalStorageBackend backend = new LocalStorageBackend(dir);
        StoredObject a = staged("aaa".getBytes(StandardCharsets.UTF_8));
        StoredObject b = staged("bbbb".getBytes(StandardCharsets.UTF_8));
        backend.put(a, "aaa".getBytes(StandardCharsets.UTF_8));
        backend.put(b, "bbbb".getBytes(StandardCharsets.UTF_8));
        backend.markCommitted(b.ref());
        List<StoredObject> staging = backend.listStaging();
        assertEquals(1, staging.size());
        assertEquals(a.ref().key(), staging.get(0).ref().key());
    }

    @Test void nullBytesRejected() {
        LocalStorageBackend backend = new LocalStorageBackend(dir);
        StoredObject staged = staged("x".getBytes(StandardCharsets.UTF_8));
        assertEquals(422, assertThrows(PublicFailure.class, () -> backend.put(staged, null)).status());
    }

    @Test void unavailableDirectoryFailsConstruction() throws Exception {
        Path file = dir.resolve("not-a-dir");
        Files.write(file, "x".getBytes(StandardCharsets.UTF_8));
        assertThrows(IllegalStateException.class, () -> new LocalStorageBackend(file));
    }

    @Test void atomicWriteLeavesNoPartFileInObjects() throws Exception {
        LocalStorageBackend backend = new LocalStorageBackend(dir);
        byte[] bytes = "content".getBytes(StandardCharsets.UTF_8);
        StoredObject staged = staged(bytes);
        backend.put(staged, bytes);
        try (var files = Files.list(dir.resolve("objects"))) {
            List<String> names = files.map(p -> p.getFileName().toString()).toList();
            assertEquals(List.of(staged.ref().key(), staged.ref().key() + ".meta"), names.stream().sorted().toList());
        }
    }

    @Test void presignRequiresDownloadConfig() {
        LocalStorageBackend backend = new LocalStorageBackend(dir);
        byte[] bytes = "content".getBytes(StandardCharsets.UTF_8);
        StoredObject staged = staged(bytes);
        backend.put(staged, bytes);
        assertEquals(503, assertThrows(PublicFailure.class,
            () -> backend.presignDownload(staged.ref(), java.time.Duration.ofMinutes(5))).status());
    }
}

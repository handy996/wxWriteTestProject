package com.example.editorial.storage;

import static org.junit.jupiter.api.Assertions.*;

import com.example.editorial.shared.PublicFailure;
import java.net.http.HttpClient;
import java.time.Duration;
import java.time.Instant;
import org.junit.jupiter.api.Test;

class S3StorageBackendTest {
    @Test void unconfiguredReportsCapabilityMissingNotFakeSuccess() {
        S3StorageBackend backend = new S3StorageBackend(S3StorageBackend.Config.of(null, null, null, null, null, true));
        assertFalse(backend.configured());
        ObjectRef ref = new ObjectRef(ObjectKeys.generate(), "0".repeat(64), 3, "text/plain", false);
        assertEquals(503, assertThrows(PublicFailure.class, () -> backend.put(
            new StoredObject(ref, ObjectStatus.STAGING, 1, Instant.now(), null), new byte[]{1, 2, 3})).status());
        assertEquals(503, assertThrows(PublicFailure.class, () -> backend.head(ref)).status());
        assertEquals(503, assertThrows(PublicFailure.class, () -> backend.get(ref)).status());
        assertEquals(503, assertThrows(PublicFailure.class, () -> backend.presignDownload(ref, Duration.ofMinutes(5))).status());
        assertEquals(503, assertThrows(PublicFailure.class, () -> backend.listStaging()).status());
    }

    @Test void configuredPresignsFiveMinuteUrl() {
        S3StorageBackend.Config config = S3StorageBackend.Config.of(
            "https://s3.example.com", "private-bucket", "us-east-1", "AKID", "secret-secret-secret", true);
        Instant fixed = Instant.parse("2026-10-03T00:00:00Z");
        S3StorageBackend backend = new S3StorageBackend(config, HttpClient.newHttpClient(), () -> fixed);
        assertTrue(backend.configured());
        String key = ObjectKeys.generate();
        String url = backend.presignDownload(new ObjectRef(key, "0".repeat(64), 1, "text/plain", false), Duration.ofMinutes(5));
        assertTrue(url.startsWith("https://s3.example.com/private-bucket/objects/" + key + "?"));
        assertTrue(url.contains("X-Amz-Expires=300"));
        assertTrue(url.contains("X-Amz-Algorithm=AWS4-HMAC-SHA256"));
        assertTrue(url.contains("X-Amz-Signature="));
    }

    @Test void rejectsInvalidKey() {
        S3StorageBackend backend = new S3StorageBackend(S3StorageBackend.Config.of(
            "https://s3.example.com", "bucket", "us-east-1", "AKID", "secret-secret-secret", true));
        ObjectRef ref = new ObjectRef("../../etc/passwd", "0".repeat(64), 1, "text/plain", false);
        assertThrows(IllegalArgumentException.class, () -> backend.presignDownload(ref, Duration.ofMinutes(5)));
    }
}

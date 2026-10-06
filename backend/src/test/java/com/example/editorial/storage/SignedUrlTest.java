package com.example.editorial.storage;

import static org.junit.jupiter.api.Assertions.*;

import java.time.Duration;
import java.time.Instant;
import org.junit.jupiter.api.Test;

class SignedUrlTest {
    private static final String SECRET = "test-download-secret-0123456789abcdef";
    private static final String BASE = "http://127.0.0.1:8080";
    private static final String KEY = "550e8400-e29b-41d4-a716-446655440000";

    @Test void signThenVerifyReturnsKey() {
        Instant now = Instant.parse("2026-10-03T00:00:00Z");
        String url = SignedUrl.sign(SECRET, KEY, BASE, now.plus(Duration.ofMinutes(5)));
        assertEquals(KEY, SignedUrl.verify(SECRET, url, now));
    }

    @Test void fiveMinuteExpiryIsEnforced() {
        Instant now = Instant.parse("2026-10-03T00:00:00Z");
        String url = SignedUrl.sign(SECRET, KEY, BASE, now.plus(Duration.ofMinutes(5)));
        // Valid just before expiry, invalid at/after expiry.
        assertEquals(KEY, SignedUrl.verify(SECRET, url, now.plus(Duration.ofMinutes(5)).minusSeconds(1)));
        assertThrows(IllegalArgumentException.class, () -> SignedUrl.verify(SECRET, url, now.plus(Duration.ofMinutes(5))));
        assertThrows(IllegalArgumentException.class, () -> SignedUrl.verify(SECRET, url, now.plus(Duration.ofHours(1))));
    }

    @Test void tamperedExpiryOrSignatureRejected() {
        Instant now = Instant.parse("2026-10-03T00:00:00Z");
        String url = SignedUrl.sign(SECRET, KEY, BASE, now.plus(Duration.ofMinutes(5)));
        String extended = url.replace("expires=" + (now.getEpochSecond() + 300), "expires=" + (now.getEpochSecond() + 999999));
        assertThrows(IllegalArgumentException.class, () -> SignedUrl.verify(SECRET, extended, now));
        String wrongKey = url.replace(KEY, "550e8400-e29b-41d4-a716-446655440001");
        assertThrows(IllegalArgumentException.class, () -> SignedUrl.verify(SECRET, wrongKey, now));
        assertThrows(IllegalArgumentException.class, () -> SignedUrl.verify(SECRET, url + "x", now));
        assertThrows(IllegalArgumentException.class, () -> SignedUrl.verify(SECRET, url, now.plusSeconds(1).plus(Duration.ofMinutes(5))));
    }

    @Test void wrongSecretRejected() {
        Instant now = Instant.parse("2026-10-03T00:00:00Z");
        String url = SignedUrl.sign(SECRET, KEY, BASE, now.plus(Duration.ofMinutes(5)));
        assertThrows(IllegalArgumentException.class, () -> SignedUrl.verify("different-secret-9999999999999999", url, now));
    }

    @Test void shortSecretRefused() {
        assertThrows(IllegalStateException.class, () -> SignedUrl.sign("short", KEY, BASE, Instant.now().plusSeconds(300)));
    }
}

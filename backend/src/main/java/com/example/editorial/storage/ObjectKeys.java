package com.example.editorial.storage;

import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.UUID;

/**
 * Server-generated object keys and content-type detection. Keys are random
 * UUIDs — never a client path, original filename, or guessable location — and
 * every key is validated against a narrow allow-list before it reaches a
 * filesystem or object-store key, so path traversal, absolute paths, drive
 * letters, backslash confusion, NUL bytes and encoding tricks are rejected.
 */
public final class ObjectKeys {
    private ObjectKeys() {}

    /** Generate a random, unguessable object key (canonical UUID string). */
    public static String generate() {
        return UUID.randomUUID().toString();
    }

    /**
     * Reject anything that is not a canonical lowercase UUID. Defense in depth:
     * backends call this before building any path or object key, even though
     * keys are normally produced by {@link #generate()}.
     */
    public static void requireValid(String key) {
        if (key == null || key.length() != 36)
            throw new IllegalArgumentException("invalid object key");
        UUID parsed;
        try { parsed = UUID.fromString(key); }
        catch (IllegalArgumentException e) { throw new IllegalArgumentException("invalid object key"); }
        if (!parsed.toString().equals(key)) // rejects uppercase / non-canonical forms
            throw new IllegalArgumentException("invalid object key");
    }

    /** Minimal magic-byte content-type sniffing; not an image decoder (T23 owns decoding). */
    public static String detectMime(byte[] bytes) {
        if (bytes == null || bytes.length == 0) return "application/octet-stream";
        if (starts(bytes, 0xFF, 0xD8, 0xFF)) return "image/jpeg";
        if (starts(bytes, 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A)) return "image/png";
        if (starts(bytes, 0x47, 0x49, 0x46, 0x38)) return "image/gif";
        if (starts(bytes, 0x52, 0x49, 0x46, 0x46) && bytes.length > 11
                && bytes[8] == 0x57 && bytes[9] == 0x45 && bytes[10] == 0x42 && bytes[11] == 0x50) return "image/webp";
        if (starts(bytes, 0x25, 0x50, 0x44, 0x46)) return "application/pdf";
        if (starts(bytes, 0x50, 0x4B, 0x03, 0x04)) return "application/zip";
        if (starts(bytes, 0x1F, 0x8B)) return "application/gzip";
        if (looksLikeText(bytes)) return "text/plain";
        return "application/octet-stream";
    }

    private static boolean starts(byte[] b, int... prefix) {
        if (b.length < prefix.length) return false;
        for (int i = 0; i < prefix.length; i++) if ((b[i] & 0xFF) != prefix[i]) return false;
        return true;
    }

    private static boolean looksLikeText(byte[] b) {
        int limit = Math.min(b.length, 512);
        for (int i = 0; i < limit; i++) {
            int c = b[i] & 0xFF;
            if (c == 0) return false;
            if (c < 0x09 || (c > 0x0D && c < 0x20)) return false;
        }
        var probe = new String(b, 0, limit, StandardCharsets.UTF_8);
        return probe.indexOf('�') < 0;
    }

    static String normalize(String key) {
        requireValid(key);
        return key.toLowerCase(Locale.ROOT);
    }
}

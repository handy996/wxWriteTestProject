package com.example.editorial.storage;

import java.util.Locale;

/**
 * Frozen public DTO matching editorial.schema.json {@code $defs/ObjectRef}:
 * {@code key / hash / size / mime / encrypted}. The object key is generated
 * server-side and is opaque to callers; domain tables persist these fields.
 * No status or version is exposed here — those live in the storage backend
 * metadata ({@link StoredObject}), not in the public contract.
 */
public record ObjectRef(String key, String hash, long size, String mime, boolean encrypted) {
    public ObjectRef {
        if (key == null || key.isBlank() || key.length() > 1000)
            throw new IllegalArgumentException("object key is required");
        if (hash == null || !hash.matches("[a-f0-9]{64}"))
            throw new IllegalArgumentException("sha-256 hash is required");
        if (size < 0)
            throw new IllegalArgumentException("size cannot be negative");
        if (mime == null || mime.isBlank() || mime.length() > 100)
            throw new IllegalArgumentException("content type is required");
        hash = hash.toLowerCase(Locale.ROOT);
    }
}

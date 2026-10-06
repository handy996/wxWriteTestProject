package com.example.editorial.storage;

import java.time.Instant;

/**
 * Internal backend record (not a public DTO): adds the state, metadata format
 * version and timestamps that the frozen {@link ObjectRef} deliberately omits.
 * The object payload is content-addressed by {@code ref().hash()}; version here
 * is the metadata schema version used to evolve storage metadata across releases.
 */
public record StoredObject(ObjectRef ref, ObjectStatus status, int schemaVersion,
                           Instant createdAt, Instant committedAt) {
    public static final int SCHEMA_VERSION = 1;
}

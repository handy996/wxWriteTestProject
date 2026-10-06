package com.example.editorial.storage;

import java.time.Duration;
import java.util.List;

/**
 * Physical storage adapter. Local filesystem and S3-compatible implementations
 * share one contract. Backends are responsible for key isolation, atomic writes,
 * hash/size verification on read, idempotent completion marking, and signed
 * download URLs. They never trust a caller-supplied path: keys are validated
 * before any filesystem or object-store access.
 */
public interface StorageBackend {
    /** Stable adapter name for diagnostics ("local" | "s3"). */
    String name();

    /** False when required configuration/credentials are absent (FEATURE_NOT_READY). */
    boolean configured();

    /** Atomically write staged bytes plus metadata; never exposes a half-written object. */
    void put(StoredObject object, byte[] bytes);

    /** Return metadata, verifying key/hash/size against the stored record. */
    StoredObject head(ObjectRef ref);

    /** Read and re-verify bytes (hash + size) before returning them. */
    byte[] get(ObjectRef ref);

    /** Idempotently mark a staged object committed; safe to retry after failure. */
    StoredObject markCommitted(ObjectRef ref);

    /** Idempotently delete an object and its metadata. */
    void delete(ObjectRef ref);

    /** Enumerate staging objects (orphan candidates) for controlled cleanup. */
    List<StoredObject> listStaging();

    /** Recheck state under the object transaction lock; does not require readable bytes. */
    default boolean isStaging(ObjectRef ref) { return head(ref).status() == ObjectStatus.STAGING; }

    /** Best-effort removal of stale partial-write temp files older than the threshold. */
    default void cleanupStaleTemp(java.time.Instant olderThan) {}

    /** Produce a signed, time-limited download URL. */
    String presignDownload(ObjectRef ref, Duration ttl);
}

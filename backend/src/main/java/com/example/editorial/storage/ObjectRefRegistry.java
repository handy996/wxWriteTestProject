package com.example.editorial.storage;

import java.util.UUID;

/**
 * SPI implemented by the domain tasks that own object-holding tables (T06/T09/
 * T15/T23/T29 for references, T37 for retention holds). T04 does not create or
 * read domain tables directly: it asks registered registries whether an object
 * key is still referenced, who owns it, and whether a hold applies. Until a
 * registry is installed the store must fail closed, never guessing "unreferenced".
 * Reference inserts must call ObjectStore.commitReference in the SAME READ COMMITTED
 * transaction; do not swallow its failure. Hold writers must acquire
 * ObjectTransactionLock and verify the object still exists before adding a hold
 * in that transaction. Queries
 * must use that database connection, with no cached or replica reference results.
 */
public interface ObjectRefRegistry {
    /**
     * Resolve a key to its owning article for download authorization. Return
     * {@code null} when this registry does not know the key.
     */
    Resolution resolve(String objectKey);

    /** True when any current or historical domain row references the key. */
    boolean referenced(String objectKey);

    /** True when a retention or legal hold forbids deletion. */
    default boolean held(String objectKey) { return false; }

    /** Owning article and audit entity type; revoked blocks download. */
    record Resolution(UUID articleId, String entityType, boolean revoked) {}
}

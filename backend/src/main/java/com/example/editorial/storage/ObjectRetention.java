package com.example.editorial.storage;

import java.util.List;
import java.util.UUID;

/**
 * Orphan cleanup, deletion and retention. T04 owns the controlled-cleanup loop;
 * the authoritative "is this object referenced or held" answer comes from the
 * registered {@link ObjectRefRegistry} beans, never from a client-supplied flag.
 */
public interface ObjectRetention {
    /**
     * Scan staging objects, delete only those past the TTL with no current or
     * historical reference and no hold, and heal (mark committed) staging objects
     * that are already referenced. Idempotent, pausable and retryable; a dry run
     * performs the same classification without mutating storage.
     */
    CleanupReport cleanupOrphans(CleanupOptions options);

    record CleanupOptions(boolean dryRun) {
        public static CleanupOptions preview() { return new CleanupOptions(true); }
        public static CleanupOptions live() { return new CleanupOptions(false); }
    }

    record DeletedObject(UUID id, String key, long size, String reason) {}

    record CleanupReport(int scanned, List<DeletedObject> deleted, List<String> healed,
                         List<String> retained, List<String> failed, boolean dryRun) {
        public CleanupReport {
            deleted = List.copyOf(deleted);
            healed = List.copyOf(healed);
            retained = List.copyOf(retained);
            failed = List.copyOf(failed);
        }
    }
}

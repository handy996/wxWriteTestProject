package com.example.editorial.storage;

import com.example.editorial.shared.ActorContext;
import com.example.editorial.shared.Ownership;

/**
 * Frozen service port (ports.json {@code ObjectStore.*}). Only these three
 * operations are part of the cross-task contract; cleanup/retention live on
 * {@link ObjectRetention} to keep this interface aligned with rc.3 exactly.
 *
 * Protocol: {@code stage -> hash/size verify -> DB reference commit -> mark complete}.
 * Callers write the domain row and call {@link #commitReference} in the same
 * transaction; completion marking is performed after commit and is idempotent.
 */
public interface ObjectStore {
    /**
     * Write bytes to private staging and return a server-computed ObjectRef.
     * The server recomputes SHA-256 and size; a supplied expectedHash or size
     * that does not match is rejected so the object never reaches READY/COMMITTED.
     */
    ObjectRef stage(ActorContext actor, byte[] bytes, String expectedHash, long size);

    /**
     * Verify the staged object against an artifact reference that must resolve
     * to the same article and authenticated owner (T03 Ownership.require), then
     * mark it complete. Safe to retry; a failed completion stays STAGING and is
     * healed or cleaned by {@link ObjectRetention}.
     */
    ObjectRef commitReference(ActorContext actor, ObjectRef ref, Ownership.ArtifactRef artifact);

    /**
     * Authorize an authenticated owner (or their worker) to download a committed
     * object and return a signed URL valid for 5 minutes. Authorization, ownership
     * and object state are re-checked server-side; the URL is never guessable and
     * never bypasses the ownership gate.
     */
    String authorizeDownload(ActorContext actor, ObjectRef ref);
}

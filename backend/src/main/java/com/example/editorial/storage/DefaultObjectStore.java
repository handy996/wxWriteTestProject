package com.example.editorial.storage;

import com.example.editorial.audit.AuditSink;
import com.example.editorial.shared.ActorContext;
import com.example.editorial.shared.CanonicalRequest;
import com.example.editorial.shared.Ownership;
import com.example.editorial.shared.PublicFailure;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * Default implementation of the frozen ObjectStore port plus controlled cleanup.
 * Object metadata (hash/size/mime/state) lives in the storage backend; domain
 * tables owned by T06/T09/T15/T23/T29 hold the reference rows, and T04 asks the
 * registered {@link ObjectRefRegistry} beans whether a key is still referenced
 * or held. With no registry installed the store fails closed and never guesses
 * "unreferenced".
 */
public final class DefaultObjectStore implements ObjectStore, ObjectRetention {
    private static final Logger LOG = LoggerFactory.getLogger(DefaultObjectStore.class);
    public static final Duration DOWNLOAD_TTL = Duration.ofMinutes(5);

    private final StorageBackend backend;
    private final Ownership ownership;
    private final AuditSink audit;
    private final TransactionTemplate tx;
    private final TransactionTemplate independent;
    private final List<ObjectRefRegistry> registries;
    private final Clock clock;
    private final long maxObjectBytes;
    private final Duration orphanTtl;
    private final ObjectTransactionLock objectLock;

    public DefaultObjectStore(StorageBackend backend, Ownership ownership, AuditSink audit,
                              PlatformTransactionManager manager, List<ObjectRefRegistry> registries,
                              Clock clock, long maxObjectBytes, Duration orphanTtl) {
        this.backend = Objects.requireNonNull(backend);
        this.ownership = Objects.requireNonNull(ownership);
        this.audit = Objects.requireNonNull(audit);
        this.registries = List.copyOf(registries == null ? List.of() : registries);
        this.clock = clock == null ? Clock.systemUTC() : clock;
        this.maxObjectBytes = maxObjectBytes <= 0 ? 64L * 1024 * 1024 : maxObjectBytes;
        this.orphanTtl = orphanTtl == null ? Duration.ofHours(24) : orphanTtl;
        this.tx = new TransactionTemplate(manager);
        this.objectLock = new ObjectTransactionLock(manager);
        this.independent = new TransactionTemplate(manager);
        this.independent.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRES_NEW);
        this.independent.setIsolationLevel(TransactionDefinition.ISOLATION_READ_COMMITTED);
    }

    @Override public ObjectRef stage(ActorContext actor, byte[] bytes, String expectedHash, long size) {
        requireActor(actor);
        if (bytes == null || bytes.length == 0) throw new PublicFailure(422, "EMPTY_OBJECT");
        if (bytes.length > maxObjectBytes) throw new PublicFailure(422, "OBJECT_TOO_LARGE");
        String actualHash = CanonicalRequest.digest(bytes);
        if (expectedHash != null && !expectedHash.isBlank() && !expectedHash.equalsIgnoreCase(actualHash))
            throw new PublicFailure(422, "HASH_MISMATCH");
        if (size >= 0 && size != bytes.length) throw new PublicFailure(422, "SIZE_MISMATCH");
        String key = ObjectKeys.generate();
        String mime = ObjectKeys.detectMime(bytes);
        ObjectRef ref = new ObjectRef(key, actualHash, bytes.length, mime, false);
        StoredObject stored = new StoredObject(ref, ObjectStatus.STAGING, StoredObject.SCHEMA_VERSION, clock.instant(), null);
        backend.put(stored, bytes);
        independent.executeWithoutResult(s ->
            audit.append(actor, new AuditSink.Event("OBJECT_STAGED", null, "OBJECT", UUID.fromString(key), null, actualHash)));
        return ref;
    }

    @Override public ObjectRef commitReference(ActorContext actor, ObjectRef ref, Ownership.ArtifactRef artifact) {
        requireActor(actor);
        requireRef(ref);
        Objects.requireNonNull(artifact);
        return tx.execute(status -> {
            objectLock.acquire(ref.key());
            ownership.require(actor, artifact.articleId(), artifact, true);
            if (!ref.hash().equals(artifact.hash())) throw new PublicFailure(404, "OWNER_MISMATCH");
            StoredObject stored = backend.head(ref);
            if (stored.status() == ObjectStatus.DELETED) throw new PublicFailure(404, "OBJECT_MISSING");
            backend.get(ref); // Verify the physical bytes before the domain transaction can commit.
            if (TransactionSynchronizationManager.isSynchronizationActive()) {
                TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
                    @Override public void afterCommit() {
                        try { backend.markCommitted(ref); }
                        catch (RuntimeException e) { LOG.warn("object completion deferred objectId={}", ref.key()); }
                    }
                });
            } else {
                backend.markCommitted(ref);
            }
            audit.append(actor, new AuditSink.Event("OBJECT_COMMITTED", artifact.articleId(), "OBJECT",
                UUID.fromString(ref.key()), null, ref.hash()));
            return ref;
        });
    }

    @Override public String authorizeDownload(ActorContext actor, ObjectRef ref) {
        requireActor(actor);
        requireRef(ref);
        ObjectRefRegistry.Resolution resolution = resolve(ref.key());
        if (resolution == null) throw new PublicFailure(404, "NOT_FOUND");
        if (resolution.revoked()) throw new PublicFailure(404, "OBJECT_REVOKED");
        ownership.requireArticle(actor, resolution.articleId());
        StoredObject stored = backend.head(ref);
        if (stored.status() != ObjectStatus.COMMITTED) throw new PublicFailure(409, "OBJECT_NOT_READY");
        String url = backend.presignDownload(ref, DOWNLOAD_TTL);
        independent.executeWithoutResult(s -> audit.append(actor, new AuditSink.Event("OBJECT_DOWNLOADED",
            resolution.articleId(), resolution.entityType(), UUID.fromString(ref.key()), null, ref.hash())));
        return url;
    }

    @Override public CleanupReport cleanupOrphans(CleanupOptions options) {
        Instant cutoff = clock.instant().minus(orphanTtl);
        if (!options.dryRun()) backend.cleanupStaleTemp(cutoff);
        List<StoredObject> candidates = backend.listStaging();
        List<DeletedObject> deleted = new ArrayList<>();
        List<String> healed = new ArrayList<>();
        List<String> retained = new ArrayList<>();
        List<String> failed = new ArrayList<>();
        boolean canDetermine = !registries.isEmpty();
        for (StoredObject candidate : candidates) {
            String key = candidate.ref().key();
            if (!canDetermine) { retained.add(key); continue; } // fail closed: no action without a registry
            try {
                independent.executeWithoutResult(status -> {
                    objectLock.acquire(key);
                    // The snapshot from listStaging may predate a completed reference transaction.
                    if (!backend.isStaging(candidate.ref())) {
                        retained.add(key);
                        return;
                    }
                    if (referenced(key)) {
                        if (!options.dryRun()) backend.markCommitted(candidate.ref());
                        healed.add(key);
                    } else if (held(key) || candidate.createdAt().isAfter(cutoff)) {
                        retained.add(key);
                    } else {
                        if (!options.dryRun()) {
                            backend.delete(candidate.ref());
                            LOG.info("purged orphan object objectId={} size={}", key, candidate.ref().size());
                        }
                        deleted.add(new DeletedObject(UUID.fromString(key), key, candidate.ref().size(), "ORPHAN_TTL"));
                    }
                });
            } catch (RuntimeException e) {
                failed.add(key); // A failed query or physical check never authorizes deletion.
            }
        }
        return new CleanupReport(candidates.size(), deleted, healed, retained, failed, options.dryRun());
    }

    private ObjectRefRegistry.Resolution resolve(String key) {
        ObjectRefRegistry.Resolution found = null;
        for (ObjectRefRegistry r : registries) {
            ObjectRefRegistry.Resolution res = r.resolve(key);
            if (res == null) continue;
            if (found != null && !found.articleId().equals(res.articleId()))
                throw new PublicFailure(503, "OBJECT_REFERENCE_AMBIGUOUS");
            found = res;
        }
        return found;
    }

    private boolean referenced(String key) {
        for (ObjectRefRegistry r : registries) if (r.referenced(key)) return true;
        return false;
    }

    private boolean held(String key) {
        for (ObjectRefRegistry r : registries) if (r.held(key)) return true;
        return false;
    }

    private static void requireActor(ActorContext actor) {
        if (actor == null) throw new PublicFailure(401, "UNAUTHENTICATED");
    }

    private static void requireRef(ObjectRef ref) {
        if (ref == null || ref.key() == null) throw new PublicFailure(422, "INVALID_OBJECT_REF");
        ObjectKeys.requireValid(ref.key());
    }
}

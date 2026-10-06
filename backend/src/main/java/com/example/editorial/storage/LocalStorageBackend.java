package com.example.editorial.storage;

import com.example.editorial.shared.CanonicalRequest;
import com.example.editorial.shared.PublicFailure;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.attribute.PosixFilePermission;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.List;
import java.util.Locale;

/**
 * Private on-disk object store for development. Objects live in a configured,
 * non-web-root directory under server-generated UUID keys; metadata is a sidecar
 * file. Writes go through a temp file and atomic rename so a half-written object
 * is never visible. Reads re-verify hash and size. Directory and file permissions
 * are tightened to owner-only on POSIX filesystems (a no-op on Windows).
 */
public final class LocalStorageBackend implements StorageBackend {
    private static final ObjectMapper JSON = new ObjectMapper();
    private static final EnumSet<PosixFilePermission> DIR_0700 =
        EnumSet.of(PosixFilePermission.OWNER_READ, PosixFilePermission.OWNER_WRITE, PosixFilePermission.OWNER_EXECUTE);
    private static final EnumSet<PosixFilePermission> FILE_0600 =
        EnumSet.of(PosixFilePermission.OWNER_READ, PosixFilePermission.OWNER_WRITE);

    private final Path objects;
    private final Path tmp;
    private final String downloadBase;
    private final String downloadSecret;
    private final boolean windows = System.getProperty("os.name").toLowerCase(Locale.ROOT).contains("win");

    public LocalStorageBackend(Path baseDir) {
        this(baseDir, null, null);
    }

    public LocalStorageBackend(Path baseDir, String downloadBase, String downloadSecret) {
        this.objects = baseDir.resolve("objects");
        this.tmp = baseDir.resolve(".tmp");
        this.downloadBase = downloadBase;
        this.downloadSecret = downloadSecret;
        try {
            Files.createDirectories(objects);
            Files.createDirectories(tmp);
            tighten(objects); tighten(tmp); tighten(baseDir);
        } catch (IOException e) {
            throw new IllegalStateException("local storage dir unavailable", e);
        }
    }

    @Override public String name() { return "local"; }

    @Override public boolean configured() { return true; }

    @Override public void put(StoredObject object, byte[] bytes) {
        ObjectKeys.requireValid(object.ref().key());
        if (bytes == null) throw new PublicFailure(422, "EMPTY_OBJECT");
        cleanupStaleTemp(Instant.now().minus(Duration.ofDays(1)));
        try {
            atomicWrite(objectPath(object.ref().key()), bytes);
            atomicWrite(metaPath(object.ref().key()), metaJson(object).getBytes(StandardCharsets.UTF_8));
        } catch (IOException e) {
            throw new PublicFailure(503, "OBJECT_WRITE_FAILED");
        }
    }

    @Override public StoredObject head(ObjectRef ref) {
        ObjectKeys.requireValid(ref.key());
        StoredObject o = metadataOrInterruptedBody(ref.key());
        if (o == null || o.status() == ObjectStatus.DELETED) throw new PublicFailure(404, "OBJECT_MISSING");
        if (!o.ref().hash().equals(ref.hash()) || o.ref().size() != ref.size() || !o.ref().key().equals(ref.key()))
            throw new PublicFailure(404, "OBJECT_MISSING");
        verifiedBytes(ref);
        return o;
    }

    @Override public byte[] get(ObjectRef ref) {
        head(ref);
        return verifiedBytes(ref);
    }

    private byte[] verifiedBytes(ObjectRef ref) {
        byte[] bytes;
        try { bytes = Files.readAllBytes(objectPath(ref.key())); }
        catch (IOException e) { throw new PublicFailure(404, "OBJECT_MISSING"); }
        String actual = CanonicalRequest.digest(bytes);
        if (!actual.equals(ref.hash()) || bytes.length != ref.size())
            throw new PublicFailure(503, "OBJECT_CORRUPT");
        return bytes;
    }

    @Override public StoredObject markCommitted(ObjectRef ref) {
        ObjectKeys.requireValid(ref.key());
        StoredObject o = head(ref);
        if (o.status() == ObjectStatus.COMMITTED) return o;
        StoredObject committed = new StoredObject(o.ref(), ObjectStatus.COMMITTED, o.schemaVersion(),
            o.createdAt(), Instant.now());
        try { atomicWrite(metaPath(ref.key()), metaJson(committed).getBytes(StandardCharsets.UTF_8)); }
        catch (IOException e) { throw new PublicFailure(503, "OBJECT_WRITE_FAILED"); }
        return committed;
    }

    @Override public void delete(ObjectRef ref) {
        ObjectKeys.requireValid(ref.key());
        try {
            Files.deleteIfExists(objectPath(ref.key()));
            Files.deleteIfExists(metaPath(ref.key()));
        } catch (IOException e) { throw new PublicFailure(503, "OBJECT_WRITE_FAILED"); }
    }

    @Override public List<StoredObject> listStaging() {
        List<StoredObject> result = new ArrayList<>();
        try (var stream = Files.list(objects)) {
            var keys = new java.util.TreeSet<String>();
            for (Path p : stream.toList()) {
                String name = p.getFileName().toString();
                String key = name.endsWith(".meta") ? name.substring(0, name.length() - 5) : name;
                try { ObjectKeys.requireValid(key); } catch (IllegalArgumentException e) { continue; }
                keys.add(key);
            }
            for (String key : keys) {
                StoredObject o = metadataOrInterruptedBody(key);
                if (o != null && o.status() == ObjectStatus.STAGING) result.add(o);
            }
        } catch (IOException e) { throw new PublicFailure(503, "OBJECT_READ_FAILED"); }
        return result;
    }

    @Override public String presignDownload(ObjectRef ref, Duration ttl) {
        if (downloadBase == null || downloadSecret == null)
            throw new PublicFailure(503, "DOWNLOAD_NOT_CONFIGURED");
        return SignedUrl.sign(downloadSecret, ref.key(), downloadBase, Instant.now().plus(ttl));
    }

    @Override public boolean isStaging(ObjectRef ref) {
        ObjectKeys.requireValid(ref.key());
        StoredObject current = metadataOrInterruptedBody(ref.key());
        return current != null && current.status() == ObjectStatus.STAGING && current.ref().equals(ref);
    }

    @Override public void cleanupStaleTemp(Instant olderThan) {
        try (var stream = Files.list(tmp)) {
            for (Path p : stream.toList()) {
                try {
                    if (Files.getLastModifiedTime(p).toInstant().isBefore(olderThan)) Files.deleteIfExists(p);
                } catch (IOException ignored) { }
            }
        } catch (IOException ignored) { }
    }

    private Path objectPath(String key) { return objects.resolve(key); }
    private Path metaPath(String key) { return objects.resolve(key + ".meta"); }

    /** Enumerate the body-first crash window without modifying storage during preview.
     * Only an absent sidecar is recoverable; malformed metadata must fail closed.
     */
    private StoredObject metadataOrInterruptedBody(String key) {
        if (Files.exists(metaPath(key))) return readMeta(key);
        try {
            Path body = objectPath(key);
            if (!Files.isRegularFile(body, java.nio.file.LinkOption.NOFOLLOW_LINKS)) return null;
            byte[] bytes = Files.readAllBytes(body);
            ObjectRef ref = new ObjectRef(key, CanonicalRequest.digest(bytes), bytes.length, ObjectKeys.detectMime(bytes), false);
            return new StoredObject(ref, ObjectStatus.STAGING, StoredObject.SCHEMA_VERSION,
                Files.getLastModifiedTime(body).toInstant(), null);
        } catch (IOException e) { throw new PublicFailure(503, "OBJECT_READ_FAILED"); }
    }

    /** Consumes a capability issued only after owner authorization. */
    byte[] download(String url, Instant now) {
        String key;
        if (downloadSecret == null) throw new PublicFailure(503, "DOWNLOAD_NOT_CONFIGURED");
        try { key = SignedUrl.verify(downloadSecret, url, now); }
        catch (IllegalArgumentException e) { throw new PublicFailure(403, "INVALID_DOWNLOAD_LINK"); }
        StoredObject object = readMeta(key);
        if (object == null) throw new PublicFailure(404, "OBJECT_MISSING");
        if (object.status() != ObjectStatus.COMMITTED) throw new PublicFailure(409, "OBJECT_NOT_READY");
        return get(object.ref());
    }

    private StoredObject readMeta(String key) {
        try { return readMeta(metaPath(key)); }
        catch (IOException e) { return null; }
    }

    private StoredObject readMeta(Path p) throws IOException {
        if (!Files.exists(p)) return null;
        try {
            var node = JSON.readTree(Files.readAllBytes(p));
            String key = node.path("key").asText();
            String hash = node.path("hash").asText();
            long size = node.path("size").asLong();
            String mime = node.path("mime").asText();
            boolean encrypted = node.path("encrypted").asBoolean();
            ObjectStatus status = ObjectStatus.valueOf(node.path("status").asText());
            int schemaVersion = node.path("schemaVersion").asInt();
            Instant createdAt = Instant.parse(node.path("createdAt").asText());
            Instant committedAt = node.has("committedAt") && !node.get("committedAt").isNull()
                ? Instant.parse(node.path("committedAt").asText()) : null;
            return new StoredObject(new ObjectRef(key, hash, size, mime, encrypted), status, schemaVersion, createdAt, committedAt);
        } catch (Exception e) { return null; }
    }

    private String metaJson(StoredObject o) throws IOException {
        var node = JSON.createObjectNode();
        node.put("key", o.ref().key());
        node.put("hash", o.ref().hash());
        node.put("size", o.ref().size());
        node.put("mime", o.ref().mime());
        node.put("encrypted", o.ref().encrypted());
        node.put("status", o.status().name());
        node.put("schemaVersion", o.schemaVersion());
        node.put("createdAt", o.createdAt().toString());
        if (o.committedAt() != null) node.put("committedAt", o.committedAt().toString());
        else node.putNull("committedAt");
        return JSON.writeValueAsString(node);
    }

    private void atomicWrite(Path target, byte[] bytes) throws IOException {
        Path temp = Files.createTempFile(tmp, "obj", ".part");
        try {
            Files.write(temp, bytes);
            tightenFile(temp);
            try { Files.move(temp, target, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING); }
            catch (AtomicMoveNotSupportedException e) { Files.move(temp, target, StandardCopyOption.REPLACE_EXISTING); }
            tightenFile(target);
        } finally { Files.deleteIfExists(temp); }
    }

    private void tighten(Path dir) throws IOException {
        if (windows) return;
        Files.setPosixFilePermissions(dir, DIR_0700);
    }

    private void tightenFile(Path file) throws IOException {
        if (windows) return;
        Files.setPosixFilePermissions(file, FILE_0600);
    }
}

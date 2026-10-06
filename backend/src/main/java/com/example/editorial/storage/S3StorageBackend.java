package com.example.editorial.storage;

import com.example.editorial.shared.PublicFailure;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.function.Supplier;

/**
 * S3-compatible private-bucket adapter using AWS SigV4 over the JDK HttpClient
 * (no SDK dependency). Endpoint, bucket, region and credentials come only from
 * server configuration; secrets and signatures are never logged or returned.
 * When configuration is absent the backend reports itself unconfigured and the
 * store returns FEATURE_NOT_READY instead of faking success. It does not assume
 * version-locking, batch delete or strong list consistency on every S3-compatible
 * service.
 */
public final class S3StorageBackend implements StorageBackend {
    public record Config(String endpoint, String bucket, String region, String accessKey,
                         String secretKey, boolean pathStyle, String prefix) {
        public static Config of(String endpoint, String bucket, String region, String accessKey, String secretKey, boolean pathStyle) {
            return new Config(endpoint, bucket, region, accessKey, secretKey, pathStyle, "objects/");
        }
        boolean complete() {
            return endpoint != null && !endpoint.isBlank() && bucket != null && !bucket.isBlank()
                && region != null && !region.isBlank() && accessKey != null && !accessKey.isBlank()
                && secretKey != null && !secretKey.isBlank();
        }
    }

    private final Config config;
    private final HttpClient client;
    private final Supplier<Instant> clock;

    public S3StorageBackend(Config config) {
        this(config, HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build(), Instant::now);
    }

    S3StorageBackend(Config config, HttpClient client, Supplier<Instant> clock) {
        this.config = config; this.client = client; this.clock = clock;
        if (configured()) validateEndpoint();
    }

    @Override public String name() { return "s3"; }

    @Override public boolean configured() { return config != null && config.complete(); }

    private void validateEndpoint() {
        URI endpoint = URI.create(config.endpoint());
        if (!("https".equals(endpoint.getScheme()) || "http".equals(endpoint.getScheme()))
                || endpoint.getHost() == null || endpoint.getUserInfo() != null
                || endpoint.getRawQuery() != null || endpoint.getFragment() != null
                || !(endpoint.getPath().isEmpty() || endpoint.getPath().equals("/"))
                || !config.bucket().matches("[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]")
                || config.prefix() == null || !config.prefix().matches("[a-zA-Z0-9_-]+/"))
            throw new IllegalArgumentException("unsupported S3 endpoint, bucket or prefix");
        if (!config.pathStyle() && (endpoint.getHost().contains(":") || endpoint.getHost().matches("[0-9.]+")
                || config.bucket().contains(".")))
            throw new IllegalArgumentException("virtual hosted S3 requires a DNS endpoint and a dot-free bucket");
    }

    private String keyFor(String key) {
        ObjectKeys.requireValid(key);
        return config.prefix() + key;
    }

    URI uri(String objectKey, String query) {
        URI endpoint = URI.create(config.endpoint());
        String authority = config.pathStyle() ? endpoint.getRawAuthority()
            : config.bucket() + "." + endpoint.getRawAuthority();
        String path = "/" + (config.pathStyle() ? config.bucket() + "/" : "") + objectKey;
        return SigV4.withoutDefaultPort(URI.create(endpoint.getScheme() + "://" + authority + path
            + (query == null ? "" : "?" + query)));
    }

    private HttpRequest request(String method, String key, String query, byte[] body, Map<String, String> extra) {
        URI target = uri(key, query);
        var builder = HttpRequest.newBuilder(target).timeout(Duration.ofSeconds(30))
            .method(method, body == null ? HttpRequest.BodyPublishers.noBody() : HttpRequest.BodyPublishers.ofByteArray(body));
        SigV4.sign(creds(), method, target, body, extra, clock.get()).forEach(builder::header);
        if (extra != null) extra.forEach(builder::header);
        // HttpClient supplies Host from this very URI; no restricted-header override.
        return builder.build();
    }

    private SigV4.Credentials creds() {
        return new SigV4.Credentials(config.accessKey(), config.secretKey(), config.region());
    }

    @Override public void put(StoredObject object, byte[] bytes) {
        requireConfigured();
        if (bytes == null) throw new PublicFailure(422, "EMPTY_OBJECT");
        send(request("PUT", keyFor(object.ref().key()), null, bytes, metaHeaders(object, clock.get())), 200);
    }

    private StoredObject metadata(String logicalKey) {
        requireConfigured();
        HttpResponse<Void> response = send(request("HEAD", keyFor(logicalKey), null, null, null), 200);
        StoredObject object = fromHeaders(response.headers().map());
        if (object == null || !object.ref().key().equals(logicalKey))
            throw new PublicFailure(503, "S3_INVALID_METADATA");
        if (object.status() == ObjectStatus.DELETED) throw new PublicFailure(404, "OBJECT_MISSING");
        long actualSize = response.headers().firstValueAsLong("content-length").orElse(-1);
        if (actualSize != object.ref().size()) throw new PublicFailure(503, "OBJECT_CORRUPT");
        return object;
    }

    @Override public StoredObject head(ObjectRef ref) {
        StoredObject object = metadata(ref.key());
        if (!object.ref().hash().equals(ref.hash()) || object.ref().size() != ref.size())
            throw new PublicFailure(404, "OBJECT_MISSING");
        return object;
    }

    @Override public byte[] get(ObjectRef ref) {
        head(ref);
        HttpResponse<byte[]> response = send(request("GET", keyFor(ref.key()), null, null, null), 200);
        byte[] bytes = response.body();
        if (!SigV4.hexSha256(bytes).equals(ref.hash()) || bytes.length != ref.size())
            throw new PublicFailure(503, "OBJECT_CORRUPT");
        return bytes;
    }

    @Override public StoredObject markCommitted(ObjectRef ref) {
        StoredObject object = head(ref);
        if (object.status() == ObjectStatus.COMMITTED) return object;
        get(ref);
        StoredObject committed = new StoredObject(object.ref(), ObjectStatus.COMMITTED,
            object.schemaVersion(), object.createdAt(), clock.get());
        Map<String, String> headers = metaHeaders(committed, clock.get());
        headers.put("x-amz-copy-source", "/" + config.bucket() + "/" + keyFor(ref.key()));
        headers.put("x-amz-metadata-directive", "REPLACE");
        // Every x-amz header, including replacement metadata, participates in the signature.
        HttpResponse<byte[]> response = send(request("PUT", keyFor(ref.key()), null, null, headers), 200);
        var document = parseXml(response.body());
        if (!"CopyObjectResult".equals(document.getDocumentElement().getLocalName()))
            throw new PublicFailure(503, "S3_COPY_FAILED"); // CopyObject may return an Error with HTTP 200.
        StoredObject verified = head(ref);
        if (verified.status() != ObjectStatus.COMMITTED) throw new PublicFailure(503, "S3_COPY_FAILED");
        return verified;
    }

    @Override public void delete(ObjectRef ref) {
        requireConfigured();
        send(request("DELETE", keyFor(ref.key()), null, null, null), 204);
    }

    @Override public List<StoredObject> listStaging() {
        requireConfigured();
        List<StoredObject> result = new ArrayList<>();
        java.util.Set<String> seenTokens = new java.util.HashSet<>();
        String token = null;
        do {
            Map<String, String> query = new java.util.TreeMap<>();
            query.put("list-type", "2");
            query.put("prefix", config.prefix());
            if (token != null) query.put("continuation-token", token);
            HttpResponse<byte[]> response = send(request("GET", "", SigV4.encodeQuery(query), null, null), 200);
            var document = parseXml(response.body());
            if (!"ListBucketResult".equals(document.getDocumentElement().getLocalName()))
                throw new PublicFailure(503, "S3_INVALID_LIST");
            var contents = document.getElementsByTagNameNS("*", "Contents");
            for (int i = 0; i < contents.getLength(); i++) {
                String objectKey = elementText((org.w3c.dom.Element) contents.item(i), "Key");
                if (objectKey == null || !objectKey.startsWith(config.prefix())) continue;
                String logicalKey = objectKey.substring(config.prefix().length());
                try { ObjectKeys.requireValid(logicalKey); } catch (IllegalArgumentException e) { continue; }
                try {
                    StoredObject object = metadata(logicalKey);
                    if (object.status() == ObjectStatus.STAGING) result.add(object);
                } catch (PublicFailure failure) {
                    if (failure.status() != 404) throw failure; // Concurrent removal is safe; outages are not empty lists.
                }
            }
            var root = document.getDocumentElement();
            String truncated = elementText(root, "IsTruncated");
            if (!"true".equals(truncated) && !"false".equals(truncated))
                throw new PublicFailure(503, "S3_INVALID_LIST");
            token = "true".equals(truncated) ? elementText(root, "NextContinuationToken") : null;
            if ("true".equals(truncated) && (token == null || token.isBlank() || !seenTokens.add(token)))
                throw new PublicFailure(503, "S3_INVALID_LIST");
        } while (token != null);
        return result;
    }

    @Override public String presignDownload(ObjectRef ref, Duration ttl) {
        requireConfigured();
        return SigV4.presignGet(creds(), uri(keyFor(ref.key()), null), clock.get(), ttl);
    }

    private static org.w3c.dom.Document parseXml(byte[] xml) {
        try {
            var factory = javax.xml.parsers.DocumentBuilderFactory.newInstance();
            factory.setNamespaceAware(true);
            factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
            factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
            factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
            factory.setAttribute(javax.xml.XMLConstants.ACCESS_EXTERNAL_DTD, "");
            factory.setAttribute(javax.xml.XMLConstants.ACCESS_EXTERNAL_SCHEMA, "");
            var builder = factory.newDocumentBuilder();
            builder.setErrorHandler(new org.xml.sax.helpers.DefaultHandler());
            return builder.parse(new java.io.ByteArrayInputStream(xml));
        } catch (Exception e) { throw new PublicFailure(503, "S3_INVALID_XML"); }
    }

    private static String elementText(org.w3c.dom.Element parent, String name) {
        var elements = parent.getElementsByTagNameNS("*", name);
        return elements.getLength() == 1 ? elements.item(0).getTextContent() : null;
    }

    private void requireConfigured() {
        if (!configured()) throw new PublicFailure(503, "FEATURE_NOT_READY");
    }

    private Map<String, String> metaHeaders(StoredObject o, Instant now) {
        return new java.util.TreeMap<>(Map.of(
            "x-amz-meta-key", o.ref().key(),
            "x-amz-meta-hash", o.ref().hash(),
            "x-amz-meta-size", Long.toString(o.ref().size()),
            "x-amz-meta-mime", o.ref().mime(),
            "x-amz-meta-encrypted", Boolean.toString(o.ref().encrypted()),
            "x-amz-meta-status", o.status().name(),
            "x-amz-meta-schema-version", Integer.toString(o.schemaVersion()),
            "x-amz-meta-created-at", Long.toString(o.createdAt().toEpochMilli()),
            "x-amz-meta-committed-at", o.committedAt() == null ? "" : Long.toString(o.committedAt().toEpochMilli())));
    }

    private StoredObject fromHeaders(Map<String, List<String>> headers) {
        String key = headerValue(headers, "x-amz-meta-key"), hash = headerValue(headers, "x-amz-meta-hash"),
            size = headerValue(headers, "x-amz-meta-size"), mime = headerValue(headers, "x-amz-meta-mime"),
            encrypted = headerValue(headers, "x-amz-meta-encrypted"), status = headerValue(headers, "x-amz-meta-status"),
            schema = headerValue(headers, "x-amz-meta-schema-version"), created = headerValue(headers, "x-amz-meta-created-at"),
            committed = headerValue(headers, "x-amz-meta-committed-at");
        if (key == null || hash == null || size == null || status == null || created == null) return null;
        try {
            return new StoredObject(new ObjectRef(key, hash, Long.parseLong(size), mime == null ? "application/octet-stream" : mime,
                Boolean.parseBoolean(encrypted)), ObjectStatus.valueOf(status),
                schema == null ? StoredObject.SCHEMA_VERSION : Integer.parseInt(schema),
                Instant.ofEpochMilli(Long.parseLong(created)),
                committed == null || committed.isBlank() ? null : Instant.ofEpochMilli(Long.parseLong(committed)));
        } catch (IllegalArgumentException e) { return null; }
    }

    private static String headerValue(Map<String, List<String>> headers, String name) {
        List<String> values = headers.get(name);
        return values == null || values.isEmpty() ? null : values.get(0);
    }

    private <T> HttpResponse<T> send(HttpRequest req, int expected) {
        try {
            HttpResponse<T> resp = client.send(req, responseBodyHandler(req));
            int code = resp.statusCode();
            if (code == expected) return resp;
            if (code == 404) throw new PublicFailure(404, "OBJECT_MISSING");
            if (code == 403) throw new PublicFailure(503, "S3_SIGNATURE_FAILED");
            if (code == 408 || code == 504) throw new PublicFailure(503, "S3_TIMEOUT");
            throw new PublicFailure(503, "S3_UNAVAILABLE");
        } catch (PublicFailure e) { throw e; }
        catch (java.io.IOException e) { throw new PublicFailure(503, "S3_UNAVAILABLE"); }
        catch (InterruptedException e) { Thread.currentThread().interrupt(); throw new PublicFailure(503, "S3_UNAVAILABLE"); }
    }

    @SuppressWarnings("unchecked")
    private <T> HttpResponse.BodyHandler<T> responseBodyHandler(HttpRequest req) {
        String method = req.method();
        if (method.equals("HEAD")) return (HttpResponse.BodyHandler<T>) HttpResponse.BodyHandlers.discarding();
        if (method.equals("DELETE")) return (HttpResponse.BodyHandler<T>) HttpResponse.BodyHandlers.discarding();
        return (HttpResponse.BodyHandler<T>) HttpResponse.BodyHandlers.ofByteArray();
    }
}

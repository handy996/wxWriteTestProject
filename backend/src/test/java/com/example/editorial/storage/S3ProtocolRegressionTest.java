package com.example.editorial.storage;

import static org.junit.jupiter.api.Assertions.*;
import com.example.editorial.shared.PublicFailure;
import com.sun.net.httpserver.HttpServer;
import java.net.*;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.time.*;
import java.util.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;

class S3ProtocolRegressionTest {
    private static final SigV4.Credentials EXAMPLE = new SigV4.Credentials(
        "AKIAIOSFODNN7EXAMPLE", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", "us-east-1");
    private static final Instant NOW = Instant.parse("2013-05-24T00:00:00Z");

    @Test void awsPublishedHeaderAndPresignVectors() {
        // https://docs.aws.amazon.com/AmazonS3/latest/developerguide/sig-v4-header-based-auth.html
        var signed = SigV4.sign(EXAMPLE, "GET", URI.create("https://examplebucket.s3.amazonaws.com/test.txt"),
            null, Map.of("Range", "bytes=0-9"), NOW);
        assertTrue(signed.get("Authorization").endsWith("Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"));
        // https://docs.aws.amazon.com/AmazonS3/latest/developerguide/sigv4-query-string-auth.html
        assertTrue(SigV4.presignGet(EXAMPLE, URI.create("https://examplebucket.s3.amazonaws.com/test.txt"), NOW, Duration.ofDays(1))
            .endsWith("X-Amz-Signature=aeeed9bbccd4d02ee5c0109b86d86835f995330da4c265957d157751f604d404"));
    }

    @Test void absentAndEmptyQueriesHaveIdenticalSignatures() {
        for (String method : List.of("PUT", "GET", "HEAD", "DELETE"))
            assertEquals(SigV4.sign(EXAMPLE, method, "example.com", "/bucket/objects/x", "", null, null, NOW),
                SigV4.sign(EXAMPLE, method, "example.com", "/bucket/objects/x", null, null, null, NOW));
    }

    S3StorageBackend backend(String endpoint, boolean pathStyle) {
        return new S3StorageBackend(S3StorageBackend.Config.of(endpoint, "private-bucket", "us-east-1", "TEST", "test-fixture-only", pathStyle));
    }

    @Test void uriAndPresignShareSchemeAuthorityAndObjectPath() {
        String id = ObjectKeys.generate();
        ObjectRef ref = new ObjectRef(id, "0".repeat(64), 1, "text/plain", false);
        for (var item : Map.of("https://s3.amazonaws.com", true, "http://127.0.0.1:19000", true,
                "http://s3.example.com:19000", false).entrySet()) {
            var backend = backend(item.getKey(), item.getValue());
            var uri = backend.uri("objects/" + id, null);
            URI download = URI.create(backend.presignDownload(ref, Duration.ofMinutes(5)));
            assertEquals(uri.getScheme(), download.getScheme());
            assertEquals(uri.getRawAuthority(), download.getRawAuthority());
            assertEquals(uri.getRawPath(), download.getRawPath());
            if (!item.getValue()) assertEquals("private-bucket.s3.example.com", uri.getHost());
        }
        assertThrows(IllegalArgumentException.class, () -> backend("https://s3.example.com/proxy", true));
        assertThrows(IllegalArgumentException.class, () -> backend("http://127.0.0.1:19000", false));
    }

    @Test void paginatedNamespacedListReadsRealMetadataAndEscapesToken() throws Exception {
        String first = ObjectKeys.generate(), second = ObjectKeys.generate();
        AtomicInteger lists = new AtomicInteger(), heads = new AtomicInteger();
        AtomicReference<Throwable> serverFailure = new AtomicReference<>();
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/", exchange -> {
            try {
                assertEquals("127.0.0.1:" + server.getAddress().getPort(), exchange.getRequestHeaders().getFirst("Host"));
                if (exchange.getRequestMethod().equals("HEAD")) {
                    heads.incrementAndGet();
                    String id = exchange.getRequestURI().getPath().endsWith(first) ? first : second;
                    headers(exchange, id, "STAGING");
                    exchange.sendResponseHeaders(200, -1);
                } else {
                    int page = lists.incrementAndGet();
                    String query = exchange.getRequestURI().getRawQuery();
                    assertTrue(query.contains("prefix=objects%2F"));
                    if (page == 2) assertTrue(query.contains("continuation-token=next%2B%2F%3D%26"));
                    String xml = "<ListBucketResult xmlns=\"http://s3.amazonaws.com/doc/2006-03-01/\"><IsTruncated>" +
                        (page == 1) + "</IsTruncated><Contents><Key>objects/" + (page == 1 ? first : second) +
                        "</Key></Contents>" + (page == 1 ? "<NextContinuationToken>next+/=&amp;</NextContinuationToken>" : "") + "</ListBucketResult>";
                    byte[] bytes = xml.getBytes(StandardCharsets.UTF_8);
                    exchange.sendResponseHeaders(200, bytes.length); exchange.getResponseBody().write(bytes);
                }
            } catch (Throwable failure) { serverFailure.set(failure); exchange.sendResponseHeaders(500, -1); }
            finally { exchange.close(); }
        });
        server.start();
        try {
            var objects = backend("http://127.0.0.1:" + server.getAddress().getPort(), true).listStaging();
            assertNull(serverFailure.get()); assertEquals(2, lists.get()); assertEquals(2, heads.get());
            assertEquals(Set.of(first, second), new HashSet<>(objects.stream().map(o -> o.ref().key()).toList()));
            assertEquals(4, objects.getFirst().ref().size());
        } finally { server.stop(0); }
    }

    static void headers(com.sun.net.httpserver.HttpExchange exchange, String id, String status) {
        Map.of("key", id, "hash", SigV4.hexSha256("data".getBytes()), "size", "4", "status", status,
            "created-at", "0", "schema-version", "1", "mime", "text/plain").forEach((k, v) -> exchange.getResponseHeaders().set("x-amz-meta-" + k, v));
        exchange.getResponseHeaders().set("Content-Length", "4");
    }

    @Test void malformedXmlXxeMissingPaginationTokenAndHeadFailureAreNotEmptySuccess() throws Exception {
        for (String mode : List.of("malformed", "xxe", "token", "head")) {
            HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
            server.createContext("/", exchange -> {
                try {
                    if (exchange.getRequestMethod().equals("HEAD")) { exchange.sendResponseHeaders(503, -1); return; }
                    String xml = switch (mode) {
                        case "malformed" -> "<ListBucketResult>";
                        case "xxe" -> "<!DOCTYPE root [<!ENTITY x SYSTEM 'file:///not-readable'>]><ListBucketResult>&x;</ListBucketResult>";
                        case "token" -> "<ListBucketResult><IsTruncated>true</IsTruncated></ListBucketResult>";
                        default -> "<ListBucketResult><IsTruncated>false</IsTruncated><Contents><Key>objects/" + ObjectKeys.generate() + "</Key></Contents></ListBucketResult>";
                    };
                    byte[] bytes = xml.getBytes(StandardCharsets.UTF_8);
                    exchange.sendResponseHeaders(200, bytes.length); exchange.getResponseBody().write(bytes);
                } finally { exchange.close(); }
            });
            server.start();
            try { assertEquals(503, assertThrows(PublicFailure.class, () ->
                backend("http://127.0.0.1:" + server.getAddress().getPort(), true).listStaging()).status(), mode); }
            finally { server.stop(0); }
        }
    }

    @Test void copySignsAllReplacementMetadataAndRejectsHttp200Error() throws Exception {
        String id = ObjectKeys.generate();
        AtomicReference<String> authorization = new AtomicReference<>();
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/", exchange -> {
            try {
                if (exchange.getRequestMethod().equals("HEAD")) { headers(exchange, id, "STAGING"); exchange.sendResponseHeaders(200, -1); }
                else {
                    String body = "data";
                    if (exchange.getRequestMethod().equals("PUT")) {
                        authorization.set(exchange.getRequestHeaders().getFirst("Authorization"));
                        body = "<Error><Code>InternalError</Code></Error>";
                    }
                    byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
                    exchange.sendResponseHeaders(200, bytes.length); exchange.getResponseBody().write(bytes);
                }
            } finally { exchange.close(); }
        });
        server.start();
        try {
            var ref = new ObjectRef(id, SigV4.hexSha256("data".getBytes()), 4, "text/plain", false);
            assertEquals("S3_COPY_FAILED", assertThrows(PublicFailure.class, () ->
                backend("http://127.0.0.1:" + server.getAddress().getPort(), true).markCommitted(ref)).code());
            assertTrue(authorization.get().contains("x-amz-meta-status"));
            assertTrue(authorization.get().contains("x-amz-meta-hash"));
            assertTrue(authorization.get().contains("x-amz-copy-source"));
        } finally { server.stop(0); }
    }
}

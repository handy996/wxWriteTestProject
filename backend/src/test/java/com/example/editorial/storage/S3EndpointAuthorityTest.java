package com.example.editorial.storage;

import static org.junit.jupiter.api.Assertions.*;
import java.io.*;
import java.net.*;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.KeyStore;
import java.time.*;
import java.util.*;
import java.util.concurrent.*;
import javax.net.ssl.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

/** Capture real JDK HTTP and TLS requests through a loopback proxy on an ephemeral port.
 * The proxy avoids requiring privileged ports or public DNS for virtual-hosted endpoints.
 * It does not simulate an S3 server or assert real-bucket acceptance.
 */
class S3EndpointAuthorityTest {
    @TempDir static Path directory;
    static SSLContext tls;
    static final Instant NOW = Instant.parse("2026-10-04T00:00:00Z");
    static final SigV4.Credentials CREDENTIALS = new SigV4.Credentials("fixture-id", "test-fixture-only", "us-east-1");

    @BeforeAll static void certificate() throws Exception {
        String password = UUID.randomUUID().toString();
        Path store = directory.resolve("loopback.p12"), output = directory.resolve("keytool.log");
        String executable = System.getProperty("os.name").startsWith("Windows") ? "keytool.exe" : "keytool";
        Process process = new ProcessBuilder(Path.of(System.getProperty("java.home"), "bin", executable).toString(),
            "-genkeypair", "-alias", "loopback", "-keyalg", "RSA", "-keysize", "2048", "-validity", "1",
            "-dname", "CN=s3.invalid", "-ext", "SAN=DNS:s3.invalid,DNS:private-bucket.s3.invalid",
            "-storetype", "PKCS12", "-keystore", store.toString(), "-storepass", password, "-noprompt")
            .redirectErrorStream(true).redirectOutput(output.toFile()).start();
        try {
            assertTrue(process.waitFor(30, TimeUnit.SECONDS), "test certificate generation timed out");
            assertEquals(0, process.exitValue(), "test certificate generation failed");
        } finally { if (process.isAlive()) process.destroyForcibly(); }
        KeyStore keys = KeyStore.getInstance("PKCS12");
        try (var input = Files.newInputStream(store)) { keys.load(input, password.toCharArray()); }
        var keyManagers = KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm());
        keyManagers.init(keys, password.toCharArray());
        var trustManagers = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm());
        trustManagers.init(keys);
        tls = SSLContext.getInstance("TLS");
        tls.init(keyManagers.getKeyManagers(), trustManagers.getTrustManagers(), null);
        // Trust is restricted to this client's temporary certificate; no global TLS/Host override.
    }

    record Captured(String method, URI target, Map<String, String> headers, byte[] body) {}

    static Captured read(Socket socket) throws IOException {
        // Read the header byte by byte so CONNECT cannot consume TLS handshake bytes.
        var input = socket.getInputStream();
        var header = new ByteArrayOutputStream();
        int end = 0;
        while (end != 0x0d0a0d0a) {
            int value = input.read();
            if (value < 0) throw new EOFException("missing request headers");
            header.write(value); end = (end << 8) | value;
            if (header.size() > 65536) throw new IOException("oversized test request headers");
        }
        String[] lines = header.toString(StandardCharsets.ISO_8859_1).split("\r\n");
        String[] request = lines[0].split(" ", 3);
        Map<String, String> headers = new TreeMap<>();
        for (int i = 1; i < lines.length; i++) {
            int colon = lines[i].indexOf(':');
            headers.put(lines[i].substring(0, colon).toLowerCase(Locale.ROOT), lines[i].substring(colon + 1).trim());
        }
        byte[] body = input.readNBytes(Integer.parseInt(headers.getOrDefault("content-length", "0")));
        return new Captured(request[0], URI.create(request[1]), headers, body);
    }

    static Captured receive(ServerSocket proxy) throws Exception {
        try (Socket socket = proxy.accept()) {
            socket.setSoTimeout(10000);
            Captured request = read(socket);
            if (request.method().equals("CONNECT")) {
                socket.getOutputStream().write("HTTP/1.1 200 Connection Established\r\n\r\n".getBytes(StandardCharsets.US_ASCII));
                socket.getOutputStream().flush();
                try (var secure = (SSLSocket) tls.getSocketFactory().createSocket(socket, "s3.invalid", 443, false)) {
                    secure.setUseClientMode(false); secure.setSoTimeout(10000); secure.startHandshake();
                    request = read(secure);
                    respond(secure);
                    return request;
                }
            }
            respond(socket);
            return request;
        }
    }

    static void respond(Socket socket) throws IOException {
        socket.getOutputStream().write("HTTP/1.1 200 OK\r\nContent-Length: 4\r\nConnection: close\r\n\r\ndata".getBytes(StandardCharsets.US_ASCII));
        socket.getOutputStream().flush();
    }

    @ParameterizedTest
    @CsvSource({
        "http://s3.invalid, true, s3.invalid",
        "http://s3.invalid:80, true, s3.invalid",
        "https://s3.invalid, true, s3.invalid",
        "https://s3.invalid:443, true, s3.invalid",
        "http://s3.invalid:19000, true, s3.invalid:19000",
        "https://s3.invalid:19443, true, s3.invalid:19443",
        "http://s3.invalid:80, false, private-bucket.s3.invalid",
        "https://s3.invalid:443, false, private-bucket.s3.invalid",
        "http://s3.invalid:19000, false, private-bucket.s3.invalid:19000"
    })
    void ordinaryAndPresignedRequestsSignTheWireHost(String endpoint, boolean pathStyle, String expectedHost) throws Exception {
        try (var proxy = new ServerSocket(0, 10, InetAddress.getByName("127.0.0.1"));
             var executor = Executors.newVirtualThreadPerTaskExecutor();
             var client = HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1).sslContext(tls)
                 .proxy(ProxySelector.of(new InetSocketAddress("127.0.0.1", proxy.getLocalPort())))
                 .connectTimeout(Duration.ofSeconds(10)).build()) {
            proxy.setSoTimeout(10000);
            var backend = new S3StorageBackend(S3StorageBackend.Config.of(endpoint, "private-bucket", "us-east-1",
                CREDENTIALS.accessKey(), CREDENTIALS.secretKey(), pathStyle), client, () -> NOW);
            byte[] bytes = "data".getBytes(StandardCharsets.UTF_8);
            var ref = new ObjectRef(ObjectKeys.generate(), SigV4.hexSha256(bytes), bytes.length, "text/plain", false);
            var pending = executor.submit(() -> receive(proxy));
            backend.put(new StoredObject(ref, ObjectStatus.STAGING, 1, NOW, null), bytes);
            Captured sent = pending.get(10, TimeUnit.SECONDS);
            assertEquals(expectedHost, sent.headers().get("host"));
            assertArrayEquals(bytes, sent.body());
            Map<String, String> metadata = new TreeMap<>();
            sent.headers().forEach((key, value) -> { if (key.startsWith("x-amz-meta-")) metadata.put(key, value); });
            String expected = SigV4.sign(CREDENTIALS, sent.method(), sent.headers().get("host"), sent.target().getRawPath(),
                sent.target().getRawQuery(), sent.body(), metadata, NOW).get("Authorization");
            assertEquals(expected, sent.headers().get("authorization"), "ordinary signature must match the captured wire Host");

            URI url = URI.create(backend.presignDownload(ref, Duration.ofMinutes(5)));
            assertEquals(expectedHost, url.getRawAuthority());
            pending = executor.submit(() -> receive(proxy));
            var response = client.send(HttpRequest.newBuilder(url).timeout(Duration.ofSeconds(10)).GET().build(), HttpResponse.BodyHandlers.ofByteArray());
            assertEquals(200, response.statusCode());
            sent = pending.get(10, TimeUnit.SECONDS);
            assertEquals(expectedHost, sent.headers().get("host"));
            URI wireAddress = URI.create(url.getScheme() + "://" + sent.headers().get("host") + sent.target().getRawPath());
            URI expectedPresign = URI.create(SigV4.presignGet(CREDENTIALS, wireAddress, NOW, Duration.ofMinutes(5)));
            assertEquals(expectedPresign.getRawQuery(), sent.target().getRawQuery(), "presign must match the captured wire Host");
        }
    }

    @Test void directSignerPreservesEncodedPathQueryAndIpv6WhileNormalizingDefaultPort() {
        for (String scheme : List.of("http", "https")) {
            int port = scheme.equals("http") ? 80 : 443;
            String base = scheme + "://[::1]";
            String path = "/bucket/a%2Fb//c%20d";
            var implicit = URI.create(base + path + "?prefix=a%2Fb");
            var explicit = URI.create(base + ":" + port + path + "?prefix=a%2Fb");
            assertEquals(SigV4.sign(CREDENTIALS, "GET", implicit, null, null, NOW),
                SigV4.sign(CREDENTIALS, "GET", explicit, null, null, NOW));
            assertEquals(SigV4.presignGet(CREDENTIALS, URI.create(base + path), NOW, Duration.ofMinutes(5)),
                SigV4.presignGet(CREDENTIALS, URI.create(base + ":" + port + path), NOW, Duration.ofMinutes(5)));
        }
    }
}

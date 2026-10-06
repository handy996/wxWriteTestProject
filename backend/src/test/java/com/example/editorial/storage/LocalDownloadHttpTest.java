package com.example.editorial.storage;

import static org.junit.jupiter.api.Assertions.*;
import java.net.URI;
import java.net.http.*;
import java.nio.file.*;
import java.time.*;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import org.junit.jupiter.api.*;
import org.springframework.boot.autoconfigure.EnableAutoConfiguration;
import org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration;
import org.springframework.boot.autoconfigure.orm.jpa.HibernateJpaAutoConfiguration;
import org.springframework.boot.autoconfigure.flyway.FlywayAutoConfiguration;
import org.springframework.boot.autoconfigure.security.servlet.UserDetailsServiceAutoConfiguration;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.web.servlet.context.ServletWebServerApplicationContext;
import org.springframework.context.annotation.*;
import org.springframework.core.annotation.Order;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.web.SecurityFilterChain;

/** Actual Tomcat/Spring handler mapping/security chain and real HTTP bytes, no MockMvc. */
class LocalDownloadHttpTest {
    static Path directory;
    static ServletWebServerApplicationContext app;
    static String base;
    static LocalStorageBackend backend;
    static final String SECRET = "local-download-test-fixture-only";
    static final Map<String, ObjectRefRegistry.Resolution> REFERENCES = new ConcurrentHashMap<>();
    static final HttpClient CLIENT = HttpClient.newHttpClient();

    @Configuration(proxyBeanMethods = false)
    @EnableAutoConfiguration(exclude = {DataSourceAutoConfiguration.class, HibernateJpaAutoConfiguration.class,
        FlywayAutoConfiguration.class, UserDetailsServiceAutoConfiguration.class})
    @Import(LocalDownloadConfiguration.class)
    static class App {
        @Bean StorageBackend storageBackend() { return new LocalStorageBackend(directory, "http://unused", SECRET); }
        @Bean ObjectRefRegistry references() {
            return new ObjectRefRegistry() {
                public Resolution resolve(String id) { return REFERENCES.get(id); }
                public boolean referenced(String id) { return REFERENCES.containsKey(id); }
            };
        }
        @Bean @Order(2) SecurityFilterChain otherRoutes(HttpSecurity http) throws Exception {
            return http.authorizeHttpRequests(c -> c.anyRequest().denyAll()).build();
        }
    }

    @BeforeAll static void start() throws Exception {
        directory = Files.createTempDirectory("t04-http-");
        app = (ServletWebServerApplicationContext) new SpringApplicationBuilder(App.class)
            .properties(Map.of("server.port", "0", "server.address", "127.0.0.1", "editorial.storage.enabled", "true",
                "editorial.storage.mode", "local", "spring.main.banner-mode", "off", "logging.level.root", "WARN"))
            .run("--server.port=0", "--server.address=127.0.0.1", "--management.endpoint.health.group.readiness.include=ping");
        base = "http://127.0.0.1:" + app.getWebServer().getPort();
        backend = (LocalStorageBackend) app.getBean(StorageBackend.class);
    }
    @AfterAll static void stop() { if (app != null) app.close(); }

    ObjectRef committed() {
        byte[] bytes = "private HTTP content".getBytes();
        ObjectRef ref = new ObjectRef(ObjectKeys.generate(), SigV4.hexSha256(bytes), bytes.length, "text/plain", false);
        backend.put(new StoredObject(ref, ObjectStatus.STAGING, 1, Instant.now(), null), bytes);
        backend.markCommitted(ref);
        REFERENCES.put(ref.key(), new ObjectRefRegistry.Resolution(UUID.randomUUID(), "IMAGE_VARIANT", false));
        return ref;
    }
    String link(ObjectRef ref, Instant expires) { return SignedUrl.sign(SECRET, ref.key(), base, expires); }
    HttpResponse<byte[]> fetch(String url) throws Exception {
        return CLIENT.send(HttpRequest.newBuilder(URI.create(url)).GET().build(), HttpResponse.BodyHandlers.ofByteArray());
    }

    @Test void validCapabilityDownloadsExactBytesWithPrivateHeaders() throws Exception {
        ObjectRef ref = committed();
        var response = fetch(link(ref, Instant.now().plusSeconds(300)));
        assertEquals(200, response.statusCode());
        assertArrayEquals(backend.get(ref), response.body());
        assertEquals("no-store", response.headers().firstValue("cache-control").orElseThrow());
        assertEquals("nosniff", response.headers().firstValue("x-content-type-options").orElseThrow());
        assertTrue(response.headers().firstValue("content-disposition").orElseThrow().startsWith("attachment;"));
    }

    @Test void disabledStorageAndS3DoNotRegisterLocalRoute() {
        for (String[] properties : List.of(new String[]{"editorial.storage.enabled=false"},
                new String[]{"editorial.storage.enabled=true", "editorial.storage.mode=s3"})) {
            new org.springframework.boot.test.context.runner.ApplicationContextRunner()
                .withUserConfiguration(LocalDownloadConfiguration.class).withPropertyValues(properties)
                .run(context -> {
                    assertNull(context.getStartupFailure());
                    assertFalse(context.containsBean("localDownloadHandler"));
                    assertFalse(context.containsBean("localDownloadSecurity"));
                });
        }
    }

    @Test void unsignedExpiredTamperedAndDuplicateParameterRequestsAreDenied() throws Exception {
        ObjectRef ref = committed();
        String valid = link(ref, Instant.now().plusSeconds(300));
        for (String url : List.of(base + LocalDownloadHandler.PATH + ref.key(), link(ref, Instant.now().minusSeconds(1)),
                valid.replace("signature=", "signature=00"), valid + "&expires=9999999999",
                valid.replace(ref.key(), ObjectKeys.generate()))) {
            var response = fetch(url);
            assertEquals(403, response.statusCode());
            assertFalse(new String(response.body()).contains("private HTTP content"));
        }
        assertNotEquals(200, fetch(base + "/api/v1/other").statusCode());
    }

    @Test void revokedUnknownAndMissingObjectsRejectPreviouslyValidLink() throws Exception {
        ObjectRef ref = committed(); String valid = link(ref, Instant.now().plusSeconds(300));
        var resolution = REFERENCES.get(ref.key());
        REFERENCES.put(ref.key(), new ObjectRefRegistry.Resolution(resolution.articleId(), resolution.entityType(), true));
        assertEquals(404, fetch(valid).statusCode());
        REFERENCES.remove(ref.key()); assertEquals(404, fetch(valid).statusCode());
        REFERENCES.put(ref.key(), resolution);
        Files.delete(directory.resolve("objects").resolve(ref.key()));
        assertEquals(404, fetch(valid).statusCode());
    }
}

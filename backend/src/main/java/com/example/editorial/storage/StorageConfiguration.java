package com.example.editorial.storage;

import com.example.editorial.audit.AuditSink;
import com.example.editorial.shared.Ownership;
import java.nio.file.Path;
import java.time.Clock;
import java.time.Duration;
import java.util.List;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.transaction.PlatformTransactionManager;

/**
 * Wires the object store. Disabled by default; enabled by the main agent at
 * integration alongside T03 identity (the store requires Ownership, AuditSink
 * and a transaction manager). Backend selection and all credentials come from
 * server configuration only — never from client input.
 */
@Configuration(proxyBeanMethods = false)
@ConditionalOnProperty(name = "editorial.storage.enabled", havingValue = "true")
public class StorageConfiguration {

    @Bean StorageBackend storageBackend(
            @Value("${editorial.storage.mode:local}") String mode,
            @Value("${editorial.storage.local.dir:${java.io.tmpdir}/wxagent-editorial-storage}") String localDir,
            @Value("${editorial.storage.local.download-base:}") String downloadBase,
            @Value("${editorial.storage.local.download-secret:}") String downloadSecret,
            @Value("${editorial.storage.s3.endpoint:}") String s3Endpoint,
            @Value("${editorial.storage.s3.bucket:}") String s3Bucket,
            @Value("${editorial.storage.s3.region:}") String s3Region,
            @Value("${editorial.storage.s3.access-key:}") String s3AccessKey,
            @Value("${editorial.storage.s3.secret-key:}") String s3SecretKey,
            @Value("${editorial.storage.s3.path-style:true}") boolean s3PathStyle) {
        return switch (mode) {
            case "local" -> new LocalStorageBackend(Path.of(localDir), blankToNull(downloadBase), blankToNull(downloadSecret));
            case "s3" -> new S3StorageBackend(S3StorageBackend.Config.of(
                blankToNull(s3Endpoint), blankToNull(s3Bucket), blankToNull(s3Region),
                blankToNull(s3AccessKey), blankToNull(s3SecretKey), s3PathStyle));
            default -> throw new IllegalStateException("T04_STORAGE: mode must be local or s3");
        };
    }

    @Bean ObjectStore objectStore(StorageBackend backend, Ownership ownership, AuditSink audit,
                                  PlatformTransactionManager manager, List<ObjectRefRegistry> registries,
                                  @Value("${editorial.storage.max-object-bytes:67108864}") long maxBytes,
                                  @Value("${editorial.storage.orphan-ttl-seconds:86400}") long ttlSeconds) {
        return new DefaultObjectStore(backend, ownership, audit, manager, registries,
            Clock.systemUTC(), maxBytes, Duration.ofSeconds(ttlSeconds));
    }

    private static String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value;
    }
}

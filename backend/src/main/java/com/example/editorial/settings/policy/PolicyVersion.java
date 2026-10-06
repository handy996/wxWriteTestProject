package com.example.editorial.settings.policy;

import com.fasterxml.jackson.databind.JsonNode;
import java.time.Instant;
import java.util.UUID;

/** Persisted policy_version row (internal, not a wire DTO). */
public record PolicyVersion(UUID id, PolicyType type, String version, JsonNode rules, String hash,
                            PublicationStatus status, UUID createdBy, UUID publishedBy, Instant publishedAt,
                            Instant createdAt, long lockVersion) {}

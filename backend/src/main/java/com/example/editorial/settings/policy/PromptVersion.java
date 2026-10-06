package com.example.editorial.settings.policy;

import com.fasterxml.jackson.databind.JsonNode;
import java.time.Instant;
import java.util.UUID;

/** Persisted prompt_version row (internal, not a wire DTO). */
public record PromptVersion(UUID id, String agentName, String version, String systemTemplate, String userTemplate,
                            JsonNode outputSchema, String hash, PublicationStatus status, UUID createdBy,
                            Instant createdAt, long lockVersion) {}

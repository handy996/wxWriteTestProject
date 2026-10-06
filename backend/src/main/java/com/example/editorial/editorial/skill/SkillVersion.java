package com.example.editorial.editorial.skill;

import com.example.editorial.settings.policy.PublicationStatus;
import com.fasterxml.jackson.databind.JsonNode;
import java.time.Instant;
import java.util.UUID;

/** Persisted editorial_skill_version row (internal, not a wire DTO). */
public record SkillVersion(UUID id, UUID skillId, String version, JsonNode config, String rulesHash,
                           String schemaVersion, PublicationStatus status, UUID parentVersionId, String changeLog,
                           UUID createdBy, UUID publishedBy, Instant publishedAt, Instant createdAt, long lockVersion) {}

package com.example.editorial.editorial.skill;

import com.example.editorial.settings.policy.PolicySnapshot;
import com.example.editorial.settings.policy.PublicationStatus;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.List;
import java.util.UUID;

/**
 * Frozen DTO matching editorial.schema.json {@code $defs/SkillSnapshot}. Immutable projection of a specific
 * skill version: id/version/rulesHash/schemaVersion/config/policySnapshots/status, projected from the version
 * row — never from a mutable "current active version" head.
 */
public record SkillSnapshot(UUID id, UUID skillId, String version, String rulesHash, String schemaVersion,
                            JsonNode config, List<PolicySnapshot> policySnapshots, PublicationStatus status) {}

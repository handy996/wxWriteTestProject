package com.example.editorial.editorial.skill;

import java.util.UUID;

/** Frozen DTO matching editorial.schema.json {@code $defs/SkillIdentity}. */
public record SkillIdentity(UUID id, String code, String name, UUID activeVersionId) {}

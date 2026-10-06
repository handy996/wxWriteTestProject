package com.example.editorial.editorial.skill;

import java.util.List;

/** Frozen page envelope matching editorial.schema.json {@code $defs/SkillIdentityPage}. */
public record SkillIdentityPage(List<SkillIdentity> items, String nextCursor) {}

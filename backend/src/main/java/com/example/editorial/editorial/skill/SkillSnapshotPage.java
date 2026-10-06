package com.example.editorial.editorial.skill;

import java.util.List;

/** Frozen page envelope matching editorial.schema.json {@code $defs/SkillSnapshotPage}. */
public record SkillSnapshotPage(List<SkillSnapshot> items, String nextCursor) {}

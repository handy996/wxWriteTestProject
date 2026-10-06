package com.example.editorial.editorial.skill;

import com.example.editorial.shared.ActorContext;
import java.util.UUID;

/**
 * Frozen service port (ports.json {@code SkillSnapshot.read}): {@code read(ActorContext, skillVersionId) -> SkillSnapshot},
 * error {@code SKILL_NOT_PUBLISHED}. Returns the immutable projection of the specific version row (owner-checked),
 * so publishing or retiring later never rewrites a previously read snapshot.
 */
public final class SkillSnapshotPort {
    private final SkillService skills;
    public SkillSnapshotPort(SkillService skills) { this.skills = skills; }

    public SkillSnapshot read(ActorContext actor, UUID skillVersionId) {
        return skills.readPublished(actor, skillVersionId);
    }
}

package com.example.editorial.editorial.skill;

import java.time.Instant;
import java.util.UUID;

/**
 * Configuration-change notification for T11. Emitted once per committed publish/retire of a skill version;
 * the {@code idempotencyKey} is deterministic per (skillVersionId, reason) so T11 can consume idempotently.
 * T05 only emits this event on skill config changes — never on budget-only edits (that is T06/T11's boundary).
 */
public record ConfigChangeEvent(UUID eventId, UUID skillId, UUID skillVersionId, String reason,
                                Instant occurredAt, String idempotencyKey) {
    public static String key(UUID skillVersionId, String reason) {
        return "skill-config|" + skillVersionId + "|" + reason;
    }
}

package com.example.editorial.settings.policy;

import java.util.UUID;

/**
 * Frozen service port (ports.json {@code PolicySnapshot.read}): {@code read(policyVersionId) -> PolicySnapshot},
 * error {@code POLICY_NOT_FOUND}. The returned snapshot carries the actual policy version id/type/version/hash and a
 * content-addressed rules reference, and is immutable — it is projected from the version row, never from a mutable
 * "current" head.
 */
public final class PolicySnapshotPort {
    private final PolicyService policies;
    public PolicySnapshotPort(PolicyService policies) { this.policies = policies; }

    public PolicySnapshot read(UUID policyVersionId) {
        return policies.snapshot(policyVersionId);
    }
}

package com.example.editorial.settings.policy;

import com.example.editorial.storage.ObjectRef;
import java.util.UUID;

/** Frozen DTO matching editorial.schema.json {@code $defs/PolicySnapshot}. Immutable projection of a policy version. */
public record PolicySnapshot(UUID id, PolicyType type, String version, String hash, ObjectRef rules) {}

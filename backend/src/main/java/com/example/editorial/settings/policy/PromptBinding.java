package com.example.editorial.settings.policy;

import java.util.UUID;

/** Frozen DTO matching editorial.schema.json {@code $defs/PromptBinding}. */
public record PromptBinding(String agentName, UUID promptVersionId, String hash, String outputSchema) {}

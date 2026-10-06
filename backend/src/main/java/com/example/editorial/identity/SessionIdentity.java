package com.example.editorial.identity;

import java.io.Serializable;
import java.time.Instant;
import java.util.UUID;

/** Session principal contains no credential/hash/token. */
public record SessionIdentity(UUID id, String displayName, Instant authenticatedAt) implements Serializable {}

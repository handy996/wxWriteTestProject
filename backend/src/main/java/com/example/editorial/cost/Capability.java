package com.example.editorial.cost;

import com.example.editorial.shared.PublicFailure;

/** rc.3 {@code AIRequest.capability}: the four billed capabilities a chargeable call may declare. */
public enum Capability {
    TEXT, VISION, SEARCH, GENERATION;

    /** Image generation is the only capability the pipeline may start automatically, so its price must be known. */
    public boolean isAutomaticImageGeneration() { return this == GENERATION; }

    /** Output tokens are only billed on the model capabilities; a search or image call has none. */
    public boolean billsModelTokens() { return this == TEXT || this == VISION; }

    public static Capability of(String raw) {
        try { return valueOf(raw); }
        catch (IllegalArgumentException | NullPointerException e) { throw new PublicFailure(422, "INVALID_CAPABILITY"); }
    }
}

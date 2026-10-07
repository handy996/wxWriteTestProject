package com.example.editorial.cost;

import com.example.editorial.shared.PublicFailure;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.EnumMap;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

/**
 * One frozen price version for one provider model: the set of published rates per billed capability, plus the
 * canonical hash the ledger pins so a settlement is always computed against the same numbers the estimate was.
 *
 * <p>Absence and zero are different states. A capability with no entry is an <em>unknown</em> price and must
 * stop a chargeable call; a capability whose published rates are all zero is a real free price and must not be
 * confused with a missing configuration. That distinction is what allows a free-tier text call while keeping
 * automatic image generation forbidden until its price is known.</p>
 */
public record PriceVersion(UUID id, String provider, String model, Map<Capability, PriceEntry> entries, String hash) {

    public PriceVersion {
        Map<Capability, PriceEntry> copy = new EnumMap<>(Capability.class);
        copy.putAll(entries);
        entries = Map.copyOf(copy);
    }

    public Optional<PriceEntry> find(Capability capability) { return Optional.ofNullable(entries.get(capability)); }

    public boolean known(Capability capability) { return entries.containsKey(capability); }

    /**
     * Estimate for a planned call. An absent price is never silently read as zero, and the estimate always rounds
     * up: a published rate must never reserve less than it can cost, whatever rounding the settlement uses.
     */
    public Money estimate(Capability capability, Usage usage, Money otherProviderFees) {
        PriceEntry entry = find(capability).orElseThrow(() -> unknown(capability));
        return entry.cost(usage, otherProviderFees, estimateRounding());
    }

    /** Actual cost of a reported call, priced under the same frozen version as its estimate. */
    public Money actual(Capability capability, Usage usage, Money otherProviderFees) {
        PriceEntry entry = find(capability).orElseThrow(() -> unknown(capability));
        return entry.cost(usage, otherProviderFees);
    }

    /**
     * Automatic image generation is only allowed when the generation price is known. A published zero is
     * accepted; a missing entry refuses the call with its own code so the caller cannot fall back to a guess.
     */
    public PriceEntry requireGeneratable() {
        return find(Capability.GENERATION).orElseThrow(() -> unknown(Capability.GENERATION));
    }

    public PublicFailure unknown(Capability capability) {
        return new PublicFailure(409, capability == Capability.GENERATION ? "GENERATION_PRICE_UNKNOWN" : "PRICING_UNKNOWN");
    }

    /** Rounding used when turning rates into an estimate: never under-reserve a published rate. */
    public static RoundingMode estimateRounding() { return RoundingMode.CEILING; }

    public BigDecimal rate(Capability capability, java.util.function.Function<PriceEntry, BigDecimal> field) {
        return find(capability).map(field).orElseThrow(() -> unknown(capability));
    }
}

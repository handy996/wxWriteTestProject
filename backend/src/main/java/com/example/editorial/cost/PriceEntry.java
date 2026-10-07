package com.example.editorial.cost;

import com.example.editorial.shared.PublicFailure;
import java.math.BigDecimal;
import java.math.RoundingMode;

/**
 * One published unit price set inside a {@link PriceVersion}. Rates are decimal strings per one million tokens
 * (or per call/unit for tool and image fees), so no money arithmetic ever passes through a float.
 *
 * <p>Reasoning tokens have exactly two lawful shapes. A provider that already counts reasoning inside its
 * output total bills the reported output once ({@code reasoningBilledSeparately=false}); adding that count
 * again would charge the same tokens twice, which is what this flag exists to prevent. A provider that bills
 * reasoning as its own line is declared with the flag and its own rate, and only then are reasoning tokens
 * priced — on top of the non-reasoning remainder, never on top of the whole output.</p>
 */
public record PriceEntry(Capability capability, BigDecimal inputPerMillion, BigDecimal cachedInputPerMillion,
                         BigDecimal outputPerMillion, BigDecimal reasoningPerMillion, BigDecimal searchPerCall,
                         BigDecimal imagePerUnit, BigDecimal otherPerCall, boolean reasoningBilledSeparately,
                         RoundingMode rounding) {

    public PriceEntry {
        rounding = rounding == null ? RoundingMode.CEILING : rounding;
        for (BigDecimal rate : new BigDecimal[]{inputPerMillion, cachedInputPerMillion, outputPerMillion,
                reasoningPerMillion, searchPerCall, imagePerUnit, otherPerCall})
            if (rate == null) throw new PublicFailure(503, "PRICING_INCOMPLETE");
        if (inputPerMillion.signum() < 0 || cachedInputPerMillion.signum() < 0 || outputPerMillion.signum() < 0
                || reasoningPerMillion.signum() < 0 || searchPerCall.signum() < 0 || imagePerUnit.signum() < 0
                || otherPerCall.signum() < 0)
            throw new PublicFailure(503, "NEGATIVE_PRICING");
        if (cachedInputPerMillion.compareTo(inputPerMillion) > 0) throw new PublicFailure(503, "CACHED_RATE_ABOVE_INPUT");
    }

    /** Tokens billed at the plain output rate: everything reported, or only the non-reasoning remainder. */
    public int standardOutputTokens(Usage usage) {
        if (!reasoningBilledSeparately) return usage.outputTokens();
        int reasoning = usage.reasoningTokensIfProvided() == null ? 0 : usage.reasoningTokensIfProvided();
        if (reasoning > usage.outputTokens()) throw new PublicFailure(422, "REASONING_TOKENS_EXCEED_OUTPUT");
        return usage.outputTokens() - reasoning;
    }

    /** Tokens billed at the reasoning rate. Zero unless the price version declares reasoning is billed separately. */
    public int reasoningTokens(Usage usage) {
        if (!reasoningBilledSeparately || usage.reasoningTokensIfProvided() == null) return 0;
        return usage.reasoningTokensIfProvided();
    }

    /** Total tokens charged on the output line. Never more than the reported output, so nothing is counted twice. */
    public int billedOutputTokens(Usage usage) {
        int billed = standardOutputTokens(usage) + reasoningTokens(usage);
        if (billed > usage.outputTokens()) throw new PublicFailure(503, "PRICING_DOUBLE_COUNT");
        return billed;
    }

    /**
     * The SRS 32.3 cost formula, component by component at the canonical six-decimal scale: uncached input,
     * cached input, output, reasoning, search calls, image units, then other provider fees. Settlements use the
     * rounding the published version declares; estimates use the rounding {@link PriceVersion} forces upward.
     */
    public Money cost(Usage usage, Money otherProviderFees) {
        return cost(usage, otherProviderFees, rounding);
    }

    public Money cost(Usage usage, Money otherProviderFees, RoundingMode mode) {
        return Money.ZERO
                .add(perMillion(inputPerMillion, usage.uncachedInputTokens(), mode))
                .add(perMillion(cachedInputPerMillion, usage.cachedInputTokens(), mode))
                .add(perMillion(outputPerMillion, standardOutputTokens(usage), mode))
                .add(perMillion(reasoningPerMillion, reasoningTokens(usage), mode))
                .add(perCall(searchPerCall, usage.searchCalls(), mode))
                .add(perCall(imagePerUnit, usage.imageUnits(), mode))
                .add(otherProviderFees == null ? Money.ZERO : otherProviderFees);
    }

    /** True when every rate is exactly zero: a real published free price, never a missing configuration. */
    public boolean isPublishedFree() {
        return inputPerMillion.signum() == 0 && cachedInputPerMillion.signum() == 0 && outputPerMillion.signum() == 0
                && reasoningPerMillion.signum() == 0 && searchPerCall.signum() == 0 && imagePerUnit.signum() == 0
                && otherPerCall.signum() == 0;
    }

    public Money imageCost(int units) { return perCall(imagePerUnit, units, rounding); }

    /**
     * A rate is not money: it may carry more decimals than the canonical six, so it is priced here and only the
     * result enters {@link Money}. Nothing in this path uses a double.
     */
    private static Money perMillion(BigDecimal rate, long tokens, RoundingMode mode) {
        if (tokens < 0) throw new PublicFailure(422, "NEGATIVE_USAGE");
        if (rate.signum() < 0) throw new PublicFailure(503, "NEGATIVE_PRICING");
        if (tokens == 0 || rate.signum() == 0) return Money.ZERO;
        return Money.ofExact(rate.multiply(BigDecimal.valueOf(tokens))
                .divide(BigDecimal.valueOf(1_000_000), Money.SCALE, mode));
    }

    private static Money perCall(BigDecimal rate, long units, RoundingMode mode) {
        if (units < 0) throw new PublicFailure(422, "NEGATIVE_USAGE");
        if (rate.signum() < 0) throw new PublicFailure(503, "NEGATIVE_PRICING");
        if (units == 0 || rate.signum() == 0) return Money.ZERO;
        return Money.ofExact(rate.multiply(BigDecimal.valueOf(units)).setScale(Money.SCALE, mode));
    }
}

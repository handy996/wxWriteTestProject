package com.example.editorial.cost;

import com.example.editorial.shared.PublicFailure;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.regex.Pattern;

/**
 * Frozen money type for T08. canonical-v1 carries amounts as exactly six-decimal strings with a
 * {@code USD} literal, so this type keeps a {@link BigDecimal} at scale 6 internally and refuses every
 * other shape on the way in. There is no float/double constructor and no silent scale widening.
 */
public final class Money implements Comparable<Money> {
    public static final int SCALE = 6;
    public static final String CURRENCY = "USD";
    /** Same pattern the rc.3 contract declares for amount strings. */
    private static final Pattern WIRE = Pattern.compile("^(0|[1-9][0-9]{0,11})\\.[0-9]{6}$");
    private static final BigDecimal MAX = new BigDecimal("999999999999.999999");

    private final BigDecimal value;

    private Money(BigDecimal value) { this.value = value; }

    public static final Money ZERO = new Money(BigDecimal.ZERO.setScale(SCALE));

    /** Strict wire parse: exactly six decimals, no exponent, no sign, no surrounding spaces. */
    public static Money of(String text) {
        if (text == null || !WIRE.matcher(text).matches()) fail("INVALID_AMOUNT");
        BigDecimal parsed = new BigDecimal(text);
        if (parsed.compareTo(MAX) > 0) fail("AMOUNT_OUT_OF_RANGE");
        return new Money(parsed);
    }

    /** Trusted internal value (database NUMERIC(18,6) or a computed result). Rechecks scale and range. */
    public static Money ofExact(BigDecimal value) {
        if (value == null) fail("INVALID_AMOUNT");
        if (value.signum() < 0) fail("NEGATIVE_AMOUNT");
        if (value.scale() > SCALE) fail("AMOUNT_SCALE");
        BigDecimal scaled = value.setScale(SCALE);
        if (scaled.compareTo(MAX) > 0) fail("AMOUNT_OUT_OF_RANGE");
        return new Money(scaled);
    }

    public static Money currency(String supplied) {
        if (!CURRENCY.equals(supplied)) fail("UNSUPPORTED_CURRENCY");
        return ZERO;
    }

    public Money add(Money other) { return ofExact(value.add(other.value)); }

    /** Subtraction is a balance release, never a negative ledger amount. */
    public Money subtract(Money other) {
        BigDecimal result = value.subtract(other.value);
        if (result.signum() < 0) fail("NEGATIVE_AMOUNT");
        return ofExact(result);
    }

    /**
     * {@code unitPrice * units / unitsPerPrice} with an explicit rounding mode. Rounding is applied to the
     * component, so an estimate cannot drift below the sum of its own parts.
     */
    public Money scale(long units, long unitsPerPrice, RoundingMode mode) {
        if (units < 0) fail("NEGATIVE_USAGE");
        if (unitsPerPrice <= 0) fail("INVALID_PRICING_UNIT");
        if (units == 0 || value.signum() == 0) return ZERO;
        BigDecimal priced = value.multiply(BigDecimal.valueOf(units))
                .divide(BigDecimal.valueOf(unitsPerPrice), SCALE, mode);
        return ofExact(priced);
    }

    public Money multiply(long times, RoundingMode mode) {
        if (times < 0) fail("NEGATIVE_USAGE");
        return ofExact(value.multiply(BigDecimal.valueOf(times)).setScale(SCALE, mode));
    }

    public BigDecimal decimal() { return value; }
    public String text() { return value.toPlainString(); }
    public boolean isZero() { return value.signum() == 0; }
    public boolean exceeds(Money other) { return value.compareTo(other.value) > 0; }
    public boolean atLeast(Money other) { return value.compareTo(other.value) >= 0; }
    public Money max(Money other) { return value.compareTo(other.value) >= 0 ? this : other; }
    public Money min(Money other) { return value.compareTo(other.value) <= 0 ? this : other; }

    @Override public int compareTo(Money other) { return value.compareTo(other.value); }
    @Override public boolean equals(Object o) { return o instanceof Money m && value.compareTo(m.value) == 0; }
    @Override public int hashCode() { return value.stripTrailingZeros().hashCode(); }
    @Override public String toString() { return text() + " " + CURRENCY; }

    private static void fail(String code) { throw new PublicFailure(422, code); }
}

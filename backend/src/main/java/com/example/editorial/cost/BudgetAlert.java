package com.example.editorial.cost;

/**
 * Budget and quota alert data (SRS 34: budget above the alert percent; SRS 35: budget or quota exhausted).
 * Emitted through {@link CostPorts.AlertSink} and returned by the usage projection; delivery to a human queue
 * belongs to the notification and workflow domains, so the alert itself carries only accounting facts.
 */
public record BudgetAlert(Code code, String scope, String scopeKey, Money spent, Money reserved, Money unknown,
                          Money limit, int percent, String provider, String model, Long counterValue, Long counterCap) {

    public enum Code {
        /** Spend plus live holds reached the configured alert percent. */
        BUDGET_WARNING,
        /** The article ceiling can no longer admit the next reservation. */
        ARTICLE_BUDGET_EXCEEDED,
        /** The owner's daily ceiling can no longer admit the next reservation. */
        DAILY_BUDGET_EXCEEDED,
        /** A count cap (queries, tokens, loops, image units) is exhausted. */
        QUOTA_EXCEEDED,
        /** A provider concurrency or rate ceiling is exhausted. */
        PROVIDER_QUOTA_EXCEEDED,
        /** A reservation has been holding an outcome for longer than the reconciliation window. */
        RECONCILIATION_STALE,
        /** Price configuration is missing or unusable for a capability that was asked for. */
        PRICING_UNAVAILABLE
    }

    public BudgetAlert {
        spent = spent == null ? Money.ZERO : spent;
        reserved = reserved == null ? Money.ZERO : reserved;
        unknown = unknown == null ? Money.ZERO : unknown;
    }

    /** Percentage of the ceiling occupied, clamped for display; a zero ceiling reports 100. */
    public static int percentOf(Money occupied, Money limit) {
        if (limit.isZero()) return 100;
        long percent = occupied.decimal().multiply(java.math.BigDecimal.valueOf(100))
                .divide(limit.decimal(), 0, java.math.RoundingMode.DOWN).longValue();
        return (int) Math.min(100, Math.max(0, percent));
    }
}

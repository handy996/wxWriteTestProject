package com.example.editorial.cost;

import com.example.editorial.shared.PublicFailure;
import java.util.Set;

/** rc.3 {@code BudgetReservation.status}. RESERVED/SETTLED/RELEASED/UNKNOWN are the only states. */
public enum ReservationStatus {
    RESERVED, SETTLED, RELEASED, UNKNOWN;

    /** Transitions are one-way except that an UNKNOWN outcome may still be settled or released by reconciliation. */
    public void allowTransitionTo(ReservationStatus next) {
        boolean legal = switch (this) {
            case RESERVED -> next != RESERVED;
            case UNKNOWN -> next == SETTLED || next == RELEASED;
            case SETTLED, RELEASED -> false;
        };
        if (!legal) throw new PublicFailure(409, "SETTLEMENT_CONFLICT");
    }

    /** Still occupies the budget: the money is held until an outcome is known. */
    public boolean holdsBudget() { return this == RESERVED || this == UNKNOWN; }

    public static ReservationStatus of(String raw) {
        try { return valueOf(raw); }
        catch (IllegalArgumentException | NullPointerException e) { throw new PublicFailure(422, "INVALID_STATUS"); }
    }

    static {
        // Fail fast at class load if the frozen enum list and the transition table drift apart.
        if (Set.of(RESERVED, SETTLED, RELEASED, UNKNOWN).size() != values().length) throw new ExceptionInInitializerError();
    }
}

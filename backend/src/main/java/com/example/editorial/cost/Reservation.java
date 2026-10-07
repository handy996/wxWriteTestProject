package com.example.editorial.cost;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;

/**
 * One row of {@code cost_ledger} as the reservation it represents. {@code estimatedAmount} is the frozen
 * hold and never changes; the settlement columns only ever describe the outcome that released it. A row in
 * {@code UNKNOWN} keeps holding the estimate while it waits for reconciliation, which is why the held
 * amount is defined by status and not by the presence of a settlement.
 */
public record Reservation(UUID id, UUID article, UUID owner, UUID execution, String executionKind,
                          String provider, String model, Capability capability, Money estimatedAmount,
                          Money settledAmount, Money releasedAmount, Money overRun, UUID pricingVersion,
                          String pricingHash, ReservationStatus status, CostType costType, UUID idempotencyKey,
                          UUID settlementKey, String settlementHash, String providerRequestId, Usage usage,
                          LocalDate bucketDay, long lockVersion, Instant createdAt, Instant updatedAt,
                          Instant reconciledAt) {

    /** Live hold plus the amount retained for reconciliation: exactly what occupies a ceiling. */
    public Money heldAmount() { return status.holdsBudget() ? estimatedAmount : Money.ZERO; }

    public boolean terminal() { return !status.holdsBudget() && status != ReservationStatus.UNKNOWN; }

    /** The rc.3 {@code BudgetReservation} projection: the ten declared fields, nothing else. */
    public ObjectNode wire(ObjectMapper json) {
        ObjectNode n = json.createObjectNode();
        n.put("id", id.toString());
        n.put("articleId", article.toString());
        n.put("executionId", execution.toString());
        n.put("amount", reportedAmount().text());
        n.put("currency", Money.CURRENCY);
        n.put("pricingVersion", pricingVersion.toString());
        n.put("status", status.name());
        n.put("costType", status == ReservationStatus.SETTLED && settledAmount != null
                ? CostType.ACTUAL.name() : costType.name());
        n.put("idempotencyKey", idempotencyKey.toString());
        n.put("createdAt", createdAt.toString());
        return n;
    }

    /** A settled reservation reports what it actually cost; everything else still reports the estimate. */
    public Money reportedAmount() {
        return status == ReservationStatus.SETTLED && settledAmount != null ? settledAmount : estimatedAmount;
    }
}

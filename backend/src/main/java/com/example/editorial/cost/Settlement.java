package com.example.editorial.cost;

import com.example.editorial.shared.CanonicalRequest;
import com.example.editorial.shared.PublicFailure;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.util.Set;
import java.util.UUID;

/**
 * rc.3 {@code Settlement}: the only way a held reservation stops holding budget.
 *
 * <p>The six declared fields are the whole wire shape. {@code UNKNOWN} keeps the estimate occupied and books
 * nothing, moving the row into the reconciliation set; {@code SETTLED} requires a six-decimal amount;
 * {@code RELEASED} means no charge occurred and cancels the whole estimate. Reported usage is never read from
 * the wire — it is attached server-side through {@link #withUsage} by the caller that actually observed the
 * call, so a settlement amount can be re-priced under the pinned price version instead of trusted.</p>
 */
public record Settlement(UUID reservationId, String providerRequestId, Money actualAmount,
                         ReservationStatus result, UUID settlementKey, Usage actualUsage, String requestHash) {
    private static final Set<String> WIRE = Set.of("reservationId", "providerRequestId", "actualAmount", "currency",
            "result", "settlementKey");

    public Settlement {
        if (reservationId == null || settlementKey == null || result == null) throw new PublicFailure(422, "INVALID_SETTLEMENT");
        if (result == ReservationStatus.RESERVED) throw new PublicFailure(422, "INVALID_SETTLEMENT");
        if (result == ReservationStatus.UNKNOWN) {
            if (actualAmount != null) throw new PublicFailure(422, "UNKNOWN_WITH_AMOUNT");
        } else if (result == ReservationStatus.SETTLED) {
            if (actualAmount == null && actualUsage == null) throw new PublicFailure(422, "SETTLEMENT_AMOUNT_REQUIRED");
        } else if (result == ReservationStatus.RELEASED) {
            if (actualAmount != null && !actualAmount.isZero()) throw new PublicFailure(422, "RELEASE_WITH_AMOUNT");
        }
        if (providerRequestId != null && (providerRequestId.isBlank() || providerRequestId.length() > 1000))
            throw new PublicFailure(422, "INVALID_PROVIDER_REQUEST_ID");
    }

    /** Wire parse. Only the six declared fields are accepted and the declared currency must be the USD literal. */
    public static Settlement read(ObjectMapper json, JsonNode node) {
        if (node == null || !node.isObject()) throw new PublicFailure(422, "INVALID_SETTLEMENT");
        for (String required : WIRE) if (!node.has(required)) throw new PublicFailure(422, "SETTLEMENT_FIELD_MISSING");
        node.fieldNames().forEachRemaining(name -> {
            if (!WIRE.contains(name)) throw new PublicFailure(422, "UNKNOWN_SETTLEMENT_FIELD");
        });
        if (!Money.CURRENCY.equals(node.path("currency").asText())) throw new PublicFailure(422, "UNSUPPORTED_CURRENCY");
        Money amount = node.get("actualAmount").isNull() ? null : Money.of(node.get("actualAmount").asText());
        String requestId = node.get("providerRequestId").isNull() ? null : node.get("providerRequestId").asText();
        UUID reservation = uuid(node.path("reservationId").asText());
        UUID key = uuid(node.path("settlementKey").asText());
        ReservationStatus result = ReservationStatus.of(node.path("result").asText());
        return new Settlement(reservation, requestId, amount, result, key, null,
                digest(json, reservation, requestId, amount, result, key, null));
    }

    /**
     * Construction for the internal port caller: the same facts, the usage that was actually observed, and the
     * replay hash computed over both. A caller cannot choose the hash, so a replayed settlement is recognized
     * only when every fact matches.
     */
    public static Settlement of(ObjectMapper json, UUID reservationId, String providerRequestId, Money actualAmount,
                                ReservationStatus result, UUID settlementKey, Usage usage) {
        return new Settlement(reservationId, providerRequestId, actualAmount, result, settlementKey, usage,
                digest(json, reservationId, providerRequestId, actualAmount, result, settlementKey, usage));
    }

    /**
     * The server-side extension of a settlement: the same facts plus the usage that was actually observed,
     * attached by the caller that observed it. Replaying it is only possible with the same usage, because the
     * usage is part of the hash the replay compares.
     */
    public Settlement withUsage(ObjectMapper json, Usage usage) {
        if (usage == null) return this;
        return new Settlement(reservationId, providerRequestId, actualAmount, result, settlementKey, usage,
                digest(json, reservationId, providerRequestId, actualAmount, result, settlementKey, usage));
    }

    public ObjectNode wire(ObjectMapper json) {
        ObjectNode n = json.createObjectNode();
        n.put("reservationId", reservationId.toString());
        if (providerRequestId == null) n.putNull("providerRequestId"); else n.put("providerRequestId", providerRequestId);
        if (actualAmount == null) n.putNull("actualAmount"); else n.put("actualAmount", actualAmount.text());
        n.put("currency", Money.CURRENCY);
        n.put("result", result.name());
        n.put("settlementKey", settlementKey.toString());
        return n;
    }

    private static String digest(ObjectMapper json, UUID reservation, String requestId, Money amount,
                                 ReservationStatus result, UUID key, Usage usage) {
        ObjectNode wire = json.createObjectNode();
        wire.put("reservationId", reservation.toString());
        if (requestId == null) wire.putNull("providerRequestId"); else wire.put("providerRequestId", requestId);
        if (amount == null) wire.putNull("actualAmount"); else wire.put("actualAmount", amount.text());
        wire.put("currency", Money.CURRENCY);
        wire.put("result", result.name());
        wire.put("settlementKey", key.toString());
        if (usage != null) wire.set("usage", usage.write(json));
        return CanonicalRequest.digest(CanonicalRequest.canonical(wire));
    }

    private static UUID uuid(String raw) {
        try { return UUID.fromString(raw); } catch (IllegalArgumentException e) { throw new PublicFailure(422, "INVALID_SETTLEMENT"); }
    }
}

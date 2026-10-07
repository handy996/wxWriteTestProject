package com.example.editorial.cost;

import com.example.editorial.shared.ActorContext;
import com.example.editorial.shared.CanonicalRequest;
import com.example.editorial.shared.PublicFailure;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.util.Base64;
import java.util.List;
import java.util.Locale;
import java.util.UUID;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

/**
 * The frozen {@code GET /api/v1/usage} projection: totals for the owner over a date window, a keyset page of
 * reservations, and the budget alert data that the console and the manual-task queue need. Grouping changes
 * the page order and the cursor binding only; the totals always describe the whole filtered window, so paging
 * cannot change what a user sees they have spent.
 */
public final class UsageService {
    /** Cursor groups are the four rc.3 {@code groupBy} values. */
    private static final List<String> GROUPS = List.of("DAY", "ARTICLE", "PROVIDER", "MODEL");
    private static final int MAX_PAGE = 100;

    private final CostLedger ledger;
    private final ObjectMapper json;
    private final BudgetPolicy policy;
    private final byte[] cursorKey;

    public UsageService(CostLedger ledger, ObjectMapper json, BudgetPolicy policy, String cursorSecret) {
        this.ledger = ledger;
        this.json = json;
        this.policy = policy;
        if (cursorSecret == null || cursorSecret.length() < 32) throw new PublicFailure(503, "CURSOR_KEY_MISSING");
        this.cursorKey = cursorSecret.getBytes(StandardCharsets.UTF_8);
    }

    public ObjectNode usage(ActorContext actor, String rawFrom, String rawTo, String rawGroup, String cursor, int limit) {
        LocalDate to = rawTo == null ? LocalDate.now(java.time.ZoneOffset.UTC) : date(rawTo, "dateTo");
        LocalDate from = rawFrom == null ? to.minusDays(29) : date(rawFrom, "dateFrom");
        if (to.isBefore(from)) throw new PublicFailure(422, "INVALID_DATE_RANGE");
        String group = rawGroup == null ? "DAY" : rawGroup.toUpperCase(Locale.ROOT);
        if (!GROUPS.contains(group)) throw new PublicFailure(422, "INVALID_GROUP_BY");
        if (limit < 1 || limit > MAX_PAGE) throw new PublicFailure(422, "INVALID_PAGE_SIZE");

        Position after = cursor == null ? Position.start() : Position.read(cursor, actor, from, to, group, cursorKey);
        List<Reservation> page = ledger.page(actor.ownerId(), from, to, groupSql(group), after.group(), after.id(), limit);
        CostPorts.Occupancy window = ledger.occupancy("l.owner_id=? AND l.bucket_day>=? AND l.bucket_day<=?",
                actor.ownerId(), from, to);
        Usage tokens = ledger.totals(actor.ownerId(), from, to);

        ObjectNode summary = json.createObjectNode();
        summary.put("currency", Money.CURRENCY);
        summary.put("actual", window.spent().text());
        summary.put("estimated", window.reserved().text());
        summary.put("unknownReserved", window.unknown().text());
        summary.put("inputTokens", tokens.inputTokens());
        summary.put("cachedInputTokens", tokens.cachedInputTokens());
        summary.put("outputTokens", tokens.outputTokens());
        summary.put("searchCalls", tokens.searchCalls());
        summary.put("imageUnits", tokens.imageUnits());
        ArrayNode entries = summary.putArray("entries");
        for (Reservation reservation : page) entries.add(reservation.wire(json));
        summary.set("nextCursor", page.size() == limit
                ? com.fasterxml.jackson.databind.node.TextNode.valueOf(new Position(
                        lastGroup(page.get(page.size() - 1), group), page.get(page.size() - 1).id())
                        .sign(actor, from, to, group, cursorKey))
                : com.fasterxml.jackson.databind.node.NullNode.getInstance());
        return summary;
    }

    /**
     * Budget alert data for the console and the workflow queue: every ceiling that has reached the alert
     * percent, plus what is still occupied by unresolved outcomes. Delivered through
     * {@link CostPorts.AlertSink} when the notification domain is wired, and always readable here.
     */
    public List<BudgetAlert> alerts(ActorContext actor, LocalDate from, LocalDate to) {
        CostPorts.Occupancy day = ledger.occupancy("l.owner_id=? AND l.bucket_day>=? AND l.bucket_day<=?",
                actor.ownerId(), from, to);
        List<BudgetAlert> alerts = new java.util.ArrayList<>();
        if (policy.reachedAlert(day.occupied(), policy.dailyLimit()))
            alerts.add(new BudgetAlert(BudgetAlert.Code.BUDGET_WARNING, "DAY", actor.ownerId() + "|" + from,
                    day.spent(), day.reserved(), day.unknown(), policy.dailyLimit(),
                    BudgetAlert.percentOf(day.occupied(), policy.dailyLimit()), null, null, null, null));
        for (Reservation unresolved : ledger.unknown(actor.ownerId(), from, to))
            alerts.add(new BudgetAlert(BudgetAlert.Code.RECONCILIATION_STALE, "ARTICLE", unresolved.article().toString(),
                    Money.ZERO, Money.ZERO, unresolved.estimatedAmount(), Money.ZERO, 100, unresolved.provider(),
                    unresolved.model(), null, null));
        return List.copyOf(alerts);
    }

    private static String groupSql(String group) {
        return switch (group) {
            case "DAY" -> "l.bucket_day::text";
            case "ARTICLE" -> "l.article_id::text";
            case "PROVIDER" -> "l.provider";
            case "MODEL" -> "l.model";
            default -> throw new PublicFailure(422, "INVALID_GROUP_BY");
        };
    }

    private static String lastGroup(Reservation r, String group) {
        return switch (group) {
            case "DAY" -> r.bucketDay().toString();
            case "ARTICLE" -> r.article().toString();
            case "PROVIDER" -> r.provider();
            case "MODEL" -> r.model();
            default -> throw new PublicFailure(422, "INVALID_GROUP_BY");
        };
    }

    private static LocalDate date(String raw, String field) {
        if (raw == null) throw new PublicFailure(422, "DATE_REQUIRED");
        try { return LocalDate.parse(raw); }
        catch (DateTimeParseException e) { throw new PublicFailure(422, "INVALID_" + field.toUpperCase(Locale.ROOT)); }
    }

    /** Opaque signed cursor: bound to the owner, the filters and the last row, so it cannot be steered. */
    private record Position(String group, UUID id) {
        static Position start() { return new Position(null, new UUID(0, 0)); }

        String sign(ActorContext actor, LocalDate from, LocalDate to, String filter, byte[] key) {
            String payload = actor.ownerId() + "|" + from + "|" + to + "|" + filter + "|" + group + "|" + id;
            return Base64.getUrlEncoder().withoutPadding().encodeToString(payload.getBytes(StandardCharsets.UTF_8))
                    + "." + Base64.getUrlEncoder().withoutPadding().encodeToString(hmac(payload, key));
        }

        static Position read(String cursor, ActorContext actor, LocalDate from, LocalDate to, String filter, byte[] key) {
            int dot = cursor.lastIndexOf('.');
            if (dot < 1 || dot == cursor.length() - 1) throw new PublicFailure(422, "INVALID_CURSOR");
            String payload;
            try {
                payload = new String(Base64.getUrlDecoder().decode(cursor.substring(0, dot)), StandardCharsets.UTF_8);
            } catch (IllegalArgumentException e) { throw new PublicFailure(422, "INVALID_CURSOR"); }
            if (!java.security.MessageDigest.isEqual(hmac(payload, key), decodeSignature(cursor.substring(dot + 1))))
                throw new PublicFailure(422, "INVALID_CURSOR");
            String[] parts = payload.split("\\|", -1);
            if (parts.length != 6 || !parts[0].equals(actor.ownerId().toString()) || !parts[1].equals(from.toString())
                    || !parts[2].equals(to.toString()) || !parts[3].equals(filter))
                throw new PublicFailure(409, "CURSOR_STALE");
            try {
                return new Position(parts[4].equals("null") ? null : parts[4], UUID.fromString(parts[5]));
            } catch (IllegalArgumentException e) { throw new PublicFailure(422, "INVALID_CURSOR"); }
        }

        private static byte[] decodeSignature(String raw) {
            try { return Base64.getUrlDecoder().decode(raw); }
            catch (IllegalArgumentException e) { throw new PublicFailure(422, "INVALID_CURSOR"); }
        }

        private static byte[] hmac(String payload, byte[] key) {
            try {
                Mac mac = Mac.getInstance("HmacSHA256");
                mac.init(new SecretKeySpec(key, "HmacSHA256"));
                return mac.doFinal(payload.getBytes(StandardCharsets.UTF_8));
            } catch (Exception e) { throw new PublicFailure(503, "CURSOR_KEY_UNUSABLE"); }
        }
    }

    /** Digest of a filter set, kept for the audit trail of a usage read. */
    public static String filterHash(LocalDate from, LocalDate to, String group) {
        return CanonicalRequest.digest((from + "|" + to + "|" + group).getBytes(java.nio.charset.StandardCharsets.UTF_8));
    }
}

package com.example.editorial.cost;

import com.example.editorial.shared.ActorContext;
import com.example.editorial.shared.CanonicalRequest;
import com.example.editorial.shared.PublicFailure;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.Instant;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.jdbc.core.JdbcTemplate;

/**
 * Every statement that touches {@code cost_ledger}. This class decides no policy: it takes the transaction
 * scoped advisory lock for an accounting scope, reads that scope's occupancy, and writes either an estimate
 * hold or a settlement fact. Atomic last-balance admission is the scope lock plus the guarded write; the draft
 * migration repeats the same ceiling as a database constraint, so a writer that skipped the lock still cannot
 * oversubscribe a budget.
 */
public final class CostLedger {
    /** Rows that occupy a ceiling or report spend: live holds, plus settled facts once they exist. */
    private static final String COUNTED = "((l.kind='ESTIMATED' AND l.status IN ('RESERVED','UNKNOWN'))"
            + " OR (l.kind='ACTUAL' AND l.status='SETTLED'))";
    private static final String HEAD = "SELECT id, article_id, owner_id, execution_id, execution_kind, status,"
            + " amount, currency, pricing_version, pricing_hash, idempotency_key, settlement_key, settlement_hash,"
            + " provider, model, capability, bucket_day, search_calls, image_units, output_tokens, input_tokens,"
            + " cached_input_tokens, reasoning_tokens, usage::text AS usage_json, provider_request_id,"
            + " settled_amount, released_amount, over_run, reconciled_at, lock_version, created_at, updated_at"
            + " FROM editorial.cost_ledger AS l";

    private final JdbcTemplate db;
    private final ObjectMapper json;

    public CostLedger(JdbcTemplate db, ObjectMapper json) {
        this.db = db;
        this.json = json;
    }

    /** Serialize on one accounting scope for the rest of the current transaction. */
    public void lockScope(String scopeKey) {
        db.query("SELECT pg_advisory_xact_lock(?)", rs -> { }, CanonicalRequest.lockKey(scopeKey));
    }

    public Optional<CostPorts.ArticleBudget> article(UUID owner, UUID article) {
        return db.query("SELECT owner_id, budget_limit, status, deletion_pending, archived_at IS NOT NULL"
                        + " FROM editorial.article_job WHERE id=? AND owner_id=?",
                (rs, n) -> new CostPorts.ArticleBudget(article, rs.getObject(1, UUID.class),
                        Money.ofExact(rs.getBigDecimal(2)), rs.getString(3), rs.getBoolean(4), rs.getBoolean(5)),
                article, owner).stream().findFirst();
    }

    public Optional<PriceVersion> publishedPrice(String provider, String model) {
        return db.query("SELECT id, rules::text FROM editorial.cost_pricing_version"
                        + " WHERE provider=? AND model=? AND status='PUBLISHED'",
                (rs, n) -> PricingRules.parse(rs.getObject(1, UUID.class), provider, model, rs.getString(2)),
                provider, model).stream().findFirst();
    }

    /** The exact version the reservation was estimated under — a settlement may not switch price tables. */
    public Optional<PriceVersion> priceVersion(UUID id) {
        return db.query("SELECT provider, model, rules::text FROM editorial.cost_pricing_version WHERE id=?",
                (rs, n) -> PricingRules.parse(id, rs.getString(1), rs.getString(2), rs.getString(3)), id)
                .stream().findFirst();
    }

    /** Occupancy of one scope in a single read: spent, held, retained for reconciliation, counters, live holds. */
    public CostPorts.Occupancy occupancy(String where, Object... args) {
        BigDecimal[] money = db.query("SELECT"
                        + " coalesce(sum(l.amount) FILTER (WHERE l.kind='ACTUAL' AND l.status='SETTLED'),0),"
                        + " coalesce(sum(l.amount) FILTER (WHERE l.kind='ESTIMATED' AND l.status='RESERVED'),0),"
                        + " coalesce(sum(l.amount) FILTER (WHERE l.kind='ESTIMATED' AND l.status='UNKNOWN'),0),"
                        + " coalesce(count(*) FILTER (WHERE l.kind='ESTIMATED' AND l.status='RESERVED'),0)"
                        + " FROM editorial.cost_ledger AS l WHERE " + where,
                (rs, n) -> new BigDecimal[]{rs.getBigDecimal(1), rs.getBigDecimal(2), rs.getBigDecimal(3),
                        BigDecimal.valueOf(rs.getLong(4))}, args)
                .stream().findFirst().orElseThrow(() -> new PublicFailure(503, "OCCUPANCY_UNREADABLE"));
        Map<BudgetPolicy.Counter, Long> counters = new EnumMap<>(BudgetPolicy.Counter.class);
        db.query("SELECT c.key, coalesce(sum((c.value)::numeric),0) FROM editorial.cost_ledger AS l,"
                        + " jsonb_each_text(l.counters) AS c(key,value) WHERE (" + COUNTED + ") AND " + where
                        + " GROUP BY c.key", (org.springframework.jdbc.core.RowCallbackHandler) rs ->
                        counters.put(BudgetPolicy.Counter.of(rs.getString(1)), rs.getBigDecimal(2).longValueExact()),
                args);
        return new CostPorts.Occupancy(Money.ofExact(money[0]), Money.ofExact(money[1]), Money.ofExact(money[2]),
                Map.copyOf(counters), money[3].longValueExact());
    }

    /** Token and call totals over a window, for the frozen usage projection. */
    public Usage totals(UUID owner, LocalDate from, LocalDate to) {
        return db.query("SELECT"
                        + " coalesce(sum(l.input_tokens) FILTER (WHERE " + COUNTED + "),0),"
                        + " coalesce(sum(l.cached_input_tokens) FILTER (WHERE " + COUNTED + "),0),"
                        + " coalesce(sum(l.output_tokens) FILTER (WHERE " + COUNTED + "),0),"
                        + " coalesce(sum(l.search_calls) FILTER (WHERE " + COUNTED + "),0),"
                        + " coalesce(sum(l.image_units) FILTER (WHERE " + COUNTED + "),0),"
                        + " coalesce(sum(l.reasoning_tokens) FILTER (WHERE " + COUNTED + "),0)"
                        + " FROM editorial.cost_ledger AS l WHERE l.owner_id=? AND l.bucket_day>=? AND l.bucket_day<=?",
                (rs, n) -> new Usage(exact(rs, 1), exact(rs, 2), exact(rs, 3),
                        exact(rs, 6) == 0 ? null : exact(rs, 6), exact(rs, 5), exact(rs, 4)), owner, from, to)
                .stream().findFirst().orElseGet(Usage::zero);
    }

    private static int exact(ResultSet rs, int column) throws SQLException {
        long value = rs.getLong(column);
        if (value > Integer.MAX_VALUE) throw new PublicFailure(409, "USAGE_OVERFLOW");
        return (int) value;
    }

    public Optional<Reservation> head(UUID owner, UUID article, UUID reservationId) {
        return db.query(HEAD + " WHERE l.kind='ESTIMATED' AND l.owner_id=? AND l.article_id=? AND l.id=?",
                (rs, n) -> map(rs), owner, article, reservationId).stream().findFirst();
    }

    /** Row-locked read used by settlement: the guard predicate below relies on this being the live version. */
    public Optional<Reservation> headByOwner(UUID owner, UUID reservationId) {
        return db.query(HEAD + " WHERE l.kind='ESTIMATED' AND l.owner_id=? AND l.id=? FOR UPDATE",
                (rs, n) -> map(rs), owner, reservationId).stream().findFirst();
    }

    public Optional<Reservation> byReservationKey(UUID article, UUID idempotencyKey) {
        return db.query(HEAD + " WHERE l.kind='ESTIMATED' AND l.article_id=? AND l.idempotency_key=?",
                (rs, n) -> map(rs), article, idempotencyKey).stream().findFirst();
    }

    /**
     * Replay lookup. A settlement key is unique across the ledger and lives on the appended fact, so the head is
     * found through the fact it produced: the same key can only ever identify one reservation.
     */
    public Optional<Reservation> bySettlementKey(UUID owner, UUID settlementKey) {
        return db.query(HEAD + " WHERE l.kind='ESTIMATED' AND l.owner_id=? AND l.id=(SELECT f.reservation_id"
                        + " FROM editorial.cost_ledger f WHERE f.kind='ACTUAL' AND f.settlement_key=?)",
                (rs, n) -> map(rs), owner, settlementKey).stream().findFirst();
    }

    /** Insert the ESTIMATED hold. Throws {@link DuplicateReservation} when the reservation key already exists. */
    public void insertEstimate(ActorContext actor, Reservation r, UUID claim, UUID slot, Usage usage,
                               Map<BudgetPolicy.Counter, Long> counters) {
        List<String> columns = List.of("id", "article_id", "owner_id", "execution_id", "execution_kind",
                "reservation_id", "kind", "status", "amount", "currency", "pricing_version", "pricing_hash",
                "idempotency_key", "provider", "model", "capability", "bucket_day", "claim_id", "slot_id",
                "search_calls", "image_units", "output_tokens", "input_tokens", "cached_input_tokens",
                "reasoning_tokens", "usage@jsonb", "counters@jsonb", "created_by", "updated_by", "trace_id");
        List<Object> args = java.util.Arrays.asList(r.id(), r.article(), r.owner(), r.execution(), r.executionKind(), r.id(),
                "ESTIMATED", "RESERVED", amount(r.estimatedAmount()), Money.CURRENCY, r.pricingVersion(),
                r.pricingHash(), r.idempotencyKey(), r.provider(), r.model(), r.capability().name(), r.bucketDay(),
                claim, slot, usage.searchCalls(), usage.imageUnits(), usage.outputTokens(), usage.inputTokens(),
                usage.cachedInputTokens(), nullable(usage.reasoningTokensIfProvided()), canonical(usage.write(json)),
                canonical(counterNode(counters)), actor.actorId(), actor.actorId(), actor.traceId());
        try {
            db.update(insert(columns), args.toArray());
        } catch (DuplicateKeyException raced) {
            throw new DuplicateReservation();
        }
    }

    /**
     * Move the hold and append the settlement fact. The UPDATE is guarded by the status and lock version that
     * were read under the scope lock, so a concurrent settlement of the same reservation moves zero rows and
     * reports a conflict instead of overwriting the winner. The ACTUAL row is never updated afterwards.
     */
    public void applySettlement(ActorContext actor, Reservation head, Settlement command, Money settled,
                                Money released, Money overRun, Usage usage, Map<BudgetPolicy.Counter, Long> counters) {
        Timestamp resolved = command.result() == ReservationStatus.UNKNOWN ? null : Timestamp.from(Instant.now());
        int moved = db.update("UPDATE editorial.cost_ledger SET status=?, settled_amount=?, released_amount=?,"
                        + " over_run=?, settlement_hash=?, provider_request_id=?, reconciled_at=?,"
                        + " lock_version=lock_version+1, updated_by=?, updated_at=clock_timestamp(), trace_id=?"
                        + " WHERE kind='ESTIMATED' AND id=? AND owner_id=? AND status=? AND lock_version=?",
                command.result().name(), amount(settled), amount(released), amount(overRun),
                command.requestHash(), command.providerRequestId(), resolved, actor.actorId(), actor.traceId(),
                head.id(), head.owner(), head.status().name(), head.lockVersion());
        if (moved != 1) throw new PublicFailure(409, "SETTLEMENT_CONFLICT");
        List<String> columns = List.of("id", "article_id", "owner_id", "execution_id", "execution_kind",
                "reservation_id", "kind", "status", "amount", "currency", "pricing_version", "pricing_hash",
                "idempotency_key", "settlement_key", "settlement_hash", "provider", "model", "capability",
                "bucket_day", "search_calls", "image_units", "output_tokens", "input_tokens", "cached_input_tokens",
                "reasoning_tokens", "usage@jsonb", "counters@jsonb", "provider_request_id", "settled_amount",
                "reconciled_at", "created_by", "updated_by", "trace_id");
        List<Object> args = java.util.Arrays.asList(UUID.randomUUID(), head.article(), head.owner(), head.execution(),
                head.executionKind(), head.id(), "ACTUAL", command.result().name(),
                amount(settled == null ? Money.ZERO : settled), Money.CURRENCY, head.pricingVersion(),
                head.pricingHash(), command.settlementKey(), command.settlementKey(), command.requestHash(),
                head.provider(), head.model(), head.capability().name(), head.bucketDay(), usage.searchCalls(),
                usage.imageUnits(), usage.outputTokens(), usage.inputTokens(), usage.cachedInputTokens(),
                nullable(usage.reasoningTokensIfProvided()), canonical(usage.write(json)),
                canonical(counterNode(counters)), command.providerRequestId(), amount(settled), resolved,
                actor.actorId(), actor.actorId(), actor.traceId());
        db.update(insert(columns), args.toArray());
    }

    /** Unresolved outcomes waiting for reconciliation, oldest first. */
    public List<Reservation> unknown(UUID owner, LocalDate from, LocalDate to) {
        return db.query(HEAD + " WHERE l.kind='ESTIMATED' AND l.owner_id=? AND l.status='UNKNOWN'"
                + " AND l.bucket_day>=? AND l.bucket_day<=? ORDER BY l.bucket_day, l.created_at, l.id",
                (rs, n) -> map(rs), owner, from, to);
    }

    /** Holds that never received an outcome — the stale half of the reconciliation queue. */
    public List<Reservation> staleHolds(UUID owner, LocalDate from, LocalDate to, Instant staleBefore) {
        return db.query(HEAD + " WHERE l.kind='ESTIMATED' AND l.owner_id=? AND l.status='RESERVED'"
                        + " AND l.bucket_day>=? AND l.bucket_day<=? AND l.updated_at<?"
                        + " ORDER BY l.bucket_day, l.created_at, l.id",
                (rs, n) -> map(rs), owner, from, to, Timestamp.from(staleBefore));
    }

    /** Keyset page of holds for the usage projection, ordered by the group expression then id. */
    public List<Reservation> page(UUID owner, LocalDate from, LocalDate to, String groupSql, String afterGroup,
                                  UUID afterId, int limit) {
        List<Object> args = new ArrayList<>(List.of(owner, from, to));
        String tail = "";
        if (afterGroup != null) {
            args.addAll(List.of(afterGroup, afterGroup, afterId));
            tail = " AND ((" + groupSql + ") > ? OR ((" + groupSql + ") = ? AND l.id > ?))";
        }
        args.add(limit);
        return db.query(HEAD + " WHERE l.kind='ESTIMATED' AND l.owner_id=? AND l.bucket_day>=? AND l.bucket_day<=?"
                        + tail + " ORDER BY (" + groupSql + "), l.id LIMIT ?", (rs, n) -> map(rs), args.toArray());
    }

    /** A settlement books an amount, releases the whole estimate, or books nothing and keeps the hold. */
    public static Money settledAmount(Settlement command, Money actual) {
        return switch (command.result()) {
            case SETTLED -> actual;
            case RELEASED -> null;
            case UNKNOWN -> null;
            case RESERVED -> throw new PublicFailure(422, "INVALID_SETTLEMENT");
        };
    }

    /** The difference returned to every ceiling the estimate occupied. An UNKNOWN returns nothing. */
    public static Money releasedAmount(Settlement command, Money estimate, Money settled) {
        if (command.result() == ReservationStatus.RELEASED) return estimate;
        if (command.result() == ReservationStatus.UNKNOWN || settled == null) return Money.ZERO;
        return estimate.compareTo(settled) > 0 ? estimate.subtract(settled) : Money.ZERO;
    }

    /** A real bill above the estimate is booked as an overrun and reported, never rejected or hidden. */
    public static Money overRun(Settlement command, Money estimate, Money settled) {
        if (command.result() != ReservationStatus.SETTLED || settled == null) return Money.ZERO;
        return settled.compareTo(estimate) > 0 ? settled.subtract(estimate) : Money.ZERO;
    }

    private static Map<String, Long> counterObject(Map<BudgetPolicy.Counter, Long> counters) {
        Map<String, Long> named = new LinkedHashMap<>();
        counters.forEach((c, v) -> { if (v != null && v > 0) named.put(c.name(), v); });
        return Map.copyOf(named);
    }

    private Reservation map(ResultSet rs) throws SQLException {        BigDecimal actual = rs.getBigDecimal("settled_amount");
        ReservationStatus status = ReservationStatus.of(rs.getString("status"));
        return new Reservation(rs.getObject("id", UUID.class), rs.getObject("article_id", UUID.class),
                rs.getObject("owner_id", UUID.class), rs.getObject("execution_id", UUID.class),
                rs.getString("execution_kind"), rs.getString("provider"), rs.getString("model"),
                Capability.of(rs.getString("capability")), Money.ofExact(rs.getBigDecimal("amount")),
                actual == null ? null : Money.ofExact(actual),
                Money.ofExact(rs.getBigDecimal("released_amount")), Money.ofExact(rs.getBigDecimal("over_run")),
                rs.getObject("pricing_version", UUID.class), rs.getString("pricing_hash"), status,
                status == ReservationStatus.SETTLED ? CostType.ACTUAL : CostType.ESTIMATED,
                rs.getObject("idempotency_key", UUID.class), rs.getObject("settlement_key", UUID.class),
                rs.getString("settlement_hash"), rs.getString("provider_request_id"),
                Usage.read(PricingRules.read(rs.getString("usage_json"))),
                rs.getObject("bucket_day", LocalDate.class), rs.getLong("lock_version"), instant(rs, "created_at"),
                instant(rs, "updated_at"), rs.getTimestamp("reconciled_at") == null ? null : instant(rs, "reconciled_at"));
    }

    private static Instant instant(ResultSet rs, String column) throws SQLException {
        Timestamp value = rs.getTimestamp(column);
        return value == null ? null : value.toInstant();
    }

    private String canonical(JsonNode node) {
        return new String(CanonicalRequest.canonical(node), java.nio.charset.StandardCharsets.UTF_8);
    }

    /**
     * Builds one INSERT statement from the column list, so the columns and the placeholders cannot drift apart
     * when a field is added. A column written as {@code usage@jsonb} binds a text parameter cast to JSON.
     */
    private static String insert(List<String> columns) {
        StringBuilder sql = new StringBuilder("INSERT INTO editorial.cost_ledger (");
        StringBuilder marks = new StringBuilder(") VALUES (");
        for (int i = 0; i < columns.size(); i++) {
            String column = columns.get(i);
            int cast = column.indexOf('@');
            if (i > 0) { sql.append(", "); marks.append(", "); }
            sql.append(cast < 0 ? column : column.substring(0, cast));
            marks.append(cast < 0 ? "?" : "?::" + column.substring(cast + 1));
        }
        return sql.append(marks).append(")").toString();
    }

    /** Counters are stored as a JSON object of name to whole-number usage, so caps aggregate in one statement. */
    private JsonNode counterNode(Map<BudgetPolicy.Counter, Long> counters) {
        var node = json.createObjectNode();
        counters.forEach((c, v) -> { if (v != null && v > 0) node.put(c.name(), v); });
        return node;
    }

    /** A reported reasoning count is optional; the column is nullable so "not provided" is not zero. */
    private static Object nullable(Integer value) { return value; }

    private static BigDecimal amount(Money value) { return value == null ? null : value.decimal(); }

    /** Raised when the reservation key already exists; the caller replays the stored answer instead. */
    public static final class DuplicateReservation extends RuntimeException {
        public DuplicateReservation() { super(null, null, false, false); }
    }
}

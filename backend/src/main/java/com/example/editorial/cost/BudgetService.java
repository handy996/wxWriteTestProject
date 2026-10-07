package com.example.editorial.cost;

import com.example.editorial.shared.ActorContext;
import com.example.editorial.shared.PublicFailure;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.EnumMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.UUID;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * Budget pre-occupancy and settlement — the {@code Budget.reserve} / {@code Budget.settle} ports.
 *
 * <p>Admission is one database transaction. Every ceiling a call touches is ordered by its scope key and
 * locked in that order with transaction-scoped advisory locks; the occupancy of each ceiling is then read and
 * the new estimate is checked against it. Because a lock is held until commit, two callers racing for the last
 * of a balance serialize: the first writes its hold and the second reads that hold and is refused with
 * {@code BUDGET_EXCEEDED}. A single-winner race is therefore a property of the lock and the read, not of a
 * Java-side check, and the installed migration repeats the article ceiling as a database rule: the admission
 * trigger locks the {@code article_job} row before it aggregates occupancy, so a writer that skipped these
 * advisory locks cannot oversubscribe an article even concurrently — which {@code T08PostgresTest} measures by
 * racing two direct INSERTs, not by reasoning about it. The daily ceiling, the count caps and the provider
 * quotas are enforced on this service path only: their limits live in configuration rather than in a row the
 * database could lock, so a bypassing writer meets the article ceiling and nothing else.</p>
 *
 * <p>One shape the reader has to see plainly (round-4 finding F-R4-01): every window this service locks and
 * measures is partitioned by {@code owner_id}, the provider-wide quota window included. A
 * {@code provider-quota.<provider>.max-concurrent: 2} is therefore enforced per
 * {@code (owner, provider, day)}, not globally per provider — two Owners using one provider credential hold four
 * calls between them. SRS 32.2 asks for the provider's own limit and forbids routing around it with extra keys;
 * whether that limit is one global window or one window per Owner is <strong>the Owner's open decision</strong>,
 * registered against this card as {@code openedBy: T08-REVIEW-4TH}. This implementation states the second
 * reading, {@code T08PostgresTest#providerWideQuotaWindowIsPartitionedByOwnerToday} pins it as data, and neither
 * the window nor the lock key is to be reinterpreted here.</p>
 *
 * <p>Settlement is idempotent by {@code settlementKey}: the same key replays the stored answer, while the row
 * move itself is guarded by the status and lock version read under the lock, so a concurrent second settlement
 * reports {@code SETTLEMENT_CONFLICT} instead of overwriting the outcome that was really billed. An
 * {@code UNKNOWN} outcome keeps the estimate held and books nothing until reconciliation, and settling below
 * the estimate releases exactly the difference back to every ceiling it occupied.</p>
 */
public final class BudgetService {
    private final CostLedger ledger;
    private final TransactionTemplate tx;
    private final BudgetPolicy policy;
    private final CostPorts.Executions executions;
    private final CostPorts.Audit audit;
    private final CostPorts.AlertSink alerts;

    public BudgetService(CostLedger ledger, TransactionTemplate tx, BudgetPolicy policy, CostPorts.Executions executions,
                         CostPorts.Audit audit, CostPorts.AlertSink alerts) {
        this.ledger = ledger;
        this.tx = tx;
        this.policy = policy;
        this.executions = executions;
        this.audit = audit;
        this.alerts = alerts;
    }

    /**
     * One reservation request: which route will be called, with what planned usage, under which execution, and
     * whether the pipeline started it automatically. {@code estimate} is always computed server-side from the
     * published price version — a caller cannot reserve an amount of its own choosing.
     */
    public record Request(UUID article, UUID execution, String provider, String model, Capability capability,
                          Usage usage, Money otherProviderFees, boolean automatic, boolean autoEditLoop,
                          UUID idempotencyKey) {
        public Request {
            if (article == null || execution == null || idempotencyKey == null || capability == null || usage == null)
                throw new PublicFailure(422, "INVALID_RESERVATION");
            if (provider == null || provider.isBlank() || provider.length() > 64 || model == null || model.isBlank()
                    || model.length() > 128) throw new PublicFailure(422, "INVALID_ROUTE_IDENTITY");
            otherProviderFees = otherProviderFees == null ? Money.ZERO : otherProviderFees;
        }
    }

    /** The answer to {@code Budget.reserve}: a held reservation, or {@code BUDGET_EXCEEDED}. */
    public Reservation reserve(ActorContext actor, Request request) {
        return Objects.requireNonNull(tx.execute(status -> reserveInTransaction(actor, request)));
    }

    private Reservation reserveInTransaction(ActorContext actor, Request request) {
        CostPorts.ArticleBudget article = ledger.article(actor.ownerId(), request.article())
                .orElseThrow(() -> new PublicFailure(404, "NOT_FOUND"));
        CostPorts.Executions.Scope scope = executions.resolve(actor, article.article(), request.execution());
        if (!scope.article().equals(article.article()) || !scope.owner().equals(actor.ownerId()))
            throw new PublicFailure(404, "NOT_FOUND");
        LocalDate day = LocalDate.now(ZoneOffset.UTC);
        PriceVersion price = ledger.publishedPrice(request.provider(), request.model())
                .orElseThrow(() -> new PublicFailure(503, "PRICING_NOT_PUBLISHED"));
        // A published version that does not price this capability is an unknown price. Zero is allowed;
        // absence is not, and an automatic image generation is refused by name.
        if (!price.known(request.capability())) throw price.unknown(request.capability());

        List<Ceiling> ceilings = ceilings(article, request.provider(), request.model(), scope, day);
        // The order is the invariant, not the sort call: every transaction that admits a call takes the same
        // ascending sequence of advisory locks, so no two writers can hold each other's keys in opposite hands.
        // inLockOrder is the one place that sequence is decided — round-4 finding F-R4-09 measured that the
        // claim had no watchman (deleting the sort left every static gate and every delivered case green), so
        // the sequence is now pinned by CostPricingTest and the call site by verify.py.
        ceilings = inLockOrder(ceilings);
        for (Ceiling ceiling : ceilings) ledger.lockScope(ceiling.lockKey());

        // Replay before anything else: the same reservation key returns the hold already made, never a second one.
        // Recorded asymmetry (round-1 finding F-10): settlement compares a canonical request digest and answers
        // SETTLEMENT_CONFLICT when the same key arrives with different content, while reservation replay
        // deliberately ignores changed content — rc.3's BudgetReservation carries no request-digest field to
        // compare against, so the first hold wins. A caller that needs conflict detection must derive
        // idempotencyKey from its own request digest; closing the gap needs a contract field, not a guess here.
        Optional<Reservation> replay = ledger.byReservationKey(article.article(), request.idempotencyKey());
        if (replay.isPresent()) return replay.get();
        if (!article.billable()) throw new PublicFailure(409, article.refusal());

        Money estimate = price.estimate(request.capability(), request.usage(), request.otherProviderFees());
        Map<BudgetPolicy.Counter, Long> counters = counters(request, scope);

        for (Ceiling ceiling : ceilings) {
            CostPorts.Occupancy used = ledger.occupancy(ceiling.where(), ceiling.args().toArray());
            if (ceiling.limit() != null && used.occupied().add(estimate).compareTo(ceiling.limit()) > 0) refuse(actor,
                    ceiling, used, estimate, request, ceiling.exceededCode(), null, null);
            for (Map.Entry<BudgetPolicy.Counter, Long> cap : ceiling.caps().entrySet()) {
                long already = used.counter(cap.getKey());
                long incoming = counters.getOrDefault(cap.getKey(), 0L);
                if (incoming > 0 && already + incoming > cap.getValue())
                    refuse(actor, ceiling, used, estimate, request, BudgetAlert.Code.QUOTA_EXCEEDED,
                            already + incoming, cap.getValue());
            }
        }
        checkProviderQuota(actor, request, scope, day, ceilings);

        Reservation reservation = new Reservation(UUID.randomUUID(), article.article(), article.owner(),
                request.execution(), scope.kind().name(), request.provider(), request.model(), request.capability(),
                estimate, null, Money.ZERO, Money.ZERO, price.id(), price.hash(), ReservationStatus.RESERVED,
                CostType.ESTIMATED, request.idempotencyKey(), null, null, null, request.usage(), day, 1,
                Instant.now(), Instant.now(), null);
        try {
            ledger.insertEstimate(actor, reservation, scope.claim(), scope.slot(), request.usage(), counters);
        } catch (CostLedger.DuplicateReservation raced) {
            return ledger.byReservationKey(article.article(), request.idempotencyKey())
                    .orElseThrow(() -> new PublicFailure(409, "IDEMPOTENCY_CONFLICT"));
        }
        // audit_log carries identifiers and 64-hex hashes only (detail is CHECKed to '{}'), so the amount stays in
        // cost_ledger — the fact source — and is not smuggled through a hash column. See bootstrap/CostIntegration.
        audit.append(actor, "COST_RESERVED", article.article(), reservation.id(), null, null);
        warnIfCrossedAlert(actor, ceilings);
        return reservation;
    }

    /**
     * Provider-side quota (SRS 32.2: the provider's own limits are configured separately from the article
     * budget). Concurrency counts live holds; the daily call count counts everything already admitted today.
     * Both configured levels are enforced together (round-3 ruling F-03): the model entry caps that model's
     * window, the provider-wide entry caps the provider summed across its models, and a call has to pass every
     * window whose entry exists — a model entry looser than its provider entry lifts nothing. Every window here
     * is one {@link #ceilings} already locked, so the reads serialize with racing admissions. A provider/model
     * with no entry at either level is not read as "no limit": {@code editorial.cost.provider-quota.unconfigured}
     * states whether the deployment means UNLIMITED or REFUSE, and REFUSE stops the call before it is booked.
     *
     * <p>Where this sits in the order matters and is stated rather than inferred (round-4 finding F-R4-11a): the
     * article and day ceilings, with their count caps, are measured FIRST, and only then does this quota pass
     * run. A call that breaches both the article's own count ceiling and a provider window is therefore refused
     * as {@code QUOTA_EXCEEDED} (409, the article-side ceiling) and never as {@code PROVIDER_QUOTA_EXCEEDED}
     * (429); {@code T08PostgresTest#theArticleCeilingSpeaksBeforeTheProviderQuotaWindow} pins that rejection
     * order, and {@code verify.py} pins that the pass stays after the loop.</p>
     */
    private void checkProviderQuota(ActorContext actor, Request request, CostPorts.Executions.Scope scope, LocalDate day,
                                    List<Ceiling> ceilings) {
        List<Ceiling> windows = ceilings.stream().filter(ceiling -> ceiling.quota() != null).toList();
        if (windows.isEmpty()) {
            if (policy.unconfigured() == BudgetPolicy.UnconfiguredQuota.REFUSE) {
                throw new PublicFailure(503, "PROVIDER_QUOTA_NOT_CONFIGURED");
            }
            return;
        }
        for (Ceiling window : windows) {
            BudgetPolicy.ProviderQuota quota = window.quota();
            CostPorts.Occupancy used = ledger.occupancy(window.where(), window.args().toArray());
            if (used.holds() >= quota.maxConcurrent()) throw new PublicFailure(429, "PROVIDER_QUOTA_EXCEEDED");
            if (used.counter(BudgetPolicy.Counter.CALLS) + 1 > quota.callsPerDay())
                throw new PublicFailure(429, "PROVIDER_QUOTA_EXCEEDED");
        }
    }

    private void refuse(ActorContext actor, Ceiling ceiling, CostPorts.Occupancy used, Money estimate, Request request,
                        BudgetAlert.Code code, Long counterValue, Long counterCap) {
        emit(actor, new BudgetAlert(code, ceiling.scope(), ceiling.label(), used.spent(), used.reserved(),
                used.unknown(), ceiling.limit(),
                ceiling.limit() == null ? 100 : BudgetAlert.percentOf(used.occupied().add(estimate), ceiling.limit()),
                request.provider(), request.model(), counterValue, counterCap));
        if (code == BudgetAlert.Code.QUOTA_EXCEEDED) throw new PublicFailure(409, "QUOTA_EXCEEDED");
        throw new PublicFailure(409, ceiling.exceededCode() == BudgetAlert.Code.ARTICLE_BUDGET_EXCEEDED
                ? "BUDGET_EXCEEDED" : "DAILY_BUDGET_EXCEEDED");
    }

    /**
     * Settlement (the {@code Budget.settle} port). The reservation row is locked and moved by an optimistic
     * predicate, then the settlement fact is appended. A settlement with an {@code UNKNOWN} result keeps the
     * hold and answers {@code RECONCILIATION_REQUIRED}: the estimate stays occupied until a real outcome or a
     * manual release arrives.
     */
    public Reservation settle(ActorContext actor, Settlement settlement) {
        return reportUnresolved(tx.execute(status -> settleInTransaction(actor, settlement, false)));
    }

    /** Reconciliation command: only an unresolved row may be reconciled, and the estimate is never rewritten. */
    public Reservation reconcile(ActorContext actor, Settlement settlement) {
        return reportUnresolved(tx.execute(status -> settleInTransaction(actor, settlement, true)));
    }

    /**
     * An {@code UNKNOWN} outcome is written and committed first, then reported: throwing inside the transaction
     * would roll the ledger back and silently drop the hold that the estimate is still occupying.
     */
    private static Reservation reportUnresolved(Reservation outcome) {
        Reservation settled = Objects.requireNonNull(outcome);
        if (settled.status() == ReservationStatus.UNKNOWN) throw new PublicFailure(409, "RECONCILIATION_REQUIRED");
        return settled;
    }

    private Reservation settleInTransaction(ActorContext actor, Settlement settlement, boolean reconciliation) {
        ledger.lockScope("T08|SETTLEMENT|" + settlement.reservationId());
        Optional<Reservation> replay = ledger.bySettlementKey(actor.ownerId(), settlement.settlementKey());
        if (replay.isPresent()) {
            Reservation replayed = replay.get();
            if (!settlement.requestHash().equals(replayed.settlementHash()))
                throw new PublicFailure(409, "SETTLEMENT_CONFLICT");
            return replayed;
        }
        Reservation head = ledger.headByOwner(actor.ownerId(), settlement.reservationId())
                .orElseThrow(() -> new PublicFailure(404, "NOT_FOUND"));
        if (reconciliation && head.status() != ReservationStatus.UNKNOWN)
            throw new PublicFailure(409, "RECONCILIATION_REQUIRED");
        if (reconciliation && settlement.result() == ReservationStatus.UNKNOWN)
            throw new PublicFailure(422, "RECONCILIATION_RESULT_REQUIRED");
        head.status().allowTransitionTo(settlement.result());

        Usage usage = settlement.actualUsage() == null ? head.usage() : settlement.actualUsage();
        Money actual = settlement.result() == ReservationStatus.SETTLED ? pricedActual(head, settlement, usage) : null;
        Money settled = CostLedger.settledAmount(settlement, actual);
        Money released = CostLedger.releasedAmount(settlement, head.estimatedAmount(), settled);
        Money overRun = CostLedger.overRun(settlement, head.estimatedAmount(), settled);
        ledger.applySettlement(actor, head, settlement, settled, released, overRun, usage,
                settlement.result() == ReservationStatus.UNKNOWN ? Map.of() : countersFromUsage(head, usage));
        audit.append(actor, switch (settlement.result()) {
            case UNKNOWN -> "COST_UNRESOLVED";
            case RELEASED -> "COST_RELEASED";
            default -> "COST_SETTLED";
        }, head.article(), head.id(), null, null);
        return ledger.head(head.owner(), head.article(), head.id()).orElseThrow();
    }

    /**
     * The amount to book. Reported usage is re-priced under the price version pinned by the reservation, so a
     * settlement cannot smuggle in a different rate table; an amount supplied without usage is taken as the
     * provider's own bill. Both must satisfy the canonical six-decimal shape.
     */
    private Money pricedActual(Reservation head, Settlement settlement, Usage usage) {
        if (settlement.actualUsage() == null) {
            if (settlement.actualAmount() == null) throw new PublicFailure(422, "SETTLEMENT_AMOUNT_REQUIRED");
            return settlement.actualAmount();
        }
        Money priced = ledger.priceVersion(head.pricingVersion())
                .orElseThrow(() -> new PublicFailure(503, "PRICING_NOT_PUBLISHED"))
                .actual(head.capability(), usage, Money.ZERO);
        if (settlement.actualAmount() != null && !priced.equals(settlement.actualAmount()))
            throw new PublicFailure(422, "SETTLEMENT_AMOUNT_MISMATCH");
        return priced;
    }

    /** Counters this call contributes to each ceiling. Claim and slot counters only apply when scoped. */
    private Map<BudgetPolicy.Counter, Long> counters(Request request, CostPorts.Executions.Scope scope) {
        Map<BudgetPolicy.Counter, Long> counters = new EnumMap<>(BudgetPolicy.Counter.class);
        counters.put(BudgetPolicy.Counter.CALLS, 1L);
        if (request.usage().searchCalls() > 0) {
            counters.put(BudgetPolicy.Counter.SEARCH_QUERY, (long) request.usage().searchCalls());
            if (scope.claim() != null) counters.put(BudgetPolicy.Counter.CLAIM_QUERY, (long) request.usage().searchCalls());
        }
        if (request.capability().billsModelTokens() && request.usage().outputTokens() > 0)
            counters.put(BudgetPolicy.Counter.MODEL_OUTPUT_TOKENS, (long) request.usage().outputTokens());
        if (request.usage().imageUnits() > 0) {
            counters.put(BudgetPolicy.Counter.IMAGE_GENERATION_ARTICLE, (long) request.usage().imageUnits());
            if (scope.slot() != null)
                counters.put(BudgetPolicy.Counter.IMAGE_GENERATION_SLOT, (long) request.usage().imageUnits());
        }
        if (request.autoEditLoop()) counters.put(BudgetPolicy.Counter.AUTO_EDIT_LOOP, 1L);
        return Map.copyOf(counters);
    }

    /** A settlement carries the counters of what was actually used; only ceilings it occupied are re-derived. */
    private Map<BudgetPolicy.Counter, Long> countersFromUsage(Reservation head, Usage usage) {
        Map<BudgetPolicy.Counter, Long> counters = new EnumMap<>(BudgetPolicy.Counter.class);
        counters.put(BudgetPolicy.Counter.CALLS, 1L);
        if (usage.searchCalls() > 0) counters.put(BudgetPolicy.Counter.SEARCH_QUERY, (long) usage.searchCalls());
        if (head.capability().billsModelTokens() && usage.outputTokens() > 0)
            counters.put(BudgetPolicy.Counter.MODEL_OUTPUT_TOKENS, (long) usage.outputTokens());
        if (usage.imageUnits() > 0) counters.put(BudgetPolicy.Counter.IMAGE_GENERATION_ARTICLE, (long) usage.imageUnits());
        return Map.copyOf(counters);
    }

    /**
     * The one place the admission lock sequence is decided: ceilings in the dictionary order of their
     * {@code lockKey}, whatever order {@link #ceilings} built them in. Sorting is not cosmetic — with a
     * construction-order sequence the set of keys two racing transactions hold depends on the request shape
     * (a claim window present or absent), which is the classic shape of a cross-transaction wait cycle.
     * Round-4 finding F-R4-09: deleting this sort changed no exit code anywhere in the delivery, so the
     * invariant existed only as prose in this class comment until {@code CostPricingTest} pinned the sequence
     * for two differently shaped ceiling lists and {@code verify.py} pinned the call site. No deadlock has
     * been observed today and none is claimed — the claim is only that the order is fixed and now watched.
     */
    static List<Ceiling> inLockOrder(List<Ceiling> ceilings) {
        List<Ceiling> ordered = new ArrayList<>(ceilings);
        ordered.sort(Comparator.comparing(Ceiling::lockKey));
        return List.copyOf(ordered);
    }

    /** Every ceiling a call touches: the article row, the owner's UTC day, the provider window, and any claim/slot. */
    private List<Ceiling> ceilings(CostPorts.ArticleBudget article, String provider, String model,
                                   CostPorts.Executions.Scope scope, LocalDate day) {
        List<Ceiling> ceilings = new ArrayList<>();
        ceilings.add(new Ceiling("ARTICLE", article.article().toString(), "T08|ARTICLE|" + article.article(),
                "l.article_id=?", List.of(article.article()), article.limit(),
                BudgetAlert.Code.ARTICLE_BUDGET_EXCEEDED, articleCaps(), null));
        ceilings.add(new Ceiling("DAY", article.owner() + "|" + day, "T08|DAY|" + article.owner() + "|" + day,
                "l.owner_id=? AND l.bucket_day=?", List.of(article.owner(), day), policy.dailyLimit(),
                BudgetAlert.Code.DAILY_BUDGET_EXCEEDED, Map.of(), null));
        // Provider ceilings are two-level and both levels bind (round-3 ruling F-03): the model entry caps the
        // window of that one model, the provider-wide entry caps the provider summed across every model it
        // serves, and a window is locked and measured exactly when its entry exists — reusing one window for
        // both numbers is how a provider ceiling got silently divided by the number of models. Lock labels go
        // through String.join so provider + "|" + model stays a concatenation only BudgetPolicy.scope performs.
        // Both provider windows carry l.owner_id in their WHERE clause and their lock key: "the provider summed
        // across every model" is summed per Owner and per UTC day, not across the planet (round-4 F-R4-01; the
        // class comment states the consequence and the Owner decision that owns it).
        Optional<BudgetPolicy.ProviderQuota> modelEntry = policy.modelQuota(provider, model);
        Optional<BudgetPolicy.ProviderQuota> wideEntry = policy.providerWideQuota(provider);
        if (modelEntry.isPresent())
            ceilings.add(new Ceiling("PROVIDER-MODEL",
                    String.join("|", article.owner().toString(), provider, model, day.toString()),
                    String.join("|", "T08|PROVIDER-MODEL", article.owner().toString(), provider, model,
                            day.toString()),
                    "l.owner_id=? AND l.provider=? AND l.model=? AND l.bucket_day=?",
                    List.of(article.owner(), provider, model, day), null,
                    BudgetAlert.Code.PROVIDER_QUOTA_EXCEEDED, Map.of(), modelEntry.get()));
        if (wideEntry.isPresent())
            ceilings.add(new Ceiling("PROVIDER", String.join("|", article.owner().toString(), provider,
                            day.toString()),
                    String.join("|", "T08|PROVIDER", article.owner().toString(), provider, day.toString()),
                    "l.owner_id=? AND l.provider=? AND l.bucket_day=?",
                    List.of(article.owner(), provider, day), null,
                    BudgetAlert.Code.PROVIDER_QUOTA_EXCEEDED, Map.of(), wideEntry.get()));
        if (scope.claim() != null)
            ceilings.add(new Ceiling("CLAIM", scope.claim().toString(), "T08|CLAIM|" + scope.claim(), "l.claim_id=?",
                    List.of(scope.claim()), null, BudgetAlert.Code.QUOTA_EXCEEDED,
                    Map.of(BudgetPolicy.Counter.CLAIM_QUERY, policy.cap(BudgetPolicy.Counter.CLAIM_QUERY)), null));
        if (scope.slot() != null)
            ceilings.add(new Ceiling("SLOT", scope.slot().toString(), "T08|SLOT|" + scope.slot(), "l.slot_id=?",
                    List.of(scope.slot()), null, BudgetAlert.Code.QUOTA_EXCEEDED,
                    Map.of(BudgetPolicy.Counter.IMAGE_GENERATION_SLOT,
                            policy.cap(BudgetPolicy.Counter.IMAGE_GENERATION_SLOT)), null));
        return ceilings;
    }

    private Map<BudgetPolicy.Counter, Long> articleCaps() {
        Map<BudgetPolicy.Counter, Long> caps = new LinkedHashMap<>();
        for (BudgetPolicy.Counter counter : List.of(BudgetPolicy.Counter.CALLS, BudgetPolicy.Counter.SEARCH_QUERY,
                BudgetPolicy.Counter.MODEL_OUTPUT_TOKENS, BudgetPolicy.Counter.AUTO_EDIT_LOOP,
                BudgetPolicy.Counter.IMAGE_GENERATION_ARTICLE))
            caps.put(counter, policy.cap(counter));
        return Map.copyOf(caps);
    }

    /** Budget warning data after a hold: emitted when spend plus live reaches the configured alert percent. */
    private void warnIfCrossedAlert(ActorContext actor, List<Ceiling> ceilings) {
        for (Ceiling ceiling : ceilings) {
            if (ceiling.limit() == null) continue;
            CostPorts.Occupancy used = ledger.occupancy(ceiling.where(), ceiling.args().toArray());
            if (policy.reachedAlert(used.occupied(), ceiling.limit()))
                emit(actor, new BudgetAlert(BudgetAlert.Code.BUDGET_WARNING, ceiling.scope(), ceiling.label(),
                        used.spent(), used.reserved(), used.unknown(), ceiling.limit(),
                        BudgetAlert.percentOf(used.occupied(), ceiling.limit()), null, null, null, null));
        }
    }

    /** Reconciliation queue: unresolved outcomes, then holds that have waited past the configured window. */
    public List<Reservation> pendingReconciliations(ActorContext actor, LocalDate from, LocalDate to) {
        List<Reservation> pending = new ArrayList<>(ledger.unknown(actor.ownerId(), from, to));
        List<Reservation> stale = ledger.staleHolds(actor.ownerId(), from, to,
                Instant.now().minusSeconds(policy.staleReconciliationMinutes() * 60L));
        for (Reservation waiting : stale) {
            emit(actor, new BudgetAlert(BudgetAlert.Code.RECONCILIATION_STALE, "ARTICLE", waiting.article().toString(),
                    Money.ZERO, waiting.estimatedAmount(), Money.ZERO, Money.ZERO, 100, waiting.provider(),
                    waiting.model(), null, null));
            pending.add(waiting);
        }
        return List.copyOf(pending);
    }

    private void emit(ActorContext actor, BudgetAlert alert) { alerts.emit(actor, alert); }

    /**
     * One ceiling as the admission check sees it: a lock key, an aggregate read, the limits it carries, and —
     * when it is one of the provider-quota windows — the quota entry that ceiling enforces. The other ceilings
     * carry {@code null} there and never enter the quota pass. Package-private rather than private so
     * {@code CostPricingTest} can feed a real ceiling list to {@link #inLockOrder} and assert the lock sequence
     * itself (round-4 finding F-R4-09); nothing outside this package constructs one.
     */
    record Ceiling(String scope, String label, String lockKey, String where, List<Object> args, Money limit,
                   BudgetAlert.Code exceededCode, Map<BudgetPolicy.Counter, Long> caps,
                   BudgetPolicy.ProviderQuota quota) {}
}

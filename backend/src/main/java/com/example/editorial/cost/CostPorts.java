package com.example.editorial.cost;

import com.example.editorial.shared.ActorContext;
import com.example.editorial.shared.PublicFailure;
import java.util.Map;
import java.util.UUID;

/**
 * Consumer-owned ports for the cost domain (the {@code Budget.reserve} / {@code Budget.settle} shape in
 * ports.json). The composition root alone binds these to other domains; nothing from another package is
 * imported here, and every unbound port fails closed instead of assuming a budget, an owner or a price.
 */
public final class CostPorts {
    private CostPorts() {}

    /**
     * Article budget ceiling and lifecycle, read from the T06 row while the reservation holds its article lock.
     * A decrease is refused by T06, so a stale read of the ceiling is always conservative, never permissive.
     */
    public record ArticleBudget(UUID article, UUID owner, Money limit, String status, boolean deletionPending,
                                boolean archived) {
        /** A cancelled, paused, archived or deletion-pending job may not start a new chargeable call (SRS 35). */
        public boolean billable() {
            return !deletionPending && !archived && !"CANCELLED".equals(status) && !"PAUSED".equals(status);
        }
        public String refusal() {
            if (deletionPending) return "DELETION_PENDING";
            if (archived) return "ARTICLE_ARCHIVED";
            if ("CANCELLED".equals(status)) return "ARTICLE_CANCELLED";
            if ("PAUSED".equals(status)) return "ARTICLE_PAUSED";
            return "BILLABLE";
        }
    }

    /**
     * rc.3 makes {@code executionId} mandatory on a reservation, but {@code agent_execution} and
     * {@code tool_execution} belong to T09/T10 and do not exist yet. Until they do, the binding must be refused
     * rather than invented: an unbound resolver reports 503 instead of pretending a charge belongs to a real
     * execution. The resolved scope also carries the claim and image slot, which is where the per-claim and
     * per-slot count caps are measured.
     */
    public interface Executions {
        enum Kind { AGENT, TOOL }
        record Scope(UUID execution, Kind kind, UUID article, UUID owner, UUID claim, UUID slot) {}
        Scope resolve(ActorContext actor, UUID article, UUID execution);
    }

    /** Metadata-only audit trail; never carries bodies, prompts or provider payloads. */
    public interface Audit {
        void append(ActorContext actor, String action, UUID article, UUID entity, String beforeHash, String afterHash);
    }

    /**
     * Budget alert delivery (SRS 34: budget past the alert percent, quota reached, reservations waiting on an
     * outcome). The accounting facts behind every alert are always queryable — through the usage service or
     * {@code BudgetService.pendingReconciliations} — so this sink only carries the notification.
     *
     * <p>The default drops the alert silently. That is a known gap, not a finished feature: the composition
     * root binds it only once a notification domain exists (T10/T11), and a deployment that enables cost with
     * this default gets budget data it can pull but never a message pushed. Registered as a prerequisite; no
     * alert delivery may be claimed until a real sink is bound.</p>
     */
    public interface AlertSink { void emit(ActorContext actor, BudgetAlert alert); }

    public static Executions unavailableExecutions() {
        return (actor, article, execution) -> { throw new PublicFailure(503, "EXECUTION_SCOPE_NOT_READY"); };
    }

    public static AlertSink noAlerts() { return (actor, alert) -> {}; }

    /**
     * There is deliberately no {@code noAudit()} factory: an audit trail that swallows every entry would make a
     * charge untraceable, which is worse than refusing to start. The composition root must bind {@link Audit} to
     * the append-only audit table (bootstrap's cost audit bean), and a build that cannot do so fails at startup.
     */

    /**
     * Occupancy of one accounting scope, read in a single statement under the scope lock. {@code unknown} is a
     * subset of the held total: an unresolved call keeps holding its estimate until reconciliation.
     */
    public record Occupancy(Money spent, Money reserved, Money unknown, Map<BudgetPolicy.Counter, Long> counters,
                            long holds) {
        public static Occupancy empty() {
            return new Occupancy(Money.ZERO, Money.ZERO, Money.ZERO, Map.of(), 0);
        }
        public long counter(BudgetPolicy.Counter counter) { return counters.getOrDefault(counter, 0L); }
        /** Everything that still occupies the ceiling: live reservations plus amounts held for reconciliation. */
        public Money held() { return reserved.add(unknown); }
        public Money occupied() { return spent.add(held()); }
    }
}

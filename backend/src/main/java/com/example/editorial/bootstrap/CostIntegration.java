package com.example.editorial.bootstrap;

import com.example.editorial.audit.AuditSink;
import com.example.editorial.cost.CostPorts;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Cost domain wiring, allocated by the main agent when T08 was integrated.
 *
 * <p>Only the audit port can be bound today. {@code agent_execution} and {@code tool_execution} belong to T09/T10,
 * so {@link CostPorts.Executions} stays fail-closed (503 {@code EXECUTION_SCOPE_NOT_READY}) and alert delivery stays
 * unbound until the T10/T11 manual-task queue exists — a reservation therefore still cannot be made against an
 * invented execution, and enabling this domain does not make the budget path look production-ready.</p>
 *
 * <p>{@code audit_log} stores {@code before_hash}/{@code after_hash} as {@code char(64)} with a
 * {@code ^[a-f0-9]{64}$} CHECK and pins {@code detail} to {@code '{}'}, so the trail can carry identifiers and
 * hashes and nothing else. Amounts belong to {@code cost_ledger}. The shape check below is what keeps a money
 * string from reaching those columns: without it the violation surfaces as a database CHECK error in the middle
 * of a live request instead of here.</p>
 */
@Configuration(proxyBeanMethods = false)
@ConditionalOnProperty(name = "editorial.cost.enabled", havingValue = "true")
public class CostIntegration {
    private static final String HASH_SHAPE = "^[a-f0-9]{64}$";

    /** Required binding: with {@code editorial.cost.enabled=true} and no audit chain, startup fails instead of silently dropping accounting audit. */
    @Bean CostPorts.Audit costAudit(AuditSink audit) {
        return (actor, action, article, entity, beforeHash, afterHash) -> {
            requireHashShape("before_hash", beforeHash);
            requireHashShape("after_hash", afterHash);
            audit.append(actor, new AuditSink.Event(action, article, "COST", entity, beforeHash, afterHash));
        };
    }

    private static void requireHashShape(String field, String value) {
        if (value != null && !value.matches(HASH_SHAPE)) {
            // The value is not echoed: it is a caller-supplied string and this message can reach a log.
            throw new IllegalStateException("COST_AUDIT: " + field + " must be null or 64 lowercase hex, got " + value.length() + " characters");
        }
    }
}

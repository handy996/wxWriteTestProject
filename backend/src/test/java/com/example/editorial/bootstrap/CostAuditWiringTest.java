package com.example.editorial.bootstrap;

import com.example.editorial.audit.AuditSink;
import com.example.editorial.cost.CostPorts;
import com.example.editorial.shared.ActorContext;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Guards the cost-&gt;audit wiring allocated at T08 integration. The adapter is the only path from the ledger to
 * {@code audit_log}, whose hash columns are CHECK-constrained, so the assertions here must reject weakened payloads
 * rather than merely pass on a happy path.
 */
class CostAuditWiringTest {
    private static final String HEX64 = "a3f1".repeat(16);

    static final class Capture implements AuditSink {
        final List<AuditSink.Event> events = new ArrayList<>();
        @Override public AuditSink.AuditRecord append(ActorContext actor, AuditSink.Event event) { events.add(event); return null; }
    }

    private static ActorContext actor() { return ActorContext.forWorker(UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID()); }

    @Test void bindsCostFactsOntoTheSharedAuditTrail() {
        Capture sink = new Capture();
        CostPorts.Audit audit = new CostIntegration().costAudit(sink);
        UUID article = UUID.randomUUID();
        UUID entity = UUID.randomUUID();
        audit.append(actor(), "COST_RESERVED", article, entity, null, HEX64);
        assertEquals(1, sink.events.size());
        AuditSink.Event event = sink.events.get(0);
        assertEquals("COST_RESERVED", event.action());
        assertEquals("COST", event.entityType());
        assertEquals(article, event.articleId());
        assertEquals(entity, event.entityId());
        assertNull(event.beforeHash());
        assertEquals(HEX64, event.afterHash());
    }

    @Test void rejectsNonHashPayloadsBeforeTheyReachTheDatabase() {
        for (String payload : new String[] {"0.034200", "12.500000 USD", "ABCDEF", "a".repeat(63), "A".repeat(64), "z".repeat(64), ""}) {
            Capture sink = new Capture();
            CostPorts.Audit audit = new CostIntegration().costAudit(sink);
            assertThrows(IllegalStateException.class,
                    () -> audit.append(actor(), "COST_SETTLED", UUID.randomUUID(), UUID.randomUUID(), payload, null),
                    "before_hash would violate the audit_log CHECK for a weakened payload");
            assertThrows(IllegalStateException.class,
                    () -> audit.append(actor(), "COST_SETTLED", UUID.randomUUID(), UUID.randomUUID(), null, payload),
                    "after_hash would violate the audit_log CHECK for a weakened payload");
            assertTrue(sink.events.isEmpty(), "a rejected payload must never be appended");
        }
    }

    @Test void messageDoesNotEchoTheRejectedValue() {
        CostPorts.Audit audit = new CostIntegration().costAudit(new Capture());
        IllegalStateException failure = assertThrows(IllegalStateException.class,
                () -> audit.append(actor(), "COST_SETTLED", UUID.randomUUID(), UUID.randomUUID(), "super-secret-amount", null));
        assertTrue(!failure.getMessage().contains("super-secret-amount"), "audit rejection must not leak the payload into logs");
    }
}

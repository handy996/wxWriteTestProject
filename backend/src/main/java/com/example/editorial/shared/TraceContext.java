package com.example.editorial.shared;

import java.util.UUID;
import org.slf4j.MDC;

public final class TraceContext implements AutoCloseable {
    private static final ThreadLocal<UUID> CURRENT = new ThreadLocal<>();
    private final UUID previous;
    private TraceContext(UUID id) { previous = CURRENT.get(); CURRENT.set(id); MDC.put("traceId", id.toString()); }
    public static TraceContext open(UUID id) { return new TraceContext(id); }
    public static UUID current() {
        UUID id = CURRENT.get();
        if (id == null) throw new IllegalStateException("Trusted trace scope required");
        return id;
    }
    public void close() {
        if (previous == null) { CURRENT.remove(); MDC.remove("traceId"); }
        else { CURRENT.set(previous); MDC.put("traceId", previous.toString()); }
    }
}

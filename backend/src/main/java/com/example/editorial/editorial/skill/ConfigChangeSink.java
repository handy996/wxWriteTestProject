package com.example.editorial.editorial.skill;

import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;

/**
 * SPI T11 consumes to detect skill config changes. Implementations must be transactional (invoked inside the
 * publish/retire transaction) and idempotent by {@link ConfigChangeEvent#idempotencyKey()}.
 */
public interface ConfigChangeSink {
    void publish(ConfigChangeEvent event);

    /** In-process collector for T05 tests and for T11's integration registration. */
    final class InMemory implements ConfigChangeSink {
        private final List<ConfigChangeEvent> events = new CopyOnWriteArrayList<>();
        @Override public void publish(ConfigChangeEvent event) { events.add(event); }
        public List<ConfigChangeEvent> events() { return List.copyOf(events); }
    }
}

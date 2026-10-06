package com.example.editorial.editorial.skill;

import static org.junit.jupiter.api.Assertions.*;
import com.example.editorial.shared.PublicFailure;
import org.junit.jupiter.api.Test;

class CursorCodecTest {
    @Test void roundTripAndTampering() {
        var codec = new CursorCodec("test-only-cursor-key-32-characters-long");
        String payload = "skill-list-v2|owner|DRAFT|2026-10-04T01:00:00Z|id";
        String cursor = codec.encode(payload);
        assertEquals(payload, codec.decode(cursor));
        assertNull(codec.decode(null));
        for (String bad : java.util.List.of("!" + cursor, cursor + ".extra", "invalid", "x".repeat(1001),
                codec.encode("different").split("\\.")[0] + "." + cursor.split("\\.")[1])) {
            assertEquals("INVALID_CURSOR", assertThrows(PublicFailure.class, () -> codec.decode(bad)).code());
        }
    }
}

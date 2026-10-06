package com.example.editorial.editorial.skill;

import static org.junit.jupiter.api.Assertions.*;
import org.junit.jupiter.api.Test;

class SemVerTest {
    @Test void parsesAndOrders() {
        assertEquals(new SemVer(1, 0, 0), SemVer.parse("1.0.0"));
        assertEquals(new SemVer(1, 0, 10), SemVer.parse("1.0.10"));
        assertTrue(SemVer.parse("1.0.9").compareTo(SemVer.parse("1.0.10")) < 0);
        assertTrue(SemVer.parse("2.0.0").compareTo(SemVer.parse("1.99.99")) > 0);
    }

    @Test void nextPatchNeverReuses() {
        assertEquals(new SemVer(1, 0, 1), SemVer.FIRST.nextPatch());
        assertEquals(new SemVer(1, 0, 11), SemVer.parse("1.0.10").nextPatch());
    }

    @Test void rejectsMalformed() {
        for (String bad : new String[]{"", "1", "1.0", "a.b.c", "1.0.0.0", "-1.0.0", "1..0"})
            assertThrows(IllegalArgumentException.class, () -> SemVer.parse(bad));
    }
}

package com.example.editorial.editorial.skill;

import static org.junit.jupiter.api.Assertions.*;
import com.example.editorial.settings.policy.JsonIO;
import org.junit.jupiter.api.Test;

class SkillConfigDiffTest {
    @Test void additionsRemovalsModificationsAndPointerEscaping() {
        var before = JsonIO.parse("{\"gone\":true,\"rules\":[\"old\"],\"a/b~c\":1}");
        var after = JsonIO.parse("{\"added\":null,\"rules\":[\"new\",\"extra\"],\"a/b~c\":2}");
        var diff = SkillConfigDiff.compare(before, after);
        assertEquals(5, diff.size());
        assertEquals(java.util.List.of("/a~1b~0c", "/added", "/gone", "/rules/0", "/rules/1"),
                diff.stream().map(SkillConfigDiff.Change::path).toList());
        assertEquals(SkillConfigDiff.Kind.ADDED, diff.get(1).kind());
        assertNull(diff.get(1).before());
        assertTrue(diff.get(1).after().isNull());
        assertEquals(SkillConfigDiff.Kind.REMOVED, diff.get(2).kind());
        assertEquals("old", diff.get(3).before().asText());
        assertEquals("new", diff.get(3).after().asText());
        assertEquals(SkillConfigDiff.Kind.MODIFIED, diff.get(3).kind());
        assertEquals(SkillConfigDiff.Kind.REMOVED, SkillConfigDiff.compare(after, before).getLast().kind());
    }

    @Test void sameConfigurationIgnoresObjectKeyOrder() {
        assertTrue(SkillConfigDiff.compare(JsonIO.parse("{\"a\":1,\"b\":2}"),
                JsonIO.parse("{\"b\":2,\"a\":1}")).isEmpty());
    }
}

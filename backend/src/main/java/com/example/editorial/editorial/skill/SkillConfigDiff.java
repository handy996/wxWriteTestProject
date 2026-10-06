package com.example.editorial.editorial.skill;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.ArrayList;
import java.util.List;
import java.util.TreeSet;
import java.util.UUID;

/** Deterministic structural diff. Paths are JSON Pointers; arrays compare by index (order is meaningful).
 * Missing values use Java null, while explicit JSON null remains a NullNode. This is a comparison, not a patch.
 */
public final class SkillConfigDiff {
    public enum Kind { ADDED, REMOVED, MODIFIED }
    public record Change(Kind kind, String path, JsonNode before, JsonNode after) {}
    public record Result(UUID fromVersionId, UUID toVersionId, List<Change> changes) {
        public Result { changes = List.copyOf(changes); }
    }

    private SkillConfigDiff() {}

    public static List<Change> compare(JsonNode before, JsonNode after) {
        List<Change> changes = new ArrayList<>();
        compare("", before, after, changes);
        return List.copyOf(changes);
    }

    private static void compare(String path, JsonNode before, JsonNode after, List<Change> changes) {
        if (java.util.Objects.equals(before, after)) return;
        if (before != null && after != null && before.isObject() && after.isObject()) {
            var names = new TreeSet<String>();
            before.fieldNames().forEachRemaining(names::add);
            after.fieldNames().forEachRemaining(names::add);
            for (String name : names)
                compare(path + "/" + name.replace("~", "~0").replace("/", "~1"), before.get(name), after.get(name), changes);
        } else if (before != null && after != null && before.isArray() && after.isArray()) {
            for (int i = 0; i < Math.max(before.size(), after.size()); i++)
                compare(path + "/" + i, before.get(i), after.get(i), changes);
        } else {
            changes.add(new Change(before == null ? Kind.ADDED : after == null ? Kind.REMOVED : Kind.MODIFIED,
                    path, before == null ? null : before.deepCopy(), after == null ? null : after.deepCopy()));
        }
    }
}

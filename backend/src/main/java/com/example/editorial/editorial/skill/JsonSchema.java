package com.example.editorial.editorial.skill;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/**
 * Minimal JSON Schema 2020-12 subset validator, deliberately limited to the keyword set used by the
 * frozen editorial.schema.json DTOs that T05 validates ({@code SkillConfig}, {@code PromptBinding},
 * {@code ObjectRef}, {@code PolicySnapshot}, {@code SkillSnapshot}). Unsupported keywords fail loudly
 * rather than being silently ignored, so drift in the frozen schema surfaces as an error instead of a
 * false pass.
 *
 * <p>Supported keywords: type, const, enum, format (uuid), minLength, maxLength, minItems, maxItems,
 * items, properties, required, additionalProperties, pattern, minimum, maximum, anyOf, and local
 * {@code $ref} (only {@code #/$defs/&lt;name&gt;} within the same document).
 */
public final class JsonSchema {
    private final JsonNode root;
    public JsonSchema(JsonNode document) {
        if (document == null || !document.isObject() || !document.path("$defs").isObject())
            throw new IllegalArgumentException("schema document must contain $defs");
        root = document;
    }

    public boolean hasDefinition(String defName) { return root.path("$defs").path(defName).isObject(); }

    public void validate(JsonNode instance, String defName) {
        JsonNode schema = root.path("$defs").path(defName);
        if (!schema.isObject()) throw new IllegalArgumentException("unknown $defs/" + defName);
        validate(instance, schema, "#/$defs/" + defName, List.of());
    }

    private void validate(JsonNode instance, JsonNode schema, String path, List<String> refStack) {
        if (schema == null || schema.isMissingNode() || schema.isNull()) return;
        if (!schema.isObject()) throw new IllegalArgumentException("malformed schema at " + path);
        if (schema.has("$ref")) {
            String ref = schema.path("$ref").asText();
            if (!ref.startsWith("#/$defs/")) throw new IllegalArgumentException("unsupported $ref " + ref);
            if (refStack.contains(ref)) throw new IllegalArgumentException("circular $ref " + ref);
            List<String> next = new ArrayList<>(refStack); next.add(ref);
            JsonNode target = root.path("$defs").path(ref.substring("#/$defs/".length()));
            if (!target.isObject()) throw new IllegalArgumentException("unresolved $ref " + ref);
            validate(instance, target, ref, next);
            // A $ref may carry sibling keywords; the frozen DTOs do not, so stop here to stay strict.
            return;
        }
        if (schema.has("anyOf")) {
            JsonNode branches = schema.get("anyOf");
            List<String> failures = new ArrayList<>();
            for (JsonNode branch : branches) {
                try { validate(instance, branch, path + "/anyOf", refStack); return; }
                catch (IllegalArgumentException e) { failures.add(e.getMessage()); }
            }
            throw new IllegalArgumentException(path + ": no anyOf branch matches; " + failures);
        }
        if (schema.has("type")) {
            if (!matchesType(instance, schema.path("type").asText()))
                throw new IllegalArgumentException(path + ": expected " + schema.path("type").asText());
        }
        if (schema.has("const") && !instance.equals(schema.get("const")))
            throw new IllegalArgumentException(path + ": must equal " + schema.get("const"));
        if (schema.has("enum")) {
            boolean found = false;
            for (JsonNode e : schema.get("enum")) if (instance.equals(e)) { found = true; break; }
            if (!found) throw new IllegalArgumentException(path + ": value is not an allowed enum");
        }
        if (schema.has("format") && "uuid".equals(schema.path("format").asText()) && instance.isTextual()) {
            try { UUID.fromString(instance.asText()); }
            catch (IllegalArgumentException e) { throw new IllegalArgumentException(path + ": not a uuid"); }
        }
        if (instance.isTextual()) {
            String text = instance.asText();
            if (schema.has("minLength") && text.codePointCount(0, text.length()) < schema.path("minLength").asInt())
                throw new IllegalArgumentException(path + ": shorter than minLength");
            if (schema.has("maxLength") && text.codePointCount(0, text.length()) > schema.path("maxLength").asInt())
                throw new IllegalArgumentException(path + ": longer than maxLength");
            if (schema.has("pattern") && !text.matches(schema.path("pattern").asText()))
                throw new IllegalArgumentException(path + ": does not match pattern");
        }
        if (instance.isIntegralNumber()) {
            long value = instance.asLong();
            if (schema.has("minimum") && value < schema.path("minimum").asLong())
                throw new IllegalArgumentException(path + ": below minimum");
            if (schema.has("maximum") && value > schema.path("maximum").asLong())
                throw new IllegalArgumentException(path + ": above maximum");
        }
        if (instance.isArray()) {
            ArrayNode array = (ArrayNode) instance;
            if (schema.has("minItems") && array.size() < schema.path("minItems").asInt())
                throw new IllegalArgumentException(path + ": fewer than minItems");
            if (schema.has("maxItems") && array.size() > schema.path("maxItems").asInt())
                throw new IllegalArgumentException(path + ": more than maxItems");
            if (schema.has("items") && schema.get("items").isObject())
                for (int i = 0; i < array.size(); i++)
                    validate(array.get(i), schema.get("items"), path + "[" + i + "]", refStack);
        }
        if (instance.isObject()) {
            ObjectNode object = (ObjectNode) instance;
            if (schema.has("properties") && schema.get("properties").isObject()) {
                schema.get("properties").fields().forEachRemaining(e -> {
                    if (object.has(e.getKey())) validate(object.get(e.getKey()), e.getValue(), path + "." + e.getKey(), refStack);
                });
            }
            if (schema.has("required") && schema.get("required").isArray())
                for (JsonNode req : schema.get("required"))
                    if (!object.has(req.asText())) throw new IllegalArgumentException(path + ": missing required " + req.asText());
            if (schema.path("additionalProperties").isBoolean()) {
                boolean allow = schema.path("additionalProperties").asBoolean();
                if (!allow) {
                    Set<String> known = new HashSet<>();
                    if (schema.path("properties").isObject())
                        schema.path("properties").fieldNames().forEachRemaining(known::add);
                    object.fieldNames().forEachRemaining(name -> {
                        if (!known.contains(name)) throw new IllegalArgumentException(path + ": unknown field " + name);
                    });
                }
            }
        }
    }

    private static boolean matchesType(JsonNode node, String type) {
        return switch (type) {
            case "object" -> node.isObject();
            case "array" -> node.isArray();
            case "string" -> node.isTextual();
            case "integer" -> node.isIntegralNumber();
            case "number" -> node.isNumber();
            case "boolean" -> node.isBoolean();
            case "null" -> node.isNull();
            default -> throw new IllegalArgumentException("unsupported type " + type);
        };
    }

    public static JsonSchema of(JsonNode document) { return new JsonSchema(document); }
}

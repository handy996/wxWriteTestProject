package com.example.editorial.article.ast;

import com.example.editorial.shared.CanonicalRequest;
import com.example.editorial.shared.PublicFailure;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.*;
import java.net.URI;
import java.nio.ByteBuffer;
import java.nio.charset.*;
import java.util.*;
import java.util.regex.Pattern;

/** Restricted Markdown, never HTML and never a network client. IDs are allocated only on import/clone. */
public final class ArticleAst {
    public static final String SCHEMA = "1.0.0-rc.3";
    public static final ObjectMapper JSON = new ObjectMapper();
    private static final Pattern HTML = Pattern.compile("(?is)<\\s*(?:/?[a-z][^>]*|!.*?|\\?.*?)>");
    private ArticleAst() {}
    public static String decode(byte[] bytes) {
        if (bytes.length > 1048576) fail("TEXT_TOO_LARGE");
        try { return StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes)).toString(); }
        catch (CharacterCodingException e) { throw new PublicFailure(422, "INVALID_UTF8"); }
    }
    public static void text(String s) {
        if (s == null) fail("INVALID_TEXT");
        CanonicalRequest.canonical(TextNode.valueOf(s));
        if (s.indexOf('\0') >= 0) fail("INVALID_TEXT");
        if (HTML.matcher(s).find()) fail("HTML_NOT_ALLOWED");
    }
    public static String hash(JsonNode n) { return CanonicalRequest.digest(CanonicalRequest.canonical(n)); }
    public static String blockHash(String text) { text(text); return CanonicalRequest.digest(text.getBytes(StandardCharsets.UTF_8)); }
    public static String contentHash(String title, String subtitle, JsonNode ast) {
        var n = JSON.createObjectNode().put("schemaVersion", SCHEMA).put("title", title);
        n.put("subtitle", subtitle); n.set("contentAst", ast); return hash(n);
    }
    public static int length(String s) { return s.codePointCount(0, s.length()); }
    public static void capacity(JsonNode ast) {
        long count = plainText(ast).codePoints().filter(c -> !Character.isWhitespace(c) && !Character.isSpaceChar(c) && c != 0x85).count();
        if (count < 100 || count > 30000) fail("CONTENT_LENGTH_INVALID");
    }
    public static ObjectNode parse(String format, String content) {
        text(content); decode(content.getBytes(StandardCharsets.UTF_8));
        if (!Set.of("TEXT", "MARKDOWN").contains(format)) fail("UNSUPPORTED_FORMAT");
        var ast = JSON.createObjectNode().put("schemaVersion", SCHEMA); var blocks = ast.putArray("blocks");
        String section = UUID.randomUUID().toString();
        String[] lines = content.replace("\r\n", "\n").replace('\r', '\n').split("\n", -1);
        for (int i = 0; i < lines.length;) {
            if (lines[i].isBlank()) { i++; continue; }
            String line = lines[i++], type = "paragraph"; Integer level = null;
            var items = JSON.createArrayNode();
            if (format.equals("MARKDOWN")) {
                if (line.matches("^\\s*(?:```|~~~|\\|).*" ) || line.matches("^\\s*\\[[^]]+]:.*")) fail("UNSUPPORTED_MARKDOWN");
                var h = Pattern.compile("^(#{1,6}) +(.+)$").matcher(line);
                if (h.matches()) { type = "heading"; level = h.group(1).length(); line = h.group(2); section = UUID.randomUUID().toString(); }
                else if (line.startsWith("> ")) { type = "quote"; line = line.substring(2); }
                else if (line.matches("^(?:[-+*]|[0-9]+\\.) +.+")) {
                    type = "list"; items.add(line.replaceFirst("^(?:[-+*]|[0-9]+\\.) +", ""));
                    while (i < lines.length && lines[i].matches("^(?:[-+*]|[0-9]+\\.) +.+"))
                        items.add(lines[i++].replaceFirst("^(?:[-+*]|[0-9]+\\.) +", ""));
                    var joined = new ArrayList<String>(); items.forEach(x -> joined.add(x.asText())); line = String.join("\n", joined);
                }
            }
            var b = JSON.createObjectNode().put("sectionId", section).put("blockId", UUID.randomUUID().toString()).put("blockType", type);
            var marks = b.putArray("marks");
            String visible = format.equals("TEXT") ? line : inline(line, marks, 0);
            b.put("text", visible); b.putArray("claimRefs"); b.put("level", level); b.putNull("slotId");
            items.removeAll(); if (type.equals("list")) for (String item : visible.split("\n", -1)) items.add(item);
            b.set("items", items); blocks.add(b);
        }
        validate(ast, (kind, id) -> { fail("INVALID_REFERENCE"); }); capacity(ast); return ast;
    }
    private record InlineResult(String text, ArrayNode marks, int next, boolean closed) {}
    private static String inline(String s, ArrayNode marks, int depth) {
        var result = inlineSegment(s, 0, null, depth, 0);
        shift(result.marks(), 0, marks);
        return result.text();
    }
    private static InlineResult inlineSegment(String s, int from, String closing, int depth, int pendingSameChar) {
        if (depth > 8) fail("MARKDOWN_DEPTH");
        StringBuilder out = new StringBuilder();
        var marks = JSON.createArrayNode();
        for (int i = from; i < s.length();) {
            if (s.startsWith("![", i) || s.charAt(i) == '`') fail("UNSUPPORTED_MARKDOWN");
            if (s.charAt(i) == '\\' && i + 1 < s.length()) { out.append(s.charAt(i + 1)); i += 2; continue; }
            char c = s.charAt(i);
            if (c == '*' || c == '_') {
                int end = i + 1;
                while (end < s.length() && s.charAt(end) == c) end++;
                int run = end - i;
                if (run > 3) fail("UNSUPPORTED_MARKDOWN");
                String delimiter = s.substring(i, end);
                int runStart = i;
                while (runStart > 0 && s.charAt(runStart - 1) == c) runStart--;
                int before = runStart == 0 ? -1 : s.codePointBefore(runStart);
                int after = end == s.length() ? -1 : s.codePointAt(end);
                boolean beforeSpace = markdownSpace(before), afterSpace = markdownSpace(after);
                boolean beforePunctuation = markdownPunctuation(before), afterPunctuation = markdownPunctuation(after);
                boolean canOpen = !afterSpace && (!afterPunctuation || beforeSpace || beforePunctuation);
                boolean canClose = !beforeSpace && (!beforePunctuation || afterSpace || afterPunctuation);
                // A run matching all pending same-character layers closes them, even when followed by text.
                if (closing != null && closing.charAt(0) == c && run >= closing.length() && canClose
                        && (run == closing.length() || !canOpen || run == pendingSameChar)) {
                    return new InlineResult(out.toString(), marks, i + closing.length(), true);
                }
                if (canOpen) {
                    if (run == 3) {
                        var triple = tripleEmphasis(s, end, c, depth,
                                closing != null && closing.charAt(0) == c ? pendingSameChar : 0);
                        if (triple.closed()) {
                            int start = length(out.toString()); out.append(triple.text());
                            shift(triple.marks(), start, marks); i = triple.next(); continue;
                        }
                        fail("UNSUPPORTED_MARKDOWN");
                    }
                    int pending = run + (closing != null && closing.charAt(0) == c ? pendingSameChar : 0);
                    var nested = inlineSegment(s, end, delimiter, depth + 1, pending);
                    if (nested.closed() && !nested.text().isEmpty()) {
                        int start = length(out.toString()); out.append(nested.text());
                        int finish = start + length(nested.text());
                        marks.add(mark(run == 2 ? "bold" : "italic", start, finish, null));
                        shift(nested.marks(), start, marks); i = nested.next(); continue;
                    }
                }
                out.append(delimiter); i = end; continue;
            }
            if (s.charAt(i) == '[') {
                int mid = s.indexOf("](", i), close = mid < 0 ? -1 : s.indexOf(')', mid + 2);
                if (close < 0) fail("UNSUPPORTED_MARKDOWN_REFERENCE");
                String href = s.substring(mid + 2, close); https(href);
                var nested = JSON.createArrayNode(); String inner = inline(s.substring(i + 1, mid), nested, depth + 1);
                int start = length(out.toString()); out.append(inner); marks.add(mark("link", start, start + length(inner), href));
                shift(nested, start, marks); i = close + 1; continue;
            }
            out.append(s.charAt(i++));
        }
        return new InlineResult(out.toString(), marks, s.length(), false);
    }
    private static InlineResult tripleEmphasis(String s, int from, char c, int depth, int parentPending) {
        for (int innerSize : new int[]{1, 2}) {
            int outerSize = 3 - innerSize;
            var inner = inlineSegment(s, from, String.valueOf(c).repeat(innerSize), depth + 2, parentPending + 3);
            if (!inner.closed() || inner.text().isEmpty()) continue;
            var outerTail = inlineSegment(s, inner.next(), String.valueOf(c).repeat(outerSize), depth + 1, parentPending + outerSize);
            if (!outerTail.closed()) continue;
            String visible = inner.text() + outerTail.text();
            var marks = JSON.createArrayNode();
            marks.add(mark(outerSize == 2 ? "bold" : "italic", 0, length(visible), null));
            marks.add(mark(innerSize == 2 ? "bold" : "italic", 0, length(inner.text()), null));
            shift(inner.marks(), 0, marks);
            shift(outerTail.marks(), length(inner.text()), marks);
            return new InlineResult(visible, marks, outerTail.next(), true);
        }
        return new InlineResult("", JSON.createArrayNode(), from, false);
    }
    private static boolean markdownSpace(int cp) {
        return cp < 0 || Character.isWhitespace(cp) || Character.isSpaceChar(cp) || cp == 0x85;
    }
    private static boolean markdownPunctuation(int cp) {
        if (cp < 0) return false;
        return switch (Character.getType(cp)) {
            case Character.CONNECTOR_PUNCTUATION, Character.DASH_PUNCTUATION,
                 Character.START_PUNCTUATION, Character.END_PUNCTUATION,
                 Character.INITIAL_QUOTE_PUNCTUATION, Character.FINAL_QUOTE_PUNCTUATION,
                 Character.OTHER_PUNCTUATION, Character.MATH_SYMBOL,
                 Character.CURRENCY_SYMBOL, Character.MODIFIER_SYMBOL,
                 Character.OTHER_SYMBOL -> true;
            default -> false;
        };
    }
    private static ObjectNode mark(String type, int start, int end, String href) { return JSON.createObjectNode().put("type", type).put("start", start).put("end", end).put("href", href); }
    private static void shift(ArrayNode source, int by, ArrayNode to) { source.forEach(n -> { var o = (ObjectNode)n; o.put("start", n.path("start").asInt() + by); o.put("end", n.path("end").asInt() + by); to.add(o); }); }
    private static void https(String href) {
        try { URI uri = URI.create(href); if (!href.startsWith("https://") || uri.getHost() == null || uri.getUserInfo() != null) fail("UNSAFE_LINK"); }
        catch (IllegalArgumentException e) { fail("UNSAFE_LINK"); }
    }
    @FunctionalInterface public interface References { void require(String kind, UUID id); }
    public static void validate(JsonNode ast, References references) {
        fields(ast, "schemaVersion", "blocks");
        if (!SCHEMA.equals(ast.path("schemaVersion").asText()) || !ast.path("blocks").isArray() || ast.path("blocks").isEmpty() || ast.path("blocks").size() > 30000) fail("INVALID_AST");
        Set<String> ids = new HashSet<>(), slots = new HashSet<>();
        for (JsonNode b : ast.path("blocks")) {
            fields(b, "sectionId", "blockId", "blockType", "text", "marks", "claimRefs", "level", "items", "slotId");
            for (String key : List.of("sectionId", "blockId")) if (!b.path(key).isTextual() || !b.path(key).asText().matches("[A-Za-z0-9_-]{1,80}")) fail("INVALID_BLOCK_ID");
            if (Set.of("title","subtitle").contains(b.path("blockId").asText()) || !ids.add(b.path("blockId").asText())) fail("DUPLICATE_BLOCK_ID");
            String type = b.path("blockType").asText();
            if (!Set.of("heading", "paragraph", "list", "quote", "imagePlaceholder").contains(type)) fail("UNKNOWN_BLOCK_TYPE");
            if (!b.path("text").isTextual()) fail("INVALID_TEXT"); String value = b.path("text").asText(); text(value);
            if (length(value) > 30000) fail("BLOCK_TOO_LARGE");
            if (type.equals("heading")) { if (!b.path("level").isIntegralNumber() || b.path("level").asInt() < 1 || b.path("level").asInt() > 6) fail("INVALID_LEVEL"); }
            else if (!b.path("level").isNull()) fail("INVALID_LEVEL");
            array(b.path("items")); var values = new ArrayList<String>();
            for (var item : b.path("items")) { if (!item.isTextual() || item.asText().isEmpty() || length(item.asText()) > 30000) fail("INVALID_ITEMS"); values.add(item.asText()); }
            if (type.equals("list") ? values.isEmpty() || !String.join("\n", values).equals(value) : !values.isEmpty()) fail("INVALID_ITEMS");
            if (type.equals("imagePlaceholder")) {
                if (!value.isEmpty() || !b.path("marks").isEmpty() || !b.path("claimRefs").isEmpty() || !slots.add(b.path("slotId").asText())) fail("INVALID_PLACEHOLDER");
                references.require("SLOT", uuid(b.path("slotId").asText()));
            } else if (!b.path("slotId").isNull()) fail("INVALID_SLOT");
            array(b.path("claimRefs")); Set<String> claims = new HashSet<>();
            b.path("claimRefs").forEach(ref -> { if (!claims.add(ref.asText())) fail("DUPLICATE_REFERENCE"); references.require("CLAIM", uuid(ref.asText())); });
            array(b.path("marks"));
            for (JsonNode m : b.path("marks")) {
                fields(m, "type", "start", "end", "href"); String mt = m.path("type").asText();
                if (!Set.of("bold", "italic", "link").contains(mt)) fail("INVALID_MARK"); range(m, length(value));
                if (mt.equals("link")) https(m.path("href").asText()); else if (!m.path("href").isNull()) fail("INVALID_MARK");
            }
        }
        CanonicalRequest.canonical(ast);
    }
    public static void span(JsonNode ast, JsonNode span) {
        fields(span, "blockId", "start", "end", "quote", "blockHash");
        JsonNode block = null; for (var b : ast.path("blocks")) if (b.path("blockId").equals(span.path("blockId"))) block = b;
        if (block == null) fail("BLOCK_NOT_FOUND"); String s = block.path("text").asText(); range(span, length(s));
        String quote = s.substring(s.offsetByCodePoints(0, span.path("start").intValue()), s.offsetByCodePoints(0, span.path("end").intValue()));
        if (!quote.equals(span.path("quote").asText()) || !blockHash(s).equals(span.path("blockHash").asText())) fail("SPAN_MISMATCH");
    }
    public static void versionSpan(JsonNode version, JsonNode span) {
        String id=span.path("blockId").asText();
        if(!Set.of("title","subtitle").contains(id)) {span(version.path("contentAst"),span);return;}
        if(!version.path(id).isTextual()) fail("BLOCK_NOT_FOUND");
        var ast=JSON.createObjectNode();ast.putArray("blocks").add(JSON.createObjectNode().put("blockId",id).put("text",version.path(id).asText()));span(ast,span);
    }
    private static void range(JsonNode n, int length) {
        if (!n.path("start").isIntegralNumber() || !n.path("end").isIntegralNumber() || n.path("start").longValue() < 0 || n.path("end").longValue() <= n.path("start").longValue() || n.path("end").longValue() > length) fail("INVALID_SPAN");
    }
    public static String plainText(JsonNode ast) { var lines = new ArrayList<String>(); ast.path("blocks").forEach(b -> lines.add(b.path("text").asText())); return String.join("\n", lines); }
    public static ObjectNode cloneAst(JsonNode ast) {
        ObjectNode copy = ast.deepCopy(); var sections = new HashMap<String,String>(); var kept = JSON.createArrayNode();
        for (var n : copy.path("blocks")) { var b = (ObjectNode)n;
            if (b.path("blockType").asText().equals("imagePlaceholder")) continue;
            b.put("sectionId", sections.computeIfAbsent(b.path("sectionId").asText(), k -> UUID.randomUUID().toString()));
            b.put("blockId", UUID.randomUUID().toString()); b.putArray("claimRefs"); kept.add(b);
        }
        copy.set("blocks", kept); validate(copy, (k,id) -> fail("INVALID_REFERENCE")); return copy;
    }
    public static void fields(JsonNode n, String... keys) { var allowed = Set.of(keys); if (!n.isObject() || n.size() != allowed.size()) fail("INVALID_FIELDS"); n.fieldNames().forEachRemaining(k -> { if (!allowed.contains(k)) fail("INVALID_FIELDS"); }); }
    private static void array(JsonNode n) { if (!n.isArray() || n.size() > 1000) fail("INVALID_ARRAY"); }
    public static UUID uuid(String s) { try { var id = UUID.fromString(s); if (!id.toString().equalsIgnoreCase(s)) fail("INVALID_UUID"); return id; } catch (IllegalArgumentException e) { throw new PublicFailure(422,"INVALID_UUID"); } }
    public static void fail(String code) { throw new PublicFailure(422, code); }
}

package com.example.editorial.article.version;

import static com.example.editorial.article.ast.ArticleAst.*;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.*;
import java.util.*;

/** Frozen Diff carries text, not spans or mapping fields. Equal text may still be CHANGE (marks/order).
 * Target order comes first, followed by removed blocks in source order. Split/merge appear as delete/add;
 * their verified mapping remains on the immutable target ArticleVersion. */
public final class VersionDiff {
    private VersionDiff() {}
    public static Map<String,JsonNode> blocks(JsonNode ast) {
        var result=new LinkedHashMap<String,JsonNode>();for(var b:ast.path("blocks"))result.put(b.path("blockId").asText(),b);return result;
    }
    public static ObjectNode between(UUID article,JsonNode from,JsonNode to) {
        var out=JSON.createObjectNode().put("articleId",article.toString()).put("fromVersionId",from.path("meta").path("id").asText()).put("toVersionId",to.path("meta").path("id").asText());
        var rows=out.putArray("blocks");
        for(String anchor:List.of("title","subtitle"))row(rows,anchor,from.path(anchor).asText(""),to.path(anchor).asText(""),from.path(anchor).equals(to.path(anchor))?"UNCHANGED":"CHANGE");
        var old=blocks(from.path("contentAst"));var next=blocks(to.path("contentAst"));var oldOrder=new ArrayList<>(old.keySet());int i=0;
        for(var e:next.entrySet()) {var b=old.get(e.getKey());row(rows,e.getKey(),b==null?"":b.path("text").asText(),e.getValue().path("text").asText(),b==null?"ADD":b.equals(e.getValue()) && oldOrder.indexOf(e.getKey())==i?"UNCHANGED":"CHANGE");i++;}
        old.forEach((id,b)->{if(!next.containsKey(id))row(rows,id,b.path("text").asText(),"","DELETE");});
        if(rows.size()>1000)fail("DIFF_TOO_LARGE");return out;
    }
    private static void row(ArrayNode rows,String id,String before,String after,String kind) {rows.add(JSON.createObjectNode().put("blockId",id).put("kind",kind).put("before",before).put("after",after));}
    public static void mappings(JsonNode oldAst,JsonNode newAst,JsonNode mappings) {
        var old=blocks(oldAst);var next=blocks(newAst);var usedFrom=new HashSet<String>();var usedTo=new HashSet<String>();
        for(var m:mappings) {
            var from=ids(m.path("fromBlockIds"));var to=ids(m.path("toBlockIds"));String reason=m.path("reason").asText();
            if(from.isEmpty()||to.isEmpty()||!old.keySet().containsAll(from)||!next.keySet().containsAll(to))fail("INVALID_BLOCK_MAPPING");
            if(reason.equals("SPLIT") && (from.size()!=1||to.size()<2) || reason.equals("MERGE") && (from.size()<2||to.size()!=1)
                )fail("INVALID_BLOCK_MAPPING");
            for(String id:from)if(next.containsKey(id)||!usedFrom.add(id))fail("INVALID_BLOCK_MAPPING");
            for(String id:to)if(old.containsKey(id)||!usedTo.add(id))fail("INVALID_BLOCK_MAPPING");
        }
        var removed=new HashSet<>(old.keySet());removed.removeAll(next.keySet());
        var added=new HashSet<>(next.keySet());added.removeAll(old.keySet());
        if(!removed.isEmpty()&&!added.isEmpty()&&(!usedFrom.containsAll(removed)||!usedTo.containsAll(added)))fail("BLOCK_MAPPING_REQUIRED");
        // Exact corresponding blocks cannot silently acquire another ID without an explicit mapping.
        for(var e:old.entrySet()) if(!next.containsKey(e.getKey())&&!usedFrom.contains(e.getKey())) {
            var a=(ObjectNode)e.getValue().deepCopy();a.remove("blockId");
            for(var n:next.entrySet())if(!old.containsKey(n.getKey())&&!usedTo.contains(n.getKey())) {var b=(ObjectNode)n.getValue().deepCopy();b.remove("blockId");if(a.equals(b))fail("STABLE_BLOCK_ID_REQUIRED");}
        }
    }
    /** WriterOutput has no mapping field. A structural full replacement is explicit, never offset-based. */
    public static ArrayNode replacement(JsonNode before,JsonNode after) {
        var old=blocks(before);var next=blocks(after);var from=JSON.createArrayNode();var to=JSON.createArrayNode();
        old.keySet().stream().filter(id->!next.containsKey(id)).forEach(from::add);next.keySet().stream().filter(id->!old.containsKey(id)).forEach(to::add);
        var out=JSON.createArrayNode();if(!from.isEmpty()&&!to.isEmpty()){var m=JSON.createObjectNode().put("reason","REPLACE");m.set("fromBlockIds",from);m.set("toBlockIds",to);out.add(m);}return out;
    }
    private static Set<String> ids(JsonNode n) {var s=new LinkedHashSet<String>();for(var id:n)if(!s.add(id.asText()))fail("INVALID_BLOCK_MAPPING");return s;}
}

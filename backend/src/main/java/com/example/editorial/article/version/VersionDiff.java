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
    private record Plan(Map<String,JsonNode> old,List<Map.Entry<String,JsonNode>> next,
                        Map<String,Integer> oldPosition,List<Map.Entry<String,JsonNode>> removed) {
        int total(){return 2+next.size()+removed.size();}
    }
    private static Plan plan(JsonNode from,JsonNode to) {
        var old=blocks(from.path("contentAst"));var next=blocks(to.path("contentAst"));
        var positions=new HashMap<String,Integer>();int index=0;
        for(String id:old.keySet())positions.put(id,index++);
        var removed=new ArrayList<Map.Entry<String,JsonNode>>();
        for(var entry:old.entrySet())if(!next.containsKey(entry.getKey()))removed.add(entry);
        return new Plan(old,new ArrayList<>(next.entrySet()),positions,removed);
    }
    private static ObjectNode header(UUID article,JsonNode from,JsonNode to) {
        return JSON.createObjectNode().put("articleId",article.toString())
            .put("fromVersionId",from.path("meta").path("id").asText())
            .put("toVersionId",to.path("meta").path("id").asText());
    }
    public static ObjectNode between(UUID article,JsonNode from,JsonNode to) {
        var p=plan(from,to);if(p.total()>1000)fail("DIFF_TOO_LARGE");
        var out=header(article,from,to);var rows=out.putArray("blocks");
        for(int i=0;i<p.total();i++)append(rows,p,from,to,i);
        return out;
    }
    /** Additive paged contract: immutable version IDs fix the source and signed cursors fix the offset. */
    public static ObjectNode page(UUID article,JsonNode from,JsonNode to,int offset,int limit) {
        if(limit<1||limit>100)fail("INVALID_PAGE");
        var p=plan(from,to);if(offset<0||offset>=p.total())fail("INVALID_CURSOR");
        var out=header(article,from,to).put("offset",offset).put("totalBlocks",p.total());
        var rows=out.putArray("blocks");
        for(int i=offset;i<Math.min(p.total(),offset+limit);i++)append(rows,p,from,to,i);
        return out;
    }
    private static void append(ArrayNode rows,Plan p,JsonNode from,JsonNode to,int position) {
        if(position<2){String anchor=position==0?"title":"subtitle";
            row(rows,anchor,from.path(anchor).asText(""),to.path(anchor).asText(""),from.path(anchor).equals(to.path(anchor))?"UNCHANGED":"CHANGE");return;}
        int target=position-2;
        if(target<p.next().size()){
            var e=p.next().get(target);var before=p.old().get(e.getKey());
            row(rows,e.getKey(),before==null?"":before.path("text").asText(),e.getValue().path("text").asText(),
                before==null?"ADD":before.equals(e.getValue())&&p.oldPosition().get(e.getKey())==target?"UNCHANGED":"CHANGE");return;
        }
        var e=p.removed().get(target-p.next().size());row(rows,e.getKey(),e.getValue().path("text").asText(),"","DELETE");
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

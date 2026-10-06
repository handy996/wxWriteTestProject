package com.example.editorial.audit;

import com.example.editorial.shared.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.*;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import org.springframework.jdbc.core.JdbcTemplate;

public final class AuditQuery {
    public record Page(List<AuditSink.AuditRecord> items,String nextCursor) {}
    private final JdbcTemplate db;private final Ownership ownership;private final byte[] signingKey;
    public AuditQuery(JdbcTemplate db,Ownership ownership,String key) {
        this.db=db;this.ownership=ownership;
        if(key==null || key.length()<32)throw new IllegalStateException("T03_CURSOR_KEY: external signing key required");
        signingKey=key.getBytes(StandardCharsets.UTF_8);
    }
    public Page page(ActorContext actor,UUID article,String cursor,int limit) {
        ownership.requireArticle(actor,article);
        if(limit<1 || limit>100)throw new PublicFailure(422,"INVALID_LIMIT");
        List<Object> args=new ArrayList<>();args.add(article);
        String where="";
        if(cursor!=null) {
            try {
                if(cursor.length()>1000)throw new IllegalArgumentException();
                String[] parts=cursor.split("\\.",-1);
                if(parts.length!=2 || !MessageDigest.isEqual(sign(parts[0]),Base64.getUrlDecoder().decode(parts[1])))throw new IllegalArgumentException();
                String[] values=new String(Base64.getUrlDecoder().decode(parts[0]),StandardCharsets.UTF_8).split("\\|",-1);
                if(values.length!=5 || !values[0].equals("audit-desc-v1") || !values[1].equals(actor.ownerId().toString()) || !values[2].equals(article.toString()))throw new IllegalArgumentException();
                where=" AND (created_at,id)<(?,?)";args.add(Timestamp.from(Instant.parse(values[3])));args.add(UUID.fromString(values[4]));
            }catch(Exception e){throw new PublicFailure(422,"INVALID_CURSOR");}
        }
        args.add(limit+1);
        var rows=db.query("SELECT id,actor_id,actor_type,action,article_id,entity_type,entity_id,before_hash,after_hash,trace_id,created_at FROM editorial.audit_log WHERE article_id=?"+where+" ORDER BY created_at DESC,id DESC LIMIT ?",
            (rs,n)->new AuditSink.AuditRecord(rs.getObject(1,UUID.class),rs.getObject(2,UUID.class),rs.getString(3),rs.getString(4),rs.getObject(5,UUID.class),rs.getString(6),rs.getObject(7,UUID.class),rs.getString(8),rs.getString(9),rs.getObject(10,UUID.class),rs.getTimestamp(11).toInstant()),args.toArray());
        boolean more=rows.size()>limit;var result=List.copyOf(rows.subList(0,Math.min(rows.size(),limit)));
        String next=null;
        if(more){var last=result.getLast();String payload=Base64.getUrlEncoder().withoutPadding().encodeToString(("audit-desc-v1|"+actor.ownerId()+"|"+article+"|"+last.createdAt()+"|"+last.id()).getBytes(StandardCharsets.UTF_8));next=payload+"."+Base64.getUrlEncoder().withoutPadding().encodeToString(sign(payload));}
        return new Page(result,next);
    }
    private byte[] sign(String payload) {
        try {Mac mac=Mac.getInstance("HmacSHA256");mac.init(new SecretKeySpec(signingKey,"HmacSHA256"));return mac.doFinal(payload.getBytes(StandardCharsets.UTF_8));}
        catch(Exception e){throw new IllegalStateException("Cursor signing unavailable");}
    }
}

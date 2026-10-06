package com.example.editorial.article.version;

import static com.example.editorial.article.ast.ArticleAst.*;
import com.example.editorial.shared.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

/** Signed keyset position bound to the authorized collection and its filters. */
public final class PageCursor {
    private final byte[] key;
    public PageCursor(String key) {if(key==null || key.length()<32)throw new IllegalArgumentException("Cursor key required");this.key=key.getBytes(StandardCharsets.UTF_8);}
    public String scope(ActorContext a, UUID article, String kind, String filter) {return hash(JSON.createObjectNode().put("owner",a.ownerId().toString()).put("article",article.toString()).put("kind",kind).put("filter",filter));}
    public String read(String cursor,String scope) {
        if(cursor==null)return null;
        try {
            if(cursor.length()>1000)throw new IllegalArgumentException();
            var p=cursor.split("\\.",-1);
            if(p.length!=2 || !MessageDigest.isEqual(sign(p[0]),Base64.getUrlDecoder().decode(p[1])))throw new IllegalArgumentException();
            var n=JSON.readTree(Base64.getUrlDecoder().decode(p[0]));
            if(!scope.equals(n.path("scope").asText()))throw new IllegalArgumentException();
            return n.path("last").asText();
        } catch(Exception e) {throw new PublicFailure(422,"INVALID_CURSOR");}
    }
    public String write(String last,String scope) {
        String p=Base64.getUrlEncoder().withoutPadding().encodeToString(CanonicalRequest.canonical(JSON.createObjectNode().put("scope",scope).put("last",last)));
        return p+"."+Base64.getUrlEncoder().withoutPadding().encodeToString(sign(p));
    }
    private byte[] sign(String s) {try {var m=Mac.getInstance("HmacSHA256");m.init(new SecretKeySpec(key,"HmacSHA256"));return m.doFinal(s.getBytes(StandardCharsets.UTF_8));}catch(Exception e){throw new IllegalStateException(e);}}
    public static void limit(int n) {if(n<1||n>100)fail("INVALID_PAGE");}
}

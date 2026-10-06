package com.example.editorial.shared;

import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;

/** Frozen canonical-v1, deliberately not RFC 8785. */
public final class CanonicalRequest {
    private static final ObjectMapper JSON=new ObjectMapper().enable(JsonParser.Feature.STRICT_DUPLICATE_DETECTION)
            .enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS)
            .disable(com.fasterxml.jackson.core.json.JsonWriteFeature.WRITE_HEX_UPPER_CASE.mappedFeature())
            .enable(com.fasterxml.jackson.core.json.JsonWriteFeature.COMBINE_UNICODE_SURROGATES_IN_UTF8.mappedFeature());
    private CanonicalRequest() {}
    public static JsonNode parse(byte[] bytes) {
        try {
            if(bytes.length>8*1_048_576) throw new PublicFailure(422,"BODY_TOO_LARGE");
            return bytes.length==0 ? NullNode.instance : validate(JSON.readTree(bytes));
        } catch(PublicFailure e){throw e;} catch(Exception e){throw new PublicFailure(400,"INVALID_JSON");}
    }
    private static JsonNode validate(JsonNode n) {
        if(n==null) throw new PublicFailure(400,"INVALID_JSON");
        if(n.isObject()) {
            ObjectNode out=JSON.createObjectNode(); List<String> names=new ArrayList<>(); n.fieldNames().forEachRemaining(names::add);
            Collections.sort(names);
            for(String name:names) {
                if(!name.chars().allMatch(c->c<128)) throw new PublicFailure(422,"NON_ASCII_KEY");
                out.set(name,validate(n.get(name)));
            }
            return out;
        }
        if(n.isArray()) {ArrayNode out=JSON.createArrayNode(); n.forEach(x->out.add(validate(x))); return out;}
        if(n.isTextual()) {
            String s=n.textValue();
            for(int i=0;i<s.length();i++) if(Character.isSurrogate(s.charAt(i))) {
                if(!Character.isHighSurrogate(s.charAt(i)) || i+1>=s.length() || !Character.isLowSurrogate(s.charAt(++i)))
                    throw new PublicFailure(422,"INVALID_UNICODE");
            }
        } else if(n.isIntegralNumber()) {
            if(n.bigIntegerValue().abs().compareTo(java.math.BigInteger.valueOf(9007199254740991L))>0)
                throw new PublicFailure(422,"INTEGER_OUT_OF_RANGE");
        } else if(!n.isNull() && !n.isBoolean()) throw new PublicFailure(422,"FLOAT_NOT_SUPPORTED");
        return n;
    }
    public static byte[] canonical(JsonNode n) {
        try {return JSON.writeValueAsBytes(validate(n));} catch(PublicFailure e){throw e;} catch(Exception e){throw new IllegalStateException(e);}
    }
    /** Actual raw URI, not a route template. Sort raw query pairs, retaining duplicate parameters. */
    public static String route(String path,String query) {
        if(path==null || !path.startsWith("/") || path.contains("?") || path.contains("#")) throw new PublicFailure(422,"INVALID_ROUTE");
        if(query==null || query.isEmpty()) return path;
        String[] pairs=query.split("&",-1); Arrays.sort(pairs);
        return path+"?"+String.join("&",pairs);
    }
    public static String hash(String method,String route,byte[] body) {
        ObjectNode n=JSON.createObjectNode(); n.put("method",method.toUpperCase(Locale.ROOT)); n.put("route",route); n.set("body",parse(body));
        return digest(canonical(n));
    }
    public static String digest(byte[] bytes) {
        try{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));}
        catch(Exception e){throw new IllegalStateException(e);}
    }
    public static long lockKey(String scope) {
        return Long.parseUnsignedLong(digest(scope.getBytes(StandardCharsets.UTF_8)).substring(0,16),16);
    }
}

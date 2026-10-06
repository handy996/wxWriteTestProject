package com.example.editorial.storage;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.Map;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

/**
 * HMAC-SHA256 signed download URLs for the Local adapter. The signature binds
 * (objectKey, expiry) so a URL cannot be forged or its expiry extended; the
 * secret never leaves the server. S3 uses its own presign instead.
 */
public final class SignedUrl {
    private SignedUrl() {}

    public static String sign(String secret, String key, String baseUrl, Instant expiresAt) {
        if (secret == null || secret.length() < 16) throw new IllegalStateException("download secret required");
        ObjectKeys.requireValid(key);
        long expires = expiresAt.getEpochSecond();
        return baseUrl + "/api/v1/storage/objects/" + key + "?expires=" + expires + "&signature=" + signature(secret, key, expires);
    }

    /** Verify signature and expiry; returns the object key, or throws on failure. */
    public static String verify(String secret, String url, Instant now) {
        if (secret == null || secret.length() < 16) throw new IllegalStateException("download secret required");
        int q = url.indexOf('?');
        if (q < 0) throw new IllegalArgumentException("invalid download url");
        String path = url.substring(0, q);
        String key = path.substring(path.lastIndexOf('/') + 1);
        ObjectKeys.requireValid(key);
        Map<String, String> params = new LinkedHashMap<>();
        for (String pair : url.substring(q + 1).split("&")) {
            int eq = pair.indexOf('=');
            if (eq < 0 || params.putIfAbsent(pair.substring(0, eq), pair.substring(eq + 1)) != null)
                throw new IllegalArgumentException("invalid download url");
        }
        if (params.size() != 2 || !params.containsKey("expires") || !params.containsKey("signature"))
            throw new IllegalArgumentException("invalid download url");
        long expires;
        try { expires = Long.parseLong(params.get("expires")); }
        catch (NumberFormatException e) { throw new IllegalArgumentException("invalid download url"); }
        if (expires <= now.getEpochSecond()) throw new IllegalArgumentException("download url expired");
        if (!constantTimeEquals(signature(secret, key, expires), params.get("signature")))
            throw new IllegalArgumentException("invalid download signature");
        return key;
    }

    private static String signature(String secret, String key, long expires) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            byte[] sig = mac.doFinal((key + "|" + expires).getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(sig);
        } catch (Exception e) { throw new IllegalStateException(e); }
    }

    private static boolean constantTimeEquals(String a, String b) {
        return MessageDigest.isEqual(a.getBytes(StandardCharsets.UTF_8), b.getBytes(StandardCharsets.UTF_8));
    }
}

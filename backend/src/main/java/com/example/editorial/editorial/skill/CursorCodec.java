package com.example.editorial.editorial.skill;

import com.example.editorial.shared.PublicFailure;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Base64;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

/** Signed, owner/filter-bound pagination cursor (same pattern as T03 AuditQuery). */
public final class CursorCodec {
    private final byte[] key;
    public CursorCodec(String key) {
        if (key == null || key.length() < 32) throw new IllegalStateException("T05_CURSOR_KEY: signing key required");
        this.key = key.getBytes(StandardCharsets.UTF_8);
    }

    public String encode(String payload) {
        String encoded = b64(payload);
        return encoded + "." + b64(sign(encoded));
    }

    public String decode(String cursor) {
        if (cursor == null) return null;
        try {
            if (cursor.length() > 1000) throw new IllegalArgumentException();
            String[] parts = cursor.split("\\.", -1);
            if (parts.length != 2 || !MessageDigest.isEqual(sign(parts[0]), Base64.getUrlDecoder().decode(parts[1])))
                throw new IllegalArgumentException();
            return new String(Base64.getUrlDecoder().decode(parts[0]), StandardCharsets.UTF_8);
        } catch (Exception e) { throw new PublicFailure(422, "INVALID_CURSOR"); }
    }

    private String b64(String value) {
        return Base64.getUrlEncoder().withoutPadding().encodeToString(value.getBytes(StandardCharsets.UTF_8));
    }

    private String b64(byte[] value) {
        return Base64.getUrlEncoder().withoutPadding().encodeToString(value);
    }

    private byte[] sign(String payload) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(key, "HmacSHA256"));
            return mac.doFinal(payload.getBytes(StandardCharsets.UTF_8));
        } catch (Exception e) { throw new IllegalStateException(e); }
    }
}

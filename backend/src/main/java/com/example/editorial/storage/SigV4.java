package com.example.editorial.storage;

import java.nio.charset.StandardCharsets;
import java.net.URI;
import java.security.MessageDigest;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.TreeMap;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

/**
 * Minimal AWS Signature Version 4 for the S3-compatible adapter (no SDK
 * dependency). Signed requests and presigned GET URLs are assembled from the
 * same canonical-request core. Secrets are only used to derive keys in memory
 * and never logged or returned.
 */
public final class SigV4 {
    public static final String ALGORITHM = "AWS4-HMAC-SHA256";
    private static final DateTimeFormatter AMZ_DATE = DateTimeFormatter.ofPattern("yyyyMMdd'T'HHmmss'Z'").withZone(ZoneOffset.UTC);
    private static final DateTimeFormatter DATE = DateTimeFormatter.ofPattern("yyyyMMdd").withZone(ZoneOffset.UTC);

    private SigV4() {}

    public record Credentials(String accessKey, String secretKey, String region) {}

    public static byte[] signingKey(String secret, String date, String region) {
        byte[] kDate = hmac(("AWS4" + secret).getBytes(StandardCharsets.UTF_8), date.getBytes(StandardCharsets.UTF_8));
        byte[] kRegion = hmac(kDate, region.getBytes(StandardCharsets.UTF_8));
        byte[] kService = hmac(kRegion, "s3".getBytes(StandardCharsets.UTF_8));
        return hmac(kService, "aws4_request".getBytes(StandardCharsets.UTF_8));
    }

    public static String hexSha256(byte[] data) {
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(data)); }
        catch (Exception e) { throw new IllegalStateException(e); }
    }

    private static byte[] hmac(byte[] key, byte[] data) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(key, "HmacSHA256"));
            return mac.doFinal(data);
        } catch (Exception e) { throw new IllegalStateException(e); }
    }

    private static String hexHmac(byte[] key, byte[] data) {
        return HexFormat.of().formatHex(hmac(key, data));
    }

    private static String signature(String secret, String date, String region, String stringToSign) {
        return hexHmac(signingKey(secret, date, region), stringToSign.getBytes(StandardCharsets.UTF_8));
    }

    private static String canonicalRequest(String method, String canonicalUri, String canonicalQuery,
                                           String canonicalHeaders, String signedHeaders, String payloadHash) {
        return method + "\n" + canonicalUri + "\n" + (canonicalQuery == null ? "" : canonicalQuery) + "\n"
            + canonicalHeaders + "\n" + signedHeaders + "\n" + payloadHash;
    }

    private static String scope(String date, String region) {
        return date + "/" + region + "/s3/aws4_request";
    }

    private static String stringToSign(String amzDate, String scope, String canonicalRequest) {
        return ALGORITHM + "\n" + amzDate + "\n" + scope + "\n" + hexSha256(canonicalRequest.getBytes(StandardCharsets.UTF_8));
    }

    /** Presigned GET URL valid for {@code ttl}. */
    public static String presignGet(Credentials c, String host, String uri, Instant now, Duration ttl) {
        return presignGet(c, URI.create("https://" + host + uri), now, ttl);
    }

    public static String presignGet(Credentials c, URI requestUri, Instant now, Duration ttl) {
        requestUri = withoutDefaultPort(requestUri);
        if (requestUri.getRawQuery() != null || ttl.toSeconds() < 1 || ttl.toSeconds() > 604800)
            throw new IllegalArgumentException("invalid presign URI or lifetime");
        String host = requestUri.getRawAuthority();
        String uri = requestUri.getRawPath();
        String amzDate = AMZ_DATE.format(now);
        String date = DATE.format(now);
        String credentialScope = scope(date, c.region());
        String credential = c.accessKey() + "/" + credentialScope;
        Map<String, String> query = new TreeMap<>();
        query.put("X-Amz-Algorithm", ALGORITHM);
        query.put("X-Amz-Credential", credential);
        query.put("X-Amz-Date", amzDate);
        query.put("X-Amz-Expires", Long.toString(ttl.toSeconds()));
        query.put("X-Amz-SignedHeaders", "host");
        String canonicalQuery = encodeQuery(query);
        String canonicalRequest = canonicalRequest("GET", uri, canonicalQuery, "host:" + host + "\n", "host", "UNSIGNED-PAYLOAD");
        String toSign = stringToSign(amzDate, credentialScope, canonicalRequest);
        String sig = signature(c.secretKey(), date, c.region(), toSign);
        return requestUri + "?" + canonicalQuery + "&X-Amz-Signature=" + sig;
    }

    public static Map<String, String> sign(Credentials c, String method, URI uri,
                                           byte[] payload, Map<String, String> extra, Instant now) {
        uri = withoutDefaultPort(uri);
        return sign(c, method, uri.getRawAuthority(), uri.getRawPath(), uri.getRawQuery(), payload, extra, now);
    }

    /** Match HttpClient's wire Host without changing S3's significant raw path/query bytes. */
    static URI withoutDefaultPort(URI uri) {
        boolean defaultPort = ("http".equalsIgnoreCase(uri.getScheme()) && uri.getPort() == 80)
            || ("https".equalsIgnoreCase(uri.getScheme()) && uri.getPort() == 443);
        if (!defaultPort) return uri;
        String authority = uri.getRawAuthority();
        // Remove only the final port suffix, preserving bracketed IPv6 and the bucket subdomain.
        authority = authority.substring(0, authority.lastIndexOf(':'));
        return URI.create(uri.getScheme() + "://" + authority
            + (uri.getRawPath() == null ? "" : uri.getRawPath())
            + (uri.getRawQuery() == null ? "" : "?" + uri.getRawQuery())
            + (uri.getRawFragment() == null ? "" : "#" + uri.getRawFragment()));
    }

    /** Build Authorization headers for a non-presigned request. */
    public static Map<String, String> sign(Credentials c, String method, String host, String uri,
                                           String query, byte[] payload, Map<String, String> extra, Instant now) {
        String amzDate = AMZ_DATE.format(now);
        String date = DATE.format(now);
        String credentialScope = scope(date, c.region());
        String payloadHash = payload == null ? hexSha256(new byte[0]) : hexSha256(payload);
        TreeMap<String, String> headers = new TreeMap<>();
        headers.put("host", host);
        headers.put("x-amz-content-sha256", payloadHash);
        headers.put("x-amz-date", amzDate);
        if (extra != null) extra.forEach((name, value) ->
            headers.put(name.toLowerCase(java.util.Locale.ROOT), value.trim().replaceAll("\\s+", " ")));
        StringBuilder canonicalHeaders = new StringBuilder();
        StringBuilder signedHeaders = new StringBuilder();
        for (var e : headers.entrySet()) {
            canonicalHeaders.append(e.getKey()).append(':').append(e.getValue().trim()).append('\n');
            signedHeaders.append(e.getKey()).append(';');
        }
        String signed = signedHeaders.substring(0, signedHeaders.length() - 1);
        String canonicalRequest = canonicalRequest(method, uri, query, canonicalHeaders.toString(), signed, payloadHash);
        String toSign = stringToSign(amzDate, credentialScope, canonicalRequest);
        String sig = signature(c.secretKey(), date, c.region(), toSign);
        String authorization = ALGORITHM + " Credential=" + c.accessKey() + "/" + credentialScope
            + ", SignedHeaders=" + signed + ", Signature=" + sig;
        Map<String, String> result = new LinkedHashMap<>();
        result.put("Authorization", authorization);
        result.put("x-amz-date", amzDate);
        result.put("x-amz-content-sha256", payloadHash);
        return result;
    }

    static String encodeQuery(Map<String, String> query) {
        StringBuilder sb = new StringBuilder();
        Map<String, String> encoded = new TreeMap<>();
        query.forEach((name, value) -> encoded.put(uriEncode(name), uriEncode(value)));
        for (var e : encoded.entrySet()) {
            if (sb.length() > 0) sb.append('&');
            sb.append(e.getKey()).append('=').append(e.getValue());
        }
        return sb.toString();
    }

    private static String uriEncode(String value) {
        StringBuilder sb = new StringBuilder();
        for (byte b : value.getBytes(StandardCharsets.UTF_8)) {
            int c = b & 0xFF;
            if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '-' || c == '_' || c == '.' || c == '~')
                sb.append((char) c);
            else sb.append('%').append(Character.toUpperCase(Character.forDigit(c >> 4, 16)))
                .append(Character.toUpperCase(Character.forDigit(c & 0xF, 16)));
        }
        return sb.toString();
    }
}

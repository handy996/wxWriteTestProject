package com.example.editorial.storage;

import static org.junit.jupiter.api.Assertions.*;

import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import org.junit.jupiter.api.Test;

class SigV4Test {
    private static final SigV4.Credentials C = new SigV4.Credentials("AKIDEXAMPLE", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", "us-east-1");

    @Test void emptySha256KnownValue() {
        assertEquals("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            SigV4.hexSha256(new byte[0]));
    }

    @Test void signingKeyIsDeterministicAnd32Bytes() {
        byte[] a = SigV4.signingKey(C.secretKey(), "20130524", "us-east-1");
        byte[] b = SigV4.signingKey(C.secretKey(), "20130524", "us-east-1");
        assertArrayEquals(a, b);
        assertEquals(32, a.length);
        assertFalse(java.util.Arrays.equals(a, SigV4.signingKey(C.secretKey(), "20130525", "us-east-1")));
    }

    @Test void presignedGetHasAllRequiredParams() {
        String url = SigV4.presignGet(C, "examplebucket.s3.amazonaws.com", "/test.txt",
            Instant.parse("2013-05-24T00:00:00Z"), Duration.ofMinutes(5));
        assertTrue(url.startsWith("https://examplebucket.s3.amazonaws.com/test.txt?"));
        assertTrue(url.contains("X-Amz-Algorithm=AWS4-HMAC-SHA256"));
        assertTrue(url.contains("X-Amz-Credential=AKIDEXAMPLE%2F20130524%2Fus-east-1%2Fs3%2Faws4_request"));
        assertTrue(url.contains("X-Amz-Date=20130524T000000Z"));
        assertTrue(url.contains("X-Amz-Expires=300"));
        assertTrue(url.contains("X-Amz-SignedHeaders=host"));
        assertTrue(url.contains("X-Amz-Signature="));
    }

    @Test void signProducesAuthorizationHeader() {
        Map<String, String> headers = SigV4.sign(C, "PUT", "bucket.example.com", "/objects/x",
            null, "hello".getBytes(java.nio.charset.StandardCharsets.UTF_8), Map.of(),
            Instant.parse("2026-10-03T00:00:00Z"));
        assertTrue(headers.get("Authorization").startsWith("AWS4-HMAC-SHA256 Credential=AKIDEXAMPLE/20261003/us-east-1/s3/aws4_request"));
        assertTrue(headers.get("Authorization").contains("SignedHeaders=host;x-amz-content-sha256;x-amz-date"));
        assertTrue(headers.get("Authorization").contains("Signature="));
        assertEquals("2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
            headers.get("x-amz-content-sha256")); // sha256("hello")
        assertFalse(headers.containsKey("secret"));
    }
}

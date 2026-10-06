package com.example.editorial.storage;

import static org.junit.jupiter.api.Assertions.*;

import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.Test;

class ObjectKeysTest {
    @Test void generatedKeyIsCanonicalUuid() {
        for (int i = 0; i < 1000; i++) {
            String key = ObjectKeys.generate();
            assertEquals(36, key.length());
            ObjectKeys.requireValid(key);
        }
    }

    @Test void generatesDistinctUnguessableKeys() {
        String a = ObjectKeys.generate(), b = ObjectKeys.generate();
        assertNotEquals(a, b);
    }

    @Test void rejectsTraversalAndPathConfusion() {
        String[] bad = {
            "../../etc/passwd", "..\\..\\windows\\system32", "/abs/path", "C:\\foo", "C:/foo",
            "a/../b", "a\\..\\b", "..", ".", "a\0b", "a\u0000b", "UPPERCASE-UUID".toLowerCase() + "-x",
            "zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz", // non-hex
            "550e8400e29b41d4a716446655440000",      // no hyphens
            "", " ", "x", "..%2f..%2fetc", "http://evil", "file:///etc/passwd",
        };
        for (String key : bad) assertThrows(IllegalArgumentException.class, () -> ObjectKeys.requireValid(key), key);
    }

    @Test void rejectsUppercaseOrNonCanonicalUuid() {
        String canonical = "550e8400-e29b-41d4-a716-446655440000";
        ObjectKeys.requireValid(canonical);
        assertThrows(IllegalArgumentException.class, () -> ObjectKeys.requireValid(canonical.toUpperCase()));
    }

    @Test void detectsMagicBytesNotExtension() {
        assertEquals("image/jpeg", ObjectKeys.detectMime(new byte[]{(byte) 0xFF, (byte) 0xD8, (byte) 0xFF, 0x00}));
        assertEquals("image/png", ObjectKeys.detectMime(new byte[]{(byte) 0x89, 'P', 'N', 'G', '\r', '\n', 0x1A, '\n', 0, 0}));
        assertEquals("image/gif", ObjectKeys.detectMime("GIF89a".getBytes(StandardCharsets.UTF_8)));
        assertEquals("application/pdf", ObjectKeys.detectMime("%PDF-1.7".getBytes(StandardCharsets.UTF_8)));
        assertEquals("application/zip", ObjectKeys.detectMime(new byte[]{'P', 'K', 3, 4, 0, 0}));
        assertEquals("text/plain", ObjectKeys.detectMime("hello world".getBytes(StandardCharsets.UTF_8)));
        assertEquals("application/octet-stream", ObjectKeys.detectMime(new byte[]{0, 1, 2, 3, 0}));
        assertEquals("application/octet-stream", ObjectKeys.detectMime(new byte[0]));
    }
}

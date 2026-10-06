package com.example.editorial.shared;

import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class CanonicalRequestTest {
    byte[] b(String s){return s.getBytes(StandardCharsets.UTF_8);}
    @Test void frozenCanonical(){assertEquals("{\"a\":\"中文/😀\",\"b\":1}",new String(CanonicalRequest.canonical(CanonicalRequest.parse(b("{\"b\":1,\"a\":\"中文/😀\"}"))),StandardCharsets.UTF_8));}
    @Test void invalidCanonical(){for(String input:new String[]{"{\"a\":1,\"a\":2}","{\"中\":1}","1.5","9007199254740992","\"\\ud800\"","{} {}"})assertThrows(PublicFailure.class,()->CanonicalRequest.canonical(CanonicalRequest.parse(b(input))));}
    @Test void routeAndNull(){assertEquals("/api/v1/a?x=1&x=2&z=3",CanonicalRequest.route("/api/v1/a","z=3&x=2&x=1"));assertEquals(CanonicalRequest.hash("post","/a",b("null")),CanonicalRequest.hash("POST","/a",new byte[0]));}
    @Test void etagSemantics(){assertEquals(428,assertThrows(PublicFailure.class,()->Idempotency.requireEtag(null,2)).status());assertEquals(412,assertThrows(PublicFailure.class,()->Idempotency.requireEtag("\"job-1\"",2)).status());Idempotency.requireEtag("\"job-2\"",2);}
}

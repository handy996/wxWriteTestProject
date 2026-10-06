package com.example.editorial.storage;

import static org.junit.jupiter.api.Assertions.*;
import java.net.*;
import java.net.http.*;
import java.time.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import com.example.editorial.shared.PublicFailure;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.Test;

/** Controlled protocol fixtures only; these are NOT a real S3 integration claim. */
class ReviewS3ProtocolTest {
    @Test void noQuerySignatureDiffersFromEmptyQueryRequiredByS3() {
        var c=new SigV4.Credentials("review-id","review-only-generated-key","us-east-1");
        Instant now=Instant.parse("2026-10-04T00:00:00Z");
        String nullQuery=SigV4.sign(c,"PUT","example.com","/b/k",null,new byte[0],null,now).get("Authorization");
        String emptyQuery=SigV4.sign(c,"PUT","example.com","/b/k","",new byte[0],null,now).get("Authorization");
        assertNotEquals(emptyQuery,nullQuery);
        System.out.println("COUNTEREXAMPLE no-query adapter request signs literal null instead of required empty canonical query");
    }

    @Test void normalListXmlYieldsNoCandidatesAndZeroMetadataHeads() throws Exception {
        String key=ObjectKeys.generate();
        HttpServer server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        AtomicInteger heads=new AtomicInteger();
        server.createContext("/",x->{
            if(x.getRequestMethod().equals("HEAD")) {
                heads.incrementAndGet();
                var h=x.getResponseHeaders();
                Map.of("key",key,"hash","a".repeat(64),"size","3","status","STAGING").forEach((k,v)->h.set("x-amz-meta-"+k,v));
                x.sendResponseHeaders(200,-1);
            } else {
                byte[] xml=("<?xml version=\"1.0\"?><ListBucketResult xmlns=\"http://s3.amazonaws.com/doc/2006-03-01/\"><IsTruncated>false</IsTruncated><Contents><Key>objects/"+key+"</Key><Size>3</Size></Contents></ListBucketResult>").getBytes();
                x.sendResponseHeaders(200,xml.length);x.getResponseBody().write(xml);
            }
            x.close();
        });server.start();
        try {
            var backend=new S3StorageBackend(S3StorageBackend.Config.of("http://127.0.0.1:"+server.getAddress().getPort(),"review","us-east-1","review-id","review-only-generated-key",true));
            assertEquals(0,backend.listStaging().size());
            assertEquals(0,heads.get());
            // Even after correcting XML parsing, the placeholder hash and size cannot match a real object.
            assertEquals("OBJECT_MISSING",assertThrows(PublicFailure.class,()->backend.head(new ObjectRef(key,"0".repeat(64),0,"text/plain",false))).code());
            System.out.println("COUNTEREXAMPLE one valid staged key in ListObjectsV2 -> listStaging=[]; HEADs during listing=0; placeholder HEAD also rejects actual metadata");
        }finally {server.stop(0);}
    }

    @Test void configuredEndpointPortAndSchemeAreLostFromPresignedUrl() {
        var backend=new S3StorageBackend(S3StorageBackend.Config.of("http://127.0.0.1:19000","review","us-east-1","review-id","review-only-generated-key",true));
        URI uri=URI.create(backend.presignDownload(new ObjectRef(ObjectKeys.generate(),"a".repeat(64),1,"text/plain",false),Duration.ofMinutes(5)));
        assertEquals("https",uri.getScheme()); assertEquals(-1,uri.getPort());
        System.out.println("COUNTEREXAMPLE endpoint=http://127.0.0.1:19000 -> presigned authority=https://127.0.0.1 (wrong port/protocol)");
    }
}

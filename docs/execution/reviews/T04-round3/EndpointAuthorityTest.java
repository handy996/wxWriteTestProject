package com.example.editorial.storage;

import static org.junit.jupiter.api.Assertions.*;
import com.sun.net.httpserver.HttpServer;
import java.net.*;
import java.net.http.*;
import java.time.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;

/** Observe the real JDK wire Host and independently re-sign against that authority. */
class EndpointAuthorityTest {
    @Test void explicitDefaultPortUsesSameHostForSigningAndTransmission() throws Exception {
        HttpServer server=HttpServer.create(new InetSocketAddress("127.0.0.1",80),0);
        var wireHost=new AtomicReference<String>();
        var authorization=new AtomicReference<String>();
        var actualHeaders=new AtomicReference<Map<String,String>>();
        var date=new AtomicReference<String>();
        server.createContext("/",x->{
            wireHost.set(x.getRequestHeaders().getFirst("Host"));
            authorization.set(x.getRequestHeaders().getFirst("Authorization"));
            date.set(x.getRequestHeaders().getFirst("x-amz-date"));
            Map<String,String> meta=new TreeMap<>();
            x.getRequestHeaders().forEach((k,v)->{if(k.toLowerCase(Locale.ROOT).startsWith("x-amz-meta-"))meta.put(k.toLowerCase(Locale.ROOT),v.getFirst());});
            actualHeaders.set(meta); x.getRequestBody().readAllBytes(); x.sendResponseHeaders(200,-1); x.close();
        });server.start();
        try {
            var credentials=new SigV4.Credentials("review-id","review-fixture-only","us-east-1");
            byte[] bytes="test".getBytes();
            var ref=new ObjectRef(ObjectKeys.generate(),SigV4.hexSha256(bytes),4,"text/plain",false);
            var backend=new S3StorageBackend(S3StorageBackend.Config.of("http://127.0.0.1:80","review-bucket","us-east-1",credentials.accessKey(),credentials.secretKey(),true));
            backend.put(new StoredObject(ref,ObjectStatus.STAGING,1,Instant.now(),null),bytes);
            Instant sent=java.time.LocalDateTime.parse(date.get(),java.time.format.DateTimeFormatter.ofPattern("yyyyMMdd'T'HHmmss'Z'")).toInstant(ZoneOffset.UTC);
            String expected=SigV4.sign(credentials,"PUT",wireHost.get(),"/review-bucket/objects/"+ref.key(),"",bytes,actualHeaders.get(),sent).get("Authorization");
            System.out.println("REVIEW endpoint explicit authority=127.0.0.1:80; wire Host="+wireHost.get()+"; signature matches wire="+expected.equals(authorization.get()));
            assertEquals(expected,authorization.get(),"Request signature must bind the Host actually sent by HttpClient");
        }finally {server.stop(0);}
    }
}

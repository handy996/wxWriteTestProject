package com.example.editorial.storage;

import static org.junit.jupiter.api.Assertions.*;
import com.example.editorial.shared.PublicFailure;
import com.example.editorial.shared.CanonicalRequest;
import java.nio.file.*;
import java.time.*;
import java.util.*;
import org.junit.jupiter.api.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.support.TransactionTemplate;

/** Independent second-review rejection reasons and real reference rollback. */
class IndependentRevisionTest {
    T04PostgresTest f;
    @BeforeAll static void schema() throws Exception {
        T04PostgresTest.createSchema();
        try(var c=T04PostgresTest.adminConnection(); var s=c.createStatement()) {
            s.execute("CREATE TABLE editorial.review_round2_ref (id text PRIMARY KEY)");
            s.execute("GRANT SELECT,INSERT ON editorial.review_round2_ref TO editorial_runtime");
        }
    }
    @BeforeEach void setup() throws Exception { f=new T04PostgresTest(); f.setUp(); }

    @Test void damagedObjectRollsBackRealReferenceAndFailsForExpectedReason() throws Exception {
        var db=new JdbcTemplate(T04PostgresTest.runtime);
        for(String mode:List.of("missing","truncated","same-size")) {
            byte[] bytes="test".getBytes();
            var ref=f.store.stage(f.owner,bytes,CanonicalRequest.digest(bytes),4);
            Path file=f.dir.resolve("objects").resolve(ref.key());
            if(mode.equals("missing"))Files.delete(file);
            else Files.writeString(file,mode.equals("truncated")?"t":"evil");
            var artifact=f.artifact(T04PostgresTest.ARTICLE,ref.hash());
            PublicFailure failure=assertThrows(PublicFailure.class,()->new TransactionTemplate(T04PostgresTest.txManager).execute(s->{
                db.update("INSERT INTO editorial.review_round2_ref VALUES (?)",ref.key());
                return f.store.commitReference(f.owner,ref,artifact);
            }));
            assertEquals(mode.equals("missing")?"OBJECT_MISSING":"OBJECT_CORRUPT",failure.code());
            assertEquals(0,db.queryForObject("SELECT count(*) FROM editorial.review_round2_ref WHERE id=?",Integer.class,ref.key()));
            assertEquals(0,T04PostgresTest.auditCount("OBJECT_COMMITTED"));
        }
        System.out.println("REVIEW R02: missing/truncated/same-size corruption reject for correct reason; actual DB references rolled back");
    }

    @Test void cleanupQueryFailureAndEmptyRegistryNeverDeleteBodyOnlyCandidate() throws Exception {
        byte[] bytes="unregistered body".getBytes();
        String key=ObjectKeys.generate();
        Path body=f.dir.resolve("objects").resolve(key);
        Files.write(body,bytes); Files.setLastModifiedTime(body,java.nio.file.attribute.FileTime.from(Instant.now().minus(Duration.ofHours(25))));
        for(List<ObjectRefRegistry> registries:List.of(List.<ObjectRefRegistry>of(),List.<ObjectRefRegistry>of(new ObjectRefRegistry(){
            public Resolution resolve(String k){return null;}
            public boolean referenced(String k){throw new PublicFailure(503,"TEST_REGISTRY_DOWN");}
        }))) {
            var store=new DefaultObjectStore(f.backend,f.ownership,T04PostgresTest.audit,T04PostgresTest.txManager,registries,
                Clock.systemUTC(),1024,Duration.ofHours(24));
            assertEquals(0,store.cleanupOrphans(ObjectRetention.CleanupOptions.live()).deleted().size());
            assertArrayEquals(bytes,Files.readAllBytes(body));
            assertFalse(Files.exists(body.resolveSibling(key+".meta")));
        }
        System.out.println("REVIEW R06: recovery candidate retained when reference inventory unavailable; no speculative metadata repair");
    }
}

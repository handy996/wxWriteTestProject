package com.example.editorial.article.job;

import static org.junit.jupiter.api.Assertions.*;
import com.example.editorial.shared.*;
import com.example.editorial.article.ast.ArticleAst;
import java.time.*;
import java.util.*;
import org.junit.jupiter.api.Test;

/** Explicit in-memory T10/T37 substitutes. Proves handoff ordering only, never durable deletion/disaster recovery. */
class DeletionHandoffTest {
    final UUID owner=UUID.randomUUID(),article=UUID.randomUUID(),key=UUID.randomUUID(); final Instant now=Instant.parse("2026-10-05T00:00:00Z");
    final ActorContext actor=ActorContext.forWorker(owner,owner,UUID.randomUUID());
    class Commands implements DeletionHandoff.Commands {
        DeletionHandoff.Impact impact=new DeletionHandoff.Impact(article,owner,1,2,3,4,List.of("actorId"),List.of(),true,true,now.plusSeconds(900));
        DeletionHandoff.Command command;boolean failAck;int guards,acknowledgements;
        public DeletionHandoff.Impact preview(ActorContext a,UUID id,Instant expiry){assertEquals(now.plusSeconds(900),expiry);return impact;}
        public DeletionHandoff.Command prepare(ActorContext a,UUID id,String p,String q,String k,String h,byte[] b,DeletionHandoff.Guard guard) {
            if(command==null){guards++;guard.check(impact,1);command=new DeletionHandoff.Command(article,UUID.randomUUID(),owner,new Idempotency.Response(202,new byte[0],Map.of("Location","/api/v1/operations/"+UUID.randomUUID())),false);}return command;
        }
        public void acknowledge(DeletionHandoff.Command c,DeletionHandoff.Receipt r){if(failAck)throw new PublicFailure(503,"TEST_ACK_FAILURE");acknowledgements++;command=new DeletionHandoff.Command(c.article(),c.deletion(),c.owner(),c.accepted(),true);}
    }
    Idempotency.Response submit(DeletionHandoff d,String hash) {
        var n=ArticleAst.JSON.createObjectNode().put("impactHash",hash).put("reason","test");byte[] b=CanonicalRequest.canonical(n);String path="/api/v1/articles/"+article+"/deletion";
        return d.submit(actor,article,path,null,key.toString(),CanonicalRequest.hash("POST",path,b),"\"job-1\"",b);
    }
    @Test void journalFailureAndPostJournalFailureNeverReplayFakeSuccess() {
        var commands=new Commands();var receipts=new HashMap<UUID,DeletionHandoff.Receipt>();boolean[] available={false};
        var d=new DeletionHandoff(commands,(a,id)->{if(!available[0])throw new RuntimeException();return receipts.computeIfAbsent(id,k->new DeletionHandoff.Receipt(a,id,"signed-head"));},Clock.fixed(now,ZoneOffset.UTC));
        String hash=d.preview(actor,article).path("impactHash").asText();
        for(int i=0;i<2;i++)assertEquals("DELETION_JOURNAL_UNAVAILABLE",assertThrows(PublicFailure.class,()->submit(d,hash)).code());assertEquals(0,receipts.size());
        available[0]=true;commands.failAck=true;assertThrows(PublicFailure.class,()->submit(d,hash));assertEquals(1,receipts.size());assertFalse(commands.command.journalAcknowledged());
        commands.failAck=false;assertEquals(202,submit(d,hash).status());assertEquals(1,receipts.size());assertEquals(1,commands.guards);assertEquals(1,commands.acknowledgements);
        assertEquals(202,submit(d,hash).status());assertEquals(1,commands.acknowledgements);
    }
    @Test void incompleteInventoryHoldUnknownRetentionAndExpiryFailClosed() {
        for(String mode:List.of("incomplete","hold","unknown","expired")) {
            var commands=new Commands();commands.impact=new DeletionHandoff.Impact(article,owner,1,2,3,4,List.of(),mode.equals("hold")?List.of("legal"):List.of(),!mode.equals("incomplete"),!mode.equals("unknown"),mode.equals("expired")?now:now.plusSeconds(900));
            var d=new DeletionHandoff(commands,(a,id)->{fail("Journal must not be touched");return null;},Clock.fixed(now,ZoneOffset.UTC));
            var error=assertThrows(PublicFailure.class,()->submit(d,DeletionHandoff.dto(commands.impact).path("impactHash").asText()));
            assertEquals(mode.equals("incomplete")?503:409,error.status());assertNull(commands.command);
        }
    }
}

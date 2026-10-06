package com.example.editorial.shared;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.*;
import java.util.function.Supplier;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

/** Authorization -> transaction lock -> replay -> new-command preconditions -> business + final record. */
public final class Idempotency {
    public record Response(int status, byte[] body, Map<String,String> headers) {
        public Response {
            body=body.clone(); headers=Map.copyOf(headers);
            if(status<200 || status>299 || !Set.of("Location","ETag","Content-Type").containsAll(headers.keySet()))
                throw new IllegalArgumentException("Only successful, safe responses may be retained");
        }
        @Override public byte[] body(){return body.clone();}
        public static Response empty(){return new Response(204,new byte[0],Map.of());}
    }
    private final JdbcTemplate db; private final TransactionTemplate tx; private final ObjectMapper json=new ObjectMapper();
    public Idempotency(JdbcTemplate db,PlatformTransactionManager manager){this.db=db;tx=new TransactionTemplate(manager); tx.setTimeout(3);}
    public Response execute(ActorContext actor,String method,String path,String query,String key,String claimedHash,byte[] body,
                            Runnable authorize,Runnable preconditions,Supplier<Response> business) {
        Objects.requireNonNull(actor);
        return tx.execute(status->{
            authorize.run(); // Always re-authorize, including replay. Caller locks mutable scope if required.
            if(key==null || claimedHash==null) throw new PublicFailure(428,"IDEMPOTENCY_REQUIRED");
            UUID uuid;
            try {uuid=UUID.fromString(key); if(!uuid.toString().equalsIgnoreCase(key)) throw new IllegalArgumentException();}
            catch(IllegalArgumentException e){throw new PublicFailure(422,"INVALID_IDEMPOTENCY_KEY");}
            String route=CanonicalRequest.route(path,query), verb=method.toUpperCase(Locale.ROOT), scope=verb+" "+route;
            String hash=CanonicalRequest.hash(verb,route,body);
            if(!hash.equals(claimedHash)) throw new PublicFailure(422,"REQUEST_HASH_MISMATCH");
            db.execute("SET LOCAL lock_timeout='2000ms'");
            db.queryForObject("SELECT pg_advisory_xact_lock(?)",Object.class,CanonicalRequest.lockKey(actor.ownerId()+"|"+scope+"|"+uuid));
            var rows=db.query("SELECT request_hash,response_code,response_body,response_headers::text FROM editorial.idempotency_record WHERE owner_id=? AND route=? AND key=?",
                (rs,n)-> {
                    if(!hash.equals(rs.getString(1))) throw new PublicFailure(409,"IDEMPOTENCY_CONFLICT");
                    try{return new Response(rs.getInt(2),rs.getBytes(3),json.readValue(rs.getString(4),new TypeReference<Map<String,String>>(){}));}
                    catch(java.io.IOException e){throw new PublicFailure(503,"IDEMPOTENCY_UNAVAILABLE");}
                },actor.ownerId(),scope,uuid);
            if(!rows.isEmpty()) return rows.getFirst(); // Expiry is a retention hint, never automatic approval permission.
            preconditions.run();
            Response response=business.get();
            try {
                db.update("INSERT INTO editorial.idempotency_record(id,owner_id,route,key,request_hash,response_code,response_body,response_headers) VALUES (?,?,?,?,?,?,?,?::jsonb)",
                    UUID.randomUUID(),actor.ownerId(),scope,uuid,hash,response.status(),response.body(),json.writeValueAsString(response.headers()));
            } catch(com.fasterxml.jackson.core.JsonProcessingException e){throw new PublicFailure(503,"IDEMPOTENCY_UNAVAILABLE");}
            return response;
        });
    }
    public static void requireEtag(String supplied,long version) {
        if(supplied==null) throw new PublicFailure(428,"IF_MATCH_REQUIRED");
        if(!supplied.equals("\"job-"+version+"\"")) throw new PublicFailure(412,"ETAG_MISMATCH");
    }
}

package com.example.editorial.identity;

import com.example.editorial.audit.AuditSink;
import com.example.editorial.shared.*;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.transaction.*;
import org.springframework.transaction.support.TransactionTemplate;

public final class IdentityService {
    private final JdbcTemplate db; private final PasswordEncoder passwords; private final AuditSink audit;
    private final TransactionTemplate tx,independent; private final String dummy;
    private UUID systemId;
    public IdentityService(JdbcTemplate db,PasswordEncoder passwords,AuditSink audit,PlatformTransactionManager manager) {
        this.db=db;this.passwords=passwords;this.audit=audit;tx=new TransactionTemplate(manager);
        independent=new TransactionTemplate(manager);independent.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRES_NEW);
        dummy=passwords.encode(UUID.randomUUID().toString());
    }
    public void initialize(String username,String displayName,String initialPassword) {
        tx.executeWithoutResult(status->{
            db.queryForObject("SELECT pg_advisory_xact_lock(?)",Object.class,CanonicalRequest.lockKey("T03_BOOTSTRAP"));
            if(db.queryForObject("SELECT count(*) FROM editorial.app_user WHERE bootstrap_key='OWNER'",Integer.class)==0) {
                if(username==null || !username.matches("[A-Za-z0-9_.@-]{1,100}") || displayName==null || displayName.isBlank()
                        || displayName.length()>1000 || initialPassword==null || initialPassword.length()<16 || initialPassword.length()>1000)
                    throw new IllegalStateException("T03_INITIAL_OWNER: external credentials required");
                db.update("INSERT INTO editorial.app_user(id,username,display_name,actor_type,password_hash,bootstrap_key) VALUES (?,?,?,'OWNER',?,'OWNER')",
                    UUID.randomUUID(),username,displayName,passwords.encode(initialPassword));
            }
            db.update("INSERT INTO editorial.app_user(id,username,display_name,actor_type,bootstrap_key) VALUES (?,'__system__','System','SYSTEM_WORKER','SYSTEM') ON CONFLICT(bootstrap_key) DO NOTHING",UUID.randomUUID());
            systemId=db.queryForObject("SELECT id FROM editorial.app_user WHERE bootstrap_key='SYSTEM' AND actor_type='SYSTEM_WORKER'",UUID.class);
        });
    }
    /** TCP peer only. Forwarded headers are disabled by the integration configuration. */
    public void loginAttempt(String peer) {
        independent.executeWithoutResult(status->{
            UUID peerId=UUID.nameUUIDFromBytes(("T03_LOGIN|"+peer).getBytes(StandardCharsets.UTF_8));
            db.execute("SET LOCAL lock_timeout='2000ms'");
            db.queryForObject("SELECT pg_advisory_xact_lock(?)",Object.class,CanonicalRequest.lockKey("T03_LOGIN|"+peer));
            Integer count=db.queryForObject("SELECT count(*) FROM editorial.audit_log WHERE entity_id=? AND action='AUTH_ATTEMPT' AND created_at>clock_timestamp()-interval '1 minute'",Integer.class,peerId);
            if(count>=5) throw new PublicFailure(429,"LOGIN_RATE_LIMIT");
            audit.append(ActorContext.forWorker(systemId,systemId,TraceContext.current()),new AuditSink.Event("AUTH_ATTEMPT",null,"LOGIN_IP",peerId,null,null));
        });
    }
    public SessionIdentity authenticate(String username,String password) {
        record User(UUID id,String name,String hash,boolean enabled,String type) {}
        var users=db.query("SELECT id,display_name,password_hash,enabled,actor_type FROM editorial.app_user WHERE username=?",
            (rs,n)->new User(rs.getObject(1,UUID.class),rs.getString(2),rs.getString(3),rs.getBoolean(4),rs.getString(5)),username);
        User user=users.isEmpty()?null:users.getFirst();
        boolean match=passwords.matches(password,user==null || user.hash()==null?dummy:user.hash());
        if(!match || user==null || !user.enabled() || !user.type().equals("OWNER")) throw new PublicFailure(401,"INVALID_CREDENTIALS");
        return new SessionIdentity(user.id(),user.name(),Instant.now());
    }
    public boolean active(UUID id) {
        return Boolean.TRUE.equals(db.queryForObject("SELECT EXISTS(SELECT 1 FROM editorial.app_user WHERE id=? AND enabled AND actor_type='OWNER')",Boolean.class,id));
    }
    public void loginSuccess(ActorContext actor) {
        tx.executeWithoutResult(s->audit.append(actor,new AuditSink.Event("LOGIN_SUCCEEDED",null,"USER",actor.actorId(),null,null)));
    }
}

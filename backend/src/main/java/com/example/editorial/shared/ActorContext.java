package com.example.editorial.shared;

import com.example.editorial.identity.SessionIdentity;
import java.time.Instant;
import java.util.UUID;
import org.springframework.security.core.context.SecurityContextHolder;

/** Not a request DTO. No public constructor or client-field conversion. */
public final class ActorContext {
    private final UUID actorId, ownerId, traceId;
    private final String actorType;
    private final Instant authenticatedAt;
    private ActorContext(UUID actor, UUID owner, String type, UUID trace, Instant at) {
        actorId=actor; ownerId=owner; actorType=type; traceId=trace; authenticatedAt=at;
    }
    public static ActorContext current() {
        var auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth == null || !auth.isAuthenticated() || !(auth.getPrincipal() instanceof SessionIdentity p))
            throw new PublicFailure(401,"UNAUTHENTICATED");
        return new ActorContext(p.id(),p.id(),"OWNER",TraceContext.current(),p.authenticatedAt());
    }
    /** Internal worker adapter only. Owner scope must come from a persisted authorized job. Never bind to HTTP. */
    public static ActorContext forWorker(UUID systemId, UUID authorizedOwner, UUID trace) {
        return new ActorContext(systemId,authorizedOwner,"SYSTEM_WORKER",trace,Instant.now());
    }
    public void requireHuman() { if (!actorType.equals("OWNER") || !actorId.equals(ownerId)) throw new PublicFailure(403,"HUMAN_REQUIRED"); }
    public UUID actorId(){return actorId;} public UUID ownerId(){return ownerId;}
    public UUID traceId(){return traceId;} public String actorType(){return actorType;}
    public Instant authenticatedAt(){return authenticatedAt;}
}

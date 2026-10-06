package com.example.editorial.identity;

import com.example.editorial.audit.AuditSink;
import com.example.editorial.shared.*;
import jakarta.servlet.http.*;
import java.io.IOException;
import java.util.*;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.context.HttpSessionSecurityContextRepository;
import org.springframework.security.web.csrf.*;
import org.springframework.web.bind.annotation.*;

@RestController
@ConditionalOnProperty(name="editorial.identity.enabled",havingValue="true")
public final class AuthController {
    public record CurrentUser(UUID id,String displayName,String role,List<String> capabilities,String csrfToken) {}
    private final IdentityService identity;private final HttpSessionCsrfTokenRepository csrf;
    private final Idempotency idempotency;private final AuditSink audit;
    public AuthController(IdentityService identity,HttpSessionCsrfTokenRepository csrf,Idempotency idempotency,AuditSink audit) {
        this.identity=identity;this.csrf=csrf;this.idempotency=idempotency;this.audit=audit;
    }
    @PostMapping(value="/api/v1/auth/login",consumes="application/json")
    public CurrentUser login(HttpServletRequest req,HttpServletResponse res)throws IOException {
        var body=CanonicalRequest.parse(req.getInputStream().readNBytes(1_048_577));
        if(!body.isObject() || body.size()!=2 || !body.path("username").isTextual() || !body.path("password").isTextual()
            || body.path("username").textValue().isEmpty() || body.path("username").textValue().length()>100
            || body.path("password").textValue().isEmpty() || body.path("password").textValue().length()>1000)
            throw new PublicFailure(422,"VALIDATION_FAILED");
        SessionIdentity principal=identity.authenticate(body.get("username").textValue(),body.get("password").textValue());
        var context=SecurityContextHolder.createEmptyContext();
        context.setAuthentication(UsernamePasswordAuthenticationToken.authenticated(principal,null,List.of(new SimpleGrantedAuthority("ROLE_OWNER"))));
        SecurityContextHolder.setContext(context);
        try {identity.loginSuccess(ActorContext.current());} catch(RuntimeException e){SecurityContextHolder.clearContext();throw e;}
        if(req.getSession(false)!=null) req.getSession(false).invalidate(); // Do not retain pre-authentication attributes.
        req.getSession(true);
        new HttpSessionSecurityContextRepository().saveContext(context,req,res);
        var token=csrf.generateToken(req);csrf.saveToken(token,req,res);
        return user(principal,token.getToken());
    }
    @GetMapping("/api/v1/me") public CurrentUser me(HttpServletRequest req) {
        var principal=(SessionIdentity)SecurityContextHolder.getContext().getAuthentication().getPrincipal();
        var token=(CsrfToken)req.getAttribute(CsrfToken.class.getName());
        return user(principal,token.getToken());
    }
    private CurrentUser user(SessionIdentity p,String token){return new CurrentUser(p.id(),p.displayName(),"OWNER",List.of(),token);}
    @PostMapping("/api/v1/auth/logout") public void logout(HttpServletRequest req,HttpServletResponse res)throws IOException {
        ActorContext actor=ActorContext.current();
        byte[] bytes=req.getInputStream().readNBytes(1_048_577);
        if(bytes.length!=0)throw new PublicFailure(422,"BODY_NOT_ALLOWED");
        var response=idempotency.execute(actor,req.getMethod(),req.getRequestURI(),req.getQueryString(),req.getHeader("Idempotency-Key"),req.getHeader("X-Request-Hash"),bytes,
            actor::requireHuman,()->{},()->{audit.append(actor,new AuditSink.Event("LOGOUT",null,"USER",actor.actorId(),null,null));return Idempotency.Response.empty();});
        csrf.saveToken(null,req,res);
        if(req.getSession(false)!=null)req.getSession(false).invalidate();
        SecurityContextHolder.clearContext();res.setStatus(response.status());
    }
}

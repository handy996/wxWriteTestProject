package com.example.editorial.identity;

import com.example.editorial.audit.*;
import com.example.editorial.shared.*;
import java.net.URI;
import java.util.List;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.*;
import org.springframework.core.env.Environment;
import org.springframework.http.HttpMethod;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.crypto.password.*;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.context.SecurityContextHolderFilter;
import org.springframework.security.web.csrf.*;
import org.springframework.transaction.PlatformTransactionManager;

/** Disabled until main agent applies shared integration patch and allocates migration. */
@Configuration(proxyBeanMethods=false)
@ConditionalOnProperty(name="editorial.identity.enabled",havingValue="true")
public class T03Configuration {
    /** rc.3 declares the session cookie by this exact name; the container default is not contract-conformant. */
    public static final String SESSION_COOKIE_NAME="EDITORIAL_SESSION";
    @Bean PasswordEncoder t03Passwords(){return Pbkdf2PasswordEncoder.defaultsForSpringSecurity_v5_8();}
    @Bean AuditSink auditSink(JdbcTemplate db,PlatformTransactionManager tx){return new JdbcAuditSink(db,tx);}
    @Bean Ownership ownership(List<Ownership.Resolver> resolvers){return new Ownership(resolvers);}
    @Bean Idempotency idempotency(JdbcTemplate db,PlatformTransactionManager tx){return new Idempotency(db,tx);}
    @Bean AuditQuery auditQuery(JdbcTemplate db,Ownership ownership,Environment env){return new AuditQuery(db,ownership,env.getProperty("editorial.identity.cursor-key"));}
    @Bean IdentityService identityService(JdbcTemplate db,PasswordEncoder passwords,AuditSink audit,PlatformTransactionManager tx){return new IdentityService(db,passwords,audit,tx);}
    @Bean ApplicationRunner initializeIdentity(IdentityService identity,Environment env){return args->identity.initialize(env.getProperty("editorial.identity.owner-username"),env.getProperty("editorial.identity.owner-display-name","Owner"),env.getProperty("editorial.identity.owner-password"));}
    @Bean HttpSessionCsrfTokenRepository t03Csrf(){var repository=new HttpSessionCsrfTokenRepository();repository.setHeaderName("X-CSRF-Token");return repository;}
    @Bean SecurityFilterChain identitySecurity(HttpSecurity http,IdentityService identity,HttpSessionCsrfTokenRepository csrf,Environment env)throws Exception {
        String origin=env.getProperty("editorial.identity.origin","");
        URI uri;
        try {uri=URI.create(origin);}catch(Exception e){throw new IllegalStateException("T03_ORIGIN: valid origin required");}
        if(uri.getHost()==null || uri.getUserInfo()!=null || uri.getRawQuery()!=null || uri.getFragment()!=null || !uri.getPath().isEmpty()
            || !("https".equals(uri.getScheme()) || ("http".equals(uri.getScheme()) && !env.matchesProfiles("prod"))))
            throw new IllegalStateException("T03_ORIGIN: explicit origin required; HTTPS in production");
        if(!"none".equals(env.getProperty("server.forward-headers-strategy","none"))) throw new IllegalStateException("T03_PEER: forwarded headers must be disabled");
        verifySessionCookieContract(env);
        return http
            .securityContext(c->c.requireExplicitSave(true))
            .requestCache(c->c.disable()).formLogin(c->c.disable()).httpBasic(c->c.disable()).logout(c->c.disable())
            .csrf(c->c.csrfTokenRepository(csrf).csrfTokenRequestHandler(new CsrfTokenRequestAttributeHandler())
                .ignoringRequestMatchers(req->req.getMethod().equals("POST") && req.getRequestURI().equals("/api/v1/auth/login")))
            .exceptionHandling(c->c.authenticationEntryPoint((req,res,e)->ErrorResponses.write(res,new PublicFailure(401,"UNAUTHENTICATED")))
                .accessDeniedHandler((req,res,e)->ErrorResponses.write(res,new PublicFailure(403,e instanceof CsrfException?"CSRF_REJECTED":"FORBIDDEN"))))
            .authorizeHttpRequests(c->c.requestMatchers(HttpMethod.POST,"/api/v1/auth/login").permitAll()
                .requestMatchers(HttpMethod.GET,"/actuator/health","/actuator/health/**","/actuator/info").permitAll()
                .requestMatchers("/api/v1/**").hasRole("OWNER").anyRequest().denyAll())
            .addFilterBefore(new RequestBoundary(),SecurityContextHolderFilter.class)
            .addFilterBefore(new RequestGuards(origin,identity),CsrfFilter.class).build();
    }

    /**
     * Session cookie contract check, kept as a package-visible static method so the rejection itself is testable
     * without an {@link HttpSecurity} instance: before this extraction nothing proved that a wrong cookie name
     * actually fails the boot rather than merely being described in a gate. It runs during bean creation, so a
     * deployment that names the cookie anything other than what rc.3 declares cannot start, and a production
     * profile cannot ship an insecure session cookie.
     */
    static void verifySessionCookieContract(Environment env) {
        if(!SESSION_COOKIE_NAME.equals(env.getProperty("server.servlet.session.cookie.name","")))
            throw new IllegalStateException("T03_COOKIE: session cookie name must equal the approved contract name "+SESSION_COOKIE_NAME);
        if(env.matchesProfiles("prod") && (!env.getProperty("server.servlet.session.cookie.secure",Boolean.class,false)
            || !env.getProperty("server.servlet.session.cookie.http-only",Boolean.class,true)
            || !"strict".equals(env.getProperty("server.servlet.session.cookie.same-site","strict"))))
            throw new IllegalStateException("T03_COOKIE: secure production cookie required");
    }
}

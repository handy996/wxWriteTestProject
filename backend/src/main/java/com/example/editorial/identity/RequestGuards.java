package com.example.editorial.identity;

import com.example.editorial.shared.*;
import jakarta.servlet.*;
import jakarta.servlet.http.*;
import java.io.IOException;
import java.util.Set;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.filter.OncePerRequestFilter;

public final class RequestGuards extends OncePerRequestFilter {
    private final String origin; private final IdentityService identity;
    public RequestGuards(String origin,IdentityService identity){this.origin=origin;this.identity=identity;}
    @Override protected void doFilterInternal(HttpServletRequest req,HttpServletResponse res,FilterChain chain)throws ServletException,IOException {
        boolean write=!Set.of("GET","HEAD","OPTIONS").contains(req.getMethod());
        if(write && (!origin.equals(req.getHeader("Origin")) || "cross-site".equals(req.getHeader("Sec-Fetch-Site"))))
            throw new PublicFailure(403,"ORIGIN_REJECTED");
        boolean login=req.getMethod().equals("POST") && req.getRequestURI().equals("/api/v1/auth/login");
        if(login) identity.loginAttempt(req.getRemoteAddr());
        var authentication=SecurityContextHolder.getContext().getAuthentication();
        boolean signedIn=authentication!=null && authentication.isAuthenticated() && authentication.getPrincipal() instanceof SessionIdentity;
        if(signedIn && !identity.active(((SessionIdentity)authentication.getPrincipal()).id())) {
            if(req.getSession(false)!=null)req.getSession(false).invalidate();
            SecurityContextHolder.clearContext();throw new PublicFailure(401,"UNAUTHENTICATED");
        }
        if(req.getRequestURI().startsWith("/api/") && !login && !signedIn) throw new PublicFailure(401,"UNAUTHENTICATED");
        chain.doFilter(req,res);
    }
}

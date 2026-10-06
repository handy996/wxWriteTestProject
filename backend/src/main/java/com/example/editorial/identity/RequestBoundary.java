package com.example.editorial.identity;

import com.example.editorial.shared.*;
import jakarta.servlet.*;
import jakarta.servlet.http.*;
import java.io.IOException;
import java.util.UUID;
import org.springframework.web.filter.OncePerRequestFilter;

/** Outer boundary includes Spring Security failures, not merely MVC exceptions. */
public final class RequestBoundary extends OncePerRequestFilter {
    @Override protected void doFilterInternal(HttpServletRequest req,HttpServletResponse res,FilterChain chain)throws ServletException,IOException {
        UUID trace=UUID.randomUUID();
        try(var ignored=TraceContext.open(trace)) {
            res.setHeader("X-Trace-Id",trace.toString());res.setHeader("Cache-Control","no-store");
            try {chain.doFilter(req,res);} catch(Exception e){if(!res.isCommitted()) ErrorResponses.write(res,ErrorResponses.classify(e));}
        }
    }
}

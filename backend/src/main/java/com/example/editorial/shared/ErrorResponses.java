package com.example.editorial.shared;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.List;
import java.util.UUID;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;

@RestControllerAdvice
@ConditionalOnProperty(name="editorial.identity.enabled",havingValue="true")
public final class ErrorResponses {
    public record Error(String code,String message,UUID traceId,List<Object> details,boolean retryable) {}
    private static final ObjectMapper JSON=new ObjectMapper();
    public static PublicFailure classify(Exception ex) {
        if(ex instanceof PublicFailure p)return p;
        if(ex instanceof org.springframework.security.access.AccessDeniedException) return new PublicFailure(403,"FORBIDDEN");
        if(ex instanceof org.springframework.web.servlet.NoHandlerFoundException || ex instanceof org.springframework.web.servlet.resource.NoResourceFoundException)
            return new PublicFailure(404,"NOT_FOUND");
        if(ex instanceof org.springframework.web.bind.MissingRequestValueException || ex instanceof org.springframework.web.method.annotation.MethodArgumentTypeMismatchException
            || ex instanceof org.springframework.http.converter.HttpMessageNotReadableException || ex instanceof IllegalArgumentException)
            return new PublicFailure(422,"VALIDATION_FAILED");
        if(ex instanceof org.springframework.web.HttpRequestMethodNotSupportedException || ex instanceof org.springframework.web.HttpMediaTypeNotSupportedException)
            return new PublicFailure(400,"INVALID_REQUEST");
        return new PublicFailure(503,"DEPENDENCY_UNAVAILABLE");
    }
    private static Error error(PublicFailure p){return new Error(p.code(),p.safeMessage(),TraceContext.current(),List.of(),p.retryable());}
    public static void write(HttpServletResponse response,PublicFailure p)throws IOException {
        response.setStatus(p.status()); response.setContentType("application/json");response.setHeader("Cache-Control","no-store");
        if(p.status()==429) response.setHeader("Retry-After","60");
        JSON.writeValue(response.getOutputStream(),error(p));
    }
    @ExceptionHandler(Exception.class) public ResponseEntity<Error> handle(Exception ex) {
        PublicFailure p=classify(ex);
        return ResponseEntity.status(p.status()).header("Cache-Control","no-store").body(error(p));
    }
}

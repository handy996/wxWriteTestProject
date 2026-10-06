package com.example.editorial.audit;

import com.example.editorial.shared.ActorContext;
import java.util.UUID;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.web.bind.annotation.*;

@RestController
@ConditionalOnProperty(name="editorial.identity.enabled",havingValue="true")
public final class AuditController {
    private final AuditQuery query;
    public AuditController(AuditQuery query){this.query=query;}
    @GetMapping("/api/v1/articles/{id}/audit-logs")
    public AuditQuery.Page list(@PathVariable UUID id,@RequestParam(required=false)String cursor,@RequestParam(defaultValue="20")int limit) {
        return query.page(ActorContext.current(),id,cursor,limit);
    }
}

package com.example.editorial.cost;

import com.example.editorial.shared.ActorContext;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * The only HTTP surface rc.3 freezes for this domain: {@code GET /api/v1/usage}. Budget alert data is exposed
 * through the service port for the console and workflow domains, not through a new route, because no other
 * cost route exists in the frozen contract.
 */
@RestController
@RequestMapping("/api/v1")
@ConditionalOnProperty(name = "editorial.cost.enabled", havingValue = "true")
public final class CostController {
    private final UsageService usage;

    public CostController(UsageService usage) { this.usage = usage; }

    @GetMapping("/usage")
    public JsonNode usage(@RequestParam(required = false) String dateFrom, @RequestParam(required = false) String dateTo,
                          @RequestParam(required = false) String groupBy, @RequestParam(required = false) String cursor,
                          @RequestParam(defaultValue = "20") int limit) {
        return usage.usage(ActorContext.current(), dateFrom, dateTo, groupBy, cursor, limit);
    }
}

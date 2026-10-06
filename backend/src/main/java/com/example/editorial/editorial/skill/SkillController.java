package com.example.editorial.editorial.skill;

import com.example.editorial.settings.policy.JsonIO;
import com.example.editorial.shared.ActorContext;
import com.example.editorial.shared.CanonicalRequest;
import com.example.editorial.shared.Idempotency;
import com.example.editorial.shared.PublicFailure;
import com.fasterxml.jackson.databind.JsonNode;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.util.Map;
import java.util.UUID;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/** T05 Skill endpoints. Writes are owner-authorized, idempotent and audited through T03's Idempotency component. */
@RestController
@RequestMapping("/api/v1")
@ConditionalOnProperty(name = "editorial.identity.enabled", havingValue = "true")
public final class SkillController {
    private final SkillService skills;
    private final Idempotency idem;
    private final JsonSchema schema;

    public SkillController(SkillService skills, Idempotency idem, JsonSchema schema) {
        this.skills = skills; this.idem = idem; this.schema = schema;
    }

    @GetMapping("/skills")
    public void list(@RequestParam(required = false) String status,
                     @RequestParam(required = false) String cursor,
                     @RequestParam(defaultValue = "20") int limit,
                     HttpServletResponse res) throws Exception {
        var page = skills.list(ActorContext.current(), status, cursor, limit);
        write(res, 200, page, Map.of("Content-Type", "application/json"));
    }

    @PostMapping("/skills")
    public void create(HttpServletRequest req, HttpServletResponse res) throws Exception {
        command(req, res, 201, "CreateSkillRequest", body -> {
            SkillIdentity created = skills.create(ActorContext.current(),
                    body.path("code").asText(), body.path("name").asText());
            return new Idempotency.Response(201, JsonIO.bytes(created),
                    Map.of("Location", "/api/v1/skills/" + created.id(), "ETag", "\"skill-" + created.id() + "\"",
                           "Content-Type", "application/json"));
        });
    }

    @GetMapping("/skills/{id}/versions")
    public void listVersions(@PathVariable UUID id,
                             @RequestParam(required = false) String cursor,
                             @RequestParam(defaultValue = "20") int limit,
                             HttpServletResponse res) throws Exception {
        var page = skills.listVersions(ActorContext.current(), id, cursor, limit);
        write(res, 200, page, Map.of("Content-Type", "application/json"));
    }

    @PostMapping("/skills/{id}/versions")
    public void createVersion(@PathVariable UUID id, HttpServletRequest req, HttpServletResponse res) throws Exception {
        command(req, res, 201, "CreateSkillVersionRequest", body -> {
            var actor = ActorContext.current();
            UUID base = body.hasNonNull("baseVersionId") ? UUID.fromString(body.path("baseVersionId").asText()) : null;
            SkillSnapshot created = skills.createVersion(actor, id, base, new SkillConfig(body.path("config")));
            return new Idempotency.Response(201, JsonIO.bytes(created),
                    Map.of("Location", "/api/v1/skill-versions/" + created.id(), "ETag", "\"skill-version-" + created.id() + "\"",
                           "Content-Type", "application/json"));
        });
    }

    @PutMapping("/skill-versions/{id}")
    public void edit(@PathVariable UUID id, HttpServletRequest req, HttpServletResponse res) throws Exception {
        command(req, res, 200, "EditSkillVersionRequest", body -> {
            SkillSnapshot edited = skills.edit(ActorContext.current(), id, new SkillConfig(body.path("config")));
            return new Idempotency.Response(200, JsonIO.bytes(edited),
                    Map.of("ETag", "\"skill-version-" + edited.id() + "\"", "Content-Type", "application/json"));
        });
    }

    @PostMapping("/skill-versions/{id}/publish")
    public void publish(@PathVariable UUID id, HttpServletRequest req, HttpServletResponse res) throws Exception {
        command(req, res, 200, "PublishSkillRequest", body -> {
            SkillSnapshot published = skills.publish(ActorContext.current(), id, body.path("changeLog").asText());
            return new Idempotency.Response(200, JsonIO.bytes(published),
                    Map.of("ETag", "\"skill-version-" + published.id() + "\"", "Content-Type", "application/json"));
        });
    }

    @PostMapping("/skill-versions/{id}/retire")
    public void retire(@PathVariable UUID id, HttpServletRequest req, HttpServletResponse res) throws Exception {
        command(req, res, 200, "ReasonRequest", body -> {
            SkillSnapshot retired = skills.retire(ActorContext.current(), id, body.path("reason").asText());
            return new Idempotency.Response(200, JsonIO.bytes(retired),
                    Map.of("ETag", "\"skill-version-" + retired.id() + "\"", "Content-Type", "application/json"));
        });
    }

    @FunctionalInterface
    interface Business { Idempotency.Response apply(JsonNode body); }

    private void command(HttpServletRequest req, HttpServletResponse res, int status, String requestDef, Business business) throws Exception {
        var actor = ActorContext.current();
        byte[] body = req.getInputStream().readNBytes(1_048_577);
        String path = req.getRequestURI();
        Runnable authorize = () -> actor.requireHuman();
        // Re-authorize the target resource before any replay is served (ownership must hold on every request).
        var result = idem.execute(actor, req.getMethod(), path, req.getQueryString(),
                req.getHeader("Idempotency-Key"), req.getHeader("X-Request-Hash"), body,
                authorize,
                () -> { JsonNode parsed = CanonicalRequest.parse(body); require(parsed, requestDef); },
                () -> { JsonNode parsed = CanonicalRequest.parse(body); return business.apply(parsed); });
        write(res, result.status(), result.body(), result.headers());
    }

    private void require(JsonNode node, String requestDef) {
        try { schema.validate(node, requestDef); }
        catch (IllegalArgumentException e) { throw new PublicFailure(422, "VALIDATION_FAILED"); }
    }

    private static void write(HttpServletResponse res, int status, Object value, Map<String, String> headers) throws Exception {
        res.setStatus(status);
        headers.forEach(res::setHeader);
        res.setContentType("application/json");
        res.getOutputStream().write(JsonIO.bytes(value));
    }

    private static void write(HttpServletResponse res, int status, byte[] body, Map<String, String> headers) throws Exception {
        res.setStatus(status);
        headers.forEach(res::setHeader);
        res.getOutputStream().write(body);
    }
}

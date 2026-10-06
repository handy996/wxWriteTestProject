package com.example.editorial.editorial.skill;

import static org.junit.jupiter.api.Assertions.*;

import com.example.editorial.EditorialApplication;
import com.example.editorial.settings.policy.PolicyService;
import com.example.editorial.settings.policy.PolicySnapshotPort;
import com.example.editorial.settings.policy.PolicyType;
import com.example.editorial.settings.policy.PromptService;
import com.example.editorial.shared.ActorContext;
import com.example.editorial.shared.CanonicalRequest;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.net.CookieManager;
import java.net.CookiePolicy;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.MethodOrderer;
import org.junit.jupiter.api.Order;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestMethodOrder;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.jdbc.core.JdbcTemplate;

/**
 * Real PostgreSQL + real HTTP + servlet sessions + CSRF + idempotency for the T05 skill/prompt/policy domain.
 * The T05 migration draft (4 tables + triggers + grants) is applied by the external integration harness alongside
 * T03's draft; the baseline loader seeds policies/prompts/skill through the same service paths. No paid calls.
 */
@SpringBootTest(classes = EditorialApplication.class, webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@EnabledIfEnvironmentVariable(named = "T05_REAL_PG", matches = "true")
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class T05PostgresTest {
    static final String ORIGIN = "http://localhost:3000";
    static final ObjectMapper JSON = new ObjectMapper();
    @LocalServerPort int port;
    @Autowired JdbcTemplate db;
    @Autowired PolicyService policies;
    @Autowired PromptService prompts;
    @Autowired SkillService skills;
    @Autowired SkillSnapshotPort skillSnapshotPort;
    @Autowired PolicySnapshotPort policySnapshotPort;
    @Autowired ConfigChangeSink.InMemory events;
    @Autowired org.springframework.security.crypto.password.PasswordEncoder encoder;

    UUID owner() { return db.queryForObject("SELECT id FROM editorial.app_user WHERE bootstrap_key='OWNER'", UUID.class); }
    UUID system() { return db.queryForObject("SELECT id FROM editorial.app_user WHERE bootstrap_key='SYSTEM'", UUID.class); }
    String password() { return System.getenv("INITIAL_OWNER_PASSWORD"); }
    String username() { return System.getenv("INITIAL_OWNER_USERNAME"); }
    void admin(String sql) throws Exception {
        try (Connection c = DriverManager.getConnection(System.getenv("DB_URL"), "editorial_admin", System.getenv("T05_ADMIN_PASSWORD"));
             var s = c.createStatement()) { s.execute(sql); }
    }
    String adminQuery(String sql) throws Exception {
        try (Connection c = DriverManager.getConnection(System.getenv("DB_URL"), "editorial_admin", System.getenv("T05_ADMIN_PASSWORD"));
             var s = c.createStatement(); ResultSet r = s.executeQuery(sql)) { return r.next() ? r.getString(1) : null; }
    }
    @BeforeEach void clearRateWindow() throws Exception { admin("DELETE FROM editorial.audit_log WHERE action='AUTH_ATTEMPT'"); }

    class Client {
        CookieManager cookies = new CookieManager(null, CookiePolicy.ACCEPT_ALL);
        HttpClient client = HttpClient.newBuilder().cookieHandler(cookies).build();
        String csrf;
        HttpResponse<String> call(String method, String path, String body, Map<String, String> headers) throws Exception {
            var r = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + path))
                    .method(method, body == null ? HttpRequest.BodyPublishers.noBody() : HttpRequest.BodyPublishers.ofString(body));
            if (body != null) r.header("Content-Type", "application/json");
            headers.forEach(r::header);
            return client.send(r.build(), HttpResponse.BodyHandlers.ofString());
        }
        HttpResponse<String> login(String user, String pass) throws Exception {
            var r = call("POST", "/api/v1/auth/login", JSON.writeValueAsString(Map.of("username", user, "password", pass)), Map.of("Origin", ORIGIN));
            if (r.statusCode() == 200) csrf = JSON.readTree(r.body()).get("csrfToken").asText();
            return r;
        }
        HttpResponse<String> write(String method, String path, String body, String key) throws Exception {
            String hash = CanonicalRequest.hash(method, path, body == null ? new byte[0] : body.getBytes(StandardCharsets.UTF_8));
            Map<String, String> h = new HashMap<>(Map.of("Origin", ORIGIN, "X-CSRF-Token", csrf, "Idempotency-Key", key, "X-Request-Hash", hash));
            return call(method, path, body, h);
        }
        HttpResponse<String> get(String path) throws Exception { return call("GET", path, null, Map.of()); }
    }

    Client signed() throws Exception { var c = new Client(); assertEquals(200, c.login(username(), password()).statusCode()); return c; }

    void error(HttpResponse<String> r, int status) throws Exception {
        assertEquals(status, r.statusCode(), r.body());
        var n = JSON.readTree(r.body());
        assertEquals(Set.of("code", "message", "traceId", "details", "retryable"),
                new HashSet<String>() {{ n.fieldNames().forEachRemaining(this::add); }});
        assertTrue(n.get("details").isArray());
        assertFalse(r.body().contains("Exception"));
        assertFalse(r.body().contains(password()));
    }

    // ---- config fixture built from the seeded policies/prompts
    String configBody() {
        ObjectNode c = JSON.createObjectNode();
        c.put("name", "CustomSkill");
        c.put("description", "测试技能配置");
        c.put("locale", "zh-CN");
        c.put("channel", "WECHAT");
        c.set("audience", arr("普通读者"));
        c.set("tone", arr("真实"));
        c.set("structureRules", arr("场景→问题"));
        c.set("titleRules", arr("5 个候选"));
        c.set("openingRules", JSON.createObjectNode().put("problemWithinChars", 300));
        c.set("headingRules", arr("信息差小标题"));
        c.set("readabilityRules", JSON.createObjectNode().put("recommendedMin", 40).put("recommendedMax", 160)
                .put("longParagraphWarning", 220).put("veryLongParagraph", 320)
                .put("shortParagraphMax", 29).put("shortParagraphRun", 5));
        c.set("imageRules", JSON.createObjectNode().put("maxBodyImages", 5).put("optionalCover", true));
        c.put("factPolicyRef", policies.getPublished(PolicyType.FACT).id().toString());
        c.put("licensePolicyRef", policies.getPublished(PolicyType.LICENSE).id().toString());
        ArrayNode bindings = JSON.createArrayNode();
        for (String agent : BaselineAgents.ALL) {
            var p = prompts.getPublished(agent);
            ObjectNode b = JSON.createObjectNode();
            b.put("agentName", agent);
            b.put("promptVersionId", p.id().toString());
            b.put("hash", p.hash());
            b.put("outputSchema", "AnalysisOutput");
            bindings.add(b);
        }
        c.set("promptBindings", bindings);
        c.set("examples", arr("示例"));
        c.set("antiExamples", arr("反例"));
        c.set("evaluationRubric", arr("主题保真"));
        try { return JSON.writeValueAsString(c); } catch (Exception e) { throw new IllegalStateException(e); }
    }

    static ArrayNode arr(String... v) { ArrayNode a = new ObjectMapper().createArrayNode(); for (String s : v) a.add(s); return a; }

    UUID createSkill(Client c, String code) throws Exception {
        String body = "{\"code\":\"" + code + "\",\"name\":\"" + code + "\"}";
        var r = c.write("POST", "/api/v1/skills", body, UUID.randomUUID().toString());
        assertEquals(201, r.statusCode(), r.body());
        return UUID.fromString(JSON.readTree(r.body()).get("id").asText());
    }

    UUID createVersion(Client c, UUID skillId, String baseVersionId, String config, int expected) throws Exception {
        ObjectNode body = JSON.createObjectNode();
        body.set("config", JSON.readTree(config));
        if (baseVersionId != null) body.put("baseVersionId", baseVersionId);
        var r = c.write("POST", "/api/v1/skills/" + skillId + "/versions", JSON.writeValueAsString(body), UUID.randomUUID().toString());
        assertEquals(expected, r.statusCode(), r.body());
        return expected == 201 ? UUID.fromString(JSON.readTree(r.body()).get("id").asText()) : null;
    }

    String versionOf(UUID versionId) throws Exception {
        return adminQuery("SELECT version FROM editorial.editorial_skill_version WHERE id='" + versionId + "'");
    }

    // ------------------------------------------------------------------ tests

    @Test @Order(1) void emptyInitBaselineAndFourTables() throws Exception {
        // migration created all four tables; baseline loader seeded them through the same service paths
        assertEquals(1, db.queryForObject("SELECT count(*) FROM editorial.editorial_skill", Integer.class));
        assertEquals(5, db.queryForObject("SELECT count(*) FROM editorial.policy_version", Integer.class));
        assertEquals(4, db.queryForObject("SELECT count(*) FROM editorial.prompt_version", Integer.class));
        assertEquals(1, db.queryForObject("SELECT count(*) FROM editorial.editorial_skill_version WHERE status='PUBLISHED'", Integer.class));
        assertEquals(5, db.queryForObject("SELECT count(*) FROM editorial.policy_version WHERE status='PUBLISHED'", Integer.class));
        assertEquals(4, db.queryForObject("SELECT count(*) FROM editorial.prompt_version WHERE status='PUBLISHED'", Integer.class));
        var c = signed();
        var r = c.get("/api/v1/skills");
        assertEquals(200, r.statusCode());
        assertEquals(1, JSON.readTree(r.body()).get("items").size());
        assertEquals("WechatEditorialSkill", JSON.readTree(r.body()).get("items").get(0).get("code").asText());
    }

    @Test @Order(2) void codeUnique() throws Exception {
        var c = signed();
        String body = "{\"code\":\"WechatEditorialSkill\",\"name\":\"x\"}";
        error(c.write("POST", "/api/v1/skills", body, UUID.randomUUID().toString()), 409);
    }

    @Test @Order(3) void firstVersionIs100AndCopySameSkill() throws Exception {
        var c = signed();
        UUID skill = createSkill(c, "FirstVersionSkill");
        UUID v1 = createVersion(c, skill, null, configBody(), 201);
        assertEquals("1.0.0", versionOf(v1));
        UUID v2 = createVersion(c, skill, v1.toString(), configBody(), 201);
        assertEquals("1.0.1", versionOf(v2));
    }

    @Test @Order(4) void crossSkillCopyRejected() throws Exception {
        var c = signed();
        UUID a = createSkill(c, "CrossSkillA");
        UUID b = createSkill(c, "CrossSkillB");
        UUID va = createVersion(c, a, null, configBody(), 201);
        String body = "{\"baseVersionId\":\"" + va + "\",\"config\":" + configBody() + "}";
        error(c.write("POST", "/api/v1/skills/" + b + "/versions", body, UUID.randomUUID().toString()), 422);
    }

    @Test @Order(5) void concurrentFirstVersionOnlyOneSucceeds() throws Exception {
        var c = signed();
        UUID skill = createSkill(c, "ConcurrentSkill");
        var pool = Executors.newFixedThreadPool(4);
        try {
            var jobs = new ArrayList<Future<Integer>>();
            for (int i = 0; i < 4; i++) {
                String body = "{\"config\":" + configBody() + "}";
                jobs.add(pool.submit(() -> c.write("POST", "/api/v1/skills/" + skill + "/versions", body, UUID.randomUUID().toString()).statusCode()));
            }
            int created = 0, conflicted = 0;
            for (var j : jobs) { int code = j.get(20, TimeUnit.SECONDS); if (code == 201) created++; else if (code == 409) conflicted++; }
            assertEquals(1, created);
            assertEquals(3, conflicted);
        } finally { pool.shutdown(); }
        assertEquals(1, db.queryForObject("SELECT count(*) FROM editorial.editorial_skill_version WHERE skill_id=?", Integer.class, skill));
    }

    @Test @Order(6) void versionNumberNeverReusedAcrossPublishAndRetire() throws Exception {
        var c = signed();
        UUID skill = createSkill(c, "NoReuseSkill");
        UUID v1 = createVersion(c, skill, null, configBody(), 201);
        UUID v2 = createVersion(c, skill, v1.toString(), configBody(), 201);
        UUID v3 = createVersion(c, skill, v2.toString(), configBody(), 201);
        assertEquals("1.0.2", versionOf(v3));
        assertEquals(200, c.write("POST", "/api/v1/skill-versions/" + v3 + "/publish", "{\"changeLog\":\"publish\"}", UUID.randomUUID().toString()).statusCode());
        assertEquals(200, c.write("POST", "/api/v1/skill-versions/" + v3 + "/retire", "{\"reason\":\"retire\"}", UUID.randomUUID().toString()).statusCode());
        UUID v4 = createVersion(c, skill, v2.toString(), configBody(), 201);
        assertEquals("1.0.3", versionOf(v4)); // 1.0.2 was retired, not reused
    }

    @Test @Order(7) void publishedCannotBeEdited() throws Exception {
        var c = signed();
        UUID skill = createSkill(c, "ImmutableSkill");
        UUID v = createVersion(c, skill, null, configBody(), 201);
        assertEquals(200, c.write("POST", "/api/v1/skill-versions/" + v + "/publish", "{\"changeLog\":\"p\"}", UUID.randomUUID().toString()).statusCode());
        error(c.write("PUT", "/api/v1/skill-versions/" + v, "{\"config\":" + configBody() + "}", UUID.randomUUID().toString()), 409);
    }

    @Test @Order(8) void invalidConfigRejected() throws Exception {
        var c = signed();
        UUID skill = createSkill(c, "InvalidConfigSkill");
        ObjectNode bad = (ObjectNode) JSON.readTree(configBody());
        bad.put("skipFactCheck", true); // malicious hard-gate bypass attempt
        error(c.write("POST", "/api/v1/skills/" + skill + "/versions", "{\"config\":" + JSON.writeValueAsString(bad) + "}", UUID.randomUUID().toString()), 422);
        bad = (ObjectNode) JSON.readTree(configBody());
        bad.put("locale", "en-US"); // illegal enum
        error(c.write("POST", "/api/v1/skills/" + skill + "/versions", "{\"config\":" + JSON.writeValueAsString(bad) + "}", UUID.randomUUID().toString()), 422);
        bad = (ObjectNode) JSON.readTree(configBody());
        bad.set("promptBindings", JSON.createArrayNode()); // empty bindings
        error(c.write("POST", "/api/v1/skills/" + skill + "/versions", "{\"config\":" + JSON.writeValueAsString(bad) + "}", UUID.randomUUID().toString()), 422);
        bad = (ObjectNode) JSON.readTree(configBody());
        bad.put("factPolicyRef", UUID.randomUUID().toString()); // nonexistent policy
        error(c.write("POST", "/api/v1/skills/" + skill + "/versions", "{\"config\":" + JSON.writeValueAsString(bad) + "}", UUID.randomUUID().toString()), 404);
        bad = (ObjectNode) JSON.readTree(configBody());
        ((ObjectNode) bad.path("readabilityRules")).put("recommendedMin", 999); // baseline case violation
        error(c.write("POST", "/api/v1/skills/" + skill + "/versions", "{\"config\":" + JSON.writeValueAsString(bad) + "}", UUID.randomUUID().toString()), 422);
    }

    @Test @Order(9) void hashRecomputableAndBindingsCorrect() throws Exception {
        UUID v = db.queryForObject("SELECT active_version_id FROM editorial.editorial_skill WHERE code='WechatEditorialSkill'", UUID.class);
        String rulesHash = db.queryForObject("SELECT rules_hash FROM editorial.editorial_skill_version WHERE id=?", String.class, v);
        String config = db.queryForObject("SELECT config::text FROM editorial.editorial_skill_version WHERE id=?", String.class, v);
        assertEquals(rulesHash, com.example.editorial.settings.policy.Hashing.ofContent(JSON.readTree(config)));
        for (String agent : BaselineAgents.ALL) {
            var p = prompts.getPublished(agent);
            String recomputed = com.example.editorial.settings.policy.Hashing.ofPrompt(p.systemTemplate(), p.userTemplate(), p.outputSchema());
            assertEquals(p.hash(), recomputed);
        }
    }

    @Test @Order(10) void replayDoesNotDuplicateBusinessResult() throws Exception {
        var c = signed();
        UUID skill = createSkill(c, "ReplaySkill");
        UUID v = createVersion(c, skill, null, configBody(), 201);
        int before = events.events().size();
        String key = UUID.randomUUID().toString();
        String body = "{\"changeLog\":\"publish\"}";
        var first = c.write("POST", "/api/v1/skill-versions/" + v + "/publish", body, key);
        assertEquals(200, first.statusCode());
        var replay = c.write("POST", "/api/v1/skill-versions/" + v + "/publish", body, key);
        assertEquals(200, replay.statusCode());
        assertEquals(first.body(), replay.body());
        assertEquals(before + 1, events.events().size()); // only one config-change event
        // a NEW publish request on an already-published version conflicts
        error(c.write("POST", "/api/v1/skill-versions/" + v + "/publish", body, UUID.randomUUID().toString()), 409);
    }

    @Test @Order(11) void ownerIsolation() throws Exception {
        var c = signed();
        UUID skill = createSkill(c, "IsolationSkill");
        UUID v = createVersion(c, skill, null, configBody(), 201);
        // second owner (test-only isolation account)
        UUID second = UUID.randomUUID();
        db.update("INSERT INTO editorial.app_user(id,username,display_name,actor_type,password_hash) VALUES (?::uuid,?,?, 'OWNER',?)",
                second, "t05-isolation", "Isolation", encoder.encode(password()));
        try {
            var other = new Client();
            assertEquals(200, other.login("t05-isolation", password()).statusCode());
            var list = other.get("/api/v1/skills");
            assertEquals(200, list.statusCode());
            assertEquals(0, JSON.readTree(list.body()).get("items").size()); // no foreign skills visible
            error(other.get("/api/v1/skills/" + skill + "/versions"), 404);
            error(other.write("PUT", "/api/v1/skill-versions/" + v, "{\"config\":" + configBody() + "}", UUID.randomUUID().toString()), 404);
        } finally { admin("UPDATE editorial.app_user SET enabled=false WHERE username='t05-isolation'"); }
    }

    @Test @Order(12) void anonymousAndForgedRejected() throws Exception {
        var anon = new Client();
        error(anon.get("/api/v1/skills"), 401);
        // forged actor fields are ignored by the security layer; a bogus login fails
        error(new Client().call("POST", "/api/v1/auth/login", JSON.writeValueAsString(Map.of("username", username(), "password", password(), "actorId", owner().toString())), Map.of("Origin", ORIGIN)), 422);
    }

    @Test @Order(13) void auditAppendOnlyAndSanitized() throws Exception {
        var c = signed();
        UUID skill = createSkill(c, "AuditSkill");
        UUID v = createVersion(c, skill, null, configBody(), 201);
        c.write("POST", "/api/v1/skill-versions/" + v + "/publish", "{\"changeLog\":\"p\"}", UUID.randomUUID().toString());
        assertEquals(1, db.queryForObject("SELECT count(*) FROM editorial.audit_log WHERE action='SKILL_CREATED' AND entity_type='SKILL' AND entity_id=?", Integer.class, skill));
        assertEquals(1, db.queryForObject("SELECT count(*) FROM editorial.audit_log WHERE action='SKILL_VERSION_CREATED' AND entity_id=?", Integer.class, v));
        assertEquals(1, db.queryForObject("SELECT count(*) FROM editorial.audit_log WHERE action='SKILL_VERSION_PUBLISHED' AND entity_id=?", Integer.class, v));
        String leak = adminQuery("SELECT string_agg(coalesce(action,'')||coalesce(before_hash::text,'')||coalesce(after_hash::text,'')||coalesce(entity_type,''),' ') FROM editorial.audit_log");
        assertFalse(leak.contains("测试技能配置")); // config content never logged
    }

    @Test @Order(14) void snapshotPreservedAfterPublishAndRetire() throws Exception {
        var c = signed();
        UUID skill = createSkill(c, "SnapshotSkill");
        UUID v1 = createVersion(c, skill, null, configBody(), 201);
        c.write("POST", "/api/v1/skill-versions/" + v1 + "/publish", "{\"changeLog\":\"p\"}", UUID.randomUUID().toString());
        String v1hash = db.queryForObject("SELECT rules_hash FROM editorial.editorial_skill_version WHERE id=?", String.class, v1);
        // publish a newer version, then retire it
        UUID v2 = createVersion(c, skill, v1.toString(), configBody(), 201);
        c.write("POST", "/api/v1/skill-versions/" + v2 + "/publish", "{\"changeLog\":\"p\"}", UUID.randomUUID().toString());
        c.write("POST", "/api/v1/skill-versions/" + v2 + "/retire", "{\"reason\":\"r\"}", UUID.randomUUID().toString());
        // historical snapshot unchanged
        var snapshot = skillSnapshotPort.read(ActorContext.forWorker(system(), owner(), UUID.randomUUID()), v1);
        assertEquals(v1hash, snapshot.rulesHash());
        assertEquals("1.0.0", snapshot.version());
    }

    @Test @Order(15) void draftSnapshotIsNotPublishedAndPortErrors() throws Exception {
        var c = signed();
        UUID skill = createSkill(c, "DraftSnapshotSkill");
        UUID v = createVersion(c, skill, null, configBody(), 201); // DRAFT
        var actor = ActorContext.forWorker(system(), owner(), UUID.randomUUID());
        assertEquals(409, assertThrows(com.example.editorial.shared.PublicFailure.class,
                () -> skillSnapshotPort.read(actor, v)).status());
        assertEquals(404, assertThrows(com.example.editorial.shared.PublicFailure.class,
                () -> policySnapshotPort.read(UUID.randomUUID())).status());
    }

    @Test @Order(16) void eventIdempotencyKeyIsStable() throws Exception {
        var c = signed();
        UUID skill = createSkill(c, "EventSkill");
        UUID v = createVersion(c, skill, null, configBody(), 201);
        int before = events.events().size();
        c.write("POST", "/api/v1/skill-versions/" + v + "/publish", "{\"changeLog\":\"p\"}", UUID.randomUUID().toString());
        assertEquals(before + 1, events.events().size());
        var evt = events.events().get(events.events().size() - 1);
        assertEquals(ConfigChangeEvent.key(v, "PUBLISH"), evt.idempotencyKey());
        assertEquals(skill, evt.skillId());
    }

    @Test @Order(17) void runtimeRoleHasNoDeleteAndPublishedImmutableInDb() throws Exception {
        // runtime role has no UPDATE on published content thanks to the DB trigger; no DELETE/TRUNCATE at all
        for (String sql : List.of("DELETE FROM editorial.editorial_skill", "TRUNCATE editorial.policy_version")) {
            assertThrows(org.springframework.dao.DataAccessException.class, () -> db.execute(sql));
        }
        UUID v = db.queryForObject("SELECT active_version_id FROM editorial.editorial_skill WHERE code='WechatEditorialSkill'", UUID.class);
        String before = db.queryForObject("SELECT rules_hash FROM editorial.editorial_skill_version WHERE id=?", String.class, v);
        // direct UPDATE of published config must be rejected by the immutability trigger (executed as runtime)
        assertThrows(org.springframework.dao.DataAccessException.class, () -> db.update(
                "UPDATE editorial.editorial_skill_version SET rules_hash=repeat('0',64) WHERE id=?", v));
        assertEquals(before, db.queryForObject("SELECT rules_hash FROM editorial.editorial_skill_version WHERE id=?", String.class, v));
    }
    // Independent review cases, appended only to the isolated copy of the author's test fixture.
    @Test @Order(101) void reviewWriterSchemaMustResolveAgainstApprovedDefinitions() throws Exception {
        var defs = JSON.readTree(new org.springframework.core.io.ClassPathResource("skills/editorial.schema.json").getInputStream()).path("$defs");
        var p = prompts.getPublished("Writer");
        String ref = p.outputSchema().path("$ref").asText();
        assertTrue(defs.has(ref.substring("#/$defs/".length())), "Published Writer has unresolved schema reference: " + ref);
    }

    @Test @Order(102) void reviewUnknownOutputSchemaBindingMustBeRejected() throws Exception {
        var c = signed();
        UUID skill = createSkill(c, "ReviewInvalidOutputSchema");
        ObjectNode cfg = (ObjectNode) JSON.readTree(configBody());
        ((ObjectNode) cfg.path("promptBindings").get(0)).put("outputSchema", "NonexistentOutputSchema");
        var response = c.write("POST", "/api/v1/skills/" + skill + "/versions", "{\"config\":" + cfg + "}", UUID.randomUUID().toString());
        if (response.statusCode() == 201) {
            String id = JSON.readTree(response.body()).path("id").asText();
            var published = c.write("POST", "/api/v1/skill-versions/" + id + "/publish", "{\"changeLog\":\"review\"}", UUID.randomUUID().toString());
            assertEquals(422, published.statusCode(), "Unknown output schema created with 201 and published: " + published.body());
        } else assertEquals(422, response.statusCode(), response.body());
    }

    @Test @Order(103) void reviewDraftStatusFilterMustReturnDraftSkill() throws Exception {
        var c = signed();
        UUID skill = createSkill(c, "ReviewDraftFilter");
        createVersion(c, skill, null, configBody(), 201);
        var response = c.get("/api/v1/skills?status=DRAFT&limit=100");
        assertEquals(200, response.statusCode(), response.body());
        boolean found = false;
        for (var n : JSON.readTree(response.body()).path("items")) if (n.path("id").asText().equals(skill.toString())) found = true;
        assertTrue(found, "DRAFT skill absent from DRAFT listing: " + response.body());
    }

    @Test @Order(104) void reviewCursorMustBindStatusFilter() throws Exception {
        var c = signed();
        var response = c.get("/api/v1/skills?limit=1");
        assertEquals(200, response.statusCode());
        String cursor = JSON.readTree(response.body()).path("nextCursor").asText();
        assertFalse(cursor.isBlank());
        var sameFilter = c.get("/api/v1/skills?limit=1&cursor=" + java.net.URLEncoder.encode(cursor, StandardCharsets.UTF_8));
        assertEquals(200, sameFilter.statusCode(), "Server's own cursor fails unchanged query: " + sameFilter.body());
        var changedFilter = c.get("/api/v1/skills?status=PUBLISHED&limit=1&cursor=" + java.net.URLEncoder.encode(cursor, StandardCharsets.UTF_8));
        assertEquals(422, changedFilter.statusCode(), "Cursor accepted under a different filter: " + changedFilter.body());
    }

    @Test @Order(105) void reviewPublishedPrimaryKeysMustBeImmutable() throws Exception {
        var failures = new ArrayList<String>();
        for (String table : List.of("editorial_skill_version", "policy_version", "prompt_version")) {
            UUID oldId = db.queryForObject("SELECT id FROM editorial." + table + " WHERE status='PUBLISHED' LIMIT 1", UUID.class);
            try (Connection conn = DriverManager.getConnection(System.getenv("DB_URL"), "editorial_runtime", System.getenv("DB_RUNTIME_PASSWORD"))) {
                conn.setAutoCommit(false);
                try (var stmt = conn.prepareStatement("UPDATE editorial." + table + " SET id=? WHERE id=?")) {
                    stmt.setObject(1, UUID.randomUUID()); stmt.setObject(2, oldId);
                    try {
                        int count = stmt.executeUpdate();
                        if (count == 1) failures.add(table + ": runtime changed published id");
                    } catch (java.sql.SQLException ex) {
                        assertTrue(List.of("P0001", "42501", "23503").contains(ex.getSQLState()), "Unexpected rejection: " + ex.getSQLState());
                    }
                } finally { conn.rollback(); }
            }
        }
        assertTrue(failures.isEmpty(), failures.toString());
    }

    @Test @Order(106) void reviewPromptLatestUsesSemanticVersion() throws Exception {
        var actor = ActorContext.forWorker(system(), owner(), UUID.randomUUID());
        var schema = JSON.createObjectNode().put("type", "object");
        prompts.seed(actor, "ReviewSemverAgent", "1.0.9", "system", "user", schema);
        prompts.seed(actor, "ReviewSemverAgent", "1.0.10", "system", "user", schema);
        policies.seed(actor, PolicyType.COST, "1.0.9", schema);
        policies.seed(actor, PolicyType.COST, "1.0.10", schema);
        assertAll(
            () -> assertEquals("1.0.10", prompts.getPublished("ReviewSemverAgent").version(), "Prompt semver"),
            () -> assertEquals("1.0.10", policies.getPublished(PolicyType.COST).version(), "Policy semver"));
    }
}

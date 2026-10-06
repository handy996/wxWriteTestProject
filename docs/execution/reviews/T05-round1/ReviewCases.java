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

    // ==================== ROUND-4 INDEPENDENT PROBE (reviewer: T08 round 4) ====================
    // Appended only into an isolated copy of backend/src (never into the repository), to answer the round-4
    // dispatch item 1: is the provider-wide ceiling really measured across models? Delivered shape is provider=2
    // with ONE model entry at 5; these cases set BOTH model entries loose, interleave the calls, spread them over
    // articles and owners, and mix a dotted model id with a plain one. Every assertion states the STRICT
    // expectation, so a放行 shows up as a red case with the actual value in the message.

    private static final UUID OWNER2 = UUID.fromString("aaaaaaaa-0000-4000-8000-000000000002");

    private UUID articleOwned(UUID owner, String budgetLimit) {
        execute("INSERT INTO editorial.app_user(id,username,display_name,actor_type,password_hash,enabled) VALUES ("
                + "'" + owner + "','r4-owner2','R4 Owner Two','OWNER','x',true) ON CONFLICT (id) DO NOTHING");
        UUID id = UUID.randomUUID();
        adminUpdate("INSERT INTO editorial.article_job"
                        + "(id,owner_id,name,skill_version_id,target_length,budget_limit,currency,status,summary,"
                        + "style_snapshot,original_rights_basis,created_by,updated_by) VALUES (?,?,?,'" + SKILL_VERSION
                        + "',1500,?::numeric,'USD',?,?::jsonb,'{}'::jsonb,"
                        + "'[{\"basis\":\"OWNER_AUTHORIZED\",\"note\":\"r4 probe\"}]'::jsonb,?,?)",
                id, owner, "r4-article", budgetLimit, "ANALYZING",
                "{\"id\":\"" + id + "\",\"budget\":\"" + budgetLimit + "\"}", owner, owner);
        return id;
    }

    private UUID executionFor(UUID owner, UUID article) {
        UUID id = UUID.randomUUID();
        scopes.put(id, new CostPorts.Executions.Scope(id, CostPorts.Executions.Kind.AGENT, article, owner, null, null));
        return id;
    }

    private ActorContext actor(UUID owner) {
        return ActorContext.forWorker(owner, owner, UUID.randomUUID());
    }

    /** One hold on a chosen model of the configured provider, placed on a chosen article/owner. */
    private BudgetService.Request hold(UUID article, String model, UUID owner) {
        return new BudgetService.Request(article, executionFor(owner, article), PROVIDER, model,
                Capability.GENERATION, new Usage(0, 0, 0, null, 1, 0), Money.ZERO, true, false, UUID.randomUUID());
    }

    private java.util.Map<String, BudgetPolicy.ProviderQuota> twoLooseModels(int providerConcurrent) {
        return java.util.Map.of(
                BudgetPolicy.scope(PROVIDER, null), new BudgetPolicy.ProviderQuota(providerConcurrent, 30),
                BudgetPolicy.scope(PROVIDER, MODEL), new BudgetPolicy.ProviderQuota(5, 30),
                BudgetPolicy.scope(PROVIDER, "second-model"), new BudgetPolicy.ProviderQuota(5, 30));
    }

    private PublicFailure expectQuotaRefusal(java.util.function.Supplier<Reservation> call, String which) {
        PublicFailure refused = assertThrows(PublicFailure.class, call::get,
                () -> which + " was ADMITTED: the provider-wide ceiling did not bind this window");
        assertEquals(429, refused.status(), which + " refused with the wrong status: " + refused.code());
        assertEquals("PROVIDER_QUOTA_EXCEEDED", refused.code(), which + " refused for the wrong reason");
        return refused;
    }

    @Test
    @DisplayName("R4 probe: provider=2 with BOTH model entries at 5 — three calls on one model")
    void r4ProbeThreeCallsOnOneModelWithBothEntriesLoose() {
        policy(wideCaps(), "20.000000", 80, twoLooseModels(2));
        publish(PROVIDER, "second-model", generation());
        UUID article = article("10.000000");
        assertNotNull(budget.reserve(actor(), hold(article, MODEL, OWNER)));
        assertNotNull(budget.reserve(actor(), hold(article, MODEL, OWNER)));
        expectQuotaRefusal(() -> budget.reserve(actor(), hold(article, MODEL, OWNER)), "third call on mock-gpt");
        assertEquals(2, holds(), "the refusal must book nothing");
    }

    @Test
    @DisplayName("R4 probe: provider=2, both models 5 — interleaved A, B, A")
    void r4ProbeInterleavedAthenBthenA() {
        policy(wideCaps(), "20.000000", 80, twoLooseModels(2));
        publish(PROVIDER, "second-model", generation());
        UUID article = article("10.000000");
        assertNotNull(budget.reserve(actor(), hold(article, MODEL, OWNER)), "A admitted");
        assertNotNull(budget.reserve(actor(), hold(article, "second-model", OWNER)), "B admitted");
        expectQuotaRefusal(() -> budget.reserve(actor(), hold(article, MODEL, OWNER)), "A again (third live hold)");
        expectQuotaRefusal(() -> budget.reserve(actor(), hold(article, "second-model", OWNER)),
                "B again: the provider window is already at two");
        assertEquals(2, holds(), "two refusals booked nothing");
    }

    @Test
    @DisplayName("R4 probe: provider=2, both models 5 — interleaved A, B, B, A")
    void r4ProbeInterleavedAABB() {
        policy(wideCaps(), "20.000000", 80, twoLooseModels(2));
        publish(PROVIDER, "second-model", generation());
        UUID article = article("10.000000");
        assertNotNull(budget.reserve(actor(), hold(article, MODEL, OWNER)));
        assertNotNull(budget.reserve(actor(), hold(article, "second-model", OWNER)));
        expectQuotaRefusal(() -> budget.reserve(actor(), hold(article, "second-model", OWNER)), "third hold (B)");
        expectQuotaRefusal(() -> budget.reserve(actor(), hold(article, MODEL, OWNER)), "fourth attempt (A)");
        assertEquals(2, holds());
    }

    @Test
    @DisplayName("R4 probe: provider-wide window spans articles of one owner")
    void r4ProbeProviderWindowSpansArticles() {
        policy(wideCaps(), "20.000000", 80,
                java.util.Map.of(BudgetPolicy.scope(PROVIDER, null), new BudgetPolicy.ProviderQuota(2, 30)));
        UUID first = article("10.000000");
        UUID second = article("10.000000");
        assertNotNull(budget.reserve(actor(), hold(first, MODEL, OWNER)));
        assertNotNull(budget.reserve(actor(), hold(second, MODEL, OWNER)));
        expectQuotaRefusal(() -> budget.reserve(actor(), hold(first, MODEL, OWNER)),
                "third live hold of the provider across two articles");
        assertEquals(2, holds());
    }

    @Test
    @DisplayName("R4 probe: a dotted model id shares the provider window with a plain model id")
    void r4ProbeDottedAndPlainShareOneProviderWindow() {
        policy(wideCaps(), "20.000000", 80,
                java.util.Map.of(BudgetPolicy.scope(PROVIDER, null), new BudgetPolicy.ProviderQuota(2, 30)));
        publish(PROVIDER, "gpt-4.1", generation());
        UUID article = article("10.000000");
        assertNotNull(budget.reserve(actor(), hold(article, "gpt-4.1", OWNER)), "dotted id admitted");
        assertNotNull(budget.reserve(actor(), hold(article, MODEL, OWNER)), "plain id admitted");
        expectQuotaRefusal(() -> budget.reserve(actor(), hold(article, "gpt-4.1", OWNER)),
                "third live hold: dotted rows and plain rows must fill ONE provider window");
        assertEquals(2, holds());
    }

    @Test
    @DisplayName("R4 probe: provider calls-per-day counts across models")
    void r4ProbeProviderDayCountIsCrossModel() {
        policy(wideCaps(), "20.000000", 80, java.util.Map.of(
                BudgetPolicy.scope(PROVIDER, null), new BudgetPolicy.ProviderQuota(10, 2),
                BudgetPolicy.scope(PROVIDER, MODEL), new BudgetPolicy.ProviderQuota(30, 30),
                BudgetPolicy.scope(PROVIDER, "second-model"), new BudgetPolicy.ProviderQuota(30, 30)));
        publish(PROVIDER, "second-model", generation());
        UUID article = article("10.000000");
        assertNotNull(budget.reserve(actor(), hold(article, MODEL, OWNER)));
        assertNotNull(budget.reserve(actor(), hold(article, "second-model", OWNER)));
        expectQuotaRefusal(() -> budget.reserve(actor(), hold(article, MODEL, OWNER)),
                "third call of the day: the provider-wide day count is 2 and it spans models");
        assertEquals(2, holds());
    }

    @Test
    @DisplayName("R4 probe: is the provider window partitioned per owner? (documents the real semantics)")
    void r4ProbeProviderWindowOwnerPartition() {
        policy(wideCaps(), "20.000000", 80,
                java.util.Map.of(BudgetPolicy.scope(PROVIDER, null), new BudgetPolicy.ProviderQuota(2, 30)));
        UUID mine = article("10.000000");
        UUID theirs = articleOwned(OWNER2, "10.000000");
        assertNotNull(budget.reserve(actor(), hold(mine, MODEL, OWNER)), "owner one, hold one");
        assertNotNull(budget.reserve(actor(), hold(mine, MODEL, OWNER)), "owner one, hold two");
        assertNotNull(budget.reserve(actor(OWNER2), hold(theirs, MODEL, OWNER2)), "owner two, hold one");
        assertNotNull(budget.reserve(actor(OWNER2), hold(theirs, MODEL, OWNER2)), "owner two, hold two");
        int live = holds();
        System.out.println("R4-OWNER-PARTITION live holds on provider=" + PROVIDER
                + " with maxConcurrent=2 -> " + live);
        expectQuotaRefusal(() -> budget.reserve(actor(), hold(mine, MODEL, OWNER)),
                "owner one third hold (window is per owner, so this must still refuse)");
        assertEquals(live, holds(), "the refusal books nothing");
    }
    // ==================== END ROUND-4 INDEPENDENT PROBE ====================

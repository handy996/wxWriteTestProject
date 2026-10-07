package com.example.editorial.cost;

import static org.junit.jupiter.api.Assertions.*;

import com.example.editorial.audit.AuditSink;
import com.example.editorial.audit.JdbcAuditSink;
import com.example.editorial.shared.ActorContext;
import com.example.editorial.shared.CanonicalRequest;
import com.example.editorial.shared.PublicFailure;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.SQLException;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.stream.StreamSupport;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.junit.jupiter.api.function.Executable;
import org.postgresql.ds.PGSimpleDataSource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * T08 against a real PostgreSQL 17 cluster with the draft migration applied. Everything the task card calls
 * atomic — the last-balance race, idempotent settlement, the retained UNKNOWN hold, the count caps, and the
 * database guards that must hold even for a writer that skipped the service — is asserted here on the single
 * table {@code cost_ledger} this domain owns.
 *
 * <p>Runs only when {@code T08_REAL_PG=true}; the harness provisions the cluster, applies V1–V4 plus
 * {@code tests/engineering/T08/migration-draft.sql} and creates the roles. Article and price fixtures are seeded
 * on the admin connection with {@code session_replication_role = replica}: seeding a fully valid T06 article
 * projection is T06's own coverage, and T08 must not depend on it to exercise its ledger. Guard tests switch
 * that session back to {@code origin} so the cost triggers really fire; the runtime connection is never in
 * replica mode, so its rows always face the ledger guards.</p>
 */
@EnabledIfEnvironmentVariable(named = "T08_REAL_PG", matches = "true")
class T08PostgresTest {
    private static final ObjectMapper JSON = new ObjectMapper();
    private static final UUID OWNER = UUID.fromString("aaaaaaaa-0000-4000-8000-000000000001");
    private static final UUID SKILL = UUID.fromString("bbbbbbbb-0000-4000-8000-000000000001");
    private static final UUID SKILL_VERSION = UUID.fromString("bbbbbbbb-0000-4000-8000-000000000002");
    private static final String PROVIDER = "mock-provider";
    private static final String MODEL = "mock-gpt";
    private static final Money IMAGE_UNIT = Money.of("1.000000");

    private static Connection admin;
    private static JdbcTemplate runtime;
    private static DataSourceTransactionManager manager;
    private static TransactionTemplate tx;
    private static AuditSink sink;

    private final Map<UUID, CostPorts.Executions.Scope> scopes = new ConcurrentHashMap<>();
    private final List<BudgetAlert> emitted = new CopyOnWriteArrayList<>();
    private final List<String> audited = new CopyOnWriteArrayList<>();
    /** What the service actually handed the audit port for each hash column, recorded verbatim. */
    private final List<String> auditPayloads = new CopyOnWriteArrayList<>();
    /** Audit port the services are bound to: the recording stub, swapped for the database mirror by one case. */
    private CostPorts.Audit auditPort = recordingAudit();
    private BudgetPolicy activePolicy;
    private CostLedger ledger;
    private BudgetService budget;
    private UsageService usage;

    // ------------------------------------------------------------------ fixture

    @BeforeAll
    static void connect() throws Exception {
        String url = System.getenv().getOrDefault("T08_ADMIN_URL", "jdbc:postgresql://127.0.0.1:55432/editorial");
        admin = DriverManager.getConnection(url, System.getenv().getOrDefault("T08_ADMIN_USER", "probe_admin"),
                System.getenv().getOrDefault("T08_ADMIN_PASSWORD", ""));
        PGSimpleDataSource dataSource = new PGSimpleDataSource();
        dataSource.setUrl(url);
        dataSource.setUser("editorial_runtime");
        dataSource.setPassword(System.getenv().getOrDefault("T08_RUNTIME_PASSWORD", ""));
        runtime = new JdbcTemplate(dataSource);
        manager = new DataSourceTransactionManager(dataSource);
        tx = new TransactionTemplate(manager);
        sink = new JdbcAuditSink(runtime, manager);
        execute("SET session_replication_role = replica");
        execute("INSERT INTO editorial.app_user(id,username,display_name,actor_type,password_hash,enabled) VALUES ("
                + "'" + OWNER + "','t08-owner','T08 Owner','OWNER','x',true) ON CONFLICT (id) DO NOTHING");
        // article_job requires a skill version; one shared fixture row is enough for the cost tests.
        execute("INSERT INTO editorial.editorial_skill(id,code,name,owner_id,created_by,created_at,updated_at,"
                + "lock_version) VALUES ('" + SKILL + "','t08-skill','T08 Skill','" + OWNER + "','" + OWNER
                + "',now(),now(),1) ON CONFLICT (id) DO NOTHING");
        execute("INSERT INTO editorial.editorial_skill_version(id,skill_id,version,config,rules_hash,schema_version,"
                + "status,created_by,created_at,updated_at,lock_version) VALUES ('" + SKILL_VERSION + "','" + SKILL
                + "','1.0.0','{}'::jsonb,'" + "0".repeat(64) + "','editorial.skill/1','PUBLISHED','" + OWNER
                + "',now(),now(),1) ON CONFLICT (id) DO NOTHING");
    }

    @AfterAll
    static void closeAdmin() throws Exception {
        execute("SET session_replication_role = DEFAULT");
        admin.close();
    }

    /** Admin statements run in fixture mode by default, so seeding never trips another domain's triggers. */
    private static void execute(String sql) {
        try (var statement = admin.createStatement()) {
            statement.execute(sql);
        } catch (SQLException seed) {
            throw new IllegalStateException(seed);
        }
    }

    private static void adminUpdate(String sql, Object... args) {
        try (PreparedStatement statement = admin.prepareStatement(sql)) {
            for (int i = 0; i < args.length; i++) statement.setObject(i + 1, args[i]);
            statement.executeUpdate();
        } catch (SQLException seed) {
            throw new IllegalStateException(seed);
        }
    }

    private static void originMode() {
        execute("SET session_replication_role = origin");
    }

    /**
     * Runs a statement that must fail and returns the underlying SQL error. The runtime connection goes through
     * JdbcTemplate, which rethrows the driver's SQLException wrapped, so the cause chain is walked here.
     */
    private static SQLException sqlFailure(Executable statement) {
        Throwable thrown = assertThrows(Throwable.class, statement);
        for (Throwable cursor = thrown; cursor != null; cursor = cursor.getCause())
            if (cursor instanceof SQLException error) return error;
        throw new AssertionError("no SQLException behind " + thrown, thrown);
    }

    @BeforeEach
    void setUp() {
        execute("SET session_replication_role = replica");
        execute("DELETE FROM editorial.cost_ledger");
        execute("DELETE FROM editorial.cost_pricing_version");
        execute("DELETE FROM editorial.article_job");
        execute("DELETE FROM editorial.audit_log");
        auditPort = recordingAudit();
        scopes.clear();
        emitted.clear();
        audited.clear();
        auditPayloads.clear();
        policy(Map.of(), "20.000000", 80);
        publish(PROVIDER, MODEL, text() + "," + generation() + "," + search());
    }

    private static String text() {
        return entry("TEXT", "2.500000000", "1.000000000", "10.000000000", "99.000000000", "0.000000", "0.000000",
                "0.000000", false);
    }

    private static String generation() {
        return entry("GENERATION", "0.000000000", "0.000000000", "0.000000000", "0.000000000", "0.000000",
                "1.000000000", "0.000000", false);
    }

    private static String search() {
        return entry("SEARCH", "0.000000000", "0.000000000", "0.000000000", "0.000000000", "0.000000", "0.000000",
                "0.000000", false);
    }

    private static String entry(String capability, String input, String cached, String output, String reasoning,
                                String search, String image, String other, boolean separate) {
        return "{\"capability\":\"" + capability + "\",\"inputPerMillion\":\"" + input
                + "\",\"cachedInputPerMillion\":\"" + cached + "\",\"outputPerMillion\":\"" + output
                + "\",\"reasoningPerMillion\":\"" + reasoning + "\",\"searchPerCall\":\"" + search
                + "\",\"imagePerUnit\":\"" + image + "\",\"otherPerCall\":\"" + other
                + "\",\"reasoningBilledSeparately\":" + separate + "}";
    }

    private static String rules(String entries) {
        return "{\"schemaVersion\":\"editorial.pricing/1\",\"currency\":\"USD\",\"rounding\":\"CEILING\","
                + "\"entries\":[" + entries + "]}";
    }

    /** Operator path: a PUBLISHED price version is written by the admin role; the runtime role holds no grant. */
    private static void publish(String provider, String model, String entries) {
        publishAt(provider, model, "1.0.0", entries);
    }

    private static void publishAt(String provider, String model, String version, String entries) {
        String document = rules(entries);
        String hash = CanonicalRequest.digest(CanonicalRequest.canonical(PricingRules.read(document)));
        adminUpdate("INSERT INTO editorial.cost_pricing_version"
                + "(id,provider,model,version,currency,rules,hash,status,created_by,updated_by) VALUES"
                + "(?,?,?,?,?,?::jsonb,?,'PUBLISHED',?,?)",
                UUID.randomUUID(), provider, model, version, "USD", document, hash, OWNER, OWNER);
    }

    private static Money money(String value) { return Money.of(value); }

    /** Rebuilds the service with a chosen daily ceiling, count caps, alert line and provider quotas. */
    private void policy(Map<BudgetPolicy.Counter, Long> caps, String daily, int alertPercent) {
        policy(caps, daily, alertPercent, Map.of());
    }

    private void policy(Map<BudgetPolicy.Counter, Long> caps, String daily, int alertPercent,
                        Map<String, BudgetPolicy.ProviderQuota> providers) {
        Map<BudgetPolicy.Counter, Long> all = new EnumMap<>(BudgetPolicy.Counter.class);
        all.put(BudgetPolicy.Counter.CALLS, 1000L);
        all.put(BudgetPolicy.Counter.SEARCH_QUERY, 30L);
        all.put(BudgetPolicy.Counter.MODEL_OUTPUT_TOKENS, 40_000L);
        all.put(BudgetPolicy.Counter.CLAIM_QUERY, 3L);
        all.put(BudgetPolicy.Counter.AUTO_EDIT_LOOP, 1L);
        all.put(BudgetPolicy.Counter.IMAGE_GENERATION_SLOT, 2L);
        all.put(BudgetPolicy.Counter.IMAGE_GENERATION_ARTICLE, 4L);
        all.putAll(caps);
        BudgetPolicy used = new BudgetPolicy(money(daily), Map.copyOf(all), providers, alertPercent, 30);
        service(used);
    }

    /** Binds the services to one exact policy, so a deliberate configuration gap can be exercised. */
    private void service(BudgetPolicy used) {
        activePolicy = used;
        ledger = new CostLedger(runtime, JSON);
        budget = new BudgetService(ledger, tx, used, (actor, article, execution) -> {
            CostPorts.Executions.Scope scope = scopes.get(execution);
            if (scope == null) throw new PublicFailure(404, "EXECUTION_NOT_FOUND");
            return scope;
        }, auditPort, (actor, alert) -> emitted.add(alert));
        usage = new UsageService(ledger, JSON, used, "t08-cursor-secret-value-for-tests-0001");
    }

    /** Default port: remembers what the service asked to be audited, so ordering and payload stay assertable. */
    private CostPorts.Audit recordingAudit() {
        return (actor, action, article, entity, before, after) -> {
            audited.add(action + "|" + entity);
            auditPayloads.add(action + "|" + before + "|" + after);
        };
    }

    /**
     * Port bound to the production audit writer. {@code bootstrap/CostIntegration} is the authoritative guard and
     * {@code bootstrap/CostAuditWiringTest} tests it; this mirror exists only to reach the same real
     * {@code audit.JdbcAuditSink} INSERT from the cost side, because {@code audit_log.before_hash}/{@code
     * after_hash} are {@code char(64)} with a {@code ^[a-f0-9]{64}$} CHECK and {@code detail} is pinned to
     * {@code '{}'}: a money string there is a runtime 23514 inside a live request. The rejected value is never
     * echoed, since the message can reach a log.
     */
    private CostPorts.Audit realAuditSinkPort() {
        return (actor, action, article, entity, beforeHash, afterHash) -> {
            auditPayloads.add(action + "|" + beforeHash + "|" + afterHash);
            for (String hash : new String[] {beforeHash, afterHash})
                if (hash != null && !hash.matches("^[a-f0-9]{64}$"))
                    throw new IllegalStateException("COST_AUDIT: hash field must be null or 64 lowercase hex, got "
                            + hash.length() + " characters");
            sink.append(actor, new AuditSink.Event(action, article, "COST", entity, beforeHash, afterHash));
        };
    }

    private static Map<BudgetPolicy.Counter, Long> wideCaps() {
        Map<BudgetPolicy.Counter, Long> caps = new EnumMap<>(BudgetPolicy.Counter.class);
        for (BudgetPolicy.Counter counter : BudgetPolicy.Counter.values()) caps.put(counter, 1000L);
        return caps;
    }

    private UUID article(String budgetLimit) { return article(budgetLimit, "ANALYZING"); }

    private UUID article(String budgetLimit, String status) {
        UUID id = UUID.randomUUID();
        adminUpdate("INSERT INTO editorial.article_job"
                + "(id,owner_id,name,skill_version_id,target_length,budget_limit,currency,status,summary,"
                + "style_snapshot,original_rights_basis,created_by,updated_by) VALUES (?,?,?,'" + SKILL_VERSION
                + "',1500,?::numeric,'USD',?,?::jsonb,'{}'::jsonb,"
                + "'[{\"basis\":\"OWNER_AUTHORIZED\",\"note\":\"t08 fixture\"}]'::jsonb,?,?)",
                id, OWNER, "t08-article", budgetLimit, status,
                "{\"id\":\"" + id + "\",\"budget\":\"" + budgetLimit + "\"}", OWNER, OWNER);
        return id;
    }

    private UUID execution(UUID article, UUID claim, UUID slot) {
        UUID id = UUID.randomUUID();
        scopes.put(id, new CostPorts.Executions.Scope(id, CostPorts.Executions.Kind.AGENT, article, OWNER, claim, slot));
        return id;
    }

    private ActorContext actor() { return ActorContext.forWorker(OWNER, OWNER, UUID.randomUUID()); }

    private BudgetService.Request image(UUID article, UUID execution, UUID key, int units) {
        return new BudgetService.Request(article, execution, PROVIDER, MODEL, Capability.GENERATION,
                new Usage(0, 0, 0, null, units, 0), Money.ZERO, true, false, key);
    }

    private BudgetService.Request text(UUID article, UUID execution, UUID key, Usage used, boolean loop) {
        return new BudgetService.Request(article, execution, PROVIDER, MODEL, Capability.TEXT, used, Money.ZERO,
                true, loop, key);
    }

    private BudgetService.Request searchCall(UUID article, UUID execution, UUID key, int queries) {
        return new BudgetService.Request(article, execution, PROVIDER, MODEL, Capability.SEARCH,
                new Usage(0, 0, 0, null, 0, queries), Money.ZERO, true, false, key);
    }

    private static Settlement settle(Reservation reservation, ReservationStatus result, Money amount) {
        return Settlement.of(JSON, reservation.id(), "req-" + result.name(), amount, result, UUID.randomUUID(), null);
    }

    private int rows() {
        return runtime.queryForObject("SELECT count(*) FROM editorial.cost_ledger", Integer.class).intValue();
    }

    private int holds() {
        return runtime.queryForObject("SELECT count(*) FROM editorial.cost_ledger WHERE status='RESERVED'",
                Integer.class).intValue();
    }

    // ------------------------------------------------------------------ atomic pre-occupancy

    @Test
    @DisplayName("AC-28: the last of a balance is won by exactly one task")
    void lastBalanceSingleWinner() throws Exception {
        UUID article = article("1.000000");
        assertTrue(ledger.occupancy("l.article_id=?", article).occupied().isZero());
        UUID one = execution(article, null, null), two = execution(article, null, null);
        UUID keyOne = UUID.randomUUID(), keyTwo = UUID.randomUUID();
        ExecutorService pool = Executors.newFixedThreadPool(2);
        CountDownLatch ready = new CountDownLatch(2), start = new CountDownLatch(1);
        List<String> outcomes;
        try {
            Future<String> first = pool.submit(() -> attempt(article, one, keyOne));
            Future<String> second = pool.submit(() -> attempt(article, two, keyTwo));
            ready.await(10, TimeUnit.SECONDS);
            start.countDown();
            outcomes = List.of(first.get(30, TimeUnit.SECONDS), second.get(30, TimeUnit.SECONDS));
        } finally {
            pool.shutdownNow();
        }
        long winners = outcomes.stream().filter(outcome -> outcome.startsWith("reserved")).count();
        assertEquals(1, winners, "exactly one caller may take the last unit: " + outcomes);
        assertTrue(outcomes.contains("BUDGET_EXCEEDED"), "the other stops on the budget: " + outcomes);
        CostPorts.Occupancy after = ledger.occupancy("l.article_id=?", article);
        assertEquals("1.000000", after.reserved().text(), "holds never exceed the user budget");
        assertEquals(1, rows());
        assertTrue(emitted.stream().anyMatch(a -> a.code() == BudgetAlert.Code.ARTICLE_BUDGET_EXCEEDED),
                "the refusal is reported as budget alert data");
        assertEquals(1, audited.stream().filter(a -> a.startsWith("COST_RESERVED")).count());
    }

    private String attempt(UUID article, UUID execution, UUID key) {
        try {
            return "reserved:" + budget.reserve(actor(), image(article, execution, key, 1)).id();
        } catch (PublicFailure refused) {
            return refused.code();
        }
    }

    @Test
    @DisplayName("The database repeats the ceiling for a writer that skipped the lock")
    void admissionCeilingIsADatabaseRule() {
        UUID article = article("1.000000");
        assertNotNull(budget.reserve(actor(), image(article, execution(article, null, null), UUID.randomUUID(), 1)));
        SQLException refused = sqlFailure(() -> runtime.update(
                "INSERT INTO editorial.cost_ledger (id,article_id,owner_id,execution_id,execution_kind,"
                        + "reservation_id,kind,status,amount,currency,pricing_version,pricing_hash,idempotency_key,"
                        + "provider,model,capability,bucket_day,usage,counters,created_by,updated_by,trace_id) "
                        + "SELECT k.g,?,?,'00000000-0000-4000-8000-000000000009','AGENT',k.g,'ESTIMATED','RESERVED',"
                        + "0.5,'USD',p.id,p.hash,k.g,?,?,'GENERATION',current_date,'{}'::jsonb,'{}'::jsonb,?,?,? "
                        + "FROM (SELECT gen_random_uuid() AS g) k, editorial.cost_pricing_version p "
                        + "WHERE p.status='PUBLISHED' LIMIT 1",
                article, OWNER, PROVIDER, MODEL, OWNER, OWNER, UUID.randomUUID()));
        assertEquals("23514", refused.getSQLState());
        assertTrue(refused.getMessage().contains("cost budget ceiling"), refused.getMessage());
        assertEquals("1.000000", ledger.occupancy("l.article_id=?", article).occupied().text(),
                "the rejected insert left nothing behind");
    }

    @Test
    @DisplayName("Repeating a reservation key replays the hold instead of spending twice")
    void reservationIsIdempotent() {
        UUID article = article("5.000000");
        UUID execution = execution(article, null, null), key = UUID.randomUUID();
        Reservation first = budget.reserve(actor(), image(article, execution, key, 1));
        Reservation replay = budget.reserve(actor(), image(article, execution, key, 4));
        assertEquals(first.id(), replay.id(), "the same key returns the hold already made");
        assertEquals("1.000000", replay.estimatedAmount().text(), "the replayed estimate is not recomputed larger");
        assertEquals(1, rows());
        assertEquals("1.000000", ledger.occupancy("l.article_id=?", article).reserved().text());
        assertEquals(1, audited.size(), "a replay audits nothing new");
    }

    @Test
    @DisplayName("Article, day and count ceilings are each admitted atomically")
    void articleAndDayCeilings() {
        UUID rich = article("5.000000"), poor = article("0.500000");
        assertEquals("1.000000", budget.reserve(actor(), image(rich, execution(rich, null, null),
                UUID.randomUUID(), 1)).estimatedAmount().text());
        PublicFailure tooBig = assertThrows(PublicFailure.class, () -> budget.reserve(actor(),
                image(poor, execution(poor, null, null), UUID.randomUUID(), 1)));
        assertEquals(409, tooBig.status());
        assertEquals("BUDGET_EXCEEDED", tooBig.code());
        // The owner's daily ceiling binds across articles; the ledger is emptied so only today's new holds count.
        execute("DELETE FROM editorial.cost_ledger");
        policy(wideCaps(), "2.000000", 80);
        UUID a = article("9.000000"), b = article("9.000000");
        budget.reserve(actor(), image(a, execution(a, null, null), UUID.randomUUID(), 1));
        budget.reserve(actor(), image(b, execution(b, null, null), UUID.randomUUID(), 1));
        PublicFailure daily = assertThrows(PublicFailure.class, () -> budget.reserve(actor(),
                image(a, execution(a, null, null), UUID.randomUUID(), 1)));
        assertEquals("DAILY_BUDGET_EXCEEDED", daily.code());
        assertEquals("2.000000", ledger.occupancy("l.owner_id=?", OWNER).reserved().text());
        // An unconfigured count cap refuses instead of treating absence as unlimited.
        service(new BudgetPolicy(money("20.000000"), Map.of(BudgetPolicy.Counter.CALLS, 1000L), Map.of(), 80, 30));
        PublicFailure uncapped = assertThrows(PublicFailure.class, () -> budget.reserve(actor(),
                image(a, execution(a, null, null), UUID.randomUUID(), 1)));
        assertEquals(503, uncapped.status());
        assertEquals("QUOTA_NOT_CONFIGURED", uncapped.code());
    }

    @Test
    @DisplayName("A provider quota stops concurrency and the daily call count")
    void providerQuota() {
        policy(wideCaps(), "20.000000", 80, Map.of(PROVIDER, new BudgetPolicy.ProviderQuota(1, 2)));
        UUID article = article("10.000000");
        Reservation one = budget.reserve(actor(), image(article, execution(article, null, null), UUID.randomUUID(), 1));
        PublicFailure concurrent = assertThrows(PublicFailure.class, () -> budget.reserve(actor(),
                image(article, execution(article, null, null), UUID.randomUUID(), 1)));
        assertEquals(429, concurrent.status());
        assertEquals("PROVIDER_QUOTA_EXCEEDED", concurrent.code());
        budget.settle(actor(), settle(one, ReservationStatus.SETTLED, IMAGE_UNIT));
        Reservation two = budget.reserve(actor(), image(article, execution(article, null, null), UUID.randomUUID(), 1));
        budget.settle(actor(), settle(two, ReservationStatus.SETTLED, IMAGE_UNIT));
        assertEquals(0, holds(), "settling released the concurrency slot");
        PublicFailure exhausted = assertThrows(PublicFailure.class, () -> budget.reserve(actor(),
                image(article, execution(article, null, null), UUID.randomUUID(), 1)));
        assertEquals("PROVIDER_QUOTA_EXCEEDED", exhausted.code(), "the daily call count is spent");
        assertEquals(4, rows(), "two holds and two facts; the refusals wrote nothing");
        // Another route under the same article budget is unaffected by this provider's quota.
        publish("other-provider", "other-model", generation());
        assertNotNull(budget.reserve(actor(), new BudgetService.Request(article, execution(article, null, null),
                "other-provider", "other-model", Capability.GENERATION, new Usage(0, 0, 0, null, 1, 0),
                Money.ZERO, true, false, UUID.randomUUID())));
    }

    // ------------------------------------------------------------------ settlement, release, UNKNOWN

    @Test
    @DisplayName("Settling below the estimate releases exactly the difference")
    void settlementReleasesTheDifference() {
        UUID article = article("1.400000");
        Reservation held = budget.reserve(actor(), image(article, execution(article, null, null),
                UUID.randomUUID(), 1));
        assertEquals("1.000000", ledger.occupancy("l.article_id=?", article).reserved().text());
        Reservation settled = budget.settle(actor(), settle(held, ReservationStatus.SETTLED, money("0.400000")));
        assertEquals(ReservationStatus.SETTLED, settled.status());
        assertEquals("0.400000", settled.settledAmount().text());
        assertEquals("0.600000", settled.releasedAmount().text());
        CostPorts.Occupancy after = ledger.occupancy("l.article_id=?", article);
        assertEquals("0.400000", after.spent().text());
        assertTrue(after.reserved().isZero());
        // The released difference is spendable again, to the last unit.
        assertEquals("1.000000", budget.reserve(actor(), image(article, execution(article, null, null),
                UUID.randomUUID(), 1)).estimatedAmount().text());
        assertEquals(3, rows(), "one hold, one fact, one new hold");
        assertEquals("BUDGET_EXCEEDED", assertThrows(PublicFailure.class, () -> budget.reserve(actor(),
                image(article, execution(article, null, null), UUID.randomUUID(), 1))).code(),
                "the difference released is exactly the room that was won back");
        assertTrue(audited.contains("COST_SETTLED|" + settled.id()));
    }

    @Test
    @DisplayName("Settlement is idempotent by key, and a different outcome is a conflict")
    void settlementReplayAndConflict() {
        UUID article = article("5.000000");
        Reservation held = budget.reserve(actor(), image(article, execution(article, null, null),
                UUID.randomUUID(), 2));
        Settlement command = settle(held, ReservationStatus.SETTLED, money("1.500000"));
        Reservation first = budget.settle(actor(), command);
        Reservation replay = budget.settle(actor(), command);
        assertEquals(first.id(), replay.id());
        assertEquals("1.500000", replay.settledAmount().text());
        assertEquals(2, rows(), "the replay appended no second fact");
        assertEquals(1, audited.stream().filter(a -> a.startsWith("COST_SETTLED")).count());
        Settlement another = settle(held, ReservationStatus.SETTLED, money("1.500000"));
        PublicFailure conflicting = assertThrows(PublicFailure.class, () -> budget.settle(actor(), another));
        assertEquals(409, conflicting.status());
        assertEquals("SETTLEMENT_CONFLICT", conflicting.code(), "a settled reservation cannot be repriced");
        assertEquals(2, rows(), "the refused conflict wrote nothing new");
        // The same key with a different amount is a conflict too, never a silent overwrite.
        Settlement changed = Settlement.of(JSON, held.id(), "req-other", money("2.000000"),
                ReservationStatus.SETTLED, command.settlementKey(), null);
        assertEquals("SETTLEMENT_CONFLICT",
                assertThrows(PublicFailure.class, () -> budget.settle(actor(), changed)).code());
    }

    @Test
    @DisplayName("An unknown outcome keeps the reservation until reconciliation")
    void unknownKeepsTheHold() {
        UUID article = article("1.000000");
        Reservation held = budget.reserve(actor(), image(article, execution(article, null, null),
                UUID.randomUUID(), 1));
        PublicFailure unresolved = assertThrows(PublicFailure.class, () -> budget.settle(actor(),
                settle(held, ReservationStatus.UNKNOWN, null)));
        assertEquals(409, unresolved.status());
        assertEquals("RECONCILIATION_REQUIRED", unresolved.code());
        CostPorts.Occupancy occupied = ledger.occupancy("l.article_id=?", article);
        assertTrue(occupied.spent().isZero(), "nothing was booked");
        assertEquals("1.000000", occupied.unknown().text(), "the estimate still occupies the budget");
        assertEquals("1.000000", occupied.held().text());
        assertEquals("BUDGET_EXCEEDED", assertThrows(PublicFailure.class, () -> budget.reserve(actor(),
                image(article, execution(article, null, null), UUID.randomUUID(), 1))).code());
        LocalDate today = LocalDate.now(ZoneOffset.UTC);
        assertEquals(1, budget.pendingReconciliations(actor(), today, today).size());
        PublicFailure stillUnknown = assertThrows(PublicFailure.class, () -> budget.reconcile(actor(),
                settle(held, ReservationStatus.UNKNOWN, null)));
        assertEquals(422, stillUnknown.status());
        assertEquals("RECONCILIATION_RESULT_REQUIRED", stillUnknown.code());
        Reservation reconciled = budget.reconcile(actor(), settle(held, ReservationStatus.SETTLED, money("0.500000")));
        assertEquals(ReservationStatus.SETTLED, reconciled.status());
        assertEquals("0.500000", reconciled.settledAmount().text());
        assertEquals("0.500000", reconciled.releasedAmount().text());
        assertEquals("0.000000", ledger.occupancy("l.article_id=?", article).unknown().text());
        assertEquals("0.500000", ledger.occupancy("l.article_id=?", article).spent().text());
        assertEquals(2, runtime.queryForObject("SELECT count(*) FROM editorial.cost_ledger WHERE kind='ACTUAL'",
                Integer.class).intValue(), "both the unresolved fact and its resolution are kept");
        assertTrue(audited.contains("COST_UNRESOLVED|" + held.id()));
        assertTrue(audited.contains("COST_SETTLED|" + held.id()));
        assertTrue(budget.pendingReconciliations(actor(), today, today).isEmpty());
        assertEquals("RECONCILIATION_REQUIRED", assertThrows(PublicFailure.class, () -> budget.reconcile(actor(),
                settle(reconciled, ReservationStatus.RELEASED, null))).code(), "only an unresolved row reconciles");
    }

    @Test
    @DisplayName("Releasing a reservation returns the whole estimate and closes the row")
    void releaseClearsTheHold() {
        UUID article = article("2.000000");
        Reservation held = budget.reserve(actor(), image(article, execution(article, null, null),
                UUID.randomUUID(), 2));
        Reservation released = budget.settle(actor(), settle(held, ReservationStatus.RELEASED, null));
        assertEquals(ReservationStatus.RELEASED, released.status());
        assertEquals("2.000000", released.releasedAmount().text());
        CostPorts.Occupancy after = ledger.occupancy("l.article_id=?", article);
        assertTrue(after.spent().isZero());
        assertTrue(after.reserved().isZero());
        assertTrue(audited.contains("COST_RELEASED|" + released.id()));
        assertEquals("SETTLEMENT_CONFLICT", assertThrows(PublicFailure.class, () -> budget.settle(actor(),
                settle(released, ReservationStatus.SETTLED, money("1.000000")))).code(), "released is terminal");
        assertEquals(2, rows());
        // The whole ceiling is free again, so the same estimate fits.
        assertNotNull(budget.reserve(actor(), image(article, execution(article, null, null), UUID.randomUUID(), 2)));
    }

    @Test
    @DisplayName("Reconciling an ordinary hold is refused before anything is written")
    void reconciliationGate() {
        UUID article = article("2.000000");
        Reservation held = budget.reserve(actor(), image(article, execution(article, null, null),
                UUID.randomUUID(), 1));
        PublicFailure refused = assertThrows(PublicFailure.class, () -> budget.reconcile(actor(),
                settle(held, ReservationStatus.SETTLED, money("1.000000"))));
        assertEquals("RECONCILIATION_REQUIRED", refused.code());
        assertEquals(1, rows(), "a refused reconciliation left no fact behind");
        assertTrue(ledger.occupancy("l.article_id=?", article).reserved().exceeds(Money.ZERO));
    }

    @Test
    @DisplayName("A cancelled or paused article still pays for what already happened")
    void cancellationDoesNotWaiveIncurredCost() {
        for (String status : List.of("CANCELLED", "PAUSED")) {
            UUID article = article("2.000000");
            Reservation held = budget.reserve(actor(), image(article, execution(article, null, null),
                    UUID.randomUUID(), 1));
            adminUpdate("UPDATE editorial.article_job SET status=? WHERE id=?", status, article);
            String code = assertThrows(PublicFailure.class, () -> budget.reserve(actor(),
                    image(article, execution(article, null, null), UUID.randomUUID(), 1))).code();
            assertEquals(status.equals("CANCELLED") ? "ARTICLE_CANCELLED" : "ARTICLE_PAUSED", code);
            // The cost already incurred is still billable and still counted against the article.
            Reservation settled = budget.settle(actor(), settle(held, ReservationStatus.SETTLED, IMAGE_UNIT));
            assertEquals(ReservationStatus.SETTLED, settled.status());
            assertEquals("1.000000", ledger.occupancy("l.article_id=?", article).spent().text());
            assertEquals(0, holds());
        }
        // A deletion-pending article is refused the same way, and never quietly charges on.
        UUID doomed = article("2.000000");
        adminUpdate("UPDATE editorial.article_job SET deletion_pending=true WHERE id=?", doomed);
        assertEquals("DELETION_PENDING", assertThrows(PublicFailure.class, () -> budget.reserve(actor(),
                image(doomed, execution(doomed, null, null), UUID.randomUUID(), 1))).code());
    }

    @Test
    @DisplayName("An execution outside the article or owner is never billed to it")
    void executionScopeIsChecked() {
        UUID article = article("5.000000");
        UUID foreign = UUID.randomUUID();
        scopes.put(foreign, new CostPorts.Executions.Scope(foreign, CostPorts.Executions.Kind.TOOL,
                UUID.randomUUID(), OWNER, null, null));
        assertEquals("NOT_FOUND", assertThrows(PublicFailure.class, () -> budget.reserve(actor(),
                image(article, foreign, UUID.randomUUID(), 1))).code());
        assertEquals("EXECUTION_NOT_FOUND", assertThrows(PublicFailure.class, () -> budget.reserve(actor(),
                image(article, UUID.randomUUID(), UUID.randomUUID(), 1))).code());
        assertEquals(0, rows());
        // Another owner cannot reserve against this article even with a matching execution.
        assertEquals("NOT_FOUND", assertThrows(PublicFailure.class, () -> budget.reserve(
                ActorContext.forWorker(OWNER, UUID.randomUUID(), UUID.randomUUID()),
                image(article, execution(article, null, null), UUID.randomUUID(), 1))).code());
    }

    // ------------------------------------------------------------------ price rules on the ledger

    @Test
    @DisplayName("An unknown price refuses automatic generation; a published zero does not")
    void unknownPriceRefusesGeneration() {
        execute("DELETE FROM editorial.cost_pricing_version");
        publish(PROVIDER, MODEL, text());
        UUID article = article("5.000000");
        UUID execution = execution(article, null, null);
        PublicFailure refused = assertThrows(PublicFailure.class, () -> budget.reserve(actor(),
                image(article, execution, UUID.randomUUID(), 1)));
        assertEquals(409, refused.status());
        assertEquals("GENERATION_PRICE_UNKNOWN", refused.code());
        assertEquals(0, rows(), "a refused generation left no hold");
        assertEquals("PRICING_UNKNOWN", assertThrows(PublicFailure.class, () -> budget.reserve(actor(),
                searchCall(article, execution, UUID.randomUUID(), 1))).code());
        // A route with no published version at all is a configuration gap, not a price decision.
        assertEquals("PRICING_NOT_PUBLISHED", assertThrows(PublicFailure.class, () -> budget.reserve(actor(),
                new BudgetService.Request(article, execution, "other-provider", "other-model", Capability.TEXT,
                        new Usage(10, 0, 10, null, 0, 0), Money.ZERO, true, false, UUID.randomUUID()))).code());
        // Published free is a real price: the hold is admitted with a zero estimate, unlike the unknown case.
        publish("free-provider", "free-model", entry("GENERATION", "0.000000000", "0.000000000", "0.000000000",
                "0.000000000", "0.000000", "0.000000", "0.000000", false));
        Reservation free = budget.reserve(actor(), new BudgetService.Request(article, execution, "free-provider",
                "free-model", Capability.GENERATION, new Usage(0, 0, 0, null, 2, 0), Money.ZERO, true, false,
                UUID.randomUUID()));
        assertTrue(free.estimatedAmount().isZero());
        assertEquals(ReservationStatus.RESERVED, free.status());
        assertEquals(1, rows(), "only the admitted free generation hold was written");
        assertEquals("0.000000", ledger.occupancy("l.article_id=?", article).reserved().text());
    }

    @Test
    @DisplayName("Reasoning tokens inside the output total are never billed twice")
    void reasoningIsBilledOnceOnTheLedger() {
        UUID article = article("5.000000");
        Usage reported = new Usage(1000, 0, 1000, 400, 0, 0);
        Reservation held = budget.reserve(actor(), text(article, execution(article, null, null), UUID.randomUUID(),
                reported, false));
        // 1000 input at 2.5/M plus 1000 output at 10/M: the 400 reasoning tokens are already inside that output.
        assertEquals("0.012500", held.estimatedAmount().text());
        Settlement command = Settlement.of(JSON, held.id(), "req-1", null, ReservationStatus.SETTLED,
                UUID.randomUUID(), reported);
        Reservation settled = budget.settle(actor(), command);
        assertEquals("0.012500", settled.settledAmount().text());
        assertEquals("0.012500", runtime.queryForObject("SELECT amount FROM editorial.cost_ledger WHERE kind='ACTUAL'",
                String.class));
        assertEquals(400, runtime.queryForObject("SELECT reasoning_tokens FROM editorial.cost_ledger"
                + " WHERE kind='ACTUAL'", Integer.class).intValue(), "the reported count is kept, and not priced");
        // Billing the reported reasoning on top of the output is refused as a mismatch, not rounded away.
        Reservation second = budget.reserve(actor(), text(article, execution(article, null, null),
                UUID.randomUUID(), reported, false));
        PublicFailure doubleCount = assertThrows(PublicFailure.class, () -> budget.settle(actor(),
                Settlement.of(JSON, second.id(), "req-2", money("0.052100"), ReservationStatus.SETTLED,
                        UUID.randomUUID(), reported)));
        assertEquals(422, doubleCount.status());
        assertEquals("SETTLEMENT_AMOUNT_MISMATCH", doubleCount.code());
        assertEquals(0, runtime.queryForObject("SELECT count(*) FROM editorial.cost_ledger WHERE amount=0.052100",
                Integer.class).intValue());
    }

    @Test
    @DisplayName("A settlement is priced under the version the reservation pinned, not the newest one")
    void settlementUsesThePinnedVersion() {
        UUID article = article("5.000000");
        Usage reported = new Usage(1000, 0, 1000, null, 0, 0);
        Reservation held = budget.reserve(actor(), text(article, execution(article, null, null), UUID.randomUUID(),
                reported, false));
        UUID pinned = held.pricingVersion();
        // The operator retires this table and publishes a cheaper one; the old hold keeps its own prices.
        originMode();
        adminUpdate("UPDATE editorial.cost_pricing_version SET status='RETIRED', lock_version=lock_version+1"
                + " WHERE id=?", pinned);
        execute("SET session_replication_role = replica");
        publishAt(PROVIDER, MODEL, "2.0.0", entry("TEXT", "0.000000000", "0.000000000", "0.000000000",
                "0.000000000", "0.000000", "0.000000", "0.000000", false));
        Reservation settled = budget.settle(actor(), Settlement.of(JSON, held.id(), "req-1", null,
                ReservationStatus.SETTLED, UUID.randomUUID(), reported));
        assertEquals("0.012500", settled.settledAmount().text(), "the retired pinned version still prices it");
        assertEquals(pinned, settled.pricingVersion());
        // A new hold under the same route uses the newly published table.
        Reservation fresh = budget.reserve(actor(), text(article, execution(article, null, null),
                UUID.randomUUID(), reported, false));
        assertTrue(fresh.estimatedAmount().isZero());
        assertNotEquals(pinned, fresh.pricingVersion());
    }

    @Test
    @DisplayName("Count limits stop the next call atomically, per article, claim and slot")
    void countCapsAreEnforced() {
        policy(Map.of(BudgetPolicy.Counter.CALLS, 3L, BudgetPolicy.Counter.SEARCH_QUERY, 5L), "20.000000", 80);
        UUID article = article("20.000000");
        for (int i = 0; i < 3; i++) {
            assertNotNull(budget.reserve(actor(), image(article, execution(article, null, null),
                    UUID.randomUUID(), 1)));
        }
        PublicFailure calls = assertThrows(PublicFailure.class, () -> budget.reserve(actor(),
                image(article, execution(article, null, null), UUID.randomUUID(), 1)));
        assertEquals(409, calls.status());
        assertEquals("QUOTA_EXCEEDED", calls.code());
        assertTrue(emitted.stream().anyMatch(a -> a.code() == BudgetAlert.Code.QUOTA_EXCEEDED
                && a.counterCap() == 3L && a.counterValue() == 4L), "the refusal reports the counter it hit");

        UUID second = article("20.000000"), claim = UUID.randomUUID(), slot = UUID.randomUUID();
        UUID otherClaim = UUID.randomUUID();
        assertNotNull(budget.reserve(actor(), searchCall(second, execution(second, claim, slot),
                UUID.randomUUID(), 2)));
        assertEquals("QUOTA_EXCEEDED", assertThrows(PublicFailure.class, () -> budget.reserve(actor(),
                searchCall(second, execution(second, claim, slot), UUID.randomUUID(), 2))).code(),
                "three queries per claim");
        assertNotNull(budget.reserve(actor(), searchCall(second, execution(second, otherClaim, slot),
                UUID.randomUUID(), 1)), "another claim still has room");

        UUID third = article("20.000000"), slotOne = UUID.randomUUID(), slotTwo = UUID.randomUUID();
        assertNotNull(budget.reserve(actor(), image(third, execution(third, null, slotOne), UUID.randomUUID(), 2)));
        assertEquals("QUOTA_EXCEEDED", assertThrows(PublicFailure.class, () -> budget.reserve(actor(),
                image(third, execution(third, null, slotOne), UUID.randomUUID(), 1))).code(), "two units per slot");
        assertNotNull(budget.reserve(actor(), image(third, execution(third, null, slotTwo), UUID.randomUUID(), 2)),
                "a second slot may fill the article allowance");
        assertEquals("QUOTA_EXCEEDED", assertThrows(PublicFailure.class, () -> budget.reserve(actor(),
                image(third, execution(third, null, UUID.randomUUID()), UUID.randomUUID(), 1))).code(),
                "four units per article");
        assertEquals(7, rows(), "only admitted calls are written");
    }

    @Test
    @DisplayName("One automatic revision loop per article, manual edits excluded")
    void autoEditLoopCap() {
        UUID article = article("20.000000");
        Usage used = new Usage(1000, 0, 1000, null, 0, 0);
        assertNotNull(budget.reserve(actor(), text(article, execution(article, null, null), UUID.randomUUID(),
                used, true)));
        assertEquals("QUOTA_EXCEEDED", assertThrows(PublicFailure.class, () -> budget.reserve(actor(),
                text(article, execution(article, null, null), UUID.randomUUID(), used, true))).code());
        assertNotNull(budget.reserve(actor(), new BudgetService.Request(article, execution(article, null, null),
                PROVIDER, MODEL, Capability.TEXT, used, Money.ZERO, false, false, UUID.randomUUID())),
                "a human edit loop is not the automatic one");
        assertEquals(1, runtime.queryForObject("SELECT coalesce(sum((c.value)::int),0) FROM editorial.cost_ledger l,"
                + " jsonb_each_text(l.counters) c(key,value) WHERE c.key='AUTO_EDIT_LOOP'", Integer.class).intValue());
    }

    // ------------------------------------------------------------------ usage projection and alerts

    @Test
    @DisplayName("GET /api/v1/usage shape, grouping, paging and cursor binding")
    void usageProjectionIsTheFrozenShape() {
        UUID first = article("20.000000"), second = article("20.000000");
        for (UUID article : List.of(first, second)) {
            Reservation held = budget.reserve(actor(), image(article, execution(article, null, null),
                    UUID.randomUUID(), 1));
            budget.settle(actor(), settle(held, ReservationStatus.SETTLED, IMAGE_UNIT));
            budget.reserve(actor(), text(article, execution(article, null, null), UUID.randomUUID(),
                    new Usage(1000, 0, 1000, null, 0, 2), false));
        }
        LocalDate today = LocalDate.now(ZoneOffset.UTC);
        ObjectNode summary = usage.usage(actor(), today.toString(), today.toString(), "DAY", null, 100);
        assertEquals(11, summary.size(), "exactly the eleven UsageSummary members rc.3 declares");
        assertEquals("USD", summary.get("currency").asText());
        for (String field : List.of("actual", "estimated", "unknownReserved"))
            assertTrue(summary.get(field).asText().matches("^(0|[1-9][0-9]{0,11})\\.[0-9]{6}$"), field);
        assertEquals("2.000000", summary.get("actual").asText());
        assertEquals("0.025000", summary.get("estimated").asText());
        assertEquals("0.000000", summary.get("unknownReserved").asText());
        assertEquals(2000, summary.get("inputTokens").asInt());
        assertEquals(0, summary.get("cachedInputTokens").asInt());
        assertEquals(2000, summary.get("outputTokens").asInt());
        assertEquals(4, summary.get("searchCalls").asInt());
        assertEquals(2, summary.get("imageUnits").asInt());
        assertEquals(4, summary.get("entries").size(), "one entry per reservation in the window");
        JsonNode entry = summary.get("entries").get(0);
        assertEquals(10, entry.size(), "BudgetReservation declares exactly ten members");
        for (String field : List.of("id", "articleId", "executionId", "amount", "currency", "pricingVersion",
                "status", "costType", "idempotencyKey", "createdAt"))
            assertTrue(entry.has(field), "missing " + field);
        assertTrue(entry.get("amount").asText().matches("^(0|[1-9][0-9]{0,11})\\.[0-9]{6}$"));
        assertEquals("USD", entry.get("currency").asText());
        assertTrue(entry.get("createdAt").asText().contains("T"));
        var statuses = StreamSupport.stream(summary.get("entries").spliterator(), false)
                .map(node -> node.get("status").asText()).toList();
        assertEquals(2, statuses.stream().filter("SETTLED"::equals).count());
        assertEquals(2, statuses.stream().filter("RESERVED"::equals).count());
        var types = StreamSupport.stream(summary.get("entries").spliterator(), false)
                .map(node -> node.get("costType").asText()).toList();
        assertEquals(2, types.stream().filter("ACTUAL"::equals).count(), "a settled row reports its actual cost");
        assertEquals(2, types.stream().filter("ESTIMATED"::equals).count());
        assertTrue(summary.get("nextCursor").isNull(), "one page covers the window");
        // Paging by article: two per page, and the cursor walks all four rows without repeating one.
        ObjectNode pageOne = usage.usage(actor(), today.toString(), today.toString(), "ARTICLE", null, 2);
        assertEquals(2, pageOne.get("entries").size());
        String cursor = pageOne.get("nextCursor").asText();
        ObjectNode pageTwo = usage.usage(actor(), today.toString(), today.toString(), "ARTICLE", cursor, 2);
        assertEquals(2, pageTwo.get("entries").size());
        assertNotEquals(pageOne.get("entries").get(0).get("id").asText(),
                pageTwo.get("entries").get(0).get("id").asText());
        assertEquals("2.000000", pageTwo.get("actual").asText(), "totals describe the window, not the page");
        assertEquals(0, usage.usage(actor(), today.toString(), today.toString(), "ARTICLE",
                pageTwo.get("nextCursor").asText(), 2).get("entries").size());
        assertEquals(4, usage.usage(actor(), today.toString(), today.toString(), "PROVIDER", null, 100)
                .get("entries").size());
        assertEquals(4, usage.usage(actor(), today.toString(), today.toString(), "MODEL", null, 100)
                .get("entries").size());
        // Defaults: no window means the last thirty UTC days, and no group means DAY.
        assertEquals(4, usage.usage(actor(), null, null, null, null, 20).get("entries").size());
        // A cursor from another filter or window is refused rather than silently re-used.
        PublicFailure stale = assertThrows(PublicFailure.class, () -> usage.usage(actor(), today.toString(),
                today.toString(), "PROVIDER", cursor, 2));
        assertEquals(409, stale.status());
        assertEquals("CURSOR_STALE", stale.code());
        assertEquals("CURSOR_STALE", assertThrows(PublicFailure.class, () -> usage.usage(actor(),
                today.minusDays(3).toString(), today.minusDays(3).toString(), "ARTICLE", cursor, 2)).code());
        assertEquals("INVALID_CURSOR", assertThrows(PublicFailure.class, () -> usage.usage(actor(), today.toString(),
                today.toString(), "ARTICLE", cursor + "x", 2)).code());
        assertEquals("INVALID_CURSOR", assertThrows(PublicFailure.class, () -> usage.usage(actor(), today.toString(),
                today.toString(), "ARTICLE", "nonsense", 2)).code());
        assertEquals("INVALID_GROUP_BY", assertThrows(PublicFailure.class, () -> usage.usage(actor(), null, null,
                "COST_TYPE", null, 20)).code());
        assertEquals("INVALID_PAGE_SIZE", assertThrows(PublicFailure.class, () -> usage.usage(actor(), null, null,
                null, null, 0)).code());
        assertEquals("INVALID_PAGE_SIZE", assertThrows(PublicFailure.class, () -> usage.usage(actor(), null, null,
                null, null, 101)).code());
        assertEquals("INVALID_DATE_RANGE", assertThrows(PublicFailure.class, () -> usage.usage(actor(),
                today.plusDays(1).toString(), today.toString(), null, null, 20)).code());
        assertEquals("INVALID_DATEFROM", assertThrows(PublicFailure.class, () -> usage.usage(actor(), "yesterday",
                null, null, null, 20)).code());
        assertEquals("INVALID_DATETO", assertThrows(PublicFailure.class, () -> usage.usage(actor(), null,
                "tomorrow", null, null, 20)).code());
        // Another owner's window is empty, and none of these rows leaks into it.
        ObjectNode empty = usage.usage(ActorContext.forWorker(OWNER, UUID.randomUUID(), UUID.randomUUID()),
                null, null, null, null, 20);
        assertEquals(0, empty.get("entries").size());
        assertEquals("0.000000", empty.get("actual").asText());
    }

    @Test
    @DisplayName("Budget alert data: the alert line and the unresolved queue")
    void budgetAlertData() {
        policy(wideCaps(), "20.000000", 60);
        UUID article = article("5.000000");
        budget.reserve(actor(), image(article, execution(article, null, null), UUID.randomUUID(), 3));
        BudgetAlert warning = emitted.stream().filter(a -> a.code() == BudgetAlert.Code.BUDGET_WARNING
                && "ARTICLE".equals(a.scope())).findFirst().orElseThrow();
        assertEquals(60, warning.percent());
        assertEquals("5.000000", warning.limit().text());
        assertEquals("3.000000", warning.reserved().text());
        assertTrue(warning.spent().isZero());
        LocalDate today = LocalDate.now(ZoneOffset.UTC);
        assertTrue(usage.alerts(actor(), today, today).isEmpty(), "the daily ceiling is nowhere near its line");
        Reservation held = budget.reserve(actor(), image(article, execution(article, null, null),
                UUID.randomUUID(), 1));
        assertThrows(PublicFailure.class, () -> budget.settle(actor(), settle(held, ReservationStatus.UNKNOWN, null)));
        List<BudgetAlert> alerts = usage.alerts(actor(), today, today);
        assertEquals(1, alerts.size(), "the unresolved reservation reports itself");
        assertEquals(BudgetAlert.Code.RECONCILIATION_STALE, alerts.get(0).code());
        assertEquals("1.000000", alerts.get(0).unknown().text());
        assertEquals(100, alerts.get(0).percent());
        assertEquals(1, budget.pendingReconciliations(actor(), today, today).size());
    }

    @Test
    @DisplayName("A stale hold enters the reconciliation queue and reports its own alert")
    void staleHoldsAreReported() {
        UUID article = article("20.000000");
        Reservation held = budget.reserve(actor(), image(article, execution(article, null, null),
                UUID.randomUUID(), 1));
        adminUpdate("UPDATE editorial.cost_ledger SET updated_at = now() - interval '2 hours',"
                + " created_at = now() - interval '2 hours' WHERE id=?", held.id());
        LocalDate today = LocalDate.now(ZoneOffset.UTC);
        List<Reservation> pending = budget.pendingReconciliations(actor(), today, today);
        assertEquals(1, pending.size());
        assertEquals(held.id(), pending.get(0).id());
        assertEquals(ReservationStatus.RESERVED, pending.get(0).status());
        assertTrue(emitted.stream().anyMatch(a -> a.code() == BudgetAlert.Code.RECONCILIATION_STALE));
        assertNotNull(budget.reserve(actor(), image(article, execution(article, null, null), UUID.randomUUID(), 1)));
        assertEquals(1, budget.pendingReconciliations(actor(), today, today).size(), "a fresh hold is not stale");
        assertEquals(0, budget.pendingReconciliations(actor(), today.minusDays(2), today.minusDays(1)).size());
    }

    // ------------------------------------------------------------------ over-run and database guards

    @Test
    @DisplayName("A real bill above the estimate is booked, reported, and never re-reserved")
    void overRunIsBookedAndReported() {
        UUID article = article("2.000000");
        Reservation cheap = budget.reserve(actor(), text(article, execution(article, null, null), UUID.randomUUID(),
                new Usage(1000, 0, 1000, null, 0, 0), false));
        assertEquals("0.012500", cheap.estimatedAmount().text());
        Reservation under = budget.settle(actor(), settle(cheap, ReservationStatus.SETTLED, money("0.002500")));
        assertEquals("0.010000", under.releasedAmount().text());
        assertTrue(under.overRun().isZero());
        assertEquals("0.002500", ledger.occupancy("l.article_id=?", article).spent().text());

        Reservation tight = budget.reserve(actor(), image(article, execution(article, null, null),
                UUID.randomUUID(), 1));
        Reservation over = budget.settle(actor(), settle(tight, ReservationStatus.SETTLED, money("1.500000")));
        assertEquals("0.500000", over.overRun().text(), "the final reconciliation difference is reported");
        assertEquals("1.000000", over.estimatedAmount().text(), "the estimate itself is never rewritten");
        assertTrue(over.releasedAmount().isZero(), "nothing is released when the bill was larger");
        assertEquals("1.502500", ledger.occupancy("l.article_id=?", article).spent().text());
        assertEquals("1.502500", ledger.occupancy("l.article_id=?", article).occupied().text());
        // Settlement never fails for budget reasons; the next hold is what the ceiling stops.
        assertEquals("BUDGET_EXCEEDED", assertThrows(PublicFailure.class, () -> budget.reserve(actor(),
                image(article, execution(article, null, null), UUID.randomUUID(), 1))).code());
        assertEquals("1.502500", runtime.queryForObject("SELECT sum(amount) FROM editorial.cost_ledger"
                + " WHERE kind='ACTUAL' AND status='SETTLED' AND article_id=?", String.class, article));
    }

    @Test
    @DisplayName("The ledger refuses repricing, re-transitioning and a second terminal fact")
    void ledgerGuardsHold() {
        UUID article = article("5.000000");
        Reservation held = budget.reserve(actor(), image(article, execution(article, null, null),
                UUID.randomUUID(), 1));
        Reservation settled = budget.settle(actor(), settle(held, ReservationStatus.SETTLED, IMAGE_UNIT));
        assertTrue(sqlFailure(() -> runtime.update(
                "UPDATE editorial.cost_ledger SET amount=0.000001 WHERE id=?", held.id())).getMessage()
                .contains("reservation fact immutable"));
        assertTrue(sqlFailure(() -> runtime.update(
                "UPDATE editorial.cost_ledger SET status='RELEASED', lock_version=lock_version+1 WHERE id=?",
                held.id())).getMessage().contains("illegal ledger transition"));
        assertTrue(sqlFailure(() -> runtime.update(
                "UPDATE editorial.cost_ledger SET status='RESERVED' WHERE id=? AND lock_version=2", held.id()))
                .getMessage().contains("ledger revision required"));
        assertTrue(sqlFailure(() -> runtime.update(
                "UPDATE editorial.cost_ledger SET settled_amount=1 WHERE reservation_id=? AND kind='ACTUAL'",
                settled.id()))
                .getMessage().contains("settlement fact is immutable"));
        assertTrue(sqlFailure(() -> runtime.update(
                "INSERT INTO editorial.cost_ledger SELECT * FROM editorial.cost_ledger WHERE id=?", held.id()))
                .getMessage().contains("duplicate key"));
        // A second terminal fact for the same reservation is refused at commit by the consistency check.
        SQLException second = sqlFailure(() -> tx.executeWithoutResult(status ->
                runtime.update("INSERT INTO editorial.cost_ledger (id,article_id,owner_id,execution_id,"
                        + "execution_kind,reservation_id,kind,status,amount,currency,pricing_version,pricing_hash,"
                        + "idempotency_key,settlement_key,provider,model,capability,bucket_day,usage,counters,"
                        + "created_by,updated_by,trace_id) SELECT gen_random_uuid(),l.article_id,l.owner_id,"
                        + "l.execution_id,l.execution_kind,l.reservation_id,'ACTUAL','RELEASED',0,'USD',"
                        + "l.pricing_version,l.pricing_hash,gen_random_uuid(),gen_random_uuid(),l.provider,"
                        + "l.model,l.capability,l.bucket_day,'{}'::jsonb,'{}'::jsonb,?,?,? FROM "
                        + "editorial.cost_ledger l WHERE l.kind='ESTIMATED' AND l.id=?", OWNER, OWNER,
                        UUID.randomUUID(), held.id())));
        assertTrue(second.getMessage().contains("terminal row needs exactly one fact"), second.getMessage());
        assertEquals(2, rows(), "the refused fact rolled the whole transaction back");
    }

    @Test
    @DisplayName("The runtime role may not erase cost facts or publish prices")
    void runtimeGrantsAreMinimal() {
        UUID article = article("5.000000");
        Reservation held = budget.reserve(actor(), image(article, execution(article, null, null),
                UUID.randomUUID(), 1));
        assertTrue(sqlFailure(() -> runtime.update(
                "DELETE FROM editorial.cost_ledger WHERE id=?", held.id())).getMessage().contains("permission denied"));
        assertTrue(sqlFailure(() -> runtime.execute("TRUNCATE editorial.cost_ledger"))
                .getMessage().contains("permission denied"));
        assertTrue(sqlFailure(() -> runtime.update(
                "INSERT INTO editorial.cost_pricing_version(id,provider,model,version,currency,rules,hash,status,"
                        + "created_by,updated_by) VALUES (gen_random_uuid(),'p','m','1.0.0','USD','{}'::jsonb,?,"
                        + "'PUBLISHED',?,?)", "0".repeat(64), OWNER, OWNER)).getMessage().contains("permission denied"));
        assertTrue(sqlFailure(() -> runtime.update(
                "UPDATE editorial.cost_pricing_version SET status='RETIRED'")).getMessage()
                .contains("permission denied"));
        assertEquals("1.000000", ledger.occupancy("l.article_id=?", article).reserved().text());
    }

    @Test
    @DisplayName("A published price version is frozen, unique per route, and may only retire")
    void publishedPriceIsImmutable() {
        UUID article = article("5.000000");
        UUID execution = execution(article, null, null);
        originMode();
        UUID version = runtime.queryForObject("SELECT id FROM editorial.cost_pricing_version WHERE provider=? AND"
                + " model=?", UUID.class, PROVIDER, MODEL);
        assertTrue(sqlFailure(() -> adminUpdate(
                "UPDATE editorial.cost_pricing_version SET rules='{}'::jsonb WHERE id=?", version))
                .getMessage().contains("price rules immutable"));
        assertTrue(sqlFailure(() -> adminUpdate(
                "UPDATE editorial.cost_pricing_version SET status='DRAFT' WHERE id=?", version))
                .getMessage().contains("published price only retires"));
        assertTrue(sqlFailure(() -> adminUpdate(
                "UPDATE editorial.cost_pricing_version SET status='RETIRED' WHERE id=?", version))
                .getMessage().contains("price revision required"), "even retirement needs a revision");
        // Only one published version may exist per route.
        SQLException duplicate = sqlFailure(() -> publishAt(PROVIDER, MODEL, "1.0.1", text()));
        assertTrue(duplicate.getMessage().contains("cost_pricing_one_published")
                || duplicate.getMessage().contains("duplicate key"), duplicate.getMessage());
        assertTrue(sqlFailure(() -> adminUpdate(
                "DELETE FROM editorial.cost_pricing_version WHERE id=?", version))
                .getMessage().contains("price version immutable"));
        adminUpdate("UPDATE editorial.cost_pricing_version SET status='RETIRED', lock_version=lock_version+1"
                + " WHERE id=?", version);
        assertTrue(sqlFailure(() -> adminUpdate(
                "UPDATE editorial.cost_pricing_version SET status='PUBLISHED', lock_version=lock_version+1"
                        + " WHERE id=?", version)).getMessage().contains("retired price version final"));
        assertEquals("PRICING_NOT_PUBLISHED", assertThrows(PublicFailure.class, () -> budget.reserve(actor(),
                image(article, execution, UUID.randomUUID(), 1))).code());
        assertEquals(0, rows(), "no hold was written against a retired table");
    }

    @Test
    @DisplayName("Every cost row keeps the identity it was reserved under")
    void reservationRowsAreAuditable() throws Exception {
        UUID article = article("5.000000");
        UUID claim = UUID.randomUUID();
        UUID execution = execution(article, claim, null);
        Usage used = new Usage(1000, 400, 500, 200, 0, 1);
        Reservation held = budget.reserve(actor(), text(article, execution, UUID.randomUUID(), used, false));
        JsonNode stored = JSON.readTree(runtime.queryForObject("SELECT usage::text FROM editorial.cost_ledger"
                + " WHERE id=?", String.class, held.id()));
        assertEquals(1000, stored.get("inputTokens").asInt());
        assertEquals(400, stored.get("cachedInputTokens").asInt());
        assertEquals(200, stored.get("reasoningTokensIfProvided").asInt());
        // 600 uncached at 2.5/M, 400 cached at 1/M, 500 output at 10/M: 0.006900, once, with the reasoning kept.
        assertEquals("0.006900", held.estimatedAmount().text());
        assertEquals(held.id(), runtime.queryForObject("SELECT reservation_id FROM editorial.cost_ledger WHERE id=?",
                UUID.class, held.id()));
        assertEquals(claim, runtime.queryForObject("SELECT claim_id FROM editorial.cost_ledger WHERE id=?",
                UUID.class, held.id()));
        assertEquals(1, runtime.queryForObject("SELECT count(*) FROM editorial.cost_ledger"
                + " WHERE execution_kind='AGENT'", Integer.class).intValue());
        assertNull(runtime.queryForObject("SELECT settlement_hash FROM editorial.cost_ledger WHERE id=?",
                String.class, held.id()));
        Reservation settled = budget.settle(actor(), Settlement.of(JSON, held.id(), "req-1", null,
                ReservationStatus.SETTLED, UUID.randomUUID(), used));
        assertEquals(64, runtime.queryForObject("SELECT settlement_hash FROM editorial.cost_ledger WHERE id=?",
                String.class, settled.id()).length());
        assertNotNull(runtime.queryForObject("SELECT reconciled_at FROM editorial.cost_ledger WHERE id=?",
                java.sql.Timestamp.class, settled.id()));
        assertEquals(1, runtime.queryForObject("SELECT count(*) FROM editorial.cost_ledger WHERE kind='ACTUAL'"
                + " AND settlement_key IS NOT NULL AND provider_request_id='req-1'", Integer.class).intValue());
    }

    @Test
    @DisplayName("Cost audit lands in audit_log and the table itself refuses money payloads")
    void auditRowsLandInTheAuditTableThroughTheRealSink() {
        auditPort = realAuditSinkPort();
        service(activePolicy);
        UUID article = article("5.000000");
        UUID execution = execution(article, null, null);
        Reservation held = budget.reserve(actor(), image(article, execution, UUID.randomUUID(), 1));
        budget.settle(actor(), settle(held, ReservationStatus.SETTLED, money("0.400000")));

        List<Map<String, Object>> written = runtime.queryForList("SELECT action,actor_type,entity_type,article_id,"
                + "entity_id,before_hash,after_hash,detail::text AS detail FROM editorial.audit_log ORDER BY action");
        assertEquals(2, written.size(), "one trail row per accounting action, written by the real sink");
        assertEquals(List.of("COST_RESERVED", "COST_SETTLED"),
                written.stream().map(row -> (String) row.get("action")).toList());
        for (Map<String, Object> row : written) {
            assertEquals("COST", row.get("entity_type"));
            assertEquals("SYSTEM_WORKER", row.get("actor_type"));
            assertEquals(article, row.get("article_id"));
            assertEquals(held.id(), row.get("entity_id"));
            assertNull(row.get("before_hash"), "amounts never travel through a hash column");
            assertNull(row.get("after_hash"));
            assertEquals("{}", row.get("detail"), "audit_log.detail is pinned to the empty object");
        }
        // What the service actually handed the port: identifiers only, no amount text in either hash slot.
        assertEquals(List.of("COST_RESERVED|null|null", "COST_SETTLED|null|null"), auditPayloads);

        // Bypassing the adapter cannot bypass the table: six-decimal text is not a hash and not detail.
        SQLException hashRejected = sqlFailure(() -> runtime.update("INSERT INTO editorial.audit_log(id,actor_id,"
                + "actor_type,action,entity_type,entity_id,before_hash,trace_id) VALUES (gen_random_uuid(),?,"
                + "'SYSTEM_WORKER','COST_RESERVED','COST',gen_random_uuid(),?::char(64),gen_random_uuid())",
                OWNER, "0.034200"));
        assertEquals("23514", hashRejected.getSQLState());
        SQLException detailRejected = sqlFailure(() -> runtime.update("INSERT INTO editorial.audit_log(id,actor_id,"
                + "actor_type,action,entity_type,entity_id,detail,trace_id) VALUES (gen_random_uuid(),?,"
                + "'SYSTEM_WORKER','COST_SETTLED','COST',gen_random_uuid(),"
                + "'{\"amount\":\"0.034200\"}'::jsonb,gen_random_uuid())", OWNER));
        assertEquals("23514", detailRejected.getSQLState());
        // The shape rule is applied before any SQL runs, and a rejected value is not echoed into the message.
        IllegalStateException guarded = assertThrows(IllegalStateException.class, () -> auditPort.append(actor(),
                "COST_RESERVED", article, held.id(), "0.034200", null));
        assertFalse(guarded.getMessage() != null && guarded.getMessage().contains("0.034200"));
        // Audit is append-only for the runtime role: it may write the trail but never rewrite or erase it.
        assertEquals(2, runtime.queryForObject("SELECT count(*) FROM editorial.audit_log", Integer.class).intValue());
        assertEquals("42501", sqlFailure(() -> runtime.update("DELETE FROM editorial.audit_log")).getSQLState());
        assertEquals("42501", sqlFailure(() -> runtime.update("UPDATE editorial.audit_log SET action='COST_X'"))
                .getSQLState());
        assertEquals(2, runtime.queryForObject("SELECT count(*) FROM editorial.audit_log", Integer.class).intValue(),
                "the failed statements left nothing behind");
    }
}

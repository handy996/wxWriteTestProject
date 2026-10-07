package com.example.editorial.identity;

import com.example.editorial.audit.JdbcAuditSink;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.CopyOnWriteArrayList;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.BeanCreationException;
import org.springframework.beans.factory.config.ConfigurableListableBeanFactory;
import org.springframework.boot.env.PropertiesPropertySourceLoader;
import org.springframework.boot.env.YamlPropertySourceLoader;
import org.springframework.boot.context.properties.bind.Binder;
import org.springframework.context.ApplicationContext;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;
import org.springframework.context.support.StaticApplicationContext;
import org.springframework.core.env.MapPropertySource;
import org.springframework.core.env.PropertySource;
import org.springframework.core.env.StandardEnvironment;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.core.io.Resource;
import org.springframework.core.io.support.PathMatchingResourcePatternResolver;
import org.springframework.core.io.support.ResourcePatternResolver;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.security.config.ObjectPostProcessor;
import org.springframework.security.config.annotation.authentication.builders.AuthenticationManagerBuilder;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.crypto.password.Pbkdf2PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.csrf.HttpSessionCsrfTokenRepository;
import org.springframework.transaction.PlatformTransactionManager;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Offline negative proof for the session cookie contract, in three layers.
 *
 * <p>Direct calls: {@link T03Configuration#verifySessionCookieContract} is exercised with fixture environments, so a
 * wrong name is shown to abort rather than merely described by a static gate.</p>
 *
 * <p>Assembly: the production {@code identitySecurity} bean method is instantiated by a real
 * {@link AnnotationConfigApplicationContext} (no database, no servlet container, no mocks) so the <em>call site</em>
 * at {@code T03Configuration.java:42} is executed by Spring's own bean creation, and the rejection arrives wrapped in
 * a {@link BeanCreationException} with the guard's own stack frames - the same failure shape the live boot produces.
 * Deleting, commenting, or constant-false-wrapping that call site makes these cases fail, which no amount of text in
 * a comment or literal can imitate.</p>
 *
 * <p>Configuration: the property files are read by Spring's own {@link YamlPropertySourceLoader} and
 * {@link PropertiesPropertySourceLoader} and resolved by {@link Binder}, so the effective name is what Boot binds,
 * including flow style spanning lines, anchors, merge keys, comments, {@code .properties} files and the
 * {@code classpath:/config/} layer - shapes a hand-written text census can miss.</p>
 */
class T03SessionCookieGuardTest {
    private static final String NAME = "server.servlet.session.cookie.name";
    private static final String SECURE = "server.servlet.session.cookie.secure";
    private static final String HTTP_ONLY = "server.servlet.session.cookie.http-only";
    private static final String SAME_SITE = "server.servlet.session.cookie.same-site";
    private static final String ENABLED = "editorial.identity.enabled";
    private static final String ORIGIN = "editorial.identity.origin";
    private static final String COOKIE_ANCHOR = "EDITORIAL_SESSION";
    /** Boot's live config surface: the resources root and classpath:/config/, in the extensions its loaders accept. */
    private static final List<String> SURFACE_PATTERNS = List.of(
            "classpath*:/application*.yml", "classpath*:/application*.yaml", "classpath*:/application*.properties",
            "classpath*:/config/application*.yml", "classpath*:/config/application*.yaml",
            "classpath*:/config/application*.properties");
    /** Collected by the census case and flushed after the class, so the gate can compare it with the tree it reads. */
    private static final List<String> CENSUS = new CopyOnWriteArrayList<>();

    private static StandardEnvironment env(Map<String, Object> properties, String... profiles) {
        StandardEnvironment environment = new StandardEnvironment();
        // addFirst so the fixture wins over any inherited system property, and addLast keeps the system sources live.
        environment.getPropertySources().addFirst(new MapPropertySource("guard-test", properties));
        if (profiles.length > 0) {
            environment.setActiveProfiles(profiles);
        }
        return environment;
    }

    private static Map<String, Object> contractConformantProdCookie() {
        Map<String, Object> properties = new HashMap<>();
        properties.put(NAME, T03Configuration.SESSION_COOKIE_NAME);
        properties.put(SECURE, true);
        properties.put(HTTP_ONLY, true);
        properties.put(SAME_SITE, "strict");
        return properties;
    }

    @Test void constantIsTheApprovedContractLiteral() {
        assertEquals(COOKIE_ANCHOR, T03Configuration.SESSION_COOKIE_NAME,
                "the Java anchor must be the literal rc.3 declares, not just equal to the other sources");
    }

    @Test void absentCookieNameAbortsStartup() {
        IllegalStateException failure = assertThrows(IllegalStateException.class,
                () -> T03Configuration.verifySessionCookieContract(env(new HashMap<>())));
        assertTrue(failure.getMessage().startsWith("T03_COOKIE"), failure.getMessage());
        assertTrue(failure.getMessage().contains(COOKIE_ANCHOR), failure.getMessage());
    }

    @Test void containerDefaultNameAbortsStartup() {
        Map<String, Object> properties = new HashMap<>();
        properties.put(NAME, "JSESSIONID");
        assertThrows(IllegalStateException.class,
                () -> T03Configuration.verifySessionCookieContract(env(properties)),
                "issuing the container default is exactly the drift T07-R04 was opened for");
    }

    @Test void thirdNameAbortsStartupEvenThoughItIsNotTheContainerDefault() {
        Map<String, Object> properties = new HashMap<>();
        properties.put(NAME, "SOMETHING_ELSE");
        IllegalStateException failure = assertThrows(IllegalStateException.class,
                () -> T03Configuration.verifySessionCookieContract(env(properties)));
        assertTrue(failure.getMessage().startsWith("T03_COOKIE"), failure.getMessage());
    }

    @Test void approvedNameStartsOutsideProd() {
        Map<String, Object> properties = new HashMap<>();
        properties.put(NAME, T03Configuration.SESSION_COOKIE_NAME);
        assertDoesNotThrow(() -> T03Configuration.verifySessionCookieContract(env(properties)));
    }

    @Test void prodRejectsEachInsecureCookieAttribute() {
        for (String weakened : List.of(SECURE, HTTP_ONLY, SAME_SITE)) {
            Map<String, Object> properties = contractConformantProdCookie();
            if (SAME_SITE.equals(weakened)) {
                properties.put(SAME_SITE, "lax");
            } else {
                properties.put(weakened, false);
            }
            Map<String, Object> fixture = properties;
            IllegalStateException failure = assertThrows(IllegalStateException.class,
                    () -> T03Configuration.verifySessionCookieContract(env(fixture, "prod")),
                    weakened + " must not be relaxed in production");
            assertTrue(failure.getMessage().startsWith("T03_COOKIE"), failure.getMessage());
        }
    }

    @Test void prodAcceptsTheContractConformantCookie() {
        assertDoesNotThrow(() -> T03Configuration.verifySessionCookieContract(
                env(contractConformantProdCookie(), "prod")));
    }

    // ---------------------------------------------------------------------------------------------
    // Assembly: the call site itself, executed by Spring's bean creation.
    // ---------------------------------------------------------------------------------------------

    private static Map<String, Object> assemblyProperties(String cookieName, boolean prodShape) {
        Map<String, Object> properties = new HashMap<>();
        properties.put(ENABLED, "true");
        properties.put(ORIGIN, prodShape ? "https://editorial.example.test" : "http://localhost:3000");
        if (cookieName != null) {
            properties.put(NAME, cookieName);
        }
        return properties;
    }

    /**
     * A context that really assembles the production {@code identitySecurity} bean: the configuration class is the
     * production one, its {@code @Bean} method is invoked by Spring, and only collaborators that would need a
     * database are supplied as offline instances. Every other bean definition is marked lazy, so creating
     * {@code identitySecurity} does not drag Flyway, JPA or a DataSource into an offline test - and because
     * {@code identitySecurity} stays eager, {@code refresh()} is what runs the guard, exactly as a boot does.
     */
    private static SecurityFilterChain assembleIdentitySecurity(Map<String, Object> properties, String... profiles) {
        AnnotationConfigApplicationContext context = new AnnotationConfigApplicationContext();
        try {
            context.setEnvironment(env(new HashMap<>(properties), profiles));
            context.registerBean(JdbcTemplate.class, T03SessionCookieGuardTest::jdbcTemplate);
            context.registerBean(PlatformTransactionManager.class, T03SessionCookieGuardTest::transactionManager);
            context.registerBean(HttpSecurity.class, () -> httpSecurity(context));
            context.register(T03Configuration.class);
            context.addBeanFactoryPostProcessor(T03SessionCookieGuardTest::onlyTheCookieGuardBeanIsEager);
            context.refresh();
            return context.getBean("identitySecurity", SecurityFilterChain.class);
        } finally {
            context.close();
        }
    }

    private static void onlyTheCookieGuardBeanIsEager(ConfigurableListableBeanFactory factory) {        for (String beanName : factory.getBeanDefinitionNames()) {
            if (!beanName.equals("identitySecurity")) {
                factory.getBeanDefinition(beanName).setLazyInit(true);
            }
        }
    }

    private static HttpSecurity httpSecurity(ApplicationContext context) {
        Map<Class<?>, Object> sharedObjects = new HashMap<>();
        sharedObjects.put(ApplicationContext.class, context);
        ObjectPostProcessor<Object> postProcessor = ObjectPostProcessor.identity();
        return new HttpSecurity(postProcessor, new AuthenticationManagerBuilder(postProcessor), sharedObjects);
    }

    private static JdbcTemplate jdbcTemplate() {
        return new JdbcTemplate(dataSource());
    }

    private static PlatformTransactionManager transactionManager() {
        return new DataSourceTransactionManager(dataSource());
    }

    /** Never contacted: the guard aborts before any statement, and the assembled chain is never exercised here. */
    private static DriverManagerDataSource dataSource() {
        DriverManagerDataSource dataSource = new DriverManagerDataSource();
        dataSource.setDriverClassName("org.postgresql.Driver");
        dataSource.setUrl("jdbc:postgresql://127.0.0.1:1/absent-offline-only");
        return dataSource;
    }

    private static Throwable rootCause(Throwable failure) {
        Throwable root = failure;
        while (root.getCause() != null && root.getCause() != root) {
            root = root.getCause();
        }
        return root;
    }

    /** The guard has to be seen to come out of the bean method, not out of a helper the test calls by itself. */
    private static void assertAssembledAtTheCallSite(Throwable failure, String beanMethodName) {
        List<StackTraceElement> frames = List.of(failure.getStackTrace());
        boolean insideAssembly = frames.stream().anyMatch(frame -> frame.getClassName().equals(T03Configuration.class.getName())
                && frame.getMethodName().equals(beanMethodName));
        assertTrue(insideAssembly, "no " + beanMethodName + " frame in the rejection: " + frames);
        assertTrue(frames.stream().anyMatch(frame -> frame.getMethodName().equals("verifySessionCookieContract")),
                "the rejection did not pass through verifySessionCookieContract: " + frames);
        assertTrue(frames.stream().anyMatch(frame -> frame.getClassName().startsWith("org.springframework.beans.factory")),
                "the rejection did not come out of Spring's bean creation: " + frames);
    }

    @Test void assembledIdentitySecurityAbortsOnNonContractCookieName() {
        Map<String, Object> properties = assemblyProperties("SOMETHING_ELSE", false);
        BeanCreationException failure = assertThrows(BeanCreationException.class,
                () -> assembleIdentitySecurity(properties));
        Throwable root = rootCause(failure);
        assertTrue(root instanceof IllegalStateException, "unexpected root cause " + root.getClass());
        assertTrue(root.getMessage().startsWith("T03_COOKIE"), root.getMessage());
        assertEquals("identitySecurity", failure.getBeanName(), "the aborted bean must be the guarded assembly");
        assertAssembledAtTheCallSite(root, "identitySecurity");
    }

    @Test void assembledIdentitySecurityStartsWithContractCookieName() {
        Map<String, Object> properties = assemblyProperties(T03Configuration.SESSION_COOKIE_NAME, false);
        SecurityFilterChain chain = assertDoesNotThrow(() -> assembleIdentitySecurity(properties));
        assertNotNull(chain, "the contract-conformant name must assemble the chain, not skip it");
        assertFalse(chain.getFilters().isEmpty(), "an empty filter chain means the assembly never completed");
    }

    @Test void assembledIdentitySecurityAbortsOnInsecureProdCookie() {
        Map<String, Object> properties = contractConformantProdCookie();
        properties.put(ENABLED, "true");
        properties.put(ORIGIN, "https://editorial.example.test");
        properties.put(SECURE, false);
        BeanCreationException failure = assertThrows(BeanCreationException.class,
                () -> assembleIdentitySecurity(properties, "prod"));
        Throwable root = rootCause(failure);
        assertTrue(root.getMessage().startsWith("T03_COOKIE"), root.getMessage());
        assertAssembledAtTheCallSite(root, "identitySecurity");
    }

    // ---------------------------------------------------------------------------------------------
    // Configuration: what Spring's own loaders and binder really resolve.
    // ---------------------------------------------------------------------------------------------

    private static List<PropertySource<?>> load(Resource resource) throws IOException {
        String filename = resource.getFilename();
        if (filename != null && (filename.endsWith(".yml") || filename.endsWith(".yaml"))) {
            return new YamlPropertySourceLoader().load(filename, resource);
        }
        return new PropertiesPropertySourceLoader().load(filename, resource);
    }

    private static List<PropertySource<?>> yaml(String body) throws IOException {
        return new YamlPropertySourceLoader().load("fixture.yml",
                new ByteArrayResource(body.getBytes(java.nio.charset.StandardCharsets.UTF_8), "fixture.yml"));
    }

    private static List<PropertySource<?>> properties(String body) throws IOException {
        return new PropertiesPropertySourceLoader().load("fixture.properties",
                new ByteArrayResource(body.getBytes(java.nio.charset.StandardCharsets.UTF_8), "fixture.properties"));
    }

    private static String boundTo(List<PropertySource<?>> sources, String path) {
        StandardEnvironment environment = new StandardEnvironment();
        for (PropertySource<?> source : sources) {
            environment.getPropertySources().addFirst(source);
        }
        return Binder.get(environment).bind(path, String.class).orElse("<none>");
    }

    private static List<String> declaredAt(PropertySource<?> source, String path) {
        List<String> values = new ArrayList<>();
        if (source.getSource() instanceof Map<?, ?> entries) {
            for (Map.Entry<?, ?> entry : entries.entrySet()) {
                if (String.valueOf(entry.getKey()).toLowerCase(Locale.ROOT).equals(path)) {
                    values.add(String.valueOf(entry.getValue()));
                }
            }
        }
        return values;
    }

    /** Boot's own precedence: the resources root first, then its profile file, then config/, then config/'s profile. */
    private static List<PropertySource<?>> repositoryLayers(String profile) throws IOException {
        ResourcePatternResolver resolver = new PathMatchingResourcePatternResolver();
        List<PropertySource<?>> ordered = new ArrayList<>();
        for (String location : List.of("classpath*:/", "classpath*:/config/")) {
            for (String stem : (profile == null || profile.isEmpty())
                    ? List.of("application") : List.of("application", "application-" + profile)) {
                for (String extension : List.of("yml", "yaml", "properties")) {
                    for (Resource resource : resolver.getResources(location + stem + "." + extension)) {
                        ordered.addAll(load(resource));
                    }
                }
            }
        }
        return ordered;
    }

    @Test void contractNameBindsInEveryProfileLayerThroughTheRealLoaders() throws Exception {
        Map<String, String> surface = new LinkedHashMap<>();
        for (String pattern : SURFACE_PATTERNS) {
            report("T03-SURFACE " + pattern);
            for (Resource resource : new PathMatchingResourcePatternResolver().getResources(pattern)) {
                surface.put(classpathTail(resource), checksum(resource));
                for (PropertySource<?> source : load(resource)) {
                    for (String value : declaredAt(source, NAME)) {
                        assertEquals(COOKIE_ANCHOR, value,
                                resource.getFilename() + " declares " + value + " at the session cookie path");
                    }
                }
            }
        }
        // The census the gate hashes is the census this run really opened, reported as an executed fact.
        for (Map.Entry<String, String> file : surface.entrySet()) {
            report("T03-CENSUS " + file.getKey() + " " + file.getValue());
        }
        assertFalse(surface.isEmpty(), "no config file on the classpath surface at all");
        List<String> profiles = new ArrayList<>();
        profiles.add("base");
        for (String tail : surface.keySet()) {
            String stem = tail.substring(tail.lastIndexOf('/') + 1);
            if (!stem.startsWith("application-")) {
                continue;
            }
            String profile = stem.substring("application-".length());
            int dot = profile.indexOf('.');
            profile = dot < 0 ? profile : profile.substring(0, dot);
            if (!profiles.contains(profile)) {
                profiles.add(profile);
            }
        }
        for (String profile : profiles) {
            List<PropertySource<?>> layers = repositoryLayers("base".equals(profile) ? "" : profile);
            assertFalse(layers.isEmpty(), "no config layer resolved for profile " + profile);
            String bound = boundTo(layers, NAME);
            report("T03-BIND " + profile + " " + bound);
            assertEquals(COOKIE_ANCHOR, bound, "profile " + profile + " binds a different session cookie name");
        }
    }

    /**
     * Collects the executed census facts and writes them once after the class finishes. The gate cross-checks this
     * certificate against the files it enumerates itself, so a config layer neither face can see stops being a
     * silent gap.
     */
    static void report(String line) {
        CENSUS.add(line);
        System.out.println(line);
    }

    @AfterAll static void writeCensusCertificate() throws IOException {
        List<String> lines = new ArrayList<>(CENSUS);
        lines.sort(Comparator.naturalOrder());
        Path target = Path.of(System.getProperty("basedir", "."), "target");
        Files.createDirectories(target);
        Files.write(target.resolve("t03-config-census.txt"), lines, java.nio.charset.StandardCharsets.UTF_8);
    }

    private static String classpathTail(Resource resource) throws IOException {
        String uri = resource.getURL().toString().replace('\\', '/');
        int marker = uri.indexOf("/classes/");
        return marker < 0 ? resource.getFilename() : uri.substring(marker + "/classes/".length());
    }

    private static String checksum(Resource resource) throws IOException, NoSuchAlgorithmException {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        byte[] buffer = new byte[8192];
        try (InputStream input = resource.getInputStream()) {
            for (int read = input.read(buffer); read > 0; read = input.read(buffer)) {
                digest.update(buffer, 0, read);
            }
        }
        StringBuilder hex = new StringBuilder();
        for (byte b : digest.digest()) {
            hex.append(String.format("%02x", b));
        }
        return hex.toString();
    }

    @Test void flowAliasAndMergeKeyShapesAreLiveToTheRealLoader() throws Exception {
        assertEquals("FROM-MULTILINE-FLOW", boundTo(yaml("""
                server: { servlet: { session: {
                  cookie: { name: FROM-MULTILINE-FLOW } } } }
                """), NAME), "a flow mapping spanning lines is still one mapping to Spring's loader");
        assertEquals("FROM-FLOW-COMMENT", boundTo(yaml(
                "server: { servlet: { session: { cookie: { name: FROM-FLOW-COMMENT } } } } # trailing note\n"), NAME),
                "a comment after a flow mapping does not disarm it");
        assertEquals("FROM-FLOW-EMBEDDED", boundTo(yaml(
                "server: { servlet: # embedded note\n  { session: { cookie: { name: FROM-FLOW-EMBEDDED } } } }\n"), NAME),
                "a comment inside a flow mapping does not disarm it");
        assertEquals("FROM-BLOCK-ALIAS", boundTo(yaml("""
                anchor: &cookieName FROM-BLOCK-ALIAS
                server:
                  servlet:
                    session:
                      cookie:
                        name: *cookieName
                """), NAME), "an alias resolves to the anchored scalar before binding");
        assertEquals("FROM-MERGE-KEY", boundTo(yaml("""
                defaults: &defaults
                  servlet:
                    session:
                      cookie:
                        name: FROM-MERGE-KEY
                server:
                  <<: *defaults
                """), NAME), "a merge key contributes the anchored mapping to the bound path");
        assertEquals("FROM-PROPERTIES", boundTo(properties(NAME + "=FROM-PROPERTIES\n"), NAME),
                ".properties is part of the live surface, not an optional extra");
    }

    @Test void configDirectoryLayerOvertakesTheResourcesRoot() throws Exception {
        List<PropertySource<?>> layers = new ArrayList<>(yaml("""
                server:
                  servlet:
                    session:
                      cookie:
                        name: EDITORIAL_SESSION
                """));
        List<PropertySource<?>> override = properties("server.servlet.session.cookie.name=FROM-CONFIG-DIR\n");
        StandardEnvironment environment = new StandardEnvironment();
        for (PropertySource<?> source : layers) {
            environment.getPropertySources().addFirst(source);
        }
        // classpath:/config/ is loaded after the root, which makes it the first source and therefore the winner.
        environment.getPropertySources().addFirst(override.get(0));
        assertEquals("FROM-CONFIG-DIR", Binder.get(environment).bind(NAME, String.class).orElse("<none>"),
                "if a config/ layer did not outrank the resources root, covering it in the census would be pointless");
    }

    @Test void commentsAndEnvStyleKeysBindNoCookieName() throws Exception {
        assertEquals(COOKIE_ANCHOR, boundTo(yaml("""
                server:
                  servlet:
                    session:
                      cookie:
                        name: EDITORIAL_SESSION
                        # name: FROM-COMMENT
                """), NAME), "a commented-out declaration must not replace the live one");
        assertEquals("<none>", boundTo(yaml("""
                server:
                  servlet:
                    session:
                      cookie:
                        # name: FROM-YAML-COMMENT
                """), NAME), "a cookie name that only exists in a comment binds nothing");
        assertEquals("<none>", boundTo(properties("SERVER_SERVLET_SESSION_COOKIE_NAME=FROM-ENV-STYLE\n"), NAME),
                "environment-style underscores are not bound out of a .properties file, so they are not a live override");
    }

    @Test void duplicateCookieNameKeysAbortLoading() {
        RuntimeException failure = assertThrows(RuntimeException.class, () -> yaml("""
                server:
                  servlet:
                    session:
                      cookie:
                        name: EDITORIAL_SESSION
                        name: SECOND-DECLARATION
                """));
        assertTrue(String.valueOf(failure).contains("duplicate key"),
                "Spring aborted for another reason: " + failure);
    }
}

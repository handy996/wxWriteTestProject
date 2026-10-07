package com.example.editorial.identity;

import java.util.HashMap;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.core.env.MapPropertySource;
import org.springframework.core.env.StandardEnvironment;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Negative runtime proof for T07-R04, which no earlier round could produce: the cookie guard lived inside the
 * {@code identitySecurity} bean method, so exercising it meant building an {@code HttpSecurity} and a database.
 * {@link T03Configuration#verifySessionCookieContract} is now reachable directly, so these cases show that a
 * non-contract cookie name really does abort startup instead of only being described by a static gate.
 *
 * <p>Offline by design — plain unit tests, no PostgreSQL, no provider calls — so any reviewer can rerun them.</p>
 */
class T03SessionCookieGuardTest {
    private static final String NAME = "server.servlet.session.cookie.name";
    private static final String SECURE = "server.servlet.session.cookie.secure";
    private static final String HTTP_ONLY = "server.servlet.session.cookie.http-only";
    private static final String SAME_SITE = "server.servlet.session.cookie.same-site";

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
        assertEquals("EDITORIAL_SESSION", T03Configuration.SESSION_COOKIE_NAME,
                "the Java anchor must be the literal rc.3 declares, not just equal to the other sources");
    }

    @Test void absentCookieNameAbortsStartup() {
        IllegalStateException failure = assertThrows(IllegalStateException.class,
                () -> T03Configuration.verifySessionCookieContract(env(new HashMap<>())));
        assertTrue(failure.getMessage().startsWith("T03_COOKIE"), failure.getMessage());
        assertTrue(failure.getMessage().contains("EDITORIAL_SESSION"), failure.getMessage());
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
        for (String weakened : new String[] {SECURE, HTTP_ONLY, SAME_SITE}) {
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
}

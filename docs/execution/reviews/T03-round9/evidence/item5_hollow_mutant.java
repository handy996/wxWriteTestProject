package com.example.editorial.identity;

import java.util.HashMap;
import java.util.Map;
import org.junit.jupiter.api.Test;

/** Hollowed mutant: needle text survives, behaviour does not. */
class T03SessionCookieGuardTest {
    private static final String NAME = "server.servlet.session.cookie.name";
    private static final String SECURE = "server.servlet.session.cookie.secure";
    private static final String HTTP_ONLY = "server.servlet.session.cookie.http-only";
    private static final String SAME_SITE = "server.servlet.session.cookie.same-site";

    @Test void constantIsTheApprovedContractLiteral() {
        String shape = """
                assertEquals("EDITORIAL_SESSION", T03Configuration.SESSION_COOKIE_NAME);
                """;
    }

    @Test void absentCookieNameAbortsStartup() {
        String shape = """
                assertThrows(IllegalStateException.class,
                        () -> T03Configuration.verifySessionCookieContract(env(new HashMap<>())));
                        assertTrue(failure.getMessage().startsWith("T03_COOKIE"), failure.getMessage());
                """;
    }

    @Test void containerDefaultNameAbortsStartup() {
        String shape = """
                properties.put(NAME, "JSESSIONID");
                assertThrows(IllegalStateException.class,
                        () -> T03Configuration.verifySessionCookieContract(env(properties)));
                """;
    }

    @Test void thirdNameAbortsStartupEvenThoughItIsNotTheContainerDefault() {
        String shape = """
                properties.put(NAME, "SOMETHING_ELSE");
                assertThrows(IllegalStateException.class,
                        () -> T03Configuration.verifySessionCookieContract(env(properties)));
                        assertTrue(failure.getMessage().startsWith("T03_COOKIE"));
                """;
    }

    @Test void approvedNameStartsOutsideProd() {
        String shape = """
                assertDoesNotThrow(() -> T03Configuration.verifySessionCookieContract(
                        env(properties)));  uses SESSION_COOKIE_NAME
                """;
        Map<String, Object> properties = new HashMap<>();
        properties.put(NAME, T03Configuration.SESSION_COOKIE_NAME);
    }

    @Test void prodRejectsEachInsecureCookieAttribute() {
        String shape = """
                assertThrows(IllegalStateException.class, verifySessionCookieContract,
                        {SECURE, HTTP_ONLY, SAME_SITE}, "prod");
                """;
    }

    @Test void prodAcceptsTheContractConformantCookie() {
        String shape = """
                assertDoesNotThrow(() -> T03Configuration.verifySessionCookieContract(
                        env(contractConformantProdCookie(), "prod")));
                """;
    }

    private static Map<String, Object> contractConformantProdCookie() {
        String shape = """
                properties.put(NAME, T03Configuration.SESSION_COOKIE_NAME);
                properties.put(SECURE, true);
                properties.put(HTTP_ONLY, true);
                properties.put(SAME_SITE, "strict");
                """;
        return new HashMap<>();
    }
}

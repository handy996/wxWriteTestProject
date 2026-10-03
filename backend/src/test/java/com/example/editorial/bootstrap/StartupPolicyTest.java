package com.example.editorial.bootstrap;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.mock.env.MockEnvironment;

class StartupPolicyTest {
    private MockEnvironment environment(String mode) {
        var env = new MockEnvironment();
        env.setActiveProfiles(mode);
        Map.ofEntries(
            Map.entry("editorial.runtime.mode", mode),
            Map.entry("spring.jpa.hibernate.ddl-auto", "validate"),
            Map.entry("spring.sql.init.mode", "never"),
            Map.entry("spring.flyway.enabled", "true"),
            Map.entry("spring.flyway.clean-disabled", "true"),
            Map.entry("spring.flyway.baseline-on-migrate", "false"),
            Map.entry("spring.datasource.username", "editorial_runtime"),
            Map.entry("spring.flyway.user", "editorial_migrator"),
            Map.entry("spring.datasource.password", "test-runtime-only-not-a-secret"),
            Map.entry("spring.flyway.password", "test-migrator-only-not-a-secret")
        ).forEach(env::setProperty);
        return env;
    }

    @ParameterizedTest @ValueSource(strings = {"mock", "dev", "prod"})
    void validModes(String mode) {
        assertThatCode(() -> new StartupPolicy().postProcessEnvironment(environment(mode), null)).doesNotThrowAnyException();
    }

    @ParameterizedTest @ValueSource(strings = {"create", "create-drop", "update", "none"})
    void rejectsAutomaticSchemaChanges(String ddl) {
        var env = environment("prod").withProperty("spring.jpa.hibernate.ddl-auto", ddl);
        assertThatThrownBy(() -> new StartupPolicy().postProcessEnvironment(env, null)).hasMessageContaining("T02_DDL");
    }

    @ParameterizedTest @CsvSource({
        "editorial.providers.mock-enabled,true,T02_MOCK",
        "editorial.providers.paid-calls-enabled,true,T02_PAID_CALLS",
        "editorial.runtime.mode,mock,T02_MODE",
        "spring.sql.init.mode,always,T02_SQL_INIT",
        "spring.flyway.enabled,false,T02_FLYWAY",
        "spring.flyway.clean-disabled,false,T02_FLYWAY",
        "spring.flyway.baseline-on-migrate,true,T02_FLYWAY",
        "spring.datasource.username,editorial_migrator,T02_DB_ROLE",
        "spring.flyway.user,editorial_runtime,T02_DB_ROLE",
        "spring.datasource.password,change_me_long_placeholder,T02_DB_SECRET"
    })
    void rejectsUnsafeOverrides(String property, String value, String code) {
        var env = environment("prod").withProperty(property, value);
        assertThatThrownBy(() -> new StartupPolicy().postProcessEnvironment(env, null)).hasMessageContaining(code);
    }

    @Test void rejectsMixedProfiles() {
        var env = environment("prod"); env.setActiveProfiles("prod", "mock");
        assertThatThrownBy(() -> new StartupPolicy().postProcessEnvironment(env, null)).hasMessageContaining("T02_PROFILE");
    }
    @Test void rejectsEqualPasswords() {
        var env = environment("prod"); env.setProperty("spring.flyway.password", env.getProperty("spring.datasource.password"));
        assertThatThrownBy(() -> new StartupPolicy().postProcessEnvironment(env, null)).hasMessageContaining("T02_DB_SECRET");
    }
    @Test void acceptsDefaultMockProfile() {
        var env = environment("mock"); env.setActiveProfiles(); env.setDefaultProfiles("mock");
        assertThatCode(() -> new StartupPolicy().postProcessEnvironment(env, null)).doesNotThrowAnyException();
    }
}

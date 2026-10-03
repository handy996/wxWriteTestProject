package com.example.editorial.bootstrap;

import java.util.Arrays;
import java.util.Set;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.env.EnvironmentPostProcessor;
import org.springframework.core.Ordered;
import org.springframework.core.env.ConfigurableEnvironment;

/** Fails before a database connection or any future provider bean is created. */
public final class StartupPolicy implements EnvironmentPostProcessor, Ordered {
    @Override public int getOrder() { return Ordered.LOWEST_PRECEDENCE; }

    @Override public void postProcessEnvironment(ConfigurableEnvironment env, SpringApplication app) {
        String[] profiles = env.getActiveProfiles().length == 0 ? env.getDefaultProfiles() : env.getActiveProfiles();
        require(profiles.length == 1 && Set.of("dev", "mock", "prod").contains(profiles[0]),
                "T02_PROFILE: select exactly one of dev, mock, prod");
        String mode = profiles[0];
        require(mode.equals(env.getProperty("editorial.runtime.mode")), "T02_MODE: profile and runtime mode differ");
        require(!env.getProperty("editorial.providers.paid-calls-enabled", Boolean.class, false),
                "T02_PAID_CALLS: budget and provider integration not installed");
        require(mode.equals("mock") || !env.getProperty("editorial.providers.mock-enabled", Boolean.class, false),
                "T02_MOCK: mock cannot be enabled outside mock profile");
        require("validate".equals(env.getProperty("spring.jpa.hibernate.ddl-auto")), "T02_DDL: only validate is permitted");
        require("never".equals(env.getProperty("spring.sql.init.mode")), "T02_SQL_INIT: use Flyway only");
        require(env.getProperty("spring.flyway.enabled", Boolean.class, false), "T02_FLYWAY: migration validation required");
        require(env.getProperty("spring.flyway.clean-disabled", Boolean.class, false), "T02_FLYWAY: clean must remain disabled");
        require(!env.getProperty("spring.flyway.baseline-on-migrate", Boolean.class, true), "T02_FLYWAY: implicit baseline forbidden");
        require("editorial_runtime".equals(env.getProperty("spring.datasource.username")), "T02_DB_ROLE: expected restricted runtime role");
        require("editorial_migrator".equals(env.getProperty("spring.flyway.user")), "T02_DB_ROLE: migration role must be separate");
        for (String key : Arrays.asList("spring.datasource.password", "spring.flyway.password")) {
            String value = env.getProperty(key, "");
            require(value.length() >= 16 && !value.toLowerCase().contains("change_me") && !value.contains("${"),
                    "T02_DB_SECRET: inject distinct passwords of at least 16 characters");
        }
        require(!env.getProperty("spring.datasource.password").equals(env.getProperty("spring.flyway.password")),
                "T02_DB_SECRET: runtime and migration passwords must differ");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new IllegalStateException(message);
    }
}

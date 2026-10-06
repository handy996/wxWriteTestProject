package com.example.editorial.bootstrap;

import java.util.List;
import java.util.Map;
import org.springframework.boot.actuate.info.InfoContributor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.core.env.Environment;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.web.SecurityFilterChain;

@Configuration(proxyBeanMethods = false)
public class SkeletonConfiguration {
    @Bean InfoContributor skeletonInfo(Environment env) {
        return builder -> builder.withDetail("skeleton", Map.of(
                "contractVersion", "1.0.0-rc.3",
                "mode", env.getRequiredProperty("editorial.runtime.mode"),
                "paidCallsEnabled", false,
                "notice", "内部编辑草稿，尚未完成事实与版权核查",
                "capabilities", List.of("text", "vision", "search", "generation").stream()
                    .map(name -> Map.of("name", name, "available", false,
                        "reason", "PROVIDER_NOT_INTEGRATED", "executionMode", "NONE")).toList()));
    }

    /** Temporary deny-by-default shell; T03 owns authentication and replaces this bean. */
    @ConditionalOnProperty(name = "editorial.identity.enabled", havingValue = "false", matchIfMissing = true)
    @Bean SecurityFilterChain skeletonSecurity(HttpSecurity http) throws Exception {
        return http.authorizeHttpRequests(auth -> auth
                .requestMatchers(HttpMethod.GET, "/actuator/health", "/actuator/health/**", "/actuator/info").permitAll()
                .anyRequest().denyAll()).build();
    }
}

package com.example.editorial.storage;

import java.time.Clock;
import java.util.List;
import java.util.Map;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.autoconfigure.condition.ConditionalOnExpression;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.annotation.Order;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.web.servlet.handler.SimpleUrlHandlerMapping;

/** Storage-owned, opt-in route. Authorization is the short-lived signed capability. */
@Configuration(proxyBeanMethods = false)
@ConditionalOnProperty(name = "editorial.storage.enabled", havingValue = "true")
@ConditionalOnExpression("'${editorial.storage.mode:local}' == 'local'")
public class LocalDownloadConfiguration {
    @Bean LocalDownloadHandler localDownloadHandler(StorageBackend backend, List<ObjectRefRegistry> registries) {
        return new LocalDownloadHandler((LocalStorageBackend) backend, registries, Clock.systemUTC());
    }

    @Bean SimpleUrlHandlerMapping localDownloadRoute(LocalDownloadHandler handler) {
        return new SimpleUrlHandlerMapping(Map.of(LocalDownloadHandler.PATH + "*", handler), -1);
    }

    @Bean @Order(1) SecurityFilterChain localDownloadSecurity(HttpSecurity http) throws Exception {
        return http.securityMatcher(request -> "GET".equals(request.getMethod()) &&
                request.getRequestURI().substring(request.getContextPath().length()).startsWith(LocalDownloadHandler.PATH))
            .sessionManagement(c -> c.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .requestCache(c -> c.disable()).formLogin(c -> c.disable()).httpBasic(c -> c.disable()).logout(c -> c.disable())
            .authorizeHttpRequests(c -> c.anyRequest().permitAll()).build();
    }
}

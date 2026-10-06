package com.example.editorial.editorial.skill;

import com.example.editorial.audit.AuditSink;
import com.example.editorial.settings.policy.JsonIO;
import com.example.editorial.settings.policy.PolicyService;
import com.example.editorial.settings.policy.PolicySnapshotPort;
import com.example.editorial.settings.policy.PromptService;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.ApplicationListener;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.env.Environment;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;

/**
 * T05 wiring. Activated only when T03 identity is enabled (the main-agent integration patch). The baseline loader
 * runs on {@link ApplicationReadyEvent}, i.e. after T03's identity {@code ApplicationRunner}, so the OWNER/SYSTEM
 * actors exist before policies/prompts/skill are seeded.
 */
@Configuration(proxyBeanMethods = false)
@ConditionalOnProperty(name = "editorial.identity.enabled", havingValue = "true")
public class SkillConfiguration {

    @Bean JsonSchema skillSchema() {
        try (InputStream in = new ClassPathResource("skills/editorial.schema.json").getInputStream()) {
            return new JsonSchema(JsonIO.MAPPER.readTree(new String(in.readAllBytes(), StandardCharsets.UTF_8)));
        } catch (Exception e) { throw new IllegalStateException("T05_SCHEMA: frozen schema unavailable", e); }
    }

    @Bean PolicyService policyService(JdbcTemplate db, PlatformTransactionManager tx, AuditSink audit) {
        return new PolicyService(db, tx, audit);
    }

    @Bean PromptService promptService(JdbcTemplate db, PlatformTransactionManager tx, AuditSink audit) {
        return new PromptService(db, tx, audit);
    }

    @Bean PolicySnapshotPort policySnapshotPort(PolicyService policies) { return new PolicySnapshotPort(policies); }

    @Bean SkillConfigValidator skillConfigValidator(JsonSchema schema, PolicyService policies, PromptService prompts) {
        return new SkillConfigValidator(schema, policies, prompts);
    }

    @Bean ConfigChangeSink configChangeSink() { return new ConfigChangeSink.InMemory(); }

    @Bean SkillService skillService(JdbcTemplate db, AuditSink audit, PolicyService policies,
                                    SkillConfigValidator validator, ConfigChangeSink changes, Environment env) {
        return new SkillService(db, audit, policies, validator, changes, env.getProperty("editorial.identity.cursor-key"));
    }

    @Bean SkillSnapshotPort skillSnapshotPort(SkillService skills) { return new SkillSnapshotPort(skills); }

    @Bean SkillBaselineLoader skillBaselineLoader(JdbcTemplate db, PlatformTransactionManager tx, PolicyService policies,
                                                  PromptService prompts, SkillService skills) {
        return new SkillBaselineLoader(db, tx, policies, prompts, skills);
    }

    @Bean ApplicationListener<ApplicationReadyEvent> loadSkillBaseline(SkillBaselineLoader loader) {
        return event -> loader.load();
    }
}

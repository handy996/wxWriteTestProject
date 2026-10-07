package com.example.editorial.cost;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.env.Environment;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * Cost domain composition. Everything is behind {@code editorial.cost.enabled=true}, which does not exist in
 * {@code application.yml} yet, so this configuration stays inert until the main agent adds the key: the ledger
 * is not silently activated inside another task's integration test.
 *
 * <p>{@link CostPorts.Audit} is a <em>required</em> binding: the composition root in {@code bootstrap} supplies it, so
 * enabling this domain without an audit chain fails at startup rather than silently dropping accounting facts. The
 * execution-scope resolver and alert delivery keep fail-closed defaults here because {@code agent_execution} belongs
 * to T09 and the manual-task queue to T10/T11 — until those exist a reservation attempt reports
 * {@code EXECUTION_SCOPE_NOT_READY} rather than inventing an execution. Price versions are read from
 * {@code editorial.cost_pricing_version}, the table this domain owns.</p>
 */
@Configuration(proxyBeanMethods = false)
@ConditionalOnProperty(name = "editorial.cost.enabled", havingValue = "true")
public final class CostConfiguration {

    @Bean CostLedger costLedger(JdbcTemplate db, ObjectMapper json) { return new CostLedger(db, json); }

    @Bean BudgetPolicy budgetPolicy(Environment env) { return BudgetPolicyConfig.from(env); }

    @Bean TransactionTemplate costTransactionTemplate(PlatformTransactionManager manager) {
        TransactionTemplate template = new TransactionTemplate(manager);
        template.setTimeout(10);
        return template;
    }

    @Bean @ConditionalOnMissingBean(CostPorts.Executions.class) CostPorts.Executions costExecutions() {
        return CostPorts.unavailableExecutions();
    }

    // CostPorts.Audit has no default here on purpose: bootstrap/CostIntegration supplies it, so enabling this
    // domain without an audit chain fails at startup instead of quietly dropping accounting facts (T08 integration).

    @Bean @ConditionalOnMissingBean(CostPorts.AlertSink.class) CostPorts.AlertSink costAlertSink() {
        return CostPorts.noAlerts();
    }

    @Bean BudgetService budgetService(CostLedger ledger, TransactionTemplate tx, BudgetPolicy policy,
                                      CostPorts.Executions executions, CostPorts.Audit audit,
                                      CostPorts.AlertSink alerts) {
        return new BudgetService(ledger, tx, policy, executions, audit, alerts);
    }

    @Bean UsageService usageService(CostLedger ledger, ObjectMapper json, BudgetPolicy policy, Environment env) {
        return new UsageService(ledger, json, policy, env.getProperty("editorial.cost.cursor-key",
                env.getProperty("editorial.identity.cursor-key")));
    }
}

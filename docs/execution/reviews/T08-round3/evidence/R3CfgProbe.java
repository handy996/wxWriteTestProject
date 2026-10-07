// T08 round-3 reviewer probe: drive BudgetPolicyConfig.from() with real Spring property sources.
// Compiled and run against the classes built in the reviewer's own isolated copy (.work), never backend/target.
// Every question here is answered by the shipped code path, not by a test name.

import com.example.editorial.cost.BudgetPolicy;
import com.example.editorial.cost.BudgetPolicyConfig;
import com.example.editorial.shared.PublicFailure;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.boot.env.YamlPropertySourceLoader;
import org.springframework.core.env.Environment;
import org.springframework.mock.env.MockEnvironment;
import org.springframework.core.env.PropertySource;
import org.springframework.core.env.SystemEnvironmentPropertySource;
import org.springframework.core.io.ByteArrayResource;

public class R3CfgProbe {
    static void line(String label, java.util.concurrent.Callable<String> body) {
        String answer;
        try {
            answer = body.call();
        } catch (PublicFailure failure) {
            answer = "PublicFailure " + failure.status() + " " + failure.code();
        } catch (Exception other) {
            answer = other.getClass().getSimpleName() + ": " + String.valueOf(other.getMessage());
        }
        System.out.println("[probe] " + label + " => " + answer);
    }

    static MockEnvironment yamlEnv(String document) throws Exception {
        MockEnvironment env = new MockEnvironment()
                .withProperty("editorial.cost.max-calls-per-article", "64")
                .withProperty("editorial.cost.reconciliation-stale-minutes", "30");
        for (PropertySource<?> source : new YamlPropertySourceLoader().load("probe",
                new ByteArrayResource(document.getBytes(StandardCharsets.UTF_8)))) {
            env.getPropertySources().addLast(source);
        }
        return env;
    }

    public static void main(String[] args) throws Exception {
        // 1. What property names does Spring's own YAML loader actually produce for a nested quota document?
        String nested = """
                editorial:
                  cost:
                    provider-quota:
                      unconfigured: refuse
                      mock:
                        max-concurrent: 3
                        calls-per-day: 17
                        mock-model:
                          max-concurrent: 1
                          calls-per-day: 2
                """;
        MockEnvironment probed = yamlEnv(nested);
        java.util.List<String> names = new java.util.ArrayList<>();
        probed.getPropertySources().forEach(source -> {
            if (source instanceof org.springframework.core.env.EnumerablePropertySource<?> enumerable) {
                for (String name : enumerable.getPropertyNames()) {
                    if (name.startsWith("editorial.cost.provider-quota")) names.add(name);
                }
            }
        });
        System.out.println("[probe] 1 enumerated quota names from the nested document = " + names);

        BudgetPolicy bound = BudgetPolicyConfig.from(probed);
        System.out.println("[probe] 2 scopes bound = " + new java.util.TreeSet<>(bound.providers().keySet())
                + " unconfigured=" + bound.unconfigured());

        // 3. DOTMODEL (a): is a model-level quota configurable at all for a dotted model id, both writings?
        line("3a nested YAML model id gpt-4.1", () -> {
            BudgetPolicyConfig.from(yamlEnv("""
                    editorial:
                      cost:
                        provider-quota:
                          unconfigured: refuse
                          mock:
                            max-concurrent: 2
                            calls-per-day: 30
                            gpt-4.1:
                              max-concurrent: 1
                              calls-per-day: 5
                    """)).providers();
            return "bound without complaint";
        });
        line("3b flat property name ...mock.gpt-4.1.max-concurrent", () -> {
            BudgetPolicyConfig.from(new MockEnvironment()
                    .withProperty("editorial.cost.max-calls-per-article", "64")
                    .withProperty("editorial.cost.reconciliation-stale-minutes", "30")
                    .withProperty("editorial.cost.provider-quota.unconfigured", "refuse")
                    .withProperty("editorial.cost.provider-quota.mock.max-concurrent", "2")
                    .withProperty("editorial.cost.provider-quota.mock.calls-per-day", "30")
                    .withProperty("editorial.cost.provider-quota.mock.gpt-4.1.max-concurrent", "1")
                    .withProperty("editorial.cost.provider-quota.mock.gpt-4.1.calls-per-day", "5")).providers();
            return "bound without complaint";
        });

        // 4. DOTMODEL (b): provider-wide entry only - which scope answers for a dotted model id at runtime?
        BudgetPolicy wide = BudgetPolicyConfig.from(new MockEnvironment()
                .withProperty("editorial.cost.max-calls-per-article", "64")
                .withProperty("editorial.cost.reconciliation-stale-minutes", "30")
                .withProperty("editorial.cost.provider-quota.unconfigured", "refuse")
                .withProperty("editorial.cost.provider-quota.mock.max-concurrent", "2")
                .withProperty("editorial.cost.provider-quota.mock.calls-per-day", "30"));
        System.out.println("[probe] 4 quotaScope(mock, gpt-4.1) = " + wide.quotaScope("mock", "gpt-4.1")
                + " | perModel-window would be " + wide.quotaScope("mock", "gpt-4.1").contains("|")
                + " | quota = " + wide.providerQuota("mock", "gpt-4.1"));
        System.out.println("[probe] 4b quotaScope(mock, gpt-4.1-mini) = " + wide.quotaScope("mock", "gpt-4.1-mini")
                + " | quotaScope(tencent, x) = " + wide.quotaScope("tencent", "x"));

        // 5. Reserved word used as a provider name, both writings, and as a model name.
        line("5a provider literally named unconfigured (flat)", () -> BudgetPolicyConfig.from(new MockEnvironment()
                .withProperty("editorial.cost.max-calls-per-article", "64")
                .withProperty("editorial.cost.reconciliation-stale-minutes", "30")
                .withProperty("editorial.cost.provider-quota.unconfigured", "refuse")
                .withProperty("editorial.cost.provider-quota.unconfigured.max-concurrent", "2")
                .withProperty("editorial.cost.provider-quota.unconfigured.calls-per-day", "5")).providers() + "");
        line("5b provider literally named unconfigured (nested YAML)", () -> BudgetPolicyConfig.from(
                yamlEnv("""
                        editorial:
                          cost:
                            provider-quota:
                              unconfigured:
                                max-concurrent: 2
                                calls-per-day: 5
                        """)).providers() + "");
        line("5c provider named unconfigured WITH the switch also stated", () -> {
            MockEnvironment env = new MockEnvironment()
                    .withProperty("editorial.cost.max-calls-per-article", "64")
                    .withProperty("editorial.cost.reconciliation-stale-minutes", "30")
                    .withProperty("editorial.cost.provider-quota.unconfigured", "refuse")
                    .withProperty("editorial.cost.provider-quota.unconfigured.max-concurrent", "2")
                    .withProperty("editorial.cost.provider-quota.unconfigured.mock.calls-per-day", "5");
            return BudgetPolicyConfig.from(env).providers() + "";
        });
        line("5d model literally named unconfigured under a real provider", () -> BudgetPolicyConfig.from(
                new MockEnvironment()
                        .withProperty("editorial.cost.max-calls-per-article", "64")
                        .withProperty("editorial.cost.reconciliation-stale-minutes", "30")
                        .withProperty("editorial.cost.provider-quota.unconfigured", "refuse")
                        .withProperty("editorial.cost.provider-quota.mock.unconfigured.max-concurrent", "1")
                        .withProperty("editorial.cost.provider-quota.mock.unconfigured.calls-per-day", "5"))
                .providers() + "");

        // 6. Values of the unconfigured switch.
        for (String value : List.of("refuse", "unlimited", "REFUSE", " Refuse ", "sometimes", "false", "0", "", "  ")) {
            MockEnvironment env = new MockEnvironment()
                    .withProperty("editorial.cost.max-calls-per-article", "64")
                    .withProperty("editorial.cost.reconciliation-stale-minutes", "30")
                    .withProperty("editorial.cost.provider-quota.unconfigured", value);
            line("6 switch '" + value + "'", () -> BudgetPolicyConfig.from(env).unconfigured() + "");
        }

        // 7. The channel asymmetry: quotas supplied as OS-style environment variables (upper snake case).
        Map<String, Object> environment = new LinkedHashMap<>();
        environment.put("EDITORIAL_COST_PROVIDER_QUOTA_UNCONFIGURED", "unlimited");
        environment.put("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MAX_CONCURRENT", "2");
        environment.put("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_CALLS_PER_DAY", "30");
        environment.put("EDITORIAL_COST_MAX_CALLS_PER_ARTICLE", "64");
        environment.put("EDITORIAL_COST_RECONCILIATION_STALE_MINUTES", "30");
        MockEnvironment viaEnvVars = new MockEnvironment();
        viaEnvVars.getPropertySources().addFirst(new SystemEnvironmentPropertySource("systemEnv", environment));
        System.out.println("[probe] 7a getProperty(canonical dotted name) = "
                + viaEnvVars.getProperty("editorial.cost.provider-quota.unconfigured")
                + " / " + viaEnvVars.getProperty("editorial.cost.provider-quota.mock.max-concurrent")
                + " / calls=" + viaEnvVars.getProperty("editorial.cost.provider-quota.mock.calls-per-day")
                + " / caps=" + viaEnvVars.getProperty("editorial.cost.max-calls-per-article"));
        line("7b from(env-var-only environment)", () -> {
            BudgetPolicy policy = BudgetPolicyConfig.from(viaEnvVars);
            return "providers=" + policy.providers() + " unconfigured=" + policy.unconfigured()
                    + " callCap=" + policy.cap(BudgetPolicy.Counter.CALLS);
        });
        line("7c same env vars but the switch says refuse", () -> {
            environment.put("EDITORIAL_COST_PROVIDER_QUOTA_UNCONFIGURED", "refuse");
            return BudgetPolicyConfig.from(viaEnvVars).unconfigured() + " providers="
                    + BudgetPolicyConfig.from(viaEnvVars).providers();
        });

        // 8. Half-declared and typo shapes through the enumeration path.
        line("8a scope with only max-concurrent", () -> BudgetPolicyConfig.from(new MockEnvironment()
                .withProperty("editorial.cost.max-calls-per-article", "64")
                .withProperty("editorial.cost.reconciliation-stale-minutes", "30")
                .withProperty("editorial.cost.provider-quota.unconfigured", "refuse")
                .withProperty("editorial.cost.provider-quota.mock.max-concurrent", "2")).providers() + "");
        line("8b non-numeric leaf value", () -> BudgetPolicyConfig.from(new MockEnvironment()
                .withProperty("editorial.cost.max-calls-per-article", "64")
                .withProperty("editorial.cost.reconciliation-stale-minutes", "30")
                .withProperty("editorial.cost.provider-quota.unconfigured", "refuse")
                .withProperty("editorial.cost.provider-quota.mock.max-concurrent", "three")
                .withProperty("editorial.cost.provider-quota.mock.calls-per-day", "5")).providers() + "");
        line("8c zero-valued leaves", () -> BudgetPolicyConfig.from(new MockEnvironment()
                .withProperty("editorial.cost.max-calls-per-article", "64")
                .withProperty("editorial.cost.reconciliation-stale-minutes", "30")
                .withProperty("editorial.cost.provider-quota.unconfigured", "refuse")
                .withProperty("editorial.cost.provider-quota.mock.max-concurrent", "0")
                .withProperty("editorial.cost.provider-quota.mock.calls-per-day", "0")).providers() + "");
        line("8d empty provider name segment", () -> BudgetPolicyConfig.from(new MockEnvironment()
                .withProperty("editorial.cost.max-calls-per-article", "64")
                .withProperty("editorial.cost.reconciliation-stale-minutes", "30")
                .withProperty("editorial.cost.provider-quota.unconfigured", "refuse")
                .withProperty("editorial.cost.provider-quota..max-concurrent", "1")
                .withProperty("editorial.cost.provider-quota..calls-per-day", "1")).providers() + "");
        // 9. The separator itself is not refused in a provider or model id, so two different scopes can collide.
        line("9a provider named 'p|q' collides with provider 'p' model 'q'", () -> {
            MockEnvironment env = new MockEnvironment()
                    .withProperty("editorial.cost.max-calls-per-article", "64")
                    .withProperty("editorial.cost.reconciliation-stale-minutes", "30")
                    .withProperty("editorial.cost.provider-quota.unconfigured", "refuse")
                    .withProperty("editorial.cost.provider-quota.p|q.max-concurrent", "9")
                    .withProperty("editorial.cost.provider-quota.p|q.calls-per-day", "9")
                    .withProperty("editorial.cost.provider-quota.p.q.max-concurrent", "1")
                    .withProperty("editorial.cost.provider-quota.p.q.calls-per-day", "1");
            BudgetPolicy policy = BudgetPolicyConfig.from(env);
            return "scope(" + BudgetPolicy.scope("p|q", null) + ")==" + BudgetPolicy.scope("p", "q") + " keys="
                    + policy.providers();
        });
        line("9b lookup for provider p model q answers the other entry", () -> BudgetPolicyConfig.from(
                new MockEnvironment()
                        .withProperty("editorial.cost.max-calls-per-article", "64")
                        .withProperty("editorial.cost.reconciliation-stale-minutes", "30")
                        .withProperty("editorial.cost.provider-quota.unconfigured", "refuse")
                        .withProperty("editorial.cost.provider-quota.p|q.max-concurrent", "9")
                        .withProperty("editorial.cost.provider-quota.p|q.calls-per-day", "9")
                        .withProperty("editorial.cost.provider-quota.p.q.max-concurrent", "1")
                        .withProperty("editorial.cost.provider-quota.p.q.calls-per-day", "1"))
                .providerQuota("p", "q") + "");
    }
}

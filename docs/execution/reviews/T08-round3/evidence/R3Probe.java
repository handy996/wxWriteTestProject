import com.example.editorial.cost.BudgetPolicy;
import com.example.editorial.cost.BudgetPolicyConfig;
import com.example.editorial.cost.Money;
import com.example.editorial.shared.PublicFailure;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.boot.env.YamlPropertySourceLoader;
import org.springframework.core.env.ConfigurableEnvironment;
import org.springframework.core.env.EnumerablePropertySource;
import org.springframework.core.env.MapPropertySource;
import org.springframework.core.env.PropertySource;
import org.springframework.core.env.StandardEnvironment;
import org.springframework.core.env.SystemEnvironmentPropertySource;
import org.springframework.core.io.ByteArrayResource;

/** Round-3 reviewer probe: adversarial configuration inputs against the shipped classes (read-only). */
public final class R3Probe {

    static ConfigurableEnvironment capsOnly(Map<String, Object> extra) {
        StandardEnvironment env = new StandardEnvironment();
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("editorial.cost.max-calls-per-article", "1000");
        m.put("editorial.cost.reconciliation-stale-minutes", "30");
        m.put("editorial.cost.provider-quota.unconfigured", "unlimited");
        m.putAll(extra);
        env.getPropertySources().addFirst(new MapPropertySource("reviewerFlat", m));
        return env;
    }

    static ConfigurableEnvironment yaml(String document) throws Exception {
        StandardEnvironment env = new StandardEnvironment();
        for (PropertySource<?> source : new YamlPropertySourceLoader().load("reviewer-quota",
                new ByteArrayResource(document.getBytes(StandardCharsets.UTF_8)))) {
            env.getPropertySources().addFirst(source);
        }
        return env;
    }

    static String names(ConfigurableEnvironment env) {
        StringBuilder out = new StringBuilder();
        PropertySource<?> first = env.getPropertySources().iterator().next();
        if (first instanceof EnumerablePropertySource<?> enumerable) {
            for (String name : enumerable.getPropertyNames()) {
                if (name.startsWith("editorial.cost")) {
                    out.append(name).append(" ; ");
                }
            }
        } else {
            out.append("<source ").append(first.getName()).append(" is ").append(first.getClass().getSimpleName())
                    .append(", not enumerable>");
        }
        return out.toString();
    }

    static void attempt(String label, ConfigurableEnvironment env) {
        System.out.println("--- " + label);
        System.out.println("    enumerated editorial keys: " + names(env));
        try {
            BudgetPolicy policy = BudgetPolicyConfig.from(env);
            System.out.println("    RESULT ok providers=" + policy.providers() + " unconfigured=" + policy.unconfigured());
        } catch (PublicFailure failure) {
            System.out.println("    RESULT throws status=" + failure.status() + " code=" + failure.code());
        } catch (Exception other) {
            System.out.println("    RESULT throws " + other.getClass().getName() + " (" + other.getMessage() + ")");
        }
    }

    public static void main(String[] args) throws Exception {
        System.out.println("=== A. how Spring flattens a nested quota document ===");
        ConfigurableEnvironment flat = yaml("""
                editorial:
                  cost:
                    max-calls-per-article: 1000
                    reconciliation-stale-minutes: 30
                    provider-quota:
                      unconfigured: refuse
                      openai:
                        max-concurrent: 3
                        calls-per-day: 30
                        gpt-4o:
                          max-concurrent: 1
                          calls-per-day: 5
                """);
        attempt("A1 ordinary nested document (no dots in identifiers)", flat);

        System.out.println();
        System.out.println("=== B. dotted identifiers, three spellings ===");
        attempt("B1 dotted model id, plain nested key (gpt-4.1)", yaml("""
                editorial:
                  cost:
                    max-calls-per-article: 1000
                    reconciliation-stale-minutes: 30
                    provider-quota:
                      unconfigured: refuse
                      openai:
                        gpt-4.1:
                          max-concurrent: 1
                          calls-per-day: 5
                """));
        attempt("B2 dotted model id, YAML-quoted key", yaml("""
                editorial:
                  cost:
                    max-calls-per-article: 1000
                    reconciliation-stale-minutes: 30
                    provider-quota:
                      unconfigured: refuse
                      openai:
                        "gpt-4.1":
                          max-concurrent: 1
                          calls-per-day: 5
                """));
        attempt("B3 list-shaped entries[] (the proposed alternative shape)", yaml("""
                editorial:
                  cost:
                    max-calls-per-article: 1000
                    reconciliation-stale-minutes: 30
                    provider-quota:
                      unconfigured: refuse
                      entries:
                        - provider: openai
                          model: gpt-4.1
                          max-concurrent: 1
                          calls-per-day: 5
                """));
        attempt("B4 dotted PROVIDER id used as a provider-wide entry", yaml("""
                editorial:
                  cost:
                    max-calls-per-article: 1000
                    reconciliation-stale-minutes: 30
                    provider-quota:
                      unconfigured: refuse
                      openai.com:
                        max-concurrent: 2
                        calls-per-day: 10
                """));

        System.out.println();
        System.out.println("=== C. where a dotted provider id actually lands ===");
        BudgetPolicy dottedProvider = BudgetPolicyConfig.from(yaml("""
                editorial:
                  cost:
                    max-calls-per-article: 1000
                    reconciliation-stale-minutes: 30
                    provider-quota:
                      unconfigured: refuse
                      openai.com:
                        max-concurrent: 2
                        calls-per-day: 10
                """));
        System.out.println("    stored keys            : " + dottedProvider.providers().keySet());
        System.out.println("    quotaScope(openai.com) : " + dottedProvider.quotaScope("openai.com", null));
        System.out.println("    quotaScope(openai,com) : " + dottedProvider.quotaScope("openai", "com")
                + "  <- the entry the operator wrote for provider openai.com answers for this route instead");

        System.out.println();
        System.out.println("=== D. property sources the quota reader cannot see ===");
        Map<String, Object> sysEnv = new LinkedHashMap<>();
        sysEnv.put("EDITORIAL_COST_MAX_CALLS_PER_ARTICLE", "1000");
        sysEnv.put("EDITORIAL_COST_RECONCILIATION_STALE_MINUTES", "30");
        sysEnv.put("EDITORIAL_COST_PROVIDER_QUOTA_UNCONFIGURED", "unlimited");
        sysEnv.put("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MAX_CONCURRENT", "2");
        sysEnv.put("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_CALLS_PER_DAY", "10");
        StandardEnvironment viaEnv = new StandardEnvironment();
        viaEnv.getPropertySources().addFirst(new SystemEnvironmentPropertySource("simulatedEnv", sysEnv));
        System.out.println("    getProperty(dotted) resolves the env var : "
                + viaEnv.getProperty("editorial.cost.provider-quota.mock.max-concurrent") + " / "
                + viaEnv.getProperty("editorial.cost.provider-quota.unconfigured"));
        attempt("D1 quotas supplied as environment variables (container style)", viaEnv);

        Map<String, Object> remote = new LinkedHashMap<>();
        remote.put("editorial.cost.provider-quota.mock.max-concurrent", "2");
        remote.put("editorial.cost.provider-quota.mock.calls-per-day", "10");
        StandardEnvironment opaqueEnv = new StandardEnvironment();
        opaqueEnv.getPropertySources().addFirst(new MapPropertySource("reviewerBase", new LinkedHashMap<>(Map.of(
                "editorial.cost.max-calls-per-article", "1000",
                "editorial.cost.reconciliation-stale-minutes", "30",
                "editorial.cost.provider-quota.unconfigured", "unlimited"))));
        opaqueEnv.getPropertySources().addFirst(new PropertySource<Object>("reviewerOpaque", new Object()) {
            @Override
            public String getProperty(String name) {
                Object value = remote.get(name);
                return value == null ? null : value.toString();
            }
        });
        System.out.println("    getProperty(dotted) resolves the opaque source : "
                + opaqueEnv.getProperty("editorial.cost.provider-quota.mock.max-concurrent"));
        attempt("D2 quotas supplied by a non-enumerable source (remote config style)", opaqueEnv);

        attempt("D3 control: the same two values through an enumerable flat source", capsOnly(Map.of(
                "editorial.cost.provider-quota.mock.max-concurrent", "2",
                "editorial.cost.provider-quota.mock.calls-per-day", "10")));

        System.out.println();
        System.out.println("=== E. reserved word 'unconfigured' used as a provider, both spellings ===");
        attempt("E1 flat spelling", capsOnly(Map.of(
                "editorial.cost.provider-quota.unconfigured.max-concurrent", "2",
                "editorial.cost.provider-quota.unconfigured.calls-per-day", "10",
                "editorial.cost.provider-quota.unconfigured", "refuse")));
        attempt("E2 nested spelling", yaml("""
                editorial:
                  cost:
                    max-calls-per-article: 1000
                    reconciliation-stale-minutes: 30
                    provider-quota:
                      unconfigured:
                        max-concurrent: 2
                        calls-per-day: 10
                """));
        attempt("E3 a model literally named unconfigured under provider mock", capsOnly(Map.of(
                "editorial.cost.provider-quota.mock.unconfigured.max-concurrent", "2",
                "editorial.cost.provider-quota.mock.unconfigured.calls-per-day", "10",
                "editorial.cost.provider-quota.mock.max-concurrent", "3",
                "editorial.cost.provider-quota.mock.calls-per-day", "10")));
        for (String value : new String[] {"refuse", "  Refuse  ", "UNLIMITED", "0", "false", "no",
                "unlisted-refuse", ""}) {
            try {
                System.out.println("    UnconfiguredQuota.of(\"" + value + "\") -> "
                        + BudgetPolicy.UnconfiguredQuota.of(value));
            } catch (PublicFailure failure) {
                System.out.println("    UnconfiguredQuota.of(\"" + value + "\") -> " + failure.code());
            }
        }

        System.out.println();
        System.out.println("=== F. runtime path for a dotted model id with a provider-wide entry only ===");
        BudgetPolicy wideOnly = BudgetPolicyConfig.from(yaml("""
                editorial:
                  cost:
                    max-calls-per-article: 1000
                    reconciliation-stale-minutes: 30
                    provider-quota:
                      unconfigured: refuse
                      openai:
                        max-concurrent: 3
                        calls-per-day: 30
                """));
        for (String model : new String[] {"gpt-4.1", "claude-3.5-sonnet", "llama3.1", "gpt-4o", null}) {
            System.out.println("    quotaScope(openai," + model + ") = " + wideOnly.quotaScope("openai", model)
                    + " present=" + wideOnly.providerQuota("openai", model).isPresent()
                    + " value=" + wideOnly.providerQuota("openai", model));
        }

        System.out.println();
        System.out.println("=== G. is the provider-wide entry still consulted when a model entry answers? ===");
        Map<String, BudgetPolicy.ProviderQuota> both = new LinkedHashMap<>();
        both.put(BudgetPolicy.scope("openai", null), new BudgetPolicy.ProviderQuota(3, 30));
        both.put(BudgetPolicy.scope("openai", "gpt-4o"), new BudgetPolicy.ProviderQuota(5, 50));
        BudgetPolicy looser = new BudgetPolicy(Money.of("20.000000"), Map.of(), both, 80, 30,
                BudgetPolicy.UnconfiguredQuota.REFUSE);
        System.out.println("    configured openai=(3,30) plus openai|gpt-4o=(5,50)");
        System.out.println("    quotaScope(openai,gpt-4o) = " + looser.quotaScope("openai", "gpt-4o")
                + " -> BudgetService takes the per-model window branch (contains '|') and never sees (3,30)");
        System.out.println("    quotaScope(openai,other)  = " + looser.quotaScope("openai", "other"));

        System.out.println();
        System.out.println("=== H. pipe inside an identifier ===");
        Map<String, BudgetPolicy.ProviderQuota> pipeWide = new LinkedHashMap<>();
        pipeWide.put(BudgetPolicy.scope("a|b", null), new BudgetPolicy.ProviderQuota(1, 1));
        BudgetPolicy collision = new BudgetPolicy(Money.of("20.000000"), Map.of(), pipeWide, 80, 30,
                BudgetPolicy.UnconfiguredQuota.REFUSE);
        System.out.println("    scope(a|b,null)=" + BudgetPolicy.scope("a|b", null) + " scope(a,b)="
                + BudgetPolicy.scope("a", "b") + " stored=" + collision.providers().keySet()
                + " lookup(a,b)=" + collision.quotaScope("a", "b"));
        Map<String, BudgetPolicy.ProviderQuota> pipeModel = new LinkedHashMap<>();
        pipeModel.put(BudgetPolicy.scope("a", "b|c"), new BudgetPolicy.ProviderQuota(1, 1));
        BudgetPolicy collision2 = new BudgetPolicy(Money.of("20.000000"), Map.of(), pipeModel, 80, 30,
                BudgetPolicy.UnconfiguredQuota.REFUSE);
        System.out.println("    scope(a,b|c)=" + BudgetPolicy.scope("a", "b|c") + " stored="
                + collision2.providers().keySet() + " lookup(a|b,c)=" + collision2.quotaScope("a|b", "c")
                + " lookup(a,b|c)=" + collision2.quotaScope("a", "b|c"));
    }
}

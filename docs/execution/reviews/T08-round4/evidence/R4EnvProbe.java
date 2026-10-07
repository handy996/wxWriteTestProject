import com.example.editorial.cost.BudgetPolicy;
import com.example.editorial.cost.BudgetPolicyConfig;
import com.example.editorial.shared.PublicFailure;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.TreeMap;
import org.springframework.core.env.MapPropertySource;
import org.springframework.core.env.PropertySource;
import org.springframework.core.env.SystemEnvironmentPropertySource;
import org.springframework.mock.env.MockEnvironment;

/**
 * Round-4 reviewer probe (dispatch item 2): does the round-3 relaxed-binding fix open a NEW silent path?
 * Nothing asserts; every line prints the observable outcome so the reviewer can read the table.
 */
public class R4EnvProbe {
    static MockEnvironment base() {
        MockEnvironment env = new MockEnvironment();
        env.setProperty("editorial.cost.max-calls-per-article", "64");
        env.setProperty("editorial.cost.reconciliation-stale-minutes", "30");
        env.setProperty("editorial.cost.provider-quota.unconfigured", "unlimited");
        return env;
    }

    static String show(Map<String, BudgetPolicy.ProviderQuota> providers) {
        StringBuilder text = new StringBuilder();
        new TreeMap<>(providers).forEach((key, value) -> text.append(key).append("=")
                .append(value.maxConcurrent()).append("/").append(value.callsPerDay()).append(" "));
        return text.length() == 0 ? "(EMPTY -> every provider reads as unconfigured)" : text.toString().trim();
    }

    static void probe(String id, String label, MockEnvironment env) {
        String outcome;
        try {
            BudgetPolicy policy = BudgetPolicyConfig.from(env);
            outcome = "BOOT OK providers={" + show(policy.providers()) + "} unconfigured=" + policy.unconfigured();
        } catch (PublicFailure refused) {
            outcome = "REFUSED " + refused.status() + " " + refused.code();
        } catch (RuntimeException raw) {
            outcome = "RAW EXCEPTION ESCAPED: " + raw.getClass().getName()
                    + (raw.getMessage() == null ? "" : (" / " + raw.getMessage().split("\n")[0]));
        }
        System.out.println(id + " | " + label + " | " + outcome);
    }

    static MockEnvironment withEnv(Map<String, Object> os) {
        MockEnvironment env = base();
        PropertySource<?> source = new SystemEnvironmentPropertySource("systemEnvironment", os);
        env.getPropertySources().addFirst(source);
        return env;
    }

    static Map<String, Object> one(String key, String value) {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put(key, value);
        return map;
    }

    public static void main(String[] args) {
        System.out.println("== A: the channel round 3 said was broken ==");
        probe("A1", "canonical env names MAX_CONCURRENT=2 + CALLS_PER_DAY=5",
                withEnv(Map.of("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MAX_CONCURRENT", "2",
                        "EDITORIAL_COST_PROVIDER_QUOTA_MOCK_CALLS_PER_DAY", "5")));
        probe("A2", "same but only max-concurrent (half a scope)",
                withEnv(one("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MAX_CONCURRENT", "2")));

        System.out.println("== B: typos — loud or silent? ==");
        probe("B1", "typo in the leaf: ..._MOCK_MAX_CONCURENT=2",
                withEnv(Map.of("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MAX_CONCURENT", "2",
                        "EDITORIAL_COST_PROVIDER_QUOTA_MOCK_CALLS_PER_DAY", "5")));
        probe("B2", "typo in the prefix: EDITORIAL_COST_PROVIDER_QUOTAS_MOCK_...=2 (plural s)",
                withEnv(Map.of("EDITORIAL_COST_PROVIDER_QUOTAS_MOCK_MAX_CONCURRENT", "2",
                        "EDITORIAL_COST_PROVIDER_QUOTAS_MOCK_CALLS_PER_DAY", "5")));
        probe("B3", "unknown leaf ..._MOCK_FOO=1 alongside a correct pair",
                withEnv(Map.of("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_FOO", "1",
                        "EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MAX_CONCURRENT", "2",
                        "EDITORIAL_COST_PROVIDER_QUOTA_MOCK_CALLS_PER_DAY", "5")));
        probe("B4", "leaf with no provider: EDITORIAL_COST_PROVIDER_QUOTA_MAX_CONCURRENT=2",
                withEnv(one("EDITORIAL_COST_PROVIDER_QUOTA_MAX_CONCURRENT", "2")));
        probe("B5", "a leaf name nobody knows but shaped like one: ..._MOCK_MIN_CONCURRENT=2",
                withEnv(Map.of("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MIN_CONCURRENT", "2",
                        "EDITORIAL_COST_PROVIDER_QUOTA_MOCK_CALLS_PER_DAY", "5")));

        System.out.println("== C: ambiguity — is 'refuse rather than guess' real? ==");
        probe("C1", "two readings: ..._QUOTA_OPEN_AI_MAX_CONCURRENT=2 (open-ai or open.ai?)",
                withEnv(one("EDITORIAL_COST_PROVIDER_QUOTA_OPEN_AI_MAX_CONCURRENT", "2")));
        probe("C2", "model level through env: ..._QUOTA_MOCK_M1_MAX_CONCURRENT=2 (+ day leaf)",
                withEnv(Map.of("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_M1_MAX_CONCURRENT", "2",
                        "EDITORIAL_COST_PROVIDER_QUOTA_MOCK_M1_CALLS_PER_DAY", "1")));

        System.out.println("== D: case of the id carried by the env name ==");
        MockEnvironment upper = withEnv(Map.of("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MAX_CONCURRENT", "2",
                "EDITORIAL_COST_PROVIDER_QUOTA_MOCK_CALLS_PER_DAY", "5"));
        probe("D1", "uppercase env segment MOCK -> which scope key is stored?", upper);
        BudgetPolicy fromUpper = BudgetPolicyConfig.from(upper);
        System.out.println("D2 | does the policy answer a provider id written as MOCK at lookup time? "
                + "providerWideQuota(\"MOCK\")=" + fromUpper.providerWideQuota("MOCK").isPresent()
                + " providerWideQuota(\"mock\")=" + fromUpper.providerWideQuota("mock").isPresent()
                + " keys=" + new TreeMap<>(fromUpper.providers()).keySet());

        System.out.println("== E: values ==");
        probe("E1", "non-numeric: ..._MOCK_MAX_CONCURRENT=three",
                withEnv(Map.of("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MAX_CONCURRENT", "three",
                        "EDITORIAL_COST_PROVIDER_QUOTA_MOCK_CALLS_PER_DAY", "5")));
        probe("E2", "negative: ..._MOCK_CALLS_PER_DAY=-1",
                withEnv(Map.of("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MAX_CONCURRENT", "2",
                        "EDITORIAL_COST_PROVIDER_QUOTA_MOCK_CALLS_PER_DAY", "-1")));
        probe("E3", "max-concurrent=0 (wedge)",
                withEnv(Map.of("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MAX_CONCURRENT", "0",
                        "EDITORIAL_COST_PROVIDER_QUOTA_MOCK_CALLS_PER_DAY", "5")));
        probe("E4", "calls-per-day=0 (closed day: must boot)",
                withEnv(Map.of("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MAX_CONCURRENT", "2",
                        "EDITORIAL_COST_PROVIDER_QUOTA_MOCK_CALLS_PER_DAY", "0")));
        probe("E5", "beyond int: calls-per-day=99999999999 (the record field is a long)",
                withEnv(Map.of("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MAX_CONCURRENT", "2",
                        "EDITORIAL_COST_PROVIDER_QUOTA_MOCK_CALLS_PER_DAY", "99999999999")));
        probe("E6", "empty value: ..._MOCK_MAX_CONCURRENT=",
                withEnv(Map.of("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MAX_CONCURRENT", "",
                        "EDITORIAL_COST_PROVIDER_QUOTA_MOCK_CALLS_PER_DAY", "5")));

        System.out.println("== F: one scope named by two sources with different values ==");
        MockEnvironment both = base();
        both.setProperty("editorial.cost.provider-quota.mock.max-concurrent", "100");
        both.setProperty("editorial.cost.provider-quota.mock.calls-per-day", "100");
        both.getPropertySources().addFirst(new SystemEnvironmentPropertySource("systemEnvironment",
                Map.of("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MAX_CONCURRENT", "2",
                        "EDITORIAL_COST_PROVIDER_QUOTA_MOCK_CALLS_PER_DAY", "2")));
        probe("F1", "file says 100, env says 2 (Spring precedence: env wins) — which value bound, refused?", both);

        System.out.println("== G/H: source-type recognition ==");
        MockEnvironment wrongSource = base();
        wrongSource.getPropertySources().addFirst(new MapPropertySource("plainMap",
                Map.of("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MAX_CONCURRENT", "2",
                        "EDITORIAL_COST_PROVIDER_QUOTA_MOCK_CALLS_PER_DAY", "5")));
        probe("G1", "env-SHAPED names inside a plain MapPropertySource", wrongSource);
        System.out.println("G2 | would Spring itself resolve that canonical name from the plain map? getProperty("
                + "editorial.cost.provider-quota.mock.max-concurrent)="
                + wrongSource.getProperty("editorial.cost.provider-quota.mock.max-concurrent")
                + " (null means Spring also sees it as unset)");
        MockEnvironment dottedEnv = base();
        dottedEnv.getPropertySources().addFirst(new SystemEnvironmentPropertySource("systemEnvironment",
                Map.of("editorial.cost.provider-quota.mock.max-concurrent", "2",
                        "editorial.cost.provider-quota.mock.calls-per-day", "5")));
        System.out.println("H1 | dotted canonical name living IN an env-typed source: getProperty()="
                + dottedEnv.getProperty("editorial.cost.provider-quota.mock.max-concurrent"));
        probe("H2", "the same environment through BudgetPolicyConfig.from", dottedEnv);

        System.out.println("== I: does the switch itself survive the env channel? ==");
        MockEnvironment switchOnly = new MockEnvironment();
        switchOnly.setProperty("editorial.cost.max-calls-per-article", "64");
        switchOnly.setProperty("editorial.cost.reconciliation-stale-minutes", "30");
        switchOnly.getPropertySources().addFirst(new SystemEnvironmentPropertySource("systemEnvironment",
                Map.of("EDITORIAL_COST_PROVIDER_QUOTA_UNCONFIGURED", "refuse",
                        "EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MAX_CONCURRENT", "2",
                        "EDITORIAL_COST_PROVIDER_QUOTA_MOCK_CALLS_PER_DAY", "5")));
        probe("I1", "unconfigured stated as an env name, quotas as env names", switchOnly);
    }
}

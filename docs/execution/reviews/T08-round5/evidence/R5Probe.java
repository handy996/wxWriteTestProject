/*
 * Round-5 reviewer's own behaviour probe. It does not read the delivered test cases: it calls the shipped
 * BudgetPolicyConfig.from(Environment) directly against hand-built environments and prints what actually happens
 * for each shape the fourth round called a silent path. Compiled with javac outside the repository, into
 * %TEMP%\t08r5\probe-classes; it never touches backend/target.
 *
 * Each line is: <scenario> | <outcome>. OUTCOME is either OK providers={...} (assembly succeeded) or 503 <CODE>.
 */
import com.example.editorial.cost.BudgetPolicy;
import com.example.editorial.cost.BudgetPolicyConfig;
import com.example.editorial.shared.PublicFailure;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.core.env.MapPropertySource;
import org.springframework.core.env.StandardEnvironment;
import org.springframework.core.env.SystemEnvironmentPropertySource;

public class R5Probe {

    static final List<String> LINES = new ArrayList<>();

    /** The three keys every scenario needs before the quota subtree is even looked at. */
    static Map<String, Object> base() {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("editorial.cost.max-calls-per-article", "64");
        m.put("editorial.cost.reconciliation-stale-minutes", "30");
        m.put("editorial.cost.provider-quota.unconfigured", "refuse");
        return m;
    }

    static void probe(String label, Map<String, Object> osStyle, Map<String, Object> canonicalFileStyle) {
        StandardEnvironment env = new StandardEnvironment();
        if (osStyle != null && !osStyle.isEmpty()) {
            env.getPropertySources().addFirst(new SystemEnvironmentPropertySource("r5-os", osStyle));
        }
        if (canonicalFileStyle != null && !canonicalFileStyle.isEmpty()) {
            env.getPropertySources().addFirst(new MapPropertySource("r5-file", canonicalFileStyle));
        }
        try {
            BudgetPolicy policy = BudgetPolicyConfig.from(env);
            Map<String, BudgetPolicy.ProviderQuota> providers = policy.providers();
            StringBuilder sb = new StringBuilder();
            for (Map.Entry<String, BudgetPolicy.ProviderQuota> e : providers.entrySet()) {
                sb.append(e.getKey()).append("=").append(e.getValue().maxConcurrent())
                        .append("/").append(e.getValue().callsPerDay()).append(" ");
            }
            LINES.add(String.format("%-58s | OK providers={%s}unconfigured=%s", label, sb, policy.unconfigured()));
        } catch (PublicFailure refused) {
            LINES.add(String.format("%-58s | %d %s", label, refused.status(), refused.code()));
        } catch (Throwable escaped) {
            LINES.add(String.format("%-58s | ESCAPED %s: %s", label, escaped.getClass().getName(),
                    String.valueOf(escaped.getMessage())));
        }
    }

    public static void main(String[] args) {
        // F-R4-02: the quota prefix with one letter added, in either direction.
        Map<String, Object> oneLetterMore = base();
        oneLetterMore.put("EDITORIAL_COST_PROVIDER_QUOTAS_MOCK_MAX_CONCURRENT", "2");
        oneLetterMore.put("EDITORIAL_COST_PROVIDER_QUOTAS_MOCK_CALLS_PER_DAY", "30");
        probe("F-R4-02  prefix + one letter (QUOTAS_)", oneLetterMore, null);

        Map<String, Object> twoLettersMore = base();
        twoLettersMore.put("EDITORIAL_COST_PROVIDER_QUOTASS_MOCK_MAX_CONCURRENT", "2");
        probe("F-R4-02  prefix + two letters (QUOTASS_)", twoLettersMore, null);

        // Typo inside the marker word itself: "QUOTA" spelled QUTOA / QUOT.
        Map<String, Object> transposed = base();
        transposed.put("EDITORIAL_COST_PROVIDER_QUTOA_MOCK_MAX_CONCURRENT", "2");
        transposed.put("EDITORIAL_COST_PROVIDER_QUTOA_MOCK_CALLS_PER_DAY", "30");
        probe("F-R4-02  marker transposed (QUTOA_)", transposed, null);

        Map<String, Object> droppedLetter = base();
        droppedLetter.put("EDITORIAL_COST_PROVIDER_QUOT_MOCK_MAX_CONCURRENT", "2");
        droppedLetter.put("EDITORIAL_COST_PROVIDER_QUOT_MOCK_CALLS_PER_DAY", "30");
        probe("F-R4-02  marker missing a letter (QUOT_)", droppedLetter, null);

        // The other direction: a name in the namespace that says quota but is not this subtree at all.
        Map<String, Object> unrelatedQuotaWord = base();
        unrelatedQuotaWord.put("EDITORIAL_COST_QUOTA_MODE", "wide");
        probe("F-R4-02  namespace + word quota, not the subtree", unrelatedQuotaWord, null);

        // F-R4-03: capitals. Environment-shaped capital segment is the convention (folds); a canonical dotted
        // name with a capital is not addressable and must be refused through the 503 path, not a stack.
        Map<String, Object> capitalsFold = base();
        capitalsFold.put("EDITORIAL_COST_PROVIDER_QUOTA_MOCKPROVIDER_MAX_CONCURRENT", "2");
        capitalsFold.put("EDITORIAL_COST_PROVIDER_QUOTA_MOCKPROVIDER_CALLS_PER_DAY", "30");
        Map<String, Object> askMockProvider = new LinkedHashMap<>();
        askMockProvider.put("editorial.cost.provider-quota.unconfigured", "refuse");
        probe("F-R4-03  env channel, capital letters in the provider segment", capitalsFold, askMockProvider);

        Map<String, Object> fileCaps = base();
        fileCaps.put("editorial.cost.provider-quota.MOCK.max-concurrent", "2");
        fileCaps.put("editorial.cost.provider-quota.MOCK.calls-per-day", "30");
        probe("F-R4-03  file channel, capital segment (unspellable name)", null, fileCaps);

        Map<String, Object> fileCapsDay = base();
        fileCapsDay.put("editorial.cost.provider-quota.MOCK.calls-per-day", "30");
        probe("F-R4-03  file channel, capital segment on the day leaf", null, fileCapsDay);

        // F-R4-04: the width of each leaf against the field it fills.
        Map<String, Object> bigDay = base();
        bigDay.put("editorial.cost.provider-quota.mock.calls-per-day", "99999999999");
        bigDay.put("editorial.cost.provider-quota.mock.max-concurrent", "2");
        probe("F-R4-04  calls-per-day = 99999999999 (long the record stores)", null, bigDay);

        Map<String, Object> bigConcurrent = base();
        bigConcurrent.put("editorial.cost.provider-quota.mock.max-concurrent", "2147483648");
        bigConcurrent.put("editorial.cost.provider-quota.mock.calls-per-day", "30");
        probe("F-R4-04  max-concurrent = 2147483648 (int field overflow)", null, bigConcurrent);

        Map<String, Object> exactInt = base();
        exactInt.put("editorial.cost.provider-quota.mock.max-concurrent", "2147483647");
        exactInt.put("editorial.cost.provider-quota.mock.calls-per-day", "30");
        probe("F-R4-04  max-concurrent = 2147483647 (int field edge)", null, exactInt);

        // F-R4-05: canonical dotted names sitting inside an environment-shaped source.
        Map<String, Object> canonicalInsideEnvSource = new LinkedHashMap<>();
        canonicalInsideEnvSource.put("editorial.cost.provider-quota.unconfigured", "refuse");
        canonicalInsideEnvSource.put("editorial.cost.provider-quota.mock.max-concurrent", "7");
        canonicalInsideEnvSource.put("editorial.cost.provider-quota.mock.calls-per-day", "70");
        Map<String, Object> twoHeads = base();
        probe("F-R4-05  canonical dotted names inside an env-shaped source", canonicalInsideEnvSource, twoHeads);

        // The same canonical name stated in two environment-shaped sources: still refused, and still not a guess.
        StandardEnvironment twice = new StandardEnvironment();
        twice.getPropertySources().addFirst(new SystemEnvironmentPropertySource("r5-a", canonicalInsideEnvSource));
        Map<String, Object> secondCopy = new LinkedHashMap<>(canonicalInsideEnvSource);
        twice.getPropertySources().addFirst(new SystemEnvironmentPropertySource("r5-b", secondCopy));
        twice.getPropertySources().addFirst(new MapPropertySource("r5-file", twoHeads));
        try {
            BudgetPolicyConfig.from(twice);
            LINES.add(String.format("%-58s | OK (the two copies agreed)",
                    "doc-boundary same canonical name in two env-shaped sources"));
        } catch (PublicFailure refused) {
            LINES.add(String.format("%-58s | %d %s", "doc-boundary same canonical name in two env-shaped sources",
                    refused.status(), refused.code()));
        } catch (Throwable escaped) {
            LINES.add(String.format("%-58s | ESCAPED %s", "doc-boundary same canonical name in two env-shaped sources",
                    escaped.getClass().getName()));
        }

        // ... and with different values, which is the shape the code actually refuses.
        StandardEnvironment disagree = new StandardEnvironment();
        disagree.getPropertySources().addFirst(new SystemEnvironmentPropertySource("r5-a", canonicalInsideEnvSource));
        Map<String, Object> otherValue = new LinkedHashMap<>(canonicalInsideEnvSource);
        otherValue.put("editorial.cost.provider-quota.mock.max-concurrent", "8");
        disagree.getPropertySources().addFirst(new SystemEnvironmentPropertySource("r5-b", otherValue));
        disagree.getPropertySources().addFirst(new MapPropertySource("r5-file", twoHeads));
        try {
            BudgetPolicyConfig.from(disagree);
            LINES.add(String.format("%-58s | OK (it guessed one of them)",
                    "doc-boundary same canonical name, two different values (precedence)"));
        } catch (PublicFailure refused) {
            LINES.add(String.format("%-58s | %d %s", "doc-boundary same canonical name, two different values (precedence)",
                    refused.status(), refused.code()));
        } catch (Throwable escaped) {
            LINES.add(String.format("%-58s | ESCAPED %s", "doc-boundary same canonical name, two different values (precedence)",
                    escaped.getClass().getName()));
        }

        // F-R4-10: every leaf shape the enumeration does not know.
        Map<String, Object> camelLeaf = base();
        camelLeaf.put("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MAXCONCURRENCY", "2");
        probe("F-R4-10  unknown leaf, camel case (MAXCONCURRENCY)", camelLeaf, null);

        Map<String, Object> otherLeaf = base();
        otherLeaf.put("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_SHARDS", "2");
        probe("F-R4-10  unknown leaf, unrelated word (SHARDS)", otherLeaf, null);

        Map<String, Object> tooDeep = base();
        tooDeep.put("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MOCKMODEL_MAX_CONCURRENT", "2");
        tooDeep.put("EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MOCKMODEL_CALLS_PER_DAY", "2");
        probe("F-R4-10  env channel, model level (deeper than provider.leaf)", tooDeep, null);

        Map<String, Object> switchAsProvider = base();
        switchAsProvider.put("editorial.cost.provider-quota.unconfigured.max-concurrent", "2");
        switchAsProvider.put("editorial.cost.provider-quota.unconfigured.calls-per-day", "9");
        probe("F-R4-07  provider actually named unconfigured", null, switchAsProvider);

        // The two zeros keep their distinct meanings (round-3 F-08).
        Map<String, Object> zeroConcurrent = base();
        zeroConcurrent.put("editorial.cost.provider-quota.mock.max-concurrent", "0");
        zeroConcurrent.put("editorial.cost.provider-quota.mock.calls-per-day", "9");
        probe("F-08     max-concurrent = 0 (the wedge)", null, zeroConcurrent);

        Map<String, Object> zeroDay = base();
        zeroDay.put("editorial.cost.provider-quota.mock.max-concurrent", "9");
        zeroDay.put("editorial.cost.provider-quota.mock.calls-per-day", "0");
        probe("F-08     calls-per-day = 0 (the closed day)", null, zeroDay);

        // What the marker-internal typos degrade to: the provider ends up unlisted, and the unconfigured switch
        // decides. The switch only accepts the two spelled values, so "allow" itself is refused (measured below),
        // and the real question is what "unlimited" does with a misspelled name.
        Map<String, Object> transposedAllow = base();
        transposedAllow.put("editorial.cost.provider-quota.unconfigured", "allow");
        transposedAllow.put("EDITORIAL_COST_PROVIDER_QUTOA_MOCK_MAX_CONCURRENT", "2");
        transposedAllow.put("EDITORIAL_COST_PROVIDER_QUTOA_MOCK_CALLS_PER_DAY", "30");
        probe("residual  QUTOA typo with unconfigured=allow (not a value)", transposedAllow, null);

        for (String misspelt : new String[] {"QUTOA", "QUOT"}) {
            Map<String, Object> silentUnderUnlimited = base();
            silentUnderUnlimited.put("editorial.cost.provider-quota.unconfigured", "unlimited");
            silentUnderUnlimited.put("EDITORIAL_COST_PROVIDER_" + misspelt + "_MOCK_MAX_CONCURRENT", "2");
            silentUnderUnlimited.put("EDITORIAL_COST_PROVIDER_" + misspelt + "_MOCK_CALLS_PER_DAY", "30");
            probe("residual  typo " + misspelt + "_ with unconfigured=unlimited", silentUnderUnlimited, null);
        }

        Map<String, Object> correctUnlimited = base();
        correctUnlimited.put("editorial.cost.provider-quota.unconfigured", "unlimited");
        correctUnlimited.put("editorial.cost.provider-quota.mock.max-concurrent", "2");
        correctUnlimited.put("editorial.cost.provider-quota.mock.calls-per-day", "30");
        probe("control   spelled correctly with unconfigured=unlimited", null, correctUnlimited);

        Map<String, Object> noSwitch = new LinkedHashMap<>();
        noSwitch.put("editorial.cost.max-calls-per-article", "64");
        noSwitch.put("editorial.cost.reconciliation-stale-minutes", "30");
        probe("residual  no unconfigured switch at all", noSwitch, null);

        for (String line : LINES) {
            System.out.println(line);
        }
    }
}

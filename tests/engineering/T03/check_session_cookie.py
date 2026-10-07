"""Session cookie name consistency across contract, config, code and tests (rc.3 EDITORIAL_SESSION).

Zero third-party dependencies. The frozen OpenAPI is JSON-syntax YAML so json.loads reads it
directly; the additive paged-Diff document is plain block YAML, so it is read with a small
indentation scanner over the two blocks we care about (`security` and `securitySchemes`) instead
of pulling in pyyaml. Closes T07-R04: both contracts declared EDITORIAL_SESSION while the server
set no cookie name, so runtime silently issued the container default JSESSIONID and any client
generated from the contract would have been rejected with 401 on every route.

Hardened for the T03 fifth review (F02/F03/F04/F07), which showed the first version was relative
only: four sources plus the container default renamed in lockstep still agreed with each other, a
`cookie:`/`name:` pair smuggled under an unrelated parent matched, an extra `---` document could
carry a second name, and the startup guard itself was not an inspected source. So now:

  * an absolute anchor — every declaration must equal APPROVED_NAME, not merely each other;
  * a path-anchored config reader — only `server.servlet.session.cookie.name` counts, tracked by
    indentation, per document, so relocation and multi-document overrides are visible;
  * every `application*.yml` profile is scanned, not just the base and prod pair;
  * `T03Configuration.java` must still contain a live startup guard, and the identity test must
    still assert that the runtime issues the declared name; both are mutation targets.

Negative controls mutate the loaded sources **in memory only** — the approved rc.3 files are never
written to, not even temporarily.

Usage: python tests/engineering/T03/check_session_cookie.py [--output evidence.json]
Exit 0 when every source agrees; exit 1 with the mismatch printed.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
APPROVED_NAME = "EDITORIAL_SESSION"          # the name rc.3 declares and the R04 decision approved
FORBIDDEN = "JSESSIONID"                     # the container default that must never reappear
COOKIE_PATH = ("server", "servlet", "session", "cookie", "name")
SCALAR = re.compile(r"([^:#]+?):[ \t]*(.*)$")
# The guard is three things now, and each is checked separately after comments are stripped, because the sixth
# review showed that matching raw text lets an operator comment the guard out and still print startupGuardLive=true.
GUARD_CALL = re.compile(r'verifySessionCookieContract\(\s*env\s*\)\s*;')
GUARD_NAME = re.compile(
    r'if\s*\(\s*!\s*SESSION_COOKIE_NAME\.equals\s*\(\s*env\.getProperty\s*\(\s*"server\.servlet\.session\.cookie\.name"'
    r'\s*,\s*""\s*\)\s*\)\s*\)')

# The seventh round showed the prod branch was only checked for one string being present, so short-circuiting it,
# deleting either attribute test, renaming the profile token or flipping a default were all accepted. Each clause
# is now pinned with its comparison value, and both rejection messages must survive as written.

GUARD_PROD_IF = re.compile(r'if\s*\(\s*env\.matchesProfiles\s*\(\s*"prod"\s*\)\s*&&')
GUARD_PROD_SECURE = re.compile(r'"server\.servlet\.session\.cookie\.secure"\s*,\s*Boolean\.class\s*,\s*false')
GUARD_PROD_HTTP_ONLY = re.compile(r'"server\.servlet\.session\.cookie\.http-only"\s*,\s*Boolean\.class\s*,\s*true')
GUARD_PROD_SAME_SITE = re.compile(r'"strict"\.equals\s*\(\s*env\.getProperty\s*\(\s*"server\.servlet\.session\.cookie\.same-site"')
GUARD_MESSAGES = (
    "T03_COOKIE: session cookie name must equal the approved contract name ",
    "T03_COOKIE: secure production cookie required",
)
BEAN_METHOD = re.compile(r'@Bean\s+(?:public\s+)?SecurityFilterChain\s+identitySecurity\s*\(')
GUARD_TEST_DECL = re.compile(r'@Test\s+void\s+([A-Za-z0-9_]+)\s*\(')
TEST_ASSERTION = re.compile(r'allValues\(\s*"Set-Cookie"\s*\)[^\n]*startsWith\(\s*T03Configuration\.SESSION_COOKIE_NAME\s*\+\s*"="')

def strip_java_comments(text):
    """Remove // and block comments while respecting string and char literals.

    A guard that only exists inside a comment is not a guard, so every Java pattern below is matched against the
    de-commented source. Line structure is preserved so a reviewer can still map a match back to the file.
    """
    out = []
    index = 0
    size = len(text)
    quote = None
    while index < size:
        ch = text[index]
        if quote:
            out.append(ch)
            if ch == "\\" and index + 1 < size:
                out.append(text[index + 1])
                index += 2
                continue
            if ch == quote:
                quote = None
            index += 1
            continue
        if ch == "/" and index + 1 < size and text[index + 1] == "/":
            while index < size and text[index] != "\n":
                index += 1
            continue
        if ch == "/" and index + 1 < size and text[index + 1] == "*":
            index += 2
            while index + 1 < size and not (text[index] == "*" and text[index + 1] == "/"):
                if text[index] == "\n":
                    out.append("\n")
                index += 1
            index += 2
            continue
        if text[index:index + 3] == '"""':
            # Java text block. The seventh review desynced the previous scanner with an odd number of unescaped
            # quotes inside one, which let a commented-out guard survive as "code". Inside a text block single
            # quotes are content, not delimiters, so only the closing triple quote ends the run.
            out.append('"""')
            index += 3
            while index < size:
                if text[index] == "\\" and index + 1 < size:
                    out.append(text[index:index + 2])
                    index += 2
                    continue
                if text[index:index + 3] == '"""':
                    out.append('"""')
                    index += 3
                    break
                out.append(text[index])
                index += 1
            continue
        if ch in "\"'":
            quote = ch
        out.append(ch)
        index += 1
    return "".join(out)

SOURCES = {
    "frozenContract": ROOT / "docs/api/openapi.yaml",
    "additiveContract": ROOT / "docs/api/diff-pages-v1.1.openapi.yaml",
    "code": ROOT / "backend/src/main/java/com/example/editorial/identity/T03Configuration.java",
    "test": ROOT / "backend/src/test/java/com/example/editorial/identity/T03PostgresTest.java",
    # Seventh round: the offline negative guard test was not an inspected source at all, so deleting it or
    # emptying its assertions kept the gate green while removing the only proof that a wrong name aborts boot.
    "guardTest": ROOT / "backend/src/test/java/com/example/editorial/identity/T03SessionCookieGuardTest.java",
}
GUARD_TEST_METHODS = (
    "absentCookieNameAbortsStartup", "containerDefaultNameAbortsStartup", "thirdNameAbortsStartupEvenThoughItIsNotTheContainerDefault",
    "prodRejectsEachInsecureCookieAttribute", "prodAcceptsTheContractConformantCookie", "approvedNameStartsOutsideProd",
    "constantIsTheApprovedContractLiteral",
)
# The reproduction of the negative tests must be bound to the bytes under review, not merely present in the tree:
# the tracked surefire XML carried no input fingerprints and its timestamp preceded the commit that introduced it.
GUARD_TEST_BINDING = ROOT / "tests/engineering/T03/evidence/guard-test-binding.json"
BINDING_INPUTS = {
    "code": SOURCES["code"],
    "test": SOURCES["test"],
    "guardTest": SOURCES["guardTest"],
    "baseConfig": ROOT / "backend/src/main/resources/application.yml",
}
CONFIG_DIR = ROOT / "backend/src/main/resources"
BASE_CONFIG = "application.yml"

def read_sources():
    configs = {path.name: path.read_text(encoding="utf-8", errors="replace")
               for path in sorted(CONFIG_DIR.glob("application*.yml"))}
    return {key: path.read_text(encoding="utf-8", errors="replace") for key, path in SOURCES.items()} | {"configs": configs}

def contract_scheme_json(text, label):
    document = json.loads(text)
    schemes = document.get("components", {}).get("securitySchemes", {})
    root = document.get("security") or []
    if len(root) != 1 or len(root[0]) != 1:
        raise AssertionError(f"{label}: root security is not one single-scheme requirement: {root!r}")
    key = next(iter(root[0]))
    if key not in schemes:
        raise AssertionError(f"{label}: root security references undeclared scheme {key!r}")
    return key, schemes[key]

def _next_indent(lines, start):
    for index in range(start, len(lines)):
        line = lines[index].split("#")[0].rstrip()
        if line.strip():
            return len(line) - len(line.lstrip())
    return None

def contract_scheme_yaml(text, label):
    """(schemeKey, {type,in,name,...}) read from a block-YAML OpenAPI document."""
    lines = text.splitlines()
    root = None
    schemes = {}
    for index, raw in enumerate(lines):
        stripped = raw.split("#")[0].rstrip()
        if stripped == "security:":
            indent = _next_indent(lines, index + 1)
            items = []
            for follower in lines[index + 1:]:
                body = follower.split("#")[0].rstrip()
                if not body.strip():
                    continue
                if len(body) - len(body.lstrip()) < indent:
                    break
                match = re.match(r"\s*-\s+(\w+):\s*(.*)$", body)
                if match:
                    items.append({match.group(1): json.loads(match.group(2).replace("'", '"') or "null")})
            root = items
        elif stripped == "  securitySchemes:":
            key = None
            for follower in lines[index + 1:]:
                body = follower.split("#")[0].rstrip()
                if not body.strip():
                    continue
                indent = len(body) - len(body.lstrip())
                if indent <= 2:
                    break
                if indent == 4 and body.endswith(":"):
                    key = body.strip()[:-1]
                    schemes[key] = {}
                elif key and indent == 6:
                    match = re.match(r"\s*(\w+):\s*(.+)$", body)
                    if match:
                        schemes[key][match.group(1)] = match.group(2).strip().strip("'\"")
    if not root or len(root) != 1 or len(root[0]) != 1:
        raise AssertionError(f"{label}: root security is not one single-scheme requirement: {root!r}")
    name = next(iter(root[0]))
    if name not in schemes:
        raise AssertionError(f"{label}: root security references undeclared scheme {name!r}")
    return name, schemes[name]

def _unquote(value):
    if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
        return value[1:-1]
    return value.split(" #")[0].strip()

def cookie_names(text):
    """Every value declared at exactly server.servlet.session.cookie.name, per document.

    Tracked by indentation so a `cookie:`/`name:` pair nested under some unrelated parent is not
    mistaken for the session cookie, and reset at each `---` so a second document cannot hide an
    override. Flow-style mappings are not tracked, which is why the base config also has to prove
    it declares the path at all (see evaluate).
    """
    found = []
    stack = []
    for raw in text.splitlines():
        if raw.strip() in ("---", "..."):
            stack = []
            continue
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        while stack and stack[-1][0] >= indent:
            stack.pop()
        body = raw.strip()
        if body.startswith("- "):
            continue
        match = SCALAR.match(body)
        if not match:
            continue
        key, value = _unquote(match.group(1).strip()), match.group(2).strip()
        if value == "" or value.startswith("#"):
            stack.append((indent, key))
        elif tuple(k for _, k in stack) + (key,) == COOKIE_PATH:
            found.append(_unquote(value))
    return found

def code_constant(text):
    match = re.search(r'SESSION_COOKIE_NAME\s*=\s*"([^"]+)"', text)
    if not match:
        raise AssertionError("code: SESSION_COOKIE_NAME constant is missing")
    return match.group(1)

def bean_method_body(code):
    """The brace-balanced body of the identitySecurity @Bean method.

    The seventh round showed that GUARD_CALL alone only proves a call line exists somewhere: moving it into a
    never-invoked static helper kept the gate green. A guard is only live if it sits in the method that actually
    assembles the security chain, so the call site is now located inside that body. Braces inside string literals
    would skew this, and none exist in the file today; a future one must be handled before it is added.
    """
    match = BEAN_METHOD.search(code)
    if not match:
        raise AssertionError("code: the identitySecurity @Bean method is missing after comment stripping")
    start = code.find("{", match.end())
    if start < 0:
        raise AssertionError("code: identitySecurity has no body")
    depth = 0
    for position in range(start, len(code)):
        if code[position] == "{":
            depth += 1
        elif code[position] == "}":
            depth -= 1
            if depth == 0:
                return code[start:position + 1]
    raise AssertionError("code: identitySecurity body is not brace-balanced")

def binding_check(path=None):
    """Prove the tracked reproduction of the negative tests was produced from the bytes under review."""
    path = Path(path) if path else GUARD_TEST_BINDING
    if not path.exists():
        raise AssertionError(f"binding: {path.relative_to(ROOT)} is missing; rerun the guard test with fingerprints")
    recorded = json.loads(path.read_text(encoding="utf-8"))
    problems = []
    for label, path in BINDING_INPUTS.items():
        want = recorded.get("inputSha256", {}).get(label)
        have = hashlib.sha256(path.read_bytes()).hexdigest()
        if want != have:
            problems.append(f"{label}: recorded {str(want)[:12]}… != current {have[:12]}…")
    if problems:
        raise AssertionError("binding: tracked guard-test evidence is stale for the current bytes -> " + "; ".join(problems))
    counts = recorded.get("counts", {})
    if counts.get("tests") != len(GUARD_TEST_METHODS) or counts.get("failures") or counts.get("errors") or counts.get("skipped"):
        raise AssertionError(f"binding: recorded counts are not a clean {len(GUARD_TEST_METHODS)}-test run: {counts!r}")
    return {"bindingFile": str(path.relative_to(ROOT)), "recordedCounts": counts,
            "boundInputs": sorted(BINDING_INPUTS), "recordedCommand": recorded.get("command")}

def evaluate(sources):
    """Absolute agreement: every declaration must equal the approved name, and the guards must be live."""
    key, frozen_scheme = contract_scheme_json(sources["frozenContract"], "frozenContract")
    if frozen_scheme.get("type") != "apiKey" or frozen_scheme.get("in") != "cookie":
        raise AssertionError(f"frozenContract: scheme {key!r} must be apiKey/cookie, got {frozen_scheme!r}")
    cookie = frozen_scheme["name"]
    if cookie != APPROVED_NAME:
        # The anchor is absolute: renaming rc.3 in lockstep with everything else is drift, not agreement.
        raise AssertionError(f"frozenContract: declared cookie name {cookie!r} != approved {APPROVED_NAME!r}")
    additive_key, additive_scheme = contract_scheme_yaml(sources["additiveContract"], "additiveContract")
    if additive_key != key or additive_scheme != frozen_scheme:
        raise AssertionError(f"additiveContract: {additive_key}={additive_scheme!r} must equal frozen {key}={frozen_scheme!r}")
    if additive_scheme.get("name") != APPROVED_NAME:
        raise AssertionError(f"additiveContract: cookie name {additive_scheme.get('name')!r} != approved {APPROVED_NAME!r}")
    configs = sources["configs"]
    base = configs.get(BASE_CONFIG)
    if base is None:
        raise AssertionError(f"config: {BASE_CONFIG} is missing from {CONFIG_DIR}")
    declared = cookie_names(base)
    if len(declared) != 1:
        raise AssertionError(f"config: {BASE_CONFIG} must declare exactly one { '.'.join(COOKIE_PATH) }, found {declared!r}")
    if declared[0] != APPROVED_NAME:
        raise AssertionError(f"config: cookie name {declared[0]!r} != approved {APPROVED_NAME!r}")
    overrides = {}
    for name, text in configs.items():
        if name == BASE_CONFIG:
            continue
        values = cookie_names(text)
        for value in values:
            if value != APPROVED_NAME:
                raise AssertionError(f"config: profile {name} overrides the session cookie name with {value!r}")
        if values:
            overrides[name] = values
    constant = code_constant(sources["code"])
    if constant != APPROVED_NAME:
        raise AssertionError(f"code: constant {constant!r} != approved {APPROVED_NAME!r}")
    code = strip_java_comments(sources["code"])
    body = bean_method_body(code)
    if not GUARD_CALL.search(body):
        raise AssertionError("code: identitySecurity no longer calls verifySessionCookieContract(env) inside its own body")
    if not GUARD_NAME.search(code):
        raise AssertionError("code: the cookie-name guard is missing or commented out")
    if not GUARD_PROD_IF.search(code):
        raise AssertionError("code: the production guard is no longer an if(env.matchesProfiles(\"prod\") && ...) branch")
    if not GUARD_PROD_SECURE.search(code):
        raise AssertionError("code: the secure-attribute clause is missing, commented out, or its default flipped")
    if not GUARD_PROD_HTTP_ONLY.search(code):
        raise AssertionError("code: the http-only clause is missing, commented out, or its default flipped")
    if not GUARD_PROD_SAME_SITE.search(code):
        raise AssertionError("code: the same-site clause is missing, commented out, or no longer compared to strict")
    for message in GUARD_MESSAGES:
        if message not in code:
            raise AssertionError(f"code: rejection message {message!r} is missing or reworded into a different prefix")
    test = strip_java_comments(sources["test"])
    if not TEST_ASSERTION.search(test):
        raise AssertionError("test: no live assertion that the runtime issues the declared cookie name via Set-Cookie")
    guard_test = strip_java_comments(sources["guardTest"])
    guard_declared = set(GUARD_TEST_DECL.findall(guard_test))
    missing = sorted(set(GUARD_TEST_METHODS) - guard_declared)
    if missing:
        raise AssertionError(f"guardTest: negative cases disappeared: {missing}")
    if "assertThrows(IllegalStateException.class" not in guard_test:
        raise AssertionError("guardTest: no assertThrows left, so the rejection itself is unproven")
    binding = binding_check(sources.get("bindingPath"))
    return {"schemeKey": key, "frozenScheme": frozen_scheme, "additiveScheme": additive_scheme,
            "approvedName": APPROVED_NAME, "baseConfigCookieName": declared[0],
            "profileOverrides": overrides, "configFilesScanned": sorted(configs),
            "javaConstant": constant, "startupGuardLive": True, "runtimeAssertionLive": True,
            "guardCheckedAfterCommentStripping": True, "guardCallInsideBeanBody": True,
            "negativeGuardCases": len(GUARD_TEST_METHODS), "binding": binding}

def negative_control(sources):
    """Prove the guard bites: each weakening, applied in memory, must be rejected."""
    def mutate(label):
        copy = dict(sources)
        configs = dict(sources["configs"])
        base = configs[BASE_CONFIG]
        name_line = re.search(r"[ \t]*name: " + APPROVED_NAME + r"[ \t]*\r?\n", base)
        if label == "config-drops-cookie-name":
            configs[BASE_CONFIG] = base.replace(name_line.group(0), "", 1)
        elif label == "config-changes-cookie-name":
            configs[BASE_CONFIG] = base.replace("name: " + APPROVED_NAME, "name: " + FORBIDDEN, 1)
        elif label == "cookie-path-relocated-under-unrelated-parent":
            configs[BASE_CONFIG] = (base.replace(name_line.group(0), "", 1)
                                     + "spring:\n  datasource:\n    cookie:\n      name: " + APPROVED_NAME + "\n")
        elif label == "extra-document-carries-second-name":
            configs[BASE_CONFIG] = base + "---\nserver:\n  servlet:\n    session:\n      cookie:\n        name: OTHER_SESSION\n"
        elif label == "all-profiles-override-cookie-name":
            profiles = [name for name in configs if name != BASE_CONFIG]
            if not profiles:
                raise AssertionError("no profile config exists to mutate; the scan is untested")
            for name in profiles:
                configs[name] = (configs[name] + "\nserver:\n  servlet:\n    session:\n      cookie:\n        name: "
                                 + FORBIDDEN + "\n")
        elif label == "guard-call-moved-to-dead-method":
            # The seventh round's exploit: the call existed, but not on any path Spring would execute.
            relocated = sources["code"].replace("        verifySessionCookieContract(env);", "", 1)
            copy["code"] = relocated.rstrip()[:-1] + (
                "    static void harnessForReviewersOnly(Environment env) { verifySessionCookieContract(env); }\n}\n")
        elif label == "prod-branch-short-circuited":
            copy["code"] = sources["code"].replace('if(env.matchesProfiles("prod") &&', 'if(false && env.matchesProfiles("prod") &&', 1)
        elif label == "prod-profile-token-renamed":
            # Target the guard's own unique clause, not the bare token: matchesProfiles("prod") also appears in the
            # unrelated origin check, so a first-occurrence replace there mutated nothing about the cookie guard and
            # the gate correctly reported this control as ineffective.
            copy["code"] = sources["code"].replace('if(env.matchesProfiles("prod") &&', 'if(env.matchesProfiles("production") &&', 1)
        elif label == "prod-http-only-clause-deleted":
            copy["code"] = re.sub(r'\|\| !env\.getProperty\("server\.servlet\.session\.cookie\.http-only"[^\n]*\n', "",
                                  sources["code"], count=1)
        elif label == "prod-same-site-clause-deleted":
            copy["code"] = re.sub(r'\|\| !"strict"\.equals\([^\n]*same-site[^\n]*\)\n', "", sources["code"], count=1)
        elif label == "prod-secure-default-flipped":
            copy["code"] = sources["code"].replace('"server.servlet.session.cookie.secure",Boolean.class,false',
                                                   '"server.servlet.session.cookie.secure",Boolean.class,true', 1)
        elif label == "guard-message-prefix-changed":
            copy["code"] = sources["code"].replace("T03_COOKIE: secure production cookie required",
                                                    "T03_COOKIE2: secure production cookie required", 1)
        elif label == "textblock-desyncs-commented-guard":
            # The reviewer's minimal desync: an odd number of unescaped quotes inside a text block used to make the
            # scanner treat following real code as string content, so a commented-out guard survived as live code.
            copy["code"] = sources["code"].replace(
                "    @Bean PasswordEncoder t03Passwords()",
                '    private static final String DESYNC = """\n        cookie "EDITORIAL_SESSION\n        """;\n'
                "    @Bean PasswordEncoder t03Passwords()", 1).replace(
                "        verifySessionCookieContract(env);", "//verifySessionCookieContract(env);", 1)
        elif label == "guard-test-file-emptied":
            copy["guardTest"] = "class T03SessionCookieGuardTest {\n}\n"
        elif label == "guard-test-assertions-removed":
            copy["guardTest"] = sources["guardTest"].replace("assertThrows(IllegalStateException.class", "assertDoesNotThrow(() ->")
        elif label == "binding-file-missing":
            copy["bindingPath"] = str(ROOT / "tests/engineering/T03/evidence/__absent__.json")
        elif label == "contract-renames-cookie":
            # Replace every declared name value, not the first string match: the scheme block is what must move.
            copy["frozenContract"] = re.sub(r'("name"\s*:\s*)"' + APPROVED_NAME + '"', r'\1"OTHER_SESSION"',
                                            sources["frozenContract"])
        elif label == "additive-drops-scheme":
            copy["additiveContract"] = re.sub(r"  securitySchemes:\n(?:    .*\n|      .*\n)+", "",
                                              sources["additiveContract"], count=1)
        elif label == "additive-scheme-extra-key":
            copy["additiveContract"] = sources["additiveContract"].replace("      name: " + APPROVED_NAME,
                                                                           "      name: " + APPROVED_NAME + "\n      description: extra", 1)
        elif label == "code-constant-drifts":
            copy["code"] = sources["code"].replace('SESSION_COOKIE_NAME="' + APPROVED_NAME + '"',
                                                   'SESSION_COOKIE_NAME="' + FORBIDDEN + '"', 1)
        elif label == "guard-call-deleted":
            copy["code"] = sources["code"].replace("verifySessionCookieContract(env);", "", 1)
        elif label == "guard-call-commented-out":
            copy["code"] = sources["code"].replace("verifySessionCookieContract(env);", "//verifySessionCookieContract(env);", 1)
        elif label == "guard-name-check-commented-out":
            copy["code"] = sources["code"].replace("if(!SESSION_COOKIE_NAME.equals(", "//if(!SESSION_COOKIE_NAME.equals(", 1)
        elif label == "prod-check-neutered":
            copy["code"] = sources["code"].replace('"server.servlet.session.cookie.secure"', '"server.servlet.session.cookie.ssecure"', 1)
        elif label == "guard-line-deleted":
            copy["code"] = GUARD_NAME.sub("", sources["code"], count=1)
        elif label == "guard-neutered-never-fires":
            copy["code"] = sources["code"].replace("if(!SESSION_COOKIE_NAME.equals(", "if(false && !SESSION_COOKIE_NAME.equals(", 1)
        elif label == "guard-reads-wrong-property":
            copy["code"] = sources["code"].replace('getProperty("server.servlet.session.cookie.name","")',
                                                   'getProperty("server.servlet.session.cookie.nmae","")', 1)
        elif label == "quoted-duplicate-cookie-key":
            configs[BASE_CONFIG] = base.replace("        name: " + APPROVED_NAME + "\n",
                                                "        name: " + APPROVED_NAME + "\n        \"name\": OTHER_SESSION\n", 1)
        elif label == "runtime-assertion-deleted":
            copy["test"] = TEST_ASSERTION.sub("allValues(\"Set-Cookie\")", sources["test"], count=1)
        elif label == "runtime-assertion-commented-out":
            # Replace every occurrence, not just the first: the first allValues("Set-Cookie") assert is the
            # HttpOnly/SameSite one and commenting only that leaves the name assertion live, which would make
            # this control prove nothing while still looking like a rejection.
            copy["test"] = sources["test"].replace('assertTrue(r.headers().allValues("Set-Cookie")',
                                                   '//assertTrue(r.headers().allValues("Set-Cookie")')
        elif label == "all-sources-rename-in-lockstep":
            # The F04 case: relative agreement is not correctness — four sources plus code agreeing on the
            # container default must still fail against the approved anchor.
            copy["frozenContract"] = re.sub(r'("name"\s*:\s*)"' + APPROVED_NAME + '"', r'\1"' + FORBIDDEN + '"',
                                            sources["frozenContract"])
            copy["additiveContract"] = sources["additiveContract"].replace("name: " + APPROVED_NAME, "name: " + FORBIDDEN, 1)
            configs[BASE_CONFIG] = base.replace("name: " + APPROVED_NAME, "name: " + FORBIDDEN, 1)
            copy["code"] = sources["code"].replace('SESSION_COOKIE_NAME="' + APPROVED_NAME + '"',
                                                   'SESSION_COOKIE_NAME="' + FORBIDDEN + '"', 1)
        else:
            raise AssertionError(f"unknown mutation {label}")
        copy["configs"] = configs
        return copy

    labels = ("config-drops-cookie-name", "config-changes-cookie-name", "cookie-path-relocated-under-unrelated-parent",
              "extra-document-carries-second-name", "all-profiles-override-cookie-name", "contract-renames-cookie",
              "additive-drops-scheme", "additive-scheme-extra-key", "code-constant-drifts",
              "guard-call-deleted", "guard-call-commented-out", "guard-call-moved-to-dead-method",
              "guard-name-check-commented-out", "prod-check-neutered", "prod-branch-short-circuited",
              "prod-profile-token-renamed", "prod-http-only-clause-deleted", "prod-same-site-clause-deleted",
              "prod-secure-default-flipped", "guard-message-prefix-changed", "guard-line-deleted",
              "guard-neutered-never-fires", "guard-reads-wrong-property", "quoted-duplicate-cookie-key",
              "textblock-desyncs-commented-guard", "guard-test-file-emptied", "guard-test-assertions-removed",
              "binding-file-missing", "runtime-assertion-deleted", "runtime-assertion-commented-out",
              "all-sources-rename-in-lockstep")
    rejected = []
    for label in labels:
        mutated = mutate(label)
        if mutated == sources:
            raise AssertionError(f"negative control {label} changed nothing; it proves nothing")
        try:
            evaluate(mutated)
        except (AssertionError, KeyError, TypeError, json.JSONDecodeError):
            rejected.append(label)
        else:
            raise AssertionError(f"negative control {label} was accepted; the guard is ineffective")
    evaluate(sources)  # pristine sources must still pass, so controls cannot "pass" by breaking everything
    return sorted(rejected)

def benign_control(sources):
    """The other half of the proof: legal edits must still pass, or the scanner is over-stripping real code.

    The seventh review supplied benign cases its own probes relied on; encoding them here means a future change to
    the stripper cannot silently start rejecting legitimate Java while still rejecting the attacks.
    """
    cases = {
        "textblock-odd-quotes-intact": lambda c: c.replace(
            "    @Bean PasswordEncoder t03Passwords()",
            '    private static final String DESYNC = """\n        cookie "EDITORIAL_SESSION\n        """;\n'
            "    @Bean PasswordEncoder t03Passwords()", 1),
        "url-string-looks-like-comment": lambda c: c.replace(
            "    @Bean PasswordEncoder t03Passwords()",
            '    private static final String DOC = "https://example.test/a";\n    @Bean PasswordEncoder t03Passwords()', 1),
        "char-literals-hold-quote-chars": lambda c: c.replace(
            "    @Bean PasswordEncoder t03Passwords()",
            "    private static final char Q = '\"';\n    private static final char A = '\\'';\n"
            "    @Bean PasswordEncoder t03Passwords()", 1),
        "guard-reflowed-with-whitespace": lambda c: c.replace(
            'if(!SESSION_COOKIE_NAME.equals(env.getProperty("server.servlet.session.cookie.name","")))',
            'if ( ! SESSION_COOKIE_NAME.equals ( env.getProperty ( "server.servlet.session.cookie.name" , "" ) ) )', 1),
        "block-comment-containing-slashes-and-quotes": lambda c: c.replace(
            "    @Bean SecurityFilterChain identitySecurity(",
            '    /* reviewer note: "quoted" // not a nested comment */\n    @Bean SecurityFilterChain identitySecurity(', 1),
    }
    accepted = []
    for label, apply in sorted(cases.items()):
        mutated = dict(sources)
        mutated["code"] = apply(sources["code"])
        if mutated == sources:
            raise AssertionError(f"benign probe {label} changed nothing; it proves nothing")
        evaluate(mutated)
        accepted.append(label)
    return accepted

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output and args.output.exists():
        parser.error("output already exists; keep prior evidence")
    sources = read_sources()
    agreement = evaluate(sources)
    rejected = negative_control(sources)
    benign = benign_control(sources)
    texts = dict(sources)
    texts.update({"config:" + name: text for name, text in sources["configs"].items()})
    # The negative guard test names the container default on purpose — that is what it proves gets rejected — so it is
    # exempt from the drift scan, and only while it still carries the assertThrows rejections checked in evaluate().
    texts.pop("guardTest", None)
    drift = [name for name, text in texts.items() if FORBIDDEN in text]
    if drift:
        raise AssertionError(f"container default {FORBIDDEN} reappears in: {drift}")
    paths = {key: str(path.relative_to(ROOT)).replace("\\", "/") for key, path in SOURCES.items()}
    paths.update({"config:" + name: str((CONFIG_DIR / name).relative_to(ROOT)).replace("\\", "/")
                  for name in sorted(sources["configs"])})
    result = {"agreement": agreement, "forbiddenDefault": FORBIDDEN, "forbiddenDefaultInCheckedSources": drift,
              "cookiePath": list(COOKIE_PATH), "negativeControlsRejected": rejected,
              "negativeControlCount": len(rejected),
              "benignProbesAccepted": benign, "benignProbeCount": len(benign),
              "sha256": {label: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for label, path in paths.items()},
              "verdict": "PASS"}
    print(json.dumps(result, ensure_ascii=False))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

if __name__ == "__main__":
    main()

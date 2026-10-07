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
from xml.etree import ElementTree

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
    re.compile(r'throw new IllegalStateException\(\s*"T03_COOKIE: session cookie name must equal the approved contract name "'),
    re.compile(r'throw new IllegalStateException\(\s*"T03_COOKIE: secure production cookie required"'),
)
TEST_ASSERTION = re.compile(r'allValues\(\s*"Set-Cookie"\s*\)[^\n]*startsWith\(\s*T03Configuration\.SESSION_COOKIE_NAME\s*\+\s*"="')

def decode_unicode_escapes(text):
    r"""Resolve the \uXXXX escapes Java resolves before it tokenises, including inside comments.

    The eighth review shipped four ACCEPTED probes of exactly this shape (\u002f\u002f prefixing the guard, an
    escaped block comment wrapping it whole, "\u0022 /*"). Because javac resolves these first, a scanner looking at
    raw bytes sees code where the compiler sees a comment - and in the converse case, \u000a inside a line comment
    really does end that comment for the compiler, so treating the following code as a comment rejects legal files.
    Line structure may change (\u000a is a genuine newline to javac); that is the intended fidelity.
    """
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), text)


def strip_java_comments(text):
    """Remove // and block comments while respecting string and char literals.

    A guard that only exists inside a comment is not a guard, so every Java pattern below is matched against the
    de-commented source. Line structure is preserved so a reviewer can still map a match back to the file.
    """
    text = decode_unicode_escapes(text)
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
    # Eighth round: the recorded reproduction was read behind the scan's back, so none of its fields could be given
    # a negative control. As an inspected source it is now parsed, cross-checked against the surefire XML, and mutable.
    "binding": ROOT / "tests/engineering/T03/evidence/guard-test-binding.json",
    # The gate's own bytes are recorded in its evidence, so a result cannot be cited for a later gate edit.
    "gate": ROOT / "tests/engineering/T03/check_session_cookie.py",
    # Eighth round F-06: CI ran neither this gate nor the identity flag, so nothing in the repository caught cookie
    # name drift automatically. The wiring is now an inspected source, with a control that deletes it.
    "ci": ROOT / ".github/workflows/ci.yml",
}
GUARD_TEST_METHODS = (
    "absentCookieNameAbortsStartup", "containerDefaultNameAbortsStartup", "thirdNameAbortsStartupEvenThoughItIsNotTheContainerDefault",
    "prodRejectsEachInsecureCookieAttribute", "prodAcceptsTheContractConformantCookie", "approvedNameStartsOutsideProd",
    "constantIsTheApprovedContractLiteral",
)
# The reproduction of the negative tests must be bound to the bytes under review, not merely present in the tree:
# the tracked surefire XML carried no input fingerprints and its timestamp preceded the commit that introduced it.
GUARD_TEST_BINDING = ROOT / "tests/engineering/T03/evidence/guard-test-binding.json"
GUARD_TEST_XML = ROOT / "tests/engineering/T03/evidence/T03SessionCookieGuardTest.xml"
GUARD_TEST_CLASS = "T03SessionCookieGuardTest"
CONFIG_DIR = ROOT / "backend/src/main/resources"
BASE_CONFIG = "application.yml"

def read_sources():
    configs = {path.name: path.read_text(encoding="utf-8", errors="replace")
               for path in sorted(CONFIG_DIR.glob("application*.yml"))}
    sources = {}
    for key, path in SOURCES.items():
        if key == "binding" and not path.exists():
            sources[key] = None
            continue
        sources[key] = path.read_text(encoding="utf-8", errors="replace")
    return sources | {"configs": configs}

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

def _split_flow(inner):
    """Split a flow-mapping body at top-level commas, respecting nesting and quoting."""
    parts, depth, current, quote = [], 0, "", None
    for ch in inner:
        if quote:
            current += ch
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote, current = ch, current + ch
            continue
        if ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += ch
    if current.strip():
        parts.append(current)
    return parts

def _walk_flow(fragment, depth=1):
    """(key, value, depth) triples read out of a flow mapping, as a block mapping would present them."""
    inner = fragment.strip()
    if inner.startswith("{") and inner.endswith("}"):
        inner = inner[1:-1]
    for item in _split_flow(inner):
        if ":" not in item:
            continue
        key, _, value = item.partition(":")
        key, value = _unquote(key.strip()), value.strip()
        if value.startswith("{"):
            yield key, "", depth
            yield from _walk_flow(value, depth + 1)
        else:
            yield key, value, depth

def expand_flow(text):
    """Rewrite `a: {b: {c: 1}}` lines into equivalent block lines so one scanner covers both styles."""
    lines = []
    for raw in text.splitlines():
        stripped = raw.strip()
        indent = len(raw) - len(raw.lstrip(" "))
        match = SCALAR.match(stripped) if stripped and not stripped.startswith("#") else None
        if match and match.group(2).strip().startswith("{"):
            lines.append(" " * indent + _unquote(match.group(1).strip()) + ":")
            for key, value, depth in _walk_flow(match.group(2).strip()):
                lines.append(" " * (indent + 2 * depth) + key + (": " + value if value else ":"))
            continue
        lines.append(raw)
    return "\n".join(lines)

def cookie_names(text):
    """Every value declared at exactly server.servlet.session.cookie.name, per document.

    Tracked by indentation so a `cookie:`/`name:` pair nested under some unrelated parent is not mistaken for the
    session cookie, and reset at each `---` so a second document cannot hide an override. Flow style is expanded
    first, because the eighth review hid a second name in `server: { servlet: { session: { cookie: { name: X } } } }`
    and the whole gate passed while profileOverrides printed empty. Path keys are compared case-insensitively:
    Spring's relaxed binding maps server.Servlet.session.cookie.name onto the same property, so writing it with a
    capital was another way to keep a live override invisible to a case-sensitive scan.
    """
    found = []
    stack = []
    for raw in expand_flow(text).splitlines():
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
        elif tuple(k.lower() for _, k in stack) + (key.lower(),) == COOKIE_PATH:
            found.append(_unquote(value))
    return found

def code_constant(text):
    match = re.search(r'SESSION_COOKIE_NAME\s*=\s*"([^"]+)"', text)
    if not match:
        raise AssertionError("code: SESSION_COOKIE_NAME constant is missing")
    return match.group(1)

def mask_literals(text):
    """Blank the contents of string, char and text-block literals so braces and quotes inside cannot be structural.

    The eighth review paid off the assumption the previous version only documented: it put String skew = "{" in the
    bean body and the brace matcher cut the method short. Matching a guard needs a comment-free text, matching a
    brace structure needs a literal-free one, so both are derived here instead of one being used for both jobs.
    """
    out = []
    index = 0
    size = len(text)
    while index < size:
        ch = text[index]
        if text[index:index + 3] == '"""':
            out.append('"""')
            index += 3
            while index < size and text[index:index + 3] != '"""':
                if text[index] == "\\" and index + 1 < size:
                    out.append("  ")
                    index += 2
                    continue
                out.append(text[index] if text[index] == "\n" else "x")
                index += 1
            out.append(text[index:index + 3])
            index += 3
            continue
        if ch in "\"'":
            closing = text.find(ch, index + 1)
            out.append(ch)
            scan = index + 1
            while scan < size:
                if text[scan] == "\\" and scan + 1 < size:
                    out.append("  ")
                    scan += 2
                    continue
                if text[scan] == ch:
                    break
                out.append(text[scan] if text[scan] == "\n" else "x")
                scan += 1
            if scan < size:
                out.append(ch)
                index = scan + 1
            else:
                index = size
            continue
        out.append(ch)
        index += 1
    return "".join(out)


def literal_spans(text):
    """Offsets covered by string, char and text-block literals, so matched text can be proven to be code."""
    spans, index, size = [], 0, len(text)
    while index < size:
        if text[index:index + 3] == '"""':
            start, index = index, index + 3
            while index < size and text[index:index + 3] != '"""':
                index += 2 if text[index] == "\\" else 1
            spans.append((start, min(index + 3, size)))
            index += 3
            continue
        if text[index] in "\"'":
            quote, start, index = text[index], index, index + 1
            while index < size:
                if text[index] == "\\":
                    index += 2
                    continue
                if text[index] == quote:
                    index += 1
                    break
                index += 1
            spans.append((start, index))
            continue
        index += 1
    return spans


def in_literal(offset, spans):
    """Strictly inside a literal. A match that begins at the opening quote is live code using a literal.

    The distinction is what makes the check usable: the quoted property name passed as an argument starts exactly at
    the span, while the eighth review's paste of the same text into a Java text block starts after that block's
    opening delimiter, so only the second one is prose.
    """
    return any(start < offset < end for start, end in spans)


def live_pattern(pattern, text, spans, label, what):
    """Require at least one match that is not sitting inside a literal.

    The eighth review's second family: paste the guard's text into a text block, delete the real code, and every
    presence check stays green because it was matching prose. Comments stopped counting as code in round six;
    literals had to be excluded the same way, and the offsets come from the same scanner so nesting cannot hide it.
    """
    for match in pattern.finditer(text):
        if not in_literal(match.start(), spans):
            return match
    raise AssertionError(f"{label}: no live (non-literal) {what} remains")


BEAN_ANY = re.compile(r'@Bean[\s\S]{0,200}?\b([A-Za-z_][A-Za-z0-9_]*)\s*\(')


def bean_bodies(code):
    """Every brace-balanced body of a @Bean method, as (name, masked body, raw body).

    The guard has to sit in code Spring actually assembles; any @Bean method qualifies, so moving the call to a
    different assembled bean (the eighth review's over-strictness case) is legal, while a non-@Bean static helper
    is not. Literal masking is what makes the span trustworthy.
    """
    masked = mask_literals(code)
    bodies = []
    for match in BEAN_ANY.finditer(masked):
        start = masked.find("{", match.end())
        if start < 0:
            continue
        depth = 0
        for position in range(start, len(masked)):
            if masked[position] == "{":
                depth += 1
            elif masked[position] == "}":
                depth -= 1
                if depth == 0:
                    bodies.append((match.group(1), masked[start:position + 1], code[start:position + 1]))
                    break
    if not bodies:
        raise AssertionError("code: no brace-balanced @Bean method body survives comment stripping and masking")
    return bodies


def depth_at(body_masked, offset):
    """Brace depth of an offset inside a body, where the body's own braces are depth 1."""
    depth = 1
    for character in body_masked[1:offset]:
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
    return depth


def guard_is_reachable(code):
    """True only if the guard call is a direct statement of some assembled @Bean body.

    Text presence was the flaw: wrapping the call in a constant-false branch (static final boolean ... = false, or
    Boolean.FALSE.booleanValue()) kept every earlier check green because the call line was still inside the method,
    yet javac proves the statement never executes. A direct statement sits at brace depth 1; anything nested deeper
    is inside some conditional we have not evaluated, so it is rejected and the reviewer must make it direct.
    """
    for name, masked, raw in bean_bodies(code):
        for match in GUARD_CALL.finditer(masked):
            if depth_at(masked, match.start()) == 1:
                return name
    return None

GUARD_TEST_REQUIRE = {
    # Needles taken from the file as it stands, so each case is pinned to the shape that makes it a proof rather
    # than to its name: the eighth review emptied six bodies, kept one unrelated assertThrows, and the gate passed.
    "absentCookieNameAbortsStartup": ("assertThrows(IllegalStateException.class", "verifySessionCookieContract",
                                      "new HashMap<>()", '"T03_COOKIE"'),
    "containerDefaultNameAbortsStartup": ("assertThrows(IllegalStateException.class", "verifySessionCookieContract", FORBIDDEN),
    "thirdNameAbortsStartupEvenThoughItIsNotTheContainerDefault": ("assertThrows(IllegalStateException.class",
                                                                    "verifySessionCookieContract", '"SOMETHING_ELSE"',
                                                                    '"T03_COOKIE"'),
    "prodRejectsEachInsecureCookieAttribute": ("assertThrows(IllegalStateException.class", "verifySessionCookieContract",
                                               "{SECURE, HTTP_ONLY, SAME_SITE}", '"prod"'),
    "prodAcceptsTheContractConformantCookie": ("assertDoesNotThrow(", "contractConformantProdCookie()", '"prod"'),
    "approvedNameStartsOutsideProd": ("assertDoesNotThrow(", "verifySessionCookieContract", "SESSION_COOKIE_NAME"),
    "constantIsTheApprovedContractLiteral": ('assertEquals("EDITORIAL_SESSION", T03Configuration.SESSION_COOKIE_NAME',),
    "contractConformantProdCookie": ("properties.put(NAME, T03Configuration.SESSION_COOKIE_NAME",
                                     "properties.put(SECURE, true)", "properties.put(HTTP_ONLY, true)",
                                     "properties.put(SAME_SITE, \"strict\")"),
}


# The three property names the production case iterates over. They live as class-level constants in the test, so the
# requirement is file-wide rather than inside the method body; hollowing the case is caught by the body needles above.
GUARD_TEST_FILE_NEEDLES = ("server.servlet.session.cookie.secure", "server.servlet.session.cookie.http-only",
                           "server.servlet.session.cookie.same-site")
# Matched on the file name alone so reformatting the CI step cannot silently unpolice the contract.
CI_GATE_NEEDLE = "check_session_cookie.py"


def method_span(stripped, name):
    """(start, end) of a named method's body in the comment-free text, located with a literal-masked copy."""
    masked = mask_literals(stripped)
    # A declaration line only: the closing paren must be followed by the opening brace, and no parenthesis may
    # precede the name. That excludes call sites such as env(contractConformantProdCookie(), "prod"), whose next
    # brace would belong to another method and silently give the wrong span.
    match = re.search(r'(?m)^[ \t]*[^\n;{}=()]*\b' + re.escape(name) + r'\s*\([^)]*\)\s*(?=\{)', masked)
    if not match:
        raise AssertionError(f"guardTest: method {name} is gone")
    start = masked.find("{", match.end())
    if start < 0:
        raise AssertionError(f"guardTest: method {name} has no body")
    depth = 0
    for position in range(start, len(masked)):
        if masked[position] == "{":
            depth += 1
        elif masked[position] == "}":
            depth -= 1
            if depth == 0:
                return start, position + 1
    raise AssertionError(f"guardTest: method {name} is not brace-balanced")


def method_body(stripped, name):
    return stripped[slice(*method_span(stripped, name))]


def binding_inputs():
    """Everything the recorded reproduction must be bound to: guard sources and every config that can set the name."""
    inputs = {"code": SOURCES["code"], "test": SOURCES["test"], "guardTest": SOURCES["guardTest"],
              "guardTestXml": GUARD_TEST_XML}
    for path in sorted(CONFIG_DIR.glob("application*.yml")):
        inputs["config:" + path.name] = path
    return inputs


def binding_check(recorded, label):
    """Prove the tracked reproduction is self-consistent and bound to the bytes under review.

    The eighth review was right that this cannot prove a human ran the suite - a hand-written artefact plus a
    matching XML is forgeable - so it cross-validates every field it can reach: the exit code, the command that had
    to be pinned, the bytes of every bound input including each profile file and the surefire XML, the counts and
    testcase names re-parsed out of that XML, and their agreement with the JSON. The recorded artefact is a source
    here rather than a file the gate reads behind the scan's back, so each of those branches has a negative control.
    """
    if recorded is None:
        raise AssertionError("binding: the recorded reproduction is missing; rerun the guard test with fingerprints")
    if recorded.get("exitCode") != 0:
        raise AssertionError(f"binding: recorded exitCode is {recorded.get('exitCode')!r}, not 0")
    command = str(recorded.get("command", ""))
    if "-Dtest=" + GUARD_TEST_CLASS not in command:
        raise AssertionError(f"binding: command does not pin the guard test run: {command!r}")
    inputs = binding_inputs()
    problems = []
    for name, input_path in inputs.items():
        want = recorded.get("inputSha256", {}).get(name)
        have = hashlib.sha256(input_path.read_bytes()).hexdigest()
        if want != have:
            problems.append(f"{name}: recorded {str(want)[:12]}… != current {have[:12]}…")
    if problems:
        raise AssertionError("binding: recorded evidence is stale for the current bytes -> " + "; ".join(problems))
    xml_path = inputs["guardTestXml"]
    xml_sha = hashlib.sha256(xml_path.read_bytes()).hexdigest()
    if recorded.get("surefireXmlSha256") != xml_sha:
        raise AssertionError(f"binding: surefireXmlSha256 {str(recorded.get('surefireXmlSha256'))[:12]}… != tracked XML {xml_sha[:12]}…")
    root = ElementTree.parse(xml_path).getroot()
    observed = {"tests": int(root.get("tests")), "failures": int(root.get("failures")),
                "errors": int(root.get("errors")), "skipped": int(root.get("skipped", 0))}
    counts = recorded.get("counts", {})
    if {name: int(counts.get(name, -1)) for name in observed} != observed:
        raise AssertionError(f"binding: recorded counts {counts!r} disagree with the XML {observed!r}")
    names = sorted(case.get("name") for case in root if case.tag == "testcase")
    if names != sorted(recorded.get("testNames", [])):
        raise AssertionError("binding: recorded testNames are not the XML's testcases")
    if set(names) != set(GUARD_TEST_METHODS):
        raise AssertionError(f"binding: XML cases {names} are not the {len(GUARD_TEST_METHODS)} approved cases")
    return {"bindingLabel": label, "recordedCounts": observed, "boundInputs": sorted(inputs),
            "recordedCommand": command, "surefireXmlCrossChecked": True,
            "limit": "byte agreement plus artefact self-consistency; not proof a human ran it"}

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
    spans = literal_spans(code)
    bean = guard_is_reachable(code)
    if bean is None:
        raise AssertionError("code: verifySessionCookieContract(env) is not a direct statement of an assembled @Bean body")
    live_pattern(GUARD_NAME, code, spans, "code", "cookie-name guard clause")
    live_pattern(GUARD_PROD_IF, code, spans, "code", "if(env.matchesProfiles(\"prod\") && branch")
    live_pattern(GUARD_PROD_SECURE, code, spans, "code", "secure-attribute clause")
    live_pattern(GUARD_PROD_HTTP_ONLY, code, spans, "code", "http-only clause")
    live_pattern(GUARD_PROD_SAME_SITE, code, spans, "code", "same-site clause compared to strict")
    for index, pattern in enumerate(GUARD_MESSAGES):
        live_pattern(pattern, code, spans, "code", f"throw carrying rejection message {index + 1}")
    test = strip_java_comments(sources["test"])
    live_pattern(TEST_ASSERTION, test, literal_spans(test), "test",
                 "assertion that the runtime issues the declared cookie name via Set-Cookie")
    guard_test = strip_java_comments(sources["guardTest"])
    bodies = {name: method_body(guard_test, name)
              for name in sorted(set(GUARD_TEST_METHODS) | set(GUARD_TEST_REQUIRE))}
    for name, required in GUARD_TEST_REQUIRE.items():
        absent = [needle for needle in required if needle not in bodies[name]]
        if absent:
            raise AssertionError(f"guardTest: {name} no longer contains {absent}; the case is hollow, not a rejection proof")
    missing = [needle for needle in GUARD_TEST_FILE_NEEDLES if needle not in guard_test]
    if missing:
        raise AssertionError(f"guardTest: the production attributes {missing} are no longer exercised anywhere in the file")
    recorded = json.loads(sources["binding"]) if sources.get("binding") else None
    binding = binding_check(recorded, "binding")
    if CI_GATE_NEEDLE not in sources["ci"]:
        raise AssertionError("ci: no workflow step runs this gate, so cookie name drift has no automatic police")
    return {"schemeKey": key, "frozenScheme": frozen_scheme, "additiveScheme": additive_scheme,
            "approvedName": APPROVED_NAME, "baseConfigCookieName": declared[0],
            "profileOverrides": overrides, "configFilesScanned": sorted(configs),
            "javaConstant": constant, "startupGuardLive": True, "runtimeAssertionLive": True,
            "guardCheckedAfterCommentStripping": True, "guardCallDirectStatementInBean": bean,
            "unicodeEscapesResolvedBeforeLexing": True,
            "guardTestCaseShapes": sorted(bodies), "ciWiresThisGate": True,
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
            copy["binding"] = None
        elif label == "binding-exit-code-nonzero":
            copy["binding"] = sources["binding"].replace('"exitCode": 0', '"exitCode": 1', 1)
        elif label == "binding-command-not-pinned":
            # "command": "echo pretend" was the reviewer's forgery; the run it claims must be the pinned one.
            copy["binding"] = sources["binding"].replace("-Dtest=" + GUARD_TEST_CLASS, "echo pretend", 1)
        elif label == "binding-testnames-fabricated":
            copy["binding"] = sources["binding"].replace('"testNames": [', '"testNames": ["fabricatedCase",', 1)
        elif label == "binding-counts-disagree-with-xml":
            copy["binding"] = sources["binding"].replace('"tests": 7', '"tests": 9', 1)
        elif label == "binding-xml-sha-wrong":
            copy["binding"] = re.sub(r'"surefireXmlSha256": "[0-9a-f]{64}"', '"surefireXmlSha256": "' + "0" * 64 + '"',
                                     sources["binding"], count=1)
        elif label == "binding-profile-stale":
            # Profile files are bound inputs now; a recorded run cannot predate a later edit to application-prod.yml.
            copy["binding"] = sources["binding"].replace('"config:application-prod.yml"', '"config:application-mock.yml"', 1)
        elif label == "guard-call-in-constant-false-branch":
            # The eighth round's P1: the call line stayed in the method, every earlier check stayed green, and javac
            # proved the statement never runs. A direct statement is required, so nesting it under any condition fails.
            copy["code"] = sources["code"].replace(
                "        verifySessionCookieContract(env);",
                "        if (CHECK_COOKIE_AT_STARTUP) { verifySessionCookieContract(env); }", 1).replace(
                "    @Bean PasswordEncoder t03Passwords()",
                "    static final boolean CHECK_COOKIE_AT_STARTUP = false;\n    @Bean PasswordEncoder t03Passwords()", 1)
        elif label == "guard-call-under-boolean-false":
            copy["code"] = sources["code"].replace(
                "        verifySessionCookieContract(env);",
                "        if (Boolean.FALSE.booleanValue()) { verifySessionCookieContract(env); }", 1)
        elif label == "guard-call-under-escaped-line-comment":
            # Java resolves \u002f before tokenising, so this is a comment to the compiler and was code to us.
            copy["code"] = sources["code"].replace(
                "        verifySessionCookieContract(env);",
                "        \\u002f\\u002fverifySessionCookieContract(env);", 1)
        elif label == "guard-call-under-escaped-block-comment":
            # Wrap the call itself: an escaped comment placed in front of it leaves the statement live, and the first
            # draft of this control did exactly that, so the gate reported the control as ineffective.
            copy["code"] = sources["code"].replace(
                "        verifySessionCookieContract(env);",
                "        \\u002f\\u002a verifySessionCookieContract(env); \\u002a\\u002f", 1)
        elif label == "message-only-in-literal":
            # The reviewer moved whole clauses into a text block; the text is then prose the guard never throws.
            copy["code"] = re.sub(r'"T03_COOKIE: secure production cookie required"',
                                  '("""\n T03_COOKIE: secure production cookie required\n """)', sources["code"], count=1)
        elif label == "secure-clause-only-in-literal":
            copy["code"] = re.sub(r'"server\.servlet\.session\.cookie\.secure"',
                                  '("""server.servlet.session.cookie.secure""")', sources["code"], count=1)
        elif label == "flow-profile-override-cookie-name":
            # T03R8-F02 exactly: one flow-style line per profile kept the gate at exit 0 with profileOverrides printed empty.
            for name in list(configs):
                if name != BASE_CONFIG:
                    configs[name] = configs[name] + "\nserver: { servlet: { session: { cookie: { name: " + FORBIDDEN + " } } } }\n"
        elif label == "flow-base-second-name":
            configs[BASE_CONFIG] = base + "\nserver: { servlet: { session: { cookie: { name: " + FORBIDDEN + " } } } }\n"
        elif label == "case-variant-flow-override":
            # Spring's relaxed binding maps server.Servlet.session.cookie.NAME onto the same property, so a
            # case-sensitive path comparison left this live override invisible.
            configs["application-prod.yml"] = configs["application-prod.yml"] + (
                "\nserver: { Servlet: { Session: { Cookie: { NAME: " + FORBIDDEN + " } } } }\n")
        elif label == "guard-test-hollow-container-default":
            copy["guardTest"] = sources["guardTest"].replace('"' + FORBIDDEN + '"', '"OTHERSESSION"', 1)
        elif label == "guard-test-prod-clauses-dropped":
            copy["guardTest"] = sources["guardTest"].replace('"server.servlet.session.cookie.secure"', '"irrelevant"', 1)
        elif label == "ci-drops-cookie-gate":
            copy["ci"] = sources["ci"].replace(
                "      - name: Session cookie contract agreement gate\n"
                "        run: python tests/engineering/T03/check_session_cookie.py\n", "")
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
              "binding-file-missing", "binding-exit-code-nonzero", "binding-command-not-pinned",
              "binding-testnames-fabricated", "binding-counts-disagree-with-xml", "binding-xml-sha-wrong",
              "binding-profile-stale", "guard-call-in-constant-false-branch", "guard-call-under-boolean-false",
              "guard-call-under-escaped-line-comment", "guard-call-under-escaped-block-comment",
              "message-only-in-literal", "secure-clause-only-in-literal", "flow-profile-override-cookie-name",
              "flow-base-second-name", "case-variant-flow-override", "guard-test-hollow-container-default",
              "guard-test-prod-clauses-dropped", "ci-drops-cookie-gate",
              "runtime-assertion-deleted", "runtime-assertion-commented-out",
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

    The seventh review supplied benign cases its own probes relied on; the eighth pointed out that the dimensions it
    added (bean-body location, the binding artefact, profile files) had no benign half at all, so over-strictness
    there would have gone unnoticed. These are scanner inputs only and are never compiled: they prove the matcher
    accepts legitimate shapes, which is what stops "reject everything" from counting as a passing gate.
    """
    code_cases = {
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
        "bean-body-string-contains-brace": lambda c: c.replace(
            "        verifySessionCookieContract(env);",
            '        String skew = "{";\n        verifySessionCookieContract(env);', 1),
        "annotation-between-bean-and-signature": lambda c: c.replace(
            "    @Bean SecurityFilterChain identitySecurity(",
            "    @Bean\n    @Deprecated\n    SecurityFilterChain identitySecurity(", 1),
        "escaped-newline-inside-block-comment": lambda c: c.replace(
            "        verifySessionCookieContract(env);",
            "        /* \\u000a javac ends nothing here, the call below stays live */\n"
            "        verifySessionCookieContract(env);", 1),
        "call-moved-to-another-assembled-bean": lambda c: c.replace(
            "        verifySessionCookieContract(env);", "", 1).replace(
            "    @Bean PasswordEncoder t03Passwords()",
            "    @Bean Environment t03CookieAnchor(Environment env) {\n"
            "        verifySessionCookieContract(env);\n        return env;\n    }\n"
            "    @Bean PasswordEncoder t03Passwords()", 1),
    }
    config_cases = {
        "yaml-flow-unrelated-keys": (BASE_CONFIG, lambda t: t + (
            "\nmanagement: { endpoint: { health: { show-details: always } } }\n")),
        "yaml-flow-approved-name": ("application-prod.yml", lambda t: t + (
            "\nserver: { servlet: { session: { cookie: { name: " + APPROVED_NAME + " } } } }\n")),
    }
    # A legal reformat of the CI step must still count as policed, or the assertion is only testing its own wording.
    ci_cases = {
        "ci-invokes-gate-as-block-scalar": sources["ci"].replace(
            "        run: python tests/engineering/T03/check_session_cookie.py\n",
            "        run: |\n          python tests/engineering/T03/check_session_cookie.py --output /tmp/cookie.json\n"),
    }
    accepted = []
    for label, apply in sorted(code_cases.items()):
        mutated = dict(sources)
        mutated["code"] = apply(sources["code"])
        if mutated == sources:
            raise AssertionError(f"benign probe {label} changed nothing; it proves nothing")
        evaluate(mutated)
        accepted.append(label)
    for label, (name, apply) in sorted(config_cases.items()):
        mutated = dict(sources)
        configs = dict(mutated["configs"])
        configs[name] = apply(configs[name])
        mutated["configs"] = configs
        if mutated == sources:
            raise AssertionError(f"benign probe {label} changed nothing; it proves nothing")
        evaluate(mutated)
        accepted.append(label)
    for label, text in sorted(ci_cases.items()):
        mutated = dict(sources)
        mutated["ci"] = text
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
    # The gate names the forbidden literal in its own constants, so it cannot be scanned by itself.
    texts.pop("gate", None)
    # The negative guard test must name the container default - that is what proves a wrong name aborts boot - but
    # the exemption is now positional instead of whole-file: every occurrence has to sit inside the one case that is
    # about the container default. Replacing that literal with another name used to pass the whole gate (eighth
    # round F-03); it now fails twice, here and in GUARD_TEST_REQUIRE.
    guard_raw = strip_java_comments(sources["guardTest"])
    container_start, container_end = method_span(guard_raw, "containerDefaultNameAbortsStartup")
    outside = [index for index in range(len(guard_raw))
               if guard_raw.startswith(FORBIDDEN, index) and not container_start <= index < container_end]
    if outside:
        raise AssertionError(f"guardTest: {FORBIDDEN} occurs outside containerDefaultNameAbortsStartup at {outside}")
    texts.pop("guardTest", None)
    drift = [name for name, text in texts.items() if isinstance(text, str) and FORBIDDEN in text]
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

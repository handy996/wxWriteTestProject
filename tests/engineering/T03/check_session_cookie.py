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
GUARD = re.compile(
    r'if\s*\(\s*!\s*SESSION_COOKIE_NAME\.equals\(\s*env\.getProperty\(\s*"server\.servlet\.session\.cookie\.name"'
    r'\s*,\s*""\s*\)\s*\)\s*\)\s*throw new IllegalStateException\(\s*"T03_COOKIE')
TEST_ASSERTION = re.compile(r'allValues\(\s*"Set-Cookie"\s*\)[^\n]*startsWith\(\s*T03Configuration\.SESSION_COOKIE_NAME\s*\+\s*"="')

SOURCES = {
    "frozenContract": ROOT / "docs/api/openapi.yaml",
    "additiveContract": ROOT / "docs/api/diff-pages-v1.1.openapi.yaml",
    "code": ROOT / "backend/src/main/java/com/example/editorial/identity/T03Configuration.java",
    "test": ROOT / "backend/src/test/java/com/example/editorial/identity/T03PostgresTest.java",
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
        key, value = match.group(1).strip(), match.group(2).strip()
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
    if not GUARD.search(sources["code"]):
        raise AssertionError("code: the startup guard that rejects a cookie name other than the contract is missing or neutered")
    if not TEST_ASSERTION.search(sources["test"]):
        raise AssertionError("test: no assertion that the runtime issues the declared cookie name via Set-Cookie")
    return {"schemeKey": key, "frozenScheme": frozen_scheme, "additiveScheme": additive_scheme,
            "approvedName": APPROVED_NAME, "baseConfigCookieName": declared[0],
            "profileOverrides": overrides, "configFilesScanned": sorted(configs),
            "javaConstant": constant, "startupGuardLive": True, "runtimeAssertionLive": True}


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
        elif label == "profile-overrides-cookie-name":
            profile = next((name for name in configs if name != BASE_CONFIG), None)
            if profile is None:
                raise AssertionError("no profile config exists to mutate; the scan is untested")
            configs[profile] = configs[profile] + "\nserver:\n  servlet:\n    session:\n      cookie:\n        name: " + FORBIDDEN + "\n"
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
        elif label == "guard-line-deleted":
            copy["code"] = GUARD.sub("", sources["code"], count=1)
        elif label == "guard-neutered-never-fires":
            copy["code"] = sources["code"].replace("if(!SESSION_COOKIE_NAME.equals(", "if(false && !SESSION_COOKIE_NAME.equals(", 1)
        elif label == "guard-reads-wrong-property":
            copy["code"] = sources["code"].replace('getProperty("server.servlet.session.cookie.name","")',
                                                   'getProperty("server.servlet.session.name","")', 1)
        elif label == "runtime-assertion-deleted":
            copy["test"] = TEST_ASSERTION.sub("allValues(\"Set-Cookie\")", sources["test"], count=1)
        elif label == "all-sources-rename-in-lockstep":
            # The F04 case: relative agreement is not correctness — four sources plus code agreeing on the
            # container default must still fail against the approved anchor.
            copy["frozenContract"] = re.sub(r'("name"\s*:\s*)"' + APPROVED_NAME + '"', r'\1"' + FORBIDDEN + '"',
                                            sources["frozenContract"])
            copy["additiveContract"] = sources["additiveContract"].replace("name: " + APPROVED_NAME, "name: " + FORBIDDEN, 1)
            configs[BASE_CONFIG] = base.replace("name: " + APPROVED_NAME, "name: " + FORBIDDEN, 1)
            copy["code"] = sources["code"].replace('SESSION_COOKIE_NAME="' + APPROVED_NAME + '"',
                                                   'SESSION_COOKIE_NAME="' + FORBIDDEN + '"', 1)
            copy["test"] = sources["test"].replace("x->x.startsWith(T03Configuration.SESSION_COOKIE_NAME+\"=\")",
                                                   "x->x.startsWith(T03Configuration.SESSION_COOKIE_NAME+\"=\")", 1)
        else:
            raise AssertionError(f"unknown mutation {label}")
        copy["configs"] = configs
        return copy

    labels = ("config-drops-cookie-name", "config-changes-cookie-name", "cookie-path-relocated-under-unrelated-parent",
              "extra-document-carries-second-name", "profile-overrides-cookie-name", "contract-renames-cookie",
              "additive-drops-scheme", "additive-scheme-extra-key", "code-constant-drifts", "guard-line-deleted",
              "guard-neutered-never-fires", "guard-reads-wrong-property", "runtime-assertion-deleted",
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output and args.output.exists():
        parser.error("output already exists; keep prior evidence")
    sources = read_sources()
    agreement = evaluate(sources)
    rejected = negative_control(sources)
    texts = dict(sources)
    texts.update({"config:" + name: text for name, text in sources["configs"].items()})
    drift = [name for name, text in texts.items() if FORBIDDEN in text]
    if drift:
        raise AssertionError(f"container default {FORBIDDEN} reappears in: {drift}")
    paths = {key: str(path.relative_to(ROOT)).replace("\\", "/") for key, path in SOURCES.items()}
    paths.update({"config:" + name: str((CONFIG_DIR / name).relative_to(ROOT)).replace("\\", "/")
                  for name in sorted(sources["configs"])})
    result = {"agreement": agreement, "forbiddenDefault": FORBIDDEN, "forbiddenDefaultInCheckedSources": drift,
              "cookiePath": list(COOKIE_PATH), "negativeControlsRejected": rejected,
              "negativeControlCount": len(rejected),
              "sha256": {label: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for label, path in paths.items()},
              "verdict": "PASS"}
    print(json.dumps(result, ensure_ascii=False))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()

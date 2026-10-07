"""T03 round-10 reviewer: independent replay of R1b fake call-site shapes in a shadow tree.

Nothing here writes into the real backend tree; the shadow lives under %TEMP%\\t03r10\\shadow.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path("E:/project/codex/wxAgent")
SHADOW_ROOT = Path(os.environ["TEMP"]) / "t03r10" / "shadow"
SHADOW = SHADOW_ROOT / "backend"
JAVA_REL = "src/main/java/com/example/editorial/identity/T03Configuration.java"
PRISTINE = (ROOT / "backend" / JAVA_REL).read_text(encoding="utf-8")
MVN = ROOT / ".tools/t02/apache-maven-3.9.11/bin/mvn.cmd"
REPO = ROOT / ".tools/t02/m2"
JDK = ROOT / ".tools/t02/jdk-21.0.12.1+1"
CALL = "verifySessionCookieContract(env);"
FQCN = "com.example.editorial.identity.T03SessionCookieGuardTest"
OUT = Path(os.environ["TEMP"]) / "t03r10" / "shapes-result.json"
LOGDIR = ROOT / "docs/execution/reviews/T03-round10/logs"

PROBE = "        " + CALL


def put(text, shape):
    if PROBE not in text:
        raise SystemExit("anchor call line not found")
    return text.replace(PROBE, "        " + shape, 1)


SHAPES = []


def add(name, kind, body):
    SHAPES.append((name, kind, body))


# --- the four R1b shapes that must be mvn-red and javap-zero ---
add("braceless-if-false", "must-red-mvn",
    "if (false)\n            " + CALL)
add("boolean-false-value", "must-red-mvn",
    "if (Boolean.FALSE.booleanValue())\n            " + CALL)
add("static-final-false", "must-red-mvn",
    "if (T03_REVIEW_SKIP)\n            " + CALL)
add("conditional-early-return", "must-red-mvn",
    'if (!env.matchesProfiles("prod")) { return http.build(); }\n        ' + CALL)
add("escaped-block-comment-wrap", "must-red-mvn",
    "\\u002f\\u002a review note\n        " + CALL + "\n        \\u002a\\u002f")
# --- the two R1b shapes that are javac-time red (must not be claimed as green runs) ---
add("while-false-braced", "must-red-javac",
    "while (false) { " + CALL + " }")
add("after-unconditional-return", "must-red-javac",
    "return http.build();\n        " + CALL)
# --- benign half: must NOT be falsely red ---
add("benign-try-finally", "must-green",
    "try { " + CALL + " } finally { }")
add("benign-switch-default", "must-green",
    'switch (origin) { case "z": break; default: ' + CALL + " }")
# --- reviewer's own invented shapes ---
add("reviewer-try-catch-swallow", "reviewer",
    "try { " + CALL + " } catch (IllegalStateException swallowed) { }")
add("reviewer-runtime-unfoldable-condition", "reviewer",
    'if (env.getProperty("editorial.t03.review-switch", "on").equals("off")) { ' + CALL + " }")
add("reviewer-guard-behind-live-but-false-comparison", "reviewer",
    'if (Integer.signum(origin.length()) == -7) { ' + CALL + " }")

FIELD = '    static final boolean T03_REVIEW_SKIP = false;\n'


def prepare(shape_text):
    if SHADOW_ROOT.exists():
        shutil.rmtree(SHADOW_ROOT, ignore_errors=True)
    shutil.copytree(ROOT / "backend", SHADOW, ignore=shutil.ignore_patterns("target"))


def run_mvn():
    env = dict(os.environ, JAVA_HOME=str(JDK))
    argv = [str(MVN), "-B", "-ntp", "-o", "-f", str(SHADOW / "pom.xml"),
            "-Dmaven.repo.local=" + str(REPO), "-Dtest=" + FQCN.split(".")[-1], "test"]
    p = subprocess.run(argv, cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    text = (p.stdout or b"").decode("utf-8", errors="replace")
    return p.returncode, text


def javap_count():
    exe = str(JDK / "bin" / "javap.exe")
    cls = SHADOW / "target" / "classes"
    if not cls.exists():
        return None
    p = subprocess.run([exe, "-c", "-p", "-classpath", str(cls),
                        "com.example.editorial.identity.T03Configuration"],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    text = (p.stdout or b"").decode("utf-8", errors="replace")
    if p.returncode != 0:
        return None
    current = None
    hits = 0
    total = 0
    lines = text.splitlines()
    for index, line in enumerate(lines):
        # A method body begins where a member declaration line is immediately followed by "Code:".
        if (index + 1 < len(lines) and lines[index + 1].strip() == "Code:"
                and line.startswith("  ") and not line.startswith("   ") and line.strip()):
            current = line.strip()
        if "invokestatic" in line and "verifySessionCookieContract" in line:
            total += 1
            if current and "identitySecurity(" in current:
                hits += 1
    return {"identitySecurity": hits, "total": total,
            "identitySecuritySignature": next((l.strip() for l in lines if "identitySecurity(" in l), None)}


def surefire():
    xml = SHADOW / ("target/surefire-reports/TEST-" + FQCN + ".xml")
    if not xml.exists():
        return None
    suite = ET.parse(xml).getroot()
    counts = {k: int(suite.get(k, 0)) for k in ("tests", "failures", "errors", "skipped")}
    failed = sorted(c.get("classname") + "#" + c.get("name") for c in suite.iter("testcase")
                    if c.find("failure") is not None or c.find("error") is not None)
    return {"counts": counts, "failed": failed}


def digest(out):
    lines = [l.strip() for l in out.splitlines()]
    tests = [l for l in lines if l.startswith("Tests run:")]
    err = [l for l in lines if l.startswith("[ERROR]") and ".java:" in l][:6]
    fail = [l for l in lines if "FAIL!" in l or "BUILD" in l][:4]
    return {"testsRun": tests[-2:], "javaErrors": err, "build": fail}


def main():
    LOGDIR.mkdir(parents=True, exist_ok=True)
    results = []
    for name, kind, shape in SHAPES:
        prepare(None)
        text = put(PRISTINE, shape)
        if name == "static-final-false":
            text = text.replace("public class T03Configuration {",
                                "public class T03Configuration {\n" + FIELD, 1)
        (SHADOW / JAVA_REL).write_text(text, encoding="utf-8", newline="\n")
        code, out = run_mvn()
        compile_error = bool(re.search(r"\bERROR\].*\.java:\[\d+,\d+\]", out)) or "unreachable statement" in out
        log = LOGDIR / ("shadow-" + name + ".log")
        log.write_bytes(out.encode("utf-8"))
        results.append({"shape": name, "kind": kind, "mvn": code, "compileError": compile_error,
                        "surefire": surefire(), "javap": javap_count(), "digest": digest(out),
                        "logBytes": len(out), "logSha": hashlib.sha256(out.encode("utf-8")).hexdigest()[:12],
                        "log": str(log)})
        print(json.dumps({k: results[-1][k] for k in
                          ("shape", "kind", "mvn", "compileError", "surefire", "javap")}, ensure_ascii=False))
        sys.stdout.flush()
    # baseline pristine run
    prepare(None)
    (SHADOW / JAVA_REL).write_text(PRISTINE, encoding="utf-8", newline="\n")
    code, out = run_mvn()
    (LOGDIR / "shadow-PRISTINE.log").write_bytes(out.encode("utf-8"))
    results.append({"shape": "PRISTINE", "kind": "baseline", "mvn": code, "compileError": False,
                    "surefire": surefire(), "javap": javap_count(),
                    "log": str(LOGDIR / "shadow-PRISTINE.log")})
    print(json.dumps({"shape": "PRISTINE", "mvn": code, "surefire": surefire(), "javap": javap_count()}))
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


main()

"""Record the guard-test reproduction against the bytes in this working tree.

Run me, do not hand-write the artefact. The eighth T03 review showed that a binding JSON assembled by hand proves
nothing about execution, so this recorder performs the pinned run itself, stores the exit code it observed, copies
the surefire XML it produced, and fingerprints every input the gate re-checks. check_session_cookie.py then
cross-validates those fields against the tree it is scanning: stale bytes, an inconsistent count, a rewritten
command or a swapped XML all fail the gate.

Usage (from the repository root):
    python tests/engineering/T03/record_guard_binding.py --jdk .tools/t02/jdk-21.0.12.1+1
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "tests/engineering/T03/evidence"
CLASS = "T03SessionCookieGuardTest"
PACKAGE = "com.example.editorial.identity"
CONFIG_DIR = ROOT / "backend/src/main/resources"
MVN = ROOT / ".tools/t02/apache-maven-3.9.11/bin/mvn.cmd"
REPO = ROOT / ".tools/t02/m2"
Pinned = ["-B", "-ntp", "-o", "-f", "backend/pom.xml", "-Dmaven.repo.local=" + str(REPO),
          "-Dtest=" + CLASS, "test"]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs():
    """The label set check_session_cookie.binding_inputs() expects, kept identical on purpose."""
    found = {"code": ROOT / "backend/src/main/java/com/example/editorial/identity/T03Configuration.java",
             "test": ROOT / "backend/src/test/java/com/example/editorial/identity/T03PostgresTest.java",
             "guardTest": ROOT / "backend/src/test/java/com/example/editorial/identity/T03SessionCookieGuardTest.java",
             "guardTestXml": EVIDENCE / (CLASS + ".xml")}
    for path in sorted(CONFIG_DIR.glob("application*.yml")):
        found["config:" + path.name] = path
    return found


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jdk", type=Path, required=True, help="JDK home to run the pinned suite with")
    parser.add_argument("--output", type=Path, default=EVIDENCE / "guard-test-binding.json")
    parser.add_argument("--dry-run", action="store_true", help="record nothing, print the plan only")
    args = parser.parse_args()
    jdk = (args.jdk if args.jdk.is_absolute() else ROOT / args.jdk).resolve()
    if not args.dry_run and not (jdk / "bin" / "java.exe").exists():
        raise SystemExit(f"jdk not usable: {jdk}")
    env = dict(os.environ, JAVA_HOME=str(jdk))
    command = " ".join([str(MVN)] + Pinned)
    if args.dry_run:
        print(json.dumps({"command": command, "jdk": str(jdk), "boundInputs": sorted(inputs())}, ensure_ascii=False))
        return
    if not MVN.exists():
        raise SystemExit(f"maven wrapper not found: {MVN}")
    result = subprocess.run([str(MVN)] + Pinned, cwd=str(ROOT), env=env, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    reports = ROOT / "backend/target/surefire-reports"
    # surefire names artefacts by fully qualified class name (TEST-<fqcn>.xml, <fqcn>.txt); the tracked evidence
    # copies drop the package prefix, which is the convention the gate's GUARD_TEST_XML path already assumes.
    fqcn = PACKAGE + "." + CLASS
    for source_name, target_name in (("TEST-" + fqcn + ".xml", CLASS + ".xml"), (fqcn + ".txt", CLASS + ".txt")):
        source = reports / source_name
        if not source.exists():
            raise SystemExit(f"exit {result.returncode}: expected surefire artefact {source} is absent")
        shutil.copyfile(source, EVIDENCE / target_name)
    xml = EVIDENCE / (CLASS + ".xml")
    from xml.etree import ElementTree
    root = ElementTree.parse(xml).getroot()
    counts = {"tests": int(root.get("tests")), "failures": int(root.get("failures")),
              "errors": int(root.get("errors")), "skipped": int(root.get("skipped", 0))}
    names = sorted(case.get("name") for case in root if case.tag == "testcase")
    jars = sorted((REPO / "org/apache/maven/surefire").rglob("maven-surefire-common-*.jar"))
    if not jars:
        raise SystemExit("no surefire jar found to fingerprint; refusing to record an unattributable run")
    record = {"command": command, "exitCode": result.returncode, "counts": counts, "testNames": names,
              "inputSha256": {name: sha256(path) for name, path in sorted(inputs().items()) if path.exists()},
              "surefireXmlSha256": sha256(xml), "surefireJarSha256": sha256(jars[0]), "surefireJar": str(jars[0]),
              "jdk": str(jdk), "workspace": str(ROOT),
              "note": "produced by record_guard_binding.py; the gate re-hashes every input listed here and re-parses the XML"}
    if result.returncode != 0:
        print(result.stdout[-4000:], file=sys.stderr)
        print(result.stderr[-2000:], file=sys.stderr)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"exitCode": result.returncode, "counts": counts, "output": str(args.output),
                      "boundInputs": sorted(record["inputSha256"])}, ensure_ascii=False))
    sys.exit(0 if result.returncode == 0 else 1)


if __name__ == "__main__":
    main()

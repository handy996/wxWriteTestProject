"""Record the guard-test reproduction against the bytes in this working tree.

Run me, do not hand-write the artefact. The eighth and ninth T03 reviews both showed that a binding JSON assembled by
hand proves nothing about execution, so this recorder performs the pinned offline run itself, stores the exit code it
observed, copies the surefire XML and the config census that run produced, and fingerprints every input the gate
re-checks. check_session_cookie.py then re-hashes those inputs, re-parses the XML, re-hashes the provider jar and the
JDK launcher and compares the census with the config surface it enumerates itself.

The recorder imports check_session_cookie rather than restating its constants, so the command, the input label set and
the note the artefact carries are the same objects the gate checks against - there is no second copy to drift. What it
still cannot provide is a signature: a reviewer who wants proof that a person ran it, rather than a text editor
producing matching bytes, has to look at CI, where the same job re-runs the gate and the test class.

Usage (from the repository root):
    python tests/engineering/T03/record_guard_binding.py --jdk .tools/t02/jdk-21.0.12.1+1
"""
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "tests/engineering/T03/evidence"
CENSUS_TARGET = ROOT / "backend/target/t03-config-census.txt"


def gate():
    """Load the gate as a module, so the recorder and the checker share one definition of the pinned run."""
    spec = importlib.util.spec_from_file_location("t03_gate", Path(__file__).with_name("check_session_cookie.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_text(source, target):
    """Copy a text artefact with LF endings, so the bytes the recorder hashes are the bytes the gate re-reads.

    surefire and JDK files.write emit the platform separator, which on Windows is CRLF; the gate reads text and hashes
    those characters. Normalising once, here, keeps one digest meaning on both sides instead of two.
    """
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")


def relative(path):
    return str(Path(path).relative_to(ROOT)).replace("\\", "/")


def read_recorded_argv(argv):
    """The argv as the gate will normalise it, kept as a list so no shell word is hidden in a joined string."""
    return [str(part) for part in argv]


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--jdk", type=Path, required=True, help="JDK home to run the pinned suite with")
    parser.add_argument("--output", type=Path, default=EVIDENCE / "guard-test-binding.json")
    parser.add_argument("--dry-run", action="store_true", help="print the plan, run and record nothing")
    arguments = parser.parse_args()
    checker = gate()
    argv = read_recorded_argv(checker.expected_argv())
    jdk = (arguments.jdk if arguments.jdk.is_absolute() else ROOT / arguments.jdk).resolve()
    launcher = next((jdk / "bin" / name for name in ("java.exe", "java") if (jdk / "bin" / name).exists()), None)
    if launcher is None:
        raise SystemExit(f"jdk not usable: {jdk} has no bin/java")
    if arguments.dry_run:
        print(json.dumps({"argv": argv, "jdk": relative(jdk), "boundInputs": sorted(checker.binding_inputs())},
                         ensure_ascii=False, indent=2))
        return
    if not Path(argv[0]).exists():
        raise SystemExit(f"maven wrapper not found: {argv[0]}")

    environment = dict(os.environ, JAVA_HOME=str(jdk))
    result = subprocess.run(argv, cwd=str(ROOT), env=environment, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    reports = ROOT / "backend/target/surefire-reports"
    fqcn = checker.GUARD_TEST_PACKAGE + "." + checker.GUARD_TEST_CLASS
    copies = (("TEST-" + fqcn + ".xml", checker.SOURCES["guardTestXml"]),
              (fqcn + ".txt", EVIDENCE / (checker.GUARD_TEST_CLASS + ".txt")),
              ("t03-config-census.txt", checker.SOURCES["census"]))
    for source_name, target in copies:
        source = CENSUS_TARGET if source_name == "t03-config-census.txt" else reports / source_name
        if not source.exists():
            print(result.stdout[-4000:], file=sys.stderr)
            raise SystemExit(f"exit {result.returncode}: expected artefact {source} is absent, nothing recorded")
        if source != target:
            target.parent.mkdir(parents=True, exist_ok=True)
            copy_text(source, target)

    xml = checker.SOURCES["guardTestXml"]
    suite = ElementTree.parse(xml).getroot()
    counts = {key: int(suite.get(key, 0)) for key in ("tests", "failures", "errors", "skipped")}
    names = sorted(case.get("name") for case in suite if case.tag == "testcase")
    properties = {item.get("name"): item.get("value") for item in suite.iter("property")}
    if result.returncode != 0 or counts["failures"] or counts["errors"] or counts["skipped"]:
        print(result.stdout[-4000:], file=sys.stderr)
        print(json.dumps({"exitCode": result.returncode, "counts": counts, "names": names}, ensure_ascii=False),
              file=sys.stderr)
        raise SystemExit("the pinned run is not clean; refusing to record a reproduction that did not pass")

    # Refuse to record a run that does not contain the executed proof the gate is going to demand: the assembly cases
    # and the binder census are the point of this artefact, so a suite that lost them must not be recorded as good.
    census = checker.census_facts(checker.read_sources())
    roles, cases, _verbs = checker.executed_roles(checker.JavaSource(
        checker.SOURCES["guardTest"].read_text(encoding="utf-8"), "guardTest"))
    absent = {role: sorted(grouped) for role, grouped in roles.items() if set(grouped) - set(names)}
    if absent:
        raise SystemExit(f"the recorded run does not execute {absent}; cases in the XML: {names}")
    if len(names) != counts["tests"]:
        raise SystemExit(f"the XML declares tests={counts['tests']} but carries {len(names)} testcase elements")

    jars = sorted((checker.REPO / "org/apache/maven/surefire").rglob("maven-surefire-common-*.jar"))
    if not jars:
        raise SystemExit("no surefire provider jar to fingerprint; refusing to record an unattributable run")
    record = {"command": argv, "exitCode": result.returncode, "counts": counts, "testNames": names,
              "executedRoles": {role: sorted(cases) and sorted(grouped) for role, grouped in sorted(roles.items())},
              "inputSha256": {name: (sha256(path) if name not in ("census",) else sha256(checker.SOURCES["census"]))
                              for name, path in sorted(checker.binding_inputs().items())},
              "surefireXmlSha256": sha256(xml), "configCensusSha256": sha256(checker.SOURCES["census"]),
              "surefireJar": relative(jars[0]), "surefireJarSha256": sha256(jars[0]),
              "jdk": relative(jdk), "jdkLauncherSha256": sha256(launcher),
              "jdkVersion": properties.get("java.version"), "jdkVendor": properties.get("java.vendor"),
              "workspace": relative(ROOT), "note": checker.BINDING_NOTE}
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                                encoding="utf-8", newline="\n")
    print(json.dumps({"exitCode": result.returncode, "counts": counts, "cases": len(names),
                      "censusFiles": len(census["census"]), "boundInputs": sorted(record["inputSha256"]),
                      "output": relative(arguments.output)}, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()

"""Record the guard-test reproduction against the bytes in this working tree.

Run me, do not hand-write the artefact. The eighth and ninth T03 reviews both showed that a binding JSON assembled by
hand proves nothing about execution, so this recorder performs the pinned offline run itself, stores the exit code it
observed, copies the surefire XML and the config census that run produced, and fingerprints every input the gate
re-checks. check_session_cookie.py then re-hashes those inputs, re-parses the XML, re-hashes the provider jar and the
JDK launcher and compares the census with the config surface it enumerates itself.

Write discipline (round ten's D-2). Every check this recorder makes - exit code, the XML's counts, the executed roles,
the case list, the census certificate - is answered from the build tree before a single byte is copied, and each copy
is staged next to its target and swapped in by an atomic rename. A pinned run with failures=1 therefore leaves
tests/engineering/T03/evidence exactly as it found it. The first version of this file copied the XML, the surefire
report and the census into evidence before judging the run, so one red run replaced clean evidence with the evidence
of a failure and moved the starting point of the next replay; that is now a property of the code path, not a sentence.

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


def normalized_text(source):
    """The text an artefact will land as: surefire and JDK files.write emit the platform separator.

    On Windows that is CRLF, while the gate reads text and hashes those characters. Normalising once, here, keeps one
    digest meaning on both sides instead of two.
    """
    return source.read_text(encoding="utf-8")


def stage(source, target):
    """Write the normalised bytes beside the target and hand back the staged path; the evidence set is not changed yet.

    Each rename is atomic for one file, not a transaction across the whole evidence set. An I/O failure during
    staging or replacement can leave partial staging files or a mixed generation; use a fresh directory per run.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + ".part")
    part.write_text(normalized_text(source), encoding="utf-8", newline="\n")
    return part


def stage_text(text, target):
    """Stage serialised text beside its target, for the binding record the run has already been judged against."""
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + ".part")
    part.write_text(text, encoding="utf-8", newline="\n")
    return part


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
    # (build-tree product, evidence target). Nothing is copied yet: the run is judged from these paths first.
    products = ((reports / ("TEST-" + fqcn + ".xml"), checker.SOURCES["guardTestXml"]),
                (reports / (fqcn + ".txt"), EVIDENCE / (checker.GUARD_TEST_CLASS + ".txt")),
                (CENSUS_TARGET, checker.SOURCES["census"]))
    missing = sorted(relative(source) for source, _target in products if not source.exists())
    if missing:
        print(result.stdout[-4000:], file=sys.stderr)
        raise SystemExit(f"exit {result.returncode}: expected artefact(s) {missing} are absent, nothing recorded "
                         "and nothing copied")

    xml_source = products[0][0]
    suite = ElementTree.parse(xml_source).getroot()
    counts = {key: int(suite.get(key, 0)) for key in ("tests", "failures", "errors", "skipped")}
    names = sorted(case.get("name") for case in suite if case.tag == "testcase")
    properties = {item.get("name"): item.get("value") for item in suite.iter("property")}
    if result.returncode != 0 or counts["failures"] or counts["errors"] or counts["skipped"]:
        print(result.stdout[-4000:], file=sys.stderr)
        print(json.dumps({"exitCode": result.returncode, "counts": counts, "names": names}, ensure_ascii=False),
              file=sys.stderr)
        raise SystemExit("the pinned run is not clean; refusing to record a reproduction that did not pass, and "
                         "no artefact of that run was written into " + relative(EVIDENCE))

    # Refuse to record a run that does not contain the executed proof the gate is going to demand: the assembly cases
    # and the binder census are the point of this artefact, so a suite that lost them must not be recorded as good.
    # The census certificate is judged from the build tree too, by substituting the bytes about to be staged.
    census = checker.census_facts(dict(checker.read_sources(), census=normalized_text(products[2][0])))
    roles, cases, _verbs = checker.executed_roles(checker.JavaSource(
        checker.SOURCES["guardTest"].read_text(encoding="utf-8"), "guardTest"))
    absent = {role: sorted(grouped) for role, grouped in roles.items() if set(grouped) - set(names)}
    if absent:
        raise SystemExit(f"the pinned run does not execute {absent}; cases in the XML: {names}")
    if len(names) != counts["tests"]:
        raise SystemExit(f"the XML declares tests={counts['tests']} but carries {len(names)} testcase elements")

    jars = sorted((checker.REPO / "org/apache/maven/surefire").rglob("maven-surefire-common-*.jar"))
    if not jars:
        raise SystemExit("no surefire provider jar to fingerprint; refusing to record an unattributable run")

    # The record is assembled before anything moves, because assembling it touches the toolchain paths and a failure
    # there has to leave the evidence directory as it was. Its digests for the XML and the census are the bytes about
    # to land - the normalised ones - not the bytes currently on disk, which are the build tree's CRLF originals.
    landing = {target: checker.sha256_text(normalized_text(source)) for source, target in products}
    # binding_inputs() leaves out an optional source that is absent, and a recording run is precisely the case where
    # the XML and the census may not be on disk yet - the artefacts this run is about to write. Adding them back keeps
    # the recorded input set equal to the one the gate enumerates after the swap; without it the first replay of a
    # fresh evidence directory would fail on "not recorded" rather than being a clean record.
    bound = dict(checker.binding_inputs())
    for name in ("guardTestXml", "census"):
        bound.setdefault(name, checker.SOURCES[name])
    record = {"command": argv, "exitCode": result.returncode,
              "counts": counts, "testNames": names,
              "executedRoles": {role: sorted(cases) and sorted(grouped) for role, grouped in sorted(roles.items())},
              "inputSha256": {name: (landing[path] if path in landing else sha256(path))
                              for name, path in sorted(bound.items())},
              "surefireXmlSha256": landing[checker.SOURCES["guardTestXml"]],
              "configCensusSha256": landing[checker.SOURCES["census"]],
              "surefireJar": relative(jars[0]), "surefireJarSha256": sha256(jars[0]),
              "jdk": relative(jdk), "jdkLauncherSha256": sha256(launcher),
              "jdkVersion": properties.get("java.version"), "jdkVendor": properties.get("java.vendor"),
              "workspace": relative(ROOT), "note": checker.BINDING_NOTE}

    # Only now is the evidence directory touched, and only with bytes that already passed every check above: each
    # artefact is staged beside its target and then swapped in. A .part left behind after the swap loop is an I/O
    # failure, and it is deleted rather than being left in a controlled directory.
    staged = [(stage(source, target), target) for source, target in products if source != target]
    staged.append((stage_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                              arguments.output), arguments.output))
    try:
        for part, target in staged:
            os.replace(part, target)
    finally:
        for part, _target in staged:
            if part.exists():
                part.unlink()

    print(json.dumps({"exitCode": result.returncode, "counts": counts, "cases": len(names),
                      "censusFiles": len(census["census"]), "boundInputs": sorted(record["inputSha256"]),
                      "output": relative(arguments.output)}, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()

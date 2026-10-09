"""Round-eleven load-bearing audit: what this registry proves, and what it refuses to claim.

Method, unchanged from the round-ten audit so the arithmetic stays comparable: take the gate source text, replace one
judgement with a permissive stub (a stub that removes a conclusion, never adds one), and re-run the whole roster -
every negative control and every benign probe - inside that stubbed module. A stub that cannot be built (a missing or
ambiguous anchor), that times out, or that does not run is itself reported as unwatched, never as a pass.

  * `lost`   - the mutant is no longer rejected for the reason its own control names (accepted, crashed, or rejected
               on some other face): nothing watched that judgement on its own.
  * `moved`  - still rejected on the same face with a different reason: the judgement shares its witness with a
               redundant one, so it is reported as shared coverage, not as guarded on its own.
  * `probes` - stubbing turned a legal shape red: the judgement is watched by the benign half of the roster.

What this script does NOT prove - round ten's D-1 (P2). The reviewer fed three stubs of its own into this same harness
and all three came back `lost 0 / moved 0 / probes 0`: weakenings that change no verdict, one of them exactly the
"the self-measurement has to report numbers" type, which reads as guarded while nothing watches it. The registry is
authored by the same session that wrote the gate, so its completeness cannot be measured from inside it. The claim
stated here is the falsifiable one: `registered` N judgements, counted against `rejectionSites` `raise Rejected`
places in the gate source, and for each registered judgement the class it landed in plus the control and probe labels
that carry it. Nothing is claimed about a judgement that is not registered.

`--self-test` is the non-idling proof. It adds three stubs that are each *expected* to change no verdict at all - the
report-numbers requirement, the argv shell-word scan, and the `construct_reason` wording generator - and requires the
detector to name each of them as unguarded. The detector biting is red by design: exit 1, and the artefact it leaves
behind is the evidence. Exit 3 means a canary was not reported, the failure actually worth reading, because it says
this harness cannot see an inert weakening.

Two record policies, both mirrored from the shipped gate:
  * a negative control whose mutation does not itself touch the record is evaluated with the record re-fingerprinted,
    because whoever reviews a mutated checkout would re-run the recorder; otherwise a stale byte hash answers for
    every judgement and the roster only flatters the gate;
  * a benign probe is always re-fingerprinted, because a legitimate rewrite of a bound file is not a stale record.

Usage (from the repository root):
    python tests/engineering/T03/load_bearing_audit.py
    python tests/engineering/T03/load_bearing_audit.py --self-test --output <new artefact name>
"""
import argparse
import hashlib
import importlib.util
import json
import re
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GATE = ROOT / "tests/engineering/T03/check_session_cookie.py"
OUT = ROOT / "tests/engineering/T03/evidence/load-bearing-audit-r11.json"

BUDGET = 300.0
CORPUS_CAP = 40  # the shipped gate measures 600 synthetic shapes; an audit run does ~60 full rosters
ANY = "    (re.compile(r'(?s).*'), \"stub\"),"

# label, what the judgement decides, anchor line prefix, permissive replacement, or body to shadow the def
DIAGNOSTIC = ("yaml-construct-reasons",)   # declared wording-only: no verdict may depend on it

STUBS = [
    # --- one tokenizer, three views (F-09/F-10)
    ("jls-translation", "unicode escapes are translated the way javac reads them",
     "def translate_unicode_escapes(text):", None, "    return text, list(range(len(text)))"),
    ("tokenizer-selfcheck", "the projections are measured against 600 synthetic shapes and every real source",
     "def tokenizer_certificate(sources):", None, "    return {\"stub\": True}"),
    ("comment-blanking", "comments are blanked out in every view",
     "            if kind in BLANK_VIEWS:", "            if False:", None),
    ("literal-masking", "the masked view blanks literal contents",
     "        self.masked = self._projection(keep_literals=False, blank_text_blocks=False)",
     "        self.masked = self._projection(keep_literals=True, blank_text_blocks=False)", None),
    ("textblock-blanking", "the statements view blanks text-block prose",
     '            elif kind == "textBlock" and blank_text_blocks:', '            elif False:', None),
    # --- static reachability, the auxiliary layer (F-01/F-04)
    ("static-reachability", "guard_call_site decides whether the assembly reaches the call",
     "def guard_call_site(java):", None, '    return {"live": True, "bean": "stub", "basis": "stub"}'),
    ("bean-bodies", "which method bodies a bean assembly runs",
     "def bean_bodies(java):", None, "    return list(java.methods().values())"),
    ("constant-folding", "conditions javac can fold to false are dead",
     "def _constant_boolean(expression, constants, visiting):", None, "    return None"),
    ("braceless-dead-rule", "a brace-less constant-false if/while/for never runs its single statement",
     '        if construct in ("if", "while", "for"):', "        if False:", None),
    ("brace-stop-in-header", "a top-level brace ends a statement header, so a body is a body",
     '                return text[start:index], index, "{"', "                pass", None),
    ("dead-path-walk", "describe_dead_path explains why a call is unreachable",
     "def describe_dead_path(text, body_start, body_end, offset, constants, depth=0):", None, "    return None"),
    ("guard-body-scope", "the guard's clauses are judged inside the guard's own body",
     "def guard_clause_paths(java):", None,
     '    return {"clausesChecked": 0, "scope": [0, 0], "guard": "stub"}'),
    ("cookie-name-clause", "the cookie-name comparison is present and reachable",
     '    (GUARD_NAME, "cookie-name guard clause"),', ANY, None),
    ("prod-if-clause", 'the matchesProfiles("prod") branch is present and reachable',
     "    (GUARD_PROD_IF, 'if(env.matchesProfiles", ANY, None),
    ("secure-clause", "the secure attribute is read from the environment",
     '    (GUARD_PROD_SECURE, "secure-attribute clause"),', ANY, None),
    ("http-only-clause", "the http-only attribute is read from the environment",
     '    (GUARD_PROD_HTTP_ONLY, "http-only clause"),', ANY, None),
    ("same-site-clause", "the same-site attribute is compared to strict",
     '    (GUARD_PROD_SAME_SITE, "same-site clause compared to strict"),', ANY, None),
    ("guard-messages", "each rejection carries its T03_COOKIE message",
     "                                     for index, message in enumerate(GUARD_MESSAGES)]",
     "                                     for index, message in enumerate(())]", None),
    ("runtime-assertion", "the integration test asserts the issued cookie name",
     '    test.require_live(TEST_ASSERTION, "assertion that the runtime issues the declared cookie name via Set-Cookie",',
     "    (lambda *args: None)(TEST_ASSERTION, \"stub\",", None),
    # --- the guard test's executed shape (F-03/F-11)
    ("drift-scan", "the container default may not be named in code",
     "def forbidden_offsets(java):", None, "    return []"),
    ("container-default-exemption", "only the exempt case may name the container default",
     "    exempt_start, exempt_end = guard_test.methods().get(CONTAINER_DEFAULT_CASE, (0, 0))",
     "    exempt_start, exempt_end = 0, len(guard_test.code)", None),
    ("anchor-literal", "the guard test holds the approved name as a live literal",
     "    if not any(item.strip() == APPROVED_NAME for item in live_literals(guard_test)):",
     "    if False:", None),
    ("prod-attribute-paths", "the production attribute names appear in live test code",
     "    for needle in PROD_ATTRIBUTE_PATHS:", "    for needle in ():", None),
    ("case-closure", "assertions are followed through the file's own helper methods",
     "def case_texts(java):", None,
     "    return {name: java.code[start:end] for name, (start, end) in java.methods().items() if start < end}"),
    ("executed-roles", "each layer keeps its minimum number of executed cases",
     "            for role, need in required.items() if len(roles[role]) < need]",
     "            for role, need in required.items() if False]", None),
    ("per-case-role", "every executed case drives a behaviour the gate can name",
     "    witnessed = {name for group in roles.values() for name in group}", "    witnessed = set(texts)", None),
    # --- configuration census (F-02)
    ("yaml-census", "the YAML census attributes declarations across the whole surface",
     "def census_yaml(text):", None, "    return [], []"),
    ("properties-census", "properties layers are censused",
     "def census_properties(text):", None, "    return [], []"),
    ("yaml-flow-expansion", "multi-line flow mappings are folded before reading",
     "def expand_yaml_flow(text, reasons):", None, "    return text"),
    ("yaml-comment-stripping", "trailing comments are cut before a line is parsed",
     "def strip_yaml_comment(line):", None, "    return line"),
    ("yaml-construct-reasons", "anchors, merge keys and tags are reported as not attributed by text",
     "def construct_reason(key, value):", None, '    return "plain"'),
    ("unread-extension", "config files whose extension no face reads are reported",
     "    if unread:", "    if False:", None),
    ("location-overrides", "declarations that move the surface out of the census",
     "def location_overrides(sources):", None, "    return []"),
    # --- contracts
    ("contract-frozen-name", "the frozen contract declares the approved name",
     '    if frozen["name"] != APPROVED_NAME:', "    if False:", None),
    ("contract-agreement", "the two contracts agree with each other",
     "    if additive_key != key or additive != frozen:", "    if False:", None),
    # --- executed evidence (F-06/F-07)
    ("binder-certificate", "the executed binder/census certificate is re-derived and compared",
     "def binder_certificate(sources, facts, label):", None, '    return {"stub": True}'),
    ("argv-equality", "the recorded argv against the pinned constant table",
     "def argv_check(recorded, label):", None, '    return recorded.get("command") or []'),
    ("toolchain-rehash", "provider jar and JDK launcher re-hashed and cross-checked with the XML",
     "def toolchain_check(recorded, properties, label):", None, '    return {"stub": True}'),
    ("input-set-both-directions", "the recorded input keys against the surface this gate enumerates",
     "    if not_recorded or not_present:", "    if False:", None),
    ("input-bytes", "every bound input re-hashed against the record",
     '        raise Rejected("binding: recorded evidence is stale for the current bytes -> " + "; ".join(stale))',
     "        pass", None),
    ("xml-name-set", "recorded case names against the XML's own testcases",
     '    if names != sorted(recorded.get("testNames") or []):', "    if False:", None),
    ("xml-count-internal", "the XML's declared test count against its own testcase elements",
     '    if len(names) != counts["tests"]:', "    if False:", None),
    ("xml-clean", "the recorded run has to be clean",
     '    if counts["failures"] or counts["errors"] or counts["skipped"]:', "    if False:", None),
    ("xml-sha", "the tracked XML's hash",
     '    if digest("guardTestXml") != recorded.get("surefireXmlSha256"):', "    if False:", None),
    ("recorded-counts", "the recorded counts against the re-parsed XML",
     '    if {key: int((recorded.get("counts") or {}).get(key, -1)) for key in observed} != observed:',
     "    if False:", None),
    ("recorded-roles", "which case proves which layer, recorded and current, both directions",
     "    if drift:", "    if False:", None),
    ("recorded-current-cases", "the recorded run executed exactly the cases the current file has",
     "    if set(names) != set(cases):", "    if False:", None),
    ("note-verbatim", "the note is exactly the recorder's wording",
     '    if recorded.get("note") != BINDING_NOTE:', "    if False:", None),
    ("recorded-exit-code", "the recorded run succeeded",
     '    if recorded.get("exitCode") != 0:', "    if False:", None),
    # --- CI structure (F-06)
    ("ci-structure", "the CI structural enforcement of the gate step",
     "def ci_policy(text):", None,
     '    return {"job": "stub", "stepIndex": 0, "stepName": "stub", "workflowTriggers": ["push"], '
     '"needsChain": [], "skippableCopies": [], "stepLine": 0, "jobLine": 0, "stepIndent": 0, "jobIndent": 0, '
     '"enforcedBy": "stub", "limit": "stub"}'),
    ("ci-clean", "a step or job that can be skipped does not police anything",
     "def ci_clean(step_or_job):", None, "    return []"),
    ("ci-needs-chain", "an ancestor job that could be skipped",
     "def ci_needs_chain(jobs, job_name, seen=None):", None, "    return []"),
    ("ci-skippable-copies", "every copy of the gate step is checked for skippability",
     "        if blockers:", "        if False:", None),
    ("ci-trigger-required", "the job is reached by push or pull request",
     "    if not set(SILENT_ON) & set(trigger_names):", "    if False:", None),
]



# ------------------------------------------------------------------ canaries for --self-test
# Each one is a weakening expected to change no verdict: the type round ten's D-1 named. Keeping them out of STUBS
# means the ordinary audit stays green while the self-test run stays red by design.
CANARIES = [
    ("canary-report-numbers", "the tokenizer self-measurement has to report numbers (the reviewer's own type)",
     '    if unfed or not tokenizer["corpusFiles"]:', "    if False:", None),
    ("canary-shell-word-scan", "an argv element that is a shell word cannot run the suite",
     "    for part in argv:", "    for part in ():", None),
    ("canary-construct-reasons", "anchors, merge keys and tags are reported as not attributed by text",
     "def construct_reason(key, value):", None, '    return "plain"'),
]
CANARY_LABELS = [stub[0] for stub in CANARIES]


def rejection_sites(source):
    """How many places in the gate can say no. A denominator, not a coverage claim."""
    return len(re.findall(r"\braise Rejected\b", source))


def load(source, name):
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
    module.__file__ = str(GATE)
    exec(compile(source, str(GATE) + ":" + name, "exec"), module.__dict__)
    real_corpus = module.corpus
    module.corpus = lambda count=600: real_corpus(min(int(count), CORPUS_CAP))
    return module


def stub_source(source, anchor, replacement, insert):
    lines = source.split("\n")
    hits = [index for index, line in enumerate(lines) if line.startswith(anchor)]
    if len(hits) != 1:
        return None, f"anchor {'missing' if not hits else f'ambiguous ({len(hits)} hits)'}: {anchor[:60]!r}"
    index = hits[0]
    if insert is not None:
        lines.insert(index + 1, insert)
    else:
        lines[index] = replacement
    return "\n".join(lines), None


def signature(message):
    """Face plus leading reason, so a stub that hands the rejection to a redundant check still shows up."""
    face, _, rest = message.partition(":")
    return face.strip(), re.sub(r"\s+", " ", rest.strip())[:70]


def roster(module):
    base = module.read_sources()
    outcomes = {}
    for label, claim, mutate, needles in module.NEGATIVE_CONTROLS:
        key = (label, "negative")
        try:
            mutated = mutate(dict(base))
            if mutated.get("binding", base["binding"]) == base["binding"]:
                mutated = module.rehash_record(mutated)
            module.evaluate(mutated)
            outcomes[key] = "accepted"
        except AssertionError as failure:
            message = str(failure)
            if not any(needle in message for needle in needles):
                outcomes[key] = "wrong-face"
            else:
                outcomes[key] = "rejected: " + " / ".join(signature(message))
        except Exception as failure:
            outcomes[key] = f"crashed {type(failure).__name__}"
    for label, claim, mutate in module.BENIGN_PROBES:
        key = (label, "benign")
        try:
            module.evaluate(module.rehash_record(mutate(dict(base))))
            outcomes[key] = "accepted"
        except AssertionError as failure:
            outcomes[key] = "false-red: " + " / ".join(signature(str(failure)))
        except Exception as failure:
            outcomes[key] = f"crashed {type(failure).__name__}"
    return outcomes


def run(source, name, sink):
    try:
        sink.append(roster(load(source, name)))
    except BaseException as failure:
        sink.append({"__error__": ("error", "negative"),
                     "__detail__": f"{type(failure).__name__}: {str(failure)[:180]}"})


def verdicts(source, name):
    collected = []
    thread = threading.Thread(target=run, args=(source, name, collected), daemon=True)
    thread.start()
    thread.join(BUDGET)
    if thread.is_alive():
        return None
    if "__error__" in collected[0]:
        return collected[0]["__detail__"]
    return collected[0]


def classify(row):
    if row["lost"]:
        return "own-witness"
    if row["probeFlips"]:
        return "benign-half"
    if row["moved"]:
        return "shared-witness"
    return "unwatched (stub not runnable)" if row["error"] else "unwatched"


def publish(document, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--output", type=Path, default=OUT, help="where the audit artefact goes")
    parser.add_argument("--force", action="store_true", help="allow overwriting an existing artefact")
    parser.add_argument("--self-test", action="store_true",
                        help="add the three expected-inert canaries; red by design unless the detector idles")
    arguments = parser.parse_args(argv)
    if arguments.output.exists() and not arguments.force:
        print(f"refusing to overwrite existing {arguments.output}; pass --force if that is really intended")
        return 2

    source = GATE.read_text(encoding="utf-8")
    baseline = verdicts(source, "baseline")
    document = {"mode": "self-test" if arguments.self_test else "audit",
                "gate": {"path": str(GATE.relative_to(ROOT)).replace("\\", "/"),
                         "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest()},
                "registered": len(STUBS) + (len(CANARIES) if arguments.self_test else 0),
                "registryFromRoundTen": len(STUBS),
                "rejectionSites": rejection_sites(source),
                "budget": BUDGET, "corpusCap": CORPUS_CAP,
                "canaries": CANARY_LABELS if arguments.self_test else []}
    if isinstance(baseline, str) or baseline is None:
        document["baseline"] = {"error": str(baseline)}
        publish(document, arguments.output)
        print("baseline roster failed or timed out:", baseline)
        return 2
    controls = {key: value for key, value in baseline.items() if key[1] == "negative"}
    probes = {key: value for key, value in baseline.items() if key[1] == "benign"}
    rejected = sum(1 for value in controls.values() if value.startswith("rejected"))
    accepted = sum(1 for value in probes.values() if value == "accepted")
    document["baseline"] = {"controls": len(controls), "probes": len(probes), "controlsRejected": rejected,
                            "probesAccepted": accepted, "rehashedRecords": True}
    print(f"baseline: {rejected}/{len(controls)} negative controls rejected, {accepted}/{len(probes)} benign probes "
          f"accepted (records re-hashed, corpus capped at {CORPUS_CAP})", flush=True)
    for key in sorted(controls):
        if not controls[key].startswith("rejected"):
            print(f"  control not rejected: {key[0]} -> {controls[key]}", flush=True)
    for key in sorted(probes):
        if probes[key] != "accepted":
            print(f"  probe not accepted: {key[0]} -> {probes[key]}", flush=True)

    rows, unwatched, shared, declared = [], [], [], []
    registry = list(STUBS) + (list(CANARIES) if arguments.self_test else [])
    for label, claim, anchor, replacement, insert in registry:
        mutated, problem = stub_source(source, anchor, replacement, insert)
        row = {"stub": label, "claim": claim, "lost": [], "moved": [], "probeFlips": [], "error": None}
        if problem:
            row["error"] = problem
            print(f"  {label:<28} {problem}", flush=True)
        else:
            result = verdicts(mutated, "stub-" + label)
            if result is None:
                row["error"] = f"timeout ({BUDGET:.0f}s)"
            elif isinstance(result, str):
                row["error"] = result
            else:
                row["lost"] = sorted(key[0] for key in controls
                                     if controls[key].startswith("rejected")
                                     and not result.get(key, "").startswith("rejected"))
                row["moved"] = sorted(key[0] for key in controls
                                      if controls[key].startswith("rejected")
                                      and result.get(key, "").startswith("rejected")
                                      and result[key] != controls[key])
                row["probeFlips"] = sorted(key[0] for key in probes
                                           if probes[key] == "accepted" and result.get(key) != "accepted")
            if row["error"]:
                print(f"  {label:<28} {row['error'][:130]}", flush=True)
        row["class"] = classify(row)
        if label in DIAGNOSTIC:
            row["class"] = "declared-diagnostic"
        rows.append(row)
        if row["class"].startswith("unwatched"):
            unwatched.append(label)
        elif row["class"] == "shared-witness":
            shared.append(label)
        elif row["class"] == "declared-diagnostic":
            declared.append(label)
        print(f"  {label:<28} lost {len(row['lost']):>2}  moved {len(row['moved']):>2}  "
              f"probes {len(row['probeFlips']):>2}  {row['class']}", flush=True)
        document["stubResults"] = rows
        document["unwatched"] = unwatched
        document["sharedWitness"] = shared
        document["declaredDiagnostic"] = declared
        document["classes"] = {kind: sorted(row["stub"] for row in rows if row["class"] == kind)
                               for kind in sorted({row["class"] for row in rows})}
        document["claim"] = (f"registered {len(registry)} judgements against {document['rejectionSites']} "
                             f"`raise Rejected` sites in the gate; "
                             + ", ".join(f"{len(names)} {kind}" for kind, names in sorted(document["classes"].items()))
                             + "; nothing is claimed about judgements that are not registered")
        publish(document, arguments.output)

    print("\n" + document["claim"], flush=True)
    for label in unwatched:
        print(f"  unwatched: {label}", flush=True)
    for label in shared:
        print(f"  shared witness: {label}", flush=True)
    if declared:
        print("declared diagnostics (no verdict may depend on them): " + ", ".join(declared), flush=True)

    if not arguments.self_test:
        return 1 if unwatched else 0
    missed = [label for label in CANARY_LABELS if label not in unwatched]
    document["selfTest"] = {"canaries": CANARY_LABELS,
                            "reported": [label for label in CANARY_LABELS if label in unwatched],
                            "missed": missed, "detectorIdle": bool(missed)}
    publish(document, arguments.output)
    if missed:
        print("DETECTOR IDLE: these canaries were not reported as unguarded -> " + ", ".join(missed), flush=True)
        for row in rows:
            if row["stub"] in missed:
                print(f"  {row['stub']}: lost {len(row['lost'])} moved {len(row['moved'])} "
                      f"probes {len(row['probeFlips'])} error {row['error']}", flush=True)
        return 3
    print("detector bit: every expected-inert canary was reported as unguarded (red by design)", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

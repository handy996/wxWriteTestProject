r"""Gitleaks exception policy gate for T02 (CI: run with --with-controls and the pinned scanner).

Structure mode always runs and needs no scanner. It proves `tests/engineering/T02/gitleaks.toml`
carries no file-condition exception: in Gitleaks 8.30.1 an allowlist entry with a file condition
makes the scanner skip that file entirely (its own log reports "scanned 0 bytes"), so the paired
value test never runs and any credential committed into that file stays invisible.

Value exceptions in the delivered config are anchored between two CLOSED delimiter classes
(`(?:^|[\x60'"=:\s])<value>(?:$|[\x60'"\s;])`) so allowing a value is NOT the same as allowing any
string that touches it: prefix+value, value+suffix, an embedded value, and a value joined by `-`,
`.`, `=` or `_` are all reported again. A word boundary is not enough here: `regexTarget="match"`
searches inside the rule's Match span, generic-api-key's token class is `[\w.=-]{10,150}`, and
`-`/`.`/`=` are both token characters and `\b` boundaries - measured as 50 suppressed punctuation
joins in docs/execution/reviews/T02-round5/review.md (R5-1) and re-measured by this gate's
punctuation controls. The truncated 19-character prose digest cannot end in a delimiter right after
its literal dots (a dot IS a token character), so one RE2-safe `[^0-9a-f]` consumes exactly one
character and the closed right class bounds the rest. Lookaround is not used because Gitleaks 8.30.1
embeds RE2 and panics on `(?<!`/`(?!` (aborting the whole config, exit 2).

Controls mode runs the acceptance controls with Gitleaks against copies inside gitignored `.work`
only; nothing is written to a tracked path and the scratch tree is deleted before exit:

  positive   synthetic credentials (GitHub PAT, PEM key, AWS-shaped id) planted in copies of the
             three formerly exempted files are caught; two near-miss AWS ids are planted too and
             are documented NOT to fire (feature, not defect) - one with characters outside the
             rule's A-Z2-7 alphabet, one legal base32 whose entropy stays under the rule's gate;
  blind spot the same tree, scanned with the withdrawn file-condition shape, catches none of them;
  reverse    every exempted value changed by one character (first / two middles / last = 44 probes)
             is reported again; the exact value stays suppressed; and substring super-strings of
             the value - alphanumeric and punctuation-joined - are reported again (the anchoring
             is falsifiable, and the total number of assertions is pinned so that a probe quietly
             turning void cannot shrink the battery without a failure);
  benign     the fingerprint manifest the T02 generator now writes stays clean with no allowlist;
  pairing    digest_records refuses a path+digest record written on one line (the F-03 root cause),
             which is a precondition on the moment a manifest is written, not a scan of history.
"""
import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import digest_records

CONFIG = ROOT / 'tests/engineering/T02/gitleaks.toml'
WORK = ROOT / 'tests/engineering/T02/.work'
FORMERLY_EXEMPT = ('docs/AI-Editorial-Agent-SRS-v1.0.md',
                   'tests/engineering/T04/evidence/integration.json',
                   'tests/engineering/T02/evidence/r01-integrity.json')
EXEMPT_VALUE_COUNT = 11
MUTATION_BATTERY = 44          # 11 values x four de-duplicated single-character positions, no tolerance band
BARE_METACHARACTER = re.compile(r'[.*+?^${}()\[\]|]')   # wildcard shapes that must never appear
GUARD = '[^0-9a-f]'                                      # RE2-safe one-character guard for the dots value
# The closed delimiter classes the delivered config is required to use (backtick as \x60 so the
# entry stays a plain TOML literal string). Left allows what legitimately precedes a quoted value;
# right allows what legitimately follows it. Neither allows a character that continues the token.
LEFT = "(?:^|[\\x60'\"=:\\s])"
RIGHT = "(?:$|[\\x60'\"\\s;])"
# Assertion lines emitted by each mode, pinned so a silently shrinking battery is a failure.
# Structure: 5 config-shape + 11 per-value labels + 2 pairing + 1 this guard = 19.
# Controls, by measured category (this is the 223, not a guess):
#   18 structure lines + 1 scanner + 10 positive controls + 3 AWS-shape corners + 3 blind-spot
#   + 68 reverse battery (1 not-void + 11 per-value liveness + 44 one-character mutations
#     + 1 battery size + 11 unchanged-value-suppressed)
#   + 99 super-string controls (9 adjacency shapes x 11 values) + 14 span controls + 4 benign
#   + 1 process-scoped scratch + 1 scratch-deleted + 1 this guard = 223, with 0 void probes.
# R05 shipped 139: +66 super-string controls (six new adjacency shapes over 11 values), +2 AWS
# entropy-corner controls, +14 span controls, +1 process-scoped scratch, +1 pin = 223. Nothing was
# deleted to reach this number; the pin itself caught two wrong guesses (195 and 197) before it was
# right, and each time the only red line in the run was the pin.
EXPECTED_STRUCTURE_ASSERTIONS = 19
EXPECTED_CONTROL_ASSERTIONS = 223
failures = []
EMITTED = 0

# gitleaks writes microsecond timings with a 'µ' in its log line, and some of those lines end up in
# assertion details. On a GBK console (Windows PowerShell default) printing it raises
# UnicodeEncodeError and kills the whole gate mid-battery - measured in round 6 while running the
# red-control variants, where the reconstructed-shape note contained '12.3µs'. Reconfigure the
# stream so the gate degrades to a backslash escape instead of crashing.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, 'reconfigure'):
        try:
            _stream.reconfigure(encoding='utf-8', errors='backslashreplace')
        except (ValueError, OSError):
            pass


def check(label, condition, detail=''):
    global EMITTED
    EMITTED += 1
    print(('PASS  ' if condition else 'FAIL  ') + label + (('  [' + str(detail) + ']') if detail else ''))
    if not condition:
        failures.append(label)


def blocks_of(text):
    return re.findall(r'\[\[allowlists\]\](.*?)(?=\[\[allowlists\]\]|\Z)', text, re.S)


def entries_of(text):
    return [item for block in blocks_of(text) for item in re.findall(r"'''(.*?)'''", block, re.S)]


def unwrap(entry):
    """Split an anchored exception regex into (kind, core-regex, plain-value).

    Only the closed delimiter classes count as anchored: kind is 'literal' for
    `LEFT <value> RIGHT` and 'truncated' for `LEFT <hex16>\\... <GUARD> RIGHT`. A bare `\\b`, an
    entry missing either side, or a wildcard anywhere returns 'unanchored' so the label assertions
    below go red instead of silently accepting a wider exemption (round-5 R5-1 / A-8).
    Core-regex still carries regex escapes; plain-value is the un-escaped secret string.
    """
    body = entry
    if not body.startswith(LEFT):
        return 'unanchored', body, re.sub(r'\\(.)', r'\1', body)
    body = body[len(LEFT):]
    truncated = body.endswith(GUARD + RIGHT)
    if truncated:
        body = body[:-(len(GUARD) + len(RIGHT))]
    elif body.endswith(RIGHT):
        body = body[:-len(RIGHT)]
    else:
        return 'unanchored', body, re.sub(r'\\(.)', r'\1', body)
    return ('truncated' if truncated else 'literal'), body, re.sub(r'\\(.)', r'\1', body)


def value_of(entry):
    return unwrap(entry)[2]


def structure(text):
    blocks, entries = blocks_of(text), entries_of(text)
    check('allowlists parsed from the delivered config', bool(blocks), 'blocks %d' % len(blocks))
    # the file-condition ban must look at real assignments, not at prose that merely names the key
    code = re.sub(r'(?m)#.*$', '', text)
    occurrences = len(re.findall(r'(?i)\bpaths\b', code)) + len(re.findall(r'(?m)^\s*\w*paths\w*\s*=', code))
    check('no file-condition key in gitleaks.toml (paths occurrences must be 0)', occurrences == 0, occurrences)
    check('default rules extended, never replaced',
          '[extend]' in text and 'useDefault = true' in text and '[[rules]]' not in text)
    check('every allowlist is value-conditional (condition AND, regexTarget match, regexes present)',
          all('condition = "AND"' in b and 'regexTarget = "match"' in b and 'regexes = [' in b for b in blocks))
    check('exception count pinned for review', len(entries) == EXEMPT_VALUE_COUNT,
          '%d seen / %d expected' % (len(entries), EXEMPT_VALUE_COUNT))
    for entry in entries:
        kind, core, value = unwrap(entry)
        # the core must be a single literal: no un-escaped regex metacharacter survives `\\. ` removal
        bare = re.sub(r'\\.', '', core)
        meta_free = not BARE_METACHARACTER.search(bare)
        if kind == 'literal':
            label = 'exception is one full literal value, delimiter-class anchored both sides, no wildcard'
            ok = meta_free and value != entry and len(value) >= 16
        elif kind == 'truncated':
            label = 'exception is a truncated-prose digest (literal dots + one non-hex character + closed right class), not a wildcard'
            ok = meta_free and value.endswith('...') and len(value) >= 16
        else:
            label = ('exception is anchored by the two closed delimiter classes '
                     '(a bare word boundary or a wildcard tail is too wide)')
            ok = False
        check(label + ': ' + value[:10] + '...', ok, '%s len %d' % (kind, len(value)))
    return [value_of(entry) for entry in entries]


def scan(gitleaks, target, config, scratch, name):
    report = scratch / (name + '.report.json')
    if report.exists():
        report.unlink()
    result = subprocess.run([gitleaks, 'dir', str(target), '--no-banner', '--config', str(config),
                             '--report-format', 'json', '--report-path', str(report)],
                            capture_output=True, cwd=ROOT)
    findings = json.loads(report.read_bytes().decode('utf-8', 'replace')) if report.exists() else []
    blob = (result.stdout + result.stderr).decode('utf-8', 'replace')
    note = [line for line in blob.splitlines() if 'bytes' in line]
    return result.returncode, findings, (note[-1].strip() if note else '')


def relative_to(finding, tree):
    return pathlib.Path(finding['File']).resolve().relative_to(tree.resolve()).as_posix()


def resolve_scanner(spec):
    """A loud, checked look-up of the scanner path (the fourth-round A-1 sibling).

    The old code called subprocess.run([scanner,'version']) directly, so a directory or a missing
    path raised an uncaught OSError traceback. Here a non-existent path, a directory, or a
    non-executable file fails with a readable message and a non-zero exit instead.
    """
    looks_like_path = ('/' in spec) or ('\\' in spec) or spec.lower().endswith('.exe')
    if not looks_like_path:
        found = shutil.which(spec)
        return (found, '') if found else (None, 'gitleaks %r not found on PATH' % spec)
    path = pathlib.Path(spec)
    if not path.is_absolute():
        path = ROOT / path
    path = path.resolve()
    if not path.exists():
        return None, '--gitleaks path does not exist: %s' % path
    if path.is_dir():
        return None, ('--gitleaks points at a directory, not an executable: %s '
                      '(install/unpack puts the binary at a stable file path; pass that file)' % path)
    if not os.access(path, os.X_OK):
        return None, '--gitleaks is present but not executable: %s' % path
    return str(path), ''


def canary_block():
    """Synthetic credential shapes, assembled at runtime so this source never holds one.

    Three AWS shapes, deliberately one per door of `aws-access-token` (alphabet / entropy /
    its own EXAMPLE exemption), so the battery is a triangle and not a single near-miss:
      live      `AKIA` + 16 pure base32 characters, high entropy -> must be caught;
      alphabet  same string with one `1` (outside A-Z2-7)     -> must NOT be caught (feature);
      entropy   legal base32, four distinct characters        -> must NOT be caught (feature).
    """
    token = 'ghp_' + 'SYNTHETICNOTAREALKEY0123456789abcdefghij'
    pem = ('-----BEGIN RSA PRI' 'VATE KEY-----\n'
           'MIIBVgIBADANBgkqhkiG9w0BAQEFAgCVSYNTHETICNOTAREALKEYaaaaaaaaaaaaaaaa\n'
           '-----END RSA PRI' 'VATE KEY-----\n')
    alphabet = ''.join(chr(ord('A') + i) for i in range(16))          # A-P: pure base32, high entropy
    live_akia = 'AKIA' + alphabet                                     # shape aws-access-token matches
    near = list(alphabet)
    near[7] = '1'                                                     # digit outside the A-Z2-7 set
    near_akia = 'AKIA' + ''.join(near)                                # documented alphabet near-miss
    lowent = 'AKIA' + 'ABCD' * 4                                      # legal base32, entropy 2.0 < 3.0
    lowent_akia = lowent                                              # documented entropy near-miss
    return (line for line in (
        'github_token: ' + token,
        pem.rstrip('\n'),
        'aws_access_key_id = ' + live_akia,
        'nearmiss_aws_access_key_id = ' + near_akia,
        'lowentropy_aws_access_key_id = ' + lowent_akia,
    ))


def positive_and_blind_spot(gitleaks, scratch):
    tree = scratch / 'canary'
    for name in FORMERLY_EXEMPT:
        target = tree / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
        with target.open('a', encoding='utf-8', newline='\n') as stream:
            stream.write('\n'.join(canary_block()) + '\n')
    expected = {(name, rule) for name in FORMERLY_EXEMPT
                for rule in ('github-pat', 'private-key', 'aws-access-token')}
    code, findings, note = scan(gitleaks, tree, CONFIG, scratch, 'positive')
    caught = {(relative_to(f, tree), f['RuleID']) for f in findings}
    for name, rule in sorted(expected):
        check('positive control: synthetic %s caught in a copy of %s' % (rule, name), (name, rule) in caught)
    check('positive control: the nine canary findings are the only findings',
          caught == expected, 'exit %s; extra %s' % (code, sorted(caught - expected)))
    aws_hits = [f for f in findings if f['RuleID'] == 'aws-access-token']
    check('AWS-shape control: only the three base32 ids fired (near-miss with 0/1/8/9 stayed silent)',
          len(aws_hits) == 3, 'aws-access-token findings %d' % len(aws_hits))
    live_suffix = ''.join(chr(ord('A') + i) for i in range(16))
    lowent_suffix = 'ABCD' * 4
    fired = [live_suffix in f.get('Match', '') for f in aws_hits]
    check('AWS-shape control: every aws-access-token finding is the high-entropy live id',
          all(fired), 'matches %d of %d' % (sum(fired), len(aws_hits)))
    check('AWS-shape control: the entropy door still leaks a legal-base32 low-entropy id (feature, not defect)',
          not any(lowent_suffix in f.get('Match', '') for f in aws_hits),
          'suffix entropy 2.0, whole-match entropy 2.346, rule threshold 3.0')
    pattern = r"'''(?i)(?:SRS-v1\.0\.md|evidence.integration\.json|r01-integrity\.json)'''"
    legacy = scratch / 'legacy-shape.toml'
    legacy.write_text(re.sub(r'(?m)^condition = "AND"$', 'condition = "AND"\npaths = [' + pattern + ']',
                             CONFIG.read_text(encoding='utf-8'), count=3), encoding='utf-8', newline='\n')
    check('blind-spot control: the reconstructed shape really carries file conditions',
          len(re.findall(r'(?m)^paths = \[', legacy.read_text(encoding='utf-8'))) == 3)
    code, findings, note = scan(gitleaks, tree, legacy, scratch, 'blind')
    check('blind-spot control: reconstructed shape runs cleanly', code in (0, 1), 'exit %s %s' % (code, note))
    check('blind-spot control: file-condition shape catches NO canary (the defect this round closed)',
          not findings, 'exit %s; scanner: %s' % (code, note))


def flip(value, index):
    character = value[index]
    pool = '0123456789abcdef' if character in '0123456789abcdef' else 'abcdefghijklmnopqrstuvwxyz0123456789'
    unused = [c for c in pool if c != character and c not in value]
    return value[:index] + (unused or [c for c in pool if c != character] or ['z'])[0] + value[index + 1:]


def _probe(tree, name, token):
    (tree / name).write_text('{\n  "docs/api/reference.json": "%s",\n'
                             '  "note": "openapi.yaml=%s equals docs/execution/contracts/candidate-manifest.json"\n}\n'
                             % (token, token), encoding='utf-8', newline='\n')


# High-entropy tail used to build super-strings. Characters measured (R06, joiner battery) to
# continue generic-api-key's Match span: alphanumerics, `_`, `-`, `.`, `=`, `/`, `+`. Those are
# exactly the joiners an attacker can use, so the battery covers them; `;`, quote, backtick and
# whitespace end the span and are the delimiters the exceptions are allowed to see.
TAIL = 'Zk3xQ9mTg7Lp5Rw2'
SUPER_SHAPES = (
    ('pre', 'ab{0}', 'alphanumeric prefix'),
    ('suf', '{0}cd', 'alphanumeric suffix'),
    ('emb', '0123456789{0}abcdef', 'embedded in alphanumerics'),
    ('usuf', '{0}_' + TAIL, 'underscore suffix'),
    ('pdash', TAIL + '-{0}', 'dash prefix'),
    ('sdash', '{0}-' + TAIL, 'dash suffix'),
    ('sdot', '{0}.' + TAIL, 'dot suffix'),
    ('seq', '{0}=' + TAIL, 'equals suffix'),
    ('mdash', TAIL[:8] + '-{0}-' + TAIL[8:], 'dashes on both sides (mid-token face)'),
)


def reverse_control(gitleaks, scratch, values, defaults):
    tree = scratch / 'reverse'
    tree.mkdir(parents=True)
    cases = {}
    for number, value in enumerate(values):
        alnum = [index for index, character in enumerate(value) if character.isalnum()]
        mutation_positions = ('first', alnum[0]), ('middle', alnum[len(alnum) // 2]), \
                             ('upper', alnum[2 * len(alnum) // 3]), ('last', alnum[-1])
        seen = set()
        for tag, index in mutation_positions:
            if index in seen:
                continue
            seen.add(index)
            text = flip(value, index)
            name = 'case-%02d-%s.json' % (number, tag)
            _probe(tree, name, text)
            cases[name] = (number, tag, 'mutation')
        exact = 'case-%02d-exact.json' % number
        _probe(tree, exact, value)
        cases[exact] = (number, 'exact', 'exact')
        for stag, shape, _ in SUPER_SHAPES:
            name = 'case-%02d-super-%s.json' % (number, stag)
            _probe(tree, name, shape.format(value))
            cases[name] = (number, stag, 'super')
    results, void = {}, []
    for name in sorted(cases):
        _, base_findings, _ = scan(gitleaks, tree / name, defaults, scratch, 'base')
        _, gate_findings, _ = scan(gitleaks, tree / name, CONFIG, scratch, 'gate')
        results[name] = (bool(base_findings), bool(gate_findings))
        if not base_findings:
            void.append(name)

    exact_names = {name for name, (_, tag, _) in cases.items() if tag == 'exact'}
    check('reverse control: every unchanged probe really triggers generic-api-key (control is not void)',
          not [name for name in exact_names if name in void], sorted(exact_names & set(void)))

    mutation_total = 0
    for number in range(len(values)):
        mutated = [name for name, (n, tag, kind) in cases.items() if n == number and kind == 'mutation']
        live = [name for name in mutated if results[name][0]]
        mutation_total += len(live)
        check('reverse control: all %d single-character probes stay live for value %02d' % (len(mutated), number),
              len(live) == len(mutated), 'live %d of %d' % (len(live), len(mutated)))
        for name in live:
            check('reverse control: one-character change in %s is reported again' % name, results[name][1],
                  'gate suppressed it')
    check('reverse control: the 44-mutation battery is present (exactly 44 live single-character probes)',
          mutation_total == MUTATION_BATTERY, 'live mutation probes %d / expected exactly %d'
          % (mutation_total, MUTATION_BATTERY))

    for name, (number, stag, kind) in sorted(cases.items()):
        if kind != 'super':
            continue
        if name in void:
            continue
        shape = dict((s, d) for s, _, d in SUPER_SHAPES)[stag]
        check('substring control: super-string %s for value %02d is reported again (%s, not swallowed)'
              % (stag, number, shape), results[name][1],
              'the anchored value exception swallowed a longer token')

    for name in sorted(exact_names):
        if name in void:
            continue
        check('reverse control: unchanged value in %s is suppressed by that value only' % name,
              not results[name][1], 'gate reported the exact value')
    if void:
        print('NOTE    probes the rule itself does not report (entropy gate), excluded from the count: %s' % void)


def span_control(gitleaks, scratch, values, defaults):
    """R06 (round-5 R5-1 residual): pin what the rule's Match span actually covers.

    `regexTarget = "match"` means an exception is searched inside the rule's Match text, so whether
    a joined super-string is the same finding as the exempt value depends on the token class of
    `generic-api-key`, measured here character by character: `-`, `.`, `=`, `_`, `/`, `+` and
    alphanumerics CONTINUE the span (so suppressing one of those would be substring allowlisting,
    and the delivered config must not); `;`, quote, backtick and whitespace TERMINATE it (so a
    finding whose span ends there is just the exact value, and suppressing it is value
    allowlisting). This is the falsifiable form of the one residual suppression the battery still
    shows: if a future scanner or rule lets a span cross whitespace and swallow a longer token,
    the terminator assertion below goes red instead of the exception quietly becoming a prefix
    match. The continuation half proves the assertion is not vacuous.
    """
    tree = scratch / 'span'
    tree.mkdir(parents=True)
    continues = ('-', '.', '=', '_', '/', '+')
    terminates = (';', chr(34), chr(39), chr(96), ' ')
    probes = [('continues', ch, values[2]) for ch in continues]
    probes += [('terminates', ch, values[2]) for ch in terminates]
    probes += [('continues', '-', values[10]), ('terminates', ' ', values[10]),
               ('terminates', chr(9), values[10])]
    for index, (expected, ch, value) in enumerate(probes):
        name = 'span-%02d.json' % index
        _probe(tree, name, value + ch + TAIL)
        code, findings, _ = scan(gitleaks, tree / name, defaults, scratch, 'span-base')
        covered = any(TAIL in f.get('Match', '') for f in findings)
        check('span control: value + U+%04X + tail -> the Match span %s the tail (measured, not assumed)'
              % (ord(ch), 'continues through' if expected == 'continues' else 'stops before'),
              bool(findings) and covered == (expected == 'continues'),
              'exit %s; findings %d; tail covered %s; expected %s' % (code, len(findings), covered, expected))


def benign_control(gitleaks, scratch, defaults):
    tree = scratch / 'benign'
    tree.mkdir(parents=True)
    manifest = tree / 'integrity.json'
    generated = subprocess.run([sys.executable, str(ROOT / 'tests/engineering/T02/revision_integrity.py'),
                                '--out', str(manifest)], capture_output=True, cwd=ROOT)
    generated_out = (generated.stdout + generated.stderr).decode('utf-8', 'replace')
    if generated.returncode != 0 or not manifest.exists():
        check('benign control: manifest written by the T02 generator', False, generated_out.strip()[-160:])
        paths = sorted(str(p.relative_to(ROOT).as_posix())
                       for p in (ROOT / 'tests/engineering/T02/evidence').glob('*.json'))[:25]
        digest_records.write({'files': digest_records.records(paths, root=ROOT)}, manifest)
    else:
        check('benign control: manifest built by tests/engineering/T02/revision_integrity.py', True,
              generated_out.strip())
    text = manifest.read_text(encoding='utf-8')
    check('benign control: no line pairs a key-like word with a long hex token',
          not digest_records.violations(text), digest_records.violations(text))
    for label, config in (('no allowlist at all', defaults), ('delivered config', CONFIG)):
        code, findings, note = scan(gitleaks, manifest, config, scratch, 'benign')
        check('benign control: fingerprint manifest stays clean under %s' % label, not findings,
              'exit %s; %s' % (code, note))


def pairing_gate():
    """A-9: the F-03 root-cause guard runs as a precondition, before any manifest is written.

    digest_records refuses a record that puts the path and its digest on one JSON line; that refusal
    is what keeps a fresh fingerprint manifest from immediately needing a new value exemption. The
    gate proves the guard is live (a paired dump raises) and not over-eager (a split dump passes).
    """
    try:
        digest_records.dumps({'docs/api/openapi.yaml': 'ab' * 32})
        fires = False
    except AssertionError:
        fires = True
    check('pairing gate: digest_records refuses a path+digest written on one line', fires)
    try:
        digest_records.dumps({'files': [{'path': 'docs/api/openapi.yaml', 'sha256': 'ab' * 32}]})
        quiet = True
    except AssertionError:
        quiet = False
    check('pairing gate: a correctly split record is accepted (guard is not over-eager)', quiet)


def count_guard(mode, expected):
    """Pin the size of the battery (round-5 review section 3, structural weakness 1).

    A probe whose default rule does not fire is excluded from the per-probe assertions, so a
    widening of the delivered config can turn '139 PASS' into '115 PASS' with nothing failing: the
    battery shrinks by deletion, not by red. This guard makes the total itself a checked quantity,
    in both directions, so a shrinking or a padded battery is a failure rather than a smaller number.
    """
    check('assertion count: %s mode emits exactly %d assertions (pinned, battery may not shrink or pad)'
          % (mode, expected), EMITTED + 1 == expected,
          'emitted %d before this guard, %d with it / expected %d' % (EMITTED, EMITTED + 1, expected))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--gitleaks', default='gitleaks')
    parser.add_argument('--with-controls', action='store_true', help='run the acceptance controls')
    args = parser.parse_args()
    values = structure(CONFIG.read_text(encoding='utf-8'))
    pairing_gate()
    if not args.with_controls:
        count_guard('structure', EXPECTED_STRUCTURE_ASSERTIONS)
        print('GITLEAKS ALLOWLIST POLICY: ' + ('FAILED ' + json.dumps(failures) if failures else 'PASSED (structure only)'))
        raise SystemExit(1 if failures else 0)
    scanner, problem = resolve_scanner(args.gitleaks)
    if scanner is None:
        check('gitleaks scanner path is usable', False, problem)
        print('GITLEAKS ALLOWLIST POLICY: FAILED ' + json.dumps(['gitleaks scanner path is usable']))
        raise SystemExit(1)
    version = subprocess.run([scanner, 'version'], capture_output=True, cwd=ROOT)
    check('pinned scanner runs', version.returncode == 0,
          (version.stdout + version.stderr).decode('utf-8', 'replace').strip())
    WORK.mkdir(exist_ok=True)
    # The scratch tree is named per process on purpose: two runs in the same working tree (a developer
    # plus CI, or two agent sessions - which is what happened in this repository today) used to
    # `rmtree` each other's probe files mid-battery, and the victim's report came out as void probes
    # and false failures. A crashed run leaves its own directory behind under the gitignored .work
    # tree; that is the cheaper failure, so nothing sweeps the prefix (sweeping would re-open the race).
    scratch = WORK / ('allowlist-controls-%d' % os.getpid())
    shutil.rmtree(scratch, ignore_errors=True)
    scratch.mkdir()
    check('scratch is process-scoped, so a concurrent run cannot delete this run\'s probes',
          scratch.name == 'allowlist-controls-%d' % os.getpid(), scratch.name)
    try:
        defaults = scratch / 'no-allowlist.toml'
        defaults.write_text('title = "defaults only"\n[extend]\nuseDefault = true\n', encoding='utf-8', newline='\n')
        positive_and_blind_spot(scanner, scratch)
        reverse_control(scanner, scratch, values, defaults)
        span_control(scanner, scratch, values, defaults)
        benign_control(scanner, scratch, defaults)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
        check('scratch tree deleted before exit', not scratch.exists(), scratch.relative_to(ROOT).as_posix())
    count_guard('controls', EXPECTED_CONTROL_ASSERTIONS)
    print('GITLEAKS ALLOWLIST POLICY: ' + ('FAILED ' + json.dumps(failures, ensure_ascii=False) if failures else 'PASSED'))
    raise SystemExit(1 if failures else 0)


if __name__ == '__main__':
    main()

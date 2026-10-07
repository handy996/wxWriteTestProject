"""Gitleaks exception policy gate for T02 (CI: run with --with-controls and the pinned scanner).

Structure mode always runs and needs no scanner. It proves `tests/engineering/T02/gitleaks.toml`
carries no file-condition exception: in Gitleaks 8.30.1 an allowlist entry with a file condition
makes the scanner skip that file entirely (its own log reports "scanned 0 bytes"), so the paired
value test never runs and any credential committed into that file stays invisible.

Value exceptions in the delivered config are word-boundary anchored (`\\b<value>\\b`) so allowing a
value is NOT the same as allowing any string that contains it: prefix+value, value+suffix and an
embedded value are all reported again. The truncated 19-character prose digest cannot take a
trailing `\\b` (it ends in a literal dot), so it is guarded by a RE2-safe `[^0-9a-f]`. Lookaround is
not used because Gitleaks 8.30.1 embeds RE2 and panics on `(?<!`/`(?!` (aborting the whole config).

Controls mode runs the acceptance controls with Gitleaks against copies inside gitignored `.work`
only; nothing is written to a tracked path and the scratch tree is deleted before exit:

  positive   synthetic credentials (GitHub PAT, PEM key, AWS-shaped id) planted in copies of the
             three formerly exempted files are caught; a near-miss AWS id (alphabet outside the
             rule's A-Z2-7 set) is planted too and is documented NOT to fire (feature, not defect);
  blind spot the same tree, scanned with the withdrawn file-condition shape, catches none of them;
  reverse    every exempted value changed by one character (first / two middles / last = 44 probes)
             is reported again; the exact value stays suppressed; and substring super-strings of the
             value are reported again (the anchoring is falsifiable);
  benign     the fingerprint manifest the T02 generator now writes stays clean with no allowlist;
  pairing    digest_records refuses a path+digest record written on one line (the F-03 root cause).
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
BARE_METACHARACTER = re.compile(r'[.*+?^${}()\[\]|]')   # wildcard shapes that must never appear
GUARD = '[^0-9a-f]'                                      # RE2-safe trailing guard for the dots value
failures = []


def check(label, condition, detail=''):
    print(('PASS  ' if condition else 'FAIL  ') + label + (('  [' + str(detail) + ']') if detail else ''))
    if not condition:
        failures.append(label)


def blocks_of(text):
    return re.findall(r'\[\[allowlists\]\](.*?)(?=\[\[allowlists\]\]|\Z)', text, re.S)


def entries_of(text):
    return [item for block in blocks_of(text) for item in re.findall(r"'''(.*?)'''", block, re.S)]


def unwrap(entry):
    """Split an anchored exception regex into (kind, core-regex, plain-value).

    kind is 'literal' for `\\b<value>\\b` or 'truncated' for the dots value guarded by `[^0-9a-f]`.
    core-regex still carries regex escapes; plain-value is the un-escaped secret string.
    """
    body = entry
    anchored = body.startswith(r'\b')
    if anchored:
        body = body[2:]
    if body.endswith(r'\b'):
        body, kind = body[:-2], 'literal'
    elif body.endswith(GUARD):
        body, kind = body[:-len(GUARD)], 'truncated'
    else:
        kind = 'unanchored'
    return kind, body, re.sub(r'\\(.)', r'\1', body)


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
            label = 'exception is one full literal value, word-boundary anchored, no wildcard'
            ok = meta_free and value != entry and len(value) >= 16
        elif kind == 'truncated':
            label = 'exception is a truncated-prose digest (literal dots + non-hex guard), not a wildcard'
            ok = meta_free and value.endswith('...') and len(value) >= 16
        else:
            label = 'exception is anchored (word-boundary or non-hex guard)'
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
    """Synthetic credential shapes, assembled at runtime so this source never holds one."""
    token = 'ghp_' + 'SYNTHETICNOTAREALKEY0123456789abcdefghij'
    pem = ('-----BEGIN RSA PRI' 'VATE KEY-----\n'
           'MIIBVgIBADANBgkqhkiG9w0BAQEFAgCVSYNTHETICNOTAREALKEYaaaaaaaaaaaaaaaa\n'
           '-----END RSA PRI' 'VATE KEY-----\n')
    alphabet = ''.join(chr(ord('A') + i) for i in range(16))          # A-P: pure base32, high entropy
    live_akia = 'AKIA' + alphabet                                     # shape aws-access-token matches
    near = list(alphabet)
    near[7] = '1'                                                     # digit outside the A-Z2-7 set
    near_akia = 'AKIA' + ''.join(near)                                # documented near-miss
    return (line for line in (
        'github_token: ' + token,
        pem.rstrip('\n'),
        'aws_access_key_id = ' + live_akia,
        'nearmiss_aws_access_key_id = ' + near_akia,
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
        for stag, token in (('pre', 'ab' + value), ('suf', value + 'cd'), ('emb', '0123456789' + value + 'abcdef')):
            name = 'case-%02d-super-%s.json' % (number, stag)
            _probe(tree, name, token)
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
        check('reverse control: at least two single-character probes stay live for value %02d' % number,
              len(live) >= 2, 'live %d of %d' % (len(live), len(mutated)))
        for name in live:
            check('reverse control: one-character change in %s is reported again' % name, results[name][1],
                  'gate suppressed it')
    check('reverse control: the 44-mutation battery is present (>= 40 live single-character probes)',
          mutation_total >= 40, 'live mutation probes %d' % mutation_total)

    for name, (number, stag, kind) in sorted(cases.items()):
        if kind != 'super':
            continue
        if name in void:
            continue
        check('substring control: super-string %s for value %02d is reported again (not swallowed)' % (stag, number),
              results[name][1], 'the anchored value exception swallowed a longer token')

    for name in sorted(exact_names):
        if name in void:
            continue
        check('reverse control: unchanged value in %s is suppressed by that value only' % name,
              not results[name][1], 'gate reported the exact value')
    if void:
        print('NOTE    probes the rule itself does not report (entropy gate), excluded from the count: %s' % void)


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


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--gitleaks', default='gitleaks')
    parser.add_argument('--with-controls', action='store_true', help='run the acceptance controls')
    args = parser.parse_args()
    values = structure(CONFIG.read_text(encoding='utf-8'))
    pairing_gate()
    if not args.with_controls:
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
    scratch = WORK / 'allowlist-controls'
    shutil.rmtree(scratch, ignore_errors=True)
    scratch.mkdir()
    try:
        defaults = scratch / 'no-allowlist.toml'
        defaults.write_text('title = "defaults only"\n[extend]\nuseDefault = true\n', encoding='utf-8', newline='\n')
        positive_and_blind_spot(scanner, scratch)
        reverse_control(scanner, scratch, values, defaults)
        benign_control(scanner, scratch, defaults)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
        check('scratch tree deleted before exit', not scratch.exists(), scratch.relative_to(ROOT).as_posix())
    print('GITLEAKS ALLOWLIST POLICY: ' + ('FAILED ' + json.dumps(failures, ensure_ascii=False) if failures else 'PASSED'))
    raise SystemExit(1 if failures else 0)


if __name__ == '__main__':
    main()

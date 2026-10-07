"""Gitleaks exception policy gate for T02 (CI: run with --with-controls and the pinned scanner).

Structure mode always runs and needs no scanner. It proves `tests/engineering/T02/gitleaks.toml`
carries no file-condition exception: in Gitleaks 8.30.1 an allowlist entry with a file condition
makes the scanner skip that file entirely (its own log reports "scanned 0 bytes"), so the paired
value test never runs and any credential committed into that file stays invisible.

Controls mode runs the four acceptance controls with Gitleaks against copies inside gitignored
`.work` only; nothing is written to a tracked path and the scratch tree is deleted before exit:

  positive   synthetic credentials planted in copies of the three formerly exempted files are caught;
  blind spot the same tree, scanned with the withdrawn file-condition shape, catches none of them;
  reverse    every exempted value changed by one character is reported again; unchanged stays quiet;
  benign     the fingerprint manifest the T02 generator now writes stays clean with no allowlist at all.
"""
import argparse
import json
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
METACHARACTER = re.compile(r'[.*+?^$(){}\[\]|]')
failures = []


def check(label, condition, detail=''):
    print(('PASS  ' if condition else 'FAIL  ') + label + (('  [' + str(detail) + ']') if detail else ''))
    if not condition:
        failures.append(label)


def blocks_of(text):
    return re.findall(r'\[\[allowlists\]\](.*?)(?=\[\[allowlists\]\]|\Z)', text, re.S)


def entries_of(text):
    return [item for block in blocks_of(text) for item in re.findall(r"'''(.*?)'''", block, re.S)]


def value_of(entry):
    return re.sub(r'\\(.)', r'\1', entry)


def structure(text):
    blocks, entries = blocks_of(text), entries_of(text)
    check('allowlists parsed from the delivered config', bool(blocks), 'blocks %d' % len(blocks))
    occurrences = len(re.findall(r'(?i)\bpaths\b', text)) + len(re.findall(r'(?m)^\s*\w*paths\w*\s*=', text))
    check('no file-condition key in gitleaks.toml (paths occurrences must be 0)', occurrences == 0, occurrences)
    check('default rules extended, never replaced',
          '[extend]' in text and 'useDefault = true' in text and '[[rules]]' not in text)
    check('every allowlist is value-conditional (condition AND, regexTarget match, regexes present)',
          all('condition = "AND"' in b and 'regexTarget = "match"' in b and 'regexes = [' in b for b in blocks))
    check('exception count pinned for review', len(entries) == EXEMPT_VALUE_COUNT,
          '%d seen / %d expected' % (len(entries), EXEMPT_VALUE_COUNT))
    for entry in entries:
        value = value_of(entry)
        check('exception is one literal value with no wildcard: ' + value[:10] + '...',
              not METACHARACTER.search(re.sub(r'\\.', '', entry)) and len(value) >= 16, len(value))
    return [value_of(entry) for entry in entries]


def scan(gitleaks, target, config, scratch, name):
    report = scratch / (name + '.report.json')
    if report.exists():
        report.unlink()
    result = subprocess.run([gitleaks, 'dir', str(target), '--no-banner', '--config', str(config),
                             '--report-format', 'json', '--report-path', str(report)],
                            capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=ROOT)
    findings = json.loads(report.read_text(encoding='utf-8')) if report.exists() else []
    note = [line for line in (result.stdout + result.stderr).splitlines() if 'bytes' in line]
    return result.returncode, findings, (note[-1].strip() if note else '')


def relative_to(finding, tree):
    return pathlib.Path(finding['File']).resolve().relative_to(tree.resolve()).as_posix()


def canary_block():
    """Synthetic credential shapes, assembled at runtime so this source never holds one."""
    token = 'ghp_' + 'SYNTHETICNOTAREALKEY0123456789abcdefghij'
    pem = ('-----BEGIN RSA PRI' 'VATE KEY-----\n'
           'MIIBVgIBADANBgkqhkiG9w0BAQEFAgCVSYNTHETICNOTAREALKEYaaaaaaaaaaaaaaaa\n'
           '-----END RSA PRI' 'VATE KEY-----\n')
    return 'github_token: ' + token + '\n' + pem


def positive_and_blind_spot(gitleaks, scratch):
    tree = scratch / 'canary'
    for name in FORMERLY_EXEMPT:
        target = tree / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
        with target.open('a', encoding='utf-8', newline='\n') as stream:
            stream.write(canary_block())
    expected = {(name, rule) for name in FORMERLY_EXEMPT for rule in ('github-pat', 'private-key')}
    code, findings, note = scan(gitleaks, tree, CONFIG, scratch, 'positive')
    caught = {(relative_to(f, tree), f['RuleID']) for f in findings}
    for name, rule in sorted(expected):
        check('positive control: synthetic %s caught in a copy of %s' % (rule, name), (name, rule) in caught)
    check('positive control: the six canary findings are the only findings',
          caught == expected, 'exit %s; extra %s' % (code, sorted(caught - expected)))
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


def reverse_control(gitleaks, scratch, values, defaults):
    tree = scratch / 'reverse'
    tree.mkdir(parents=True)
    cases = {}
    for number, value in enumerate(values):
        alnum = [index for index, character in enumerate(value) if character.isalnum()]
        for tag, index in (('exact', None), ('first', alnum[0]),
                           ('middle', alnum[len(alnum) // 2]), ('last', alnum[-1])):
            text = value if index is None else flip(value, index)
            name = 'case-%02d-%s.json' % (number, tag)
            (tree / name).write_text('{\n  "docs/api/reference.json": "%s",\n'
                                     '  "note": "openapi.yaml=%s equals docs/execution/contracts/candidate-manifest.json"\n}\n'
                                     % (text, text), encoding='utf-8', newline='\n')
            cases[name] = tag
    results, void = {}, []
    for name in sorted(cases):
        base_code, base_findings, _ = scan(gitleaks, tree / name, defaults, scratch, 'base')
        gate_code, gate_findings, _ = scan(gitleaks, tree / name, CONFIG, scratch, 'gate')
        results[name] = (bool(base_findings), bool(gate_findings), base_code, gate_code)
        if not base_findings:
            void.append(name)
    check('reverse control: every unchanged probe really triggers generic-api-key (control is not void)',
          not [name for name, tag in cases.items() if tag == 'exact' and name in void], void)
    for number in range(len(values)):
        mutated = [name for name, tag in cases.items() if name.startswith('case-%02d-' % number) and tag != 'exact']
        live = [name for name in mutated if results[name][0]]
        check('reverse control: at least two single-character probes stay live for value %02d' % number,
              len(live) >= 2, 'live %d of %d, void %s' % (len(live), len(mutated), [n for n in mutated if n not in live]))
        for name in live:
            reported = results[name][1]
            check('reverse control: one-character change in %s is reported again' % name, reported,
                  'gate exit %s' % results[name][3])
    for name, tag in sorted(cases.items()):
        if tag == 'exact':
            check('reverse control: unchanged value in %s is suppressed by that value only' % name,
                  not results[name][1], 'gate exit %s' % results[name][3])
    if void:
        print('NOTE    probes the rule itself does not report (entropy gate), excluded from the count: %s' % void)


def benign_control(gitleaks, scratch, defaults):
    tree = scratch / 'benign'
    tree.mkdir(parents=True)
    manifest = tree / 'integrity.json'
    generated = subprocess.run([sys.executable, str(ROOT / 'tests/engineering/T02/revision_integrity.py'),
                                '--out', str(manifest)], capture_output=True, text=True,
                               encoding='utf-8', errors='replace', cwd=ROOT)
    if generated.returncode != 0 or not manifest.exists():
        check('benign control: manifest written by the T02 generator', False,
              (generated.stdout + generated.stderr).strip()[-160:])
        paths = sorted(str(p.relative_to(ROOT).as_posix())
                       for p in (ROOT / 'tests/engineering/T02/evidence').glob('*.json'))[:25]
        digest_records.write({'files': digest_records.records(paths, root=ROOT)}, manifest)
    else:
        check('benign control: manifest built by tests/engineering/T02/revision_integrity.py', True,
              generated.stdout.strip())
    text = manifest.read_text(encoding='utf-8')
    check('benign control: no line pairs a key-like word with a long hex token',
          not digest_records.violations(text), digest_records.violations(text))
    for label, config in (('no allowlist at all', defaults), ('delivered config', CONFIG)):
        code, findings, note = scan(gitleaks, manifest, config, scratch, 'benign')
        check('benign control: fingerprint manifest stays clean under %s' % label, not findings,
              'exit %s; %s' % (code, note))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--gitleaks', default='gitleaks')
    parser.add_argument('--with-controls', action='store_true', help='run the four acceptance controls')
    args = parser.parse_args()
    values = structure(CONFIG.read_text(encoding='utf-8'))
    if not args.with_controls:
        print('GITLEAKS ALLOWLIST POLICY: ' + ('FAILED ' + json.dumps(failures) if failures else 'PASSED (structure only)'))
        raise SystemExit(1 if failures else 0)
    scanner = str(pathlib.Path(args.gitleaks).resolve()) if '/' in args.gitleaks or '\\' in args.gitleaks else args.gitleaks
    version = subprocess.run([scanner, 'version'], capture_output=True, text=True, encoding='utf-8', errors='replace')
    check('pinned scanner runs', version.returncode == 0, (version.stdout or version.stderr).strip())
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

"""T02 round-4 controls C-3 (config self-trigger) and C-4 (benign half).

C-3  the delivered config holds eleven long tokens itself. Two measurement modes are separated:
     (a) the file under its real name inside a scanned tree -- gitleaks carries a built-in global
         exception for inputs named gitleaks.toml, which would make "0 hits" vacuous;
     (b) the same bytes copied to a neutral name, scanned with default rules and NO allowlists.
     The pre-deca2a1 config is measured the same way as a positive control (it must self-trigger).
C-4  the fingerprint manifest the T02 generator writes must stay clean with no allowlist at all;
     the generator must refuse to overwrite the frozen r01 records (exit 1, bytes unchanged);
     the record serialiser must reject a path+digest pairing; integration.py's artefact records are
     checked for the same line shape. Scratch lives in tests/engineering/T02/.work (gitignored) and
     is deleted before exit; nothing tracked is written.
"""
import json
import pathlib
import re
import shutil
import subprocess
import sys

PAIR_RE = re.compile(r'[0-9a-f]{32,}')
KEY_RE = re.compile(r'(?i)api|key|token|secret|passwd|password|auth|access|credential|client|cert')


def paired_lines(text):
    return [n for n, line in enumerate(text.splitlines(), 1) if PAIR_RE.search(line) and KEY_RE.search(line)]

ROOT = pathlib.Path(r'E:\project\codex\wxAgent')
HERE = pathlib.Path(__file__).resolve().parent
SCRATCH = ROOT / 'tests/engineering/T02/.work/r4-review-scratch'
GITLEAKS = str(ROOT / '.tools/t02/gitleaks/gitleaks.exe')
PY = sys.executable
FROZEN = ['tests/engineering/T02/evidence/r01-integrity.json',
          'tests/engineering/T02/evidence/r01-integrity-run.json',
          'tests/engineering/T02/evidence/gitleaks-findings.json']
CONFIG = 'tests/engineering/T02/gitleaks.toml'


def sha(path):
    import hashlib
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def defaults_config():
    path = SCRATCH / 'defaults-only.toml'
    path.write_text('title = "defaults only, no allowlists"\n[extend]\nuseDefault = true\n',
                    encoding='utf-8', newline='\n')
    return path


def scan(target, config, name):
    report = SCRATCH / (name + '.report.json')
    if report.exists():
        report.unlink()
    proc = subprocess.run([GITLEAKS, 'dir', str(target), '--no-banner', '--redact', '--config', str(config),
                           '--report-format', 'json', '--report-path', str(report)],
                          capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=ROOT)
    if not report.exists():
        return {'exit': proc.returncode, 'reportWritten': False, 'count': None, 'log': (proc.stdout + proc.stderr)[:400]}
    findings = json.loads(report.read_text(encoding='utf-8'))
    log = (proc.stdout + proc.stderr).splitlines()
    return {'exit': proc.returncode, 'reportWritten': True, 'count': len(findings),
            'rules': sorted({f['RuleID'] for f in findings}),
            'lines': sorted({f.get('Line') for f in findings}),
            'scanned': [l.strip() for l in log if 'bytes' in l][-1:],
            'leakLine': [l.strip() for l in log if 'leak' in l.lower()][-1:]}


def run(argv, name):
    proc = subprocess.run(argv, capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=ROOT)
    return {'exit': proc.returncode,
            'stdout': proc.stdout.strip()[-400:], 'stderr': proc.stderr.strip()[-600:], 'name': name}


def main():
    shutil.rmtree(SCRATCH, ignore_errors=True)
    SCRATCH.mkdir(parents=True)
    defaults = defaults_config()
    before = {p: sha(p) for p in FROZEN + [CONFIG]}
    out = {'c3': {}, 'c4': {}, 'frozenHashes': before}

    # ---- C-3: config self-trigger, both measurement modes -------------------------------
    delivered_text = (ROOT / CONFIG).read_text(encoding='utf-8')
    legacy_text = subprocess.run(['git', 'show', 'deca2a1^:' + CONFIG], capture_output=True,
                                text=True, encoding='utf-8', cwd=ROOT).stdout
    for label, text in (('delivered', delivered_text), ('preDeca2a1', legacy_text)):
        neutral_dir = SCRATCH / ('neutral-' + label)
        neutral_dir.mkdir()
        neutral = neutral_dir / ('snapshot-of-' + label + '-config.txt')
        neutral.write_text(text, encoding='utf-8', newline='\n')
        out['c3'][label + 'NeutralNameNoAllowlist'] = dict(
            bytes=len(neutral.read_bytes()), **scan(neutral, defaults, 'c3-' + label))
        named_dir = SCRATCH / ('named-' + label)
        named_dir.mkdir()
        (named_dir / 'gitleaks.toml').write_text(text, encoding='utf-8', newline='\n')
        out['c3'][label + 'UnderRealFileNameNoAllowlist'] = dict(
            bytes=len((named_dir / 'gitleaks.toml').read_bytes()), **scan(named_dir, defaults, 'c3n-' + label))
    # is the filename exception real? same live-shaped bytes, two names
    shape_dir = SCRATCH / 'filename-probe'
    shape_dir.mkdir()
    live_line = 'api_key = "%s"\n' % ('e285471760a5dce4' + 'f3df7445b6dcf29dcb1e7fefbefd3e9b535440ac8c67eb2b')
    (shape_dir / 'gitleaks.toml').write_text(live_line, encoding='utf-8', newline='\n')
    other = SCRATCH / 'filename-probe2'
    other.mkdir()
    (other / 'not-gitleaks.toml').write_text(live_line, encoding='utf-8', newline='\n')
    out['c3']['filenameExceptionProbe'] = {
        'namedGitleaksToml': scan(shape_dir, defaults, 'c3f1'),
        'namedOtherwise': scan(other, defaults, 'c3f2'),
    }

    # ---- C-4: benign half ---------------------------------------------------------------
    manifest = SCRATCH / 'r02-integrity.json'
    gen = run([PY, str(ROOT / 'tests/engineering/T02/revision_integrity.py'), '--out', str(manifest)],
              'generateManifestIntoScratch')
    out['c4']['generateIntoScratch'] = gen
    if manifest.exists():
        records = json.loads(manifest.read_text(encoding='utf-8'))
        out['c4']['manifestShape'] = {'records': len(records.get('files', [])),
                                      'bytes': manifest.stat().st_size,
                                      'sampleKeys': sorted(records['files'][0].keys()),
                                      'pathsFilterTop3': [r['path'] for r in records['files'][:3]]}
        out['c4']['manifestNoAllowlist'] = scan(manifest, defaults, 'c4-benign')
        out['c4']['manifestDeliveredConfig'] = scan(manifest, ROOT / CONFIG, 'c4-benign-delivered')
        paired = paired_lines(manifest.read_text(encoding='utf-8'))
        out['c4']['pairedKeyAndHexLines'] = paired[:10]
    # refusal to rewrite frozen evidence. Only the two paths the generator itself guards are
    # attempted -- attempting --out on a path it does NOT guard would overwrite tracked evidence,
    # so that case is settled by read-only derivation of the guard instead of execution.
    guarded = [p for p in FROZEN if p.startswith(('tests/engineering/T02/evidence/r01-integrity',))]
    for frozen in guarded:
        out['c4']['refuseFrozen-' + pathlib.Path(frozen).name] = run(
            [PY, str(ROOT / 'tests/engineering/T02/revision_integrity.py'), '--out', frozen],
            'refuseFrozen-' + pathlib.Path(frozen).name)
    guard_source = (ROOT / 'tests/engineering/T02/revision_integrity.py').read_text(encoding='utf-8')
    out['c4']['guardCoverageByDerivation'] = {
        'guardedPaths': guarded,
        'unguardedFrozenEvidenceRequiredInvariant': [p for p in FROZEN if p not in guarded],
        'frozenTupleInSource': re.search(r'FROZEN = \(([^)]*)\)', guard_source, re.S).group(1).split(),
        'note': 'evidence/gitleaks-findings.json is required byte-invariant by this review but is not in the generator FROZEN tuple; --out on it would overwrite it, so it was NOT attempted'}
    out['c4']['outsideRepoOut'] = run([PY, str(ROOT / 'tests/engineering/T02/revision_integrity.py'),
                                      '--out', str(pathlib.Path.home() / 'AppData/Local/Temp/t02r4/outside.json')],
                                     'outOutsideRepo')
    # serialiser refuses a pairing
    sys.path.insert(0, str(ROOT / 'tests/engineering/T02'))
    import digest_records
    try:
        digest_records.write({'docs/api/openapi.yaml': 'ab' * 32}, SCRATCH / 'paired.json')
        out['c4']['serialiserRefusesPairing'] = 'NO EXCEPTION - GUARD INERT'
    except AssertionError as error:
        out['c4']['serialiserRefusesPairing'] = 'AssertionError: %s' % str(error)[:160]
    try:
        digest_records.check([{'path': 'backend/secret-baseline.sql', 'sha256': 'cd' * 32}])
        out['c4']['recordSplitIsClean'] = True
    except AssertionError as error:
        out['c4']['recordSplitIsClean'] = 'FALSE POSITIVE ON SPLIT RECORD: %s' % error
    # integration.py: importable, --help works, and its artefact records use the split shape
    out['c4']['integrationHelp'] = run([PY, str(ROOT / 'tests/engineering/T02/integration.py'), '--help'],
                                       'integrationHelp')
    tracked_integration = ROOT / 'tests/engineering/T02/evidence/integration.json'
    text = tracked_integration.read_text(encoding='utf-8')
    out['c4']['trackedIntegrationEvidence'] = {
        'bytes': len(text.encode('utf-8')),
        'hasArtifactsKey': '"artifacts"' in text,
        'pairedKeyAndHexLines': paired_lines(text)[:5],
        'note': 'line shape of the serialiser used by digest_records.records()'}
    out['frozenHashesAfter'] = {p: sha(p) for p in FROZEN + [CONFIG]}
    out['frozenUnchanged'] = all(out['frozenHashesAfter'][p] == before[p] for p in before)

    print(json.dumps(out, ensure_ascii=False, indent=2)[:6000])
    (HERE / 'evidence' / 'c3-c4-config-and-benign.json').write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    shutil.rmtree(SCRATCH, ignore_errors=True)
    print('scratch removed:', not SCRATCH.exists())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

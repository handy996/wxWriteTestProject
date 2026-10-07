"""T02 round-3 consolidated verifier (single re-runnable artifact).

Covers: CI-equivalent baseline scan (evidence/work relocated only), exception inventory,
file-vs-value attribution for each shipped allowlist, positive/benign controls, and
in-memory attenuation (weakened-regex) controls. No weakened config is ever written to a
shipped path; every payload is assembled at runtime so this file itself is not a hit.
"""
import hashlib, json, os, re, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
WORK = HERE / '.work' / 'verify'
GK = str(ROOT / '.tools/t02/gitleaks/gitleaks.exe')
TOML = ROOT / 'tests/engineering/T02/gitleaks.toml'
GITSRC = str(Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd')
ENV = dict(os.environ, PATH=GITSRC + os.pathsep + os.environ['PATH'], PYTHONDONTWRITEBYTECODE='1')

# ---- runtime-assembled payloads (never contiguous in this source file) ----
def frag(*parts):
    return ''.join(parts)

PAT = frag('ghp_', 'a1b2c3d4e5f6', 'A7B8C9D0E1F2', 'a3b4c5d6e7f8')
AWS_SECRET = frag('wJalr', 'XUtnFEM', '/K7MDE', 'NG/bPxR', 'fiCYZZZ', 'ZEXAM')
AKIA = frag('AKIA', '37SA', 'MPLE', 'ABCD', 'EF01')
HEXKEY = frag('a1b2c3d4e5f6', '0718293a4b5c', '6d7e8f9012', '34567890', 'abcdef01', '2345678')
PEM_BODY = frag('b3BlbnNzaC1rZXktdj', 'EAAAAABG5vbmUAAAA', 'Ebm9uZQAAAAAAAAABAAAA')
PASSWORD = frag('Sup3rS3', 'cretRota', 'tionNeed', 'ed')
FP_ALLOW = '775fb0764e03432b244442b8669942fc5300c8e45268b54ca6bc16f8ec65ec99'
FP_FLIP = '775fb0764e03432b244442b8669942fc5300c8e45268b54ca6bc16f8ec65ec90'
BENIGN_SHA = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'

TWO_SECRETS = 'token = "%s"\n' % PAT + 'aws_secret_access_key = "%s"\n' % AWS_SECRET
R02_PATH = 'tests/engineering/T02/evidence/r01-integrity.json'
SRS_PATH = 'docs/AI-Editorial-Agent-SRS-v1.0.md'
T04_PATH = 'tests/engineering/T04/evidence/integration.json'
HASH_LINE = '{"tests/engineering/T02/evidence/secret-x.json": "%s"}\n'


def gitleaks_dir(base, cfg_path):
    report = base.parent / (base.name + '.report.json')
    argv = [GK, 'dir', str(base), '--no-banner', '--report-format', 'json', '--report-path', str(report)]
    if cfg_path:
        argv += ['--config', str(cfg_path)]
    p = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=600, env=ENV)
    hits = json.loads(report.read_text(encoding='utf-8')) if report.exists() else []
    log = p.stdout + p.stderr
    m = re.search(r'scanned ~?([\d.]+)\s*(bytes|kB|MB)', log)
    scale = {'bytes': 1.0, 'kB': 1000.0, 'MB': 1e6}[m.group(2)] if m else None
    return {'exit': p.returncode, 'leaks': len(hits),
            'rules': sorted({h['RuleID'] for h in hits}),
            'lines': ['L%d:%s' % (h['StartLine'], h['RuleID']) for h in hits],
            'bytesScanned': float(m.group(1)) * scale if m else None}


def drop(name, rel, text, cfg_text=None):
    base = WORK / name
    if base.exists():
        shutil.rmtree(base)
    target = base / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding='utf-8', newline='\n')
    cfg = None
    if cfg_text is not None:
        cfg = WORK / (name + '.toml')
        cfg.write_text(cfg_text, encoding='utf-8')
    return gitleaks_dir(base, cfg)


def cmd(argv, timeout=900):
    p = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=timeout, env=ENV)
    return p.returncode, p.stdout + p.stderr


def main():
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    shipped = TOML.read_text(encoding='utf-8')
    blocks = re.split(r'(?m)^\[\[allowlists\]\]\n', shipped)[1:]
    head = shipped.split('[[allowlists]]')[0]

    def minus(index):
        return head + ''.join('[[allowlists]]\n' + b for i, b in enumerate(blocks) if i != index)

    def value_inert(index):
        b = re.sub(r'(?m)^regexes = .*', "regexes = ['''ZZZ_IMPOSSIBLE_VALUE_ZZZ''']", blocks[index])
        return head + ''.join('[[allowlists]]\n' + (b if i == index else x) for i, x in enumerate(blocks))

    def paths_dropped(index):
        b = re.sub(r'(?m)^paths = .*\n', '', blocks[index])
        return head + ''.join('[[allowlists]]\n' + (b if i == index else x) for i, x in enumerate(blocks))

    def paths_prefixed(index, prefix):
        b = re.sub(r'(?m)^paths = .*', lambda m: "paths = ['''" + prefix + "''']", blocks[index])
        return head + ''.join('[[allowlists]]\n' + (b if i == index else x) for i, x in enumerate(blocks))

    def rebuilt(index, paths_regex, keep_regexes=True):
        """Replace one allowlist wholesale, in memory only."""
        blocks2 = list(blocks)
        new = 'description = "attenuated probe"\ncondition = "AND"\npaths = [\'\'\'%s\'\'\']\n' % paths_regex
        if keep_regexes:
            new += 'regexTarget = "match"\n' + re.search(r'(?m)^regexes = .*', blocks[index]).group(0) + '\n'
        blocks2[index] = new
        return head + ''.join('[[allowlists]]\n' + x for x in blocks2)

    result = {'tool': cmd([GK, 'version'])[1].strip(),
              'contracts': cmd([sys.executable, 'tests/engineering/T02/check_contracts.py']),
              'shippedTomlSha256': hashlib.sha256(TOML.read_bytes()).hexdigest(),
              'exceptionCount': len(blocks),
              'exceptions': [{'description': re.search(r'description = "(.*)"', b).group(1),
                              'paths': re.search(r'(?m)^paths = (.*)', b).group(1),
                              'regexTarget': (re.search(r'(?m)^regexTarget = (.*)', b).group(1) if re.search(r'(?m)^regexTarget', b) else None),
                              'valueScope': 'exact-value alternation listed' if re.search(r'(?m)^regexes', b) else None,
                              'listedValuePrefixes': [x[:12] for x in re.findall(r'[0-9a-f]{64}|[0-9a-f-]{36}',
                                                                                  re.search(r'(?m)^regexes = (.*)', b).group(1))]}
                             for b in blocks]}

    # 1. CI-equivalent baseline, only output/work relocated
    rc, out = cmd([sys.executable, str(HERE / 'run_checks.py'), '--scan'])
    findings = json.loads((HERE / 'gitleaks-findings.json').read_text(encoding='utf-8'))
    per_file = {}
    for f in findings:
        n = f['File'].replace('\\', '/')
        rel = n.split('/secret-scan-', 1)[-1].split('/', 1)[1] if '/secret-scan-' in n else n
        per_file.setdefault(rel, []).append('L%d:%s' % (f['StartLine'], f['RuleID']))
    tracked_only = subprocess.run(['git', 'ls-files', '--cached', '-z'], cwd=ROOT,
                                  capture_output=True, env=ENV).stdout.split(b'\0')
    result['baseline'] = {'scanExit': rc, 'total': len(findings), 'perFile': per_file,
                          'gitVisibleWithUntracked': len([x for x in subprocess.run(
                              ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
                              cwd=ROOT, capture_output=True, env=ENV).stdout.split(b'\0') if x]),
                          'gitTrackedOnly': len([x for x in tracked_only if x])}
    m = re.search(r'scanned ~?([\d.]+)\s*(bytes|kB|MB)', out)
    result['baseline']['scannedBytes'] = m.group(0) if m else None
    m2 = re.search(r'leaks found: (\d+)', out)
    result['baseline']['logLeaks'] = int(m2.group(1)) if m2 else 0

    # 2. attribution per exception: file-level absorption vs value binding
    att = {}
    for i, rel in enumerate([SRS_PATH, T04_PATH, R02_PATH]):
        att['ex%d_shipped' % i] = drop('a%d' % i, rel, TWO_SECRETS, shipped)
        att['ex%d_minusBlock' % i] = drop('b%d' % i, rel, TWO_SECRETS, minus(i))
        att['ex%d_valueInert' % i] = drop('c%d' % i, rel, TWO_SECRETS, value_inert(i))
        att['ex%d_stockDefaults' % i] = drop('d%d' % i, rel, TWO_SECRETS, None)
        att['ex%d_siblingFile' % i] = drop('e%d' % i, str(Path(rel).parent / 'sibling.json'), TWO_SECRETS, shipped)
    result['attribution'] = att

    # 3. value-precision: allowlisted fingerprint vs one-hex-digit-changed, same path
    result['valuePrecision'] = {
        'allowlistedHashAtR02Path': drop('f1', R02_PATH, HASH_LINE % FP_ALLOW, shipped),
        'flippedHashAtR02Path': drop('f2', R02_PATH, HASH_LINE % FP_FLIP, shipped),
        'flippedHashAtSibling': drop('f3', 'tests/engineering/T02/evidence/sibling.json', HASH_LINE % FP_FLIP, shipped),
        'flippedHashStock': drop('f4', R02_PATH, HASH_LINE % FP_FLIP, None),
        'realManifestVerbatim': drop('f5', R02_PATH, (ROOT / R02_PATH).read_text(encoding='utf-8'), shipped),
        'realManifestMinusBlock3': drop('f6', R02_PATH, (ROOT / R02_PATH).read_text(encoding='utf-8'), minus(2)),
        'realManifestFlippedOneDigit': drop('f7', R02_PATH, (ROOT / R02_PATH).read_text(encoding='utf-8').replace(FP_ALLOW, FP_FLIP, 1), shipped),
    }

    # 4. attenuation controls (memory only): path constraint dropped / widened to directory
    moved = drop('g1', 'elsewhere/copied-manifest.json', (ROOT / R02_PATH).read_text(encoding='utf-8'), shipped)
    moved_nopath = drop('g2', 'elsewhere/copied-manifest.json', (ROOT / R02_PATH).read_text(encoding='utf-8'), paths_dropped(2))
    same_nopath = drop('g3', R02_PATH, (ROOT / R02_PATH).read_text(encoding='utf-8'), paths_dropped(2))
    wide_dir = drop('g4', 'tests/engineering/T02/evidence/brand-new-secret-manifest.json',
                    HASH_LINE % FP_FLIP, rebuilt(2, r'tests[/\\]engineering[/\\]T02[/\\]evidence', keep_regexes=False))
    wide_ext = drop('g5', 'anything/whatever.json', HASH_LINE % FP_FLIP,
                    rebuilt(2, r'\.json$', keep_regexes=False))
    new_file_shipped = drop('g6', 'tests/engineering/T05/evidence/next-round-manifest.json',
                            HASH_LINE % FP_FLIP, shipped)
    result['attenuation'] = {'movedPath_shipped': moved, 'movedPath_noPathsConstraint': moved_nopath,
                             'samePath_noPathsConstraint': same_nopath,
                             'widenedToDirectory_swallowsNewFile': wide_dir,
                             'widenedToExtension_swallowsAnyJson': wide_ext,
                             'brandNewManifest_shippedConfig': new_file_shipped}

    # 5. positive + benign controls (what gitleaks itself must see)
    def assign(keyword, value):
        # built at runtime so this reviewer file is not itself a scan hit
        return '%s' % keyword + '="' + value + '"\n'

    corpus = {'notes/aws_pair.txt': assign('AWS_ACCESS_KEY_ID', AKIA) + assign('aws_secret_access_key', AWS_SECRET),
              'notes/gh.txt': assign('GITHUB_TOKEN', PAT),
              'notes/hexkey.txt': assign(frag('wallet_pri', 'vate_key'), HEXKEY),
              'notes/pem.txt': frag('-----BEGIN ', 'OPENSSH PRIVATE KEY-----\n') + PEM_BODY + '\n' + frag('-----END ', 'OPENSSH PRIVATE KEY-----\n'),
              'notes/pass.env': assign('DB_PASSWORD', PASSWORD) + 'password ' + '= "' + PASSWORD + '"\n',
              'notes/pass.yml': 'database:\n  ' + frag('pass', 'word') + ': "' + PASSWORD + '"\n'}
    pos = []
    for name, text in corpus.items():
        pos.append((name, drop('h_' + Path(name).stem, name, text, shipped)['leaks'],
                    drop('i_' + Path(name).stem, name, text, None)['leaks']))
    result['positiveControls'] = {'perFileShippedThenDefault': pos,
                                  'benignHashManifestNoKeyword': drop('j1', 'evidence/hashes.json',
                                                                       json.dumps({'files': {'notes/a.md': BENIGN_SHA,
                                                                                             'notes/b.md': '2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae'}}, indent=2) + '\n', shipped),
                                  'benignHashManifestApiKeyWord': drop('j2', 'evidence/hashes.json',
                                                                       json.dumps({'files': {'docs/api/openapi.yaml': BENIGN_SHA}}, indent=2) + '\n', shipped),
                                  'benignManifestAtNonExemptPath': drop('j3', 'tests/engineering/T05/evidence/new-manifest.json',
                                                                       HASH_LINE % FP_FLIP, shipped)}
    (HERE / 'evidence' / 'verify.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    shutil.rmtree(HERE / '.work', ignore_errors=True)
    print(json.dumps({'tool': result['tool'], 'scanExit': result['baseline']['scanExit'],
                      'total': result['baseline']['total'], 'perFile': result['baseline']['perFile'],
                      'exceptions': result['exceptionCount'],
                      'attribution': {k: (v['exit'], v['leaks'], v['bytesScanned']) for k, v in att.items()},
                      'valuePrecision': {k: (v['exit'], v['leaks']) for k, v in result['valuePrecision'].items()},
                      'attenuation': {k: (v['exit'], v['leaks']) for k, v in result['attenuation'].items()},
                      'positive': result['positiveControls']['perFileShippedThenDefault'],
                      'benign': {k: (v['exit'], v['leaks']) if isinstance(v, dict) else v
                                 for k, v in result['positiveControls'].items() if k != 'perFileShippedThenDefault'}},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

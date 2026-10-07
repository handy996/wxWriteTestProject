"""Independent R05 review harness (T02 round 5).

Writes probes only under the given scratch dir; never touches the repository.
Scans each probe twice: with a defaults-only config (control must be red) and with a config
under test, then prints/report JSON to stdout.

Usage: python probe.py <scratch> <mode>
  mode = re2 | attack | entropy | prefix | stable
"""
import hashlib
import json
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys

REPO = pathlib.Path(r'E:\project\codex\wxAgent')
PY = sys.executable
GITLEAKS = str(REPO / '.tools/t02/gitleaks/gitleaks.exe')
DELIVERED = REPO / 'tests/engineering/T02/gitleaks.toml'
SCRATCH = pathlib.Path(sys.argv[1]).resolve()
MODE = sys.argv[2]
SCRATCH.mkdir(parents=True, exist_ok=True)

DEFAULTS = SCRATCH / 'defaults.toml'
DEFAULTS.write_text('title = "defaults only"\n[extend]\nuseDefault = true\n', encoding='utf-8', newline='\n')

VALUES = [
    '397c4e7a-d8f0-4d83-b885-342f8248d8e2',
    '55565d49-a894-42ec-8a42-df7e2dc50a86',
    '775fb0764e03432b244442b8669942fc5300c8e45268b54ca6bc16f8ec65ec99',
    'ecfd7efc8206f890bc399b096c9627de4b348eece6ee83b883f1823bb881a8ea',
    'ac4a337a11169f14168abdb644d8d7c2df62c21ff26b5d0c9d3496dee0bd8cc4',
    '408651c696839292bfb9c713eefbf65f5f525e864a5a49466608822626576ac9',
    '394de144ba3293d6b1affcc1be4722a94d4bfe56990c7e6e9a3f702ccfebf4bc',
    '568ac57369de4cb42da124ae56570797323abadcded57f5fcf40933b3a9f6eb1',
    'e285471760a5dce4f3df7445b6dcf29dcb1e7fefbefd3e9b535440ac8c67eb2b',
    '0db04ea086c2c563b2153b851b54e44c80d1d1c23d927ee49f62f9cc92da68fd',
    'e285471760a5dce4' + chr(46) * 3,
]
PREFIX16 = 'e285471760a5dce4'
DOTS = chr(46) * 3


def write_probe(tree, name, token):
    """A generic-api-key shaped record: keyword path + long token, same shape as the delivered battery."""
    path = tree / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{\n  "docs/api/reference.json": "%s",\n'
                    '  "note": "openapi.yaml=%s equals docs/execution/contracts/candidate-manifest.json"\n}\n'
                    % (token, token), encoding='utf-8', newline='\n')
    return path


def write_akia(tree, name, suffix, keyword='aws_access_key_id'):
    path = tree / name
    path.parent.mkdir(parents=True, exist_ok=True)
    body = 'AKIA' + suffix
    lines = ['%s = %s' % (keyword, body),
             '# near-miss aws key candidate, synthetic, not a live credential',
             'plain_aws_access_key_id_line_below']
    lines.append(body)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
    return path


def scan(target, config, tag):
    report = SCRATCH / ('%s.report.json' % tag)
    if report.exists():
        report.unlink()
    result = subprocess.run([GITLEAKS, 'dir', str(target), '--no-banner', '--config', str(config),
                             '--report-format', 'json', '--report-path', str(report)],
                            capture_output=True, cwd=str(REPO))
    blob = (result.stdout + result.stderr).decode('utf-8', 'replace')
    findings = json.loads(report.read_bytes().decode('utf-8', 'replace')) if report.exists() else []
    note = [line for line in blob.splitlines() if 'bytes' in line]
    return {'exit': result.returncode, 'n': len(findings),
            'rules': sorted({f['RuleID'] for f in findings}),
            'match': sorted({f.get('Match', '') for f in findings})[:3],
            'scanned': (note[-1].strip() if note else ''), 'blob': blob}


def shannon(s):
    counts = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def flip(value, index):
    character = value[index]
    pool = '0123456789abcdef' if character in '0123456789abcdef' else 'abcdefghijklmnopqrstuvwxyz0123456789'
    unused = [c for c in pool if c != character and c not in value]
    return value[:index] + (unused or [c for c in pool if c != character] or ['z'])[0] + value[index + 1:]


def alnum_positions(value):
    idx = [i for i, ch in enumerate(value) if ch.isalnum()]
    out, seen = [], set()
    for tag, i in (('first', idx[0]), ('middle', idx[len(idx) // 2]),
                   ('upper', idx[2 * len(idx) // 3]), ('last', idx[-1])):
        if i not in seen:
            seen.add(i)
            out.append((tag, i))
    return out


RESULTS = []


def case(name, token, config, expect=None):
    tree = SCRATCH / 'tree' / name
    write_probe(tree, 'p.json', token)
    base = scan(tree, DEFAULTS, 'base-' + name)
    gate = scan(tree, config, 'gate-' + name)
    shutil.rmtree(tree, ignore_errors=True)
    item = {'name': name, 'token': token, 'base_n': base['n'], 'base_rules': base['rules'],
            'gate_exit': gate['exit'], 'gate_n': gate['n'], 'gate_rules': gate['rules'],
            'base_exit': base['exit'], 'base_scanned': base['scanned'], 'gate_scanned': gate['scanned']}
    RESULTS.append(item)
    print('%-42s base=%d%s gate=%d%s  %s' % (
        name, base['n'], ('(x%d)' % base['exit']) if base['exit'] != 1 else '',
        gate['n'], ('(x%d)' % gate['exit']) if gate['exit'] != 1 else '', token[:70]))
    return item


def main():
    if MODE == 're2':
        # reproduce the lookaround claim: the delivered config with one entry wrapped in negative lookaround
        text = DELIVERED.read_text(encoding='utf-8')
        variants = {}
        variants['lookbehind'] = text.replace("'''\\b" + VALUES[2] + "\\b'''",
                                              "'''(?<![0-9a-f])" + VALUES[2] + "(?![0-9a-f])'''")
        variants['lookahead'] = text.replace("'''\\b" + VALUES[2] + "\\b'''",
                                             "'''(?!" + VALUES[2] + ")'''")
        variants['lookahead_simple'] = text.replace("'''\\b" + VALUES[2] + "\\b'''",
                                                    "'''\\b" + VALUES[2] + "(?![0-9a-f])'''")
        tree = SCRATCH / 're2-target'
        write_probe(tree, 'p.json', VALUES[2])
        write_probe(SCRATCH / 're2-target-other', 'p.json', VALUES[3])
        for tag, body in variants.items():
            cfg = SCRATCH / ('re2-%s.toml' % tag)
            changed = body != text
            cfg.write_text(body, encoding='utf-8', newline='\n')
            r1 = scan(tree, cfg, 're2-' + tag)
            r2 = scan(SCRATCH / 're2-target-other', cfg, 're2other-' + tag)
            print('VARIANT %-18s substituted=%s exit=%s n=%s scanned=%s' % (tag, changed, r1['exit'], r1['n'], r1['scanned']))
            print('   untouched value 03 under same config: exit=%s n=%s' % (r2['exit'], r2['n']))
            first = [line for line in r1['blob'].splitlines() if 're2' in line or 'Error' in line or 'panic' in line]
            print('   stderr head: %s' % (first[:3]))
            RESULTS.append({'name': 're2-' + tag, 'exit': r1['exit'], 'n': r1['n'],
                            'other_n': r2['n'], 'scanned': r1['scanned'], 'head': first[:3],
                            'substituted': changed})
    elif MODE == 'attack':
        targets = {}
        for i, v in enumerate(VALUES[:10]):
            targets['exact-%02d' % i] = v
            targets['pre-alnum-%02d' % i] = 'ab' + v
            targets['suf-alnum-%02d' % i] = v + 'cd'
            targets['suf-dash-%02d' % i] = v + '-Zk3xQ9mTg7Lp5Rw2'
            targets['pre-dash-%02d' % i] = 'Zk3xQ9mTg7Lp5Rw2-' + v
            targets['suf-dot-%02d' % i] = v + '.Zk3xQ9mTg7Lp5Rw2'
            targets['suf-eq-%02d' % i] = v + '=Zk3xQ9mTg7Lp5Rw2'
            targets['suf-us-%02d' % i] = v + '_Zk3xQ9mTg7Lp5Rw2'
            targets['mid-dash-%02d' % i] = 'Zk3xQ9mT' + '-' + v + '-' + 'g7Lp5Rw2'
        # entry 11 (truncated prose digest) family; tails kept long so the rule itself fires (no void probes)
        targets['exact-10'] = VALUES[10]
        targets['10-dots-then-lowerhex'] = PREFIX16 + DOTS + 'deadbeefcafe0123456789abcdef01'
        targets['10-dots-then-upperhex'] = PREFIX16 + DOTS + 'DEADBEEFCAFE0123456789ABCDEF01'
        targets['10-dots-then-nonhex-g'] = PREFIX16 + DOTS + 'gh7Yk2mQ9xWz4Bv5Cx3Tn6Rm1Qs8Lp'
        targets['10-dots-then-nonhex-Z'] = PREFIX16 + DOTS + 'Zk3xQ9mTg7Lp5Rw2Bv5Cx3Tn6Rm1Qs'
        targets['10-dots-then-dash'] = PREFIX16 + DOTS + '-Zk3xQ9mTg7Lp5Rw2Bv5Cx3Tn6Rm1Qs'
        targets['10-dots-then-space-word'] = PREFIX16 + DOTS + ' Zk3xQ9mTg7Lp5Rw2Bv5Cx3Tn6Rm'
        targets['10-pre-dash'] = 'Zk3xQ9mTg7Lp5Rw2-' + VALUES[10]
        targets['10-dots-two'] = PREFIX16 + chr(46) * 2 + 'gh7Yk2mQ9xWz4Bv5Cx3Tn6Rm1Qs8Lp'
        targets['10-dots-four'] = PREFIX16 + chr(46) * 4 + 'gh7Yk2mQ9xWz4Bv5Cx3Tn6Rm1Qs8Lp'
        targets['10-other-prefix'] = 'f1e2d3c4b5a69788' + DOTS + 'gh7Yk2mQ9xWz4Bv5Cx3Tn6Rm1Qs'
        targets['coll-full-hex-same-prefix'] = PREFIX16 + '13579bdf02468ace13579bdf02468ace13579bdf0246'
        targets['coll-full-hex-same-prefix-2'] = PREFIX16 + '9999999900000000abcdef1234567890fedcba098765'
        targets['coll-64hex-embedded'] = 'q7' + PREFIX16 + '13579bdf02468ace13579bdf02468ace13579bdf0246'
        cfg = os.environ.get('REV5_CONFIG', str(DELIVERED))
        for name in sorted(targets):
            case(name, targets[name], cfg)
    elif MODE == 'mutation':
        cfg = os.environ.get('REV5_CONFIG', str(DELIVERED))
        for i, v in enumerate(VALUES):
            for tag, index in alnum_positions(v):
                case('mut-%02d-%s' % (i, tag), flip(v, index), cfg)
    elif MODE == 'entropy':
        tree = SCRATCH / 'entropy'
        rows = []
        letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'   # base32 alphabet, A first
        for k in range(1, 17):
            # near-uniform spread of k distinct symbols over 16 positions (mirrors the ledger sweep)
            counts = [16 // k] * k
            for j in range(16 - sum(counts)):
                counts[j] += 1
            suffix = ''.join(letters[j] * counts[j] for j in range(k))
            assert len(suffix) == 16 and len(set(suffix)) == k and re.fullmatch(r'[A-Z2-7]{16}', suffix)
            item = write_akia(tree, 'e%02d.json' % k, suffix)
            r = scan(item, DELIVERED, 'ent-%02d' % k)
            full = 'AKIA' + suffix
            rows.append({'k': k, 'suffix': suffix, 'h_suffix': round(shannon(suffix), 4),
                         'h_full': round(shannon(full), 4), 'caught': r['n'] > 0, 'exit': r['exit'],
                         'rules': r['rules']})
            print('k=%2d suffix=%s h16=%.4f h20=%.4f caught=%s %s' % (
                k, suffix, shannon(suffix), shannon(full), r['n'] > 0, r['rules']))
        RESULTS.append({'name': 'entropy-sweep', 'rows': rows})
    elif MODE == 'prefix':
        for keyword in ('aws_access_key_id', 'akia_context_line', 'AKIA'):
            tree = SCRATCH / ('prefix-' + re.sub(r'\W', '_', keyword))
            write_akia(tree, 'p.json', 'ABCDEFGHIJKLMNOP', keyword=keyword)
            r = scan(tree, DELIVERED, 'kw-' + re.sub(r'\W', '_', keyword))
            print('keyword=%-22s n=%s rules=%s' % (keyword, r['n'], r['rules']))
            RESULTS.append({'name': 'keyword-' + keyword, 'n': r['n'], 'rules': r['rules']})
    elif MODE == 'stable':
        names = ['gitleaks.toml', 'sub-gitleaks.toml', '.gitleaks.toml', 'gitleaks.toml.bak',
                 'dir-gitleaks.toml.txt', 'plain.txt', 'gitleaks-toml.txt']
        token = VALUES[2] + '-Zk3xQ9mTg7Lp5Rw2'
        for name in names:
            tree = SCRATCH / ('stable-' + re.sub(r'\W', '_', name))
            tree.mkdir(parents=True, exist_ok=True)
            (tree / name).write_text('{\n  "docs/api/reference.json": "%s"\n}\n' % token,
                                     encoding='utf-8', newline='\n')
            r = scan(tree, DEFAULTS, 'st-' + re.sub(r'\W', '_', name))
            print('%-24s exit=%s n=%s scanned=%s' % (name, r['exit'], r['n'], r['scanned']))
            RESULTS.append({'name': name, 'exit': r['exit'], 'n': r['n'], 'scanned': r['scanned'],
                            'n_of_3': sum(1 for x in ())})
        shutil.rmtree(SCRATCH / 'stable-trees', ignore_errors=True)
    else:
        raise SystemExit('unknown mode')
    print(json.dumps(RESULTS, ensure_ascii=False)[:400])
    (SCRATCH / ('%s.json' % MODE)).write_text(json.dumps(RESULTS, ensure_ascii=False, indent=2) + '\n',
                                              encoding='utf-8', newline='\n')


main()

r"""T02 round-4 control C-2: every exempted value must be individually falsifiable.

Reads the eleven literal values out of tests/engineering/T02/gitleaks.toml itself, then for each
value writes probe files under $env:TEMP\t02r4\c2 and scans each probe twice:
  defaults-only config  -> the probe must be reported (otherwise the control is void, not passed)
  delivered config      -> the unchanged value must be suppressed; every single-character change
                           (first, two mid positions, last) must be reported again
Extra attacks the implementer did not run: the value embedded in a LONGER token (prefix + value,
value + suffix), which is what an unanchored allowlist regex really matches, and the same value
placed on a real credential line (secret_key / aws_secret_access_key / password).
Nothing in the repository is written.
"""
import json
import pathlib
import re
import shutil
import subprocess

ROOT = pathlib.Path(r'E:\project\codex\wxAgent')
HERE = pathlib.Path(__file__).resolve().parent
SCRATCH = pathlib.Path.home() / 'AppData/Local/Temp/t02r4/c2'
GITLEAKS = str(ROOT / '.tools/t02/gitleaks/gitleaks.exe')
CONFIG = ROOT / 'tests/engineering/T02/gitleaks.toml'
SHAPES = {
    'json-pair': lambda v: '{\n  "docs/api/openapi.yaml": "%s",\n  "note": "openapi.yaml=%s equals manifest"\n}\n' % (v, v),
    'idempotency': lambda v: 'X-Request-Idempotency-Key: %s\n' % v,
    'api-key-assignment': lambda v: 'api_key = "%s"\n' % v,
    'secret-key-line': lambda v: 'aws_secret_access_key = "%s"\n' % v,
}


def values_from_config(text):
    blocks = re.findall(r'\[\[allowlists\]\](.*?)(?=\[\[allowlists\]\]|\Z)', text, re.S)
    entries = [item for block in blocks for item in re.findall(r"'''(.*?)'''", block, re.S)]
    return [re.sub(r'\\(.)', r'\1', e) for e in entries], blocks, entries


def flip(value, index, charset):
    pool = [c for c in charset if c != value[index]]
    return value[:index] + pool[0] + value[index + 1:]


def scan_file(path, config, name):
    report = SCRATCH / (name + '.json')
    if report.exists():
        report.unlink()
    proc = subprocess.run([GITLEAKS, 'dir', str(path), '--no-banner', '--redact', '--config', str(config),
                           '--report-format', 'json', '--report-path', str(report)],
                          capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=ROOT)
    if not report.exists():
        return None
    findings = json.loads(report.read_text(encoding='utf-8'))
    return {'exit': proc.returncode, 'count': len(findings),
            'secrets': sorted({f.get('Secret') or '' for f in findings})}


def probe(tree_dir, name, text):
    path = tree_dir / name
    path.write_text(text, encoding='utf-8', newline='\n')
    return path


def main():
    shutil.rmtree(SCRATCH, ignore_errors=True)
    tree = SCRATCH / 'tree'
    tree.mkdir(parents=True)
    defaults = SCRATCH / 'defaults-only.toml'
    defaults.write_text('title = "defaults only"\n[extend]\nuseDefault = true\n', encoding='utf-8', newline='\n')
    values, blocks, entries = values_from_config(CONFIG.read_text(encoding='utf-8'))
    print('config blocks %d, entries %d, decoded values %d' % (len(blocks), len(entries), len(values)))

    rows = []
    for number, value in enumerate(values):
        charset = ('0123456789abcdef' if re.fullmatch(r'[0-9a-f]{32,}', value)
                   else '0123456789abcdef' if re.fullmatch(r'[0-9a-f-]{32,}', value)
                   else 'abcdefghijklmnopqrstuvwxyz0123456789')
        # pick the first shape the DEFAULT rules actually report, so the control is not void
        live_shape, shape_probe = None, {}
        for shape, render in SHAPES.items():
            p = probe(tree, 'v%02d-shape-%s.txt' % (number, shape), render(value))
            r = scan_file(p, defaults, 'shape')
            shape_probe[shape] = None if r is None else r['count']
            if r and r['count'] and live_shape is None:
                live_shape, live_path = shape, p
        if live_shape is None:
            rows.append({'value': value[:12] + '...', 'error': 'no shape reported by default rules',
                        'shapeProbe': shape_probe})
            continue
        render = SHAPES[live_shape]
        alnum = [i for i, c in enumerate(value) if c.isalnum()]
        cases = {'exact': value}
        picks = [('first', alnum[0]), ('midA', alnum[len(alnum) // 2]),
                 ('midB', alnum[(2 * len(alnum)) // 3]), ('last', alnum[-1])]
        seen = set()
        for tag, idx in picks:
            if idx in seen:
                continue
            seen.add(idx)
            cases[tag] = flip(value, idx, charset)
        # substring attacks: an unanchored allowlist regex also matches a token CONTAINING the value
        cases['prefixPlus'] = ('ab' + value) if len(value) >= 32 else None
        cases['plusSuffix'] = (value + 'cd') if len(value) >= 32 else None
        cases['embedded'] = ('0123456789' + value + 'abcdef') if len(value) >= 32 else None
        row = {'valueHead': value[:10], 'valueLen': len(value), 'liveShape': live_shape,
               'defaultRuleCountsByShape': shape_probe, 'cases': {}}
        for tag, text in cases.items():
            if text is None:
                continue
            p = probe(tree, 'v%02d-%s.txt' % (number, tag), render(text))
            base = scan_file(p, defaults, 'base')
            gate = scan_file(p, CONFIG, 'gate')
            row['cases'][tag] = {
                'liveUnderDefaults': None if base is None else base['count'],
                'reportedUnderDelivered': None if gate is None else gate['count'],
                'changedFromOriginal': text != value,
            }
        rows.append(row)

    # summary judgement per value
    verdicts, mid_fail, exact_fail, mutation_fail = [], [], [], []
    for row in rows:
        if 'error' in row:
            verdicts.append({'valueHead': row['valueHead'] if 'valueHead' in row else '?', 'void': row['error']})
            continue
        cases = row['cases']
        exact = cases.get('exact', {})
        ok_exact = exact.get('liveUnderDefaults', 0) and not exact.get('reportedUnderDelivered')
        muts = {k: v for k, v in cases.items() if k in ('first', 'midA', 'midB', 'last')}
        live_muts = {k: v for k, v in muts.items() if v['liveUnderDefaults']}
        ok_muts = len(live_muts) >= 3 and all(v['reportedUnderDelivered'] for v in live_muts.values())
        inert = sorted(k for k, v in muts.items() if v['liveUnderDefaults'] and not v['reportedUnderDelivered'])
        if inert:
            mid_fail.append({'valueHead': row['valueHead'], 'inert': inert})
        if not ok_exact:
            exact_fail.append(row['valueHead'])
        if not ok_muts:
            mutation_fail.append({'valueHead': row['valueHead'],
                                 'liveMutations': sorted(live_muts), 'reported': sorted(
                                     k for k, v in live_muts.items() if v['reportedUnderDelivered'])})
        subs = {k: v for k, v in cases.items() if k in ('prefixPlus', 'plusSuffix', 'embedded')}
        row['substringSuppressed'] = sorted(k for k, v in subs.items()
                                           if v['liveUnderDefaults'] and not v['reportedUnderDelivered'])
        row['ok'] = ok_exact and ok_muts
        verdicts.append({'valueHead': row['valueHead'], 'len': row['valueLen'], 'shape': row['liveShape'],
                        'exactSuppressed': bool(ok_exact), 'liveMutations': sorted(live_muts),
                        'allMutationsReported': bool(ok_muts), 'substringSuppressed': row['substringSuppressed']})
    payload = {'values': values, 'rows': rows, 'perValue': verdicts,
               'summary': {'valuesTotal': len(values),
                           'exactNotSuppressed': exact_fail,
                           'mutationsNotAllReported': mutation_fail,
                           'inertMidSectionMutations': mid_fail,
                           'substringSuppressedValues': [v for v in verdicts if v.get('substringSuppressed')],
                           'voidValues': [r for r in rows if 'error' in r]}}
    (HERE / 'evidence' / 'c2-falsifiability.json').write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(payload['summary'], ensure_ascii=False, indent=2))
    for v in verdicts:
        print(json.dumps(v, ensure_ascii=False))
    total_cases = sum(len([k for k, c in r.get('cases', {}).items()]) for r in rows if 'cases' in r)
    print('cases written and scanned: %d' % total_cases)
    failed = bool(exact_fail or mutation_fail or mid_fail or payload['summary']['voidValues'])
    print('C2 VERDICT: ' + ('ALL PASS' if not failed else 'PROBLEMS ' + json.dumps(
        {'exact': exact_fail, 'mutations': mutation_fail, 'mid': mid_fail,
         'void': payload['summary']['voidValues']}, ensure_ascii=False)))
    shutil.rmtree(SCRATCH, ignore_errors=True)
    print('scratch removed:', not SCRATCH.exists())
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())

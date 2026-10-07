"""T02 round-4 control C-12: can the value exceptions be anchored so that only the exact value is
suppressed? This tests the remedy proposed for the substring-suppression finding, on a TEMP copy of
the delivered config with ^ and $ added around every exception regex. If anchoring suppresses the
exact value but lets a longer token containing it be reported, the hardening is real and one line.
"""
import json
import pathlib
import re
import shutil
import subprocess

ROOT = pathlib.Path(r'E:\project\codex\wxAgent')
HERE = pathlib.Path(__file__).resolve().parent
SCRATCH = pathlib.Path.home() / 'AppData/Local/Temp/t02r4/c12'
GITLEAKS = str(ROOT / '.tools/t02/gitleaks/gitleaks.exe')
CONFIG = ROOT / 'tests/engineering/T02/gitleaks.toml'


def scan(path, config, name):
    report = SCRATCH / (name + '.json')
    if report.exists():
        report.unlink()
    proc = subprocess.run([GITLEAKS, 'dir', str(path), '--no-banner', '--redact', '--config', str(config),
                           '--report-format', 'json', '--report-path', str(report)],
                          capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=ROOT)
    findings = json.loads(report.read_text(encoding='utf-8')) if report.exists() else []
    return {'exit': proc.returncode, 'count': len(findings)}


def main():
    shutil.rmtree(SCRATCH, ignore_errors=True)
    tree = SCRATCH / 'tree'
    tree.mkdir(parents=True)
    text = CONFIG.read_text(encoding='utf-8')
    values = [re.sub(r'\\(.)', r'\1', e) for block in re.findall(
        r'\[\[allowlists\]\](.*?)(?=\[\[allowlists\]\]|\Z)', text, re.S)
        for e in re.findall(r"'''(.*?)'''", block, re.S)]
    anchored_text, count = re.subn(r"'''((?:[^']|\')*?)'''", lambda m: "'''^%s$'''" % m.group(1), text)
    anchored = SCRATCH / 'anchored.toml'
    anchored.write_text(anchored_text, encoding='utf-8', newline='\n')
    defaults = SCRATCH / 'defaults-only.toml'
    defaults.write_text('title = "defaults"\n[extend]\nuseDefault = true\n', encoding='utf-8', newline='\n')

    out = {'entriesAnchored': count, 'anchoredConfigBytes': anchored.stat().st_size, 'cases': {}}
    for index, value in enumerate(values):
        probes = {'exact': value, 'superstring': 'ab' + value + 'cd'}
        row = {}
        for tag, token in probes.items():
            path = tree / ('p%02d-%s.txt' % (index, tag))
            path.write_text('api_key = "%s"\n' % token, encoding='utf-8', newline='\n')
            row[tag] = {'defaults': scan(path, defaults, 'd'),
                        'delivered': scan(path, CONFIG, 'g'),
                        'anchored': scan(path, anchored, 'a')}
        out['cases']['value-%02d' % index] = row
    exact_ok = all(r['exact']['defaults']['count'] and not r['exact']['anchored']['count']
                   for r in out['cases'].values())
    super_fixed = [k for k, r in out['cases'].items()
                   if r['superstring']['defaults']['count'] and r['superstring']['anchored']['count']
                   and not r['superstring']['delivered']['count']]
    out['verdict'] = {
        'exactStillSuppressedUnderAnchoring': exact_ok,
        'superstringNowReportedUnderAnchoring': sorted(super_fixed),
        'anchoringIsARealHardening': bool(exact_ok and len(super_fixed) == len(values) - 0),
        'note': 'values whose probe is not live under defaults are counted as void, not as failures',
    }
    print(json.dumps(out['verdict'], ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in out['cases'].items()}, ensure_ascii=False)[:1200])
    (HERE / 'evidence' / 'c12-anchoring-remedy.json').write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    shutil.rmtree(SCRATCH, ignore_errors=True)
    print('scratch removed:', not SCRATCH.exists())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

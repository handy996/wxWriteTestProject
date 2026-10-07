"""T02 round-4 control C-13: the measured hardening for substring suppression.

C-12 falsified the obvious fix (^value$): with regexTarget = "match" the text tested is the whole
rule match (`api_key = "<value>"`), so an anchored exception stops suppressing even the exact value.
This measures the alternative that keeps the exact value suppressed while making a LONGER token
that merely contains it reportable again: word boundaries around each exception value.
TEMP only, deleted before exit; the repository config is not modified.
"""
import json
import pathlib
import re
import shutil
import subprocess

ROOT = pathlib.Path(r'E:\project\codex\wxAgent')
HERE = pathlib.Path(__file__).resolve().parent
SCRATCH = pathlib.Path.home() / 'AppData/Local/Temp/t02r4/c13'
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
    wordy, hard = SCRATCH / 'word-boundary.toml', SCRATCH / 'hex-only-boundary.toml'
    wordy.write_text(re.sub(r"'''([^']+?)'''", lambda m: "'''\\b%s\\b'''" % m.group(1), text),
                     encoding='utf-8', newline='\n')
    print('entries rewritten:', len(re.findall(r"'''\\b", wordy.read_text(encoding='utf-8'))))
    defaults = SCRATCH / 'defaults-only.toml'
    defaults.write_text('title = "defaults"\n[extend]\nuseDefault = true\n', encoding='utf-8', newline='\n')

    out = {'cases': {}}
    for index, value in enumerate(values):
        cases = {'exact': value, 'prefixPlus': 'ab' + value, 'plusSuffix': value + 'cd',
                 'embedded': '0123456789' + value + 'abcdef'}
        row = {}
        for tag, token in cases.items():
            path = tree / ('p%02d-%s.txt' % (index, tag))
            path.write_text('api_key = "%s"\n' % token, encoding='utf-8', newline='\n')
            row[tag] = {'defaults': scan(path, defaults, 'd'),
                        'delivered': scan(path, CONFIG, 'g'),
                        'wordBoundary': scan(path, wordy, 'w')}
        out['cases']['value-%02d' % index] = row
    live = [k for k, r in out['cases'].items() if r['exact']['defaults']['count']]
    exact_suppressed = [k for k in live if not out['cases'][k]['exact']['wordBoundary']['count']]
    super_reported = [k for k in live
                      if all(out['cases'][k][t]['defaults']['count'] and out['cases'][k][t]['wordBoundary']['count']
                             for t in ('prefixPlus', 'plusSuffix', 'embedded'))]
    out['verdict'] = {'valuesWithLiveExactProbe': len(live),
                      'exactStillSuppressed': len(exact_suppressed),
                      'allSuperstringsReportedAgain': len(super_reported),
                      'wordBoundaryFixWorks': len(exact_suppressed) == len(live) and len(super_reported) == len(live)}
    print(json.dumps(out['verdict'], ensure_ascii=False, indent=2))
    (HERE / 'evidence' / 'c13-word-boundary-remedy.json').write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    shutil.rmtree(SCRATCH, ignore_errors=True)
    print('scratch removed:', not SCRATCH.exists())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

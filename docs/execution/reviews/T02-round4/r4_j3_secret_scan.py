"""T02 round-4 judgement J-3: is secret_scan.py's value exemption and --self-test load-bearing?

Three measurements, all in memory or in TEMP, no repository writes:
  1. the delivered scanner on the current tree (exit code expected 0);
  2. the same scanner with EXEMPT_VALUES cleared (the exemption table removed in memory only) --
     it must name the files that actually carry the AWS published example key id today;
  3. the self-test itself, plus two sabotage variants that show the self-test is not decorative:
     widen the exemption to a prefix rule, and remove a caught fixture.
"""
import importlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(r'E:\project\codex\wxAgent')
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tests/engineering/T02'))
out = {}

import secret_scan

r = subprocess.run([sys.executable, str(ROOT / 'tests/engineering/T02/secret_scan.py'), '--self-test'],
                   capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=ROOT)
out['selfTestDelivered'] = {'exit': r.returncode, 'out': r.stdout.strip(), 'err': r.stderr.strip()[-200:]}

r = subprocess.run([sys.executable, str(ROOT / 'tests/engineering/T02/secret_scan.py')],
                   capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=ROOT)
out['scanDelivered'] = {'exit': r.returncode, 'out': r.stdout.strip()[:400], 'err': r.stderr.strip()[-200:]}

saved = dict(secret_scan.EXEMPT_VALUES)
secret_scan.EXEMPT_VALUES = {}
files = []
import subprocess as sp
paths = [n.decode('utf-8') for n in sp.check_output(
    ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT).split(b'\0') if n]
for name in sorted(set(paths)):
    p = ROOT / name
    if p.is_file() and secret_scan.matches(p.read_bytes()):
        files.append(name)
out['scanWithEmptyExemptTable'] = {'files': files, 'count': len(files)}
secret_scan.EXEMPT_VALUES = saved

# which pattern index fires in each of those files, and what the matched bytes look like (length + class only)
detail = []
for name in out['scanWithEmptyExemptTable']['files']:
    data = (ROOT / name).read_bytes()
    for index, pattern in enumerate(secret_scan.patterns):
        for m in pattern.finditer(data):
            tok = m.group(0)
            detail.append({'file': name, 'patternIndex': index, 'matchedLen': len(tok),
                           'isExemptValue': tok in saved})
out['matchDetail'] = detail

# sabotage variants of the self-test
self_test_src = (ROOT / 'tests/engineering/T02/secret_scan.py').read_text(encoding='utf-8')
variants = {
    'exemptByPrefix': self_test_src.replace(
        'if found.group(0) in EXEMPT_VALUES:',
        'if any(found.group(0).startswith(v) for v in EXEMPT_VALUES):'),
    'exemptNothing': self_test_src.replace('if found.group(0) in EXEMPT_VALUES:',
                                           'if False:'),
}
scratch = pathlib.Path.home() / 'AppData/Local/Temp/t02r4/j3'
scratch.mkdir(parents=True, exist_ok=True)
out['sabotage'] = {}
for label, text in variants.items():
    path = scratch / ('variant-' + label + '.py')
    path.write_text(text, encoding='utf-8', newline='\n')
    r = subprocess.run([sys.executable, str(path), '--self-test'], capture_output=True,
                       text=True, encoding='utf-8', errors='replace', cwd=ROOT)
    out['sabotage'][label] = {'exit': r.returncode, 'out': r.stdout.strip()[:300]}
import shutil
shutil.rmtree(scratch, ignore_errors=True)
out['scratchRemoved'] = not scratch.exists()
print(json.dumps(out, ensure_ascii=False, indent=2))
(HERE / 'evidence' / 'c8-j3-secret-scan-exemption.json').write_text(
    json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')

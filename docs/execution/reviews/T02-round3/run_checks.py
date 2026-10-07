"""T02 round-3 independent re-check. Only the evidence/work destination is relocated;
scan input, config, rules and exit codes are the ones CI would use."""
import json, os, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
GIT = str(Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')
PY = sys.executable
GK = str(ROOT / '.tools/t02/gitleaks/gitleaks.exe')
os.environ['PATH'] = str(Path(GIT).parent) + os.pathsep + os.environ['PATH']

if '--scan' in sys.argv:
    sys.argv = [sys.argv[0], '--gitleaks', GK]
    path = ROOT / 'tests/engineering/T02/scan_secrets.py'
    source = (path.read_text(encoding='utf-8')
              .replace('tests/engineering/T02/evidence/gitleaks-findings.json',
                       'docs/execution/reviews/T02-round3/gitleaks-findings.json')
              .replace("ROOT / 'tests/engineering/T02/.work'", "ROOT / 'docs/execution/reviews/T02-round3/.work'"))
    exec(compile(source, str(path), 'exec'), {'__name__': '__main__', '__file__': str(path)})
    raise SystemExit

results = []
for argv in ([sys.executable, '--version'],
             [GK, 'version'],
             [PY, 'tests/engineering/T02/check_contracts.py'],
             [PY, str(HERE / 'run_checks.py'), '--scan'],
             ['git', 'ls-files', '--cached', '--others', '--exclude-standard']):
    p = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=900,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    out = p.stdout + p.stderr
    results.append({'argv': [str(x) for x in argv], 'exitCode': p.returncode,
                    'outputTail': out[-3000:], 'outputChars': len(out)})
(HERE / 'evidence').mkdir(exist_ok=True)
raw = [r for r in results]
(HERE / 'evidence' / 'raw-run.json').write_text(json.dumps(raw, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

scan = results[3]
findings_path = HERE / 'gitleaks-findings.json'
findings = json.loads(findings_path.read_text(encoding='utf-8')) if findings_path.exists() else []
sanitized = [{'file': f.get('File'), 'line': f.get('Line'), 'rule': f.get('RuleID'),
              'matchRedacted': True} for f in findings]
summary = {'gitleaksVersion': results[1]['outputTail'].strip(),
           'contractsExit': results[2]['exitCode'],
           'contractsOutput': results[2]['outputTail'].strip(),
           'scanExit': scan['exitCode'],
           'findingCount': len(findings),
           'findings': sanitized,
           'gitVisibleFiles': len([x for x in subprocess.run(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT,capture_output=True,timeout=300).stdout.split(b'\0') if x]),
           'lsFilesTruncatedToTail': False}
(HERE / 'evidence' / 'scan-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False))

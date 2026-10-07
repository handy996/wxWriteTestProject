"""Reviewer self-check: does my own round-4 harness directory stay clean under both configs?

Round three learned the hard way that a reviewer's own evidence file can become a scan input
(git-visible untracked files are in the input set). This probes that directly and reports which
file and rule would break the green baseline, so the reviewer fixes its own text instead of
adding an exemption.
"""
import json
import pathlib
import subprocess

ROOT = pathlib.Path(r'E:\project\codex\wxAgent')
HERE = pathlib.Path(__file__).resolve().parent
GITLEAKS = str(ROOT / '.tools/t02/gitleaks/gitleaks.exe')
SCRATCH = pathlib.Path.home() / 'AppData/Local/Temp/t02r4/selfcheck'
SCRATCH.mkdir(parents=True, exist_ok=True)
defaults = SCRATCH / 'defaults-only.toml'
defaults.write_text('title = "defaults only"\n[extend]\nuseDefault = true\n', encoding='utf-8', newline='\n')


def scan(target, config, name):
    report = SCRATCH / (name + '.json')
    if report.exists():
        report.unlink()
    proc = subprocess.run([GITLEAKS, 'dir', str(target), '--no-banner', '--redact', '--config', str(config),
                           '--report-format', 'json', '--report-path', str(report)],
                          capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=ROOT)
    findings = json.loads(report.read_text(encoding='utf-8')) if report.exists() else []
    return {'exit': proc.returncode, 'count': len(findings),
            'where': sorted('%s|%s' % (pathlib.Path(f['File']).name, f['RuleID']) for f in findings),
            'match': sorted({f.get('Match') for f in findings})}


result = {'reviewerDirDefaults': scan(HERE, defaults, 'd'),
          'reviewerDirDelivered': scan(HERE, ROOT / 'tests/engineering/T02/gitleaks.toml', 'v')}
print(json.dumps(result, ensure_ascii=False, indent=2))
(HERE / 'evidence' / 'c0-reviewer-self-scan.json').write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
raise SystemExit(1 if result['reviewerDirDelivered']['count'] else 0)

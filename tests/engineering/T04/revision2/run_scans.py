"""Run the exact CI scanner with revision-owned output, preserving earlier evidence."""
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
if '--scan' in sys.argv:
    sys.argv = [sys.argv[0], '--gitleaks', str(ROOT / '.tools/t02/gitleaks/gitleaks.exe').replace('\\', '/')]
    original = ROOT / 'tests/engineering/T02/scan_secrets.py'
    source = original.read_text(encoding='utf-8').replace(
        'tests/engineering/T02/evidence/gitleaks-findings.json', 'tests/engineering/T04/revision2/gitleaks-findings.json'
    ).replace("ROOT / 'tests/engineering/T02/.work'", "ROOT / 'tests/engineering/T04/.work'")
    exec(compile(source, str(original), 'exec'), {'__name__': '__main__', '__file__': str(original)})
else:
    results = []
    for command in [[str(ROOT / '.tools/t02/gitleaks/gitleaks.exe'), 'version'],
                    [sys.executable, __file__, '--scan'], ['git', 'diff', '--check']]:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8',
                                errors='replace', timeout=180, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        results.append(dict(argv=command, exitCode=result.returncode, output=result.stdout + result.stderr))
    (HERE / 'scans.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps([dict(command=item['argv'][0], exitCode=item['exitCode']) for item in results]))

"""T02 round-4 control C-9: pin the exact gitleaks 8.30.1 default-rule gaps.

Round three and the R02 report both say the default rules miss a bare `AKIA[0-9A-Z]{16}` and
plaintext `password=` / `DB_PASSWORD=`. Probing shapes one at a time (all synthetic, TEMP only)
separates what is真漏 from what was an artefact of the example value used:

  * AKIA id alone / with keyword          -> expected CAUGHT (aws-access-token)
  * 40-char mixed-case secret on a line   -> expected CAUGHT (generic-api-key)
  * AWS example secret containing '/'     -> expected MISSED (token charset)
  * short passphrase on password lines    -> expected MISSED (token length/charset)
  * long random passphrase on password    -> measures whether it is length or keyword
"""
import json
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(r'E:\project\codex\wxAgent')
HERE = pathlib.Path(__file__).resolve().parent
SCRATCH = pathlib.Path.home() / 'AppData/Local/Temp/t02r4/c9'
GITLEAKS = str(ROOT / '.tools/t02/gitleaks/gitleaks.exe')
sys.path.insert(0, str(ROOT / 'tests/engineering/T02'))

PROBES = {
    'akia-alone': ('AKIA' + 'QWERTYUIOPASDFGH') + '\n',
    'akia-with-keyword': 'aws_access_key_id = ' + ('AKIA' + 'QWERTYUIOPASDFGH') + '\n',
    'generic-40-mixedcase': 'aws_secret_access_key = ' + ('Zl9Qk3mHt7rYp2sVx8bNc4dLm6qWj0fGh5jK9pLoQ') + '\n',
    'aws-example-with-slash': 'aws_secret_access_key = ' + ('wJalrXUtnFEMI' + '/K7MDENG' + '/bPxRfiCY' + 'EXAMPLEKEY') + '\n',
    'base64-charset-with-plus': 'client_secret = ' + ('AbCd' + 'EfGhIjKlMnOpQrSt' + '/uVwXyZ012345' + '+6789abcde') + '\n',
    'password-short': 'password = hunter2%s\n' % ('hunter2' * 2),
    'db-password-short-env': 'DB_PASSWORD=' + 'Sup3rSecretPassphrase' + '\n',
    'password-long-random-40': 'password = ' + ('Zl9Qk3mHt7rYp2sVx8bNc4dLm6qWj0fGh5jK9pLoQ') + '\n',
    'db-password-quoted-40': 'DB_PASSWORD="' + ('Zl9Qk3mHt7rYp2sVx8bNc4dLm6qWj0fGh5jK9pLoQ') + '"\n',
    'bearer-jwt-style': 'Authorization: Bearer ey' + 'JhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWI' + 'iOiIxMjM0NTY3ODkwIn0\n',
}


def scan(path, config, name):
    report = SCRATCH / (name + '.json')
    proc = subprocess.run([GITLEAKS, 'dir', str(path), '--no-banner', '--redact', '--config', str(config),
                           '--report-format', 'json', '--report-path', str(report)],
                          capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=ROOT)
    findings = json.loads(report.read_text(encoding='utf-8')) if report.exists() else []
    return {'exit': proc.returncode, 'count': len(findings),
            'rules': sorted({f['RuleID'] for f in findings})}


def main():
    shutil.rmtree(SCRATCH, ignore_errors=True)
    tree = SCRATCH / 'tree'
    tree.mkdir(parents=True)
    defaults = SCRATCH / 'defaults-only.toml'
    defaults.write_text('title = "defaults only"\n[extend]\nuseDefault = true\n', encoding='utf-8', newline='\n')
    import secret_scan
    out = {}
    for name, body in sorted(PROBES.items()):
        path = tree / (name + '.txt')
        path.write_text(body, encoding='utf-8', newline='\n')
        out[name] = {'bytes': path.stat().st_size,
                     'tokenLen': len(body.strip().split(None, 1)[-1].strip('"')) if ' ' in body else len(body.strip()),
                     'gitleaksDefaults': scan(path, defaults, 'g'),
                     'secretScanPatterns': bool(secret_scan.matches(path.read_bytes()))}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    (HERE / 'evidence' / 'c9-default-rule-gaps.json').write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    shutil.rmtree(SCRATCH, ignore_errors=True)
    print('scratch removed:', not SCRATCH.exists())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

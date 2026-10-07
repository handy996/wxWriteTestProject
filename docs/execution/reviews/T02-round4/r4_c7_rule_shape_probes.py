"""T02 round-4 control C-7: sharpen two measurements that came out differently from the report.

(a) private-key shapes: the C-1 canary (RSA) was caught; an OPENSSH header probe was not. Which
    header variants does gitleaks 8.30.1 actually catch, and does the key length matter?
(b) the built-in "gitleaks.toml" exception: does a real credential shape inside a file whose NAME
    contains gitleaks.toml escape the scanner, and does the repository's own secret_scan.py still
    read those bytes (mitigation check)?
(c) is the missed aws_secret_access_key value about the EXAMPLEKEY suffix or about the shape? A
    random 40-character base64-ish secret in the same position is tested.
Synthetic only, TEMP only, deleted before exit.
"""
import json
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(r'E:\project\codex\wxAgent')
HERE = pathlib.Path(__file__).resolve().parent
SCRATCH = pathlib.Path.home() / 'AppData/Local/Temp/t02r4/c7'
GITLEAKS = str(ROOT / '.tools/t02/gitleaks/gitleaks.exe')
sys.path.insert(0, str(ROOT / 'tests/engineering/T02'))


def defaults_config():
    path = SCRATCH / 'defaults-only.toml'
    path.write_text('title = "defaults only"\n[extend]\nuseDefault = true\n', encoding='utf-8', newline='\n')
    return path


def scan_file(path, config, name):
    report = SCRATCH / (name + '.json')
    if report.exists():
        report.unlink()
    proc = subprocess.run([GITLEAKS, 'dir', str(path), '--no-banner', '--redact', '--config', str(config),
                           '--report-format', 'json', '--report-path', str(report)],
                          capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=ROOT)
    findings = json.loads(report.read_text(encoding='utf-8')) if report.exists() else []
    return {'exit': proc.returncode, 'count': len(findings),
            'rules': sorted({f['RuleID'] for f in findings}),
            'scanned': [l.strip() for l in (proc.stdout + proc.stderr).splitlines() if 'bytes' in l][-1:]}


def pem(kind, lines):
    head = '-----BEGIN %s-----' % kind
    tail = '-----END %s-----' % kind
    body = ['b3BlbnNzaC1rZXktdjEAAAAABG52' + str(i) + 'AAAA' + 'A' * 20 for i in range(lines)]
    return head + '\n' + '\n'.join(body) + '\n' + tail + '\n'


def main():
    shutil.rmtree(SCRATCH, ignore_errors=True)
    tree = SCRATCH / 'tree'
    tree.mkdir(parents=True)
    defaults = defaults_config()
    out = {'privateKeyShapes': {}, 'nameContainsGitleaksToml': {}, 'awsSecretShape': {}}

    shapes = {
        'rsa-header-only': pem('RSA PRIVATE KEY', 0),
        'rsa-two-lines': pem('RSA PRIVATE KEY', 2),
        'rsa-eight-lines': pem('RSA PRIVATE KEY', 8),
        'openssh-two-lines': pem('OPENSSH PRIVATE KEY', 2),
        'openssh-eight-lines': pem('OPENSSH PRIVATE KEY', 8),
        'pkcs8-eight-lines': pem('PRIVATE KEY', 8),
        'ec-eight-lines': pem('EC PRIVATE KEY', 8),
    }
    for name, body in shapes.items():
        path = tree / (name + '.txt')
        path.write_text(body, encoding='utf-8', newline='\n')
        out['privateKeyShapes'][name] = {'bytes': path.stat().st_size,
                                         'gitleaksDefaults': scan_file(path, defaults, 'pk')}

    # name containing gitleaks.toml
    import secret_scan
    token = 'github_token: ghp_' + 'R4REVIEW' + 'SYNTHETICNOTAREALKEY' + '0123456789abcdefghij' + '\n'
    for fname in ('gitleaks.toml', 'vendor-gitleaks.toml.bak', 'config.txt'):
        d = SCRATCH / ('nm-' + re.sub(r'\W', '_', fname))
        d.mkdir()
        path = d / fname
        path.write_text(token, encoding='utf-8', newline='\n')
        out['nameContainsGitleaksToml'][fname] = {
            'bytes': path.stat().st_size,
            'gitleaksDefaults': scan_file(path, defaults, 'nm'),
            'gitleaksDeliveredConfig': scan_file(path, ROOT / 'tests/engineering/T02/gitleaks.toml', 'nd'),
            'secretScanPatternCatches': bool(secret_scan.matches(path.read_bytes())),
        }

    # aws secret: example suffix vs random-looking 40 chars
    variants = {
        'doc-example-value': 'aws_secret_access_key = %s\n' % ('wJalrXUtnFEMI' + '/K7MDENG' + '/bPxRfiCY' + 'EXAMPLEKEY'),
        'random-looking-40': 'aws_secret_access_key = %s\n' % ('Zl9Q' + 'k3mHt7rYp2sVx8bNc4dLm6qWj0fGh5jK9pLoQ2r'),
        'quoted-random-40': 'aws_secret_access_key = "%s"\n' % ('Zl9Qk3mHt7rYp2sVx8bNc4dLm6qWj0fGh5jK9pLoQ'),
        'access-key-id-line': 'aws_access_key_id = %s\n' % ('AKIA' + 'QWERTYUIOPASDFGH'),
    }
    for name, body in variants.items():
        path = tree / ('aws-' + name + '.txt')
        path.write_text(body, encoding='utf-8', newline='\n')
        out['awsSecretShape'][name] = {'bytes': path.stat().st_size,
                                       'gitleaksDefaults': scan_file(path, defaults, 'aw'),
                                       'secretScanPatternCatches': bool(secret_scan.matches(body.encode()))}

    print(json.dumps(out, ensure_ascii=False, indent=2))
    (HERE / 'evidence' / 'c7-rule-shape-probes.json').write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    shutil.rmtree(SCRATCH, ignore_errors=True)
    print('scratch removed:', not SCRATCH.exists())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

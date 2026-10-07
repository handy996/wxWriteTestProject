r"""T02 round-4 judgement harness J-1 / J-2: inherent boundary of value exemptions, and the
coverage gaps of gitleaks 8.30.1 default rules.

All probes are SYNTHETIC and assembled at runtime; every probe file lives under $env:TEMP\t02r4\c5
and is deleted before exit. Nothing in the repository is written.

  J-1  does an exempted value placed on a real credential line (aws_secret_access_key / secret_key /
       DB_PASSWORD) get suppressed anywhere it appears, and does a one-character neighbour still get
       caught there? That is the practical shape of the "exemption is by value, not by context" risk.
  J-2  which credential shapes do the gitleaks 8.30.1 DEFAULT rules not see at all: bare AKIA ids,
       plaintext password assignments, an AWS style secret, and a secret inside a binary file.
       secret_scan.py's own four patterns are run over the same probes for the complementarity check.
"""
import json
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(r'E:\project\codex\wxAgent')
HERE = pathlib.Path(__file__).resolve().parent
SCRATCH = pathlib.Path.home() / 'AppData/Local/Temp/t02r4/c5'
GITLEAKS = str(ROOT / '.tools/t02/gitleaks/gitleaks.exe')
CONFIG = ROOT / 'tests/engineering/T02/gitleaks.toml'
sys.path.insert(0, str(ROOT / 'tests/engineering/T02'))


def build_probes(values):
    akia = 'AKIA' + 'QWERTYUIOPASDFGH'
    aws_secret = 'wJalrXUtnFEMI' + '/K7MDENG' + '/bPxRfiCY' + 'EXAMPLEKEY'
    ghp = 'ghp_' + 'R4REVIEW' + 'SYNTHETICNOTAREALKEY' + '0123456789abcdefghij'
    pem = ('-----BEGIN OPENSSH PRI' + 'VATE KEY-----\nb3BlbnNzaC1rZXktdjEAAAAA' + 'R4REVIEW\n'
           + '-----END OPENSSH PRI' + 'VATE KEY-----\n')
    digest = values[2]            # one of the exempted 64-hex fingerprints
    uuid_value = values[0]        # one of the exempted UUID values
    probes = {
        'bare-akia-line': akia + '\n',
        'akia-with-keyword': 'aws_access_key_id = %s\n' % akia,
        'akia-quoted': 'const char *k = "AKIA' + 'QWERTYUIOPASDFGH";\n',
        'password-plaintext': 'password = hunter2%s\n' % ('hunter2' * 2),
        'db-password-env': 'DB_PASSWORD=%s\n' % ('Sup3rSecretPassphrase'),
        'db-password-quoted': 'DB_PASSWORD="%s"\n' % ('Sup3rSecretPassphrase'),
        'aws-secret-access-key-context': 'aws_secret_access_key = %s\n' % aws_secret,
        'openai-style': 'OPENAI_API_KEY=sk-proj-%s\n' % ('abcdefghijklmnopqrstuvwxyz123456'),
        'github-pat': 'github_token: %s\n' % ghp,
        'private-key-block': pem,
        'exempt-digest-on-secret-line': 'aws_secret_access_key = "%s"\n' % digest,
        'exempt-digest-neighbour-on-secret-line': 'aws_secret_access_key = "%s"\n' % (
            digest[:32] + ('0' if digest[32] != '0' else '1') + digest[33:]),
        'exempt-uuid-on-secret-key': 'secret_key: %s\n' % uuid_value,
        'exempt-uuid-neighbour-on-secret-key': 'secret_key: %s\n' % (
            uuid_value[:30] + ('0' if uuid_value[30] != '0' else '1') + uuid_value[31:]),
    }
    return probes


def scan_file(path, config, name):
    report = SCRATCH / (name + '.json')
    if report.exists():
        report.unlink()
    proc = subprocess.run([GITLEAKS, 'dir', str(path), '--no-banner', '--redact', '--config', str(config),
                           '--report-format', 'json', '--report-path', str(report)],
                          capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=ROOT)
    if not report.exists():
        return {'exit': proc.returncode, 'count': None, 'log': (proc.stdout + proc.stderr)[:200]}
    findings = json.loads(report.read_text(encoding='utf-8'))
    return {'exit': proc.returncode, 'count': len(findings),
            'rules': sorted({f['RuleID'] for f in findings})}


def secret_scan_probe(data):
    import secret_scan
    return bool(secret_scan.matches(data))


def main():
    shutil.rmtree(SCRATCH, ignore_errors=True)
    tree = SCRATCH / 'tree'
    tree.mkdir(parents=True)
    defaults = SCRATCH / 'defaults-only.toml'
    defaults.write_text('title = "defaults only"\n[extend]\nuseDefault = true\n', encoding='utf-8', newline='\n')
    text = CONFIG.read_text(encoding='utf-8')
    values = [re.sub(r'\\(.)', r'\1', e) for block in re.findall(
        r'\[\[allowlists\]\](.*?)(?=\[\[allowlists\]\]|\Z)', text, re.S)
        for e in re.findall(r"'''(.*?)'''", block, re.S)]

    probes = build_probes(values)
    results = {}
    for name, body in sorted(probes.items()):
        path = tree / (name + '.txt')
        path.write_text(body, encoding='utf-8', newline='\n')
        results[name] = {
            'bytes': path.stat().st_size,
            'gitleaksDefaults': scan_file(path, defaults, 'def'),
            'gitleaksDeliveredConfig': scan_file(path, CONFIG, 'del'),
            'secretScanPatternsDefaultTable': secret_scan_probe(path.read_bytes()),
        }

    # binary handling: a PNG copy with the same canary appended
    binary_dir = SCRATCH / 'binary'
    binary_dir.mkdir()
    src = ROOT / 'tests/engineering/T02/output/playwright/offline.png'
    png = binary_dir / 'offline-with-canary.png'
    shutil.copyfile(src, png)
    with png.open('ab') as stream:
        stream.write(('github_token: ghp_' + 'R4REVIEW' + 'SYNTHETICNOTAREALKEY' + '0123456789abcdefghij\n'
                      ).encode('utf-8'))
    results['_binaryProbe'] = {
        'sourceBytes': src.stat().st_size, 'pngBytes': png.stat().st_size,
        'gitleaksDefaults': scan_file(png, defaults, 'bin'),
        'secretScanPatternsDefaultTable': secret_scan_probe(png.read_bytes()),
    }

    # filename precision: which names does gitleaks skip as "the config itself"?
    named = {}
    for fname in ('gitleaks.toml', 'sub-gitleaks.toml', 'gitleaks.toml.bak', '.gitleaks.toml',
                  'plain.txt', 'policy.txt'):
        d = SCRATCH / ('names-' + re.sub(r'\W', '_', fname))
        d.mkdir()
        (d / fname).write_text('api_key = "%s"\n' % values[2], encoding='utf-8', newline='\n')
        named[fname] = {'bytes': (d / fname).stat().st_size, 'scan': scan_file(d, defaults, 'n')}
    results['_filenameSkipProbe'] = named

    print(json.dumps(results, ensure_ascii=False, indent=2))
    (HERE / 'evidence' / 'c5-j1-j2-boundaries-and-gaps.json').write_text(
        json.dumps({'exemptValueHeads': [v[:8] for v in values], 'results': results},
                   ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    shutil.rmtree(SCRATCH, ignore_errors=True)
    print('scratch removed:', not SCRATCH.exists())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

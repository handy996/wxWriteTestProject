"""Reviewer hygiene self-check: no SyntaxWarning in my own harness, no BOM, LF endings, no
live-shaped credential text in the files I deliver. Run before finishing the round.
"""
import json
import pathlib
import py_compile
import re
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
report = {'syntax': [], 'text': [], 'liveShapes': []}
LIVE = [re.compile(r'ghp_[0-9a-zA-Z]{36}'), re.compile(r'\bAKIA[0-9A-Z]{16}\b'),
        re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
        re.compile(r'sk-(?:proj-)?[a-zA-Z0-9_-]{24,}')]
with tempfile.TemporaryDirectory() as td:
    for path in sorted(HERE.rglob('*')):
        if not path.is_file() or path.name == 'r4_lint.py':
            continue
        if path.suffix == '.py':
            try:
                py_compile.compile(str(path), cfile=str(pathlib.Path(td) / (path.name + 'c')),
                                   doraise=True, quiet=True)
                report['syntax'].append([str(path.relative_to(HERE)), 'compiles'])
            except Exception as error:
                report['syntax'].append([str(path.relative_to(HERE)), 'FAIL %s' % error])
        data = path.read_bytes()
        report['text'].append([str(path.relative_to(HERE)),
                               'BOM' if data[:3] == b'\xef\xbb\xbf' else 'noBOM',
                               'CRLF' if b'\r\n' in data else 'LF'])
        if path.suffix in ('.py', '.md', '.json'):
            text = data.decode('utf-8', 'replace')
            hits = sorted({p.pattern for p in LIVE if p.search(text)})
            if hits:
                report['liveShapes'].append([str(path.relative_to(HERE)), hits])
print(json.dumps(report, ensure_ascii=False, indent=1))
(HERE / 'evidence' / 'c14-reviewer-hygiene.json').write_text(
    json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
raise SystemExit(1 if any('FAIL' in x[1] for x in report['syntax']) or
                 any(x in ('BOM', 'CRLF') for row in report['text'] for x in row) or
                 report['liveShapes'] else 0)

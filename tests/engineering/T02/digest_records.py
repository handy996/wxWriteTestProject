"""File fingerprints that never share a line with the path they describe.

Gitleaks' generic-api-key rule fires on any line that holds a key-like word (`api`, `key`,
`secret`, `password`, ...) *and* a long hexadecimal token, so a manifest serialised as
`"docs/api/openapi.yaml": "<sha256>"` looks like a credential no matter what the file is.
Third-round review measured the consequence: each such manifest needs its own allowlist
entry (already three rounds of growth), and an entry written with a `paths` condition skips
the whole file instead of the value, which is a scanner blind spot. Records here keep the
path and the digest on separate JSON lines and the serialiser refuses to pair them again.
"""
import hashlib
import json
import re
from pathlib import Path

KEYWORD = re.compile(r'(?i)api|key|token|secret|passwd|password|auth|access|credential|client|cert')
HEX_TOKEN = re.compile(r'[0-9a-f]{32,}')


def sha256_file(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def record(path, digest=None, root=None):
    """One fingerprint as {'path': ..., 'sha256': ...}; indent serialisation splits the two."""
    relative = Path(str(path).replace('\\', '/')).as_posix()
    if digest is None:
        digest = sha256_file((root / relative if root is not None else Path(relative)))
    return {'path': relative, 'sha256': digest}


def records(paths, root=None):
    return check([record(path, root=root) for path in paths])


def violations(text):
    """1-based line numbers that pair a key-like word with a long hex token."""
    return [n for n, line in enumerate(text.splitlines(), 1)
            if HEX_TOKEN.search(line) and KEYWORD.search(line)]


def check(items):
    for entry in items:
        bad = violations(json.dumps(entry, ensure_ascii=False, indent=2))
        if bad:
            raise AssertionError(f'fingerprint record pairs path and digest on line(s) {bad}: {entry}')
    return items


def dumps(payload):
    """Serialise with two-space indent, then refuse the file if any line pairs path and digest."""
    text = json.dumps(payload, ensure_ascii=False, indent=2) + '\n'
    bad = violations(text)
    if bad:
        raise AssertionError(f'fingerprint manifest pairs path and digest on line(s) {bad}')
    return text


def write(payload, out_path):
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = dumps(payload)
    path.write_text(text, encoding='utf-8', newline='\n')
    return text

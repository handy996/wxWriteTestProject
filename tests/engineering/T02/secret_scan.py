"""Small offline baseline scan. CI additionally runs Gitleaks; neither proves absence."""
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
patterns = [
    re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(rb'\bAKIA[0-9A-Z]{16}\b'),
    re.compile(rb'\bsk-(?:proj-)?[a-zA-Z0-9_-]{24,}\b'),
    re.compile(rb'\bgh[pousr]_[a-zA-Z0-9]{30,}\b'),
]
# Exemptions are exact matched VALUES and nothing else: no path, no directory, no file type. Gitleaks allowlists that
# carry a paths clause make the whole file unscanned (measured in the third T02 round: 150,604 bytes of three tracked
# files reported as scanned, then zero findings, and the value condition never evaluated), so this scanner refuses to
# inherit that failure mode. Adding an entry here must be justified by the value being public documentation.
EXEMPT_VALUES = {
    b"AKIAIOSFODNN7EXAMPLE": "AWS published SigV4 test vector credential id, used as a fixed constant in the storage signing test",
}

def matches(data):
    """(pattern index, matched bytes) for every hit that is not exempted by exact value."""
    hits = []
    for index, pattern in enumerate(patterns):
        for found in pattern.finditer(data):
            if found.group(0) in EXEMPT_VALUES:
                continue
            hits.append((index, found.group(0)))
    return hits

def self_test():
    """The exemptions must only suppress the documented value: a neighbour must still be caught.

    Run with --self-test and no repository is touched. Without this the exemption list is unprovable: a scanner that
    reports nothing cannot be distinguished from one that reports nothing because it stopped looking.
    """
    # Fixtures are assembled at runtime. Written as literals they would be live-shaped secrets inside a tracked file,
    # and the scanner would correctly report its own source: that is what the first draft of this test did.
    fixtures = {
        "aws example key id is exempt": (b'StaticCredentials C = new StaticCredentials("AKIAIOSFODNN7EXAMPLE");', False),
        "any other AKIA shaped id is caught": (b'StaticCredentials C = new StaticCredentials("' + b'AKIAIOSFODNN7EXAMPL' + b'F' + b'");', True),
        "AKIA id with different tail is caught": (b'x ' + b'AKIA' + b'QWERTYUIOP' + b'123456' + b' y', True),
        "private key block is caught": (b'-----BEGIN OPENSSH ' + b'PRIVATE KEY-----\nabcdef\n-----END', True),
        "openai style token is caught": (b'key=sk-' + b'abcdefghijklmnopqrstuvwxyz' + b'1234', True),
        "project scoped token is caught": (b'key=sk-proj-' + b'abcdefghijklmnopqrstuvwxyz' + b'1234', True),
        "github pat is caught": (b'token: ghp_' + b'a' * 36, True),
        "github server token is caught": (b'token: ghs_' + b'b' * 36, True),
        "plain text password is out of scope here": (b'DB_PASSWORD=hunter2hunter2', False),
        "short akia prefix does not match": (b'AKIA123', False),
    }
    failures = []
    for label, (data, expected) in sorted(fixtures.items()):
        got = bool(matches(data))
        if got != expected:
            failures.append(f"{label}: expected flagged={expected}, got {got}")
    for value, reason in EXEMPT_VALUES.items():
        if matches(value + b" trailing"):
            failures.append(f"exempted value still flagged: {value!r}")
        if len(value) < 20:
            failures.append(f"exemption {value!r} is too short to be safe as an exact-value rule")
        if not reason:
            failures.append(f"exemption {value!r} has no justification")
    print("secret_scan self-test: " + ("FAILED: " + "; ".join(failures) if failures else
                                       f"{len(fixtures)} fixtures and {len(EXEMPT_VALUES)} exemptions agree"))
    return bool(failures)

def scan():
    paths = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
                                    cwd=ROOT).split(b'\0')
    failures = []
    for raw in set(paths):
        if not raw:
            continue
        path = ROOT / raw.decode('utf-8')
        if not path.is_file():
            continue
        if matches(path.read_bytes()):
            failures.append(path.relative_to(ROOT).as_posix())
    print('Secret pattern scan: ' + ('FAILED: ' + ', '.join(sorted(failures)) if failures else 'no matches'))
    return bool(failures)

if __name__ == "__main__":
    sys.exit(1 if ("--self-test" in sys.argv and self_test()) or ("--self-test" not in sys.argv and scan()) else 0)

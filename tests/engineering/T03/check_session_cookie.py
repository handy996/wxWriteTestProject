"""Session cookie name consistency across contract, config, code, tests and CI (rc.3 EDITORIAL_SESSION).

Zero third-party dependencies on the Python side. The frozen OpenAPI is JSON-syntax YAML so json.loads reads it
directly; the additive paged-Diff document is plain block YAML, read with an indentation scanner over the two blocks
that matter (`security` and `securitySchemes`).

What this gate proves, and by which mechanism (the tenth review asked for the wording to match the evidence, so the
three layers are stated separately rather than blended into one "the guard is live" claim):

  1. STATIC TEXT CENSUS. Contract anchors, config declarations, the Java constant, the guard clauses and the CI
     wiring are read as text. Text proves presence and shape; it cannot prove that a statement runs. The Java scanner
     here translates \\uXXXX escapes exactly as JLS 3.3 does (even-backslash rule, malformed escapes refused, because
     javac refuses the file) and lexes each source ONCE, so comments, string literals and text blocks are the same
     token stream for every downstream view.
  2. EXECUTED PROOF. `evidence/guard-test-binding.json` records a real offline `mvn test` run of
     T03SessionCookieGuardTest; `evidence/T03SessionCookieGuardTest.xml` is that run's surefire report. The case
     names and counts parsed out of that XML are the load-bearing evidence here: the assembly cases really invoke the
     production `identitySecurity` bean method through an AnnotationConfigApplicationContext, so a call site wrapped
     in a constant-false branch, preceded by an early return or commented out makes the recorded run fail - and the
     gate refuses a binding whose XML does not contain the executed cases it derived from the current source shape.
     The same run resolves the effective cookie name with Spring's own YamlPropertySourceLoader,
     PropertiesPropertySourceLoader and Binder over the real classpath surface, which is what a hand-written text
     census cannot do for anchors, merge keys, multi-line flow, `.properties` files or classpath:/config/.
  3. CI STRUCTURE. `.github/workflows/ci.yml` is parsed as a workflow, not grepped: the step that runs this gate must
     live in a job reachable from a push or pull_request trigger, and neither the step, the job, nor any job it
     `needs` may carry `continue-on-error` or a conditional `if:`.

Limits, stated because the last four reviews were about claims outrunning evidence: the static call-site analysis
folds only compile-time constants, so a runtime-false condition is judged by layer 2 and not here; the recorded run
is a reproduction, not a pipeline artefact, and a hand-written record that matches the current bytes is still
possible (the CI job re-runs the suite, which is where that forgery actually dies); a config file reachable only
through `spring.config.location` is not attributable, so finding one fails this gate loudly instead of skipping it.

Negative controls mutate the loaded sources **in memory only** - the approved rc.3 files are never written to, not
even temporarily.

Usage: python tests/engineering/T03/check_session_cookie.py [--output evidence.json]
Exit 0 when every layer agrees; exit 1 with the mismatch printed.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[3]
APPROVED_NAME = "EDITORIAL_SESSION"          # the name rc.3 declares and the R04 decision approved
FORBIDDEN = "JSESSION" + "ID"                # the container default; assembled so the gate never carries the literal
COOKIE_PATH = ("server", "servlet", "session", "cookie", "name")
COOKIE_PARENT = ".".join(COOKIE_PATH[:-1])
SCALAR = re.compile(r"([^:#]+?):[ \t]*(.*)$")
HEX_DIGITS = "0123456789abcdefABCDEF"


class Rejected(AssertionError):
    """A judgement this gate refuses. Subclasses AssertionError so the control loop catches it like any other."""


class Uncompilable(Rejected):
    """The file does not survive javac's own translation or lexing, so no claim about its code structure is sound."""


# --------------------------------------------------------------------------------------- sources and constants
GUARD_CALL = re.compile(r'verifySessionCookieContract\(\s*env\s*\)\s*;')
GUARD_NAME = re.compile(
    r'if\s*\(\s*!\s*SESSION_COOKIE_NAME\.equals\s*\(\s*env\.getProperty\s*\(\s*"server\.servlet\.session\.cookie\.name"'
    r'\s*,\s*""\s*\)\s*\)\s*\)')
GUARD_PROD_IF = re.compile(r'if\s*\(\s*env\.matchesProfiles\s*\(\s*"prod"\s*\)\s*&&')
GUARD_PROD_SECURE = re.compile(r'"server\.servlet\.session\.cookie\.secure"\s*,\s*Boolean\.class\s*,\s*false')
GUARD_PROD_HTTP_ONLY = re.compile(r'"server\.servlet\.session\.cookie\.http-only"\s*,\s*Boolean\.class\s*,\s*true')
GUARD_PROD_SAME_SITE = re.compile(r'"strict"\.equals\s*\(\s*env\.getProperty\s*\(\s*"server\.servlet\.session\.cookie\.same-site"')
GUARD_MESSAGES = (
    re.compile(r'throw new IllegalStateException\(\s*"T03_COOKIE: session cookie name must equal the approved contract name "'),
    re.compile(r'throw new IllegalStateException\(\s*"T03_COOKIE: secure production cookie required"'),
)
TEST_ASSERTION = re.compile(r'allValues\(\s*"Set-Cookie"\s*\)[^\n]*startsWith\(\s*T03Configuration\.SESSION_COOKIE_NAME\s*\+\s*"="')
CONTAINER_DEFAULT_CASE = "containerDefaultNameAbortsStartup"   # the one place the container default may be named
GUARD_CALL_SOURCE = "        verifySessionCookieContract(env);"
THROW_NAME = ('throw new IllegalStateException("T03_COOKIE: session cookie name must equal the approved '
              'contract name "+SESSION_COOKIE_NAME);')
THROW_PROD = 'throw new IllegalStateException("T03_COOKIE: secure production cookie required");'
GUARD_CLAUSES = (
    (GUARD_NAME, "cookie-name guard clause"),
    (GUARD_PROD_IF, 'if(env.matchesProfiles("prod") && branch'),
    (GUARD_PROD_SECURE, "secure-attribute clause"),
    (GUARD_PROD_HTTP_ONLY, "http-only clause"),
    (GUARD_PROD_SAME_SITE, "same-site clause compared to strict"),
)
# The three attributes the production prod branch reads. They live as class-level constants in the test, so the
# requirement is file-wide rather than inside one body, and it is matched on the comment-free view.
PROD_ATTRIBUTE_PATHS = ("server.servlet.session.cookie.secure", "server.servlet.session.cookie.http-only",
                        "server.servlet.session.cookie.same-site")
T03_CONFIGURATION_SYMBOL = "T03Configuration"

SOURCES = {
    "frozenContract": ROOT / "docs/api/openapi.yaml",
    "additiveContract": ROOT / "docs/api/diff-pages-v1.1.openapi.yaml",
    "code": ROOT / "backend/src/main/java/com/example/editorial/identity/T03Configuration.java",
    "test": ROOT / "backend/src/test/java/com/example/editorial/identity/T03PostgresTest.java",
    "guardTest": ROOT / "backend/src/test/java/com/example/editorial/identity/T03SessionCookieGuardTest.java",
    "binding": ROOT / "tests/engineering/T03/evidence/guard-test-binding.json",
    "guardTestXml": ROOT / "tests/engineering/T03/evidence/T03SessionCookieGuardTest.xml",
    # The census the executed case published: which config layers it opened, their checksums, and what the binder
    # resolved per profile. It is the executed answer to a text census being unable to attribute a shape.
    "census": ROOT / "tests/engineering/T03/evidence/config-census.txt",
    "gate": ROOT / "tests/engineering/T03/check_session_cookie.py",
    "recorder": ROOT / "tests/engineering/T03/record_guard_binding.py",
    "pom": ROOT / "backend/pom.xml",
    "ci": ROOT / ".github/workflows/ci.yml",
}
OPTIONAL_SOURCES = ("binding", "guardTestXml", "census", "recorder")
GUARD_TEST_CLASS = "T03SessionCookieGuardTest"
GUARD_TEST_PACKAGE = "com.example.editorial.identity"
CONFIG_ROOTS = (ROOT / "backend/src/main/resources", ROOT / "backend/src/test/resources")
CONFIG_EXTENSIONS = ("yml", "yaml", "properties")
CONFIG_STEM = "application"
BASE_CONFIG = "application.yml"
BASE_LABEL = "config:" + str((CONFIG_ROOTS[0] / BASE_CONFIG).relative_to(ROOT)).replace("\\", "/")
POM = ROOT / "backend/pom.xml"
SPRING_FACTORIES = ROOT / "backend/src/main/resources/META-INF/spring.factories"
MVN = ROOT / ".tools/t02/apache-maven-3.9.11/bin/mvn.cmd"
REPO = ROOT / ".tools/t02/m2"
SHELL_TOKENS = ("&&", "||", ";", "|", ">", "<", "&")
FORBIDDEN_EXECUTABLES = ("echo", "cmd", "sh", "bash", "pwsh", "/c", "-c")
BINDING_NOTE = (
    "produced by record_guard_binding.py. Every input listed under inputSha256 is re-hashed by the gate against this "
    "checkout, the surefire XML is re-parsed (counts, testcase names, properties), the recorded command is compared "
    "with the gate's own pinned argv, and the surefire provider jar plus the JDK launcher are re-hashed when this "
    "checkout contains them. It does not prove that a human ran the command: a hand-written record matching the "
    "current bytes is still possible, which is why .github/workflows/ci.yml re-runs both this gate and this test class "
    "in the same push/PR job.")


def relative(path):
    """Repo-relative posix text, so a record is not tied to one machine's drive letter."""
    resolved = Path(path)
    try:
        return str(resolved.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return resolved.as_posix()


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalize_path_text(text):
    return str(text).replace("\\", "/").lower().rstrip("/")


def tail_matches(absolute_text, relative_path):
    """True when a path recorded in an artefact is the repo-relative path the gate expects."""
    return normalize_path_text(absolute_text).endswith("/" + normalize_path_text(relative_path))


def config_paths():
    """Every file on the config surface Boot's config files would read: both resource roots, all loaders' extensions."""
    found = {}
    for root in CONFIG_ROOTS:
        if not root.exists():
            continue
        for location in (root, root / "config"):
            if not location.is_dir():
                continue
            for extension in CONFIG_EXTENSIONS:
                for path in sorted(location.glob(CONFIG_STEM + "*." + extension)):
                    if path.is_file():
                        found["config:" + relative(path)] = path
    return found


def config_all():
    """Every config-shaped file in both resource roots and their config/ layers, whatever the extension."""
    readable, unread = {}, {}
    for root in CONFIG_ROOTS:
        if not root.exists():
            continue
        for location in (root, root / "config"):
            if not location.is_dir():
                continue
            for path in sorted(location.glob(CONFIG_STEM + "*.*")):
                if not path.is_file():
                    continue
                label = "config:" + relative(path)
                extension = path.suffix.lstrip(".").lower()
                if extension in CONFIG_EXTENSIONS:
                    readable[label] = path
                else:
                    unread[label] = path
    return readable, unread


def config_paths():
    """The config surface this census and the executed loaders can both read: yml, yaml and properties."""
    return config_all()[0]


def config_unread():
    """Config-shaped files whose extension neither this census nor the executed loaders open.

    Boot's loader registry accepts more extensions than this card attributes, so a file like application.xml could be
    read at runtime and by no face here. That is reported loudly instead of being quietly left out of the surface.
    """
    return config_all()[1]


def config_texts():
    return {label: path.read_text(encoding="utf-8", errors="replace") for label, path in config_paths().items()}


def read_sources():
    sources = {}
    for key, path in SOURCES.items():
        if key in OPTIONAL_SOURCES and not path.exists():
            sources[key] = None
            continue
        sources[key] = path.read_text(encoding="utf-8", errors="replace")
    readable, unread = config_all()
    return sources | {"configs": {label: path.read_text(encoding="utf-8", errors="replace")
                                  for label, path in readable.items()},
                      "unread": unread}


# --------------------------------------------------------------------- JLS 3.3 translation and the one Java lexer
def translate_unicode_escapes(text):
    r"""Translate \uXXXX the way javac does before lexing, and refuse what javac refuses.

    JLS 3.3: a backslash begins a unicode escape only when it is preceded by an even number of backslashes. So
    "JSESSION\u0049D" becomes JSESSIONID in the constant pool (the ninth review's F-05: raw-byte scanning saw a
    different identifier than the compiler did), while "\\u0049" stays the two characters \u0049. Translation happens
    before tokenising, comments included, so \u002a\u002a really does open a block comment around a guard line and
    \u000a really does end a line comment. An escape that is not a valid \uXXXX (or \u{...}) form is a compile error,
    and a scanner that silently accepted it would be describing a file javac rejects.

    Returns the translated text and an offset map back into the raw source, so a mutation found in the translated
    view can be spliced into the file the reviewer will read.
    """
    out, offsets = [], []
    index, size = 0, len(text)
    while index < size:
        ch = text[index]
        if ch != "\\":
            out.append(ch)
            offsets.append(index)
            index += 1
            continue
        run = 0
        while index + run < size and text[index + run] == "\\":
            run += 1
        if run % 2 == 0:
            # an even run translates nothing; every backslash of it is content
            out.append("\\" * run)
            offsets.extend([index] * run)
            index += run
            continue
        out.append("\\" * (run - 1))
        offsets.extend([index] * (run - 1))
        # text[index] is the one backslash of the run that is eligible for translation
        probe = index + 1
        us = 0
        while probe < size and text[probe] == "u":
            probe += 1
            us += 1
        if us == 0:
            out.append("\\")
            offsets.append(index)
            index += 1
            continue
        if probe + 4 <= size and all(c in HEX_DIGITS for c in text[probe:probe + 4]):
            out.append(chr(int(text[probe:probe + 4], 16)))
            offsets.append(index)
            index = probe + 4
            continue
        if probe < size and text[probe] == "{":
            end = text.find("}", probe + 1)
            digits = text[probe + 1:end] if end > probe else ""
            if end > probe and digits and len(digits) <= 6 and all(c in HEX_DIGITS for c in digits):
                out.append(chr(int(digits, 16)))
                offsets.append(index)
                index = end + 1
                continue
        raise Uncompilable(f"illegal unicode escape {text[index:index + 12]!r}: javac rejects this file (JLS 3.3)")
    return "".join(out), offsets


def scan_java(text):
    """One lexical pass over translated Java source: [(kind, start, end)] covering every character.

    Kinds are code, lineComment, blockComment, string, char and textBlock. This is the only lexer in the gate: the
    comment-free view, the literal-masked view and the prose-free view are all built from this token list, so they
    cannot disagree about where a literal ends. The ninth review's F-09 measured 1548 of 6000 fuzzed inputs where the
    two lexers it had disagreed, 76.9% of them on plain text blocks.
    """
    tokens, size = [], len(text)
    index, code_start = 0, 0

    def flush(end):
        if end > code_start:
            tokens.append(("code", code_start, end))

    while index < size:
        if text.startswith("//", index):
            flush(index)
            end = text.find("\n", index)
            end = size if end < 0 else end
            tokens.append(("lineComment", index, end))
            index = code_start = end
            continue
        if text.startswith("/*", index):
            flush(index)
            end = text.find("*/", index + 2)
            if end < 0:
                raise Uncompilable("unclosed block comment")
            tokens.append(("blockComment", index, end + 2))
            index = code_start = end + 2
            continue
        if text.startswith('"""', index):
            flush(index)
            scan = index + 3
            while scan < size and text[scan] in " \t":
                scan += 1
            if scan >= size or text[scan] != "\n":
                raise Uncompilable("text block opening delimiter must be followed by a line terminator")
            while scan < size:
                if text.startswith("\\", scan):
                    scan += 2
                    continue
                if text.startswith('"""', scan):
                    tokens.append(("textBlock", index, scan + 3))
                    index = code_start = scan + 3
                    break
                scan += 1
            else:
                raise Uncompilable("unclosed text block")
            continue
        if text[index] in "\"'":
            flush(index)
            quote, scan = text[index], index + 1
            while scan < size and text[scan] != quote:
                if text[scan] == "\\":
                    if scan + 1 >= size:
                        raise Uncompilable("literal ends at end of file")
                    scan += 2
                    continue
                if text[scan] == "\n":
                    raise Uncompilable("unclosed string literal: javac does not carry a literal across a line")
                scan += 1
            if scan >= size:
                raise Uncompilable("unclosed literal")
            tokens.append(("string" if quote == '"' else "char", index, scan + 1))
            index = code_start = scan + 1
            continue
        index += 1
    flush(size)
    cursor = 0
    for _, start, end in tokens:
        if start != cursor or end <= start:
            raise Uncompilable(f"lexer coverage gap at offset {cursor}")
        cursor = end
    if cursor != size:
        raise Uncompilable("lexer does not cover the whole file")
    return tokens


BLANK_VIEWS = ("lineComment", "blockComment")


class JavaSource:
    """A Java file after javac's translation, lexed once, projected into the three views the checks need."""

    def __init__(self, raw, label):
        self.label = label
        self.raw = raw
        self.translated, self.offsets = translate_unicode_escapes(raw)
        self.tokens = scan_java(self.translated)
        self.code = self._projection(keep_literals=True, blank_text_blocks=False)
        self.masked = self._projection(keep_literals=False, blank_text_blocks=False)
        self.statements = self._projection(keep_literals=True, blank_text_blocks=True)
        self.literal_spans = [(start + 1, end - 1) for kind, start, end in self.tokens
                              if kind in ("string", "char", "textBlock") and end - start > 2]
        self.text_block_spans = [(start + 3, end - 3) for kind, start, end in self.tokens if kind == "textBlock"]
        self.comment_spans = [(start, end) for kind, start, end in self.tokens
                              if kind in BLANK_VIEWS]

    def _projection(self, keep_literals, blank_text_blocks):
        out = []
        for kind, start, end in self.tokens:
            piece = self.translated[start:end]
            if kind in BLANK_VIEWS:
                out.append("".join(ch if ch == "\n" else " " for ch in piece))
            elif kind == "code" or (keep_literals and kind in ("string", "char")) or \
                    (keep_literals and kind == "textBlock" and not blank_text_blocks):
                out.append(piece)
            elif kind == "textBlock" and blank_text_blocks:
                out.append('"""' + "".join(ch if ch == "\n" else " " for ch in piece[3:-3]) + '"""')
            else:
                out.append(piece[0] + "".join(ch if ch == "\n" else "x" for ch in piece[1:-1]) + piece[-1])
        return "".join(out)

    def raw_offset(self, translated_offset):
        """Map an offset in the translated view back to the raw file, so controls can splice escaped text."""
        if translated_offset >= len(self.offsets):
            return len(self.raw)
        return self.offsets[translated_offset]

    def in_prose(self, offset):
        """Strictly inside a text block's content: prose to a reader, not executable code."""
        return any(start < offset < end for start, end in self.text_block_spans)

    def in_literal(self, offset):
        """Strictly inside a literal's content: a match there is string data, not a statement using it."""
        return any(start < offset < end for start, end in self.literal_spans)

    def live(self, pattern, view=None):
        """The first match of `pattern` in the view the caller asked for.

        The views carry the comment decision: comments are blanked in every one of them, `statements` additionally
        blanks text-block prose. A match that sits strictly inside a literal's content is skipped here because it is
        data, not a statement - "T03_COOKIE" written inside a string is not a throw carrying that message, and
        `server.servlet.session.cookie.secure` written inside a string is not a clause reading that attribute. Both
        halves are measured: the round-ten audit found the position rule carried the two only-in-literal controls that
        a stale record had been hiding.
        """
        text = view if view is not None else self.statements
        for match in pattern.finditer(text):
            if not self.in_literal(match.start()):
                return match
        return None

    def require_live(self, pattern, what, view=None):
        match = self.live(pattern, view)
        if match is None:
            raise Rejected(f"{self.label}: no live (non-comment, non-prose) {what} remains")
        return match

    def methods(self):
        """{name: (start, end)} of every brace-delimited method body in the masked view."""
        found = {}
        for match in re.finditer(r'(?m)^[ \t]*(?:@\w+[ \t]*)*(?:[A-Za-z_][\w.]*[ \t]+|[A-Za-z_][\w.<>\[\], ?]*[ \t])+'
                                 r'([a-zA-Z_]\w*)[ \t]*\([^;{=]*?\)[ \t]*(?:throws[ \t][^;{]+?[ \t])?\{', self.masked):
            name, open_index = match.group(1), self.masked.find("{", match.end() - 1)
            if open_index < 0:
                continue
            try:
                close = match_brace(self.masked, open_index, len(self.masked))
            except Uncompilable:
                raise Rejected(f"{self.label}: method {name} is not brace-balanced")
            found.setdefault(name, (open_index, close + 1))
        if not found:
            raise Rejected(f"{self.label}: no method body survives translation and lexing")
        return found


def match_brace(text, start, end):
    """Index of the brace that closes text[start] == '{'."""
    depth = 0
    index = start
    while index < end:
        ch = text[index]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    raise Uncompilable(f"unbalanced brace at offset {start}")


# ------------------------------------------------------------------ statement walking, auxiliary only
NON_METHOD_WORDS = ("return", "new", "throw", "else", "for", "if", "while", "switch", "catch", "do", "try",
                    "synchronized", "case", "instanceof", "assert", "break", "continue", "yield")
CONTINUATION_WORDS = ("else", "catch", "finally", "while")


def skip_space(text, index, end):
    while index < end and text[index].isspace():
        index += 1
    return index


def leading_word(text, index, end):
    match = re.match(r"[A-Za-z_]\w*", text[index:end])
    return match.group(0) if match else ""


def scan_header(text, index, end):
    """One statement header: the text up to the first top-level ';' or '{', plus which one stopped it."""
    start, depth = index, 0
    while index < end:
        ch = text[index]
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == "{":
            if depth <= 0:
                return text[start:index], index, "{"
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
        elif depth <= 0 and ch == ";":
            return text[start:index], index + 1, ";"
        index += 1
    return text[start:end], end, "eof"


def paren_argument(header):
    """The text inside the first balanced paren group of a header, or None."""
    open_index = header.find("(")
    if open_index < 0:
        return None
    depth = 0
    for position in range(open_index, len(header)):
        if header[position] == "(":
            depth += 1
        elif header[position] == ")":
            depth -= 1
            if depth == 0:
                return header[open_index + 1:position]
    return None


def construct_of(header):
    words = set(re.findall(r"[A-Za-z_]\w*", header))
    if "->" in header:
        return "lambda"
    if words & {"class", "interface", "enum", "record"}:
        return "class"
    if re.search(r"\bnew\s+[\w.<>\[\]]*\s*\([^()]*\)\s*$", header):
        return "anonymous"
    first = leading_word(header.strip(), 0, len(header.strip()))
    return first if first in ("if", "while", "for", "do", "switch", "try", "synchronized") else "other"


def split_level(text, start, end):
    """The statements of a block body, each with its span and the blocks it owns plus the terms guarding them.

    Terms per block are a conjunction of (condition, negated) pairs, or a 'dead' marker for a lambda, anonymous or
    nested class body - code that a bean assembly never runs. try/catch/finally, switch labels, else branches and
    loop bodies with a real condition are all reachable, which is the (a) half of the tenth review's requirement:
    the previous depth-1 rule rejected them.
    """
    items = []
    index = skip_space(text, start, end)
    while index < end:
        item_start = index
        header, after, kind = scan_header(text, index, end)
        construct = construct_of(header)
        parts = []
        if kind == ";":
            items.append({"start": item_start, "end": after, "header": header, "construct": construct, "parts": parts})
            index = skip_space(text, after, end)
            continue
        if kind == "eof":
            break
        close = match_brace(text, after, end)
        index = close + 1
        if construct in ("lambda", "anonymous", "class"):
            parts.append((after, close, [("dead", construct)]))
        elif construct == "if":
            condition = paren_argument(header) or ""
            parts.append((after, close, [("const", condition, False)]))
            probe = skip_space(text, index, end)
            while leading_word(text, probe, end) == "else":
                probe = skip_space(text, probe + 4, end)
                if leading_word(text, probe, end) == "if":
                    else_header, else_after, else_kind = scan_header(text, probe, end)
                    else_close = match_brace(text, else_after, end) if else_kind == "{" else None
                    if else_close is None:
                        break
                    parts.append((else_after, else_close,
                                  [("const", condition, True), ("const", paren_argument(else_header) or "", False)]))
                    condition = paren_argument(else_header) or ""
                    index = probe = else_close + 1
                else:
                    if text[probe] != "{":
                        break
                    else_close = match_brace(text, probe, end)
                    parts.append((probe, else_close, [("const", condition, True)]))
                    index = probe = else_close + 1
                    break
        elif construct in ("while", "for"):
            parts.append((after, close, [("const", paren_argument(header) or "", False)]))
        elif construct == "try":
            parts.append((after, close, []))
            probe = skip_space(text, index, end)
            while leading_word(text, probe, end) in ("catch", "finally"):
                head, head_after, head_kind = scan_header(text, probe, end)
                if head_kind != "{":
                    break
                catch_close = match_brace(text, head_after, end)
                parts.append((head_after, catch_close, []))
                index = probe = catch_close + 1
        else:
            parts.append((after, close, []))
            if construct == "do":
                probe = skip_space(text, index, end)
                if leading_word(text, probe, end) == "while":
                    _, index = scan_header(text, probe, end)
        items.append({"start": item_start, "end": index, "header": header, "construct": construct, "parts": parts})
        index = skip_space(text, index, end)
    return items


def split_top(expression, operator):
    """Split at top-level occurrences of a boolean operator; the text is already literal-masked."""
    parts, depth, current = [], 0, ""
    index = 0
    while index < len(expression):
        ch = expression[index]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if depth == 0 and expression.startswith(operator, index):
            parts.append(current)
            current = ""
            index += len(operator)
            continue
        current += ch
        index += 1
    parts.append(current)
    return [part for part in parts if part.strip()]


FOLDED_CALLS = {
    "Boolean.TRUE.booleanValue()": True, "Boolean.FALSE.booleanValue()": False,
    "Optional.empty().isPresent()": False, "Optional.empty().isEmpty()": True,
}


def constant_boolean(expression, constants, visiting=()):
    """True/False when javac could fold it, None when it depends on runtime state. Never raises."""
    try:
        return _constant_boolean(expression.strip(), constants, visiting)
    except Exception:
        return None


def _constant_boolean(expression, constants, visiting):
    if not expression:
        return None
    while expression.startswith("(") and expression.endswith(")"):
        depth, closed = 0, True
        for position, ch in enumerate(expression):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and position != len(expression) - 1:
                    closed = False
                    break
        if closed:
            expression = expression[1:-1].strip()
            continue
        break
    for operator, unanimous, exists in (("||", False, True), ("&&", True, False)):
        parts = split_top(expression, operator)
        if len(parts) > 1:
            values = [_constant_boolean(part, constants, visiting) for part in parts]
            if any(value is exists for value in values):
                return exists
            if all(value is not None for value in values):
                return not unanimous
            return None
    if expression.startswith("!"):
        inner = _constant_boolean(expression[1:].strip(), constants, visiting)
        return None if inner is None else not inner
    if expression in ("true",):
        return True
    if expression in ("false",):
        return False
    collapsed = re.sub(r"\s+", "", expression)
    if collapsed in FOLDED_CALLS:
        return FOLDED_CALLS[collapsed]
    match = re.fullmatch(r"Boolean\.(TRUE|FALSE)\.equals\((.*)\)", collapsed)
    if match:
        inner = _constant_boolean(match.group(2), constants, visiting)
        return None if inner is None else (inner is (match.group(1) == "TRUE"))
    match = re.fullmatch(r"(-?\d+)\s*(==|!=|<|<=|>|>=)\s*(-?\d+)", collapsed)
    if match:
        left, right = int(match.group(1)), int(match.group(3))
        return {"==": left == right, "!=": left != right, "<": left < right,
                "<=": left <= right, ">": left > right, ">=": left >= right}[match.group(2)]
    if re.fullmatch(r"[A-Za-z_]\w*", expression):
        if expression in visiting:
            return None
        if expression not in constants:
            return None
        return _constant_boolean(constants[expression], constants, visiting + (expression,))
    return None


BOOLEAN_CONSTANTS = re.compile(r"\b(?:static\s+)?final\s+boolean\s+([A-Za-z_]\w*)\s*=\s*([^;]+);")
BEAN_ANY = re.compile(r"@Bean[\s\S]{0,200}?\b([A-Za-z_]\w*)\s*\(")
STATIC_TRANSFER = re.compile(r"^(return|throw|break|continue|yield)\b")


def bean_bodies(java):
    """Bodies of every @Bean method, located in the masked view so literal braces cannot cut a span short."""
    bodies = java.methods()
    found = []
    for match in BEAN_ANY.finditer(java.code):
        name = match.group(1)
        if name in bodies:
            found.append((name, bodies[name][0], bodies[name][1]))
    if not found:
        raise Rejected(f"{java.label}: no brace-balanced @Bean method body survives translation and lexing")
    return found


def guard_call_site(java):
    """Where the guard call sits, and what static analysis may honestly say about it.

    This is the auxiliary layer. It accepts a call that is a direct statement, in a try/finally, in a switch default
    or in an else branch, and rejects the shapes javac proves dead: a constant-false if/while/for condition, an
    unconditional return or throw before the call, and a call that only lives inside a lambda, anonymous or nested
    class body the assembly never runs. A condition javac cannot fold - a real test that happens to be false - is
    outside its reach and is judged by the executed assembly cases in the surefire XML instead.
    """
    masked = java.masked
    constants = {name: value.strip() for name, value in BOOLEAN_CONSTANTS.findall(java.code)}
    rejections = []
    for bean_name, open_index, close_index in bean_bodies(java):
        for match in GUARD_CALL.finditer(masked[open_index:close_index]):
            offset = open_index + match.start()
            dead = describe_dead_path(masked, open_index + 1, close_index, offset, constants)
            if dead is None:
                return {"live": True, "bean": bean_name,
                        "basis": f"direct statement of the assembled bean {bean_name}, every enclosing condition is "
                                 "open or compile-time satisfiable and no unconditional transfer precedes it"}
            rejections.append(f"{bean_name}: {dead}")
    if rejections:
        return {"live": False, "bean": None, "basis": "; ".join(rejections)}
    return {"live": False, "bean": None, "basis": "no verifySessionCookieContract(env) call in code at all"}


def describe_dead_path(text, body_start, body_end, offset, constants, depth=0):
    """Walk in from a bean body to the statement holding `offset`; None when nothing proves it dead."""
    if depth > 12:
        return "nesting too deep to follow"
    items = split_level(text, body_start, body_end)
    target, preceding = None, []
    for item in items:
        if item["start"] <= offset < item["end"]:
            target = item
            break
        preceding.append(item)
    if target is None:
        return None
    for item in preceding:
        header = item["header"].strip()
        if not item["parts"] and STATIC_TRANSFER.match(header):
            return f"an unconditional {leading_word(header, 0, len(header))} leaves the block before the call"
    if not target["parts"]:
        header = target["header"]
        arrow = header.find("->")
        if arrow >= 0 and target["start"] + arrow < offset:
            return "the call is only inside a lambda body, which bean assembly does not run"
        if STATIC_TRANSFER.match(header.strip()):
            return "the statement holding the call already transfers control"
        construct = target["construct"]
        if construct in ("if", "while", "for"):
            condition = paren_argument(header) or ""
            if constant_boolean(condition, constants) is False:
                return (f"the call is the single statement a brace-less constant-false {construct} "
                        f"({reduction(condition)}) governs, which javac proves unreachable")
        return None
    for lo, hi, terms in target["parts"]:
        if not lo <= offset <= hi:
            continue
        for term in terms:
            if term[0] == "dead":
                return f"the call is only inside a {term[1]} body, which bean assembly does not run"
            value = constant_boolean(term[1], constants)
            if value is not None:
                effective = (not value) if term[2] else value
                if effective is False:
                    polarity = "else of" if term[2] else "body of"
                    return (f"the {polarity} a compile-time constant-false condition "
                            f"({reduction(term[1])}) never executes")
        return describe_dead_path(text, lo + 1, hi, offset, constants, depth + 1)
    return None


def guard_clause_paths(java):
    """Each clause and rejection message has to be reachable live code *inside the guard*, not merely in the file.

    Round nine's F-01 second half: the assembly walk said the call site was live - it was - while the method it calls
    had been neutered into `return;` followed by checks nobody reaches. And a needle matched anywhere in the file cannot
    see a clause moved out or a profile token renamed, because this class mentions "prod" in the origin rule too. So
    the search is scoped to the guard's own body span and every clause is walked with the same statement machinery the
    bean body uses. It stays auxiliary: a condition javac cannot fold is judged by the executed cases, not here.
    """
    body = java.methods().get(GUARD_SYMBOL)
    if body is None or body[0] >= body[1]:
        raise Rejected(f"{java.label}: no readable {GUARD_SYMBOL} method body remains after translation and lexing")
    start, end = body
    constants = {name: value.strip() for name, value in BOOLEAN_CONSTANTS.findall(java.code)}
    missing, unreachable = [], []
    needles = list(GUARD_CLAUSES) + [(message, f"throw carrying rejection message {index + 1}")
                                     for index, message in enumerate(GUARD_MESSAGES)]
    for pattern, what in needles:
        match = pattern.search(java.code, start, end)
        if match is None:
            missing.append(what)
            continue
        dead = describe_dead_path(java.masked, start + 1, end, match.start(), constants)
        if dead:
            unreachable.append(f"{what}: {dead}")
    if missing:
        raise Rejected(f"{java.label}: no live (non-comment, non-prose, non-literal) {', '.join(missing)} remains "
                       f"inside {GUARD_SYMBOL}")
    if unreachable:
        raise Rejected(f"{java.label}: the guard's own clauses are not reachable -> " + "; ".join(unreachable))
    return {"clausesChecked": len(needles), "scope": [start, end], "guard": GUARD_SYMBOL}


def reduction(text):
    return re.sub(r"\s+", " ", text).strip()[:60]


# ------------------------------------------------------------------------------- config surface census
LOCATION_TOKENS = ("spring.config.location", "spring.config.additional-location",
                   "spring.config.import", "spring.config.optional", "optional:")
CONSTRUCT_TOKENS = ("&", "*", "!", "<<", "?", "|", ">", "\t")


def _unquote(value):
    if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
        return value[1:-1]
    return value.strip()


def strip_yaml_comment(line):
    """Drop a YAML comment, respecting quoting, without touching the rest of the line."""
    quote, index = None, 0
    while index < len(line):
        ch = line[index]
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (index == 0 or line[index - 1] in " \t"):
            return line[:index].rstrip()
        index += 1
    return line.rstrip()


def flow_depth(chunk):
    """Net brace/bracket depth of a flow chunk, quote aware."""
    depth, quote, index = 0, None, 0
    while index < len(chunk):
        ch = chunk[index]
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
        index += 1
    return depth


def _split_flow(inner):
    parts, depth, current, quote, index = [], 0, "", None, 0
    while index < len(inner):
        ch = inner[index]
        if quote:
            current += ch
            if ch == quote:
                quote = None
            index += 1
            continue
        if ch in "\"'":
            quote, current = ch, current + ch
            index += 1
            continue
        if ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += ch
        index += 1
    if current.strip():
        parts.append(current)
    return parts


def walk_flow(fragment, depth=1):
    """(key, value, depth) triples read out of a flow mapping, as a block mapping would present them."""
    inner = fragment.strip()
    if inner.startswith("{") and inner.endswith("}"):
        inner = inner[1:-1]
    for item in _split_flow(inner):
        if ":" not in item:
            continue
        key, _, value = item.partition(":")
        key, value = _unquote(key.strip()), value.strip()
        if value.startswith("{"):
            yield key, "", depth
            yield from walk_flow(value, depth + 1)
        else:
            yield key, value, depth


def expand_yaml_flow(text, reasons):
    """Rewrite flow mappings, including ones that span lines, into equivalent block lines.

    The ninth review's F-02 fed the gate `server: { servlet: { session: {` with the name on the next line: a
    line-by-line expander sees an unterminated mapping and finds nothing. Collecting the chunk to its closing brace
    is what a real YAML parser does, and comments inside or after the chunk are stripped first, which is how
    `# embedded note` between a key and its flow body stopped being invisible.
    """
    lines = text.splitlines()
    out, index = [], 0
    while index < len(lines):
        raw = strip_yaml_comment(lines[index])
        stripped = raw.strip()
        indent = len(raw) - len(raw.lstrip(" "))
        match = SCALAR.match(stripped) if stripped and not stripped.startswith("#") else None
        if match and match.group(2).strip().startswith(("{", "[")):
            chunk, collected = match.group(2).strip(), index
            while flow_depth(chunk) > 0:
                if collected + 1 >= len(lines):
                    reasons.append("flow-mapping-never-closes")
                    break
                collected += 1
                follower = strip_yaml_comment(lines[collected]).strip()
                if follower:
                    chunk += " " + follower
            if flow_depth(chunk) != 0:
                out.append(raw)
                index += 1
                continue
            key = _unquote(match.group(1).strip())
            if chunk.startswith("["):
                reasons.append(f"sequence-value-at-{key.lower()}")
                out.append(raw)
                index = collected + 1
                continue
            out.append(" " * indent + key + ":")
            for flow_key, value, depth in walk_flow(chunk):
                out.append(" " * (indent + 2 * depth) + flow_key + (": " + value if value else ":"))
            index = collected + 1
            continue
        out.append(raw)
        index += 1
    return "\n".join(out)


def construct_reason(key, value):
    """Why a YAML construct at this path cannot be attributed by text, or None when it can."""
    for token, label in (("<<", "merge-key"), ("&", "anchor-definition"), ("!", "tag")):
        if key == token or key.startswith(token):
            return label
    if value.startswith("*"):
        return "alias-reference"
    if value.startswith(("|", ">")):
        return "block-scalar"
    if value.startswith("!"):
        return "tag"
    if "${" in value:
        return "placeholder-resolved-at-runtime"
    if "\t" in (key + value):
        return "tab-indentation"
    if re.match(r"^\*|(?<![\w.])&[\w-]+(?![\w-])", value):
        return "alias-or-anchor"
    return None


def census_yaml(text):
    """Every value declared at exactly server.servlet.session.cookie.name, plus what this census cannot attribute."""
    values, reasons, seen = [], [], {}
    documents, current = [], []
    for line in expand_yaml_flow(text, reasons).splitlines():
        if line.strip() in ("---", "..."):
            documents.append(current)
            current = []
            continue
        current.append(line)
    documents.append(current)
    for document in documents:
        stack, local = [], {}
        for raw in document:
            line = strip_yaml_comment(raw)
            if not line.strip():
                continue
            if line.lstrip().startswith("#"):
                continue
            indent = len(line) - len(line.lstrip(" "))
            while stack and stack[-1][0] >= indent:
                stack.pop()
            body = line.strip()
            if body.startswith("- "):
                continue
            match = SCALAR.match(body)
            if not match:
                reasons.append(f"not-a-mapping-entry-{reduction(body)}")
                continue
            key, value = _unquote(match.group(1).strip()), match.group(2).strip()
            path = tuple(k.lower() for _, k in stack) + (key.lower(),)
            dotted = ".".join(path)
            local[dotted] = local.get(dotted, 0) + 1
            reason = construct_reason(key.lower(), value)
            if reason and (COOKIE_PARENT.startswith(dotted) or dotted.startswith(COOKIE_PARENT) or not stack):
                reasons.append(f"{reason}@{dotted or 'root'}")
            if value == "" or value.startswith("#"):
                stack.append((indent, key))
                continue
            if path == COOKIE_PATH:
                values.append(_unquote(value))
        for dotted, times in local.items():
            if times > 1 and (COOKIE_PARENT.startswith(dotted) or dotted.startswith(COOKIE_PARENT)):
                reasons.append(f"duplicate-key@{dotted}")
    return values, sorted(set(reasons))


def census_properties(text):
    """Dotted keys of a .properties layer; environment-style underscore names are not bound, so they are not read."""
    values, reasons, seen = [], [], {}
    logical, buffer = [], ""
    for raw in text.splitlines():
        line = raw.rstrip()
        if buffer:
            line = buffer + line.lstrip()
        if line.endswith("\\") and not line.endswith("\\\\"):
            buffer = line[:-1]
            continue
        buffer, logical_line = "", line
        logical.append(logical_line)
    for line in logical:
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "!")):
            continue
        match = re.match(r"([^=:\s]+)[ \t]*[=:][ \t]*(.*)$", stripped)
        if not match:
            reasons.append(f"not-a-property-{reduction(stripped)}")
            continue
        key, value = match.group(1).strip(), match.group(2).strip()
        dotted = key.replace("\\=", "=").replace("\\:", ":").lower()
        seen[dotted] = seen.get(dotted, 0) + 1
        if dotted == ".".join(COOKIE_PATH):
            values.append(_unquote(value))
    for dotted, times in seen.items():
        if times > 1 and (COOKIE_PARENT.startswith(dotted) or dotted.startswith(COOKIE_PARENT)):
            reasons.append(f"duplicate-key@{dotted}")
    return values, sorted(set(reasons))


def census_config(label, text):
    if label.endswith(".properties"):
        return census_properties(text) + ("properties",)
    if label.endswith(".xml"):
        return [], ("xml-config-not-attributed-by-text",), "xml"
    return census_yaml(text) + ("yaml",)


def visible_declaration(text, kind="yaml"):
    """The part of a document that is a declaration rather than prose.

    A comment that discusses spring.config.location is not a location override, exactly as a comment that mentions the
    container default is not a cookie name; the decision is taken on the comment-free text, in every face.
    """
    lines = text.splitlines()
    if kind == "yaml":
        lines = [strip_yaml_comment(line) for line in lines]
    elif kind == "properties":
        lines = [line for line in lines if not line.lstrip().startswith(("#", "!"))]
    else:
        lines = [re.sub(r"<!--.*?-->", " ", line) for line in lines]
        lines = [line for line in lines if not line.lstrip().startswith(("#", "!"))]
    return "\n".join(lines)


def location_overrides(sources):
    """Any declaration that can move the config surface outside this census. Loud, never silent.

    A layer reachable only through spring.config.location, an additional-location or an optional: import cannot be
    attributed by name, so its presence rejects the gate instead of being skipped - otherwise "the census saw four
    files" would silently stop meaning "the census saw all of them".
    """
    found = []
    for label, document in sorted(sources["configs"].items()):
        kind = "properties" if label.endswith(".properties") else "yaml"
        visible = visible_declaration(document, kind)
        for token in LOCATION_TOKENS:
            if token in visible:
                found.append(f"{label}:{token}")
    for label in ("code", "test", "guardTest"):
        visible = JavaSource(sources[label], label).code
        for token in LOCATION_TOKENS:
            if token in visible:
                found.append(f"{label}:{token}")
    visible = visible_declaration(sources["ci"], "yaml")
    for token in LOCATION_TOKENS:
        if token in visible:
            found.append(f"ci:{token}")
    for path in (POM, SPRING_FACTORIES):
        if path.exists():
            kind = "xml" if path.suffix == ".xml" else "properties"
            visible = visible_declaration(path.read_text(encoding="utf-8", errors="replace"), kind)
            for token in LOCATION_TOKENS:
                if token in visible:
                    found.append(f"{relative(path)}:{token}")
    return found


# ------------------------------------------------------------------------------------- CI structure
CI_GATE_FILE = "check_session_cookie.py"
CI_GATE_PATH = "tests/engineering/T03/check_session_cookie.py"
SILENT_ON = ("push", "pull_request")


class CiStructureError(Rejected):
    """The workflow uses a construct this reader cannot follow, so its enforcement cannot be attributed."""


BLOCK_INDICATORS = ("|", "|-", "|+", ">", ">-", ">+")


def ci_document(text):
    """Read a GitHub Actions workflow far enough to judge enforcement, refusing what it cannot attribute.

    Block mappings, block sequences (including a mapping that opens on the dash line), one-line flow collections,
    quoted scalars and block scalars are handled. Anchors, aliases, tags, merge keys, complex keys, tabs and
    multi-document files raise, because a reader that quietly guessed at those would report enforcement it had not
    read. Internal `_line`/`_indent` keys record where each mapping came from, which is what lets a control insert a
    step key at the right column instead of anchoring on one spelling of the step name.
    """
    raw = text.splitlines()
    entries = []
    for number, line in enumerate(raw):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if line[:indent + 1].endswith("\t") or "\t" in line[:indent]:
            raise CiStructureError(f"line {number + 1}: tab indentation")
        if line.strip() in ("---", "..."):
            raise CiStructureError(f"line {number + 1}: multi-document workflow")
        entries.append((indent, line[indent:].rstrip(), number))
    pointer = [0]

    def peek():
        return entries[pointer[0]] if pointer[0] < len(entries) else None

    def node(indent):
        current = peek()
        if current is None:
            return None
        return sequence(indent) if current[1].startswith("- ") else mapping(indent)

    def sequence(indent):
        items = []
        while True:
            current = peek()
            if current is None or current[0] != indent or not current[1].startswith("- "):
                return items
            line_indent, content, number = current
            remainder = content[2:].strip()
            pointer[0] += 1
            if not remainder:
                follower = peek()
                items.append(node(follower[0]) if follower and follower[0] > indent else None)
                continue
            if SCALAR.match(remainder):
                column = line_indent + 2 + (len(content[2:]) - len(content[2:].lstrip()))
                entries.insert(pointer[0], (column, remainder, number))
                items.append(mapping(column))
                continue
            items.append(scalar(remainder, number))

    def mapping(indent):
        result = {}
        while True:
            current = peek()
            if current is None or current[0] < indent:
                return result
            if current[0] > indent:
                raise CiStructureError(f"line {current[2] + 1}: unexpected indent inside a mapping")
            _line_indent, content, number = current
            if content.startswith("- "):
                return result
            match = SCALAR.match(content)
            if not match:
                raise CiStructureError(f"line {number + 1}: {reduction(content)} is not a mapping entry")
            key, value = _unquote(match.group(1).strip()), match.group(2).strip()
            refuse(key, number, "key")
            result.setdefault("_line", number)
            result["_indent"] = indent
            pointer[0] += 1
            if value in BLOCK_INDICATORS:
                end = number + 1
                body, block_indent = [], None
                while end < len(raw):
                    line = raw[end]
                    if line.strip() and (len(line) - len(line.lstrip(" "))) <= indent:
                        break
                    if line.strip() and block_indent is None:
                        block_indent = len(line) - len(line.lstrip(" "))
                    body.append(line[block_indent:] if line.strip() and block_indent else "")
                    end += 1
                while body and not body[-1].strip():
                    body.pop()
                result[key] = "\n".join(body)
                while pointer[0] < len(entries) and entries[pointer[0]][2] < end:
                    pointer[0] += 1
                continue
            if value == "":
                follower = peek()
                if follower is None:
                    result[key] = None
                elif follower[0] > indent:
                    result[key] = node(follower[0])
                elif follower[0] == indent and follower[1].startswith("- "):
                    result[key] = sequence(indent)
                else:
                    result[key] = None
                continue
            result[key] = scalar(value, number)

    def scalar(token, number):
        refuse(token, number, "value")
        if token.startswith("["):
            if flow_depth(token) != 0 or not token.endswith("]"):
                raise CiStructureError(f"line {number + 1}: unbalanced flow sequence")
            return [_scalar_item(item, number) for item in _split_flow(token[1:-1])]
        if token.startswith("{"):
            if flow_depth(token) != 0 or not token.endswith("}"):
                raise CiStructureError(f"line {number + 1}: unbalanced flow mapping")
            return {_unquote(part.partition(":")[0].strip()): _unquote(part.partition(":")[2].strip())
                    for part in _split_flow(token[1:-1])}
        return _unquote(token)

    def refuse(token, number, what):
        for bad, name in (("<<", "merge key"), ("?", "complex key")):
            if token.strip() == bad or token.strip().startswith(bad + " "):
                raise CiStructureError(f"line {number + 1}: {name} is not attributable by this reader")
        if what == "value":
            for bad, name in (("&", "anchor"), ("*", "alias"), ("!", "tag")):
                if token.strip().startswith(bad):
                    raise CiStructureError(f"line {number + 1}: {name} is not attributable by this reader")

    if not entries:
        raise CiStructureError("the workflow is empty")
    first = entries[0][0]
    document = mapping(first)
    if pointer[0] != len(entries):
        raise CiStructureError(f"line {entries[pointer[0]][2] + 1}: the reader stopped inside the workflow")
    return document


def _scalar_item(item, label):
    for bad, name in (("&", "anchor"), ("*", "alias"), ("!", "tag")):
        if item.strip().startswith(bad):
            raise CiStructureError(f"{label}: {name}")
    return _unquote(item.strip())


def ci_clean(step_or_job):
    """A step or job the runner may skip, and therefore one that does not police anything."""
    reasons = []
    if not isinstance(step_or_job, dict):
        return ["not-a-mapping"]
    if step_or_job.get("if") not in (None, ""):
        reasons.append(f"if: {reduction(str(step_or_job.get('if')))}")
    if str(step_or_job.get("continue-on-error", "")).strip().lower() in ("true", "yes", "|", ">"):
        reasons.append("continue-on-error")
    return reasons


def ci_needs_chain(jobs, job_name, seen=None):
    """Every job this one waits for; a conditional ancestor skips the whole chain, gate included."""
    seen = set(seen or [])
    chain = []
    if job_name in seen:
        raise CiStructureError(f"ci: needs cycle at {job_name}")
    seen.add(job_name)
    needs = (jobs.get(job_name) or {}).get("needs")
    wanted = needs if isinstance(needs, list) else ([needs] if needs else [])
    for wanted_name in wanted:
        wanted_name = str(wanted_name)
        chain.append(wanted_name)
        chain.extend(ci_needs_chain(jobs, wanted_name, seen))
    return chain


def ci_policy(text):
    """Locate the step that runs this gate and decide whether anything can skip it."""
    document = ci_document(text)
    if not isinstance(document, dict):
        raise Rejected("ci: the workflow is not a mapping")
    triggers = document.get("on", document.get(True))
    if isinstance(triggers, dict):
        trigger_names = [str(name) for name in triggers if not name.startswith("_")]
    elif isinstance(triggers, list):
        trigger_names = [str(name) for name in triggers]
    elif triggers is None:
        raise Rejected("ci: the workflow declares no triggers, so nothing schedules it")
    else:
        trigger_names = [str(triggers)]
    jobs = document.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        raise Rejected("ci: no jobs mapping")
    invocations = []
    for job_name, job in sorted(jobs.items()):
        if job_name.startswith("_"):
            continue
        steps = (job or {}).get("steps") if isinstance(job, dict) else None
        if not isinstance(steps, list):
            continue
        for position, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            run = step.get("run")
            if isinstance(run, str) and CI_GATE_FILE in run:
                normalized = run.replace("\\", "/")
                if CI_GATE_PATH not in normalized:
                    raise Rejected(f"ci: the step in {job_name} names {CI_GATE_FILE} at a path that is not this gate")
                if "uses" in step:
                    raise Rejected(f"ci: {job_name} step {position} mixes uses: with the gate run, cannot attribute")
                invocations.append((job_name, position, step))
    if not invocations:
        raise Rejected("ci: no step in any job runs this gate, so cookie name drift has no automatic police")
    skippable, enforced = [], None
    for job_name, position, step in invocations:
        blockers = ci_clean(step) + ci_clean(jobs[job_name] or {})
        blockers += [f"needs {name}" for name in ci_needs_chain(jobs, job_name)
                     if ci_clean(jobs[name] or {})]
        if blockers:
            skippable.append(f"{job_name}#{position}: " + ", ".join(blockers))
        elif enforced is None:
            enforced = (job_name, position, step)
    if enforced is None:
        raise Rejected("ci: every step that runs this gate can be skipped -> " + "; ".join(skippable))
    job_name, position, step = enforced
    if not set(SILENT_ON) & set(trigger_names):
        raise Rejected(f"ci: job {job_name} runs this gate but the workflow triggers are {trigger_names}, "
                       "so a push or pull request does not reach it")
    return {"job": job_name, "stepIndex": position, "stepName": step.get("name"),
            "workflowTriggers": sorted(trigger_names), "needsChain": ci_needs_chain(jobs, job_name),
            "skippableCopies": skippable, "stepLine": step.get("_line"), "jobLine": jobs[job_name].get("_line"),
            "stepIndent": step.get("_indent", 4), "jobIndent": jobs[job_name].get("_indent", 2),
            "enforcedBy": f"job {job_name} on {sorted(set(SILENT_ON) & set(trigger_names))}",
            "limit": "structure only: this gate cannot show that GitHub ran the job, only that nothing can skip it"}


# ------------------------------------------------------------------------ executed cases and their binding
ASSERTION_STATIC = re.compile(r"import static org\.junit\.jupiter\.api\.Assertions\.(\w+);")
ASSERTION_QUALIFIED = re.compile(r"\bAssertions\.(\w+)\s*\(")
ABORT_VERBS = ("assertThrows", "assertThatExceptionOfType", "assertThatThrownBy", "catchThrowableOfType", "fail")
LIVE_VERBS = ("assertDoesNotThrow",)
EQUALITY_VERBS = ("assertEquals", "assertSame", "assertThat", "assertArrayEquals", "assertTrue", "assertFalse",
                  "assertNotNull")
TEST_METHOD = re.compile(r'(?m)^[ \t]*@Test\b[ \t]*(?:[\w.<>\[\],? ]+?[ \t]+)?(\w+)[ \t]*\([^;{]*\)'
                         r'[ \t]*(?:throws[^{;]+)?\{')
CONTEXT_TYPES = ("AnnotationConfigApplicationContext", "SpringApplicationBuilder", "GenericApplicationContext",
                 "ApplicationContextRunner")
GUARD_SYMBOL = "verifySessionCookieContract"
ASSEMBLY_SYMBOL = "identitySecurity"
BINDER_SYMBOL = "Binder"
LOADER_SYMBOLS = ("YamlPropertySourceLoader", "PropertiesPropertySourceLoader")
SURFACE_SYMBOLS = ("getResources", "PathMatchingResourcePatternResolver", "ResourcePatternResolver")


def xml_properties(path):
    """The <property> elements a surefire XML recorded, which are the run's own account of its environment."""
    root = ElementTree.parse(path).getroot()
    return {item.get("name"): item.get("value") for item in root.iter("property")}


def surefire_report(text, label):
    """Parse a surefire XML from its text, returning counts, case names, properties and captured stdout."""
    root = ElementTree.fromstring(text)
    if root.tag != "testsuite":
        raise Rejected(f"{label}: the artefact root is <{root.tag}>, not <testsuite>")
    counts = {name: int(root.get(name, "0")) for name in ("tests", "failures", "errors", "skipped")}
    names = sorted(case.get("name") for case in root if case.tag == "testcase")
    properties = {item.get("name"): item.get("value") for item in root.iter("property")}
    captured = "\n".join((node.text or "") for node in root.iter() if node.tag in ("system-out", "system-err"))
    if root.get("name") != f"{GUARD_TEST_PACKAGE}.{GUARD_TEST_CLASS}":
        raise Rejected(f"{label}: the XML reports {root.get('name')!r}, not the guard test class")
    return counts, names, properties, captured


def assertion_verbs(java):
    """The assertion names this file actually pulls in, so a rewrite to assertThat or a fully-qualified call is code."""
    found = set(ASSERTION_STATIC.findall(java.code))
    found.update(ASSERTION_QUALIFIED.findall(java.code))
    if not found:
        raise Rejected(f"{java.label}: no JUnit assertion import or qualified call remains")
    return found


def case_texts(java):
    """{case name: text} where the text is the case body plus every same-file helper it reaches, prose removed."""
    methods = java.methods()
    cases = [match.group(1) for match in TEST_METHOD.finditer(java.masked)]
    if not cases:
        raise Rejected(f"{java.label}: no @Test method survives translation and lexing")
    unresolved = sorted(set(cases) - set(methods))
    if unresolved:
        raise Rejected(f"{java.label}: @Test methods with no locatable body: {unresolved}")

    def closure(name, seen):
        if name not in methods:
            return ""
        start, end = methods[name]
        body = java.statements[start:end]
        out = [body]
        for call in re.findall(r"(?<![\w.])([a-zA-Z_]\w*)\s*\(", body):
            if call in methods and call not in seen:
                out.append(closure(call, seen | {name, call}))
        return "\n".join(out)

    return {name: closure(name, {name}) for name in cases}


def mentions(text, *tokens):
    return any(token in text for token in tokens)


def executed_roles(java):
    """Group the guard test's cases by what they drive, read from the code rather than from pinned wording.

    The tenth review's F-11: pinning copied phrases meant a parameter-order swap, a List.of rewrite, an added
    `throws Exception` or renaming an unpinned helper all went red, while renaming the *pinned* phrase went green.
    These predicates look for the collaborator a case uses (a real Spring context, Spring's Binder, a property
    source loader) and for the assertion role (abort versus does-not-throw), both taken from the file's own imports
    and followed through its own helpers, so an equivalent rewrite stays the same judgement.
    """
    verbs = assertion_verbs(java)
    abort = verbs & set(ABORT_VERBS)
    live = verbs & set(LIVE_VERBS)
    if not abort or not live:
        raise Rejected(f"{java.label}: the file imports no abort assertion or no assertDoesNotThrow, so no case can "
                       "distinguish rejecting from accepting")
    texts = case_texts(java)
    roles = {"assemblyAbort": [], "assemblyLive": [], "binderCensus": [], "binderShapes": [], "loaderAbort": [],
             "guardAbort": [], "guardLive": [], "anchorConstant": []}
    for name, text in sorted(texts.items()):
        uses_context = mentions(text, *CONTEXT_TYPES)
        uses_binder = BINDER_SYMBOL in text
        uses_loader = mentions(text, *LOADER_SYMBOLS)
        aborts = any(text.count(verb) for verb in abort)
        accepts = any(text.count(verb) for verb in live)
        if GUARD_SYMBOL in text:
            roles["guardLive" if accepts and not aborts else "guardAbort"].append(name)
        if uses_context and ASSEMBLY_SYMBOL in text:
            roles["assemblyAbort" if aborts else "assemblyLive"].append(name)
        if uses_binder and mentions(text, *SURFACE_SYMBOLS):
            roles["binderCensus"].append(name)
        elif uses_binder and uses_loader:
            roles["binderShapes"].append(name)
        elif uses_loader and aborts:
            roles["loaderAbort"].append(name)
        elif BINDER_SYMBOL not in text and not uses_loader and T03_CONFIGURATION_SYMBOL in text and \
                any(text.count(verb) for verb in EQUALITY_VERBS):
            roles["anchorConstant"].append(name)
    required = {"assemblyAbort": 1, "assemblyLive": 1, "binderCensus": 1, "binderShapes": 2, "loaderAbort": 1,
                "guardAbort": 3, "guardLive": 2, "anchorConstant": 1}
    thin = [f"{role}: found {len(roles[role])}, need at least {need}"
            for role, need in required.items() if len(roles[role]) < need]
    # A role count can stay whole while one case turns into prose, so each case is also pinned to a behaviour of its
    # own: an executed name that drives nothing is not evidence, whatever the totals say.
    witnessed = {name for group in roles.values() for name in group}
    quiet = sorted(name for name in texts if name not in witnessed)
    if quiet:
        thin.append(f"these cases execute no behaviour the gate can name: {quiet}")
    if thin:
        raise Rejected(f"{java.label}: the executed cases no longer cover every layer -> " + "; ".join(thin))
    return roles, sorted(texts), sorted(verbs)


T03_CONFIGURATION_SYMBOL = "T03Configuration"


def expected_argv():
    """The one command a recorded run may claim, as a full argv rather than a string that contains a substring."""
    return [str(MVN), "-B", "-ntp", "-o", "-f", "backend/pom.xml", "-Dmaven.repo.local=" + str(REPO),
            "-Dtest=" + GUARD_TEST_CLASS, "test"]


def normalize_argv(argv):
    return [re.sub(r"\s+", " ", str(part)).replace("\\", "/").lower().replace(str(ROOT).replace("\\", "/").lower(),
                                                                               "<root>") for part in argv]


def recorded_argv(recorded):
    command = recorded.get("command")
    if not isinstance(command, list):
        raise Rejected("binding: command is not a full argv array; the recorder must emit one so shell words are "
                       "visible instead of hidden in a joined string")
    return command


def argv_check(recorded, label):
    """Every argv element has to match the pinned run, so `echo pretend -Dtest=…` cannot impersonate the suite."""
    argv = recorded_argv(recorded)
    want, have = normalize_argv(expected_argv()), normalize_argv(argv)
    if have != want:
        raise Rejected(f"{label}: recorded command {have} is not the pinned argv {want}")
    for part in argv:
        text = str(part)
        if any(token in text for token in SHELL_TOKENS) or Path(text).name in FORBIDDEN_EXECUTABLES or \
                text in FORBIDDEN_EXECUTABLES:
            raise Rejected(f"binding: argv element {text!r} is a shell word or an executable that cannot run the suite")
    return argv


CENSUS_KINDS = ("T03-SURFACE", "T03-CENSUS", "T03-BIND")
CENSUS_LINE = re.compile(r"^(T03-SURFACE|T03-CENSUS|T03-BIND) (\S+)(?: (\S+))?$")


def census_facts(sources):
    """The census the executed case published: which layers it opened, their bytes, and what the binder resolved.

    Reading it from the surefire XML's captured stdout would work today, but that is a surefire configuration choice
    the pom owns, so the recorder copies target/t03-config-census.txt into evidence and the gate re-hashes it as one
    of the bound inputs. With no certificate the surface would be a claim the gate makes alone, so its absence is a
    rejection rather than an empty set.
    """
    if not sources.get("census"):
        raise Rejected("census: evidence/config-census.txt is missing, so nothing proves which config layers the "
                       "recorded run actually opened; rerun record_guard_binding.py")
    facts = {"surface": set(), "census": {}, "bind": {}}
    for line in sources["census"].splitlines():
        match = CENSUS_LINE.match(line.strip())
        if not match:
            if line.strip():
                raise Rejected(f"census: unparseable line {reduction(line)}")
            continue
        kind, first, second = match.groups()
        if kind == "T03-SURFACE":
            facts["surface"].add(first)
        elif kind == "T03-CENSUS":
            if not re.fullmatch(r"[0-9a-f]{64}", second or ""):
                raise Rejected(f"census: {first} carries a checksum that is not 64 hex digits")
            facts["census"][first] = second
        else:
            facts["bind"][first] = second
    if not facts["census"] or not facts["bind"] or not facts["surface"]:
        raise Rejected(f"census: the certificate carries {len(facts['surface'])} patterns, "
                       f"{len(facts['census'])} files and {len(facts['bind'])} bindings; all three are required")
    return facts


def surface_tail(label):
    """The classpath-relative name the executed census reports for a file in the declared surface."""
    return label[len("config:"):].split("/resources/")[-1]


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def absolute(*parts):
    """A path inside this checkout, from the repo root, as the recorder writes it: relative and posix."""
    return ROOT.joinpath(*[str(part).replace("\\", "/") for part in parts])


def toolchain_check(recorded, properties, label):
    """Re-hash the toolchain the record names, and cross-check it against what the run said about itself."""
    facts = {}
    jar = recorded.get("surefireJar")
    if not isinstance(jar, str) or Path(jar).is_absolute() or \
            not Path(str(jar).replace("\\", "/")).name.startswith("maven-surefire-common-") or \
            not normalize_path_text(jar).startswith(normalize_path_text(relative(REPO)) + "/"):
        raise Rejected(f"{label}: surefireJar {jar!r} is not a repo-relative maven-surefire-common jar inside the "
                       "pinned local repository, so the gate has nothing to re-hash")
    jar_path = absolute(jar)
    if jar_path.exists():
        if sha256(jar_path) != recorded.get("surefireJarSha256"):
            raise Rejected(f"{label}: surefireJarSha256 {str(recorded.get('surefireJarSha256'))[:12]}.. does not "
                           f"match {jar} on this machine")
        facts["surefireJar"] = "re-hashed here"
    else:
        facts["surefireJar"] = f"absent here ({jar}); recorded hash not verifiable on this checkout"
    jdk = recorded.get("jdk")
    if not isinstance(jdk, str) or Path(jdk).is_absolute() or \
            not normalize_path_text(jdk).startswith(".tools/"):
        raise Rejected(f"{label}: jdk {jdk!r} is not the repo-relative vendored toolchain under .tools/, so the gate "
                       "cannot re-hash it")
    launcher = next((absolute(jdk, name) for name in ("bin/java.exe", "bin/java")
                     if absolute(jdk, name).exists()), None)
    if launcher is None:
        facts["jdk"] = f"absent here ({jdk}); recorded launcher hash not verifiable on this checkout"
    else:
        if sha256(launcher) != recorded.get("jdkLauncherSha256"):
            raise Rejected(f"{label}: jdkLauncherSha256 {str(recorded.get('jdkLauncherSha256'))[:12]}.. does not "
                           f"match {relative(launcher)} on this machine")
        facts["jdk"] = "re-hashed here"
    cross = {"java.home": jdk, "localRepository": relative(REPO), "test": GUARD_TEST_CLASS,
             "basedir": relative(ROOT / "backend"), "user.dir": relative(ROOT / "backend")}
    for name, want in cross.items():
        observed = properties.get(name)
        if observed is None:
            raise Rejected(f"{label}: the surefire XML records no {name} property, so the toolchain the record names "
                           "cannot be cross-checked against the run")
        want_text = want if isinstance(want, str) and not want.startswith(str(ROOT)) else relative(want)
        if normalize_path_text(observed) != normalize_path_text(want_text) and not tail_matches(observed, want_text):
            raise Rejected(f"{label}: the run reports {name}={observed!r}, which is not the recorded {want_text!r}")
    for name, property_name in (("jdkVersion", "java.version"), ("jdkVendor", "java.vendor")):
        if recorded.get(name) != properties.get(property_name):
            raise Rejected(f"{label}: recorded {name}={recorded.get(name)!r} disagrees with the XML "
                           f"{property_name}={properties.get(property_name)!r}")
    facts["crossCheckedWithXml"] = sorted(cross)
    return facts


def binding_inputs():
    """Everything the recorded run has to be bound to, in one place the recorder imports rather than duplicates.

    The contract documents, this gate and CI are inspected sources but not inputs to the test run, so they are
    fingerprinted in the evidence instead of forcing a re-record when a document is reworded.
    """
    inputs = {key: SOURCES[key] for key in ("code", "test", "guardTest", "guardTestXml", "census", "pom")}
    inputs.update(config_paths())
    return {name: path for name, path in sorted(inputs.items())
            if path.exists() or name not in OPTIONAL_SOURCES}


def binding_check(sources, recorded, label="binding"):
    """Prove the tracked reproduction describes the bytes under review, and read the executed proof out of it.

    The load-bearing part is the surefire XML: its testcase names and counts say which cases really ran, and the roles
    the guard test's own code implies - assembly, binder, loader-abort - have to appear in that set. The recorded
    command is a full argv compared element by element, every bound input is re-hashed in both directions, and the
    provider jar and JDK launcher are re-hashed when this checkout contains them. What it still cannot prove is that a
    human ran the command: a hand-written record matching the current bytes stays possible, which is why CI re-runs
    both this gate and this test class in the same push/PR job.
    """
    if recorded is None:
        raise Rejected("binding: the recorded reproduction is missing; rerun record_guard_binding.py")
    if recorded.get("exitCode") != 0:
        raise Rejected(f"binding: recorded exitCode is {recorded.get('exitCode')!r}, not 0")
    # The binder certificate first: it judges what Spring resolved on the surface the run enumerated, and it has to be
    # the reason a hidden config shape is rejected rather than an unrelated byte check firing earlier.
    facts = census_facts(sources)
    certificate = binder_certificate(sources, facts, label)
    argv = argv_check(recorded, label)
    if recorded.get("note") != BINDING_NOTE:
        raise Rejected("binding: the note is not the recorder's wording, so the claim attached to this record is not "
                       "the one this gate knows how to check")
    inputs = binding_inputs()
    # A config layer a control added in memory belongs to the surface the record has to cover, so the expected key set
    # is the union of what this checkout enumerates and what the sources under review carry - never the disk alone.
    surface_inputs = sorted(set(inputs) | set(sources["configs"]))

    def digest(name):
        """The hash the record has to agree with, taken from the text under review rather than only from disk.

        A config layer or Java source that a control mutates in memory has to fail the same byte check that a real
        edit on disk would, otherwise the probes would be testing a face the reviewer cannot reach.
        """
        if name in sources["configs"]:
            return sha256_text(sources["configs"][name])
        if isinstance(sources.get(name), str):
            return sha256_text(sources[name])
        return sha256(inputs[name])

    recorded_hashes = recorded.get("inputSha256") or {}
    not_recorded = sorted(set(surface_inputs) - set(recorded_hashes))
    not_present = sorted(set(recorded_hashes) - set(surface_inputs))
    if not_recorded or not_present:
        raise Rejected(f"binding: the recorded input set and the surface this gate enumerates differ (not recorded "
                       f"{not_recorded}, not present here {not_present})")
    stale = [f"{name}: recorded {str(recorded_hashes.get(name))[:12]}.. != current {digest(name)[:12]}.."
             for name in surface_inputs if recorded_hashes.get(name) != digest(name)]
    if stale:
        raise Rejected("binding: recorded evidence is stale for the current bytes -> " + "; ".join(stale))
    counts, names, properties, _captured = surefire_report(sources["guardTestXml"], "guardTestXml")
    if digest("guardTestXml") != recorded.get("surefireXmlSha256"):
        raise Rejected("binding: surefireXmlSha256 is not the hash of the tracked XML")
    observed = {key: counts[key] for key in ("tests", "failures", "errors", "skipped")}
    if {key: int((recorded.get("counts") or {}).get(key, -1)) for key in observed} != observed:
        raise Rejected(f"binding: recorded counts {recorded.get('counts')!r} disagree with the XML {observed!r}")
    if names != sorted(recorded.get("testNames") or []):
        raise Rejected("binding: recorded testNames are not the XML's testcases")
    if len(names) != counts["tests"]:
        raise Rejected(f"binding: the XML declares tests={counts['tests']} but carries {len(names)} testcase elements")
    if counts["failures"] or counts["errors"] or counts["skipped"]:
        raise Rejected(f"binding: the recorded run is not clean: {observed}")
    roles, cases, verbs = executed_roles(JavaSource(sources["guardTest"], "guardTest"))
    if set(names) != set(cases):
        raise Rejected(f"binding: the run executed {sorted(set(names) ^ set(cases))} which the current guard test does "
                       "not have, or the current test has cases the recorded run never executed")
    absent = {role: [name for name in grouped if name not in set(names)] for role, grouped in roles.items()}
    missing = {role: grouped for role, grouped in absent.items() if grouped}
    if missing:
        raise Rejected(f"binding: these executed roles are absent from the recorded run -> {missing}")
    toolchain = toolchain_check(recorded, properties, label)
    return {"recordedCounts": observed, "executedCases": names, "executedRoles": roles,
            "assertionVocabulary": verbs, "recordedArgv": argv, "boundInputs": surface_inputs,
            "toolchain": toolchain, "binderCertificate": certificate,
            "limit": "byte agreement, argv equality and a re-parsed XML; not proof that a human ran the command"}


# -------------------------------------------------------------------------------- the one tokenizer, re-checked
CORPUS_SHAPES = (
    'class C {{ String s = "{}"; }}\n',
    'class C {{ /* {} */ int i = 1; }}\n',
    'class C {{ // {}\n int i = 1; }}\n',
    'class C {{ String t = """\n{}\n"""; }}\n',
    "class C {{ char c = '{}'; }}\n",
    'class C {{ String a = "{0}", u = """\n{1}\n"""; char c = \'{2}\'; }}\n',
    'class C {{ /* {0} */ String s = "{1}"; // {2}\n String u = """\n{0}\n"""; }}\n',
)
CORPUS_TOKENS = ('"', "'", "\\", "\\\\", '\\"', "\\'", '"""', "//", "/*", "*/", "{", "}", "x", APPROVED_NAME, "")
CORPUS_SEED = 20261008


def corpus(count=600):
    """A deterministic pseudo-random corpus of the shapes that desynced two lexers before."""
    state, cases = CORPUS_SEED, []
    for index in range(count):
        state = (state * 1103515245 + 12345) % (2 ** 31)
        shape = CORPUS_SHAPES[index % len(CORPUS_SHAPES)]
        slots = shape.count("{0}") + shape.count("{}") + 2 * shape.count("{1}") + shape.count("{2}")
        pieces = []
        for _ in range(max(slots, 3)):
            state = (state * 1103515245 + 12345) % (2 ** 31)
            pieces.append(CORPUS_TOKENS[(state >> 7) % len(CORPUS_TOKENS)])
        try:
            if "{0}" in shape:
                cases.append(shape.format(*pieces[:3]))
            else:
                cases.append(shape.format(pieces[0]))
        except (IndexError, KeyError):
            continue
    return cases


def views_agree(java):
    """Check the projections against the one token stream they were all built from.

    The invariant worth measuring is not "does a second lexer agree" - there is only one - but that the single stream
    covers the file without gaps and that each view only ever rewrites the ranges that stream classified. A scanner
    that dropped or doubled a character, or a projection that blanked the wrong range, fails here.
    """
    checks = []
    if not (len(java.code) == len(java.masked) == len(java.statements) == len(java.translated)):
        raise Rejected(f"{java.label}: the views are not the same length, so offsets cannot be compared")
    cursor = 0
    for kind, start, end in java.tokens:
        if start != cursor:
            raise Rejected(f"{java.label}: the token stream leaves {cursor}..{start} uncovered")
        cursor = end
    if cursor != len(java.translated):
        raise Rejected(f"{java.label}: the token stream stops at {cursor} of {len(java.translated)} characters")
    for start, end in java.comment_spans:
        if java.code[start:end].strip(" \n") != "":
            raise Rejected(f"{java.label}: comment text survived at {start}")
    for start, end in java.literal_spans:
        if any(ch not in "x\n " for ch in java.masked[start:end]):
            raise Rejected(f"{java.label}: literal content survived masking at {start}")
        if java.code[start:end] != java.translated[start:end]:
            raise Rejected(f"{java.label}: the code view rewrote literal content at {start}")
    for start, end in java.text_block_spans:
        if java.statements[start:end].strip(" \n") != "":
            raise Rejected(f"{java.label}: text-block prose is still visible in the statements view at {start}")
    return {"label": java.label, "tokens": len(java.tokens), "literals": len(java.literal_spans),
            "comments": len(java.comment_spans), "textBlocks": len(java.text_block_spans)}


def tokenizer_certificate(sources):
    """The single-lexer invariant, measured over the real sources and a deterministic corpus.

    Round nine's F-09 did not complain about a rule, it complained that two lexers existed and disagreed on 1548 of
    6000 fuzzed inputs. Here there is one scanner, so what can still be measured is whether its own projections stay
    consistent - offsets identical, masking total, prose blanking total - and that is measured on every Java source
    and on a fixed corpus rather than asserted in a comment.
    """
    checked = [views_agree(JavaSource(text, label)) for label, text in sorted(_java_sources(sources).items())]
    corpus_cases, divergences = 0, []
    for case in corpus():
        try:
            java = JavaSource(case, "corpus")
        except Uncompilable:
            continue          # javac would reject the file too; those cases are not divergences
        corpus_cases += 1
        try:
            views_agree(java)
        except Rejected as failure:
            divergences.append(f"{failure}")
    if divergences:
        raise Rejected(f"tokenizer: {len(divergences)} of {corpus_cases} corpus files disagree with themselves -> "
                       + "; ".join(divergences[:3]))
    return {"sources": checked, "corpusFiles": corpus_cases, "divergences": 0,
            "note": "one lexer, three projections; measured on the sources and on a deterministic corpus"}


def _java_sources(sources):
    return {key: sources[key] for key in ("code", "test", "guardTest")}


def contract_scheme_json(text, label):
    document = json.loads(text)
    schemes = document.get("components", {}).get("securitySchemes", {})
    root = document.get("security") or []
    if len(root) != 1 or len(root[0]) != 1:
        raise Rejected(f"{label}: root security is not one single-scheme requirement: {root!r}")
    key = next(iter(root[0]))
    if key not in schemes:
        raise Rejected(f"{label}: root security references undeclared scheme {key!r}")
    return key, schemes[key]


def _next_indent(lines, start):
    for index in range(start, len(lines)):
        line = strip_yaml_comment(lines[index])
        if line.strip():
            return len(line) - len(line.lstrip())
    return None


def contract_scheme_yaml(text, label):
    """(schemeKey, {type,in,name,...}) read from a block-YAML OpenAPI document."""
    lines = text.splitlines()
    root, schemes = None, {}
    for index, raw in enumerate(lines):
        stripped = strip_yaml_comment(raw)
        if stripped == "security:":
            indent = _next_indent(lines, index + 1)
            items = []
            for follower in lines[index + 1:]:
                body = strip_yaml_comment(follower)
                if not body.strip():
                    continue
                if len(body) - len(body.lstrip()) < indent:
                    break
                match = re.match(r"\s*-\s+(\w+):\s*(.*)$", body)
                if match:
                    items.append({match.group(1): json.loads(match.group(2).replace("'", '"') or "null")})
            root = items
        elif stripped == "  securitySchemes:":
            key = None
            for follower in lines[index + 1:]:
                body = strip_yaml_comment(follower)
                if not body.strip():
                    continue
                indent = len(body) - len(body.lstrip())
                if indent <= 2:
                    break
                if indent == 4 and body.endswith(":"):
                    key = body.strip()[:-1]
                    schemes[key] = {}
                elif key and indent == 6:
                    match = re.match(r"\s*(\w+):\s*(.+)$", body)
                    if match:
                        schemes[key][match.group(1)] = match.group(2).strip().strip("'\"")
    if not root or len(root) != 1 or len(root[0]) != 1:
        raise Rejected(f"{label}: root security is not one single-scheme requirement: {root!r}")
    name = next(iter(root[0]))
    if name not in schemes:
        raise Rejected(f"{label}: root security references undeclared scheme {name!r}")
    return name, schemes[name]


def code_constant(java):
    """The declared cookie constant, read out of a string-literal token rather than out of a text search.

    Round nine's F-04 asked that no judgement rest on a condition whose arithmetic nobody checked: the earlier version
    located the value by searching the *pattern text* inside the file, which never matches, so the clause it guarded
    could never fire. The literal-token membership below is the same claim stated against the token list.
    """
    match = re.search(r'SESSION_COOKIE_NAME\s*=\s*"([^"]+)"', java.code)
    if match is None:
        raise Rejected("code: SESSION_COOKIE_NAME is not declared with a readable string literal")
    value = java.code.find(match.group(1), match.start())
    if not any(start <= value < end for start, end in java.literal_spans):
        raise Rejected("code: the declared cookie value is not the content of a string-literal token")
    return match.group(1)


def live_literals(java):
    """The contents of ordinary string literals, which is where a declared name legitimately appears in code."""
    text = java.translated
    return [text[start:end] for start, end in java.literal_spans if not java.in_prose(start)]


def forbidden_offsets(java):
    """Where the container default sits as code: a live literal or identifier, never comment prose.

    Round nine's F-05 second half: a reviewer note that only *mentions* the default was flagged as drift. The scan
    therefore runs on the comment-free view, so prose is allowed and code is not, and the decision is made after
    JLS 3.3 translation, so JSESSION\\u0049D counts exactly as JSESSIONID does.
    """
    return [index for index in range(len(java.code)) if java.code.startswith(FORBIDDEN, index)]


def binder_certificate(sources, facts, label):
    """The effective name Spring resolved, per profile, as the executed run reported it.

    This is the answer to a text census being unable to attribute an anchor, a merge key or a `.properties` layer: the
    certificate comes out of a run that used Spring's own loaders and Binder, so the census does not have to guess.
    Both directions are checked, which is what makes one more config file a rejection instead of an invisible extra.
    """
    want = {}
    for name in sorted(sources["configs"]):
        tail = surface_tail(name)
        if tail in want:
            raise Rejected(f"{label}: two surface files map to the same classpath tail {tail!r}, so the certificate "
                           "cannot attribute them separately")
        want[tail] = name
    unseen_by_run = sorted(set(want) - set(facts["census"]))
    unseen_by_gate = sorted(set(facts["census"]) - set(want))
    if unseen_by_run or unseen_by_gate:
        raise Rejected(f"{label}: the executed census and this gate disagree about the config surface; not read by "
                       f"the run {unseen_by_run}, not in the declared surface {unseen_by_gate}")
    stale = [f"{tail}: certificate {str(facts['census'][tail])[:12]}.. != current {sha256_text(sources['configs'][want[tail]])[:12]}.."
             for tail in sorted(want) if facts["census"].get(tail) != sha256_text(sources["configs"][want[tail]])]
    if stale:
        raise Rejected(f"{label}: the census certificate is stale for the current bytes -> " + "; ".join(stale))
    expected_patterns = {f"classpath*:/{location}application*.{extension}"
                         for location in ("", "config/") for extension in CONFIG_EXTENSIONS}
    if set(facts["surface"]) != expected_patterns:
        raise Rejected(f"{label}: the executed census enumerated {sorted(set(facts['surface']))} instead of "
                       f"{sorted(expected_patterns)}, so some layer is unattributed")
    profiles = {"base"}
    for tail in want:
        stem = tail.rsplit("/", 1)[-1]
        if stem.startswith("application-"):
            profiles.add(stem[len("application-"):].split(".")[0])
    if set(facts["bind"]) != profiles:
        raise Rejected(f"{label}: the binder certificate covers profiles {sorted(set(facts['bind']))} but the surface "
                       f"declares {sorted(profiles)}")
    wrong = {name: value for name, value in sorted(facts["bind"].items()) if value != APPROVED_NAME}
    if wrong:
        raise Rejected(f"{label}: Spring's own binder resolved {wrong} at {COOKIE_PARENT}.name; the approved name is "
                       f"{APPROVED_NAME!r}")
    return {"files": sorted(want), "patterns": sorted(set(facts["surface"])), "profiles": sorted(facts["bind"]),
            "boundName": APPROVED_NAME}


def evaluate(sources):
    """Every layer in one pass: contract anchors, text census over the real surface, Java shape, execution, CI."""
    key, frozen = contract_scheme_json(sources["frozenContract"], "frozenContract")
    if frozen.get("type") != "apiKey" or frozen.get("in") != "cookie":
        raise Rejected(f"frozenContract: scheme {key!r} must be apiKey/cookie, got {frozen!r}")
    if frozen["name"] != APPROVED_NAME:
        raise Rejected(f"frozenContract: declared cookie name {frozen['name']!r} != approved {APPROVED_NAME!r}")
    additive_key, additive = contract_scheme_yaml(sources["additiveContract"], "additiveContract")
    if additive_key != key or additive != frozen:
        raise Rejected(f"additiveContract: {additive_key}={additive!r} must equal frozen {key}={frozen!r}")
    if additive.get("name") != APPROVED_NAME:
        raise Rejected(f"additiveContract: cookie name {additive.get('name')!r} != approved {APPROVED_NAME!r}")

    unread = sorted(sources["unread"])
    if unread:
        raise Rejected(f"config: {unread} look like Boot config files but carry an extension this census and the "
                       f"executed loaders do not read ({'/'.join(CONFIG_EXTENSIONS)}); neither face can attribute them")
    if BASE_LABEL not in sources["configs"]:
        raise Rejected(f"config: {BASE_LABEL} is missing from the declared surface")
    declared, unattributable = {}, {}
    for name, text in sorted(sources["configs"].items()):
        values, reasons, kind = census_config(name, text)
        declared[name] = {"kind": kind, "names": values}
        for value in values:
            if value != APPROVED_NAME:
                raise Rejected(f"config: {name} declares the session cookie name {value!r} at {COOKIE_PARENT}.name; "
                               f"the approved name is {APPROVED_NAME!r}")
        if reasons:
            unattributable[name] = reasons
    base_names = declared[BASE_LABEL]["names"]
    if len(base_names) != 1:
        raise Rejected(f"config: {BASE_LABEL} must declare {COOKIE_PARENT}.name exactly once, found {base_names!r}")

    moved = location_overrides(sources)
    if moved:
        raise Rejected("config: a location override moves the config surface outside this census, which cannot "
                       f"attribute it -> {moved}; extend the executed census to that layer instead of trusting text")

    code = JavaSource(sources["code"], "code")
    constant = code_constant(code)
    if constant != APPROVED_NAME:
        raise Rejected(f"code: constant {constant!r} != approved {APPROVED_NAME!r}")
    clause_paths = guard_clause_paths(code)
    call_site = guard_call_site(code)
    if not call_site["live"]:
        raise Rejected(f"code: the guard call is not a statement the assembly reaches -> {call_site['basis']}")
    # (the scoped walk above already required every clause and message inside the guard)

    test = JavaSource(sources["test"], "test")
    test.require_live(TEST_ASSERTION, "assertion that the runtime issues the declared cookie name via Set-Cookie",
                      test.code)
    guard_test = JavaSource(sources["guardTest"], "guardTest")
    roles, cases, verbs = executed_roles(guard_test)
    if APPROVED_NAME not in live_literals(guard_test):
        raise Rejected("guardTest: no live string literal carries the approved anchor, so the cases compare against "
                       "something other than rc.3's name")
    exempt_start, exempt_end = guard_test.methods().get(CONTAINER_DEFAULT_CASE, (0, 0))
    outside = [offset for offset in forbidden_offsets(guard_test) if not exempt_start <= offset < exempt_end]
    if outside:
        raise Rejected(f"guardTest: the container default is named in code outside {CONTAINER_DEFAULT_CASE} at "
                       f"{outside}; only the case that proves it aborts may name it")
    for needle in PROD_ATTRIBUTE_PATHS:
        if guard_test.live(re.compile(re.escape(needle)), guard_test.code) is None:
            raise Rejected(f"guardTest: the production attribute {needle} is no longer read by live code anywhere in "
                           "the file")

    recorded = json.loads(sources["binding"]) if sources.get("binding") else None
    binding = binding_check(sources, recorded)
    policy = ci_policy(sources["ci"])
    tokenizer = tokenizer_certificate(sources)
    return {"schemeKey": key, "frozenScheme": frozen, "additiveScheme": additive, "approvedName": APPROVED_NAME,
            "configFilesScanned": sorted(sources["configs"]), "textCensusCookieNames": declared,
            "textCensusUnattributable": unattributable,
            "textCensusLimit": "attributed by text: block and flow mappings, multi-line flow, comments, quoting and "
                               "case variants. Not attributed by text: anchors, merge keys, tags, block scalars and "
                               "placeholders - those files are judged by the binder certificate below, which is why "
                               "their bytes have to be in the recorded run.",
            "javaConstant": constant, "staticCallSite": call_site, "guardClausePaths": clause_paths,
            "runtimeAssertionLive": True,
            "guardTestCases": cases, "guardTestCaseRoles": roles, "assertionVocabulary": verbs,
            "unicodeEscapesTranslatedPerJls33": True, "oneTokenizerPerFile": tokenizer,
            "binding": binding, "ci": policy,
            "proofLayers": {
                "textCensus": "agreement of the contract anchors, every config declaration this census can attribute "
                              "and the Java constant, all read after JLS 3.3 translation",
                "staticStructure": "the guard call is a statement an assembly reaches, and the guard clauses are live "
                                   "code rather than prose; auxiliary to the executed proof and blind to a condition "
                                   "javac cannot fold",
                "executed": "the surefire XML of an offline run: the assembly cases really invoked the production bean "
                            "method, and the binder certificate reports the name Spring's own loaders resolved",
                "ci": "the step that runs this gate sits in a job a push or pull request reaches, and nothing can "
                      "skip it",
                "notProven": "that a human rather than a text editor produced the recorded run; that GitHub executed "
                             "the CI job; a config layer outside the recorded surface; a condition javac cannot fold"}}


# --------------------------------------------------------------------- controls: mutations applied in memory
# A control is a mutation this gate must reject; a probe is a mutation that must still be accepted. Both run against
# copies of the sources, so no controlled file is touched, and both name the check face that has to fire - a control
# that passes for an unrelated reason proves nothing.

def edited(sources, **changes):
    copy = dict(sources)
    copy.update(changes)
    return copy


def splice(text, anchor, replacement, label):
    if anchor not in text:
        raise AssertionError(f"control {label}: the anchor is no longer in the source, so the control is stale")
    return text.replace(anchor, replacement, 1)


def code_edit(sources, anchor, replacement):
    return edited(sources, code=splice(sources["code"], anchor, replacement, "code"))


def guard_edit(sources, anchor, replacement):
    return edited(sources, guardTest=splice(sources["guardTest"], anchor, replacement, "guardTest"))


def test_edit(sources, anchor, replacement):
    return edited(sources, test=splice(sources["test"], anchor, replacement, "runtime test"))


def config_edit(sources, anchor, replacement, name=None):
    """Mutate one config document in memory, leaving the tree untouched."""
    target = name or sorted(sources["configs"])[-1]
    configs = dict(sources["configs"])
    configs[target] = splice(configs[target], anchor, replacement, "config " + target)
    return edited(sources, configs=configs)


def binding_add(sources, name, text):
    document = json.loads(sources["binding"])
    document["inputSha256"][name] = sha256_text(text)
    return edited(sources, binding=json.dumps(document, indent=2) + "\n")


def config_add(sources, name, text, certify=True, binds=None, record=True):
    """Add a config layer to the in-memory surface, with a certificate and binding that know about it."""
    configs = dict(sources["configs"])
    configs[name] = text
    copy = re_certified(sources, configs=configs, binds=binds) if certify else edited(sources, configs=configs)
    return binding_add(copy, name, text) if record else copy


def binding_edit(sources, **fields):
    document = json.loads(sources["binding"])
    document.update(fields)
    return edited(sources, binding=json.dumps(document, indent=2) + "\n")


def binding_drop(sources, key):
    document = json.loads(sources["binding"])
    document["inputSha256"].pop(key, None)
    return edited(sources, binding=json.dumps(document, indent=2) + "\n")


def binding_rename(sources, old, new):
    document = json.loads(sources["binding"])
    document["inputSha256"][new] = document["inputSha256"].pop(old)
    return edited(sources, binding=json.dumps(document, indent=2) + "\n")


def binding_command(sources, argv):
    return binding_edit(sources, command=argv, surefireCommand=argv)


def xml_edit(sources, anchor, replacement):
    return edited(sources, guardTestXml=splice(sources["guardTestXml"], anchor, replacement, "surefire XML"))


def ci_edit(sources, anchor, replacement):
    return edited(sources, ci=splice(sources["ci"], anchor, replacement, "ci.yml"))


def ci_key_after(sources, anchor, added, indent=None):
    """Insert a sibling key into the mapping that owns `anchor`, at that mapping's own column."""
    lines = sources["ci"].splitlines()
    for index, line in enumerate(lines):
        if anchor in line:
            stripped = line.lstrip()
            base = len(line) - len(stripped)
            column = indent if indent is not None else base + (2 if stripped.startswith("- ") else 0)
            lines.insert(index + 1, " " * column + added)
            return edited(sources, ci="\n".join(lines) + "\n")
    raise AssertionError(f"ci control: the anchor {anchor[:48]!r} is not in ci.yml")


def ci_drop_step(sources):
    lines = [line for line in sources["ci"].splitlines()
             if "Session cookie contract agreement gate" not in line and GATE_RUN_LINE not in line]
    return edited(sources, ci="\n".join(lines) + "\n")


GATE_RUN_LINE = "run: python " + relative(SOURCES["gate"])
RUNTIME_ASSERTION_LINE = ('assertTrue(r.headers().allValues("Set-Cookie").stream().anyMatch('
                          'x->x.startsWith(T03Configuration.SESSION_COOKIE_NAME+"="))')


def sources_configs_profiles(configs):
    profiles = {"base"}
    for name in configs:
        stem = surface_tail(name).rsplit("/", 1)[-1]
        if stem.startswith("application-"):
            profiles.add(stem[len("application-"):].split(".")[0])
    return profiles


def bound_profiles(profiles, override=None):
    values = {name: APPROVED_NAME for name in sorted(profiles)}
    values.update(override or {})
    return values


def census_text(configs, surface=None, binds=None, checksums=None):
    """A self-consistent certificate, so a probe can test one face without tripping another one first."""
    patterns = sorted(surface) if surface is not None else sorted(
        f"classpath*:/{location}application*.{extension}"
        for location in ("", "config/") for extension in CONFIG_EXTENSIONS)
    lines = [f"T03-SURFACE {pattern}" for pattern in patterns]
    for name in sorted(configs):
        tail = surface_tail(name)
        digest = (checksums or {}).get(tail, sha256_text(configs[name]))
        lines.append(f"T03-CENSUS {tail} {digest}")
    for profile, value in sorted((binds if binds is not None
                                  else bound_profiles(sources_configs_profiles(configs))).items()):
        lines.append(f"T03-BIND {profile} {value}")
    return "\n".join(lines) + "\n"


def re_certified(sources, configs=None, binds=None, surface=None, checksums=None):
    configs = sources["configs"] if configs is None else configs
    return edited(sources, configs=configs,
                  census=census_text(configs, surface=surface,
                                     binds=bound_profiles(sources_configs_profiles(configs), binds),
                                     checksums=checksums))


def hidden_shape(sources, fragment, wrong_name, certify=True):
    """A cookie name carried by a shape the text census refuses to attribute: anchor plus merge key."""
    target = sorted(sources["configs"])[-1]
    configs = dict(sources["configs"])
    configs[target] = configs[target] + fragment
    return re_certified(sources, configs=configs, binds={"base": wrong_name}) if certify \
        else edited(sources, configs=configs)


MERGE_KEY_FRAGMENT = ("\nt03-anchor: &t03-anchor\n  name: " + FORBIDDEN + "\nserver:\n  servlet:\n    session:\n"
                      "    cookie:\n      <<: *t03-anchor\n")
APPROVED_MERGE_FRAGMENT = ("\nt03-anchor: &t03-anchor\n  name: " + APPROVED_NAME + "\nserver:\n  servlet:\n"
                           "    session:\n      cookie:\n        <<: *t03-anchor\n")


def empty_case(sources, name):
    """Replace one executed case's body with prose naming the same collaborators - round nine's F-04 hollowing."""
    java = JavaSource(sources["guardTest"], "guardTest")
    span = java.methods().get(name)
    if span is None:
        raise AssertionError(f"control: {name} is not a method of the guard test")
    start, end = span
    hollow = ('{\n        String script = """\n        pretend: Binder getBean assertThrows '
              + APPROVED_NAME + ' getResources\n        """;\n        assert script != null;\n    }')
    return edited(sources, guardTest=sources["guardTest"][:start] + hollow + sources["guardTest"][end:])


def rename_case(sources, old, new):
    return guard_edit(sources, "void " + old + "()", "void " + new + "()")


def constant_false_wrap(condition, brace=False):
    def mutate(sources):
        return code_edit(sources, "        verifySessionCookieContract(env);",
                         "        " + condition + (" {" if brace else "") + "\n"
                         "            verifySessionCookieContract(env);" + ("\n        }" if brace else ""))
    return mutate


def guard_profile_rename(sources):
    """Rename the profile the guard's own production branch compares against, leaving the origin rule alone."""
    return code_edit(sources, 'if(env.matchesProfiles("prod") && (', 'if(env.matchesProfiles("production") && (')


def dead_return_wrap(sources):
    return code_edit(sources, "        verifySessionCookieContract(env);",
                     "        return http.build();\n        verifySessionCookieContract(env);")


def escaped_comment_wrap(sources):
    """Wrap the call in a block comment whose delimiters are spelled with unicode escapes.

    javac translates escapes before recognising comments, so the call is commented out there; a scanner working on raw
    bytes sees no comment at all. That is round nine's F-01 fifth shape, and F-05's escape asymmetry.
    """
    return code_edit(sources, "        verifySessionCookieContract(env);",
                     "        \\u002f\\u002a verifySessionCookieContract(env); moved to the runbook \\u002a\\u002f\n")


def escaped_comment_around_note(sources):
    """Benign: an escaped comment that wraps a note, with the call left exactly where it was."""
    return code_edit(sources, "        verifySessionCookieContract(env);",
                     "        \\u002f\\u002a rc.3 names the cookie; the container default is not contract-valid "
                     "\\u002a\\u002f\n        verifySessionCookieContract(env);")


def escaped_line_comment_wrap(sources):
    """The call disappears into a line comment written with escaped slashes, and nothing else changes."""
    return code_edit(sources, "        verifySessionCookieContract(env);", "        \\u002f\\u002f deferred\n")


def in_prose_wrap(sources):
    """The call survives only as text inside a text block, which javac reads as string content."""
    return code_edit(sources, "        verifySessionCookieContract(env);",
                     '        String note = """\n            verifySessionCookieContract(env);\n        """;')


def try_finally_wrap(sources):
    """Benign: the call runs on every path, inside a try/finally."""
    return code_edit(sources, "        verifySessionCookieContract(env);",
                     "        try {\n            verifySessionCookieContract(env);\n        } finally {\n"
                     "            http.logout(c -> c.disable());\n        }")


def switch_default_wrap(sources):
    """Benign: the call sits in a switch's default branch, which the old reachability walk false-rejected."""
    return code_edit(sources, "        verifySessionCookieContract(env);",
                     "        switch (origin.length() == 0 ? 0 : 1) {\n"
                     "            default:\n                verifySessionCookieContract(env);\n        }")


def else_wrap(sources):
    """Benign: the call is the else arm of a condition, still a statement the assembly reaches."""
    return code_edit(sources, "        verifySessionCookieContract(env);",
                     "        if (origin.isEmpty()) {\n            throw new IllegalStateException(\"T03_ORIGIN: blank\");\n"
                     "        } else {\n            verifySessionCookieContract(env);\n        }")


def lambda_wrap(sources):
    """The call moves into a lambda body, so assembling the bean no longer runs it."""
    return code_edit(sources, "        verifySessionCookieContract(env);",
                     "        java.util.function.Supplier<String> deferred = () -> {\n"
                     "            verifySessionCookieContract(env);\n            return origin;\n        };")


def moved_to_other_bean(sources):
    """Benign: the call runs while a different assembled bean of the same class is created."""
    body = splice(sources["code"], "        verifySessionCookieContract(env);", "", "probe")
    anchor = "Environment env){return new AuditQuery("
    return edited(sources, code=splice(body, anchor,
                                       "Environment env){ verifySessionCookieContract(env); return new AuditQuery(",
                                       "probe"))


def renamed_container_default_case(sources):
    return rename_case(sources, CONTAINER_DEFAULT_CASE, "containerDefaultNameAbortsStartupRenamed")


APPROVED = APPROVED_NAME
WRONG = "SOME_OTHER_SESSION_COOKIE"
UNCOMPILE_ANCHOR = "    static void verifySessionCookieContract(Environment env) {"


def moved_to_dead_method(sources):
    """The call is deleted from the bean body and the guard method is renamed, so nothing assembles it."""
    copy = code_edit(sources, "        verifySessionCookieContract(env);", "")
    return edited(copy, code=copy["code"].replace("verifySessionCookieContract", "neverAssembledCheck", 2))


def lockstep_rename(sources):
    """Rename the approved cookie name everywhere at once: no file disagrees, the anchor does."""
    out = {key: sources[key].replace(APPROVED_NAME, WRONG) for key in ("code", "test", "guardTest")}
    out["configs"] = {name: text.replace(APPROVED_NAME, WRONG) for name, text in sources["configs"].items()}
    out["frozenContract"] = sources["frozenContract"].replace(APPROVED_NAME, WRONG)
    out["additiveContract"] = sources["additiveContract"].replace(APPROVED_NAME, WRONG)
    out["census"] = sources["census"].replace(APPROVED_NAME, WRONG)
    return edited(sources, **out)


def unread_probe(sources):
    """A config-shaped file with an extension neither face reads, appearing on the surface in memory only."""
    label = "config:" + relative(CONFIG_ROOTS[0] / "application.r10probe.xml")
    return edited(sources, unread=dict(sources["unread"], **{label: "<configuration/>\n"}))


def move_gate_later(sources):
    """Move the gate step after the backend step, inside the same job, without touching its content."""
    lines = sources["ci"].splitlines()
    start = next(index for index, line in enumerate(lines) if "Session cookie contract agreement gate" in line)
    block = lines[start:start + 2]
    rest = lines[:start] + lines[start + 2:]
    anchor = next(index for index, line in enumerate(rest) if "apache-maven" in line and "verify" in line)
    return edited(sources, ci="\n".join(rest[:anchor + 1] + block + rest[anchor + 1:]) + "\n")


# --------------------------------------------------------------------- the roster
# label, the claim it tests, the mutator, and the fragments that have to appear in the rejection. A control rejected
# for an unrelated reason is reported as wrong-face, because then it is not testing what it says it tests.

NEGATIVE_CONTROLS = (
    ("config-drops-cookie-name", "the resources root stops declaring the approved name at all",
     lambda s: config_edit(s, "        name: " + APPROVED_NAME + "\n", "", name=BASE_LABEL), ("config",)),
    ("config-changes-cookie-name", "the resources root declares a different name",
     lambda s: config_edit(s, "        name: " + APPROVED_NAME + "\n", "        name: " + WRONG + "\n",
                           name=BASE_LABEL), ("config",)),
    ("cookie-path-relocated-under-unrelated-parent", "the declaration moves where Boot cannot read it",
     lambda s: config_edit(s, "  servlet:\n    session:\n      cookie:\n",
                           "  management-servlet:\n    session:\n      cookie:\n", name=BASE_LABEL),
     ("config", "the census certificate")),
    ("extra-document-carries-second-name", "a second YAML document declares another name",
     lambda s: config_edit(s, "management:\n", "---\nserver:\n  servlet:\n    session:\n      cookie:\n        name: "
                              + WRONG + "\n---\nmanagement:\n", name=BASE_LABEL), ("config",)),
    ("all-profiles-override-cookie-name", "every profile layer overrides the name, prod included",
     lambda s: re_certified(s, configs={name: (text + "\nserver:\n  servlet:\n    session:\n      cookie:\n        name: "
                                                + WRONG + "\n") if "application-" in name else text
                                        for name, text in s["configs"].items()},
                            binds={"prod": WRONG}), ("config",)),
    ("flow-profile-override-cookie-name", "a flow mapping in the prod layer overrides the name",
     lambda s: re_certified(s, configs={name: (text + "\nserver: {servlet: {session: {cookie: {name: " + WRONG + "}}}}\n"
                                               if "application-prod" in name else text)
                                       for name, text in s["configs"].items()},
                            binds={"prod": WRONG}), ("config",)),
    ("case-variant-flow-override", "the same override with every key upper-cased",
     lambda s: re_certified(s, configs={name: (text + "\nSERVER: {SERVLET: {SESSION: {COOKIE: {NAME: " + WRONG + "}}}}\n"
                                               if "application-prod" in name else text)
                                       for name, text in s["configs"].items()},
                            binds={"prod": WRONG}), ("config", "Spring's own binder")),
    ("flow-base-second-name", "a flow mapping in the base layer adds a second name",
     lambda s: config_edit(s, "server:\n", "server: {servlet: {session: {cookie: {name: " + WRONG + "}}}}\n",
                           name=BASE_LABEL), ("config",)),
    ("quoted-duplicate-cookie-key", "a quoted duplicate key the loader itself would reject",
     lambda s: config_edit(s, "        name: " + APPROVED_NAME + "\n",
                           '        "name": ' + WRONG + "\n        name: " + APPROVED_NAME + "\n", name=BASE_LABEL),
     ("config", "duplicate")),
    ("anchor-hides-name-text-cannot-attribute", "an anchor and merge key carry the container default",
     lambda s: hidden_shape(s, MERGE_KEY_FRAGMENT, FORBIDDEN), ("Spring's own binder",)),
    ("merge-key-second-declaration", "a merge key re-declares the name as something else",
     lambda s: hidden_shape(s, MERGE_KEY_FRAGMENT.replace(FORBIDDEN, WRONG, 1), WRONG), ("Spring's own binder",)),
    ("properties-layer-wrong-name", "a config/application.properties layer binds the container default",
     lambda s: config_add(s, "config:" + relative(CONFIG_ROOTS[0] / "config" / "application.properties"),
                          "server.servlet.session.cookie.name=" + FORBIDDEN + "\n",
                          binds={"base": FORBIDDEN}), ("Spring's own binder", "declares the session cookie name")),
    ("config-adds-unrecorded-file", "one more config layer, absent from the recorded run",
     lambda s: config_add(s, "config:" + relative(CONFIG_ROOTS[0] / "application-local.yaml"),
                          "server:\n  servlet:\n    session:\n      cookie:\n        name: " + APPROVED_NAME + "\n",
                          certify=False, record=False), ("recorded input set", "disagree about the config surface")),
    ("config-surface-pattern-dropped", "the executed census stops enumerating one extension",
     lambda s: edited(s, census="\n".join(line for line in s["census"].splitlines()
                                          if line != "T03-SURFACE classpath*:/application*.yaml") + "\n"),
     ("enumerated",)),
    ("config-checksum-stale-in-certificate", "the certificate reports checksums for bytes that are no longer there",
     lambda s: re_certified(s, checksums={"application.yml": sha256_text("edited after the run")}),
     ("census certificate is stale",)),
    ("config-bind-profile-missing", "the binder certificate stops covering one profile",
     lambda s: edited(s, census="\n".join(line for line in s["census"].splitlines()
                                          if not line.startswith("T03-BIND prod ")) + "\n"), ("covers profiles",)),
    ("config-declares-location-override", "a location override moves the surface outside this census",
     lambda s: re_certified(s, configs={**s["configs"],
                                        BASE_LABEL: s["configs"][BASE_LABEL].replace(
                                            "server:\n", "spring.config.location: classpath:/outside/\nserver:\n", 1)}),
     ("location override",)),
    ("config-imports-optional-location", "an optional import reaches a layer the census cannot name",
     lambda s: re_certified(s, configs={**s["configs"],
                                        BASE_LABEL: s["configs"][BASE_LABEL].replace(
                                            "server:\n", "spring.config.import: optional:file:./extra.yml\nserver:\n",
                                            1)}), ("location override",)),
    ("code-declares-config-location", "a launch-time location override appears in the sources under review",
     lambda s: code_edit(s, UNCOMPILE_ANCHOR,
                         '    static final String SWITCH = "-Dspring.config.location=classpath:/outside/";\n'
                         + UNCOMPILE_ANCHOR), ("location override",)),
    ("config-unread-extension-on-surface", "a config-shaped file no face reads appears on the surface",
     unread_probe, ("look like Boot config files",)),
    ("contract-renames-cookie", "the frozen contract declares another cookie name",
     lambda s: edited(s, frozenContract=splice(s["frozenContract"], '"name": "EDITORIAL_SESSION"',
                                               '"name": "SOME_OTHER_SESSION_COOKIE"', "frozenContract")),
     ("frozenContract",)),
    ("additive-drops-scheme", "the additive contract no longer declares the scheme",
     lambda s: edited(s, additiveContract=splice(s["additiveContract"], APPROVED_NAME, WRONG, "additiveContract")),
     ("additiveContract",)),
    ("additive-scheme-extra-key", "the additive scheme gains a key the frozen one does not have",
     lambda s: edited(s, additiveContract=splice(s["additiveContract"], "      in: cookie",
                                                 "      in: cookie\n      description: divergent",
                                                 "additiveContract")), ("additiveContract",)),
    ("code-constant-drifts", "the Java constant stops matching the contract",
     lambda s: code_edit(s, 'SESSION_COOKIE_NAME="EDITORIAL_SESSION"', 'SESSION_COOKIE_NAME="' + WRONG + '"'), ("code",)),
    ("guard-call-deleted", "the assembly stops calling the guard",
     lambda s: code_edit(s, "        verifySessionCookieContract(env);", ""), ("code",)),
    ("guard-call-commented-out", "the call survives only as a comment",
     lambda s: code_edit(s, "        verifySessionCookieContract(env);", "        // verifySessionCookieContract(env);"),
     ("code",)),
    ("guard-call-moved-to-dead-method", "the call lives in a method nothing assembles",
     moved_to_dead_method, ("code",)),
    ("guard-call-in-constant-false-branch", "if (false) with no braces, which brace arithmetic used to wave through",
     constant_false_wrap("if (false)"), ("code",)),
    ("guard-call-under-boolean-false", "if (Boolean.FALSE.booleanValue()) with no braces",
     constant_false_wrap("if (Boolean.FALSE.booleanValue())"), ("code",)),
    ("guard-call-under-static-final-false", "a static final false constant guarding the call",
     lambda s: constant_false_wrap("if (NEVER)")(code_edit(s, UNCOMPILE_ANCHOR,
                                                           "    static final boolean NEVER = false;\n" + UNCOMPILE_ANCHOR)),
     ("code",)),
    ("guard-call-under-while-false", "while (false) { call }",
     constant_false_wrap("while (false)", brace=True), ("code",)),
    ("guard-call-after-unconditional-return", "a return ahead of the call, which javac rejects as unreachable",
     dead_return_wrap, ("code",)),
    ("guard-call-under-escaped-block-comment", "a block comment written with \\u002f\\u002a hides the call",
     escaped_comment_wrap, ("code",)),
    ("guard-call-under-escaped-line-comment", "a line comment written with \\u002f\\u002f replaces the call",
     escaped_line_comment_wrap, ("code",)),
    ("guard-call-inside-text-block-prose", "the call survives only inside a text block",
     in_prose_wrap, ("code",)),
    ("guard-call-moved-into-lambda", "the call moves into a lambda, so assembling the bean no longer runs it",
     lambda_wrap, ("code",)),
    ("guard-name-check-commented-out", "the name comparison is commented out",
     lambda s: code_edit(s, '        if(!SESSION_COOKIE_NAME.equals(env.getProperty("server.servlet.session.cookie.name","")))',
                         '        // if(!SESSION_COOKIE_NAME.equals(env.getProperty("server.servlet.session.cookie.name","")))'),
     ("code",)),
    ("guard-message-prefix-changed", "the rejection message no longer carries the T03_COOKIE marker",
     lambda s: code_edit(s, '"T03_COOKIE: secure production cookie required"', '"COOKIE: secure production cookie required"'),
     ("code",)),
    ("guard-line-deleted", "the prod throw statement is deleted",
     lambda s: code_edit(s, '            throw new IllegalStateException("T03_COOKIE: secure production cookie required");',
                         ""), ("code",)),
    ("guard-neutered-never-fires", "the guard becomes a method that returns before checking anything",
     lambda s: code_edit(s, UNCOMPILE_ANCHOR + "\n", UNCOMPILE_ANCHOR + "\n        return;\n"), ("code",)),
    ("guard-reads-wrong-property", "the guard compares a property Boot never reads",
     lambda s: code_edit(s, 'env.getProperty("server.servlet.session.cookie.name","")',
                         'env.getProperty("server.servlet.session.cookiee.name","")'), ("code",)),
    ("prod-check-neutered", "the prod branch stops consulting matchesProfiles",
     lambda s: code_edit(s, 'if(env.matchesProfiles("prod") && (', "if(Boolean.FALSE.booleanValue() && ("), ("code",)),
    ("prod-branch-short-circuited", "the prod branch is short-circuited with a constant false",
     lambda s: code_edit(s, 'if(env.matchesProfiles("prod") && (', 'if(false && env.matchesProfiles("prod") && ('),
     ("code",)),
    ("prod-profile-token-renamed", "the guard's production branch compares against another profile",
     guard_profile_rename, ("code",)),
    ("prod-http-only-clause-deleted", "the http-only clause disappears",
     lambda s: code_edit(s, '            || !env.getProperty("server.servlet.session.cookie.http-only",Boolean.class,true)\n',
                         ""), ("code",)),
    ("prod-same-site-clause-deleted", "the same-site clause disappears",
     lambda s: code_edit(s, '            || !"strict".equals(env.getProperty("server.servlet.session.cookie.same-site","strict"))))',
                         "            ))"), ("code",)),
    ("prod-secure-default-flipped", "the secure lookup defaults to true, so any cookie passes",
     lambda s: code_edit(s, '"server.servlet.session.cookie.secure",Boolean.class,false',
                         '"server.servlet.session.cookie.secure",Boolean.class,true'), ("code",)),
    ("message-only-in-literal", "the throw statements are replaced by strings that recite them",
     lambda s: code_edit(code_edit(s, THROW_PROD, 'String quote = "throw new IllegalStateException(\\\"T03_COOKIE: '
                         'secure production cookie required\\\");";'), THROW_NAME,
                         'String quote = "throw new IllegalStateException(\\\"T03_COOKIE: session cookie name must '
                         'equal the approved contract name \\\"+SESSION_COOKIE_NAME);";'), ("code",)),
    ("secure-clause-only-in-literal", "the secure attribute is read from no more; the name survives as a string",
     lambda s: code_edit(s, '!env.getProperty("server.servlet.session.cookie.secure",Boolean.class,false)',
                         '!"server.servlet.session.cookie.secure".isEmpty()'), ("code",)),
    ("textblock-desyncs-commented-guard", "a text block's quotes must not fake a comment that hides the call",
     lambda s: code_edit(code_edit(s, UNCOMPILE_ANCHOR, '    static String banner = """\n        " /* \n        """;\n'
                         + UNCOMPILE_ANCHOR), GUARD_CALL_SOURCE,
                         '        // verifySessionCookieContract(env); moved to a filter, this note is not a call'),
     ("code", "tokenizer")),
    ("illegal-unicode-escape", "a malformed escape javac would refuse",
     lambda s: code_edit(s, UNCOMPILE_ANCHOR, '    static final String Z = "x\\uZZZZy";\n' + UNCOMPILE_ANCHOR), ("code",)),
    ("escape-swallowing-a-closing-quote", "an escape that turns a closing quote into string content",
     lambda s: code_edit(s, UNCOMPILE_ANCHOR, '    static final String Z = "x\\u0022y";\n' + UNCOMPILE_ANCHOR),
     ("unclosed", "code")),
    ("container-default-spelled-with-escape", "the container default written JSESSION\\u0049D outside the exempt case",
     lambda s: guard_edit(s, "class T03SessionCookieGuardTest {", "class T03SessionCookieGuardTest {\n"
                              '    static final String PROBE = "JSESSION\\u0049D";'), ("guardTest",)),
    ("runtime-assertion-deleted", "the integration test stops asserting the issued cookie name",
     lambda s: test_edit(s, RUNTIME_ASSERTION_LINE, "        //"), ("test",)),
    ("runtime-assertion-commented-out", "the assertion is replaced by a trivially true one",
     lambda s: test_edit(s, RUNTIME_ASSERTION_LINE, "        assertTrue(true"), ("test",)),
    ("guard-test-hollow-container-default", "the case naming the container default is renamed, moving the exemption",
     renamed_container_default_case, ("guardTest",)),
    ("guard-test-container-default-case-hollowed", "the exempt case becomes prose, so nothing names the default there",
     lambda s: empty_case(s, CONTAINER_DEFAULT_CASE), ("guardTest",)),
    ("guard-test-prod-clauses-dropped", "the guard test stops exercising the prod cookie attributes",
     lambda s: guard_edit(s, '    private static final String SAME_SITE = "server.servlet.session.cookie.same-site";',
                          '    private static final String UNUSED_TOKEN = "nothing";'), ("guardTest",)),
    ("guard-test-anchor-literal-dropped", "the guard test no longer holds the approved name as a literal",
     lambda s: guard_edit(s, "    private static final String " + "COOKIE_ANCHOR" + " = \"" + APPROVED_NAME + "\";",
                          "    private static final String " + "COOKIE_ANCHOR" + " = WRONG;"), ("guardTest",)),
    ("file-emptied-of-executed-roles", "one executed case becomes prose, so a role loses its witness",
     lambda s: empty_case(s, "prodRejectsEachInsecureCookieAttribute"), ("guardTest", "binding")),
    ("assembly-case-hollowed", "the assembly case that must not abort becomes prose",
     lambda s: empty_case(s, "assembledIdentitySecurityStartsWithContractCookieName"), ("guardTest", "binding")),
    ("assembly-helper-hollowed", "the helper that really assembles the bean becomes prose",
     lambda s: empty_case(s, "assembleIdentitySecurity"), ("guardTest", "binding")),
    ("binder-census-stops-reading-the-surface", "the census case stops enumerating the classpath surface",
     lambda s: empty_case(s, "contractNameBindsInEveryProfileLayerThroughTheRealLoaders"), ("guardTest", "binding")),
    ("binder-shape-case-hollowed", "the flow/anchor/merge-key binder case becomes prose",
     lambda s: empty_case(s, "flowAliasAndMergeKeyShapesAreLiveToTheRealLoader"), ("guardTest", "binding")),
    ("config-directory-layer-case-hollowed", "the case proving config/ outranks the resources root becomes prose",
     lambda s: empty_case(s, "configDirectoryLayerOvertakesTheResourcesRoot"), ("guardTest", "binding")),
    ("guard-test-case-renamed", "an executed case is renamed, so the recorded XML no longer matches",
     lambda s: rename_case(s, "prodRejectsEachInsecureCookieAttribute", "prodRejectsCookieAttributesRenamed"),
     ("binding",)),
    ("ci-drops-cookie-gate", "the workflow stops running this gate", ci_drop_step, ("ci",)),
    ("ci-gate-step-continue-on-error", "the step keeps running but its failure is ignored",
     lambda s: ci_key_after(s, "Session cookie contract agreement gate", "continue-on-error: true"), ("ci",)),
    ("ci-gate-step-skippable-if", "the step is skipped for pull requests",
     lambda s: ci_key_after(s, "Session cookie contract agreement gate", "if: github.event_name == 'push'"), ("ci",)),
    ("ci-job-continue-on-error", "the whole job is marked non-blocking",
     lambda s: ci_key_after(s, "  verify:", "continue-on-error: true", indent=4), ("ci",)),
    ("ci-job-skippable-if", "the whole job only runs on main",
     lambda s: ci_key_after(s, "  verify:", "if: github.ref == 'refs/heads/main'", indent=4), ("ci",)),
    ("ci-gate-behind-skippable-ancestor", "the job is reached only through a job that can be skipped",
     lambda s: edited(s, ci=s["ci"].replace(
         "jobs:\n  verify:", "jobs:\n  holder:\n    runs-on: ubuntu-24.04\n    if: github.event_name == 'schedule'\n"
         "    steps:\n      - run: true\n  verify:\n    needs: holder\n", 1)), ("ci",)),
    ("ci-workflow-schedule-only", "the workflow is triggered by a schedule, never by push or pull request",
     lambda s: ci_edit(s, "on: [push, pull_request, workflow_dispatch]", "on:\n  schedule:\n    - cron: '17 3 * * *'"),
     ("ci",)),
    ("ci-moves-gate-to-schedule-only-job", "the gate lives in a job a push or pull request never reaches",
     lambda s: edited(s, ci=ci_drop_step(s)["ci"].rstrip("\n") +
                      "\n  nightly:\n    runs-on: ubuntu-24.04\n    if: github.event_name == 'schedule'\n    steps:\n"
                      "      - name: Session cookie contract agreement gate\n        continue-on-error: true\n"
                      "        " + GATE_RUN_LINE + "\n"), ("ci",)),
    ("ci-gate-path-renamed", "the step runs a different file",
     lambda s: ci_edit(s, relative(SOURCES["gate"]), "tests/engineering/T03/session_cookie_note.py"), ("ci",)),
    ("ci-gate-step-mixed-uses", "a step that is both uses and run, which GitHub rejects",
     lambda s: ci_key_after(s, "Session cookie contract agreement gate", "uses: actions/checkout@v4", indent=8), ("ci",)),
    ("binding-file-missing", "no recorded run at all", lambda s: edited(s, binding=None), ("binding",)),
    ("binding-exit-code-nonzero", "the recorded run did not succeed",
     lambda s: binding_edit(s, exitCode=1), ("binding",)),
    ("binding-command-not-pinned", "the recorded command is prose instead of the argv the recorder ran",
     lambda s: binding_command(s, "echo pretend -Dtest=" + GUARD_TEST_CLASS + " test"), ("binding",)),
    ("binding-command-echo-argv", "an argv that only echoes the real command",
     lambda s: binding_command(s, ["echo", str(MVN), "-B", "-ntp", "-o", "-f", "backend/pom.xml",
                                   "-Dtest=" + GUARD_TEST_CLASS, "test"]), ("binding",)),
    ("binding-command-extra-flag", "an argv with one more flag than the pinned constant table",
     lambda s: binding_command(s, expected_argv() + ["-Dsurefire.failIfNoSpecifiedTests=false"]), ("binding",)),
    ("binding-command-dtest-swapped", "an argv that names a different test class",
     lambda s: binding_command(s, [str(MVN), "-B", "-ntp", "-o", "-f", "backend/pom.xml",
                                   "-Dtest=T02ContractTest", "test"]), ("binding",)),
    ("binding-note-claim-drift", "the note stops saying exactly what the gate re-verifies",
     lambda s: binding_edit(s, note=BINDING_NOTE + " It also proves a human ran it."), ("binding",)),
    ("binding-surefire-jar-hash-wrong", "the pinned surefire jar hash does not match this machine",
     lambda s: binding_edit(s, surefireJarSha256=sha256_text("not the jar")), ("binding",)),
    ("binding-surefire-jar-path-foreign", "the surefire jar is recorded outside the pinned repository",
     lambda s: binding_edit(s, surefireJar=".tools/other/m2/some.jar"), ("binding",)),
    ("binding-jdk-hash-wrong", "the vendored launcher hash does not match this machine",
     lambda s: binding_edit(s, jdkLauncherSha256=sha256_text("not the launcher")), ("binding",)),
    ("binding-jdk-path-foreign", "the JDK is recorded as a system path the gate cannot re-hash",
     lambda s: binding_edit(s, jdk="/usr/lib/jvm/java-21"), ("binding",)),
    ("binding-jdk-not-the-run-java-home", "the recorded JDK is a different directory than the run reported",
     lambda s: binding_edit(s, jdk=".tools/t02/jdk-17.0.9"), ("binding",)),
    ("binding-jdk-version-disagrees", "the recorded JDK version disagrees with the XML property",
     lambda s: binding_edit(s, jdkVersion="17.0.9"), ("binding",)),
    ("binding-jdk-vendor-disagrees", "the recorded vendor disagrees with the XML property",
     lambda s: binding_edit(s, jdkVendor="Amazon"), ("binding",)),
    ("binding-input-key-missing", "one input is quietly left out of the record",
     lambda s: binding_drop(s, "code"), ("binding",)),
    ("binding-input-key-renamed", "an input is recorded under a name this checkout does not have",
     lambda s: binding_rename(s, "code", "backend/src/main/java/elsewhere.java"), ("binding",)),
    ("binding-config-layer-unrecorded", "a config layer the record does not mention",
     lambda s: binding_drop(s, "config:" + relative(CONFIG_ROOTS[0] / "application-mock.yml")), ("binding",)),
    ("binding-profile-stale", "the record binds a config file whose bytes changed after the run",
     lambda s: binding_edit(s, inputSha256=json.loads(s["binding"])["inputSha256"] |
                            {BASE_LABEL: sha256_text("edited after the run")}), ("stale",)),
    ("binding-testnames-fabricated", "the recorded case names are not the ones the XML reports",
     lambda s: binding_edit(s, testNames=["inventedCaseName"]), ("binding",)),
    ("binding-counts-disagree-with-xml", "the recorded counts do not match the re-parsed XML",
     lambda s: binding_edit(s, counts={"tests": 8, "failures": 0, "errors": 0, "skipped": 0}), ("binding",)),
    ("binding-xml-tests-count-inflated", "the XML declares more cases than it carries",
     lambda s: xml_edit(s, f'tests="{surefire_report(s["guardTestXml"], "xml")[0]["tests"]}"', 'tests="99"'),
     ("binding",)),
    ("binding-xml-skipped-case", "a case was skipped, so the run proves less than it says",
     lambda s: xml_edit(s, 'skipped="0"', 'skipped="1"'), ("binding",)),
    ("binding-xml-failure", "a case failed in the recorded run",
     lambda s: xml_edit(s, 'failures="0"', 'failures="1"'), ("binding",)),
    ("binding-xml-sha-wrong", "the XML hash does not match the tracked artefact",
     lambda s: binding_edit(s, surefireXmlSha256=sha256_text("other bytes")), ("binding",)),
    ("all-sources-rename-in-lockstep", "every source agrees on a name that is not the approved anchor",
     lockstep_rename, ("frozenContract", "additiveContract")),
)

# A probe is a change that must still be accepted. Without them a gate can look green only because it rejects
# everything, which is how round nine's CI anchor broke on a harmless rename.
BENIGN_PROBES = (
    ("guard-call-in-try-finally", "the call runs in a try/finally, still assembly-reachable", try_finally_wrap),
    ("guard-call-in-switch-default", "the call runs in a switch default branch", switch_default_wrap),
    ("guard-call-in-else-arm", "the call runs in an else arm", else_wrap),
    ("call-moved-to-another-assembled-bean", "the call runs while a different @Bean is assembled", moved_to_other_bean),
    ("guard-reflowed-with-whitespace", "the same statements, reformatted across lines",
     lambda s: code_edit(s, "        verifySessionCookieContract(env);",
                         "        verifySessionCookieContract( env )\n        ;")),
    ("annotation-between-bean-and-signature", "an annotation sits between @Bean and the signature",
     lambda s: code_edit(s, "    @Bean SecurityFilterChain identitySecurity(",
                         '    @org.springframework.context.annotation.Description("session cookie")\n'
                         "    @Bean SecurityFilterChain identitySecurity(")),
    ("bean-body-string-contains-brace", "a class-level text block holding braces and comment openers",
     lambda s: code_edit(s, UNCOMPILE_ANCHOR, '    static String braces = """\n        { } /* "\n        """;\n'
                         + UNCOMPILE_ANCHOR)),
    ("textblock-odd-quotes-intact", "a text block holding unbalanced quotes and a comment opener",
     lambda s: edited(s, test=splice(s["test"], "class T03PostgresTest {",
                                      'class T03PostgresTest {\n    static final String BANNER = """\n        " /* \'\n        """;',
                                      "probe"))),
    ("url-string-looks-like-comment", "a literal containing what looks like a comment opener",
     lambda s: code_edit(s, UNCOMPILE_ANCHOR,
                         '    static final String URL = "https://example.com/*not-a-comment";\n' + UNCOMPILE_ANCHOR)),
    ("char-literals-hold-quote-chars", "char literals containing quote and slash characters",
     lambda s: code_edit(s, UNCOMPILE_ANCHOR, "    static final char QUOTE = '\\\"', SLASH = '/';\n" + UNCOMPILE_ANCHOR)),
    ("block-comment-containing-slashes-and-quotes", "a block comment with quotes and a fake closer",
     lambda s: code_edit(s, UNCOMPILE_ANCHOR, '    /* a "quote" */ /* another */ /* " */\n' + UNCOMPILE_ANCHOR)),
    ("escaped-newline-inside-block-comment", "an escape sequence inside a block comment",
     lambda s: code_edit(s, UNCOMPILE_ANCHOR, "    /* note \\u000a still a comment */\n" + UNCOMPILE_ANCHOR)),
    ("escaped-comment-around-nothing", "an escaped comment that hides nothing", escaped_comment_around_note),
    ("container-default-mentioned-in-prose-only", "the container default appears only in a comment",
     lambda s: guard_edit(s, "    @Test void " + CONTAINER_DEFAULT_CASE + "()",
                          "    /** " + FORBIDDEN + " is the container default and is never approved. */\n"
                          "    @Test void " + CONTAINER_DEFAULT_CASE + "()")),
    ("location-override-mentioned-in-comment", "a config comment discussing a location override",
     lambda s: re_certified(s, configs={**s["configs"],
                                        BASE_LABEL: s["configs"][BASE_LABEL].replace(
                                            "management:\n", "# spring.config.location would move this surface; we do "
                                            "not use it\nmanagement:\n", 1)})),
    ("container-default-in-config-comment", "a config comment naming the container default",
     lambda s: re_certified(s, configs={**s["configs"],
                                        BASE_LABEL: s["configs"][BASE_LABEL].replace(
                                            "management:\n", "# " + FORBIDDEN + " is the container default.\nmanagement:\n",
                                            1)})),
    ("escape-in-identifier-is-legal", "an identifier spelled with \\u escapes, which javac accepts",
     lambda s: code_edit(s, UNCOMPILE_ANCHOR, "    static void \\u0076erifySessionCookieContract(Environment env) {")),
    ("yaml-flow-unrelated-keys", "a flow mapping that touches nothing the contract cares about",
     lambda s: re_certified(s, configs={**s["configs"],
                                        BASE_LABEL: s["configs"][BASE_LABEL].replace(
                                            "server:\n", "server: {servlet: {session: {timeout: 30m}}}\nserver:\n", 1)})),
    ("yaml-flow-approved-name", "the approved name declared through a flow mapping",
     lambda s: re_certified(s, configs={**s["configs"],
                                        BASE_LABEL: s["configs"][BASE_LABEL].replace(
                                            "      cookie:\n        name: " + APPROVED_NAME + "\n",
                                            "      cookie: {name: " + APPROVED_NAME + ", http-only: true}\n", 1)})),
    ("merge-key-carries-approved-name", "an anchor and merge key the text census cannot attribute, binding the approved name",
     lambda s: hidden_shape(s, APPROVED_MERGE_FRAGMENT, APPROVED_NAME)),
    ("comment-after-flow-value", "a comment trailing a flow value",
     lambda s: re_certified(s, configs={**s["configs"],
                                        BASE_LABEL: s["configs"][BASE_LABEL].replace(
                                            "        name: " + APPROVED_NAME + "\n",
                                            "        name: " + APPROVED_NAME + "   # rc.3 anchor\n", 1)})),
    ("block-scalar-holds-an-unrelated-name", "the wrong name inside a block scalar, which is prose not a mapping",
     lambda s: re_certified(s, configs={**s["configs"],
                                        BASE_LABEL: s["configs"][BASE_LABEL].replace(
                                            "management:\n", "t03note: |\n  server.servlet.session.cookie.name: " + WRONG
                                            + "\nmanagement:\n", 1)})),
    ("env-style-underscore-keys", "underscore-separated keys outside the cookie path",
     lambda s: re_certified(s, configs={**s["configs"],
                                        BASE_LABEL: s["configs"][BASE_LABEL].replace(
                                            "management:\n", "SERVER_SERVLET_SESSION_COOKIE_TTL: 30m\nmanagement:\n", 1)})),
    ("properties-comment-names-default", "a properties layer whose comment names the container default",
     lambda s: config_add(s, "config:" + relative(CONFIG_ROOTS[0] / "config" / "application.properties"),
                          "# " + FORBIDDEN + " is the container default, never approved\n"
                          "server.servlet.session.cookie.name=" + APPROVED_NAME + "\n",
                          binds={"base": APPROVED_NAME})),
    ("ci-invokes-gate-as-block-scalar", "the same command written as a block scalar",
     lambda s: ci_edit(s, "        " + GATE_RUN_LINE, "        run: |\n          " + GATE_RUN_LINE[5:])),
    ("ci-adds-shell-to-gate-step", "the step gains an explicit shell",
     lambda s: ci_key_after(s, "Session cookie contract agreement gate", "shell: bash")),
    ("ci-renames-gate-step", "the step is renamed, which must not break the anchor",
     lambda s: ci_edit(s, "Session cookie contract agreement gate", "Session cookie agreement gate (T03)")),
    ("ci-invokes-gate-with-python3", "the step calls python3 instead of python",
     lambda s: ci_edit(s, GATE_RUN_LINE, "run: python3 " + relative(SOURCES["gate"]))),
    ("ci-adds-unrelated-ungated-job", "another job with no skip conditions appears",
     lambda s: edited(s, ci=s["ci"].rstrip("\n") +
        "\n  docs:\n    runs-on: ubuntu-24.04\n    steps:\n      - name: Docs\n        run: python -c 'print(1)'\n")),
    ("ci-runs-gate-twice-in-second-job", "the gate also runs in another job a push reaches",
     lambda s: edited(s, ci=s["ci"].rstrip("\n") + "\n  gate-again:\n    runs-on: ubuntu-24.04\n    steps:\n"
                      "      - name: Session cookie gate, twice\n        " + GATE_RUN_LINE + "\n")),
    ("ci-adds-workflow-call-trigger", "the workflow gains a trigger but keeps push and pull_request",
     lambda s: ci_edit(s, "on: [push, pull_request, workflow_dispatch]",
                       "on: [push, pull_request, workflow_dispatch, workflow_call]")),
    ("ci-moves-gate-later-in-same-job", "the step moves after the backend step, still in the same job",
     move_gate_later),
    ("binding-note-whitespace-rewrite", "the record is re-serialised with different indentation, same content",
     lambda s: edited(s, binding=json.dumps(json.loads(s["binding"]), indent=4) + "\n")),
)


def rehash_record(sources):
    """Re-fingerprint the record for mutated sources, which is what re-running the recorder would do.

    A benign rewrite of a bound file is not a stale record in the real workflow: the reviewer re-records and CI re-runs
    the suite. Benign probes therefore re-hash before asking whether the *judgement* accepts the shape, otherwise every
    probe would be answered by the byte check and none of them would test what they say. The byte-binding face stays
    policed by the negative controls that mutate a recorded hash directly.
    """
    record = json.loads(sources["binding"])
    inputs = binding_inputs()
    # A config layer a control added in memory belongs to the surface the record has to cover, so the expected key set
    # is the union of what this checkout enumerates and what the sources under review carry - never the disk alone.
    names = sorted(set(inputs) | set(sources["configs"]))

    def digest(name):
        if name in sources["configs"]:
            return sha256_text(sources["configs"][name])
        if isinstance(sources.get(name), str):
            return sha256_text(sources[name])
        return sha256(inputs[name])

    record["inputSha256"] = {name: digest(name) for name in sorted(set(inputs) | set(sources["configs"]))}
    if isinstance(sources.get("guardTestXml"), str):
        record["surefireXmlSha256"] = sha256_text(sources["guardTestXml"])
    return edited(sources, binding=json.dumps(record, indent=2, sort_keys=True) + "\n")


# --------------------------------------------------------------------- running the roster
def run_negative_controls(sources):
    outcomes = []
    for label, claim, mutate, needles in NEGATIVE_CONTROLS:
        outcome = {"label": label, "kind": "negative", "claim": claim}
        try:
            mutated = mutate(dict(sources))
        except AssertionError as failure:
            outcome.update(verdict="broken-control", detail=str(failure)[:240])
            outcomes.append(outcome)
            continue
        try:
            # A mutant that edits a bound file would be re-recorded by whoever reviews it, so the byte check is
            # answered here and the judgement under test has to carry the rejection on its own; a mutant whose claim
            # *is* the record keeps its edited record, which is why the guard below compares binding.
            if mutated.get("binding", sources.get("binding")) == sources.get("binding"):
                mutated = rehash_record(mutated)
            evaluate(mutated)
        except AssertionError as failure:
            message = str(failure)
            outcome["detail"] = message[:300]
            outcome["verdict"] = "rejected" if any(needle in message for needle in needles) else "wrong-face"
        except Exception as failure:
            outcome.update(verdict="crashed", detail=f"{type(failure).__name__}: {failure}"[:300])
        else:
            outcome.update(verdict="accepted", detail="the gate did not notice the mutation")
        outcomes.append(outcome)
    return outcomes


def run_benign_probes(sources):
    outcomes = []
    for label, claim, mutate in BENIGN_PROBES:
        outcome = {"label": label, "kind": "benign", "claim": claim}
        try:
            mutated = mutate(dict(sources))
        except AssertionError as failure:
            outcome.update(verdict="broken-probe", detail=str(failure)[:240])
            outcomes.append(outcome)
            continue
        try:
            evaluate(rehash_record(mutated))
        except AssertionError as failure:
            outcome.update(verdict="false-red", detail=str(failure)[:300])
        except Exception as failure:
            outcome.update(verdict="crashed", detail=f"{type(failure).__name__}: {failure}"[:300])
        else:
            outcome.update(verdict="accepted", detail="")
        outcomes.append(outcome)
    return outcomes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--output", type=Path, help="write the machine-readable verdict here")
    parser.add_argument("--force", action="store_true", help="allow overwriting an existing output file")
    parser.add_argument("--skip-controls", action="store_true",
                        help="evaluate the tree only; the verdict then refuses to be PASS - this exists for debugging")
    arguments = parser.parse_args(argv)

    sources = read_sources()
    report = {"gate": relative(SOURCES["gate"]), "verdict": "CHANGES_REQUIRED",
              "evidence": {key: (sha256(path) if path.exists() else None) for key, path in SOURCES.items()}}
    try:
        report["agreement"] = evaluate(sources)
    except AssertionError as failure:
        report["reason"] = str(failure)
    else:
        if arguments.skip_controls:
            report["controls"] = {"skipped": True}
            report["reason"] = "controls were skipped, so nothing here is verified"
        else:
            outcomes = run_negative_controls(sources) + run_benign_probes(sources)
            # Each half has one right answer: a control must be rejected, a probe must be accepted. Counting both as
            # "any verdict that is not the other one's success" would let a control the gate misses look like a pass.
            bad = [item for item in outcomes
                   if item["verdict"] != ("rejected" if item["kind"] == "negative" else "accepted")]
            report["controls"] = {"total": len(outcomes), "negative": len(NEGATIVE_CONTROLS),
                                  "benign": len(BENIGN_PROBES),
                                  "negativeRejected": sum(item["verdict"] == "rejected" for item in outcomes),
                                  "benignAccepted": sum(item["verdict"] == "accepted" for item in outcomes),
                                  "failures": bad, "detail": outcomes}
            if bad:
                report["reason"] = "; ".join(f"{item['label']} -> {item['verdict']}: {item['detail'][:120]}"
                                             for item in bad[:8])
    report["verdict"] = "PASS" if "reason" not in report else "CHANGES_REQUIRED"

    if arguments.output:
        if arguments.output.exists() and not arguments.force:
            print(f"refusing to overwrite existing {arguments.output}; pass --force if that is really intended")
            return 2
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {arguments.output}")

    if report["verdict"] == "PASS":
        controls = report["controls"]
        print(f"T03 session-cookie agreement gate: PASS - approved name {APPROVED_NAME!r}; "
              f"{controls['negativeRejected']}/{controls['negative']} negative controls rejected, "
              f"{controls['benignAccepted']}/{controls['benign']} benign probes accepted")
        return 0
    print("T03 session-cookie agreement gate: CHANGES_REQUIRED - " + report.get("reason", "agreement not proven"))
    for item in (report.get("controls") or {}).get("failures", [])[:20]:
        print(f"  {item['label']} [{item['verdict']}] {item['detail'][:170]}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())




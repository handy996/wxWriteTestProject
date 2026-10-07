"""T02 round-4 control C-10: is the implementer's rebuttal to the main agent's suggested shape correct?

The third-round dispatch suggested exceptions of the form "fixed head + wildcard + fixed tail".
The implementer refused, arguing that such a rule keeps suppressing a value whose MIDDLE was changed
by one character -- the control that has to fail loudly. This measures both shapes on identical
probe files: the delivered config (full literals) vs a TEMP config using head + .{20,60} + tail.
Synthetic, TEMP only, deleted before exit.
"""
import json
import pathlib
import re
import shutil
import subprocess

ROOT = pathlib.Path(r'E:\project\codex\wxAgent')
HERE = pathlib.Path(__file__).resolve().parent
SCRATCH = pathlib.Path.home() / 'AppData/Local/Temp/t02r4/c10'
GITLEAKS = str(ROOT / '.tools/t02/gitleaks/gitleaks.exe')
CONFIG = ROOT / 'tests/engineering/T02/gitleaks.toml'

# the six R01 fingerprints are exempted by the delivered config; rebuild the refused shape from them
HEAD = 8
TAIL = 8


def build_wildcard_config(values):
    lines = ['title = "refused shape: fixed head + wildcard + fixed tail"', '[extend]',
             'useDefault = true', '', '[[allowlists]]',
             'description = "head+wildcard+tail instead of the full literal"',
             'condition = "AND"', 'regexTarget = "match"', 'regexes = [']
    for v in values:
        lines.append("  '''%s.{%d,%d}%s'''," % (v[:HEAD], len(v) - HEAD - TAIL, len(v) - HEAD - TAIL, v[-TAIL:]))
    lines += [']', '']
    return '\n'.join(lines)


def mutate(value, index):
    char = value[index]
    replacement = '1' if char != '1' else '2'
    return value[:index] + replacement + value[index + 1:]


def scan(path, config, name):
    report = SCRATCH / (name + '.json')
    if report.exists():
        report.unlink()
    proc = subprocess.run([GITLEAKS, 'dir', str(path), '--no-banner', '--redact', '--config', str(config),
                           '--report-format', 'json', '--report-path', str(report)],
                          capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=ROOT)
    findings = json.loads(report.read_text(encoding='utf-8')) if report.exists() else []
    return {'exit': proc.returncode, 'count': len(findings)}


def main():
    shutil.rmtree(SCRATCH, ignore_errors=True)
    tree = SCRATCH / 'tree'
    tree.mkdir(parents=True)
    defaults = SCRATCH / 'defaults-only.toml'
    defaults.write_text('title = "defaults"\n[extend]\nuseDefault = true\n', encoding='utf-8', newline='\n')
    text = CONFIG.read_text(encoding='utf-8')
    values = [re.sub(r'\\(.)', r'\1', e) for block in re.findall(
        r'\[\[allowlists\]\](.*?)(?=\[\[allowlists\]\]|\Z)', text, re.S)
        for e in re.findall(r"'''(.*?)'''", block, re.S)]
    long_values = [v for v in values if re.fullmatch(r'[0-9a-f]{40,}', v)]
    wildcard = SCRATCH / 'wildcard-shape.toml'
    wildcard.write_text(build_wildcard_config(long_values), encoding='utf-8', newline='\n')

    out = {'configBytes': {'delivered': len(text), 'wildcardShape': len(wildcard.read_text())},
           'cases': {}}
    for number, value in enumerate(long_values):
        mid = len(value) // 2
        cases = {'exact': value, 'middle': mutate(value, mid),
                 'first': mutate(value, 0), 'last': mutate(value, len(value) - 1)}
        row = {}
        for tag, text_value in cases.items():
            path = tree / ('v%02d-%s.txt' % (number, tag))
            path.write_text('api_key = "%s"\n' % text_value, encoding='utf-8', newline='\n')
            row[tag] = {'liveUnderDefaults': scan(path, defaults, 'd')['count'],
                        'reportedDelivered': scan(path, CONFIG, 'g')['count'],
                        'reportedWildcard': scan(path, wildcard, 'w')['count']}
        out['cases']['value-%02d' % number] = row
    # summary
    mid_hidden_by_wildcard = [k for k, r in out['cases'].items()
                              if r['middle']['liveUnderDefaults'] and not r['middle']['reportedWildcard']]
    mid_reported_delivered = [k for k, r in out['cases'].items()
                              if r['middle']['liveUnderDefaults'] and r['middle']['reportedDelivered']]
    exact_suppressed_both = [k for k, r in out['cases'].items()
                             if r['exact']['liveUnderDefaults'] and not r['exact']['reportedWildcard']
                             and not r['exact']['reportedDelivered']]
    out['verdict'] = {
        'longLiteralsTested': len(long_values),
        'exactSuppressedUnderBoth': len(exact_suppressed_both),
        'middleMutationStillHiddenUnderWildcardShape': len(mid_hidden_by_wildcard),
        'middleMutationReportedUnderDeliveredShape': len(mid_reported_delivered),
        'implementerRebuttalCorrect': bool(mid_hidden_by_wildcard) and len(mid_reported_delivered) == len(long_values),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    (HERE / 'evidence' / 'c10-wildcard-shape-comparison.json').write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    shutil.rmtree(SCRATCH, ignore_errors=True)
    print('scratch removed:', not SCRATCH.exists())
    return 0 if out['verdict']['implementerRebuttalCorrect'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

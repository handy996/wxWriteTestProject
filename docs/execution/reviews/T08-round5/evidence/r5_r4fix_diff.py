"""Diff the implementer's failed artefact against its retry, field by field.

The report claims one specific thing about `r4fix-65.json`: the first draft let
`InvalidConfigurationPropertyNameException` escape the 503 normalisation, that run exited 1, and the retry is the
same round after the fix. To check "the difference is only what it claims", compare every top-level field, the
argv/exitCode of every recorded command, and the surefire case-name sets — then print exactly which fields moved
so an unclaimed difference cannot hide in the noise.
"""
import json
import sys
from pathlib import Path

VOLATILE = {'generatedAt', 'cluster', 'commands', 'isolatedWork', 'evidenceLanding', 'testResults',
            'backendCopy', 'copiedSourceFiles', 'migrationResult', 'suites', 'totals', 'expectations',
            'inputFingerprints', 'failure', 'exitCode'}


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


a, b = load(sys.argv[1]), load(sys.argv[2])
out = {}
out['onlyInFirst'] = sorted(set(a) - set(b))
out['onlyInSecond'] = sorted(set(b) - set(a))
same, moved = [], []
for key in set(a) & set(b) - VOLATILE:
    (same if a[key] == b[key] else moved).append(key)
out['identicalNonVolatileFields'] = sorted(same)
out['movedNonVolatileFields'] = sorted(moved)

out['firstFailure'] = a.get('failure')
out['secondFailure'] = b.get('failure')
out['firstExit'] = a.get('exitCode')
out['secondExit'] = b.get('exitCode')


def command_rows(doc):
    return [(c['exitCode'], c['expected'], c['argv'][0].rsplit('\\', 1)[-1],
             ' '.join(c['argv'][1:])[:120]) for c in doc['commands']]


rows_a, rows_b = command_rows(a), command_rows(b)
out['commandCount'] = [len(rows_a), len(rows_b)]
out['commandsFirst'] = rows_a
out['commandsSecond'] = rows_b

# The failing maven command: does its output actually name the exception the report claims?
maven_fail = [c for c in a['commands'] if c['exitCode'] != 0]
out['failingCommandOutputMentions'] = []
for cmd in maven_fail:
    text = cmd['output']
    out['failingCommandOutputMentions'].append({
        'argv': ' '.join(cmd['argv'])[:160],
        'InvalidConfigurationPropertyNameException': text.count('InvalidConfigurationPropertyNameException'),
        'BUILD_FAILURE': 'BUILD FAILURE' in text,
        'TestsRun': [line for line in text.splitlines() if 'Tests run' in line][:6],
        'excerpt': text[:2500],
    })

# Case-name sets, so a changed test list between the two runs would be visible.


def cases(doc):
    return sorted({c for s in doc.get('suites', []) for c in s['cases']})


ca, cb = cases(a), cases(b)
out['casesFirst'] = len(ca)
out['casesSecond'] = len(cb)
out['casesOnlyInFirst'] = sorted(set(ca) - set(cb))
out['casesOnlyInSecond'] = sorted(set(cb) - set(ca))
out['totals'] = [a.get('totals'), b.get('totals')]
print(json.dumps(out, ensure_ascii=False, indent=2))
if len(sys.argv) > 3:
    Path(sys.argv[3]).write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
                                 newline='\n')

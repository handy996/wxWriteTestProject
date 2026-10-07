"""Round-5 reviewer: does the NEW runner gate (13) actually watch the landing rule?

Two in-memory weakenings of run_pg.py, run through the delivered 16 gates:
  R1 — the landing self-check stops refusing an unchosen landing in the controlled directory;
  R2 — the scratch default moves one level DOWN inside the controlled directory (the shape gate 13's
       equality test cannot see: CONTROLLED_EVIDENCE/r5/evidence is inside it but != it).
Expected of a watching gate: both red. Printed as JSON.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(r'E:/project/codex/wxAgent/tests/engineering/T08')))
import verify  # noqa: E402

RUNNER = str(Path(r'E:/project/codex/wxAgent/tests/engineering/T08/run_pg.py'))
SELF_CHECK = ('        if evidence_dir == CONTROLLED_EVIDENCE.resolve() and not chosen:')
DEFAULT_LANDING = ("        return (work_root / 'evidence').resolve(), False")

for anchor in (SELF_CHECK, DEFAULT_LANDING):
    if anchor not in Path(RUNNER).read_text(encoding='utf-8'):
        raise SystemExit('anchor gone, this probe is stale: ' + anchor[:60])

CASES = {
    'R1-self-check-never-fires': [(SELF_CHECK, '        if False:')],
    'R2-default-lands-inside-controlled-dir': [(DEFAULT_LANDING,
                                                "        return (CONTROLLED_EVIDENCE / 'r5' / 'evidence').resolve(), False")],
}
out = []
for label, edits in CASES.items():
    verify.MUTATIONS.clear()
    verify.MUTATIONS[RUNNER] = edits
    red, note = [], ''
    try:
        results = verify.run_checks()
        red = [name for name, ok, _d in results if not ok]
        green = f'{len(results) - len(red)}/{len(results)}'
    except SystemExit as raised:
        green, note = 'SystemExit', str(raised)[:200]
    finally:
        verify.MUTATIONS.clear()
    baseline = verify.run_checks()
    out.append({'case': label, 'green': green, 'redGates': red, 'note': note,
                'baselineGreen': f'{sum(1 for _n, ok, _d in baseline if ok)}/{len(baseline)}'})
print(json.dumps(out, ensure_ascii=False, indent=2))

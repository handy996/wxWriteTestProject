import json, os, subprocess, sys, xml.etree.ElementTree as ET
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
os.environ['PATH'] = str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd') + os.pathsep + os.environ['PATH']
if '--scan' in sys.argv:
    sys.argv = [sys.argv[0], '--gitleaks', str(ROOT/'.tools/t02/gitleaks/gitleaks.exe')]
    path = ROOT/'tests/engineering/T02/scan_secrets.py'
    source = path.read_text(encoding='utf-8').replace('tests/engineering/T02/evidence/gitleaks-findings.json', 'docs/execution/reviews/T05-round1/gitleaks-findings.json').replace("ROOT / 'tests/engineering/T02/.work'", "ROOT / 'docs/execution/reviews/T05-round1/.work'")
    exec(compile(source, str(path), 'exec'), {'__name__':'__main__', '__file__':str(path)})
else:
    records=[]
    commands = [[sys.executable, '--version'], [sys.executable, 'tests/engineering/T02/check_contracts.py'], [str(ROOT/'.tools/t02/gitleaks/gitleaks.exe'), 'version'], [sys.executable, __file__, '--scan'], ['git', '--version'], ['git', 'diff', '--check']]
    for argv in commands:
        p=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
        records.append(dict(argv=argv,exitCode=p.returncode,output=p.stdout+p.stderr))
    (HERE/'checks.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps([{'command':r['argv'], 'exitCode':r['exitCode'], 'output':r['output'][-350:]} for r in records]))
    suites=[]
    for f in (HERE/'test-results').glob('TEST-*.xml'):
        root=ET.parse(f).getroot()
        suites.append({'name':root.get('name'), 'tests':root.get('tests'), 'failures':root.get('failures'), 'errors':root.get('errors'), 'skipped':root.get('skipped'), 'cases':[{'name':t.get('name'), 'failure':t.find('failure').get('message') if t.find('failure') is not None else None} for t in root.findall('testcase')]})
    (HERE/'test-summary.json').write_text(json.dumps(suites,ensure_ascii=False,indent=2),encoding='utf-8')

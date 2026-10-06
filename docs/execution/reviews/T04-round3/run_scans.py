"""CI Gitleaks version/rules/input selection, only evidence/work destination relocated."""
import json, os, subprocess, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
if '--scan' in sys.argv:
    sys.argv=[sys.argv[0],'--gitleaks',str(ROOT/'.tools/t02/gitleaks/gitleaks.exe').replace('\\','/')]
    path=ROOT/'tests/engineering/T02/scan_secrets.py'
    source=path.read_text(encoding='utf-8').replace('tests/engineering/T02/evidence/gitleaks-findings.json','docs/execution/reviews/T04-round3/gitleaks-findings.json').replace("ROOT / 'tests/engineering/T02/.work'","ROOT / 'docs/execution/reviews/T04-round3/.work'")
    exec(compile(source,str(path),'exec'),{'__name__':'__main__','__file__':str(path)})
else:
    logs=[]
    for command in [[str(ROOT/'.tools/t02/gitleaks/gitleaks.exe'),'version'],[sys.executable,__file__,'--scan'],['git','diff','--check'],['rg','-n','RequestMapping|GetMapping|storage/objects|SignedUrl.verify|Scheduled|cleanupOrphans','backend/src/main/java']]:
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),timeout=180)
        logs.append(dict(argv=command,exitCode=result.returncode,output=result.stdout+result.stderr))
    (HERE/'scans.json').write_text(json.dumps(logs,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps([dict(exitCode=x['exitCode'],command=x['argv'][0]) for x in logs]))


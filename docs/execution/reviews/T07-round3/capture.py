from pathlib import Path
import hashlib,json,subprocess,os
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
os.environ['PATH']=str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd')+os.pathsep+os.environ['PATH']
paths=[p.decode() for p in subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).split(b'\0') if p]
rows=[{'path':p,'sha256':hashlib.sha256((ROOT/p).read_bytes()).hexdigest()} for p in paths if (ROOT/p).is_file()]
record={'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'integrationBase':'5413cf4','trackedFiles':rows,'diffFiles':subprocess.check_output(['git','diff','--name-only','5413cf4','HEAD'],cwd=ROOT,text=True).splitlines()}
out=HERE/'input-snapshot.json';assert not out.exists();out.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'head':record['head'],'trackedFiles':len(rows),'diffFiles':len(record['diffFiles'])}))

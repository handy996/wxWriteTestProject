import json, re, shutil, socket, subprocess, xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
summary={'runs':[],'cleanup':[]}
base=(HERE/'.work').resolve()
for name in ['current','host-current','upgrade']:
    e=json.loads((HERE/'evidence'/f'{name}.json').read_text(encoding='utf-8'))
    suites=[]
    for p in (HERE/'evidence'/f'{name}-test-results').glob('TEST-*.xml'):
        root=ET.parse(p).getroot()
        suites.append({k:root.get(k) for k in ['name','tests','failures','errors','skipped']}|{'cases':[t.get('name') for t in root.findall('testcase')]})
    summary['runs'].append({'name':name,'exitCode':e['exitCode'],'suites':suites})
    work=(ROOT/e['isolatedWork']).resolve()
    assert work.parent==base and re.fullmatch('[0-9a-f]{32}',work.name)
    argv=[str(ROOT/'.tools/t02/postgresql-full/pgsql/bin/pg_ctl.exe'),'-D',str(work/'data'),'status']
    p=subprocess.run(argv,capture_output=True,text=True,encoding='utf-8',errors='replace')
    assert p.returncode==3, 'Cluster must be stopped before cleanup'
    record={'argv':argv,'exitCode':p.returncode,'output':p.stdout+p.stderr}
    if name!='current':
        cmd=next(c['argv'] for c in e['commands'] if '-o' in c['argv'])
        port=int(re.search(r'-p (\d+)',cmd[cmd.index('-o')+1]).group(1))
        with socket.socket() as sock:sock.bind(('127.0.0.1',port))
        record['port']=port;record['portAvailable']=True
    shutil.rmtree(work)
    record['removedOnlyOwnedPath']=str(work)
    summary['cleanup'].append(record)
deps=(base/'schema-tools').resolve()
assert deps.parent==base and deps.name=='schema-tools'
if deps.exists():shutil.rmtree(deps)
summary['cleanup'].append({'removedOnlyOwnedPath':str(deps)})
summary['gitleaks']=[{'file':r['File'],'line':r['StartLine'],'rule':r['RuleID']} for r in json.loads((HERE/'gitleaks-findings.json').read_text(encoding='utf-8'))]
summary['frozenFileVerification']=json.loads((HERE/'checks.json').read_text(encoding='utf-8'))[1]
summary['reviewBeforeFiles']=len(json.loads((HERE/'before.json').read_text(encoding='utf-8'))['files'])
(HERE/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'files':summary['reviewBeforeFiles'],'runs':[{'name':r['name'],'exit':r['exitCode'],'tests':sum(int(x['tests']) for x in r['suites']),'failures':sum(int(x['failures']) for x in r['suites'])} for r in summary['runs']],'gitleaks':len(summary['gitleaks'])}))

import json, re, shutil, socket, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
base=(HERE/'.work').resolve()
owned=['64f7940c84f945468bc4429297430095','c806284201024e218a9e457c24b0d9a1','015005125cce40fa8e95bf0f673907cc']
records=[]
for i,name in enumerate(owned):
    work=(base/name).resolve()
    assert work.parent==base and re.fullmatch('[0-9a-f]{32}',name)
    if not work.exists(): continue
    test=work/'backend/src/test/java/com/example/editorial/editorial/skill/T05PostgresTest.java'
    if test.exists():
        (HERE/'executed-tests').mkdir(exist_ok=True)
        shutil.copyfile(test,HERE/'executed-tests'/f'{i}-T05PostgresTest.java')
    argv=[str(ROOT/'.tools/t02/postgresql-full/pgsql/bin/pg_ctl.exe'),'-D',str(work/'data'),'status']
    p=subprocess.run(argv,capture_output=True,text=True,encoding='utf-8',errors='replace')
    records.append({'argv':argv,'exitCode':p.returncode,'output':p.stdout+p.stderr})
    assert p.returncode==3, 'Refuse cleanup: cluster not confirmed stopped'
    shutil.rmtree(work)
    records[-1]['removedOnlyOwnedDirectory']=str(work)
for name in ['initial-integration','integration']:
    e=json.loads((HERE/'evidence'/f'{name}.json').read_text(encoding='utf-8'))
    cmd=next(c for c in e['commands'] if '-o' in c['argv'])
    port=int(re.search(r'-p (\d+)',cmd['argv'][cmd['argv'].index('-o')+1]).group(1))
    with socket.socket() as s: s.bind(('127.0.0.1',port))
    records.append({'port':port,'canBindAfterStop':True})
(HERE/'cleanup.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
print('Three owned directories removed; both PostgreSQL ports can be bound again.')

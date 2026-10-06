"""Record reviewer test results and end-of-review input integrity without modifying delivery."""
from pathlib import Path
import hashlib,json,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[4]; HERE=Path(__file__).resolve().parent
snapshot=json.loads((HERE/'input-snapshot.json').read_text(encoding='utf-8'))
def changed(rows):
    return [r['path'] for r in rows if not (ROOT/r['path']).is_file() or hashlib.sha256((ROOT/r['path']).read_bytes()).hexdigest()!=r['sha256']]
integrity=[{'scope':key,'count':len(snapshot[key]),'changed':changed(snapshot[key])} for key in ['baseline','t06','reviewedFiles']]
runs=[]
for name in ['author-tests','review-regressions','upgrade']:
    r=json.loads((HERE/'evidence'/(name+'.json')).read_text(encoding='utf-8'))
    totals={k:0 for k in ['tests','failures','errors','skipped']}; cases=[]
    for file in sorted((ROOT/r['testResults']).glob('TEST-*.xml')):
        suite=ET.parse(file).getroot()
        for k in totals:totals[k]+=int(suite.attrib[k])
        for case in suite.findall('testcase'):
            failure=case.find('failure')
            if failure is not None:cases.append({'name':case.attrib['name'],'message':failure.attrib.get('message','')})
    last=r['commands'][-1]
    stopped=last['argv'][-1]=='stop' and last['exitCode']==0
    assert stopped, name
    runs.append({'name':name,'exitCode':r['exitCode'],'totals':totals,'failedCases':cases,'databaseStopped':stopped})
checks=json.loads((HERE/'evidence/checks.json').read_text(encoding='utf-8'))
record={'conclusion':'CHANGES_REQUIRED','openFindings':['T07-R01','T07-R02'],'contractGap':'CR-T07-01','integrity':integrity,'runs':runs,'basicCheckFailures':checks['failures'],'newSecretFindings':checks['secretScan']['newFindings']}
assert all(not x['changed'] for x in integrity)
assert runs[0]['totals']=={'tests':67,'failures':0,'errors':0,'skipped':0}
assert runs[1]['totals']=={'tests':2,'failures':2,'errors':0,'skipped':0}
assert runs[2]['totals']=={'tests':1,'failures':0,'errors':0,'skipped':0}
assert not checks['failures']
(HERE/'summary.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(record,ensure_ascii=False))

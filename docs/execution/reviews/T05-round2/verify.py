import copy, importlib.metadata, json, os, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
os.environ['PATH']=str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd')+os.pathsep+os.environ['PATH']
if '--scan' in sys.argv:
    sys.argv=[sys.argv[0],'--gitleaks',str(ROOT/'.tools/t02/gitleaks/gitleaks.exe')]
    path=ROOT/'tests/engineering/T02/scan_secrets.py'
    source=path.read_text(encoding='utf-8').replace('tests/engineering/T02/evidence/gitleaks-findings.json','docs/execution/reviews/T05-round2/gitleaks-findings.json').replace("ROOT / 'tests/engineering/T02/.work'", "ROOT / 'docs/execution/reviews/T05-round2/.work'")
    exec(compile(source,str(path),'exec'),{'__name__':'__main__','__file__':str(path)})
else:
    results=[]
    for argv in [[sys.executable,'--version'],[sys.executable,'tests/engineering/T02/check_contracts.py'],[str(ROOT/'.tools/t02/gitleaks/gitleaks.exe'),'version'],[sys.executable,__file__,'--scan'],['git','diff','--check']]:
        p=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
        results.append({'argv':argv,'exitCode':p.returncode,'output':p.stdout+p.stderr})
    (HERE/'checks.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps([{'command':r['argv'],'exitCode':r['exitCode']} for r in results]))
    sys.path.insert(0,str(HERE/'.work/schema-tools'))
    import jsonschema
    assert importlib.metadata.version('jsonschema')=='4.26.0'
    schema=json.loads((ROOT/'docs/schemas/editorial.schema.json').read_text(encoding='utf-8'))
    samples=json.loads((HERE/'model-samples.json').read_text(encoding='utf-8'))
    records=[]
    for name,sample in samples.items():
        validator=jsonschema.Draft202012Validator({'$ref':'#/$defs/'+name,'$defs':schema['$defs']},format_checker=jsonschema.FormatChecker())
        errors=list(validator.iter_errors(sample))
        record={'name':name,'errors':[e.message for e in errors],'negativeCases':[]}
        assert not errors, record
        for field in schema['$defs'][name]['required']:
            bad=copy.deepcopy(sample); del bad[field]
            failures=list(validator.iter_errors(bad))
            assert any(e.validator=='required' and field in e.message for e in failures)
            record['negativeCases'].append({'missing':field,'rejectedByRequired':True})
        bad=copy.deepcopy(sample);bad['meta']={}
        assert any(e.validator=='additionalProperties' for e in validator.iter_errors(bad))
        record['serverWrapperRejected']=True
        records.append(record)
    (HERE/'standard-schema.json').write_text(json.dumps({'version':importlib.metadata.version('jsonschema'),'samples':records},ensure_ascii=False,indent=2),encoding='utf-8')
    print('Four actual fixed outputs and required-field/wrapper negative cases verified with pinned jsonschema 4.26.0')

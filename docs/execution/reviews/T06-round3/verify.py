from pathlib import Path
HERE=Path(__file__).resolve().parent
source=(HERE.parent/'T06-round1/verify.py').read_text(encoding='utf-8')
source=source.replace('T06-round1','T06-round3').replace('author-tests-host','current-host')
source=source.replace('ReviewArticleAstTest','ReviewEmphasisPunctuationTest')
source=source.replace('evidence/delivery-checks.json','evidence/revision-v2-final-checks.json')
source=source.replace('    delivery = json.loads',"    baseline = {item['path']:item['sha256'] for item in baseline}\n    delivery = json.loads")
exec(compile(source,'round3-checks','exec'),{'__file__':__file__,'__name__':'__main__'})

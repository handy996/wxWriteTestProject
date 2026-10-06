from pathlib import Path
HERE=Path(__file__).resolve().parent
source=(HERE.parent/'T06-round2/finish.py').read_text(encoding='utf-8')
source=source.replace("['current-host','upgrade-host']", "['current-host']")
source=source.replace('ReviewNestedClosureTest','ReviewEmphasisPunctuationTest')
exec(compile(source,'round3-finish','exec'),{'__file__':__file__,'__name__':'__main__'})

from pathlib import Path
HERE=Path(__file__).resolve().parent
source=(HERE.parent/'T06-round3/capture.py').read_text(encoding='utf-8')
source=source.replace('for round in [1,2]:','for round in [1,2,3]:')
source=source.replace('revision-v2-','revision-v3-')
source=source.replace('T06-round2/reviewed-files.json','T06-round3/reviewed-files.json')
source=source.replace('changesSinceRound2','changesSinceRound3')
exec(compile(source,'round4-capture','exec'),{'__file__':__file__,'__name__':'__main__'})

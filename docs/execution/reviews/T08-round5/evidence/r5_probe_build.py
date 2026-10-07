"""Round-5 reviewer: compile and run R5Probe.java against the classes MY OWN isolated round produced.

Nothing here runs ``mvn`` and nothing writes into the repository's ``backend/target``: the classpath is the
throw-away copy under ``%TEMP%\\t08r5\\workroot\\<run>\\backend\\target\\classes`` (built by my own ``run_pg.py``
round, not by a gutted one), plus jars from the read-only offline ``.tools/t02/m2`` repository. Output is captured
as bytes and decoded UTF-8-then-GBK, because ``text=True`` dies on this host's GBK console.
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(r'E:/project/codex/wxAgent')
JDK = REPO / '.tools/t02/jdk-21.0.12.1+1'
WORK = Path(sys.argv[1]) if len(sys.argv) > 1 else None
EVIDENCE = REPO / 'docs/execution/reviews/T08-round5/evidence'
assert WORK is not None and WORK.is_dir(), 'usage: r5_probe_build.py <absolute reviewer work root>'


def decode(raw):
    for codec in ('utf-8', 'gbk', 'cp936'):
        try:
            return raw.decode(codec)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', 'replace')


def say(text):
    sys.stdout.write(text.encode('ascii', 'backslashreplace').decode('ascii') + '\n')
    sys.stdout.flush()


hits = sorted(WORK.rglob('backend/target/classes/com/example/editorial/cost/BudgetPolicyConfig.class'),
              key=lambda p: p.stat().st_mtime, reverse=True)
if not hits:
    raise SystemExit(f'no compiled cost classes under {WORK}')
classes = hits[0].parents[4]  # .../backend/target/classes
say('classes=' + str(classes))

wanted = ['spring-core-*.jar', 'spring-boot-3*.jar', 'spring-context-*.jar', 'spring-beans-*.jar',
          'spring-jcl-*.jar', 'snakeyaml-2*.jar', 'spring-boot-autoconfigure-*.jar']
jars = []
for pattern in wanted:
    found = sorted((REPO / '.tools/t02/m2').rglob(pattern))
    if not found:
        raise SystemExit(f'missing jar for {pattern}')
    jars.append(str(found[-1]))
cp = ';'.join([str(classes)] + jars)
outdir = WORK / 'probe-classes'
outdir.mkdir(parents=True, exist_ok=True)

build = subprocess.run([str(JDK / 'bin/javac.exe'), '-encoding', 'UTF-8', '-cp', cp, '-d', str(outdir),
                        str(EVIDENCE / 'R5Probe.java')], capture_output=True)
say('javac exit ' + str(build.returncode))
log = 'classes=' + str(classes) + '\njars=' + ';'.join(Path(j).name for j in jars) + '\n' \
      + decode(build.stdout) + decode(build.stderr)
if build.returncode:
    (EVIDENCE / 'r5-probe-javac.log').write_text(log, encoding='utf-8', newline='\n')
    say(log[:4000])
    raise SystemExit(1)

run = subprocess.run([str(JDK / 'bin/java.exe'), '-cp', cp + ';' + str(outdir), 'R5Probe'], capture_output=True)
text, err = decode(run.stdout), decode(run.stderr)
say('java exit ' + str(run.returncode))
say(text)
if err.strip():
    say('STDERR: ' + err[:1500])
(EVIDENCE / 'r5-behaviour-probe.txt').write_text(
    log + '\njava exit ' + str(run.returncode) + '\n\n' + text + ('\nSTDERR:\n' + err if err.strip() else ''),
    encoding='utf-8', newline='\n')

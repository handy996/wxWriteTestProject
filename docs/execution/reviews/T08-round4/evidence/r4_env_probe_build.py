"""Round-4 reviewer: compile + run R4EnvProbe.java against the reviewer's isolated build output.

Classpath = the compiled classes of the copy the reviewer already built under %TEMP%\\t08r4 (never the repo's
backend/target) + every jar in the vendored .tools/t02/m2 repository. Writes only under %TEMP%\\t08r4 plus the
transcript in this review directory; nothing in the repository's controlled sources is touched.
"""
import subprocess
from pathlib import Path

REPO = Path(r"E:/project/codex/wxAgent")
SCRATCH = Path(r"C:/Users/eie04/AppData/Local/Temp/t08r4")
JDK = REPO / ".tools/t02/jdk-21.0.12.1+1/bin"
M2 = REPO / ".tools/t02/m2"
EVIDENCE = REPO / "docs/execution/reviews/T08-round4/evidence"
LOG = SCRATCH / "envprobe-build.log"
lines = []


def say(text: str) -> None:
    lines.append(str(text))
    LOG.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


jars = [p for p in M2.rglob("*.jar") if not any(x in p.name for x in ("-sources", "-javadoc"))]
built = sorted(SCRATCH.glob("scratch/.work/*/backend/target/classes"))
if not built:
    say("NO COMPILED CLASSES in the reviewer scratch copy; run r4_probe_runner.py first")
    raise SystemExit(2)
classes = built[-1]
cp = [str(classes)] + [str(p) for p in jars]
out = SCRATCH / "envprobe-classes"
out.mkdir(exist_ok=True)
argfile = SCRATCH / "envprobe-cp.txt"
argfile.write_text('-cp "' + ";".join(p.replace("\\", "/") for p in cp) + '"\n', encoding="utf-8")

say("jars on classpath: " + str(len(jars)) + " ; classes: " + classes.as_posix())
compile_result = subprocess.run([str(JDK / "javac.exe"), "-nowarn", "-encoding", "UTF-8", "@" + str(argfile),
                                 "-d", str(out), str(EVIDENCE / "R4EnvProbe.java")],
                                capture_output=True)
say("javac exit=" + str(compile_result.returncode))
say("--- javac output ---")
say(compile_result.stdout.decode("utf-8", errors="replace") + compile_result.stderr.decode("utf-8",
                                                                                           errors="replace"))
if compile_result.returncode:
    raise SystemExit(compile_result.returncode)
run_result = subprocess.run([str(JDK / "java.exe"), "-Dfile.encoding=UTF-8", "-cp",
                             str(out) + ";" + ";".join(cp), "R4EnvProbe"], capture_output=True)
say("java exit=" + str(run_result.returncode))
stdout = run_result.stdout.decode("utf-8", errors="replace")
say(stdout)
stderr = run_result.stderr.decode("utf-8", errors="replace")
if stderr.strip():
    say("--- java stderr ---")
    say(stderr[:3000])
(EVIDENCE / "r4-envprobe-transcript.txt").write_text(stdout, encoding="utf-8", newline="\n")
say("transcript written to " + (EVIDENCE / "r4-envprobe-transcript.txt").as_posix())
raise SystemExit(run_result.returncode)

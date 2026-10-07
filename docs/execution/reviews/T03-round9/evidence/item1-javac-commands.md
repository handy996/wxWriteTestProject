# javac / java command lines and exit codes (JDK 21.0.12.1+1, repo-local .tools/t02)

## s1-if-false-unbraced
```
$ E:\project\codex\wxAgent\.tools\t02\jdk-21.0.12.1+1\bin\javac.exe -J-Duser.language=en -J-Duser.country=US -d C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s1-if-false-unbraced\out C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s1-if-false-unbraced\probe\Shape.java
exit 0
$ E:\project\codex\wxAgent\.tools\t02\jdk-21.0.12.1+1\bin\java.exe -cp C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s1-if-false-unbraced\out probe.Shape
exit 0  stdout: GUARD_RAN=false note=NONE
guard executes: False
```

## s2-if-false-braced
```
$ E:\project\codex\wxAgent\.tools\t02\jdk-21.0.12.1+1\bin\javac.exe -J-Duser.language=en -J-Duser.country=US -d C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s2-if-false-braced\out C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s2-if-false-braced\probe\Shape.java
exit 0
$ E:\project\codex\wxAgent\.tools\t02\jdk-21.0.12.1+1\bin\java.exe -cp C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s2-if-false-braced\out probe.Shape
exit 0  stdout: GUARD_RAN=false note=NONE
guard executes: False
```

## s3-boolean-false-unbraced
```
$ E:\project\codex\wxAgent\.tools\t02\jdk-21.0.12.1+1\bin\javac.exe -J-Duser.language=en -J-Duser.country=US -d C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s3-boolean-false-unbraced\out C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s3-boolean-false-unbraced\probe\Shape.java
exit 0
$ E:\project\codex\wxAgent\.tools\t02\jdk-21.0.12.1+1\bin\java.exe -cp C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s3-boolean-false-unbraced\out probe.Shape
exit 0  stdout: GUARD_RAN=false note=NONE
guard executes: False
```

## s4-static-final-false-unbraced
```
$ E:\project\codex\wxAgent\.tools\t02\jdk-21.0.12.1+1\bin\javac.exe -J-Duser.language=en -J-Duser.country=US -d C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s4-static-final-false-unbraced\out C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s4-static-final-false-unbraced\probe\Shape.java
exit 0
$ E:\project\codex\wxAgent\.tools\t02\jdk-21.0.12.1+1\bin\java.exe -cp C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s4-static-final-false-unbraced\out probe.Shape
exit 0  stdout: GUARD_RAN=false note=NONE
guard executes: False
```

## s5-while-false-unbraced
```
$ E:\project\codex\wxAgent\.tools\t02\jdk-21.0.12.1+1\bin\javac.exe -J-Duser.language=en -J-Duser.country=US -d C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s5-while-false-unbraced\out C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s5-while-false-unbraced\probe\Shape.java
exit 1  stderr: C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s5-while-false-unbraced\probe\Shape.java:14: error: unreachable statement guard(); ^ 1 error
guard executes: n/a (file does not compile)
```

## s6-return-ahead-of-call
```
$ E:\project\codex\wxAgent\.tools\t02\jdk-21.0.12.1+1\bin\javac.exe -J-Duser.language=en -J-Duser.country=US -d C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s6-return-ahead-of-call\out C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s6-return-ahead-of-call\probe\Shape.java
exit 0
$ E:\project\codex\wxAgent\.tools\t02\jdk-21.0.12.1+1\bin\java.exe -cp C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s6-return-ahead-of-call\out probe.Shape
exit 0  stdout: GUARD_RAN=false note=NONE
guard executes: False
```

## s7-runtime-always-false-test
```
$ E:\project\codex\wxAgent\.tools\t02\jdk-21.0.12.1+1\bin\javac.exe -J-Duser.language=en -J-Duser.country=US -d C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s7-runtime-always-false-test\out C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s7-runtime-always-false-test\probe\Shape.java
exit 0
$ E:\project\codex\wxAgent\.tools\t02\jdk-21.0.12.1+1\bin\java.exe -cp C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s7-runtime-always-false-test\out probe.Shape
exit 0  stdout: GUARD_RAN=false note=NONE
guard executes: False
```

## s8-for-loop
```
$ E:\project\codex\wxAgent\.tools\t02\jdk-21.0.12.1+1\bin\javac.exe -J-Duser.language=en -J-Duser.country=US -d C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s8-for-loop\out C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s8-for-loop\probe\Shape.java
exit 0
$ E:\project\codex\wxAgent\.tools\t02\jdk-21.0.12.1+1\bin\java.exe -cp C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s8-for-loop\out probe.Shape
exit 0  stdout: GUARD_RAN=true note=NONE
guard executes: True
```

## s9-try-finally
```
$ E:\project\codex\wxAgent\.tools\t02\jdk-21.0.12.1+1\bin\javac.exe -J-Duser.language=en -J-Duser.country=US -d C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s9-try-finally\out C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s9-try-finally\probe\Shape.java
exit 0
$ E:\project\codex\wxAgent\.tools\t02\jdk-21.0.12.1+1\bin\java.exe -cp C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s9-try-finally\out probe.Shape
exit 0  stdout: GUARD_RAN=true note=NONE
guard executes: True
```

## s10-switch-default
```
$ E:\project\codex\wxAgent\.tools\t02\jdk-21.0.12.1+1\bin\javac.exe -J-Duser.language=en -J-Duser.country=US -d C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s10-switch-default\out C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s10-switch-default\probe\Shape.java
exit 0
$ E:\project\codex\wxAgent\.tools\t02\jdk-21.0.12.1+1\bin\java.exe -cp C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s10-switch-default\out probe.Shape
exit 0  stdout: GUARD_RAN=true note=NONE
guard executes: True
```

## s11-else-of-real-condition
```
$ E:\project\codex\wxAgent\.tools\t02\jdk-21.0.12.1+1\bin\javac.exe -J-Duser.language=en -J-Duser.country=US -d C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s11-else-of-real-condition\out C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s11-else-of-real-condition\probe\Shape.java
exit 0
$ E:\project\codex\wxAgent\.tools\t02\jdk-21.0.12.1+1\bin\java.exe -cp C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s11-else-of-real-condition\out probe.Shape
exit 0  stdout: GUARD_RAN=true note=NONE
guard executes: True
```

## s12-lambda-never-invoked
```
$ E:\project\codex\wxAgent\.tools\t02\jdk-21.0.12.1+1\bin\javac.exe -J-Duser.language=en -J-Duser.country=US -d C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s12-lambda-never-invoked\out C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s12-lambda-never-invoked\probe\Shape.java
exit 0
$ E:\project\codex\wxAgent\.tools\t02\jdk-21.0.12.1+1\bin\java.exe -cp C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s12-lambda-never-invoked\out probe.Shape
exit 0  stdout: GUARD_RAN=false note=NONE
guard executes: False
```

## s13-return-true-then-call
```
$ E:\project\codex\wxAgent\.tools\t02\jdk-21.0.12.1+1\bin\javac.exe -J-Duser.language=en -J-Duser.country=US -d C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s13-return-true-then-call\out C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s13-return-true-then-call\probe\Shape.java
exit 0
$ E:\project\codex\wxAgent\.tools\t02\jdk-21.0.12.1+1\bin\java.exe -cp C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s13-return-true-then-call\out probe.Shape
exit 0  stdout: GUARD_RAN=false note=NONE
guard executes: False
```

## s14-ternary-side-effect
```
$ E:\project\codex\wxAgent\.tools\t02\jdk-21.0.12.1+1\bin\javac.exe -J-Duser.language=en -J-Duser.country=US -d C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s14-ternary-side-effect\out C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s14-ternary-side-effect\probe\Shape.java
exit 0
$ E:\project\codex\wxAgent\.tools\t02\jdk-21.0.12.1+1\bin\java.exe -cp C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s14-ternary-side-effect\out probe.Shape
exit 0  stdout: GUARD_RAN=false note=NONE
guard executes: False
```

## s15-inner-class-never-built
```
$ E:\project\codex\wxAgent\.tools\t02\jdk-21.0.12.1+1\bin\javac.exe -J-Duser.language=en -J-Duser.country=US -d C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s15-inner-class-never-built\out C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s15-inner-class-never-built\probe\Shape.java
exit 0
$ E:\project\codex\wxAgent\.tools\t02\jdk-21.0.12.1+1\bin\java.exe -cp C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s15-inner-class-never-built\out probe.Shape
exit 0  stdout: GUARD_RAN=false note=HOLDER
guard executes: False
```


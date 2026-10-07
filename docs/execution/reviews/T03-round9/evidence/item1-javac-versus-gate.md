# item 1: javac ground truth versus the gate's depth-1 verdict

`guardExecutes` is measured by running the compiled shape (javac exit 0), not by reading it.

| shape | javac exit | guard really executes | gate verdict | fair verdict |
| --- | --- | --- | --- | --- |
| `s1-if-false-unbraced` | 0 | False | ACCEPT | REJECT (MISMATCH) |
| `s2-if-false-braced` | 0 | False | REJECT | REJECT (fair) |
| `s3-boolean-false-unbraced` | 0 | False | ACCEPT | REJECT (MISMATCH) |
| `s4-static-final-false-unbraced` | 0 | False | ACCEPT | REJECT (MISMATCH) |
| `s5-while-false-unbraced` | 1 | n/a (file does not compile) | ACCEPT | REJECT (does not compile) (MISMATCH) |
| `s6-return-ahead-of-call` | 0 | False | ACCEPT | REJECT (MISMATCH) |
| `s7-runtime-always-false-test` | 0 | False | ACCEPT | REJECT (MISMATCH) |
| `s8-for-loop` | 0 | True | ACCEPT | ACCEPT (fair) |
| `s9-try-finally` | 0 | True | REJECT | ACCEPT (MISMATCH) |
| `s10-switch-default` | 0 | True | REJECT | ACCEPT (MISMATCH) |
| `s11-else-of-real-condition` | 0 | True | not tested | ACCEPT (MISMATCH) |
| `s12-lambda-never-invoked` | 0 | False | REJECT | REJECT (fair) |
| `s13-return-true-then-call` | 0 | False | not tested | REJECT (does not compile) (MISMATCH) |
| `s14-ternary-side-effect` | 0 | False | not tested | REJECT (MISMATCH) |
| `s15-inner-class-never-built` | 0 | False | not tested | REJECT (MISMATCH) |

javac stderr for the shapes that do not compile:

- `s5-while-false-unbraced`: C:\Users\eie04\AppData\Local\Temp\t03r9\crosstable-en\s5-while-false-unbraced\probe\Shape.java:14: error: unreachable statement guard(); ^ 1 error

runtime lines:

- `s1-if-false-unbraced` -> `GUARD_RAN=false note=NONE`
- `s2-if-false-braced` -> `GUARD_RAN=false note=NONE`
- `s3-boolean-false-unbraced` -> `GUARD_RAN=false note=NONE`
- `s4-static-final-false-unbraced` -> `GUARD_RAN=false note=NONE`
- `s6-return-ahead-of-call` -> `GUARD_RAN=false note=NONE`
- `s7-runtime-always-false-test` -> `GUARD_RAN=false note=NONE`
- `s8-for-loop` -> `GUARD_RAN=true note=NONE`
- `s9-try-finally` -> `GUARD_RAN=true note=NONE`
- `s10-switch-default` -> `GUARD_RAN=true note=NONE`
- `s11-else-of-real-condition` -> `GUARD_RAN=true note=NONE`
- `s12-lambda-never-invoked` -> `GUARD_RAN=false note=NONE`
- `s13-return-true-then-call` -> `GUARD_RAN=false note=NONE`
- `s14-ternary-side-effect` -> `GUARD_RAN=false note=NONE`
- `s15-inner-class-never-built` -> `GUARD_RAN=false note=HOLDER`

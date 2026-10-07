# out-of-repo shadow tree used for every whole-gate mutation run
root: C:\Users\eie04\AppData\Local\Temp\t03r9\shadow

ci.yml was re-synced to the bytes at HEAD fb62212 before the CI battery (an earlier commit
under this session changed it after the tree was first copied); every other file matched
the repository byte for byte, verified by sha256 comparison.

SAME  .github/workflows/ci.yml  4494B
SAME  backend/src/main/java/com/example/editorial/identity/T03Configuration.java  6319B
SAME  backend/src/main/resources/application-dev.yml  36B
SAME  backend/src/main/resources/application-mock.yml  73B
SAME  backend/src/main/resources/application-prod.yml  104B
SAME  backend/src/main/resources/application.yml  1944B
SAME  backend/src/test/java/com/example/editorial/identity/T03PostgresTest.java  19839B
SAME  backend/src/test/java/com/example/editorial/identity/T03SessionCookieGuardTest.java  5090B
SAME  docs/api/diff-pages-v1.1.openapi.yaml  2677B
SAME  docs/api/openapi.yaml  613679B
DIFF  tests/engineering/T03/__pycache__/check_session_cookie.cpython-312.pyc  61891B
SAME  tests/engineering/T03/check_session_cookie.py  58746B
SAME  tests/engineering/T03/evidence/T03SessionCookieGuardTest.txt  366B
SAME  tests/engineering/T03/evidence/T03SessionCookieGuardTest.xml  30449B
SAME  tests/engineering/T03/evidence/guard-test-binding.json  2003B
SAME  tests/engineering/T03/record_guard_binding.py  5392B

note: tests/engineering/T03/__pycache__ was produced by importing the shadow gate and is
deleted together with the whole shadow tree; nothing was written back into the repository.

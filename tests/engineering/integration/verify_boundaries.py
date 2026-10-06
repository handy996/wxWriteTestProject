"""Check the reviewed snapshot against the formal integration files."""
import hashlib
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
BASE = "ab956ec38406958a9428c0f189bc53f683e018ba"
sys.path.insert(0, str(ROOT / "tests/engineering/T06"))
sys.path.insert(0, str(ROOT / "tests/engineering/T07"))
from prepare_delivery import canonical_source
from extend_t06 import extend


def baseline(path):
    return subprocess.check_output(["git", "show", BASE + ":" + path], cwd=ROOT)


def same(path, expected):
    actual = (ROOT / path).read_bytes()
    assert actual == expected, path
    print(path, hashlib.sha256(actual).hexdigest())


for task, name in (("T03", "V1__identity_audit_idempotency.sql"),
                   ("T05", "V2__skill_prompt_policy.sql"),
                   ("T06", "V3__article_job_version.sql"),
                   ("T07", "V4__change_proposal.sql")):
    same("backend/src/main/resources/db/migration/" + name,
         baseline("tests/engineering/" + task + "/migration-draft.sql"))

path = "backend/src/main/java/com/example/editorial/shared/CanonicalRequest.java"
same(path, canonical_source(baseline(path).decode()).encode())
path = "backend/src/main/java/com/example/editorial/article/job/ArticleService.java"
same(path, extend(baseline(path).decode()).encode())
for task, name in (("T06", "ArticleIntegration.java"),
                   ("T07", "VersionIntegration.java")):
    same("backend/src/main/java/com/example/editorial/bootstrap/" + name,
         baseline("tests/engineering/" + task + "/" + name))

for path in ("backend/src/main/resources/db/migration/R__t02_schema_permissions.sql",
             "tests/engineering/T02/evidence/r01-integrity.json"):
    same(path, baseline(path))
print("Reviewed snapshot and formal integration boundaries verified")

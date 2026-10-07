# T02 整改 R02c：密钥扫描例外体系闭环报告

日期：2026-10-08（Asia/Hong_Kong）。作者：T02 卡片实现方（子会话）。状态：**实现与自测完成，提交主 agent 独立复审；本报告不自我判定采纳，不写入 `docs/execution/STATE.json`。**

判决依据：`docs/execution/reviews/T02-round3/review.md`（R02 CHANGES_REQUIRED，F-01/F-02/F-03/F-05/F-06）。开工基线 HEAD `241083f`；交付时 HEAD 已推进到 `bee014c`（主 agent 在本会话期间提交了 STATE 与 T03 CI 等，本卡未参与）。`git show HEAD:tests/engineering/T02/gitleaks.toml` 仍是含 3 条 `paths` 的被判决形状，故 3.2/3.6 的 HEAD 对照配置与判决输入一致。本卡未创建任何提交。

---

## 1. 本轮实际改了什么

| 文件 | 变化 | 状态 |
|---|---|---|
| `tests/engineering/T02/gitleaks.toml` | 3 条 `[[allowlists]]` 的 `paths` 整文件豁免全部删除，改为 4 条只按值的例外（11 个字面量值，0 个 `paths`） | 修改（1,327 → 2,076 字节） |
| `tests/engineering/T02/digest_records.py` | 新增：指纹记录器（`path` 与 `sha256` 分行），带「关键词与 32+ 位十六进制同行」序列化守卫 | 新增文件 |
| `tests/engineering/T02/revision_integrity.py` | 改用记录器输出；默认输出改 `evidence/r02-integrity.json`；新增 `--out`；拒绝覆写冻结的 `r01-integrity.json` / `r01-integrity-run.json` | 修改 |
| `tests/engineering/T02/integration.py` | `artifacts` 由 `{路径: 摘要}` 改为同一记录格式（同一根因，同一修复） | 修改 |
| `tests/engineering/T02/scan_secrets.py` | 新增可选 `--report`（默认值不变，CI 行为不变），使复跑可写入 `.work` 而不覆盖已跟踪证据（对应 F-05） | 修改 |
| `tests/engineering/T02/check_gitleaks_allowlists.py` | 新增：可重跑的策略门与四控制（结构模式无需 gitleaks，可单跑） | 新增文件 |
| `docs/execution/reports/T02.md` | 原文 :94 表行与 :115 第 6 条就地标注「撤回」并给出实测（插入 R02c 一节后两处现位于 :113 与 :135）；原 :32 追加输出路径变化注记；新增「审核整改 R02c」一节写清 `paths` 语义与复现命令 | 修改 |

本卡改动文件（按归属从整树 `git diff --name-only` 中挑出；整树实测见下一段）：

```
docs/execution/reports/T02.md
tests/engineering/T02/gitleaks.toml
tests/engineering/T02/integration.py
tests/engineering/T02/revision_integrity.py
tests/engineering/T02/scan_secrets.py
```

未跟踪新增：`tests/engineering/T02/digest_records.py`、`tests/engineering/T02/check_gitleaks_allowlists.py`、本报告。

**并发工作树提示（不属本卡）**：收尾实测 `git diff --name-only` 还包含 `backend/src/main/java/com/example/editorial/cost/BudgetPolicy.java`、`BudgetPolicyConfig.java`、`BudgetService.java`、`backend/src/test/java/com/example/editorial/cost/CostPricingTest.java`、`T08PostgresTest.java`、`tests/engineering/T08/run_pg.py`，以及未跟踪的 `docs/execution/reviews/T03-round8/`、`T08-round3/`、`tests/engineering/T08/evidence/r3-review*`。这些是其他会话在同一工作树里的改动，本卡未读写其内容（`T02-round3/review.md` 是判决输入除外），主 agent 归并时需分开归属。上表的命令退出码是在该混合工作树下实测的。

历史证据零改写：`tests/engineering/T02/evidence/**` 在 `git status --porcelain` 中无变更；`verify_boundaries.py:41-43` 断言的 `r01-integrity.json` 原字节保持。新生成的清单只落在 `.work/`，用后即删，本卡**没有**产生 `evidence/r02-integrity.json`（避免制造未经复审的证据文件；命令与默认路径已备好，由主 agent 决定是否需要）。

---

## 2. 逐条命令与退出码（PowerShell 5.1，均从项目根目录执行）

`$py = C:\Users\eie04\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`（3.12）

| 命令 | 退出码 | 实测输出 |
|---|---:|---|
| `.tools/t02/gitleaks/gitleaks.exe version` | 0 | `8.30.1` |
| `$py tests/engineering/T02/check_contracts.py` | 0 | `Approved T00 rc.3: 27 hashes verified, no regeneration`（rc.3 冻结契约未触碰） |
| `$py tests/engineering/T02/scan_secrets.py --gitleaks .tools/t02/gitleaks/gitleaks.exe`（**整改前**，HEAD 配置） | 1 | 7 条 `generic-api-key`（文件/行号见 3.6 表，与判决 F-01 一致）；同输入集对照字节数见 3.2 |
| `$py tests/engineering/T02/scan_secrets.py --gitleaks .tools/t02/gitleaks/gitleaks.exe`（**整改后**，同一输入集，报告写默认已跟踪路径） | 0 | `no leaks found`，报告体为 `[]`，`scanned ~37,078,079 bytes`；与上一行的字节差恰为 150,604。同命令后续复跑为 37,080,919、37,081,595 字节——增量只是这两份报告自身文本变大，退出码 0 / 0 命中稳定 |
| `$py tests/engineering/T02/scan_secrets.py --gitleaks .tools/t02/gitleaks/gitleaks.exe --report tests/engineering/T02/.work/r02-exp/final-report.json` | 0 | 同上，且不触碰已跟踪证据（F-05 复现路径） |
| `$py tests/engineering/T02/check_gitleaks_allowlists.py`（结构模式，无需 gitleaks） | 0 | 16 项断言全 PASS，`GITLEAKS ALLOWLIST POLICY: PASSED (structure only)` |
| `$py tests/engineering/T02/check_gitleaks_allowlists.py --with-controls --gitleaks .tools/t02/gitleaks/gitleaks.exe` | 0 | 88 项断言：88 PASS / 0 FAIL，`GITLEAKS ALLOWLIST POLICY: PASSED` |
| `$py tests/engineering/T02/revision_integrity.py --out tests/engineering/T02/.work/r02-out/r02-integrity.json` | 0 | `271 delivery fingerprints; original migration unchanged; packaged SQL matches; test V1 absent`（47,792 字节） |
| `$py tests/engineering/T02/revision_integrity.py --out tests/engineering/T02/evidence/r01-integrity.json` | 1 | `refusing to rewrite frozen evidence record: tests/engineering/T02/evidence/r01-integrity.json`（冻结保护） |
| `$py -m py_compile` 全部 6 个本卡脚本 | 0 | 无语法错误 |
| `$py tests/engineering/T02/secret_scan.py`（本卡未改此文件） | 1 | `Secret pattern scan: FAILED: backend/src/test/java/com/example/editorial/storage/S3ProtocolRegressionTest.java, docs/execution/STATE.json` → 需主 agent 处理，见第 5 节 |
| `git diff --check` | 0 | 本卡文本为 BOM-free / LF |

`secret_scan.py` 本轮新列出 `docs/execution/STATE.json`（此前只列 S3 测试文件）：该文件现命中 `secret_scan.py:10` 的 `\bAKIA[0-9A-Z]{16}\b` 之类模式；两处都不是本卡可改文件，本卡未读写 `STATE.json`。

---

## 3. 四项验控实测数字（这是本轮主交付，不是附加说明）

全部在 `tests/engineering/T02/.work/allowlist-controls/` 内的副本上执行；不修改任何已跟踪文件；脚本在 `finally` 中删除该目录并断言已删（`PASS scratch tree deleted before exit`）。

### 3.1 正向控制（盲区已消除）

把三份**曾被整文件豁免**的文件复制到 `.work`，各自末尾植入两份合成 canary：一行 `github_token: ` + `ghp_` 前缀的 40 位合成字符，以及一对运行时拼接而成的 RSA 私钥 PEM 头/尾块（canary 字符串在 `check_gitleaks_allowlists.py` 中按片段拼接，任何仓库文本里都不出现完整模式串，以免本卡自己的文档去触发 `secret_scan.py` 的模式）。用交付配置扫描：

- 6/6 canary 全部命中，规则 `github-pat` 与 `private-key`，路径按 `File` 字段核对；
- 「6 条 canary 即全部命中」成立：`extra []`，退出 1（说明这三份文件里除 canary 外没有其他被抑制的真实密钥形态，也没有多报）；
- 涉及文件字节量：`scanned ~151,174 bytes`（150,604 + canary）。

### 3.2 盲区复现控制（证明 `paths` 语义，正向结论不是空话）

同一 canary 目录树、同一 gitleaks 二进制，仅把配置换成「从交付配置文本重建的旧形状」（在 3 个 `condition = "AND"` 后各注入一条 `paths = [...]`，注入条数由脚本断言等于 3）：

- 退出 0、**0 条命中**，gitleaks 自报 `scanned ~0 bytes (0)`；
- 即：三份文件（128,810 + 7,011 + 14,783 = **150,604 字节**）在旧配置下完全不被读取，追加真实格式的 GitHub PAT 与 PEM 私钥也不会报——配不配 `regexes` 都一样；
- 全仓同输入集对照（2,411 个 git 可见文件）：HEAD 配置 `36,927,475 bytes / 7 命中 / 退出 1`，交付配置 `37,078,079 bytes / 0 命中 / 退出 0`，**字节差恰为 150,604**，即旧配置的盲区大小。

结论写进报告与配置注释：Gitleaks 8.30.1 的 allowlist 带文件条件（`paths`）时是**整文件退出扫描**，不是「该值仅在该文件豁免」；因此 `paths` 在本仓配置中被禁用，并由脚本断言出现次数为 0。

### 3.3 反向控制（例外不能全吞）

对 11 个被豁免值逐个构造探针文件（`"docs/api/reference.json": "<值>"` 加一行 `openapi.yaml=<值> …` 叙述形态，两种形态都是 `generic-api-key` 实际命中过的形态）：

- 先以「无例外」的默认规则扫描，确认 11 个原值**全部真能触发**规则（控制非空转）；
- 11/11 原值在交付配置下被抑制（退出 0）；
- 每个值改 1 个字符（首 / 中 / 末位，共 33 个变异体）在交付配置下**全部重新被报**（退出 1，规则 `generic-api-key`）；本轮 0 个变异体落入「规则本身不报」的空转情形（脚本会显式列出并剔除，避免用空转充数）。

**与主 agent 建议的偏差及理由**：建议中对两个契约文件摘要用 `775fb0764e03432b.*ec65ec99` 式「首尾定长 + 中间通配」。实测放弃该写法，改用**完整字面量**，原因两条：

1. 通配会把摘要中段变成任意文本，中段改一位仍被抑制 → 直接废掉 3.3 的反向控制；
2. 变体 A 实验出现的配置自身命中（`gitleaks.toml` L10/L17）来源不是长十六进制本身，而是值前的关键词形态（`Idempotency-Key: …`、`key=…`）；把例外拆成独立 `regexes` 行、行内不含关键词后，实测**自身 0 命中**：把交付配置复制成中性文件名（避开 gitleaks 对 `gitleaks.toml` 文件名的处理差异）用「默认规则、无任何例外」扫描 → `2,076 bytes / 0 命中 / 退出 0`；同一方式扫描 HEAD 配置副本 → `1,327 bytes / 2 命中 / 退出 1`（正是 L10/L17）。

现配置的 11 个值：SRS 示例 UUID 1 个、T04 已删除测试对象 1 个、`r01-integrity.json` 摘要 6 个、两个冻结契约文件摘要 2 个，外加 1 个短形态 `e285471760a5dce4...`——它是 `docs/execution/reviews/T03-round5/evidence/checks.json:20` 叙述行里的**截断散文摘要**（19 字符，含字面 `...`，配置里写作 `e285471760a5dce4\.\.\.`），不是通配。

### 3.4 良性控制（正常哈希清单不得被染红）

- 用真实生成器 `$py tests/engineering/T02/revision_integrity.py --out .work/…` 产出 271 条指纹清单（47,792 字节）；
- `digest_records.violations()` 对该清单返回空：不存在任何一行同时含关键词与 32+ 位十六进制；
- 该清单在**完全不配 allowlist**（`[extend] useDefault = true` 的空配置）下扫描：0 命中、退出 0、`scanned ~47,792 bytes`；在交付配置下同样 0 命中；
- 对照历史：同一空配置扫描旧格式 `evidence/r01-integrity.json` → 6 命中（这就是根因证据，文件未被改动，只在副本上扫）。

即新产物不再依赖任何例外即可通过扫描，后续同类文件不会再把门染红。

### 3.5 结构自检（可接 CI 的断言）

`check_gitleaks_allowlists.py` 默认模式即断言，无需二进制，已在 88 项全 PASS 中与单独结构运行（16 项 PASS）两次通过：

- 配置中 `paths` 出现次数 == 0（同时检查 `\bpaths\b` 与 `^\s*\w*paths\w*\s*=` 两种形态）；
- `[extend] useDefault = true` 存在、`[[rules]]` 不存在（默认规则只扩展不替换）；
- 4 个 allowlist 块全部含 `condition = "AND"`、`regexTarget = "match"`、`regexes = [`；
- 豁免值数量钉为 11（新增例外必须显式改常量并接受复审）；
- 每个例外是**单个字面量**：去掉 `\.` 式转义后不含任何正则元字符（禁止 `*`/`.*`/字符类通配），且长度 ≥ 16。

### 3.6 全量命中账目（抑制了多少、抑制在哪、是不是空转）

同一输入集（2,411 个 git 可见文件副本，`.work` 内）在**完全不加任何 allowlist** 的默认规则下实测 **15 条**命中，全部为 `generic-api-key`，逐条如下（本卡不修改这些文件，只按值抑制）：

| 命中位置 | 条数 | 此前状态 | 本轮处理 |
|---|---:|---|---|
| `tests/engineering/T02/evidence/r01-integrity.json` L67/110/111/115/124/125 | 6 | 被 `paths` 整文件豁免（不可见） | 6 个 r01 摘要完整字面量，只按值 |
| `docs/AI-Editorial-Agent-SRS-v1.0.md` L937 | 1 | 被 `paths` 整文件豁免（不可见） | SRS 示例 UUID `397c4e7a-…`，只按值 |
| `tests/engineering/T04/evidence/integration.json` L73 | 1 | 被 `paths` 整文件豁免（不可见） | T04 已删除测试对象 `55565d49-…`，只按值 |
| `docs/execution/reviews/T03-round5/evidence/checks.json` L11/12/20 | 3 | 一直显形（就是判决 F-01 的 7 条之 3） | 2 个冻结契约文件摘要 + 1 个截断散文形态 |
| `docs/execution/reviews/T07-round4/checks.json` L91/93 | 2 | 一直显形 | 同上（同一摘要的重复出现） |
| `tests/engineering/T03/evidence/session-cookie-r04.json` L29/30 | 2 | 一直显形 | 同上 |

账目闭合：旧配置的 7 条显形命中 + 被 `paths` 藏起来的 8 条 = 15 条；15 条由 11 个字面量值覆盖（同一摘要在多行重复出现）；交付配置下全仓 0 命中、退出 0。判决 F-01 报出的 7 条文件/行号与本表逐一对齐，复现基线一致。

配置自身命中的注意点：gitleaks 会跳过**文件名恰为 `gitleaks.toml`** 的输入（其内置全局例外），所以「配置自身 0 命中」不能用原名扫描来证明。本轮做法是把配置复制成中性名（`snapshot-of-delivered-config.toml`）后在**无任何 allowlist** 的规则下扫描：交付配置 2,076 字节 / 0 命中 / 退出 0；同法扫描 HEAD 配置副本得 1,327 字节 / 2 命中 / 退出 1（L10 `Idempotency-Key: …`、L17 `key=…`），即变体 A 实验出现的自身命中来源是值前的关键词形态，不是长十六进制本身。

---

## 4. 根因修复说明（生成器）

`generic-api-key` 的触发形态是「同一行含关键词（api/key/token/secret/…）与 32+ 位十六进制串」。旧 `revision_integrity.py:35` 的 `{路径: 摘要}` + `json.dumps(indent=2)` 让两者必然同行，于是 `backend/src/test/resources/db/secret-baseline.sql`、`docs/api/*.yaml` 这类路径每生成一份清单就新增一条命中，只能不断加豁免——这就是 7 条历史命中与「必须整文件豁免」的来源。

现由 `digest_records.py` 统一产出：

```json
{
  "files": [
    {
      "path": "docs/api/openapi.yaml",
      "sha256": "e285471760a5dce4f3df7445b6dcf29dcb1e7fefbefd3e9b535440ac8c67eb2b"
    }
  ]
}
```

`dumps()` 写前调用 `violations()`，任何「关键词与长十六进制同行」直接 `AssertionError` 拒绝；实测守卫对旧布局（关键词路径）拒绝、对分行布局与并排数组接受。`integration.py` 的 `artifacts` 同步改用该记录器（全仓 `*.py` 里 `artifacts` 只出现在 `integration.py:59` 的写入处，另有一处纯注释文本，无读取方；`evidence/integration.json` 现有内容不含该键，不受影响）。

冻结保护：生成器把 `evidence/r01-integrity.json`、`evidence/r01-integrity-run.json` 列入 `FROZEN`，命令行显式指定也拒绝（退出 1），默认输出改 `evidence/r02-integrity.json`，可用 `--out` 覆写。新清单**只读地把这两份冻结记录的内码摘要绑进本轮交付**（实测 271 条中包含它们），但不写它们、也不自我指纹（`excluded` 只排除输出文件自身；原 117 项的 `r01-integrity.json` 同样不含自身，属 dict 布局，本轮不改写）。

---

## 5. 仍未证明清单

1. **远端 CI 从未运行**：所有结论来自本地 PowerShell 5.1 + 真实 gitleaks 8.30.1 复现；GitHub Actions 未跑过，不能宣称 CI 通过。
2. **`secret_scan.py` 仍退出 1**（本卡不改此文件）：命中在 `S3ProtocolRegressionTest.java:16` 的 AWS 官方文档示例访问键（`AKIA` 开头的 20 字符示例 ID + 示例 secret）与 `docs/execution/STATE.json:387`（主 agent 记录同一示例键的文本）；门是否放行、改成注释形态还是加白，由主 agent 决定。本报告刻意不复制该示例键全文，否则本卡自己的文档会变成同一扫描的命中对象——这正是「模式串落在文档里」的一类残余风险，需要主 agent 在门禁口径上明确。
3. **规则覆盖缺口未闭合**：本卡只修「例外宽度/盲区」，没有扩展规则集。评审者实测 gitleaks 8.30.1 默认规则会漏掉裸 `AKIA[0-9A-Z]{16}`（无关键词上下文）与 `password=` / `DB_PASSWORD=` 明文；因此「0 命中」不等于「无密钥」，`secret_scan.py` 与 gitleaks 都不能证明不存在性。
4. **T07 下游期望必然失败**：`tests/engineering/T07/verify_delivery.py:52-53` 硬编码「恰好 6 条命中且全在 `r01-integrity.json`」；本卡改配置后该集合为 0 条。该文件不由本卡修改，需主 agent 同步更新期望（见第 6 节）。
5. **例外值不可能覆盖未来新密钥**：只按值的例外意味着任何**新**凭证形态都会正常报；但也意味着若有人把同一示例 UUID 复制进新文件，它会被同样抑制——这是按值例外的固有边界，属可接受风险（该 UUID 非真实凭证），需复审确认接受。
6. **`scan_secrets.py` 的输入集合仍由 `git ls-files --cached --others --exclude-standard` 决定**：被 `.gitignore` 排除的文件不在扫描范围（如 `.work/`、构建产物）；本卡未扩大该集合，只增加 `--report`。
7. **未验证 gitleaks 对 `paths` 的语义在其他版本是否相同**：结论绑定实测的 8.30.1；版本变更需重跑 `--with-controls`。
8. **本卡未生成新的已审认证据**：`evidence/r02-integrity.json` 未产出（只在 `.work` 验证），需要主 agent 决定是否正式生成并提交复审。
9. **未运行需 Maven/后端的任何命令**（按硬约束 `mvn -f backend/pom.xml …` 禁止），故 `integration.py` 的改动只验证到「可导入 + `--help` 退出 0 + 记录器单测形态」，未验证整条真实数据库集成链路。

## 6. 需主 agent 代跑 / 决策的命令

```powershell
# 1) 接进 CI 门（.github/workflows/ci.yml 的 "Secret and dependency scans" 步骤，建议紧随 scan_secrets 之后）
$py tests/engineering/T02/check_gitleaks_allowlists.py --with-controls --gitleaks .tools/t02/gitleaks/gitleaks.exe

# 2) T07 门期望更新后复跑（本卡未改 T07 文件）
$py tests/engineering/T07/verify_delivery.py
$py tests/engineering/integration/verify_boundaries.py   # 断言 r01-integrity.json 原字节，本卡已验证未触碰

# 3) secret_scan.py 的 2 处命中处置（S3 测试示例键 + STATE.json）
$py tests/engineering/T02/secret_scan.py

# 4) 是否正式产出 r02 完整性清单（生成器默认路径，含分行记录）
$py tests/engineering/T02/revision_integrity.py

# 5) 采纳判定与 STATE.json 写入（本卡按约束未写）
```

清理说明：本轮全部实验产物（`r02-exp/`、`r02-out/`、`r02-fmt/`、`r02-legacy/`、`r02-selfscan*/`、`r02-blindspot/`、`r02-repo-compare/`、`r02-case10/`、`allowlist-controls/`、`secret-scan-*` 临时目录、`r02-controls.txt`、`r02-baseline-*.json`）均在 gitignore 的 `tests/engineering/T02/.work/` 下，收尾时删除并以 `Test-Path` / `git status` 证明；控制脚本自身每次运行也在结束时删除其 scratch 目录并断言。

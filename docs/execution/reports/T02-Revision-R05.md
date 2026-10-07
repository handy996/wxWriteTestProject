# T02 整改 R05：值豁免子串边界、AWS canary 字母表与脚本健壮性

日期：2026-10-08（Asia/Hong_Kong）。作者：T02 卡片实现方（第五轮整改子会话）。状态：**实现与自测完成，提交主 agent 独立复审；本报告不自我判定采纳，不写入 `docs/execution/STATE.json`，不 `git add`/`git commit`。**

判决依据：`docs/execution/reviews/T02-round4/review.md`（第四轮 CHANGES_REQUIRED）。唯一 P1 **A-1** 已由主 agent 修掉并提交 `2a13a2e`（CI 解析步 + `$GITLEAKS_BIN`）；本轮不碰 `.github/workflows/ci.yml`。本轮承担 **A-2…A-9 + J-1…J-6 残余**，并吸收主 agent 对第四轮「裸 AKIA」判断的更正实测（见 §0）。

约定：引用被豁免的示例键时一律打断书写（`AKIA/IOSFODNN7EXAMPLE`、摘要 `775f…ec99`），否则本报告自身会成为 `aws-access-token` / `generic-api-key` 命中对象。合成 canary 在脚本里运行时拼接，源码与本文都不留活体连续形状。

开工基线 HEAD `8304401`；开工实测四冻结件哈希 `1d18eef28322218a` / `18be0c34fbc16ad1` / `37517e5f3dc66819` / `efd32a24525457b7`，`check_contracts.py` 退出 0（27 哈希）。收尾证明见 §收尾。

---

## 0. 主 agent 更正吸收（裸 AKIA 判据 = 字母表 AND 熵门，不是熵单独）

- **计划**：把 `T02-Revision-R02.md:164`「默认规则会漏裸 AKIA」更正为**实测口径**（既不写「能抓」也不写「不能抓」的二值结论）；在 canary 集补一条 `AKIA`+16 位 `A-Z2-7` 的活体样本，让 `--with-controls` 真能证到「AWS 形状密钥会被抓」，并保留一条含 `0/1/8/9` 的近邻样本作为「越界形状不保证」的说明（它不该命中，是特性不是缺陷）。
- **实测**（TEMP 探针，交付配置 = `[extend] useDefault=true`，逐条 `aws-access-token` 命中/漏判）：我独立跑了 base32 与近邻两组，得到比「纯字母表」更准的结论——**判据是 base32 字母表 AND 香农熵 ≥ 约 3.0 两道门同时满足**：
  - 纯 base32 后缀：熵 4.0/3.0/2.0… 的 6 个里，熵 ≥ 3.0 的 4 个全部命中、熵 2.0 与 1.0 的两个（`AAAABBBBCCCCDDDD`、`AAAAAAAABBBBBBBB`）**被漏**——所以主 agent「判据不是熵」在其高熵带 [3.2806,3.8750] 内成立，但把纯 base32 拉到极低熵仍会漏，熵是一道**独立下界**。
  - 含 `0/1/8/9` 任一者 7 个**全部漏**（熵 1.27…4.0 都漏）；含 `2-7` 允许位者全部抓；含小写者漏。故字母表也是一道独立硬门。
  - 两组熵区间 `[1.0,4.0]` 与 `[1.2718,4.0]` **重叠** → 单看熵不能判命中；单看字母表也漏低熵 base32。**两条门都要满足。** 规则 `aws-access-token`（`AKIA[A-Z0-9]{16}` 形态 + `entropy` 门，RE2 引擎）。
  - 真 AWS key id 是 base32 且高熵 → 两道门都过 → 规则对**真实形状可靠**。第一轮探针用 `A-Z0-9` 造 canary（多半含 `0/1/8/9`）落在字母表外，才被误读成「规则失明」。`wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` 不抓是因 `EXAMPLE`（stopwords）与 `/`，与「AKIA 形态整体漏」无关。
  - 据此改写 `T02-Revision-R02.md:164` 为该双门口径（已改，见该文件 §5 第 3 条）。
- **新 canary 命中证据**：`check_gitleaks_allowlists.py` 的 `canary_block()` 现运行时拼一条 `AKIA`+`ABCDEFGHIJKLMNOP`（16 位纯 base32、熵 4.0）活体样本 + 一条把第 8 位换成 `1` 的近邻样本。`--with-controls` 实测：
  - 正向控制三份副本各植 4 形（github-pat / private-key / **base32 AKIA** / 近邻 AKIA），`aws-access-token` 恰命中 **3 条（每份一条）**、近邻 0 条 → 断言 `AWS-shape control: only the three base32 ids fired` PASS；
  - 「九条 canary 即全部命中」`extra []` 成立（原六条现九条，新增三条全为 `aws-access-token`）；
  - 近邻样本 `nearmiss_aws_access_key_id = AKIA…1…` 不被抓，作为「越界形状不保证」的显式特性说明（不是缺陷），已写进断言标题与配置/脚本注释。
- **未证明**：未取 gitleaks 上游源码核对 `entropy` 门精确阈值（我实测在 3.0 处翻转，记为「约 3.0」）；未测规则对 `ASIA/ABIA/ACCA` 前缀的行为。

---

## A-2（P2）：值豁免实为子串豁免 → 词边界加固

- **计划**：按第四轮 C-13 用 `'''\b值\b'''` 包住 10 条字面量；第 11 条（19 字符含字面点 `...`）需 RE2 安全加固。**不**退回 C-12 已证伪的 `^…$`（`regexTarget="match"` 测整条匹配文本，`^值$` 使 11/11 精确值也不再被抑制）。配置注释补 gitleaks `condition="AND"` 真实语义。
- **实测**（TEMP `harden_test3/4.py`，逐探针扫两遍 defaults/delivered）：
  - **关键否定结果（推翻第四轮 C-13 的第 11 条建议）**：第四轮建议第 11 条用「否定环视 `(?<![0-9a-f])…(?![0-9a-f])`」。我实测 gitleaks 8.30.1 **内嵌 RE2，遇 `(?<!`/`(?!` 直接 panic**：`re2.cc Error parsing … invalid perl operator: (<!` → **整条配置被中止**（exit 2/3、`scanned 0 bytes`、连其它 10 条也全失效，探针全成 0 命中的**假绿**）。故环视方案在本工具链上**不可实现**，必须换 RE2 安全写法。
  - **RE2 安全设计（最终采用）**：10 条用 `'''\b值\b'''`；第 11 条（尾部是字面点，`\b` 在 `.` 后不成立）用 `'''\b<前缀>\.\.\.[^0-9a-f]'''`——前导 `\b` + 转义的字面点 + RE2 支持的否定字符类守卫。实测：
    - **11/11 精确值仍被抑制**（defaults 命中、delivered 0 命中）；
    - **33/33 超串重新被报**（前缀 `ab+值`、后缀 `值+cd`、内嵌 `0123456789+值+abcdef` 三种，逐值在加固后全部重新变红）——子串豁免被关闭；
    - 第四轮那套 **44 个变异（首 / 中两点 `n//2`+`2n//3` / 末）全部重新变红**；`--with-controls` 实测单字符变异重报 **44 条**、超串重报 **33 条**、精确抑制 **11 条**。
  - **`condition="AND"` 真实语义写进配置注释**：AND 作用在**维度之间**（paths/commits/regexes 同时满足）；**同一块内多条 `regexes` 是「任一命中即抑制」**（否则单值探针不可能被抑制，r01 六摘要共享一块即证）。
  - **`--with-controls` 断言条数：改前 88 → 改后 139**（正向 +3 变异面与 AWS canary、+33 子串控制、+2 配对门、+2 逐值标签拆分），全 PASS / 0 FAIL，退出 **0**。结构模式改前 16 → 现 18（配对门 2 条），退出 0。
- **未证明**：环视在其它 gitleaks 版本是否可用未测（本卡绑定 8.30.1）；低熵真凭据逃逸面（见 §0）。

---

## A-3（P2）：`*gitleaks.toml*` 触发范围更正

- **计划**：把「恰为 `gitleaks.toml`」更正为「路径含 `gitleaks.toml` 子串者一律不读」。
- **实测**（TEMP `a3_probe.py`，同一 77 字节 high-entropy 载荷、defaults-only 无 allowlist）：

  | 文件名 | 结果 |
  |---|---|
  | `gitleaks.toml` | `scanned ~0 bytes (0)` / 0 命中 / 退出 0 → **跳过** |
  | `sub-gitleaks.toml` | `scanned ~0 bytes` → **跳过** |
  | `.gitleaks.toml` | `scanned ~0 bytes` → **跳过** |
  | `gitleaks.toml.bak` | `scanned ~0 bytes` → **跳过** |
  | `dir-gitleaks.toml.txt` | `scanned ~0 bytes` → **跳过** |
  | `plain.txt`（同字节改名） | `scanned ~77 bytes` / **1 命中 / 退出 1** → 读取 |

  → 触发范围是**子串**，非精确名。已更正 `T02.md:57` 与 `T02-Revision-R02.md`（§3.6 注意点）。**顺带发现（见 A-5）**：该子串例外使 gitleaks.toml 自身不计入 `scanned`，故「总量 − scanned」并非纯二进制量。
- **未证明**：该例外是否可被上游关闭未测。

---

## A-4 + J-1：T02.md 覆盖边界与显式风险边界

- **计划**：`T02.md` 补覆盖边界（子串抑制、`*gitleaks.toml*` 整文件不读、二进制跳过）；写明「0 命中不能支撑基线无密钥」；把 11 个豁免值是公开示例/摘要而非真凭据、以及「同一值日后真实出现也会被抑制」写成显式风险边界（不为此新增任何豁免）。
- **实测**：`T02.md` 的 R02c 段新增小节「覆盖边界与显式风险边界（R05，A-4 + J-1）」，原位写入四条覆盖边界 + 三条风险边界；J-1 双口径（值精确 + 子串经 A-2 已关闭）均写明。**未新增任何豁免**（11 条不变，`EXEMPT_VALUE_COUNT` 钉死）。
- **未证明**：外部系统里这些值是否仍有效未核（J-1/§7.2）。

---

## A-5（P3）：断言与报告只留稳定量

- **计划**：绝对总字节是运行时量，断言里只留 `0/7/15` 命中数、`150,604` 整文件跳过量、二进制跳过量。
- **实测**（TEMP `stable_probe2.py`，三配置同一 `.work` 树；历史配置取自 `git show deca2a1^`，非重构版）：
  - 命中数 **交付 0 / defaults 15 / 历史 7** 复现，账目闭合（7 + 8 = 15）；
  - **整文件跳过量 = scanned(delivered) − scanned(historical) = 150,604** 复现（与 gitleaks.toml 自身大小无关，稳）；
  - **更正第四轮的 148,267**：该值是「复制总量 − scanned」，而 gitleaks.toml 因 A-3 子串例外**本就不计入 scanned**，故 148,267 里混进了当时 gitleaks.toml 的 2,076 字节自跳过。纯二进制跳过量 = 总量 − scanned − gitleaks.toml 字节 = **146,191**（本轮实测，稳定量）；本轮把配置从 2,076 改到 3,329 字节后，「总量 − scanned」变成 149,520 = 146,191 + 3,329，二进制本体不变。→ 报告与断言只引用 146,191 / 150,604 / 0-7-15，绝对 scanned 标为运行时量、不作结论（已改 `T02.md:61`、`:129`、R02 §2 表、§3.2、§3.6）。
- **未证明**：二进制文件的具体构成清单未逐一枚举（不递归列举工作根）。

---

## A-6（P3）：revision_integrity.py 冻结保护与仓库外 --out

- **计划**：`FROZEN` 补第三份冻结件 `gitleaks-findings.json`；仓库外 `--out` 由裸 `ValueError` 改为可读失败并退出非 0。
- **实测**（每条带退出码）：
  - `--out …/evidence/gitleaks-findings.json` → **退出 1** + `refusing to rewrite frozen evidence record: …`，运行前后哈希 `37517e5f3dc66819` 不变（拒写生效，未覆写）；
  - `--out …/evidence/r01-integrity.json` → 退出 1 + `refusing to rewrite frozen evidence record`（原两条仍在）；
  - `--out $env:TEMP\t02r5_outside.json`（仓库外）→ **退出 1** + `--out must stay inside the repository; refusing to write outside it: …`（不再是 `ValueError: … is not in the subpath of …` 裸 traceback）；
  - 正常 `--out tests/engineering/T02/.work/a6-check.json` → 退出 0（272 fingerprints），用后即删。
- **未证明**：无（三项全覆盖）。

---

## A-7（P3）：T02.md:30 就地标注

- **计划**：`T02.md:30`（`secret_scan.py` 退出 0「无命中」）像 `:113`/`:135`/`:32` 一样就地标注 F-06 证伪→值豁免恢复的历史，指向 `0b2a6f8`。**原位改，不留新章节掩盖。**
- **实测**：`:30` 行尾加「R02c/第五轮就地注」，写明第三轮 F-06 曾证伪（`S3ProtocolRegressionTest.java` 的 `AKIA/IOSFODNN7EXAMPLE` 示例键 + `STATE.json`）、主 agent 以 `EXEMPT_VALUES` 精确值豁免恢复为 0、`--self-test` 近邻仍被抓；只保留「当前退出 0」事实，撤回「从未命中」读法。示例键以 `/` 打断书写，本行不自触发。
- **未证明**：无。

---

## A-8（P3）：结构断言标签名实相符

- **计划**：把 19 字符含转义点那条不再笼统叫「no wildcard」。
- **实测**：`check_gitleaks_allowlists.py` 的 `structure()` 用 `unwrap()` 把锚点拆出后按形态分类：10 条标 `full literal value, word-boundary anchored, no wildcard`，第 11 条标 `truncated-prose digest (literal dots + non-hex guard), not a wildcard`；未锚定者标 `unanchored` 并判 FAIL。结构模式实测标签正确、退出 0。R02 §3.5 同步改述。
- **未证明**：无。

---

## A-9（P3）：配对形状前置门

- **计划**：加「配对形状」前置门——让脚本在结构模式即调 `digest_records`（同行 `path`+`digest` 配对必须报错），使这类写法在落地那一刻失败。
- **实测**：`pairing_gate()` 在结构模式与 controls 模式都先跑：`digest_records.dumps({'docs/api/openapi.yaml': 'ab'*32})` 必须抛 `AssertionError`（否则门是空转），分行记录必须被接受（否则门过严）。结构模式实测两条均 PASS、退出 0；controls 模式 139 全 PASS。
- **未证明**：本卡脚本侧已加门；`.github/workflows/ci.yml` 是否已接线调 `digest_records.check()` 属主 agent（本卡不动 CI）。

---

## 脚本自身（A-1 姊妹项）：check_gitleaks_allowlists.py 的 --gitleaks 校验

- **计划**：对传入路径做存在性/可执行性响亮校验（第四轮实测目录→`PermissionError`、不存在→`FileNotFoundError`，均未捕获 OSError），改前捕获并打印可读失败退出非 0。本地 Windows 形状 `.tools/t02/gitleaks/gitleaks.exe`；Linux 形状由 CI 解析步负责（主 agent 已在 `2a13a2e` 处理，本卡不动 ci.yml）。
- **实测**（`resolve_scanner()`）：
  - `--gitleaks .tools/t02/gitleaks`（目录）→ **退出 1** + `--gitleaks points at a directory, not an executable: …`（不再是未捕获 `PermissionError`）；
  - `--gitleaks …/nope.exe`（不存在）→ 退出 1 + `--gitleaks path does not exist: …`（不再是 `FileNotFoundError`）；
  - `--gitleaks .tools/t02/gitleaks/gitleaks.exe`（有效）→ 版本检查 PASS、controls 全跑；
  - 裸名 `gitleaks` 走 PATH 查找；崩溃在建 scratch **之前**，无 `.work` 残留。
- **未证明**：Linux 上 ENOTDIR/ENOENT 的具体 errno 未本地实测（属主 agent CI 侧）。

---

## J-2…J-6 残余处置

- **J-2**（裸 AKIA 判据）：已按 §0 更正为「base32 字母表 AND 熵 ≥ 约 3.0」双门口径，纠正「漏裸 AKIA」旧记（`T02-Revision-R02.md:164`）。
- **J-3**（`secret_scan.py` 值豁免取舍）：主 agent 已定；本卡未改 `secret_scan.py`，只在 gitleaks 侧补 base32 活体 canary + 近邻说明。序号更正：第四轮「仍未证明」第 **5** 条（非第 6 条）自报值豁免固有边界。
- **J-4**（T07 基线重录）：属 T07 卡下一轮，本卡不碰 `tests/engineering/T07/**`。
- **J-5**（A-1）：主 agent `2a13a2e` 已修 CI；本卡脚本侧补 `--gitleaks` 响亮校验（见上）。
- **J-6**（诚实度）：精度/序号更正见 §0、A-5、A-7；撤回项均**原位标注**（`:30`/`:57`/`:61`/`:129`、R02 §5）。
- **实测/未证明**：本卡未跑任何 `mvn` / `backend/target` 写命令；未写 T03/T07/T08 域文件。

---

## 必跑实测退出码（本会话，PowerShell 5.1，项目根）

| 命令 | 退出码 |
|---|---:|
| `python tests/engineering/T02/secret_scan.py --self-test` | 0 |
| `python tests/engineering/T02/secret_scan.py` | 0 |
| `python tests/engineering/T02/check_gitleaks_allowlists.py`（结构） | 0 |
| `python tests/engineering/T02/check_gitleaks_allowlists.py --with-controls --gitleaks .tools/t02/gitleaks/gitleaks.exe` | 0（139 PASS / 0 FAIL） |
| `python tests/engineering/T02/check_contracts.py` | 0（27 哈希） |
| `python tests/engineering/T02/digest_records.py` | 0 |
| `python tests/engineering/T02/scan_secrets.py --gitleaks .tools/t02/gitleaks/gitleaks.exe --report tests/engineering/T02/.work/r05-findings.json` | 0（no leaks found，未覆写冻结件） |

---

## 收尾

- **改动清单**（只在本卡可写范围）：
  - `tests/engineering/T02/gitleaks.toml`（A-2 锚定加固 + condition/RE2 注释；哈希 `efd32a24525457b7` → **`641c19b6b16282db`**，因豁免正则改写所致，2,076 → 3,329 字节）
  - `tests/engineering/T02/check_gitleaks_allowlists.py`（A-2 44 变异 + 子串控制 + AWS canary + 近邻说明；A-8 unwrap/标签；A-9 `pairing_gate()`；脚本自身 `resolve_scanner()`）
  - `tests/engineering/T02/revision_integrity.py`（A-6 FROZEN 补 `gitleaks-findings.json` + 仓库外 `--out` 可读拒绝）
  - `tests/engineering/T02/evidence/r05-allowlist-hardening.json`（**新增**证据，不覆盖既有）
  - `docs/execution/reports/T02.md`（A-3/A-4/A-5/A-7 就地改，新增覆盖/风险边界小节）
  - `docs/execution/reports/T02-Revision-R02.md`（A-1/A-3/A-5/A-8 就地改，§5 第 3 条 AKIA 更正）
  - `docs/execution/reports/T02-Revision-R05.md`（本报告，新增）
  - **未动**：`.github/workflows/**`、`tests/engineering/T03/T07/T08/**`、`backend/**`、`docs/execution/reviews/**`、`STATE.json`、`docs/api/**`、`docs/schemas/**`、`secret_scan.py`、`digest_records.py`、`scan_secrets.py`（三者未改，`scan_secrets.py` 默认路径行为不变）。
- **冻结件哈希（收尾实测，逐条不变）**：`r01-integrity.json 1d18eef28322218a/14783`、`r01-integrity-run.json 18be0c34fbc16ad1/409`、`gitleaks-findings.json 37517e5f3dc66819/3`、`docs/api/openapi.yaml e285471760a5dce4`、`docs/schemas/editorial.schema.json 7b5872e129817bbc`。`gitleaks.toml` **变** `efd32a…`→`641c…`（允许，A-2 改写所致，已在报告与证据写明）。
- **文本卫生**：本卡 authored 文件全部 **无 BOM / LF**（收尾脚本核验），`py_compile` 通过。`py_compile` 产生的瞬时 `tests/engineering/T02/__pycache__`（含 `digest_records`/`secret_scan` 等）收尾已删除并证明为 `[]`。
- **临时目录**：`$env:TEMP\t02r5\*`（探针脚本与其 scratch 树）与 `tests/engineering/T02/.work/` 下本卡新增的 `r05-stable`/`r05-stable2`/`r05-findings.json`/`r05-fullscan.json`/`r05-recheck.json` 结束前全部删除并以 `Test-Path` 证明 **False**；`.work` 仅剩其它会话既有目录，本卡未触碰。
- **改动可见性**：`git status --porcelain -- tests/engineering/T02 docs/execution/reports` 恰为本卡上列 7 项（5 改 + 2 新）；`git status --porcelain -- tests/engineering/T02/evidence` 只有新增的 `?? r05-allowlist-hardening.json`，**无任何既有证据被覆写**。
- **全树复扫**：新增/编辑后的 authored 文件重新纳入 `scan_secrets.py` 全树扫描仍为退出 0、报告体 `[]`、`gitleaks-findings.json` 哈希 `37517e5f3dc66819` 不变（扫描写的是 `.work` 内报告，未覆写冻结件）。

## 需主 agent 代跑的命令

```powershell
$py = 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'; cd E:\project\codex\wxAgent
# 1) 全树扫描写默认已跟踪报告（会覆写冻结的 gitleaks-findings.json，代跑前请留存/确认允许）
& $py tests/engineering/T02/scan_secrets.py --gitleaks .tools/t02/gitleaks/gitleaks.exe
# 2) Linux 形状 --gitleaks 解析（CI 侧跨平台，本卡未跑真实 runner）
# 3) T07 门实跑与基线重录（属 T07 卡）
```

# T02 第四轮独立复审（契约冻结 / 密钥扫描 / 修订完整性）

- 复审日期：2026-10-08（Asia/Hong_Kong）。
- **本文件为上一段中断会话的续跑**：上一段 01:39 中断（harness 判失败、无收尾消息），留下 `review.md` 骨架（当时 §0 仍是未勾选占位）、`r4_tree_scan.py`、`r4_c1_exempt_file.py`（**只写了没跑**）与 `evidence/c-tree-scan-summary.json`。续跑段按「继承需自证」处理：先核字节（§0.3），再用一次同批三配置运行（C-6）取代前段数字；C-1 本段实跑，并修掉两处断言缺陷与一处 PowerShell `Set-Content -Encoding UTF8` 引入的 BOM 配置副本问题。
- 被审对象：`deca2a1`（T02 R02c 整改）、`0b2a6f8`（主 agent 跨域两项 + `ci.yml` 接线）；第三轮原文 `docs/execution/reviews/T02-round3/`；整改方交付说明 `docs/execution/reports/T02-Revision-R02.md`。
- 判决：**CHANGES_REQUIRED**

> 判决理由（一句话）：被审整改本身（例外只按值、盲区已关、根因改分行、冻结件不被覆写、契约 27 哈希不变）四项必做控制**全部由我独立复现通过**；但 `0b2a6f8` 接入 CI 的第三条命令在 `ubuntu-24.04` runner 上指向一个**不可能存在的 Windows 路径**，使整个「Secret and dependency scans」步骤必然 traceback 失败并连带取消其后 4 条真实扫描命令（发现 A-1，P1）。修法是改一行；另有 3 项 P2 属**表述/加固**而非实现缺陷。

写作约定：下文引用被豁免的示例键时写作 `AKIA/IOSFODNN7EXAMPLE`（真实字节是连续 20 字符，此处插入 `/` 打断，否则本复审文件自身会成为 `aws-access-token` 命中对象——见 A-2 附证）。豁免摘要值一律截断书写（如 `775f…ec99`）。

## 0. 环境与基线（本会话自证）

### 0.1 工具与被审字节

| 项 | 值 |
|---|---|
| Python | `C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe` → 3.12.14（`-V` 退出 0） |
| Gitleaks | `E:\project\codex\wxAgent\.tools\t02\gitleaks\gitleaks.exe` → `version` 退出 0，输出 `8.30.1`；22,575,104 字节；sha256 `17157e2ee8b76fc8…fcb7c` |
| HEAD | 复审开始 `fb62212`，收尾 `d733b3f`（其间 T03/T08 会话提交 `c21e681`、`9f1df7e`、`d733b3f`；并发会话改变工作树是本卡的正常环境） |
| 被审文件是否被后续提交改动 | `git diff --stat 0b2a6f8 HEAD -- tests/engineering/T02 tests/engineering/T07 .github/workflows/ci.yml docs/api docs/schemas docs/execution/reports/T02.md` → **复审全程两次执行均为空、退出 0**（被审字节未变） |
| 配置 | `tests/engineering/T02/gitleaks.toml` 2,076 字节，sha256 `efd32a24525457b7…5bc82`（第三轮记为 `66e1fc1c…3ceed9`，即被审提交确实改了它） |
| 关键脚本 sha256 前 16／字节 | `secret_scan.py 9d5d070f69a2cc33/4574`、`check_gitleaks_allowlists.py 4bacc95acbefb6e6/12553`、`revision_integrity.py a1c79954b45795fd/3045`、`digest_records.py 290ecfe22aba5762/2529`、`scan_secrets.py 154ac4c15e61ded0/2070`、`T07/verify_delivery.py fd7ef90dce99864b/6704`、`ci.yml 2f651cb7ba7b429b/4494` |

### 0.2 冻结件基线（本会话开始时读取，退出 0）

| 文件 | sha256 前 16 位 | 字节 |
|---|---|---|
| `tests/engineering/T02/evidence/r01-integrity.json` | `1d18eef28322218a` | 14,783 |
| `tests/engineering/T02/evidence/r01-integrity-run.json` | `18be0c34fbc16ad1` | 409 |
| `tests/engineering/T02/evidence/gitleaks-findings.json` | `37517e5f3dc66819` | 3（内容 `[]`） |

### 0.3 继承核验、脏状态与约束遵守

- 前段工件哈希：`r4_tree_scan.py 280878c60b6e4787`、`evidence/c-tree-scan-summary.json 7dfea2fe8e739c31`。前段结论（交付配置 0 命中/退出 0；无 allowlist 15 命中/退出 1；`scanned ~37,647,470`）在本段以同一次运行的三配置结果重新校准（C-6），未直接引用前段数字作判定依据。
- 契约冻结（本卡职责之一）：`$py tests/engineering/T02/check_contracts.py` → 退出 **0**，`Approved T00 rc.3: 27 hashes verified, no regeneration`。该脚本不含写文件调用（无 `open(...,'w')`/`write_text`/`mkdir`），可安全复跑。
- 本会话开始时 `git status --porcelain`：`?? .tmp_t08fix.py`、`?? docs/execution/reviews/T02-round4/`、`?? docs/execution/reviews/T03-round9/`、`?? docs/execution/reviews/T08-round4/`（首帧另有 `M docs/execution/reports/T08.md`，随后由 T08 会话提交）。**本会话只写 `docs/execution/reviews/T02-round4/`**，收尾自证见 §7。
- 未做（按硬约束/并发会话保护）：`mvn` 与任何写 `backend/target` 的命令；`.work/t08/**`、`tests/engineering/T08/**`、`**/cost/**`、`docs/execution/reviews/T03-round9/`、`docs/execution/reviews/T08-round4/` 未触碰；未 `git add/commit`；未写 `docs/execution/STATE.json`；`tests/engineering/**` 只读（`revision_integrity.py` 的 `--out` 一律指向 `tests/engineering/T02/.work/` 内）。
- 植入/削弱全部在 `$env:TEMP\t02r4\…`（C-1/C-2/C-5/C-7/C-9/C-10/C-12/C-13/J-4）与 `tests/engineering/T02/.work/r4-review-scratch/`（C-3/C-4，需 `relative_to(ROOT)`）内，逐脚本结束时 `shutil.rmtree` 并打印 `scratch removed: True`，总证明见 §7。

## 1. 四项必做控制（本会话独立重做，不采信实施方数字）

### C-1 值豁免不放行整文件 — **通过（7/7）**

[r4_c1_exempt_file.py](r4_c1_exempt_file.py) → 退出 0；证据 [evidence/c1-value-exemption.json](evidence/c1-value-exemption.json)。

| 步骤 | 期望 | 实测 |
|---|---|---|
| canary 形状单独成文件 + 仅默认规则 | 被抓（证明植入物落在默认规则里） | `github-pat` 1 + `private-key` 1，退出 1，`scanned ~198 bytes` ✅ |
| 三份曾被豁免文件副本 + 各植入 2 枚 canary + **交付配置** | 6/6 抓到、无多余 | 6 命中、退出 1、`scanned ~151198 bytes`、命中集恰为 3×{github-pat, private-key}、`extra []` ✅ |
| 同一树 + **无任何 allowlist** | 6 canary + 该三份文件自身 8 条被抑制值显形 | 14 命中、退出 1（6+8）✅ |
| 同一树 + **`deca2a1^` 的原配置**（`git show` 取回，python 写入，无 BOM，1,327 字节，含 3 条 `paths`） | 0 canary，且扫描器自报 0 字节 | 0 命中、退出 0、`scanned ~0 bytes (0)` ✅ 盲区真实复现 |

- 与实施方的差别：他们用正则**重建**一份 legacy 配置；我用**当时真实提交的那份**（`git show deca2a1^:…`），并显式区分「扫了但没抓到」与「根本没扫」——要求报告体存在 + 扫描器自报字节数，否则「0 命中」可能是配置解析失败造成的假绿（我的第一版脚本就因 PowerShell BOM 造成过一次这种假 0 命中，已修）。
- 三份文件原字节合计 **150,604**（128,810 + 7,011 + 14,783）✅ 与整改声明一致。

### C-2 11 个字面量豁免值逐个可证伪 — **通过（44/44 变异变红，0 空转）；另测出对方未做的子串边界**

[r4_c2_falsifiability.py](r4_c2_falsifiability.py) → 退出 0；证据 [evidence/c2-falsifiability.json](evidence/c2-falsifiability.json)。85 个探针，每探针扫两遍（默认 / 交付）。

- 11/11 值在默认规则下**非空转**（每值都能被 `generic-api-key` 报告，行形态 `"docs/api/openapi.yaml": "<值>"`）。
- 原值：11/11 在交付配置下被抑制（gate 退出 0）。
- 变异：每值改 **首 / 中（两个位置 `n//2` 与 `2n//3`）/ 末**，共 **44 个变异全部重新被报**（gate 退出 1）。**中段没有一位改动仍被抑制**（含第 11 条 19 字符形态）→ 重点攻击未获成功，实施方「用完整字面量」的选择成立。
- 语义事实：单块内 6 条 `regexes` 配 `condition = "AND"` 时按**任一命中即抑制**工作（否则单值探针不可能被抑制）→ `AND` 作用于维度之间（paths/commits/regexes），不作用于同维度多条正则。配置注释「every exception below is an exact value」宜补这一句。
- **子串抑制（新发现 A-2）**：10 个长值全部出现「默认规则报告超串、交付配置抑制超串」——被抑制的是**包含**豁免值的串，不只是等于它的串（`ab`+值 / 值+`cd` / 10 位+值+6 位，三种都抑制）。

### C-3 配置不自触发 — **通过（两口径独立复现，且证明中性文件名口径是唯一有效口径）**

[r4_c3_c4_config_and_benign.py](r4_c3_c4_config_and_benign.py)；证据 [evidence/c3-c4-config-and-benign.json](evidence/c3-c4-config-and-benign.json)。

| 口径 | 交付配置 | `deca2a1^` 配置 |
|---|---|---|
| 中性文件名 + 无 allowlist | 2,076 字节 / **0 命中** / 退出 0 | 1,327 字节 / **2 命中** / 退出 1（正是 `Idempotency-Key: …` 与 `key=…` 两行） |
| 原名 `gitleaks.toml` + 无 allowlist | **`scanned ~0 bytes (0)`** / 0 命中 / 退出 0 | 同左：0 字节 / 0 命中 / 退出 0 |

→ 「配置自身 0 命中」只能由中性文件名口径支撑；实施方选了正确口径并在 [T02.md:57](../../reports/T02.md#L57)、[T02-Revision-R02.md:133](../../reports/T02-Revision-R02.md#L133) 写明理由，方法与数字均可复现。**但触发范围他们说窄了**（A-3）：C-7 实测凡路径**含** `gitleaks.toml` 子串者一律 0 字节。
另测得：交付配置里的 64-hex 值不是靠抑制自我豁免，而是 `  '''<hex>''',` 行形态本身不含「关键词 + 赋值 + 值」相邻结构，因此不触规则（§2 J-1 给出反证）。

### C-4 良性半边 — **通过**

同一脚本同一证据。

- 我自己 `--out` 到 gitignore 的 `.work/r4-review-scratch/` 跑 `revision_integrity.py`：退出 0，`271 delivery fingerprints; …`；清单 **271 条 / 47,792 字节**，记录键 `path`/`sha256` 分行。
- 该清单在**完全不配 allowlist** 的空配置下：`scanned ~47792 bytes`、**0 命中、退出 0**；交付配置下同样 0 命中；我自有「关键词 + 32 位以上十六进制同行」检测亦为 `[]` → 不再依赖任何例外 ✅。
- 拒绝覆写冻结件：`--out …r01-integrity.json` → 退出 **1** + `refusing to rewrite frozen evidence record: …`（`r01-integrity-run.json` 同样退出 1）；运行前后 `r01-integrity.json`/`r01-integrity-run.json`/`gitleaks-findings.json`/`gitleaks.toml` sha256 全等（`frozenUnchanged: true`）✅。
- 记录器守卫非空转：`digest_records.write({'docs/api/openapi.yaml': 'ab'*32})` → `AssertionError: fingerprint manifest pairs path and digest on line(s) [2]`；分行记录 `{'path': 'backend/secret-baseline.sql', 'sha256': <64hex>}` → 通过（不误红）✅。
- `integration.py`：`--help` 退出 0；已跟踪 `evidence/integration.json`（75,109 字节）不含 `artifacts` 键（与声明一致）；真实 PG+JVM 链路按约束未跑 → 未证明清单。
- 两处健壮性缺口（A-6）。

### C-6 全树三配置（决定性口径，工件定稿后最后跑）

[r4_c6_full_tree.py](r4_c6_full_tree.py)；证据 [evidence/c6-full-tree-three-configs.json](evidence/c6-full-tree-three-configs.json)。三配置同批、同一棵树：

| 配置 | 命中 | 退出 | 命中分布 |
|---|---|---|---|
| 交付配置 | 0 | 0 | — |
| `deca2a1^` 原配置 | 7 | 1 | `T03-round5/evidence/checks.json` 3、`T07-round4/checks.json` 2、`T03/evidence/session-cookie-r04.json` 2 |
| 无任何 allowlist | 15 | 1 | 上述 7 + `r01-integrity.json` 6 + SRS 1 + `T04/evidence/integration.json` 1 |

账目闭合：7 + 8 = 15；15 由 11 个字面量覆盖；交付配置 0/退出 0 → **判决 F-01 与整改声明「15 条 / 差额 150,604」在字节级对齐**，且我复现的是**当时真实提交的配置**，不是重构版。

扫描输入集随工作树变动（见 A-5），故本节只断言**编辑不变量**：命中数 **0 / 7 / 15** 与两个差值。逐文件字节数与 `scanned` 总值记在证据 `inputSet` / 各配置 `scanned` 字段里；本文件每改一个字节，总值随之变化，但下面两个差值不受影响（我的文件既非二进制、也不在被整文件跳过的三份之内，改动同时进入复制量与扫描量）：

- **复制总字节 − 默认/交付配置 `scanned` = 148,267 字节** = gitleaks 判定为二进制而跳过的字节（复制量由我逐文件求和，扫描量由扫描器自报 → 两个来源互不依赖）。
- **交付/默认 `scanned` − 原配置 `scanned` = 150,604 字节** = 原配置按 `paths` 整文件跳过的三份文件之和；我在 C-1 用 `os.stat` 逐份量得 128,810 + 7,011 + 14,783 = 150,604 ✅ 与整改声明一致。

所以整改声明里的 **150,604** 与「二进制未读 148,267」都由我独立算出；不成立的是把绝对总字节当结论数字（A-5）。

### C-15 复审工件自己也踩了同一条根因（过程事实，非被审缺陷）

- 我第一次把全树数字写进 `review.md` 时，正文里**连写**了那个 20 字符 AKIA 形态实例 → 交付配置立即报 **1 命中 / 退出 1**（文件是我自己的 `review.md`，规则 `aws-access-token`）。
- 同一轮我的 `c6` 证据把冻结哈希写成 `{"docs/api/openapi.yaml": "<64 hex>"}`（路径与摘要同行）→ 默认规则配置报 **1 命中 / 退出 1**（规则 `generic-api-key`），而这形状与被撤回的 F-03 根因**完全同类**；同一形状被我自己的行配对检测器（`r4_c3_c4…` 的 `paired_lines`，即 `digest_records` 的判定形）在已跟踪的 `evidence/integration.json` 上标出 1 处（第 13 行 `--pwfile=…\init-password`，路径含 `api` 子串 + 32 位十六进制）。
- 我的处置顺序：**先改自己的工件**（打断键形写法、把哈希改成 `path`/`sha256` 分行记录），**再重跑**——不新增豁免、也不动配置。复跑结果：我的目录在**默认规则**下 `0 命中 / 退出 0`（此前 1 命中），交付配置同样 0 命中；全树三配置回到 `0 / 7 / 15`。口径说明：`c6` 在三次扫描**之后**才写自己的证据文件，所以最后一轮全树扫描含上一轮的（已分行）证据与最终定稿前的 `review.md`；定稿后再由 `r4_selfscan.py` 单独复扫我的整个目录（两种配置，含最新 `c6` 输出）确认 0 命中。证据：[evidence/c0-reviewer-self-scan.json](evidence/c0-reviewer-self-scan.json)（收尾复扫 `reviewerDirDefaults.count: 0`）、[evidence/c14-reviewer-hygiene.json](evidence/c14-reviewer-hygiene.json)（`liveShapes: []`）、[evidence/c6-full-tree-three-configs.json](evidence/c6-full-tree-three-configs.json)。
- 这条过程事实的意义：它独立佐证 F-03 的根因判定与 A-2/A-4 的边界——**任何人**（包括复审者）在新文件里把「关键词路径 + 长摘要」写在同一行，都会立刻需要一个新增豁免；分行记录是唯一不需要例外的形状。因此 A-9 建议把配对检测前移成门。

### C-7 / C-9 规则形态补充（判定 J-2 用）

[r4_c7_rule_shape_probes.py](r4_c7_rule_shape_probes.py)、[r4_c9_default_rule_gaps.py](r4_c9_default_rule_gaps.py)；证据 [c7](evidence/c7-rule-shape-probes.json)、[c9](evidence/c9-default-rule-gaps.json)。要点：RSA/OPENSSH/PKCS8/EC 私钥块（体 ≥2 行）全部被默认 `private-key` 抓（仅头部无体不抓）；裸 `AKIA…` 被 `aws-access-token` 抓；`password=`/`DB_PASSWORD=` 短口令不被任何默认规则抓；含 `/` 的 40 字符 AWS 风格 secret 不抓、同长无 `/` 者抓（示例值含 `EXAMPLE` 亦不抓）；JWT Bearer 串不抓；PNG 里的 canary 不抓（二进制跳过），但 `secret_scan.py` 的字节级模式抓到。

### C-10 「首尾定长 + 中段通配」反驳是否成立 — **成立**

[r4_c10_wildcard_shape.py](r4_c10_wildcard_shape.py)；证据 [c10](evidence/c10-wildcard-shape-comparison.json)。同一批探针、两种配置（交付=完整字面量；TEMP= `头8.{48}尾8`）：8 个长摘要值上，**中段改一位在通配形态下 8/8 仍被抑制**，在交付形态下 8/8 重新被报；首/末改动两种形态都报 → 主 agent 建议的形态确实会把「中段改一位」这一必须响亮失败的控制变成哑铃；实施方的拒绝与理由正确。

### C-12 / C-13 加固方案实测（供 A-2 使用，非缺陷判定）

- C-12 [r4_c12_anchoring_remedy.py](r4_c12_anchoring_remedy.py)：`'''^值$'''` **不可用**——11/11 的精确值也不再被抑制（`regexTarget = "match"` 测的是整条匹配文本 `api_key = "<值>"`，不是捕获组）。这条否定结果避免我给出一条错误建议。
- C-13 [r4_c13_word_boundary_remedy.py](r4_c13_word_boundary_remedy.py)：`'''\b值\b'''` 对 **10/11** 有效（精确值仍抑制、三种超串全部重新被报）；第 11 条（19 字符 `…前缀...`）因结尾是字面点、`\b` 不成立而失效，需改用 `(?<![0-9a-f])…(?![0-9a-f])` 之类否定环视或保留不锚定（该条要求串里含真实 `...`，风险最低）。

## 2. 额外必须判定项（逐项结论）

### J-1 值豁免固有边界 — **可接受代价，但必须按「值 + 子串」双口径写进报告**

探针：[evidence/c5-j1-j2-boundaries-and-gaps.json](evidence/c5-j1-j2-boundaries-and-gaps.json)。

- **11 个值里没有任何一条是真凭据**：2 条 UUID（SRS 公开示例 `Idempotency-Key` 值、已删除 T04 测试对象 id）+ 8 条完整 SHA-256（r01 清单摘要、两个冻结契约文件摘要）+ 1 条前缀形态。全部为内容派生摘要或公开示例，不是任何系统的口令/令牌。
- **但它们在真实凭据位置上会被静默抑制**（实测）：`aws_secret_access_key = "<豁免摘要>"` → 默认规则 1 命中/退出 1，交付配置 **0 命中/退出 0**；`secret_key: <豁免 UUID>` 同样 1→0。同一行改一位的近邻：两种配置都 1 命中/退出 1 → 抑制确实是「按值」，不是「按位置/按文件」。
- 边界比实施方自报的更宽一层：由 C-2 可知被抑制的是**包含**该值的串（值豁免 = 子串豁免）。所以「任何人把同一示例 UUID 复制进新文件会被抑制」（[T02-Revision-R02.md:166](../../reports/T02-Revision-R02.md#L166)，即其「仍未证明」第 5 条——派单里写作第 6 条，序号需更正）之外，还应写明「把该值嵌进更长 token 也会被抑制」。
- 附带自证（复审自身也吃到这条边界）：我在 `evidence/c8-*.json` 里原样引用了那个 20 字符示例键的连续形态，`aws-access-token` 会把我的复审目录变成命中对象；我按规则**打断自己的文本**而不是新增豁免（lint 证据 [c14](evidence/c14-reviewer-hygiene.json) `liveShapes: []`）。这条实证支持整改方在 R02:163 的判断：文档里写全示例键会成为扫描对象。
- 结论：**判为可接受代价**（真实凭据须等于或包含一条公开摘要才能逃逸，机制上窄且被双向控制），但报告必须把它写成显式风险边界（含子串口径 + `*gitleaks.toml*` 文件名口径 + 「0 命中不证明无密钥」三件），并可选落实 C-13 的一行加固。**不得**为消除该边界而新增任何豁免。

### J-2 规则覆盖缺口 — **「0 命中」不能支撑「基线无密钥」；但被引用的实测有一半是错的**

- 实测确认的默认规则缺口（gitleaks 8.30.1，`useDefault = true`，无 T02 例外）：`password = <短口令>`、`DB_PASSWORD=<短口令>`、含 `/` 的 40 字符 AWS 风格 secret、JWT Bearer 串、二进制文件内的明文 canary、`.gitignore` 排除的路径（输入集外）、路径名含 `gitleaks.toml` 的文件。
- 实测**推翻**两条既有记载：裸 `AKIA` + `QWERTYUIOPASDFGH`（20 字符连写，此处用 ` + ` 分隔以免本文件自触发）**被 `aws-access-token` 抓到**；带关键词的 `aws_access_key_id = AKIA…` 也抓到。故「默认规则漏裸 AKIA」（第三轮 `review.md` 正向控制段、[T02-Revision-R02.md:164](../../reports/T02-Revision-R02.md#L164) 第 3 条）不成立——那是把「模式串」当「实例串」测出来的假阴性；`wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` 不被抓的原因是值里含 `EXAMPLE`（规则 stopwords）与 `/`，不是「AKIA 形态整体漏」。
- 本文件自己就撞过一次：初稿把上面那串 20 字符连写原样写出，交付配置对 `docs/execution/reviews/T02-round4/review.md` 报 **1 命中 / 退出 1**（C-6 第一次运行实测）；我按规则**打断复审文档自身**（而不是新增豁免，也无权新增）后回到 0 命中。这正是 J-1 与 R02:163 所说边界的现场版本。
- 判定口径：现报告用词是「`no leaks found`／0 命中／无命中」+ R02:164 的「不能证明不存在性」，**没有**出现「基线无密钥」这类不存在性断言（我逐行查了 [T02.md](../../reports/T02.md) 与 [T02-Revision-R02.md](../../reports/T02-Revision-R02.md) 中含「密钥/secret/0 命中」的行）→ 表述目前不越界。要改的是：(i) 更正 R02:164 的 AKIA 半句（P2，记录错误，不是实现缺陷）；(ii) 在 `T02.md`「gitleaks 例外的真实语义」一节补一段**覆盖边界**（列上面缺口 + C-6 的 148,267 字节二进制未读）；(iii) 任何下游卡若要写「无密钥」，必须同时给出规则集与输入集。

### J-3 主 agent 的 `secret_scan.py` — **「值豁免覆盖到台账与扫描器自身」判为正确取舍**

[r4_j3_secret_scan.py](r4_j3_secret_scan.py)；证据 [c8-j3-secret-scan-exemption.json](evidence/c8-j3-secret-scan-exemption.json)。

| 检查 | 期望 | 实测 |
|---|---|---|
| `secret_scan.py --self-test` | 退出 0 | 退出 **0**：`10 fixtures and 1 exemptions agree` ✅ |
| `secret_scan.py`（真实扫描，当前树） | 退出 0 | 退出 **0**：`Secret pattern scan: no matches` ✅（第三轮 F-06 转绿） |
| 内存清空 `EXEMPT_VALUES` 后扫描 | 必报 3 个文件 | 恰报 3：`S3ProtocolRegressionTest.java`、`docs/execution/STATE.json`、`tests/engineering/T02/secret_scan.py`；5 处命中全为 pattern 索引 1（AKIA）、`matchedLen 20`、`isExemptValue: true` ✅ |
| 近邻 `AKIA` 必被抓 | 抓 | 尾字符改位的 `AKIA…EXAMPL``F` 与另一 AKIA 形态夹具均 flagged=True ✅ |
| fixture 是否仍在源码内留活形状密钥 | 不留 | 四个模式与近邻夹具都是运行时拼接；全树扫描 0 命中即含此文件本身 → 源码里没有可被自家规则命中的连续键形 ✅ |
| 破坏性变体（证明 self-test 非装饰） | — | 把抑制改成 `startswith`（前缀匹配）→ **self-test 仍退出 0** ⚠️；把抑制改成 `False` → self-test 退出 **1** 并指名两条断言 ✅ |

- 判定理由：路径/目录豁免正是第三轮刚撤回的错误，`EXEMPT_VALUES` 只按被匹配字节是唯一不退回到那类错误的选项；台账与扫描器自身留在输入集内（自我暴露）比把它们踢出扫描范围更安全；被抑制的值是 AWS 官方文档公开的 SigV4 测试向量，且在 `STATE.json` 里出现的正是「记录这条豁免」的文本本身。若改为「文档内打断键形状」，台账会失去可机读的原值引用、而打断形态仍是同一个键的另一种写法，且下次引用该值的人还会再犯——所以现方案优于替代方案。
- 两点必须转给主 agent 的收紧建议（不是缺陷，P3）：(i) `--self-test` 对「豁免被改成前缀/子串匹配」不敏感（实测 `exemptByPrefix` 退出 0）。在当前 4 个模式（`\b` 锚定 + 定长）下不可利用，但模式一旦扩到无边界形态即成真实盲区 → 补一条「相等才抑制」夹具；(ii) `EXEMPT_VALUES` 的 justification 应带来源链接（公开文档 URL），否则下一轮无法在不查网的情况下判断该值是否真的公开。

### J-4 T07 不变式 — **方向正确且安全上更强，但不是「严格更强」；常年红的门等于没有门；基线重录列为 T07 下一轮必交付**

[r4_j4_t07_gate_semantics.py](r4_j4_t07_gate_semantics.py)；证据 [c11-j4-t07-gate-semantics.json](evidence/c11-j4-t07-gate-semantics.json)；`git show 0b2a6f8 -- tests/engineering/T07/verify_delivery.py` 显示旧断言为 `[x for x in finding_paths if x != BLESS]` + `len(finding_paths) != 6`，新断言为 `unexpected = list(finding_paths)` + `if unexpected: failures.append(...)`（现位于 :51-56）。

| 场景（同一份扫描结果，交付配置） | 旧断言 | 新不变式 |
|---|---|---|
| A 无命中（今天真实树形） | **FAIL**（0 ≠ 6） | PASS |
| B 在被祝福文件里植入 1 条 | FAIL | FAIL |
| C 在被祝福文件里植入 **6 条真 canary** | **PASS** ← 这正是它的漏洞 | FAIL |

- 结论 1：两个谓词**互不蕴含**（A 旧红新绿，C 旧绿新红），所以不能称「严格更强」；但就安全性质而言新形式正确——「任何存活命中即失败」是规则，「恰 6 条且在某文件」是快照。主 agent 的论证（快照会在 T02 合法修好基线时自己断裂，且 6 条真密钥也能过）由场景 C 实测成立。**不会过严误红**：当前全树 0 命中 → 新不变式为绿。
- 结论 2（新形式的残余弱点，必须记录）：**0 命中不可与「扫描失明」区分**。这一性质不在 T07 门里，而由 `check_gitleaks_allowlists.py --with-controls` 的正向 canary 承担；而该控制在 CI 上目前跑不起来（A-1）→ 所以现在 CI 里没有任何东西替 T07 兜住「扫描器仍然看得见」。修法二选一：CI 修好 A-1，或让 T07 门额外断言 `scanned bytes > 0` / 自带一枚 canary。
- 结论 3（过严误红的真实来源）：T07 门扫的是**工作树**（`git ls-files --cached --others --exclude-standard`），因此其它卡片未跟踪的在制品（今天实测存在 `.tmp_t08fix.py`、`T03-round9/`、`T08-round4/`）一旦含「关键词 + 长十六进制」行就让 T07 变红；C-6 显示无 allowlist 时 15 条命中里有 12 条在 T07 之外的文件。属可接受的耦合代价（这正是它该管的事），但口径要写「T07 门的命中集是全工作树，不是 T07 自有文件」。
- 结论 4（常年红的门）：`tests/engineering/T07/evidence/r02-secret-invariant-check.json` 记录 `scanExit 0 / findingPaths []`，而 `failures` 仍有 4 条：`git apply --check` 三个 patch（`T07/t06-extension.patch`、`T07/composition-root.patch`、`T06/shared-integration.patch`）+ `existing files changed`（`changedInputs` 实测 200，基线 `inputCount` 1151）。**判定：一个退出码恒非零、且红的原因与所验性质无关的门，在实践中等于没有门**——它教给读的人是「忽略这个门」。因此：
  1. **基线与 patch 重录应列为 T07 下一轮必交付**（排期优先级 P1，但属 T07 卡职责，不是被审 T02 整改的缺陷）；重录之前 T07 的退出码不得被任何报告当作验收依据引用；
  2. 主 agent 已在提交说明与 `STATE.json` 里如实标注该门另有 4 项失败源于基线陈旧，未掩埋 → 诚实度合格（见 J-6）。

### J-5 CI 三条新命令 — **本地全部实跑通过；在 runner 上第三条必然崩溃并取消其后 4 条命令（A-1，P1）；不会静默跳过；结构模式可独立承重「形状」半边**

本地实测（Windows / 仓库根 / 工作目录=ROOT）：

| 命令 | 结果 |
|---|---|
| `secret_scan.py --self-test` | 退出 0（J-3 表） |
| `check_gitleaks_allowlists.py`（结构模式，无二进制） | 退出 **0**，16 条结构断言全 PASS，尾行 `PASSED (structure only)` |
| `check_gitleaks_allowlists.py --with-controls --gitleaks .tools/t02/gitleaks/gitleaks.exe` | 退出 **0**，88 条断言全 PASS（正向 6、盲区 3、反向 33/33 与 exact 11、良性 4、scratch 删除 1），`GITLEAKS ALLOWLIST POLICY: PASSED` |
| `scan_secrets.py --gitleaks .tools/t02/gitleaks --report .work/…` | 退出 0（与 CI 的 L62 同参数写法；本地该路径是目录 → 见下） |

runner 侧判定（静态推导 + 本地失败类比；未在真实 Actions 上跑，列入未证明清单）：

1. `ci.yml:35-37` 下载 `gitleaks_8.30.1_linux_x64.tar.gz` 并 `tar -xzf … -C .tools/t02` → 释出**单个文件** `.tools/t02/gitleaks`（同一 workflow 的 `ci.yml:62` 正是按这个路径调用，第三轮亦核过）。因此 `ci.yml:60` 的 `.tools/t02/gitleaks/gitleaks.exe`（既带 Windows 扩展名、又把它当目录用）在 ubuntu runner 上**不可能存在**。
2. 该脚本对 `--gitleaks` **不做存在性检查**，直接 `subprocess.run([scanner,'version'])` → 抛 OSError（`FileNotFoundError` / Linux 上 `ENOTDIR`），**未捕获 → traceback → 退出 1**。本地类比实测：`--gitleaks .tools/t02/gitleaks`（目录）→ 退出 1，`PermissionError: [WinError 5]`；`--gitleaks …gitleaks.exe.missing` → 退出 1，`FileNotFoundError: [WinError 2]`；`scan_secrets.py --gitleaks <目录>` → 退出 1。两次运行后 `.work/allowlist-controls` 与探针报告均 `Test-Path False`（崩溃发生在建 scratch 之前，无残留）。
3. 后果不是「静默跳过」也不是「装饰性绿」，而是**响亮的全灭**：该步以 `run: |` 多行执行，GitHub Actions 默认 `bash -e`，第 3 条命令崩溃后**其后的 `secret_scan.py` 真实扫描、`scan_secrets.py` 全树 gitleaks、`dependency_scan.py`、`npm --prefix frontend audit` 永不执行**。即 CI 的密钥与依赖扫描能力当前等于 0。
4. 结构模式能否独立承重：**能承「形状」半边**——它证明配置无文件条件、11 条例外皆为无通配字面量、`useDefault` 未被替换、条数钉死；这些不需要二进制。**不能承「有效性」半边**——canary 是否被抓、变异是否变红、良性清单是否 0 命中只能在有 gitleaks 时证明。CI 现在两条都写了，但第二条不可执行 → 实际只剩结构半边。
5. 建议（最小改动，任选其一并实测）：把 L60 的 `--gitleaks` 改为与 L62 相同的 `.tools/t02/gitleaks`，并让脚本在传入目录时自动在该目录下找 `gitleaks`/`gitleaks.exe`（本地与 runner 同一条命令可跑）；或安装步骤把释出的二进制复制到稳定名。同时把 controls 一步**移到两条真实扫描之后**或拆成独立 step，避免一条崩溃掩盖其余四条。另注：`ci.yml:62` 沿用默认报告路径，会在本地复跑时写已跟踪的 `evidence/gitleaks-findings.json`（`--report` 已提供出口，CI 里不改无危害，但报告口径应写明）。

### J-6 诚实度抽核 — **合格；两处序号/精度需更正**

- 撤回是否在原位：**是**。[T02.md:113](../../reports/T02.md#L113) 在命令表行内就地标「**撤回（R02c…）**」并给出证伪数据与整改后数字；[T02.md:135](../../reports/T02.md#L135) 在异常史第 6 条就地标「**本条后半句撤回（R02c，2026-10-08）**」，并写明「本条只保留『首次命中』与『原命中记录已脱敏』两项事实」。第三轮点名的 `T02.md:115`（旧「未豁免目录或真实密钥」句）正是这条被标注的行。另 [T02.md:32](../../reports/T02.md#L32) 也给 `revision_integrity.py` 的输出格式变化加了「R02c 注」，处理一致。
- 残留未标注表述：仅找到一处同类问题的**处理不一致**（A-7）——[T02.md:30](../../reports/T02.md#L30)「`secret_scan.py` … 无命中」这行在第三轮 F-06 被证伪、现由主 agent 以值豁免恢复为真，但该行没有像 :113/:135 那样就地标注这段历史。数字精度问题见 A-5（`2,411 个可见文件`、`37,078,079` 字节为运行时量，我实测同一命令得 2,242 个列项 / `scanned ~37,647,470`，稳定量只有 150,604 差额与 0/7/15 命中数）。
- 整改方反驳主 agent 建议（「首尾定长 + 中段通配」会被中段改一位仍抑制）：**成立**，C-10 实测 8/8。
- 序号更正：派单说「实施方在『仍未证明』第 6 条自报值豁免固有边界」——实际是**第 5 条**（[T02-Revision-R02.md:166](../../reports/T02-Revision-R02.md#L166)）；第 6 条是「输入集由 `git ls-files` 决定」（:167）。
- 主 agent 侧：`0b2a6f8` 提交说明与 `STATE.json` 都如实记录「值豁免覆盖到台账与扫描器自身」是**取舍**，并写明「若某天需要报告『无密钥』，必须先补规则覆盖缺口而不是删掉这条命中」，与我 J-2/J-3 的结论同向；同时主动披露 T07 门另有 4 项失败源于基线陈旧 → 无掩埋。

## 3. 第三轮 F-01…F-05（含 F-06）逐条闭合判定

| 编号 | 第三轮内容 | 本轮判定 | 我的依据（退出码） |
|---|---|---|---|
| **F-01** | CI 等价全量扫描退出 1、7 条命中，R02 验收第 2 条未满足 | **CLOSED** | C-6：交付配置 **0 命中 / 退出 0**；`deca2a1^` 配置复现 **7 命中 / 退出 1**；`scan_secrets.py --report .work/…` 退出 0 |
| **F-02** | 例外实为整文件豁免，值条件从不求值 | **CLOSED**（缺陷真实存在，非伪证） | C-1：交付配置 6/6 canary 全抓、退出 1；原配置 `scanned ~0 bytes (0)`、0 canary、退出 0；结构断言 `paths` 出现次数 0；`--with-controls` 88 条全 PASS |
| **F-03** | 根因（路径与摘要同行）未修，逐值例外不可持续 | **CLOSED** | C-4：271 条分行清单在**无 allowlist** 下 0 命中/退出 0；`digest_records` 对同行布局抛 `AssertionError`、对分行不误报；`integration.py` 同记录器；C-6 里 15→0 全由 11 个值解释，未新增任何文件级豁免 |
| **F-04** | 例外改动使 T07 交付门自身失效 | **CLOSED（就性质不匹配而言），转化为新的排期项** | J-4：新不变式在当前扫描（`scanExit 0 / findingPaths []`）下绿；场景 C 证明旧式会放行 6 条真密钥；剩余 4 条失败为基线/patch 陈旧 → **T07 下一轮必交付：重录 input 基线与三个 patch**；另记录「0 命中无法区分扫描失明」的残余弱点 |
| **F-05** | `scan_secrets.py` 把报告写进被跟踪证据原件 | **CLOSED（带残余）** | `scan_secrets.py:12-14` 新增 `--report`，默认值未变（CI 行为不变）；我全程用 `--report` 指到 `.work`，`gitleaks-findings.json` 哈希 `37517e5f…` 不变。残余：CI 仍用默认路径 + 生成器 `FROZEN` 不含该文件（A-6） |
| **F-06** | 同一 CI 步骤第一条命令 `secret_scan.py` 退出 1 | **CLOSED** | J-3 表：真实扫描退出 **0**、`--self-test` 退出 0；清表必报 3 文件，证明抑制面恰为那一个公开示例值 |

## 4. 发现清单（P0–P3）

| 编号 | 级别 | 内容 | 最小复现（第三方可直接跑） | 期望 / 实际 |
|---|---|---|---|---|
| **A-1** | **P1** | `ci.yml:60` 的 `--gitleaks .tools/t02/gitleaks/gitleaks.exe` 在 `ubuntu-24.04` 上不可能存在（linux tar 释出 `.tools/t02/gitleaks` 单文件），脚本对 `--gitleaks` 无存在性检查 → 整步 traceback 失败，其后 `secret_scan.py`/`scan_secrets.py`/`dependency_scan.py`/`npm audit` 四条命令全部不执行 → CI 密钥与依赖扫描能力当前为 0 | 静态：读 `ci.yml:35-37` 与 `:60`/`:62` 路径形态；动态类比（本地）：`$py tests/engineering/T02/check_gitleaks_allowlists.py --with-controls --gitleaks .tools/t02/gitleaks` | 期望：三条新命令在 runner 上均可执行且退出 0；实际：本地类比 **退出 1（未捕获 OSError）**，Linux 上为 `ENOTDIR`/`ENOENT` 同形失败；**未**在真实 runner 验证 |
| **A-2** | P2 | 值豁免实际是**子串**豁免：包含豁免值的更长 token 同样被抑制（10/10 长值实测）；`condition = "AND"` 的跨维度语义也未写进配置注释 | `$py docs/execution/reviews/T02-round4/r4_c2_falsifiability.py`（`substringSuppressed`）→ 退出 0；加固实测：`r4_c13_word_boundary_remedy.py`（10/11 有效）、`r4_c12_anchoring_remedy.py`（`^$` 方案 **失败**） | 期望：抑制面 = 恰该值；实际：抑制面 ⊇ 含该值的串。要求写进报告风险边界；可选按 C-13 用 `\b`（第 11 条需否定环视）；**不得**新增豁免 |
| **A-3** | P2 | 「gitleaks 会跳过名字**恰为** `gitleaks.toml` 的输入」范围说窄：凡路径**含** `gitleaks.toml` 子串者一律不读（`sub-gitleaks.toml`、`.gitleaks.toml`、`gitleaks.toml.bak` 实测 `scanned ~0 bytes (0)`；同字节改名 `plain.txt` 即 1 命中）。真凭据若写进仓库根 `.gitleaks.toml`，gitleaks 侧永久不可见（`secret_scan.py` 的 4 模式仍能抓 `ghp_`/`sk-`/PEM/AKIA） | `$py docs/execution/reviews/T02-round4/r4_c7_rule_shape_probes.py` → `nameContainsGitleaksToml`；`r4_c3_c4_config_and_benign.py` → `c3.filenameExceptionProbe` | 期望：口径为「名字含 `gitleaks.toml` 的文件整体退出扫描，由 `secret_scan.py` 部分兜住」；实际现文写「恰为」→ 需更正（表述问题，非实现缺陷） |
| **A-4** | P2 | 「0 命中」不能支撑「无密钥」类措辞；且被引用的实测有一半错：**裸 `AKIA…` 实际被 `aws-access-token` 抓到**，第三轮与 `T02-Revision-R02.md:164` 的「漏裸 AKIA」为假阴性记载；真正漏的是 `password=`/`DB_PASSWORD=` 短口令、含 `/` 的 40 字符 AWS 风格 secret、JWT、二进制内明文、被 gitignore 的路径、`*gitleaks.toml*` 文件 | `$py docs/execution/reviews/T02-round4/r4_c9_default_rule_gaps.py`；`r4_c7_rule_shape_probes.py`；`r4_c6_full_tree.py`（148,267 字节二进制未读） | 期望：更正 R02:164 的 AKIA 半句 + 在 `T02.md` 补一段覆盖边界；实际现文含不可复现的「实测」句且缺口径 → 表述问题，按 P2 |
| **A-5** | P3 | 报告把**运行时量**当结论数字：`2,411 个可见文件`、`36,927,475 / 37,078,079 / 37,081,945 bytes` 随未跟踪文件集变动（我三次实测：前段 2,187 项 / `scanned ~37,647,470`；本段 2,261 项 / `scanned ~38,113,037`；`git ls-files` 列项在会话中从 2,242 涨到 2,261 因并发会话提交）；只有 **150,604 与 148,267 两个差值**、以及 **0/7/15** 命中数是稳定量 | `$py docs/execution/reviews/T02-round4/r4_c6_full_tree.py`（`inputSet` 与三次 `scanned`；§1 C-6 给出两差值的独立算法） | 期望：写成「命中数 + 两个差值 + 输入集定义」；实际写绝对总字节 → P3 措辞 |
| **A-6** | P3 | 冻结保护有覆盖与形态缺口：`revision_integrity.py:21-22` 的 `FROZEN` 只含两份 r01 记录，本轮要求字节不变的第三份 `evidence/gitleaks-findings.json` **不在保护内**（`--out` 指它就会覆盖——我只读推导，未做破坏试验）；`--out` 指向仓库外路径得 `ValueError` 裸 traceback（退出 1）而非明确拒绝 | `$py docs/execution/reviews/T02-round4/r4_c3_c4_config_and_benign.py` → `c4.guardCoverageByDerivation`、`c4.outsideRepoOut` | 期望：拒绝消息含「路径必须在仓库内」；实际 `ValueError: … is not in the subpath of …` → P3 |
| **A-7** | P3 | 同类被证伪表述处理不一致：`T02.md:30`（`secret_scan.py` 退出 0「无命中」）在第三轮 F-06 曾被证伪、现由主 agent 值豁免恢复，但未像 `:113`/`:135`/`:32` 那样就地标注 | 读 [T02.md:30](../../reports/T02.md#L30) 与 [T02.md:113](../../reports/T02.md#L113) 对照；恢复证明见 J-3（退出 0） | 期望：一行就地注记 + 指向 `0b2a6f8`；实际缺 → P3 |
| **A-8** | P3 | 结构断言口径易误读：`check_gitleaks_allowlists.py:69-70` 把第 11 条例外（剥掉转义后为 19 字符「16 位前缀 + 三个字面点」）判入「one literal value with no wildcard」。判定本身安全（真通配 `.*` 会被同一断言拒），但标签让人误以为 11 条全是定长摘要 | 读 `check_gitleaks_allowlists.py:34,69-70`；运行结构模式可见第 16 条断言 `[19]` | 期望：注释区分「完整字面量」与「含转义点的字面量」；实际标签笼统 → P3 |
| **A-9** | P3 | 「配对形状」没有前置门：F-03 的根因（路径与摘要同行）只在**已经出现命中**时才由豁免或整改处理，任何新文件写出同一形状都要再补一条值豁免。现成检测器已存在但未被任何门调用——`digest_records.violations()`。本卡的直接复现：我的 `c6` 证据初稿 `{"docs/api/openapi.yaml": "<64 hex>"}` 在默认规则下立即 1 命中/退出 1（见 C-15），改成 `path`/`sha256` 分行后同样扫描 0 命中 | `$py docs/execution/reviews/T02-round4/r4_c3_c4_config_and_benign.py`（`paired_lines` 在已跟踪 `evidence/integration.json` 上标出 1 处）；`$py docs/execution/reviews/T02-round4/r4_c6_full_tree.py` + `r4_selfscan.py`（我的目录从 1 命中变 0 命中） | 期望：CI 对已跟踪证据跑一次配对检测（命中即红并指名行号），使这类写法在落地那一刻失败；实际无此门 → P3 建议（非被审实现的缺陷，属下一轮加固） |

无 P0。被审整改的安全实质（盲区关闭、例外只按值、根因改分行、冻结件与 rc.3 契约不动）经我独立重做全部成立。

## 5. 未证明清单

1. **未在真实 GitHub Actions runner 上复跑**：A-1 的 Linux 侧结论由「同 workflow 内 `ci.yml:62` 的路径形态 + tar 包布局 + 本地 OSError 类比」静态推导；Linux 上具体 errno 未实测。
2. **gitleaks 上游语义未取文档**：`paths` 整文件跳过、allowlist `condition` 跨维度、`regexTarget = "match"` 匹配整条匹配文本（C-12 反证）、`*gitleaks.toml*` 内置例外、二进制跳过、规则 stopwords——均为本机 8.30.1 行为证据，未取上游源码/文档；版本升级需重跑 `--with-controls`。
3. **真实集成链路未跑**：`integration.py`（PG + 打包 JVM）与 `compose_smoke.py` 只验到「可导入 / `--help` 退出 0 / 记录器形态」；`mvn`、`backend/target` 写入、Docker 路径按硬约束未执行，故 `artifacts` 分行输出没有端到端证据。
4. **T07 门我未实跑**：`verify_delivery.py` 会写 `tests/engineering/T07/evidence/`（越出我的可写范围），只做「读旧新断言 + 用交付配置在等价探针形态上重放两谓词」（C-11）；「4 项陈旧失败」引用被审提交自带的 `r02-secret-invariant-check.json`；基线漂移规模（200/1151）未独立重算。
5. **其它卡是否也隐含「6 条」或密钥扫描期望**：本轮只核到 T07（已改）；`tests/engineering/integration/verify_boundaries.py` 等未跑、未全仓清点。
6. **子串抑制的实际可利用性**：证明了机制存在（C-2/C-13），未评估既有真实形态或供应链侧依赖把公开摘要嵌进 token 的概率。
7. **11 个值在外部系统是否仍为有效凭据**：只依据仓库内文本与公开文档属性判断，未做（也无法做）外部核验。

## 6. 需要主 agent 代跑的精确命令（本会话受只读/禁写约束者）

```powershell
$py = 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
cd E:\project\codex\wxAgent

# 1) A-1：CI 第三条命令改为跨平台路径后复跑（本地两种形态都应退出 0）
git show 0b2a6f8:.github/workflows/ci.yml            # 核 L60 是否与 L62 一致
& $py tests/engineering/T02/check_gitleaks_allowlists.py --with-controls --gitleaks .tools/t02/gitleaks
& $py tests/engineering/T02/check_gitleaks_allowlists.py --with-controls --gitleaks .tools/t02/gitleaks/gitleaks.exe

# 2) T07 门实跑（会写 tests/engineering/T07/evidence/，复审方无权）：先重录基线与 3 个 patch，再读退出码
& $py tests/engineering/T07/verify_delivery.py --evidence-name r04-t07-gate-recheck

# 3) 全树扫描写默认已跟踪报告（会覆盖 evidence/gitleaks-findings.json，复跑前请留存）
& $py tests/engineering/T02/scan_secrets.py --gitleaks .tools/t02/gitleaks/gitleaks.exe

# 4) 真实集成链路（需本机 PG/JVM；复审方受禁 mvn / 禁写 backend/target 约束未跑）
& $py tests/engineering/T02/integration.py --pg-bin .tools/t02/postgresql-full/pgsql/bin --java .tools/t02/jdk-21.0.12.1+1/bin/java.exe --evidence-name r04-integration-recheck

# 5) 是否正式产出 r02 完整性清单（会新增未复审证据，需你决策）
& $py tests/engineering/T02/revision_integrity.py

# 6) 可选加固（A-2）：先实测再改配置，勿新增豁免
& $py docs/execution/reviews/T02-round4/r4_c13_word_boundary_remedy.py
```

## 7. 收尾自证

### 7.1 判决与必改项

判决 **CHANGES_REQUIRED**。必改（合入前）只有 A-1 一项：CI 第三条命令在 runner 上不可执行且会取消其后 4 条扫描。A-2…A-8 是表述/加固类，应在同一轮把口径改对（尤其 R02:164 那句不可复现的「实测」），但不构成实现缺陷。**无需新增任何豁免**。

### 7.2 工件清单（本会话产出的全部证据，均在本目录内）

| 探针/脚本 | 证据 | 实测退出 |
|---|---|---|
| `r4_tree_scan.py`（前段） | `evidence/c-tree-scan-summary.json` | 0（数字已被 C-6 取代） |
| `r4_c1_exempt_file.py` | `evidence/c1-value-exemption.json` | 0（7/7 判定） |
| `r4_c2_falsifiability.py` | `evidence/c2-falsifiability.json` | 0（11 exact + 44 变异 + 子串表） |
| `r4_c3_c4_config_and_benign.py` | `evidence/c3-c4-config-and-benign.json` | 0 |
| `r4_c6_full_tree.py` | `evidence/c6-full-tree-three-configs.json` | 0（0/7/15） |
| `r4_c5_boundaries_and_gaps.py` | `evidence/c5-j1-j2-boundaries-and-gaps.json` | 0 |
| `r4_c7_rule_shape_probes.py` | `evidence/c7-rule-shape-probes.json` | 0 |
| `r4_c9_default_rule_gaps.py` | `evidence/c9-default-rule-gaps.json` | 0 |
| `r4_c10_wildcard_shape.py` | `evidence/c10-wildcard-shape-comparison.json` | 0（反驳成立） |
| `r4_c12_anchoring_remedy.py` | `evidence/c12-anchoring-remedy.json` | 0（记录的是**否定**结果） |
| `r4_c13_word_boundary_remedy.py` | `evidence/c13-word-boundary-remedy.json` | 0（10/11 可用） |
| `r4_j3_secret_scan.py` | `evidence/c8-j3-secret-scan-exemption.json` | 0 |
| `r4_j4_t07_gate_semantics.py` | `evidence/c11-j4-t07-gate-semantics.json` | 0 |
| `r4_selfscan.py` / `r4_lint.py` | `evidence/c0-reviewer-self-scan.json` / `evidence/c14-reviewer-hygiene.json` | 0 / 0 |

所有 harness 都**打印被试命令自身的退出码**并把它写进证据 JSON（例如 `revision_integrity.py --out <冻结名>` 的退出 1、`--self-test` 与真实 `secret_scan.py` 的退出 0/0、被削弱变体的退出 1）；没有「脚本写了但没跑」的条目——上表每一行的证据文件都由该脚本本次实跑生成。

### 7.3 约束遵守证明（收尾实测，退出码 0）

- 临时树全部删除并证明不可存在：`Test-Path $env:TEMP\t02r4` → **False**；`Test-Path tests/engineering/T02/.work/r4-review-scratch` → **False**；`Test-Path tests/engineering/T02/.work/allowlist-controls` → **False**；`tests/engineering/T02/.work/secret-scan-*` 计数 **0**；`.work` 其余子目录（11 个 GUID 目录 + `r01-legacy`）均非本会话创建。
- 本会话未产生 `__pycache__`（`Get-ChildItem -Recurse -Filter '__pycache__'` 计数 **0**，全程 `PYTHONDONTWRITEBYTECODE=1`）。
- 需字节不变的四份文件在**每一次**运行前后同哈希，收尾再核一次：`r01-integrity.json 1d18eef28322218a/14783`、`r01-integrity-run.json 18be0c34fbc16ad1/409`、`gitleaks-findings.json 37517e5f3dc66819/3`、`gitleaks.toml efd32a24525457b7/2076`；契约两份也核过：`docs/api/openapi.yaml e285471760a5dce4/613679`、`docs/schemas/editorial.schema.json 7b5872e129817bbc/212954`（与 §0.2、C-4、C-6 一致 → 冻结件与 rc.3 契约未被改动）。
- 收尾 `git status --porcelain`（HEAD `1efeb5a`；复审期间 HEAD 从 `fb62212` 经 `c21e681`/`9f1df7e`/`d733b3f` 到 `1efeb5a`，全是并发会话的提交）：`?? docs/execution/reviews/T02-round4/`（我的目录）、`?? docs/execution/reviews/T08-round4/`、`?? tests/engineering/T08/evidence/r4-main-test-results/`、`?? tests/engineering/T08/evidence/r4-main.json`。其中**只有 `docs/execution/reviews/T02-round4/` 属本会话**（31 份文件 / 211,249 字节，含本文件与 14 个脚本与 15 份证据）→ 我目录之外没有我造成的新增脏项。开工时的 `?? .tmp_t08fix.py`、`?? docs/execution/reviews/T03-round9/`、`?? .tmp_r9.py` 均系并发会话产生并已由其提交，非我所为。
- 未 add/commit/push；未写 `docs/execution/STATE.json`；未写 `tests/engineering/**`（写入只发生在 `tests/engineering/T02/.work/r4-review-scratch/`，已删）；未跑 `mvn`、未写 `backend/target`；未触碰 T03/T08 的复审目录与 `.work/t08/**`。
- 文本卫生（`r4_lint.py` → `evidence/c14-reviewer-hygiene.json`）：除 lint 自身外 14 个脚本全部 `compiles`（无 SyntaxWarning）；目录内 31 份工件（15 个脚本 + 15 份证据 + 本文件；lint 的检查行 30 条，因它不检自己）全部 `noBOM` + `LF`；`liveShapes: []`（复审工件内不残留可被扫描的连续凭据形）；`.pyc` 计数 0。
- 复审目录自身在全树扫描之后单独复扫（`r4_selfscan.py`，本会话共 3 次）：交付配置 **0 命中 / 退出 0**；**默认规则**（无任何 allowlist）也 **0 命中 / 退出 0** → 本会话的工件不会把下一轮的全树基线弄红（前段那次红是我自己写出连写键形所致，见 C-15，已按「先改自己工件」修掉）。

### 7.4 交回主 agent 的行动项（按优先级）

1. **A-1（P1，必改）**：`ci.yml:60` 的路径改成与 `ci.yml:62` 一致的稳定路径（或安装步把 linux 二进制复制成跨平台同形路径），并把 controls 步移到两条真实扫描之后/拆独立 step；改完用 §6 命令 1 复跑，要求退出 0 且断言行数不降。
2. **A-4 + A-2 + A-3（P2，口径）**：更正 `T02-Revision-R02.md:164` 的「漏裸 AKIA」半句；在 `T02.md`「gitleaks 例外的真实语义」补三条边界（子串抑制、`*gitleaks.toml*` 文件名整文件退出、二进制与 148,267 字节未读）；配置注释补一句 `condition = "AND"` 的跨维度语义。
3. **T07（排期，属 T07 卡）**：重录 input 基线与三个 patch，让交付门回到可绿状态；在此之前任何报告不得引用 T07 退出码作为验收依据（J-4 结论 4）。
4. **可选加固 A-2**：按 C-13 用 `\b` 包住 10 条字面量、第 11 条用否定环视；改完必须重跑 `--with-controls`（88 条）与 C-2 全量变异，两者都绿才算落地。
5. **建议把「配对形状」前移成门**（不属必改）：让 CI 对所有已跟踪证据跑一遍 `digest_records.check()`，使「路径与摘要同行」这类写法在写出的那一刻就失败，而不是下一轮再补一条值豁免——C-15 里我自己的证据文件就是活例。


# T02 第五轮独立复审

- 复审对象：提交 `a051eb2`（第五轮整改）+ 主 agent 的 `2a13a2e`（A-1 修复，CI 解析步 / controls 顺序）
- 上游判决：`docs/execution/reviews/T02-round4/review.md`（A-1…A-9、J-1…J-6）
- 复审方：T02-round5 独立复审（本文件）
- 判决：**CHANGES_REQUIRED**

> 判决词只用 PASS / CHANGES_REQUIRED / BLOCKED。落盘优先：每完成一节即更新本文件。

**§1–§7 一行摘要**：

1. **§1 词界加固**：11/11 精确值仍被抑制、44/44 变异全复报（我自己生成的），但**加固确实把豁免换宽了**——`-`/`.`/`=` 邻接超串在 10/10 个值上仍被抑制（50 例），第 11 条 `[^0-9a-f]` 尾巴无界再吞 5 例，而交付门的 33 条超串探针只测字母数字拼接，看不到这个面 ⇒ **R5-1（P2）**。
2. **§2 RE2 断言**：三种否定环视形式**全部 exit=2 且整条配置中止**（未改动的例外也 0 命中）⇒ 实施方的「RE2 不支持环视」为真、第四轮建议的形式不可用，处置正确；但「环视不可用 ≠ 只能留通配尾巴」，我在 §1-附实测出 RE2 可表达的两侧定界候选。
3. **§3 139 断言**：139 是真数（0 重复行、0 空转剔除、搬移副本同样 139/0），随机抽 10 条**逐条用宽容桩削弱，10/10 变红**；两处结构弱点记 P3（空转是「删断言」而非「失败」，总数未钉死；`>= 40` 容忍一个值空转）。
4. **§4 canary 双门**：复现主 agent 的 (2.561, 2.781]（后缀口径），并从二进制抽出规则真实形态 `entropy = 3` + `[A-Z2-7]{16}` ⇒ 两处报告各说对一半但都**没写计量单位**（R5-3）；「当且仅当」被第三道门 `'''.+EXAMPLE$'''` 证伪（R5-2）；R05:19 把字符类写成 `[A-Z0-9]`（R5-4）；canary 缺一条「合法字母表 + 低熵」的近例（R5-5）。
5. **§5 三条覆盖边界**：路径含 `gitleaks.toml` 者整文件不读 ✓（8 种名字形状，且字面大小写敏感）；二进制跳过 146,191 与 150,604/149,520/3,329 我用自抓量**全部复现** ✓；「0 命中不支撑无密钥」写在行为段标题与结论 ✓。残余：`T02-Revision-R02.md:163` 仍留「`secret_scan.py` 仍退出 1」未就地标注（我实测退出 0）⇒ **R5-6（P3）**。
6. **§6 诚实度与证据形状**：R02:164 改写方向正确、被撤回原话原位可读、`revision_integrity.py` 冻结与仓外拒绝都是**可读失败 + 退出 1 且不留文件**（4 种绕过形状我也试了，无旁路）、配对门两方向都 live；`r05-allowlist-hardening.json` 10 个字段里 8 个独立复现，另 2 个口径过宽/缺单位（R5-1、R5-2/R5-3）。
7. **§7 主 agent 两笔**：`2a13a2e` 的 `.exe` 只在注释与候选列表、调用点改用 `${GITLEAKS_BIN:?}`、controls 确在真实扫描之后 ⇒ 静态与逻辑侧闭合（5 种布局 Python 模拟选对，含目录+exe 共存不误选）；但**本框无 `/bin/bash`、无 pyyaml、无 Linux tarball** ⇒ runner 实跑、tar 成员名、YAML 解析、端到端**未由我复现**，连同 `STATE.json:937` 的「纯 base32 是 100%」限定缺失（R5-7）一并交回（§10/§11）。

**必改（本轮落槌的条件）**：R5-1（P2）与 R5-2（P2）；其余 R5-3…R5-7 为 P3 尾款，可在下一轮一并清。

---

## §0 基线自证

- 我在 `HEAD = 37542cb`（T08 第四轮记录）开工；被审整改提交 `a051eb2` 是 `HEAD~1`，主 agent 的 A-1 修复 `2a13a2e` 是 `HEAD~4`。开工时 `git status --porcelain` 的脏项全部属于另两路会话（`T03SessionCookieGuardTest.java`、`check_session_cookie.py`、`T08-Revision-R4.md`、`tests/engineering/T08/evidence/**`）与本目录 `?? docs/execution/reviews/T02-round5/`；**无一项是我造成的**。
- 全树扫描一律 `--report` 指向 `$env:TEMP\t02r5rev\`；`--with-controls` 用脚本自带的 `.work/allowlist-controls`（脚本自删）。我的植入与削弱只在 `$env:TEMP\t02r5rev\`。
- 我读 `.github/workflows/ci.yml` 的 `2a13a2e` diff 是**只读**（`git show`），因为必审第 7 项要求自证 A-1；我未写该文件。
- **第二次续跑自证**：开工先读回本文件与 `evidence/`，实测 `review.md` **29,085 B / sha256 前 12 位 `16d26aaf572e` / 无 BOM / CRLF 0**（换行符计数 257；主 agent 报 258 行 = 末行换行的计数口径差，字节与摘要一致）⇒ 与主 agent 交回的锚点一致，本轮**不重写骨架**，只补 §8–§12 与判决。`evidence/` 逐份字节数与主 agent 列的 9 份**完全一致**；合计我算得 **32,788 B**，主 agent 报的 61,873 B 正好是 `32,788 + 29,085`（把 `review.md` 也加进去了）⇒ 是求和口径差，不是缺件。续跑后我又向 `evidence/` 加了 1 份探针原件（`r5-harness-probe.py`，见 §11）并对既有 9 份做了**活体形状脱敏**（见 §12），因此该目录字节数此后与我这里记的数不同，属我本轮改动，已在此声明。

| 项 | 期望（任务书） | 我实测 | 判定 |
|---|---|---|---|
| `evidence/r01-integrity.json` | `1d18eef28322218a`/14783 | `1d18eef28322218a`/14783 | 一致 |
| `evidence/r01-integrity-run.json` | `18be0c34fbc16ad1`/409 | `18be0c34fbc16ad1`/409 | 一致 |
| `evidence/gitleaks-findings.json` | `37517e5f3dc66819`/3 | `37517e5f3dc66819`/3（开工时、跑完七条命令后各测一次） | 一致，未被覆写 |
| `docs/api/openapi.yaml` | `e285471760a5dce4`/613679 | 同 | 一致 |
| `docs/schemas/editorial.schema.json` | `7b5872e129817bbc`/212954 | 同 | 一致 |
| `tests/engineering/T02/gitleaks.toml` | `641c19b6b16282db`/3329 | `641c19b6b16282db`/3329 | 一致（2,076→3,329 已申报） |

摘要口径 = `sha256` 前 16 位十六进制。

主 agent 报的七条命令，**我全部自己重跑**（不复用它的输出）：

| # | 命令 | 期望 | 我的实际退出码 | 我的实际输出要点 |
|---|---|---|---|---|
| 1 | `secret_scan.py --self-test` | 0 | **0** | `10 fixtures and 1 exemptions agree` |
| 2 | `secret_scan.py` | 0 | **0** | `Secret pattern scan: no matches` |
| 3 | `check_gitleaks_allowlists.py`（结构） | 0 | **0** | 18 条 PASS、`PASSED (structure only)`（16→18 ✓） |
| 4 | `… --with-controls --gitleaks .tools/t02/gitleaks/gitleaks.exe` | 0 | **0** | 140 行 = 139 断言 + 1 汇总；**139 PASS / 0 FAIL / 0 NOTE**（无空转被吞） |
| 5 | `check_contracts.py` | 0 | **0** | `27 hashes verified, no regeneration` |
| 6 | `digest_records.py` | 0 | **0** | 静默 |
| 7 | `scan_secrets.py --gitleaks … --report $env:TEMP\…` | 0 | **0** | `no leaks found`、报告体 `[]`；冻结件哈希不变 |

---

## §1 词界加固是否把豁免换宽（11/11 + 44 变异 + 前缀碰撞攻击）

**最小复现**：`$env:TEMP\t02r5rev\probe.py`（我独立写的第二实现，不共享被审脚本的 `flip`/`_probe` 之外的任何判据代码路径；探针形状与被审门一致 = `docs/api/reference.json` 关键词 + 长 token，逐探针扫两遍 defaults / 交付配置）。

| 子项 | 期望 | 我实测 | 判定 |
|---|---|---|---|
| 11 条精确值仍被抑制 | 11/11 抑制 | `exact-00…10` **11/11 base=1 → gate=0**（含第 11 条 `e285471760…`） | ✓ 未换窄 |
| 第四轮 44 个变异重新变红 | 44/44 变红 | 我独立生成 44 个（首 / `n//2` / `2n//3` / 末，按 alnum 下标去重）：**44/44 base=1 且 gate=1**，0 个空转、0 个被抑制 | ✓ 未换宽（单字符面） |
| 字母数字超串重报 | 33/33 变红 | `pre-alnum` 10/10、`suf-alnum` 10/10、`suf-us`（下划线）10/10 **全部重报** | ✓ 与报告一致 |
| **标点连接超串** | 报告称「包含某豁免值的更长 token 现在会重新被报」 | **全部仍被抑制**：`suf-dash` 10/10、`pre-dash` 10/10、`mid-dash` 10/10、`suf-dot` 10/10、`suf-eq` 10/10 | ✗ **主张不成立（发现 R5-1，P2）** |
| 第 11 条通配尾巴连带抑制 | 只抑制该 19 字符值 | `…\.\.\.` + 任一非十六进制首字符 + **任意长尾巴** → 一律抑制：`10-dots-then-nonhex-g`、`-Z`、`-dash`、`-space-word`、`10-dots-four`（四点）、`10-pre-dash` 全 **gate=0**；同前缀但**后接小写十六进制**者不被吞（`10-dots-two` 两点、`10-other-prefix` 异前缀 → gate=1 重报） | ✗ **第 11 条是「前缀 + 字面点 + 一个任意字符」的无界面豁免（并入 R5-1）** |
| 共享 16 位前缀的**不同完整摘要** | 不被连带抑制 | `coll-full-hex-same-prefix`（`e285471760a5dce4` + 48 位不同十六进制，共 64 位）base=1 → **gate=1 重报** ✓；`coll-64hex-embedded`（前面多 2 字符）也重报 ✓。`coll-full-hex-same-prefix-2` 与 `10-dots-then-lowerhex/upperhex` **base=0（默认规则本身不报，空转）**，我不据此下结论 | ✓ 该方向未被换宽（3 个探针空转，已标注） |

**R5-1 的机理（一句话）**：`regexTarget = "match"` 是**子串搜索**，`\b` 只在「字」与「非字」之间成立；而 `generic-api-key` 的 token 字符类是 `[\w.=-]{10,150}`——`-`、`.`、`=` 既是 token 的合法内部字符、又是 `\b` 的边界。于是 `<豁免值>-<任意高熵串>` 这类**合成 token** 里豁免值自成一词，整条命中被抑制。我抓到的实际 Match 文本就是整条合成串（见 `attack.json` 的 `token` 列）。可走私形状：`值-SECRET`、`SECRET-值`、`值.SECRET`、`值=SECRET`；字母数字与下划线连接则安全重报。

**门自身的盲区**：被审 `--with-controls` 的子串控制只生成 `ab+值` / `值+cd` / `0123456789+值+abcdef` 三种**字母数字**超串（`check_gitleaks_allowlists.py:244`），因此 139 条断言对上面这 50 个抑制面**一条都看不见**。这不是计数问题，是断言集选点问题。

**RE2 安全的可能收口（我实测，仅供下一轮参考，不作为要求）**：见 §1-附（候选写法 `(?:^|[^\w.=-])<值>(?:$|[^\w.=-])`）。

---

## §2 RE2 否定环视断言独立复核

**我复现了实施方与主 agent 的断言：成立。** 方法：把交付配置里第 3 条例外（`775f…ec99`，与本轮争议无关的一条）分别改写成三种环视形式，用同一探针（该值本身）扫两遍——一遍打靶值、一遍打**未被改动的另一条值**（`ecfd…a8ea`），以验「整条配置被中止」而不只是「那一条例外失效」。原件 [evidence/r5-re2-panic.txt](evidence/r5-re2-panic.txt)。

| 变体 | 是否真的替换进去了 | 期望退出码 | 我实测退出码 | 命中数（打靶值 / 未改动值） | 关键 stderr |
|---|---|---|---|---|---|
| `(?<![0-9a-f])值(?![0-9a-f])`（第四轮 C-13 原建议） | 是 | 非 0 | **2** | 0 / **0** | `re2.cc:237] Error parsing '(?<!…': invalid perl operator: (?<!` + `panic: regexp: Compile(...): bad perl operator: (?<!` + `github.com/wasilibs/go-re2.MustCompile` |
| `(?!值)` 前向环视 | 是 | 非 0 | **2** | 0 / **0** | 同上形态，`invalid perl operator: (?!` |
| `\b值(?![0-9a-f])`（只留一个环视） | 是 | 非 0 | **2** | 0 / **0** | 同上形态 |

三点结论：

1. **panic 属实且是中止整条配置**：三种形式都 exit=2、都**没有任何 `scanned … bytes` 行**（扫描器根本没跑起来）；未改动的那条例外在同一配置下也 0 命中 → 「连其它 10 条一起失效」为真。若有人照第四轮建议改，得到的是**全绿假象 + 退出码 2**，比红更难发现。
2. 因此第四轮 J/A-2 里「第 11 条可用否定环视」这句**在本工具链（gitleaks 8.30.1 内嵌 RE2）上不可实现**，实施方以 RE2 安全形式替代、并把理由写进 `gitleaks.toml:22-24` 注释与 R05 §0，**处置正确**。复审建议本身应撤回该形式。
3. 但**替代形式的代价没有被如实记账**：`\be285471760a5dce4\.\.\.[^0-9a-f]` 不是「精确值」豁免，而是「前缀 + 三个点 + 任一非十六进制字符 + **其后任意内容**」的无界面豁免（§1 表第 5 行实测）。RE2 里确有可表达**两侧封闭**的形式，我在 §1-附实测了一条候选（无环视、`(?:^|[^\w.=-])…(?:$|[^\w.=-])`）。所以「环视不可用」不等于「只能留通配尾巴」，这一点构成对 A-2 闭合度的扣分，而非对 RE2 断言本身的扣分。

---

## §3 `--with-controls` 139 断言的承重审计

**139 是真断言数**：controls 输出 140 行 = 139 条 `PASS  ` + 1 条汇总；**精确重复行 0 条**；**`NOTE` 空转剔除 0 条**（被审脚本把「默认规则本身不报的探针」计入 `void` 并从逐条断言里剔除，本轮交付配置下没有一条被剔除）。我用**搬到 `.work/rev5-audit/BASE/` 的同内容副本**（只改 ROOT/CONFIG/WORK 三行）重跑，同样 139 PASS / 0 FAIL / 退出 0 → 计数不是我环境的产物。结构模式 **16 → 18** ✓（16 条配置结构 + `pairing_gate()` 2 条），两条模式退出均 0。

**随机抽样**：`random.Random(20261008)` 从 1..139 抽 10 条 → 序号 **12, 23, 40, 55, 56, 62, 72, 75, 80, 113**。逐条把「该断言所检查的对象」换成宽容桩/植入缺陷，跑副本，要求该行变红。原件 [evidence/r5-audit-variants.txt](evidence/r5-audit-variants.txt)（含每轮 PASS/FAIL 计数与全部 RED 行）。

| 抽样序号 | 断言 | 我植入的宽容桩（只在 `.work/rev5-audit/<变体>/`） | 该条是否变红 | 该变体总计 |
|---|---|---|---|---|
| 12 | `exception is … anchored … 394de144ba…` | 去掉第 06 条例外的两侧 `\b`（子串豁免复活） | **RED**（`[unanchored len 64]`） | 17 PASS / 1 FAIL |
| 23 | `positive control: synthetic aws-access-token caught in … r01-integrity.json` | 活体 canary 后缀换成 16 个 `A`（字母表合法、熵 0） | **RED** | 134 PASS / 5 FAIL |
| 40 | `at least two … stay live for value 01` | 值 01/04/08/09 的变异探针换成低熵串（默认规则静默 → 探针空转） | **RED**（`live 0 of 4`） | 118 PASS / 5 FAIL |
| 55 | 同上 value 04 | 同上植入 | **RED** | 同上 |
| 56 | `one-character change in case-04-first.json is reported again` | 门改用「首/尾字符换成 `.`」的宽松桩（探针仍是真变异） | **RED** | 133 PASS / 6 FAIL |
| 62 | `case-05-middle` | 门改用 `头20 + .* + 尾8` 通配桩 | **RED** | 133 PASS / 6 FAIL |
| 72 | `case-07-middle` | 同上 | **RED** | 同上 |
| 75 | `… stay live for value 08` | 低熵变异桩 | **RED** | 118 PASS / 5 FAIL |
| 80 | `… stay live for value 09` | 同上 | **RED** | 同上 |
| 113 | `substring control: super-string pre for value 07 is reported again` | 只去掉第 07 条例外的**前导** `\b` | **RED**（唯一一条 FAIL，定位精确） | 138 PASS / 1 FAIL |

**10/10 抽中条全部变红 ⇒ 139 条不是装饰，是承重**。另有两点结构性弱点（都判 P3，不否认本轮结果，因为本轮 0 空转）：

1. **空转是「删断言」而不是「让断言失败」**：把配置通配化（变体 CRA）后，输出行数从 139 **缩到 115**（24 条逐条断言凭空消失），红是靠三条聚合断言兜住的（`control is not void`、`at least two … live`、`44-mutation battery >= 40`）。**没有任何一条断言钉住总数 139**。建议下一轮加 `check('assertion count is 139', ...)`（或把 void 探针本身判 FAIL），否则「139 PASS」这句话在将来某次改动后可能变成「115 PASS」而没人报错。
2. **`>= 40` 的容忍带**：报告与断言标题都写「44 变异」，门只要求 ≥40，即允许整整 1 个值（4 条）空转仍绿。CRA 实测把 3 个值打成空转（32 条）才触发该 FAIL。

顺带自证两点：`resolve_scanner()` 的响亮失败我复跑 ✓（目录 → 退出 1 + `points at a directory, not an executable`；不存在 → 退出 1 + `path does not exist`；均无裸 Traceback、无 `.work` 残留）；配对门的两条不是空转——我直接调 `digest_records.dumps` 复核：同行记录在**第 2 行**报 `AssertionError`、分行记录接受、`violations('sha = <64hex>')` 为空（只抓「配对」不抓裸摘要）✓。

---

## §4 canary 双门实测（字母表 AND 熵）与报告措辞一致性

**我复现了主 agent 的扫描**（原件 [evidence/r5-entropy-sweep.txt](evidence/r5-entropy-sweep.txt)）：base32 后缀按唯一字符数 k 扫，k=1…6（熵 0.000/1.000/1.579/2.000/2.311/**2.561**）全部漏，k=7（**2.781**）起全部抓 ⇒ 翻转区间 **(2.561, 2.781]**（后缀口径）✓ 与主 agent 完全一致，且不是二值化表述（我把 16 档全扫了）。

**我给出一条更窄且可复现的边界，并解释为什么两句话「各自都对」**：我从钉死的二进制里抽出内嵌配置（只读，[evidence/r5-alphabet-and-nameskip.txt](evidence/r5-alphabet-and-nameskip.txt) 同批）：

```
id = "aws-access-token"
regex = '''\b((?:A3T[A-Z0-9]|AKIA|ASIA|ABIA|ACCA)[A-Z2-7]{16})\b'''
entropy = 3
[[rules.allowlists]] regexes = ['''.+EXAMPLE$''']
```

- 熵门的**精确值就是 3.0**（不是「约」），但它的**计量对象是整条匹配串（20 字符，含 `AKIA`）而不是 16 位后缀**。我的表同时给出两个口径：k=6 → 后缀 2.5613 / 整串 2.8282（漏）；k=7 → 后缀 2.7806 / 整串 **3.0037**（抓）。⇒ 主 agent 的 (2.561, 2.781] 是**后缀口径下的观测翻转**，实施方的「约 3.0」是**整串口径下的规则阈值**，两者不矛盾；**但两处文字都没写计量单位**，照 R02:164「其香农熵 ≥ 约 3.0」去判 16 位后缀，会把 k=7（后缀 2.781）误判为漏。⇒ **R5-3（P3 口径）**：补一句「熵按整条匹配串（含 `AKIA` 前缀）计，规则阈值 3.0」。
- **但「当且仅当」不成立，还有第三道门**：规则自带 `'''.+EXAMPLE$'''` 豁免。实测（同 evidence 文件）：`AKIA`+`IOSFODNN7EXAMPLE`（字母表合法、后缀熵 3.708、整串 ≥3）→ **0 命中**；只改末位 `…EXAMPLF` → **命中**。⇒ 该值被漏掉与字母表/熵无关。**R5-2（P2 口径）**：`T02-Revision-R02.md:164` 的「当且仅当…base32 AND 熵≥约 3.0」是**过宽地宣称了检出能力**（方向 = 高估覆盖，与第四轮 A-4 同一类），`evidence/r05-allowlist-hardening.json` 的 `note` 与 `T02.md` 覆盖边界第 4 条同样需补第三道门。附带价值：`secret_scan.py` 里那条 `AKIA/IOSFODNN7EXAMPLE` 豁免在 gitleaks 侧**本来就不需要**（上游自豁免），这条应写进 J-1/J-3 的取舍理由里。
- 字母表门独立成立 ✓：7 条含 `0/1/8/9` 的后缀（熵 1.272–4.084）全部 `rules=[]`，即**没有任何规则**报它们（我按 finding 级别核，不只是按 `aws-access-token`）⇒ 实施方证据表里 `caught: false` 在 finding 级别可复现 ✓。
- **R05:19 写错规则正则**：该句称规则为 `AKIA[A-Z0-9]{16}` 形态；实为 `[A-Z2-7]{16}`（与 R05 自己 §0 第 15–16 行、R02:164 的更正文自相矛盾）。这正是第三轮把 canary 造错的**同一个误读**，留在整改报告里是危险的。**R5-4（P3）**。
- R05 §0「未证明：未测 `ASIA/ABIA/ACCA` 前缀」我这边**已闭合**：三条前缀在三种上下文（`aws_access_key_id =`、含 `akia` 字样行、裸行）均命中 `aws-access-token`（[evidence/r5-entropy-sweep.txt](evidence/r5-entropy-sweep.txt) 同批 prefix 探针），与抽取的正则一致。
- **canary 集形状核对**：合法形状正例 1 条（`AKIA`+`ABCDEFGHIJKLMNOP`，`--with-controls` 里 3 份副本各必须被抓，断言存在 ✓ 且经变体 CRD 证明承重 ✓）；越界近例 1 条（含 `1`，写明「不命中是特性」，断言 `only the three base32 ids fired` 里以 `== 3` 反向钉住 ✓）。**残余**：近例只测了**字母表越界**，没有测 R05 §0 自己发现的**低熵合法**那角（k≤6）——门对「熵门也会漏合法形状」没有对照。**R5-5（P3）**：建议再加一条 `AKIA`+`AAAAAA8ABBBBBBBB` 之外的合法低熵近例（如 `AAAABBBBCCCCDDDD`）作为「必须不被抓」的特性说明。
- 是否二值化：报告与配置注释都写成「两道门 + 区间」✓ 未二值化；`condition = "AND"` 的跨维度语义注释我**独立实测与实现一致**：带 `paths`+`regexes` 的块在 `condition="AND"` 下，路径不匹配的文件里同一值仍被报（n=2）、路径匹配的整个文件 0 字节不读；把 `AND` 改成 `OR` 后同值在别处也被抑制（n=0）⇒「AND 作用在维度之间」为真。同块两条正则的「任一命中即抑制」：两块正则共享一块时，值 02、03 各自被抑制、值 04（不在块内）仍报 ⇒ 块内 OR 为真 ✓（`gitleaks.toml:12-16` 注释无需修改）。

---


## §5 覆盖边界三条是否名副其实（A-3 / A-4 / J-1）

**① 「路径含 `gitleaks.toml` 者整文件不读」名副其实，不是只按文件名相等。** 同一 281 字节载荷、defaults-only 配置、每棵树只放一个文件（原件 [evidence/r5-alphabet-and-nameskip.txt](evidence/r5-alphabet-and-nameskip.txt)）：

| 树内路径 | 读取量 | 命中 |
|---|---|---|
| `gitleaks.toml` | `scanned ~0 bytes (0)` | 0（整文件不读） |
| `sub-gitleaks.toml`（前缀拼上） | 0 字节 | 0 |
| `.gitleaks.toml`（隐藏点） | 0 字节 | 0 |
| `gitleaks.toml.bak`（后缀拼上） | 0 字节 | 0 |
| `dir-gitleaks.toml.txt`（子串埋在中间） | 0 字节 | 0 |
| `plain.txt`（对照） | **281 字节** | **1**，退出 1 |
| `gitleaks-toml.txt`（点换破折号） | 281 字节 | 1 |
| `subGitleaksToml.txt`（驼峰、无点） | 281 字节 | 1 |

⇒ 「含该子串即不读」为真 ✓，第四轮「文件名等于」的口径确实太窄；且匹配是**字面子串**（大小写与标点敏感），所以 `gitleaks-toml`、`GitleaksToml` 不受影响 —— 这点两条报告都没写坏，`T02.md` 覆盖边界第 3 条与 R05:45-58 我逐句核对**与实测一致** ✓。这条也解释了 §5② 里「配置自己因 A-3 被跳过」的机制成立。

**② 二进制跳过量 148,267 → 146,191 的算术，我用自己抓的原始量全链复现**（同一输入集 `git ls-files --cached --others --exclude-standard`，2,320 个文件 / 复制总量 39,125,989 B；原件 [evidence/r5-fulltree-arithmetic.txt](evidence/r5-fulltree-arithmetic.txt)）：

| 量 | 实施方口径 | 我的独立实测 |
|---|---|---|
| 命中数（交付 / 仅默认 / 历史基线） | 0 / 15 / 7 | **0 / 15 / 7** ✓ |
| `scanned` 交付 vs 仅默认 | — | 38,976,469 B **逐字节相同** ⇒ 例外只改抑制、不改读取范围（A-2「盲区没有变大」的独立佐证） |
| 整文件跳过量 = 交付 − 历史 | 150,604 | 38,976,469 − 38,825,865 = **150,604** ✓ |
| 「总量 − scanned」（第四轮误用口径） | 149,520 | 39,125,989 − 38,976,469 = **149,520** ✓ |
| 配置自身被 A-3 跳过的字节 | 3,329（改前 2,076） | 树内命中该子串的文件字节数 = **3,329** ✓ |
| **纯二进制跳过 = 总量 − scanned − 配置字节** | **146,191** | 149,520 − 3,329 = **146,191** ✓ |
| 反推第四轮的 148,267 | = 146,191 + 2,076 | **148,267** ✓（当年混进了旧配置 2,076 B 的自跳过） |

历史基线我取 `deca2a1^` 的配置（1,327 B，摘要 `66e1fc1cd93d6be2`），与实施方同一条 ✓。⇒ R05:74-78 的更正算式成立；把绝对总字节换成「同一输入集上两个 scanned 之差」也满足 A-5 的稳量要求 ✓。

**③ 「0 命中不得支撑基线无密钥」写在行为段，不是新章遮羞。** `T02.md:63` 的小节标题本身就把结论写进标题（「覆盖边界与显式风险边界（R05，A-4 + J-1；『0 命中』不支撑『基线无密钥』）」），位置紧接同章 `:61` 闭环实测之后；`:65` 声明四条边界「每条都有可复现实测」；`:77` 给出结论口径：任何「0 命中 / no leaks found」只说明「在该规则集与该输入集下无命中」，不构成存在性断言，并要求下游卡改写。三处旧断言（`:30` 命令表、`:129` gitleaks 行、`:151` 撤回段）都是**原位追加限定**，处理一致 ✓（插入 16 行后，第四轮点名的原 `:113`/`:135` 顺移到 `:129`/`:151`，仍在同一表格行内）。

**同型残余（本条唯一扣分）**：`T02-Revision-R02.md:163` 仍写「**`secret_scan.py` 仍退出 1**（本卡不改此文件）」，而我今天实测它退出 **0**（§0 命令表第 1、2 行）。同一类「当时为真、现已被 `0b2a6f8` 的值例外消解」的句子，`T02.md:30` 做了就地标注，这一处没有 ⇒ **R5-6（P3）**：保留原话 + 就地标注「（R05 复核：现退出 0，消解于 `0b2a6f8`；本句为当时记录）」，与 A-7 同法。

---

## §6 诚实度与证据形状（R02:164 改写 / 撤回留痕 / r05 证据可复现 / 退出码与失败形状）

| 抽查点 | 结论 |
|---|---|
| `T02-Revision-R02.md:164` 改写为实测口径 | **方向对、两处口径不齐**：双门（字母表 AND 熵）写清了、不再二值化、把「漏」与「能抓」两边都判错 ✓；但「当且仅当」被第三道门（规则自带 `.+EXAMPLE$` 豁免，§4）证伪，且没写熵的计量单位 ⇒ R5-2 / R5-3 |
| 被撤回的原话是否留在原位可读 | ✓ 原话带引号留在同一行（「前几轮…记为『漏裸 `AKIA`+16 位』——该『漏』与反过来断言『能抓』都是错的」，并点名「第三轮正向控制段与本条旧文」两个来源）；`T02.md:129` 表格行内「**撤回（R02c，见下方…）**」、`:151`「**本条后半句撤回（R02c，2026-10-08）**」先引原话再写「与 Gitleaks 8.30.1 实际语义不符，是假表述」。没有把被证伪的句子静默抹平 |
| `revision_integrity.py` FROZEN 完成度 | ✓ 冻结 3 条（新增 `evidence/gitleaks-findings.json`）；`--out` 指冻结文件 → **退出 1** + `refusing to rewrite frozen evidence record: tests/engineering/T02/evidence/gitleaks-findings.json`（相对写法与 `E:\…` 绝对写法**都拒**）；`--out` 指仓库外 → **退出 1** + 可读的 `--out must stay inside the repository; …`，且**没有留下半个文件**（`Test-Path` 假），不再是裸 `ValueError`；`--out` 指仓内非冻结路径 → 退出 0、正常产出 272 条指纹。我再试 4 种绕过形状（`GITLEAKS-FINDINGS.JSON` 大小写、目录段大小写、`./` 段、绝对路径）：`resolve()` 在本文件系统把四种都规范化回同一相对名，**全部拒** ⇒ 我找不到旁路，A-6 按第四轮要求闭合 |
| `digest_records` 配对门两方向 | ✓ 同行记录 → `fingerprint manifest pairs path and digest on line(s) [2]`（**指名行号**）；分行记录 → 接受、`violations()` 空；`violations('sha = <64hex>')`（有长摘要无关键词）→ 空 ⇒ 只抓配对、不过严 |
| `resolve_scanner()` 失败形状 | ✓ 目录 → 退出 1 + `points at a directory, not an executable`；不存在 → 退出 1 + `path does not exist`；两者都**不是裸 Traceback/OSError**，且崩溃发生在建 scratch 之前（`Test-Path .work/<变体>` 假）⇒ 第四轮实测的未捕获 `PermissionError`/`FileNotFoundError` 已消解 |
| 是否用新增章节掩盖残余 | 没有。R05 全文 182 行里每节都带 **计划 / 实测 / 未证明** 三段，`未证明` 明确把 CI 接线、tarball 成员名、ENOTDIR/ENOENT  errno 交回主 agent（R05:115、:127），与本文件 §10 的清单一致 |

`evidence/r05-allowlist-hardening.json` 逐字段复现（原字段名照抄；我只核下列量）：

| 证据字段 | 声称 | 我的独立结果 |
|---|---|---|
| `withControlsAssertionCount` | 139 | **139**（140 行 − 1 汇总；0 精确重复行；0 条 `NOTE` 剔除）✓ |
| 结构模式条数 | 16 → 18 | 现测 **18** PASS ✓ |
| `exactValuesStillSuppressed` | 11/11 | **11/11** ✓（§1 表） |
| `mutationTotal` / 复报 | 44 / 44 | 我自己生成的 44 条（首、`n//2`、`2n//3`、末位）base=1 且 gate=1：**44/44，0 空转** ✓ |
| `substringSuperstringsReReported` | 33/33 | 我的同型 11×3 全部复报 ✓；**但 5 类标点连接超串（`-`/`.`/`=` 邻接）逐值 10/10 仍被抑制** ⇒ 该字段为真却不完备，见 R5-1 |
| `binarySkippedBytes` | 146,191 | **146,191** ✓ |
| `configSha256PrefixBefore` | `efd32a24525457b7` | `git show a051eb2^:…gitleaks.toml` → `efd32a24525457b7` / 2,076 B；`a051eb2` → `641c19b6b16282db` / 3,329 B ✓ |
| `forbiddenAlphabetSuffixes[].caught = false` | 7 条 | ✓ 复现，且强度更高（**任何规则** 0 命中，非仅 `aws-access-token`） |
| `awsAlphabetFinding.note`「当且仅当…」 | — | **不成立**（第三道门）⇒ R5-2 |
| 熵门「约 3.0」 | — | 精确 **3.0**，但按**整条匹配串**（含 `AKIA`）计 ⇒ R5-3 |

---

## §7 主 agent 的两笔（2a13a2e CI 解析步 / 台账单因表述残留）

**A-1 的静态与逻辑侧：闭合；Linux 实跑：明确交回。** `2a13a2e` 之后 `.github/workflows/ci.yml` 里 `.exe` 只出现在**注释 `:42`** 和**候选列表 `:44`**（我 grep 全文，两处之外 0 次命中）。解析步 `:38-51`：`for candidate in .tools/t02/gitleaks .tools/t02/gitleaks/gitleaks .tools/t02/gitleaks/gitleaks.exe` 取第一个 `[ -f ] && [ -x ]` 者，写 `$GITHUB_ENV` 并回显；找不到就 `::error::pinned gitleaks binary not found …` + 退出 1（`:51`）✓ 响亮失败。两个调用点 `:77`（`scan_secrets.py`）与 `:86`（`--with-controls`）都改成 `${GITLEAKS_BIN:?gitleaks binary unresolved}`，`:85` 另有 `test -x` ✓。**控制段确在真实扫描之后**：扫描步 `:69-79`（`secret_scan --self-test` → 结构模式 → `secret_scan` → `scan_secrets` → `dependency_scan` → `npm audit`），控制段是独立步骤 `:80-86`，`:83-84` 注释写明改前耦合原因 ⇒ 第四轮 P1 的「一个控制取消四件被控对象」结构已拆除 ✓。

解析逻辑我用 Python 按形状模拟（等价于 `[ -f ] && [ -x ]` 的判定，**不是**跑 bash）：

| 假设布局 | 解析结果 | 退出 |
|---|---|---|
| 只有 `.tools/t02/gitleaks`（Linux tar 单文件形状） | `.tools/t02/gitleaks` | 0 |
| 只有 `.tools/t02/gitleaks/gitleaks` | `.tools/t02/gitleaks/gitleaks` | 0 |
| 只有 `.tools/t02/gitleaks/gitleaks.exe`（本机形状） | `.tools/t02/gitleaks/gitleaks.exe` | 0 |
| 同名目录 + 目录内 exe **同时存在**（本机真实形状） | `.tools/t02/gitleaks/gitleaks.exe`（目录被 `-f` 正确跳过，不会误选） | 0 |
| 什么都没装 | 命名 `::error::` | 1 |

**未由我复现（不猜，见 §10/§11）**：① 本框 `bash` 是 WSL 存根，`bash -c` 报 `execvpe(/bin/bash) failed`，解析步**没被真实 shell 执行过**；② 本机 `.tools/t02/` 只有 `gitleaks.zip` 与已解出的 `gitleaks/` 目录，**没有** Linux tarball ⇒ tar 成员名是否恰为单个 `gitleaks`（候选 1 能否命中）未证；③ 本框无 pyyaml，`ci.yml` 未经真 YAML 解析器验证（缩进/步骤是否合法只做了行级目视）；④ 整条 workflow 未在 runner 上端到端跑过。

**台账单因表述残留**：我已核的位置都写成了「字母表 AND 熵双门 + 适用域」，没有把「判据不是熵」当活断言留着 —— `STATE.json:26`（T02-5th-measurement，明说「我此前写『判据不是熵』那只在高熵带成立」）、`:594`（GITLEAKS-RULE-COVERAGE 的更正）、`:729`（closure 给出翻转区间）、`T02-Revision-R05.md:13/17`（标题即「不是熵单独」）。**唯一残留**：`STATE.json:937` 的经验条目仍写「纯 base32（A-Z2-7）是 **100%**」，限定只在紧邻的 `:939` 里；按 `:939` 自己给的方法沿熵维扫一遍即证伪（k≤6 的合法 base32 命中率为 **0%**）⇒ **R5-7（P3）**，且该文件我无写权，交回主 agent 一行限定（补「随机抽取的高熵样本」+ 熵计量单位）。另：`STATE.json:714` 已登记「第五轮整改完成后需独立复审第五轮」✓ 台账与本复审对得上。

---


## §8 A-1…A-9 闭合判定

| 编号 | 上游要求 | 本轮状态 | 判定 |
|---|---|---|---|
| A-1 | CI 解析步不得让本地 Windows 路径泄漏成 `.exe`，且 controls 不能取消真实扫描 | `.exe` 仅 `:42` 注释 + `:44` 候选；`:77`/`:86` 均用 `${GITLEAKS_BIN:?}`；controls 独立步骤 `:80-86` 排在扫描步 `:69-79` 之后；5 种布局的 Python 形状模拟全部选对（含「同名目录 + 目录内 exe」不误选） | **闭合（静态与逻辑侧）**；Linux 真跑与 YAML 解析未由我证明 → §10/§11 |
| A-2 | 词界加固不能把豁免换宽；11 精确值仍抑制、变异全复报 | 11/11 ✓、44/44 ✓、alnum 超串复报 ✓；**但 `-`/`.`/`=` 邻接超串 10/10 值仍被抑制（50 例）**，第 11 条 `\b<prefix>\.\.\.[^0-9a-f]` 尾无界再吞 5 例；交付门只测 alnum 拼接，看不到这条 | **部分闭合** → **R5-1（P2）** |
| A-3 | `*gitleaks.toml*` 触发范围要写准 | 8 种文件名形状实测：含该字面子串一律 `scanned ~0 bytes`，`gitleaks-toml`/`GitleaksToml` 正常读取并命中 | **闭合** |
| A-4 | 覆盖边界要落到行为段，且引用的 AKIA 实测须为真 | 行为段 `T02.md:63-77` 四条边界 + 三条风险边界，「0 命中≠无密钥」写在标题与结论；R02:164 改成实测口径 ✓；**但「当且仅当」被规则自带 `.+EXAMPLE$` 豁免证伪** | **部分闭合** → **R5-2（P2）** |
| A-5 | 断言里只留稳量 | 0/15/7 命中、150,604 / 149,520 / 3,329 / **146,191** 我用自抓原始量逐条复现，`scanned` 交付 = 默认（38,976,469）证明例外不改读取范围 | **闭合** |
| A-6 | `revision_integrity.py` 的 `--out` 要完成冻结与仓外拒绝 | 冻结 3 条；相对/绝对写法指冻结件 → 退出 1 + 可读拒写；仓外 → 退出 1 + 可读拒写且不留文件；4 种大小写/`./`/绝对绕过形状均拒；仓内非冻结路径正常退出 0 | **闭合**（我找不到旁路） |
| A-7 | 被证伪的断言要就地标注，不留孤立旧文 | `T02.md:30`/`:129`/`:151` 三处同法 ✓；**`T02-Revision-R02.md:163` 仍写「`secret_scan.py` 仍退出 1」而无就地标注（我实测退出 0）** | **部分闭合** → **R5-6（P3）** |
| A-8 | 豁免标签要能区分「整值」与「截断散文」 | 结构模式逐值标签实测：整值 `\b…\b` → `literal len 64/30`；我去锚 → `unanchored`；我塞 `.*` → 标签断言精确变红（变体 SR1/CRA/CRE） | **闭合** |
| A-9 | 配对形状前置门（同行 path+digest 命中即红、指名行号） | `pairing_gate()` 两方向都 live（同行在第 2 行报 `AssertionError`、分行接受、裸摘要不误报）；R05:113-115 的计划文字与实现范围一致，且已声明 CI 接线属主 agent | **闭合**，附**范围决策**：门只约束「经 `digest_records` 落地的那一刻」，不扫既有证据；若按第四轮字面加全量扫描，今日 `tests/engineering/T02/evidence/*.json` 里 **8 个既有文件会红**（含冻结件 `r01-integrity.json:110,111`）⇒ 需主 agent 明确取舍，不是本轮缺陷 |

## §9 J-1…J-6 闭合判定

| 编号 | 上游要求 | 本轮状态 | 判定 |
|---|---|---|---|
| J-1 | 「值 + 子串」双口径写进报告 | 双口径都在（`T02.md:63-77`、R05:67）；**子串半边结论不完整**：只测 alnum 拼接，标点邻接未测 → 与 R5-1 同一件事 | **部分闭合**（随 R5-1 收口） |
| J-2 | 「0 命中」不能支撑「基线无密钥」，且被引用的 AKIA 实测有一半是错的 | 边界句写在位 ✓；AKIA 口径已改为双门实测 ✓；**残余：熵计量单位缺失（R5-3）、「当且仅当」过宽（R5-2）、R05:19 规则正则写错字符类（R5-4）** | **部分闭合** |
| J-3 | `secret_scan.py` 用值豁免覆盖台账与扫描器自身，判为正确取舍 | 本轮未触碰该文件；我实测两模式退出 0、`gitleaks-findings.json` 未被覆写、无新增豁免条目 | **维持闭合** |
| J-4 | T07 不变式「严格更强」说法与基线重录 | 属 T07 卡；本轮我被禁止读写 `tests/engineering/T07/**`，未复测 | **不适用本卡**（沿第四轮判定，交回 T07 下一轮） |
| J-5 | CI 三条新命令的 runner 后果（A-1 的 P1 来源） | 结构侧同 A-1：P1 已拆；**runner 实跑、`bash -x` 解析步、tar 成员名、YAML 解析均未由我复现**（本框无 `/bin/bash`、无 pyyaml、无 Linux tarball） | **部分闭合**（待 §11 runner 证据） |
| J-6 | 诚实度抽核合格，两处序号/精度待更正 | 撤回留痕 ✓、证据 10 字段里 8 字段独立复现 ✓、FROZEN/退出码形状 ✓；**精度残余 3 条：R5-2 / R5-3 / R5-4** | **部分闭合** |


---

## §10 未由我复现清单

1. **Linux runner 上的解析步实跑**：本框 `bash` 是 WSL 存根（`bash -c` 报 `execvpe(/bin/bash) failed`），`[ -f ] && [ -x ]` 的循环我只做了 Python 等价模拟，没有真 shell 跑过 `ci.yml:38-51`。
2. **tar 成员名**：本机 `.tools/t02/` 里只有 `gitleaks.zip` 与已解出的 `gitleaks/` 目录，**没有** `gitleaks_8.30.1_linux_x64.tar.gz` ⇒ 「`tar -xzf … -C .tools/t02` 后落出单个文件 `.tools/t02/gitleaks`（候选 1 能命中）」这一前提我未证。
3. **`ci.yml` 未经真 YAML 解析器验证**：本框无 pyyaml；我只做了行级目视 + grep（缩进/`run: |` 块合法性未程序化验证）。
4. **整条 workflow 端到端**：未跑，也不会由我跑（涉及 `npm ci`/`mvn`，且 `mvn` 与 `backend/target` 为其他会话独占，我禁写）。
5. **`mvn` 全量 verify**：本轮未复现（同上，属 `95794bd8` 独占）。
6. **gitleaks 上游源码**：规则文本与 `entropy = 3`、`'''.+EXAMPLE$'''` 我是**从钉死的二进制里抽内嵌配置**得到（不是读上游源码），因此「上游实现细节」层面仍以二进制内嵌文本为准；RE2 环视不可用则由三种形式的 exit=2 实测支撑（§2）。
7. **P3 尾项我没有全部实测**：例如「熵门按整串计」我用了两口径对照表 + 精确阈值抽取文本，未再做一次「整串=20 而阈值上下各 0.1」的更细二分扫描（k=6/k=7 已足够定位，但 k=6.5 之类的中间态不存在——熵按离散唯一字符数取值）。

## §11 需主 agent 代跑的精确命令

**(A) 必改 R5-1（P2）：把「词界」写成两侧封闭的定界类，并让门看得见标点邻接。** 我实测过的候选（无环视、RE2 可表达、11/11 仍抑制、55/55 超串复报，见 [evidence/r5-remedy-candidate.txt](evidence/r5-remedy-candidate.txt)）：左界 `(?:^|[\x60'"=:\s])`、右界 `(?:$|[\x60'"\s;])`，第 11 条保留 `[^0-9a-f]` 后再接右界。

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$py='C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
cd E:\project\codex\wxAgent
# 1) 先复现我看到的洞（改配置之前必须先红）：workdir 用任意临时目录，脚本只读仓库
& $py docs/execution/reviews/T02-round5/evidence/r5-harness-probe.py "$env:TEMP\r5chk" attack
#    期望（交付配置现状）：10/10 个值的 suf-dash / pre-dash / mid-dash / suf-dot / suf-eq 行 gate=0（被抑制）
# 2) 改 gitleaks.toml 后再跑同一条 + 结构/控制两模式
& $py tests/engineering/T02/check_gitleaks_allowlists.py
& $py tests/engineering/T02/check_gitleaks_allowlists.py --with-controls --gitleaks .tools/t02/gitleaks/gitleaks.exe
```
注意：`check_gitleaks_allowlists.py` 的 `unwrap()` 认的是 `\b…\b` 形态，换锚后**必须同步**让标签逻辑认得定界类，否则 11 条逐值标签断言会红（这是预期的联动改，不是回归）。同时给 `super` 三例（约 `:244`）补 `-`/`.`/`=` 三种邻接，让 139 条里真的包含标点面。

**(B) P3 文字尾款（三条，都不动代码）：**

```powershell
Select-String -Path docs/execution/reports/T02-Revision-R02.md -Pattern '当且仅当|仍退出 1' -Context 0,0   # :164 与 :163
Select-String -Path docs/execution/reports/T02-Revision-R05.md -Pattern 'A-Z0-9\]\{16\}|约 3.0' -Context 0,0  # :19 与 :17
Select-String -Path docs/execution/STATE.json -Pattern 'A-Z2-7） 是 100%|纯 base32' -Context 0,0              # :937
```
要改成什么：① R02:164 与 R05 证据 `note` 的「当且仅当」→ 加第三道门（规则自带 `'''.+EXAMPLE$'''` 豁免；实测 `AKIA+IOSFODNN7EXAMPLE` 0 命中、改末位 1 字符即命中）；② R05:17/26 与 R02:164 的「熵 ≥ 约 3.0」→ 写「阈值精确 3.0，计量对象是整条匹配串（含 `AKIA` 前缀，20 字符）；按 16 位后缀口径翻转在 (2.561, 2.781]」；③ R05:19 的 `AKIA[A-Z0-9]{16}` → `AKIA[A-Z2-7]{16}`；④ R02:163「`secret_scan.py` 仍退出 1」→ 保留原话 + 就地标注（现退出 0，消解于 `0b2a6f8`）；⑤ STATE.json:937「纯 base32（A-Z2-7）是 100%」→ 加适用域（随机抽取的高熵样本；k≤6 的合法 base32 为 0%）。

**(C) A-9 范围决策（要么写清边界，要么补全量门）：** 若决定按第四轮字面「对已跟踪证据跑配对检测」，先跑我这段确认影响面（只读）：

```powershell
& $py -c "import sys,pathlib,subprocess; sys.path.insert(0,'tests/engineering/T02'); import digest_records as dr`nns=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard'],text=True).splitlines()`nfor n in [x for x in ns if '/evidence/' in x and x.endswith('.json')]:`n    v=dr.violations(pathlib.Path(n).read_text(encoding='utf-8',errors='replace'))`n    print(n, v[:3]) if v else None"
```
今日实测：`tests/engineering/T02/evidence/*.json` 里 **8 个文件命中**（`integration.json:13`、`r01-compose-final.json:9`、`r01-compose-fixed.json:9`、`r01-docker-availability.json:9`、`r01-empty-integrity.json:13`、`r01-entrypoint-final.json:10`、**`r01-integrity.json:67,110,111`（冻结件）**、`r01-upgrade-integration.json:13`），全仓库 511 个证据 JSON 里 132 个有同行配对。⇒ 直接加全量门会让 CI 常红；请二选一：把边界写进报告（「门只约束经 `digest_records` 新写入的那一刻，历史冻结件由 11 条值例外覆盖」），或给门加「冻结件白名单（点名 + 行号）」。

**(D) runner 侧（消灭 §10 第 1-4 项）：**
```bash
tar -tzf .tools/t02/gitleaks.tar.gz          # 期望成员名恰为 gitleaks（候选 1 命中）
bash -c 'set -eu; for c in .tools/t02/gitleaks .tools/t02/gitleaks/gitleaks .tools/t02/gitleaks/gitleaks.exe; do
  if [ -f "$c" ] && [ -x "$c" ]; then echo "GITLEAKS_BIN=$c"; break; fi; done; test -n "${GITLEAKS_BIN:-}"'
python -c "import yaml;d=yaml.safe_load(open('.github/workflows/ci.yml',encoding='utf-8'));j=d['jobs'][next(iter(d['jobs']))];print([s.get('name') for s in j['steps']]);print([i for i,s in enumerate(j['steps']) if 'with-controls' in str(s.get('run',''))])"
```
第三条同时证明「YAML 可解析」与「controls 步确在真实扫描步之后」（比较两个 name 的下标）。

**(E) §3 的两条 P3（可选，但建议一次做完）：** 加一条 `check('assertion count is 139', …)` 钉住总行数（CRA 实测证明：断言会因 `void` 剔除而**静默减少**，139 → 115 而无人报错）；把 `mutation_total >= 40` 收紧为 `== 44`（现在允许整整一个值的变异面空转仍绿）。


## §12 清理与自证

**结束前实测（全部我自己跑，退出码紧跟命令存变量）**：

| 项 | 结果 |
|---|---|
| 我的植入/削弱目录删除并证明不存在 | `Test-Path` **False** ×7：`tests/engineering/T02/.work/rev5-audit`、`.work/rev5-audit-work`、`.work/rev5-none`、`.work/secret-scan-wrvxw93k`、`%TEMP%\t02r5rev`、`%TEMP%\r5chk`、`%TEMP%\t02r5rev_outside.json`（仓外那次 `--out` 从未生成文件） |
| `.work` 剩余目录 | 只有他人/脚本自管的哈希目录与 `r01-legacy`；我的 `rev5-*` 已全部消失 |
| 被审件与冻结件未被改动 | `r01-integrity.json 1d18eef28322218a/14783`、`r01-integrity-run.json 18be0c34fbc16ad1/409`、`evidence/gitleaks-findings.json 37517e5f3dc66819/3`、`gitleaks.toml 641c19b6b16282db/3329` ⇒ 四件**逐字节原样**（全树扫描一律 `--report` 指 TEMP） |
| 我的目录不制造命中 | `secret_scan.py` → `no matches`、**退出 0**；`scan_secrets.py --gitleaks .tools/t02/gitleaks/gitleaks.exe --report %TEMP%\r5-final.json` → `no leaks found`、**退出 0**（TEMP 报告随后删除） |
| `git status --porcelain` | 脏项全部属于另两路会话（`T03*`、`T08*`、`integration/evidence/*`、`.gitattributes`、`config-census.txt`、`session-cookie-r10.json`）与本目录 `?? docs/execution/reviews/T02-round5/`；**`tests/engineering/T02/**` 与 `.github/**` 零改动**，`backend/**` 零改动 |
| 未使用 | `git add` / `git commit` / `mvn`；未写 `docs/execution/STATE.json`；未读写 `T08-round4/**`、`T03-round9/**`、`tests/engineering/{T03,T07,T08}/**`、`backend/src/**` |

**本轮对自身产物的一次真实反噬（记为过程事实，不是被审缺陷）**：我把探针原始输出直接落进 `evidence/` 时，`r5-attack-battery.txt` 的 `token=` 列里带大小写混合的 20+ 字符随机串，**在交付配置下自己构成了 10 条 `generic-api-key` 命中**（`scan_secrets` 退出 1、`secret_scan` 也红）。这与 R5-1 是同一机理的现场演示：`generic-api-key` 的关键词/连接面极宽（`token=` 就是关键词），而**十六进制之外的混合大小写串不会被我的第一版脱敏（只截 `[0-9a-f]{20,}`）抓住**。处置：① 对所有 `token=`/`suffix=`/尾部取值列做 6 字符 + 长度标注的截断（45 行）；② 把 `AKIA` 等前缀与 16 位主体之间插入 `+` 以打断活体形状（2 行），两份改动都在文件头部写明是显示层脱敏、测量值不变；③ 重跑两个扫描器至退出 0（上表）。**没有任何既有证据被删除**；`r5-harness-probe.py` 是运行时从 `gitleaks.toml` 读取豁免值的脚本，自身不含字面密钥形状。

**产物清单（本目录，共 10 份）**：`review.md` + `evidence/r5-re2-panic.txt`、`r5-attack-battery.txt`、`r5-mutation-battery.txt`、`r5-entropy-sweep.txt`、`r5-alphabet-and-nameskip.txt`、`r5-fulltree-arithmetic.txt`、`r5-audit-variants.txt`、`r5-remedy-candidate.txt`、`r5-command-matrix.txt`、`r5-harness-probe.py`。


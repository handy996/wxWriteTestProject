# T08 第五轮整改（成本计量与配额准入）

被审对象：`docs/execution/reviews/T08-round5/review.md`（判决 CHANGES_REQUIRED）
本轮整改范围：F-R5-01 … F-R5-06 + 三条不编号观察项。F-R5-07 不归本卡（属主 agent 提交归属账）。

> 骨架优先：下列每一节先立「计划 / 实测退出码 / 反向控制 / 良性半边 / 未证明」五槽，边做边填，做完即写盘。

---

## §A 基线与约束自证

| 项 | 计划 | 实测（开工时） |
| --- | --- | --- |
| `git rev-parse HEAD` | 开工时记录 | `e3efcd8b9ef4c9b448a3f6f5cb05ea8a541810c3`（分支 `main`）；`47caf6c`（被审整改提交）在其祖先链中，被审 T08 字节未变 |
| 开工时 `git status --porcelain` 里属于我的痕迹 | 应仅有本轮我新增的文件 | 开工时仅有 `?? docs/execution/reports/T08-Revision-R5.md`（本骨架）；其余 `M`/`??` 全属 T02/T03 会话在制品，我未碰（`T03SessionCookieGuardTest.java`、`check_session_cookie.py`、`T03/evidence/*`、`T02-Revision-R06.md`、`T03-Revision-R10.md`） |
| `Get-Process postgres`（开工前） | 先数再决定动谁，别人的一律不碰 | **0**（无他人集群在跑；我的 `run_pg.py` 用随机端口集群并 `finally` 里 `pg_ctl stop`） |
| 受控证据目录基线 | `git ls-files` 与磁盘各数一次，应 105 | `git ls-files …/evidence` = **105**，磁盘 `-Recurse -File` = **105** |
| `tests/engineering/T08/.work/` | 六个哈希命名旧根属早先会话，不读不删 | 存在六根 `336f4ccd/6621bb23/8abbdcfd/9da386b1/c1277cf0/d2bdf470` + 早先 `probe*.py`；**我不读不删**；我的运行目录只叫 `r5fix-*` 或落 `$env:TEMP\t08r5fix\` |
| Python / PowerShell 版本 | 派单指定 | `Python 3.12.14`；`PowerShell 5.1.26100.9444`（culture `zh-CN`，故字节捕获、不用 `[System.IO.*]::`、写盘走 python） |
| `mvn` | **未执行**（agent-95794bd8 独占 maven） | 未执行任何 `mvn`（见 §K） |
| `backend/target` | **未写** | 未写；`run_pg.py` 用自己的隔离副本 |

### A.1 整改前基线读数（与 §11 第 1/2/4 条对表）

| 命令 | 退出码 | 读数 |
| --- | --- | --- |
| `python tests/engineering/T08/verify.py` | **0** | `16/16 passed` |
| `python tests/engineering/T08/verify.py --reverse-control` | **0** | 66 `[REJECT]` / 8 benign / `blind=none, misplaced=none, brittle=none` |
| `run_pg.py --path-selftest --work-root tests/engineering/T08/evidence` | **0** ❌ | `evidenceDir=…/evidence/evidence`、`evidenceDirChosen=false`、`problems=[]`（F-R5-02 等值判据被攻下，复现成功） |
| `run_pg.py --path-selftest --tests "CostPricingTest#someMethod,NotARealSuite"` | **0** | `methodFilterStripped=["CostPricingTest","T08PostgresTest"]`——**未回显我传的值**，证 F-R5-03 硬编码 |

G1/G2 的「当前 16/16 全绿」由 `r5_gate_probe.py` 复现（见 §B）。

---

## §B F-R5-01（P2）体内绑定证据连续第三轮可整段摘空

**缺陷**：`bound_in()` 只查「出现过 loader / 解析 / `add` / `from(env)`」五件事，不查**数据流**（解析出来的源是否进到被绑的那具环境）；平铺键禁令是同一具正文里的**子串测试**。故 G1（诱饵解析进另一具环境后丢弃，真键由 `r5Head + rQuota` 拼接）、G2（平铺键由同文件 helper 装配）两型都能 16/16 全绿且真库整轮退出 0。

| 槽 | 内容 |
| --- | --- |
| 计划 | ① `bound_in` 加数据流：`add(...)` 的目标变量**就是** `from(env)` 读的那具环境。② 体内禁止属性写入调用与助手调用（白名单外的一律拒）。③ G1/G2 收编进 `MUTATIONS` 并实测红。④ 自找第三型并证明也被拦住；找不到则如实写「未找到第三型」。 |
| 实测退出码 | `python tests/engineering/T08/verify.py` = **0**（16/16，交付形态未破）。审阅者自带静态探针 `docs/execution/reviews/T08-round5/evidence/r5_gate_probe.py`（不改它，只跑它）= **0**，其中 G1、G2 现各 **15/16**、红的正是门 11「provider quota scopes…」（`binding evidence inside the asserting case bodies=[True, False, True, True]`，即活库切片的 `bound_in` 判 False），A8「局部变量喂 service」仍 **16/16 全绿**。 |
| 反向控制 | `--reverse-control` 减弱条数 **66 → 77**（本轮共 +11，全部 `[REJECT]`）：F-R5-01 加 4 条体内绑定流减弱（G1 拼接平铺键、G2 同文件 helper 装配、**H3 我的第三型**=正确 loader→env 之后再 `env.setProperty(r5fHead + r5fQuota + …)` 平铺属性写入、**H4 我的第四型**=正确 loader→env 之后再调同文件 `r5QuotaShadow(env)` 助手），四条都打在新数据流子句上而非子串上——探针同时显示 `flat dotted keys inside the case bodies=none` 仍在，即旧子串规则对 G1/G2/H3/H4 一律放行、是 `bound_in` 的数据流把它们逐下去的。 |
| 良性半边 | 8 条良性等价重写全绿（含 A8 那类「绑好的政策经局部变量中转给 service」）——新子句没有硬编码到拼写：`add` 目标仍写 `env`、正文不再二次触碰 `env` 的合法改写照样绿。`brittle=none`。 |
| 未证明 | **活库整轮（`r5_gutted_live.py`，需 mvn）不在本卡可跑**：`mvn` 与 `backend/target` 由 agent-95794bd8 独占。静态层已证 G1/G2/H3/H4 在 `bound_in` 上红；「红 ⇒ 真库退出码非 0」需主 agent 代跑（见 §L）。残留理论绕过面：把整段绑定（含 `env` 声明）挪进同文件 helper、正文只留一次 `from(helperEnv())` 的写法——因 F-R4-06 裁决明确要求「绑定证据必须在断言所在的方法体内」，此形会撞 `declared`（正文无 `String x = """`）判 False 而红，属**刻意的严格**、非误杀，已在 §M 记为「未观测的合法形态」。 |

---

## §C F-R5-02（P3）落点自检被攻下：等值非包含 + 摘掉判据后门仍绿

**缺陷**：判据 `evidence_dir == CONTROLLED_EVIDENCE.resolve()` 是等值，故 `--work-root …/evidence`（或其子目录）算出 `…/evidence/evidence` 仍 `problems=[]`、exit 0；且把 `and not chosen` 摘成 `if False:` 后门 13 仍 16/16（看守不看可达性）。

| 槽 | 内容 |
| --- | --- |
| 计划 | ① 判据与 JSON 字段改**祖先路径包含**（新增 `lands_in_controlled(candidate)`：`candidate == CONTROLLED_EVIDENCE.resolve() or CONTROLLED_EVIDENCE.resolve() in candidate.parents`）。② 「未点名却要落进受控树」在 `--path-selftest` 里进 `problems`，在真实运行里于**启动集群/构建之前** `raise SystemExit`，故拒绝是可达的、不是躲在 `if False:` 后面的一句话。③ JSON 字段 `insideControlledDirectory` 与落点判定都走同一 helper。④ 门 13 `check_runner_paths` 从「读句子」改为「读决策」：盯 helper 存在、盯可达的拒绝守卫、盯记录字段走同一祖先判定，并禁旧等值式复现。⑤ 给「摘掉 `not chosen` / 改回等值 / 字段回等值」补内置反向控制。 |
| 实测退出码 | 攻击（改前复现、改后已被拦）：`run_pg.py --path-selftest --work-root tests/engineering/T08/evidence` = **1**（`problems=["evidence would land in the controlled directory … or under it without an explicit --evidence-dir"]`、`insideControlledDirectory=true`）；`--work-root …/evidence/sub`（子目录）= **1**（同一 problem）。良性半边：`--path-selftest`（默认 `.work` 落点）= **0**、`problems=[]`、`insideControlledDirectory=false`。`python verify.py` = **0**（16/16）。 |
| 反向控制 | 门 13 侧新增 4 条（计入上面 77）：R1「守卫摘成 `if False and not chosen:`」红；R1b「真实运行里 `if lands_in_controlled(evidence_dir): raise` 摘成 `if False:`」红；「helper 退回纯等值 `return candidate == controlled`（子目录不再算受控）」红；「JSON 字段 `insideControlledDirectory` 退回等值」红。全 `[REJECT]`，无 `BLIND`。 |
| 良性半边 | 默认 scratch 落点（`.work/evidence`）仍 `problems=[]` exit 0；显式 `--evidence-dir tests/engineering/T08/evidence` 时 `chosen=True`、可达守卫不触发（`lands_in_controlled` 为真但 `and not chosen` 为假），交付路径不破。自检为纯只读：`evidence/sub`、`evidence/evidence` 跑后 `Test-Path` 均 False，受控目录仍 105 文件、git/disk 一致。 |
| 未证明 | 真实运行的 `raise SystemExit` 分支需 `--work-root` 指向受控树且不带 `--evidence-dir` 才触发；该路径在启动 mvn 之前，故本卡能证「可达 + 门 13 红」，但「真库整轮在此退出码非 0」仍需主 agent 代跑（见 §L）。 |

---

## §D F-R5-03（P3）`--path-selftest` 校验的 `--tests` 是硬编码

**缺陷**：`run_pg.py:210` 写死 `CostPricingTest#…`，不吃操作者传入的 `--tests` ⇒ 自检声称检查的那条路径不是操作者走的那条。

| 槽 | 内容 |
| --- | --- |
| 计划 | 删硬编码字符串，改 `filtered = wanted_suites(args.tests)`；新增 `KNOWN_SUITES = ('CostPricingTest','T08PostgresTest')`；`filtered` 里出现 `KNOWN_SUITES` 之外的套件名 ⇒ 进 `problems`；JSON 里回显原始输入 `testsInput: args.tests`。门 13 加锚点：自检路径必须出现 `filtered = wanted_suites(args.tests)` 与 `'testsInput': args.tests`。 |
| 实测退出码 | 攻击：`run_pg.py --path-selftest --tests "CostPricingTest#someMethod,NotARealSuite"` = **1**（`problems=["--tests names suites Surefire never reports here: NotARealSuite …"]`、`testsInput` 与 `methodFilterStripped=["CostPricingTest","NotARealSuite"]` 均回显我传的值）。良性半边：默认 `--tests`（含 `#` 剥后仍为两类）= **0**；`--tests "CostPricingTest#dayCountLeafCarriesTheLongTheRecordStores,T08PostgresTest"` = **0**（方法过滤器被正确剥成两类、不误报）。 |
| 反向控制 | 门 13 侧新增 1 条（计入 77）：「自检退回硬编码 `wanted_suites('CostPricingTest,T08PostgresTest')`」红（`filtered = wanted_suites(args.tests)` 锚点消失）。`[REJECT]`。 |
| 良性半边 | 合法收窄单套件 `--tests "CostPricingTest"` 不误报（存在性检查按 `set(filtered) - set(KNOWN_SUITES)` 判，不看数量）；真实运行的套件存在性检查 `wanted = wanted_suites(args.tests)` 未动（F-R4-13 那条既有对照仍红）。 |
| 未证明 | 无本卡未证项——`--path-selftest` 不启动 mvn，退出码即实测。 |

---

## §E F-R5-04（P3）`quota` 词内拼错仍在近邻拦截面之外

**缺陷**：近邻拦截靠 `contains("quota")`，标记词内部拼错（`QUTOA_` / `QUOT_`）落在面外；`unlimited` 之下无声不设帽。

| 槽 | 内容 |
| --- | --- |
| 计划 | **选「用例钉住」而非响亮拒绝**：改精确前缀 + edit-distance 属 `backend/src/main/**` 语义改动、且重新引入主 agent 已裁掉的权衡，本卡写域不含产品语义。故把 `quota` **词内拼错**这一类的实测边界钉进既有单元用例 `environmentQuotaPrefixTypoRefusesTheBoot`（§11.5 允许「加进近邻拒绝断言」）：`EDITORIAL_COST_PROVIDER_QUTOA_MOCK_…`（`ua` 反）与 `EDITORIAL_COST_PROVIDER_QUOT_MOCK_…`（丢尾 `a`）都不含 marker、不在精确前缀上 ⇒ `providers().isEmpty()`、反转型另断 `unconfigured()==UNLIMITED`。报告 §2.4（`:80`）写明边界；门 11 `honesty` 加一条同时盯用例里两个键名与报告里「词内拼错」标记；不新增用例方法 ⇒ 用例数保持 65。 |
| 实测退出码 | `python tests/engineering/T08/verify.py` = **0**（16/16）。新增断言是**正确构造**（不依赖运行）：`QUTOA` 不含 `quota` 子串，`environmentQuotaName` 在 `!startsWith(ENVIRONMENT_QUOTA_PREFIX)` 分支里既 `return`（不绑）又不 `throw`（不拒），`environmentBase()` 未点名任何合法 provider 键 ⇒ `providers()` 必空。真实 surefire 退出码待主 agent 代跑（见 §L）。 |
| 反向控制 | 门 11 侧新增 2 条（计入 77）：「报告把『词内拼错』改口成『所有拼写错误一律拦下』」红；「用例把 `QUTOA_…` 键名换回合法 `QUOTA_…`（边界不再被钉）」红。均 `[REJECT]`。 |
| 良性半边 | 既有对照仍绿：合法单键绑进 provider、`QUOTAS_`（仍含 `quota`）照旧 503 拒装配、`CLUSTER_SHARDS`（不含 `quota`）照旧可读不受影响——新增两条断言只钉住「词内拼错静默落空」这一实测，未把拦截面扩到任何合法名。 |
| 未证明 | 新增的两条 `assertTrue` 需 `mvn` 实跑确认（本卡不跑 mvn）；已在 §L 给主 agent 命令。响亮拒绝方案（改产品）本卡**刻意不做**，非未证明而是未采纳，理由见「计划」。 |

---

## §F F-R5-05（P3）`T08.md:122` 仍写「默认 57」而计数已迁到 65

**缺陷**：同一份报告对当前默认值给了两个数（65 与 57），57 是第三轮旧值；门 11 honesty 盯句子标记不盯这个数字，所以它不会被跑红。

| 槽 | 内容 |
| --- | --- |
| 计划 | 就地订正 `T08.md:122`「默认 **57**」→「默认 **65**」并补 57→65 的逐发现用例名台账（与 `EXPECTED_TESTS` 注释、`T08-Revision-R4.md` §3 对齐）；全文复查所有裸 `57`/旧计数，区分**当前默认值**（须为 65）与**历史运行行**（`r10-pg`/`r4-baseline-57`/`--expect-tests 49`/`--expect-tests 57` 等是当时真实读数，保留）；同步 66→77 只在**实时清单行 `:13`** 改，历史对照行（`:130/:137/:142/:145`）保留其当轮读数不动；核 `EXPECTED_TESTS=65`、`--expect-tests` 默认=`EXPECTED_TESTS`、`:13`、`:122` 四处一致。 |
| 实测退出码 | 无独立命令——这是文本订正；`python tests/engineering/T08/verify.py` = **0** 佐证门 16/`:13` 未被改崩。 |
| 反向控制 | 本轮不为「数字本身」加门（审阅者已指出门 11 honesty 盯句子不盯此数）；改在 §I 用**人读四处对照表**证明一致，避免把报告数字硬编码进第二处看守（会制造 brittle 门）。 |
| 良性半边 | 历史运行行（`:131` 49、`:132/:134` 57、`:136/:143` 57 等）**刻意不改**——它们是当时那轮的真实读数，回改等于伪造历史；只有描述「当前默认」的两处（`:13`、`:122`）改到 65/77。 |
| 未证明 | 无。四处一致性见 §I 实测（`EXPECTED_TESTS` L63、`--expect-tests` 默认 L185、`:13`、`:122` 均为 65）。 |

---

## §G F-R5-06（P3）`run_pg.py` 的 `credentials.txt` 存在重复写入

**缺陷**：`--keep-cluster` 分支 430-434 与 437-441 各写一遍 `credentials.txt`，后者覆盖前者且格式不同；`evidence['credentialsFile']` 赋值两次。

| 槽 | 内容 |
| --- | --- |
| 计划 | 删掉第二次 `credentials.txt` 写入（原 `--keep-cluster` 分支两处 `write_text` + 两处 `evidence['credentialsFile']` 赋值，第二次覆盖第一次且格式不同）；合并为**一处**一致写法（含 `database=`，逐角色口令一行），一次赋值。保留 `print` 与 `inside_repo(...)` 记录。 |
| 实测退出码 | `python -m py_compile run_pg.py verify.py` = **0**；`grep` 自证：`credentials.txt').write_text` 现 **1** 处、`evidence['credentialsFile'] =` 现 **1** 处（原各 2）。真实 `--keep-cluster` 分支需 `mvn`+集群，本卡不跑；逻辑改动纯文本级（少一次覆盖），不改变落点/字段语义。 |
| 反向控制 | 不加门——重复写入不是「被削弱会放行的安全判据」，而是清洁度缺陷，为它造门会教读者去绕无意义的东西；`--path-selftest`（默认与三种输入）仍全 0 佐证无回归。 |
| 良性半边 | `--keep-cluster` 的凭证落点仍在被忽略的 `work` 目录、仍 REDACTED 于 evidence JSON、`--help` 文案（`:193`）未动；不影响任何交付测试路径。 |
| 未证明 | 真实 `--keep-cluster` 运行产出的 `credentials.txt` 内容格式（需 mvn+集群，§L 交主 agent）——但去重是纯删除，语义无歧义。 |

---

## §H 三条不编号观察项（按判断处理，写明取舍）

| 观察 | 处理决定 | 理由 |
| --- | --- | --- |
| ① 单测夹具 `window(scope, lockKey)` 令 `label == lockKey`，该用例自身看不见「按 label 排序」这一退化 | **保留，不改夹具**；把「按 label 排序」这一退化交给门 12 + 反向对照 B1b 看守，不伪装成单测能抓 | `inLockOrder` 按 `Comparator.comparing(Ceiling::lockKey)` 排；夹具里 label 与 lockKey 同值，则「退回按 label 排」在该单测内**观测等价**、不会红——这是夹具的固有局限，不是缺陷。审阅者观察 ① 成立。取舍：若把夹具 label 改成与 lockKey 字典序不同的值，`advisoryLockOrderIsTheDictionaryOrderOfLockKeys` 才能自身区分二者，但那要动 `backend/src/test/**/CostPricingTest.java` 里既有用例的夹具语义、且 F-R4-09 的锁序承重已由**门 12**（`inLockOrder` 唯一入口 + `lockScope` 前 + `lockKey` 实参 + 六窗前缀）与 **B1b「按 label 排」减弱 `[REJECT]`** 双重钉住（见本轮 `--reverse-control`），故不再为观测①增设可能彼此冲突的第二套断言。 |
| ② `BudgetService.java:308-317` javadoc「classic shape of a cross-transaction wait cycle」措辞略强 | **不改产品**；如实登记边界，交主 agent 定夺 | 该行在 `backend/src/main/**`，非本卡写域（本轮只授权 `bound_in` 相关的产品改动，此处与 `bound_in` 无关）。措辞确实偏强：同段末已写「No deadlock has been observed today and none is claimed」，但「classic shape」易被读成「不排就会死锁」。最小更正（交 §L）是把 `:311-312` 改成「the set of keys two racing transactions hold would depend on the request shape (a claim window present or absent) — the *setup* a cross-transaction wait cycle needs」，把「形状」降级为「所需前提」而非既成事实。本卡不自改、不自证。 |
| ③「66/77 条」计的是**场景数**（= `reversals()` 条数），不等于去重后的编辑三元组数 | 本轮报「**77 个减弱场景 / 82 次编辑 / 81 个唯一三元组**」，把口径写明 | 实测（`import verify; reversals()`）：场景 77、编辑三元组共 82、去重 81——仅 1 个三元组（V5 触发器里 `SELECT … FOR UPDATE` 那句诱饵）被 2 个场景共用。上一轮报的「66」同样指场景（其编辑数亦略高）。取舍：反向对照的**语义单位是场景**（一次削弱=一个被拒假设），非「改了几处文本」；继续用场景数、但首次附去重数，避免读者把 77 读成 77 处唯一文本改动。良性探针 8 条不变。 |

---

## §I 计数同步证明

| 计数点 | 现值 | 本轮改动 | 同步证据 |
| --- | --- | --- | --- |
| 静态门数 | 16 | **不变**（本轮只加/改子句，未增删门） | `verify.py` = 16/16，`:13`「16 项静态自检」 |
| 用例数 | 65 | **不变**（F-R5-04 走「扩既有方法断言」，未新增 `@Test`） | 单元 28 + 活库 37 = 65；`EXPECTED_TESTS=65`（`run_pg.py:63`，注释台账 `:42-62` 自证 22+35=57→28+37=65） |
| `EXPECTED_TESTS`（run_pg） | 65 | 不变 | `run_pg.py:63 EXPECTED_TESTS = 65` |
| `--expect-tests` 默认 | `EXPECTED_TESTS` | 不变（取常量，天然同步） | `run_pg.py:185 default=EXPECTED_TESTS` |
| `T08.md` 各处 | `:13` 现写 65/16/77/8；`:122` 现写 65 | `:122` 57→**65**（F-R5-05）；`:13` 反向对照 66→**77**（本轮计数） | 历史运行行（`:130/:132/:134/:136/:142/:143/:145` 的 49/57/66/44）为各轮真实读数，**保留不改** |
| 反向对照减弱条数 | 77 | 66 → **77**（+11：F-R5-01 ×4 [G1/G2/H3/H4]、F-R5-02/03 ×5 [R1/R1b/等值/字段/硬编码 tests]、F-R5-04 ×2 [报告改口/用例键名改回合法]） | `--reverse-control` 打印 `77 weakenings … blind=none, misplaced=none, brittle=none`，退出 0 |
| 良性重写探针 | 8 | 不变 | `--reverse-control` 打印 `8 benign probes`，全绿 |
| 新增/删除/改名用例名集合 | 新增 0、删除 0、静默改名 0 | F-R5-04 只在既有用例 `environmentQuotaPrefixTypoRefusesTheBoot` 内**加断言**，未增删改名 | 单元/活库用例名集合与 R4 §3 完全一致（65 名）；本轮 `bound_in`/门改动只发生在 `verify.py`/`run_pg.py`，未触任何 `@Test` 方法名 |

---

## §J 证据目录清洁自证

| 项 | 要求 | 实测 |
| --- | --- | --- |
| `evidence/r4fix-65.json` 失败原件 | 原样保留不覆盖 | `git show :…/r4fix-65.json` 的 sha256 == 磁盘 sha256（`34201318…b233`），**未被改动**；未覆盖、未删除任何既有证据 |
| 受控证据目录文件数 | 不「顺手多写」，只新增本轮必需 | 105 → **106**：仅新增一个 `evidence/r5-gates.json`（静态门读数，镜像 R4 的 `r4-gates.json`，无 mvn）；磁盘 106、`git ls-files` 105（新文件未 `git add`，符合禁 add） |
| 新证据磁盘 sha256 == `git show :<path>` sha256 | 逐条自证（`.gitattributes` 把 evidence 设 `-text`） | 本卡禁 `git add`，故对**未入库**新文件用等价证法：`git hash-object <file>`（带属性）== `git hash-object --no-filters <file>`（裸字节）——`r5-gates.json` 两者同为 `39cde664…`，且 `check-attr` 显示 `text: unset / eol: lf`（无 eol 转换、`-text` 不重写）。⇒ 属性不改动一个字节，主 agent `git add` 后 `git show :…/r5-gates.json` 的 sha256 必等于磁盘 `82df157d…`。既有已入库件（如 `r4fix-65.json`）则直接实测磁盘 sha256 == `git show` sha256（见上行）。`r5-gates.json` 无 BOM、纯 LF |

---

## §K 清理自证

| 项 | 结果 |
| --- | --- |
| 植入/削弱只在 `$env:TEMP\t08r5fix\` 或 `.work/r5fix-*` | 是。本轮唯一 scratch：`$env:TEMP\t08r5fix\`（H3/H4 探摸脚本）+ `$env:TEMP\t08r5fix_probe.txt`/`t08r5fix_rc.txt`（审阅者静态探针与反向对照输出捕获）+ `tests/engineering/T08/.work\r5fix-scratch\`（证据生成脚本）。**静态门/削弱全走 `verify.py` 的内存 `MUTATIONS` 通道，不落任何仓库文件**；`--path-selftest` 纯只读（跑后 `evidence/sub`、`evidence/evidence`、`.work/evidence` 全 `Test-Path` False） |
| 结束前 `Test-Path` = False | `$env:TEMP\t08r5fix`、`t08r5fix_probe.txt`、`t08r5fix_rc.txt`、`.work\r5fix-scratch` **全部 False**（已删） |
| `.work` 六个哈希旧根 | 属早先会话，**未读未删**，结束仍为原六根 `336f4ccd/6621bb23/8abbdcfd/9da386b1/c1277cf0/d2bdf470`；本轮无新增哈希根 |
| 未跑 `mvn` | 是。全程零 `mvn`；`mvn`/`backend/target` 归 agent-95794bd8。`backend/target` 有近 3 小时内改动的文件属该 mvn 独占会话，**非本卡所写**（本卡对 target 无任何写操作） |
| 未写 `backend/target` | 是。`--path-selftest` 在构建前返回；证据生成器不碰 target |
| postgres | 开工与收工 `Get-Process postgres` 均 **0**；本卡未启任何持久集群（`--path-selftest` 不启动，`--keep-cluster` 未用） |
| `git status` 里属于我的痕迹 | 仅：`M CostPricingTest.java`、`M T08.md`、`M run_pg.py`、`M verify.py`、`?? T08-Revision-R5.md`、`?? evidence/r5-gates.json`——全在可写域内；**未 `git add`/`commit`**（`git ls-files` evidence 仍 105、磁盘 106，差的那 1 即未入库新证据）。并行会话的 `identity/T03*`、`tests/engineering/T03*`、`reviews/T02-*`、`T02-Revision-R05.md`、`check_session_cookie.py` 等 M/?? 一律**未读写** |

---

## §L 需主 agent 代跑的精确命令（含期望值）

本卡不跑 `mvn`、不写 `backend/target`（agent-95794bd8 独占）。静态层已全部实测（见 §A/§B/§C/§D 与 `evidence/r5-gates.json`）。以下需 mvn 或真库：

1. `python tests/engineering/T08/verify.py` → 期望退出 **0**、`16/16`。（本卡已跑，0。）
2. `python tests/engineering/T08/verify.py --reverse-control` → 期望退出 **0**、`77 weakenings, 8 benign probes, blind=none, misplaced=none, brittle=none`。（本卡已跑，0。）
3. 全库静态+契约：`python tests/engineering/T02/check_contracts.py` → `Approved T00 rc.3: 27 hashes verified, no regeneration`。
4. 真库整轮（交付路径，显式点名受控目录）：
   ```
   python tests/engineering/T08/run_pg.py --work-root C:\Users\eie04\AppData\Local\Temp\t08r5fix\outroot --evidence-dir tests/engineering/T08/evidence --evidence-name r5fix-65 --expect-tests 65
   ```
   期望退出 **0**、`Tests run: 65, Failures: 0, Errors: 0, Skipped: 0`（单元 28/28、活库 37/37）、`expectations.problems=[]`、`evidenceLanding.explicitlyChosen=true`。**新增证据文件** `r5fix-65.json` + 同名 `-test-results/`（唯一可再增的两个证据物件）。
5. **F-R5-01 活库证红**（审阅者自带脚本，只读、不改）：
   ```
   python docs/execution/reviews/T08-round5/evidence/r5_gutted_live.py
   ```
   期望：`G1`、`G2` 两具削弱副本整轮退出码**非 0**（`bound_in` 数据流判 False → 门 11 红 → runner 拒写 evidence）；`CONTROL`（未削弱）退出 **0**。静态层已由 `r5_gate_probe.py` 证 G1/G2 各 15/16、红在门 11（见 `evidence/r5-gates.json`）。
6. **F-R5-02 可达拒绝的真实运行半边**：
   ```
   python tests/engineering/T08/run_pg.py --work-root tests/engineering/T08/evidence --evidence-name r5-should-refuse
   ```
   期望退出码 **非 0** 且打印 `…puts the unchosen default evidence into the controlled directory…`（启集群前 `SystemExit`，不产生任何证据）。
7. （可选，交审阅复核）观察 ②：`BudgetService.java:311-312` 的「classic shape of a cross-transaction wait cycle」降级为「the *setup* a cross-transaction wait cycle needs」——属 `backend/src/main/**`，本卡不自改。

## §M 仍未证明清单

| 项 | 为何未证 | 谁来证 |
| --- | --- | --- |
| 65 项真库全绿（含 F-R5-04 新增两条 `assertTrue`） | 需 `mvn`+真库，本卡写域不含 mvn | §L 第 4 条，主 agent |
| G1/G2 **活库**整轮退出非 0（非仅静态 15/16） | 需 mvn 隔离副本 | §L 第 5 条 `r5_gutted_live.py` |
| 真实运行 `raise SystemExit` 的可达拒绝（F-R5-02 半边） | 需真跑一轮（虽在启集群前退出，但属整轮命令） | §L 第 6 条（本卡只能证静态门 13 红 + `--path-selftest` 报 problem） |
| H3/H4（我自造第三/四型）**活库**证红 | 已折进 `reversals()` 静态证红，未单独跑真库副本 | 若审阅要活库件，同 §L 第 5 条机制加两型 |
| 观察 ② javadoc 措辞 | `backend/src/main/**` 非本卡可写 | §L 第 7 条，主 agent 定夺 |
| 「未找到第三型」 | **已找到并证**：H3（正确 loader→env 后再拼接平铺属性写入）、H4（正确 loader→env 后再调同文件助手）——两型都逃过旧第四轮子串检查、只在新 `bound_in` 数据流子句上转红；故本卡**不**写「未找到第三型」 | — |

---

## §N 改动清单

只动可写域：`backend/src/test/java/com/example/editorial/cost/**`、`tests/engineering/T08/**`、`docs/execution/reports/T08*.md`。**未**动 `backend/src/main/**`、`.github/workflows/**`、`STATE.json`、`reviews/**`、`T02/T03/T07/**`、`identity/**`、冻结契约。**未** `git add`/`commit`。

| 文件 | 改动 | 对应发现 |
| --- | --- | --- |
| `tests/engineering/T08/verify.py` | `bound_in()` 改**数据流判定**：`add(...)` 目标变量必须**就是** `from(env)` 读的那具环境（`env.getPropertySources().add*` 目标全等 `env`）；禁体内出现 `new *PropertySource(`、`.setProperty/.withProperty/.getMutablePropertySources/.merge` 属性写入；`from(env)` 后残留任何 `env` 触碰即拒（掐断「正确 loader 之后再平铺写入/助手装配」）；保留 loader→ByteArrayResource(声明变量)→document 三锚点。门 13 `check_runner_paths` 从读句子改读决策：盯 `lands_in_controlled` helper 存在、可达的 `if lands_in_controlled(evidence_dir) and not chosen:` 与 `if lands_in_controlled(evidence_dir): raise`、JSON 字段走同一 helper、自检用 `wanted_suites(args.tests)` 且回显 `'testsInput': args.tests`、禁旧等值式复现。门 11 `honesty` 加 F-R5-04 一条（用例含两型 marker 词内拼错键名 + 报告含「词内拼错」）。`reversals()` +11：G1/G2/H3/H4（F-R5-01，含我自造 H3/H4）、R1/R1b/等值回归/字段回归/硬编码 tests（F-R5-02·03）、报告改口/键名改回合法（F-R5-04）。`benign_probes()` 不变（8）。 | F-R5-01·02·03·04 |
| `tests/engineering/T08/run_pg.py` | 新增 `lands_in_controlled(candidate)`（`== CONTROLLED_EVIDENCE.resolve() or … in candidate.parents`）；`--path-selftest` 落点判定走它并新增 `insideControlledDirectory/testsInput/methodFilterStripped` 回显；真实运行 `if not chosen:` 内加**可达** `raise SystemExit`（启集群前）；`KNOWN_SUITES` 常量 + 自检用 `wanted_suites(args.tests)` 报未知套件名；JSON `insideControlledDirectory` 改走 helper；`--keep-cluster` 分支 `credentials.txt` 两处写**去重为一处**（含 `database=`）、`credentialsFile` 一次赋值。`EXPECTED_TESTS=65` 与台账注释更新到本轮。 | F-R5-02·03·06 |
| `backend/src/test/java/com/example/editorial/cost/CostPricingTest.java` | 既有 `environmentQuotaPrefixTypoRefusesTheBoot` 内**加断言**（未新增方法）：`EDITORIAL_COST_PROVIDER_QUTOA_…`（词内反字）与 `EDITORIAL_COST_PROVIDER_QUOT_…`（截断）均 `providers().isEmpty()`、反转型另断 `unconfigured()==UNLIMITED`。 | F-R5-04 |
| `docs/execution/reports/T08.md` | `:122` 「默认 **57**」→「默认 **65**」并补 57→65 逐发现台账；`:13` 实时清单更新（落点祖先包含、`--tests` 操作者值校验、反向对照 66→**77**）；§2.4（`:80`）加 F-R5-04 词内拼错实测边界段。历史运行行（49/57/66/44）保留。 | F-R5-02·03·04·05 |
| `docs/execution/reports/T08-Revision-R5.md` | 本文件（返工记录）。 | 全 |
| `tests/engineering/T08/evidence/r5-gates.json` | **新增**静态门读数（verify/reverse-control/gate-probe/path-selftest 六读数/计数同步），字节捕获自真实命令。 | 证据自证 |

F-R5-07（父 agent `e4f0f3c` 归属账）不归本卡。注：批量 `git add` + `--renormalize` **并非内容中性**，会按 `.gitattributes` 重写行尾——交付说明里不重复该错误。

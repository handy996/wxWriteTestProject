# T08 第五轮独立复审（成本计量与配额准入）

判决：**CHANGES_REQUIRED**

（**P2 两条**：F-R5-01＝第四轮 F-R4-06「体内绑定证据可降级为文本」**未闭合**，本轮我另找到两型掏法，16 道静态门全绿且真库整轮 65 例全过、`run_pg.py` 退出 0；F-R5-07＝主 agent 的 `e4f0f3c` 提交自述与实际内容不符，把 T03 会话的在途工作以「修换行」的名义记进了主线。**P3 五条 + 清洁项一条**：F-R5-02 落点自检等值非包含（且摘掉判据后门 13 仍绿）、F-R5-03 `--path-selftest` 吃硬编码 `--tests`、F-R5-04 标记词内部拼错仍在近邻拦截面外、F-R5-05 `T08.md:122` 仍写「默认 57」、F-R5-06 `credentials.txt` 重复写入。其余 F-R4 事项我按实测判为关闭。）

### 八个必答问题的逐条结论（每条附最小复现与期望/实测退出码）

| # | 问题 | 结论 | 关键实测（期望 → 实际） |
| --- | --- | --- | --- |
| 1 | F-R4-06 真闭合了吗 | **没有**（P2，F-R5-01） | 期望「A5/E4 红、A8 绿、找不出第三种掏法」。实际：A5 红 **14/16**（门 11+16）✅、E4 红 **14/16** ✅、A8 绿 **16/16** ✅，但 **G1/G2 两型都 16/16 绿**，且把它们送进隔离副本跑真库 → **退出 0、65/0/0**（`evidence/r5-gut-g1.json`、`r5-gut-g2.json`）。复现见 §1.4 |
| 2 | 锁序 F-R4-09 | **关闭** | 期望「删 sort 必须红」。实际 B1/B1b/B1c 各 **15/16 红**（门 12）；`inLockOrder` 在 `BudgetService.java:109`、首个 `lockScope` 在 `:110`；单测用 String 自然序作独立预言、另钉 `PROVIDER-MODEL < PROVIDER` 与新增第 7 窗 ⇒ 非自证；措辞五处审计，**无一处声称今天存在死锁** |
| 3 | F-R4-01 语义有没有被偷改 | **关闭** | 宽窗 `where`/锁键都带 `owner_id`；用例真跑两 Owner 各 2 笔、第 3 笔两侧 429、`assertEquals(4, holds())`，我的真库原件里有该 `testcase` 节点；文档写「待 Owner 决定，本卡不擅自改成全局帽」，未见「已实现全局帽」 |
| 4 | 四条静默路径是否真响亮 | **关闭，残留一条 P3** | 我直调 `BudgetPolicyConfig.from` 造了 20 个反例：近邻前缀 `QUOTAS_/QUOTASS_` → **503 INVALID_PROVIDER_QUOTA_KEY**；文件通道大写段 → **503 INVALID_BUDGET_POLICY**（不再裸栈）；`99999999999` 放行、`2147483648` 拒、`2147483647` 放行；点号规范名进 env 源 → 绑上；三种未知叶 → 503；开关非法值/缺失 → 503。残留：拼错发生在 `quota` 这个词**内部**（`QUTOA_`）时仍在面外（F-R5-04）。`r4fix-65.json` 与 retry 的差异**只落在声称处**（`failure` 只在原件、`totals/expectations` 只在重试件、65 例名单一致、scratch uuid 不同） |
| 5 | 数字是否承重 | **基本承重，报告有 1 处旧数** | 门 14→16 = `check_advisory_lock_order` + `check_runner_paths` 两条新对象（旧 14 条一名未改）✅；反向 44→66 = 新增 22、删除 0、条目名无重复（69 次编辑去重 68，仅 1 个三元组被两场景共用，非凑数）✅；用例 57→65 = 单元 +6、活库 +2、**删除 0、改名 0**（我自己比的名字集合）✅；`EXPECTED_TESTS=65` ⇔ `default=EXPECTED_TESTS` ⇔ `T08.md:13` ✅；但 **`T08.md:122` 仍写「默认 57」**（F-R5-05） |
| 6 | F-R4-12/13 工具修复 | **修好了两半，另有 3 条 P3** | 默认落点确在 `<work-root>/evidence`、`explicitlyChosen=false`，受控目录 **105 文件全程未增**；仓库外绝对根由第四轮的退出 1 变为 **退出 0**；`methodFilterStripped` 剥 `#method` ✅。攻击结果：`--work-root tests/engineering/T08/evidence` → `evidenceDir=…/evidence/evidence`、**`problems=[]`、退出 0**（判据是等值不是包含，F-R5-02）；把判据摘成 `if False:` → 门 13 **仍 16/16 绿**；`--path-selftest` 校验的 `--tests` 是**硬编码**，不吃我传的值（F-R5-03） |
| 7 | e4f0f3c 的证据保真修复（审主 agent） | **修复为真，但同一枚提交自述与实际不符 ⇒ 另立 F-R5-07（P2）** | 全量而非抽样：**1026** 个记录型跟踪文件 **disk vs HEAD 分叉 = 0**；同一批在 `fb62212` 有 **127** 个分叉且全部在 HEAD 修好；磁盘带 CRLF 的 **130** 个与自述精确对上；`docs/execution` 另扫 831 文件也是 **0** 分叉 ⇒ 修复本体 ✅。新规则只覆盖 `evidence/**`、`*-test-results/**`、`output/**`，`check-attr` 实测 authored `.py` 仍 `text: set / eol: lf` ⇒ **没把 authored 一并免掉** ✅。**但是**：我把该提交改到的 136 个文件逐个比 parent/新 blob，**130 个是纯 CR 还原、1 个是 `.gitattributes` 本体、5 个是换行解释不了的真实内容改动**（全属 T03 在途：`check_session_cookie.py` 入库 58,746→155,999 字节、`record_guard_binding.py` 5,392→8,078，两件前后都不含 CR；另 3 件 T03 证据）⇒「restage the affected blobs」「an authored test file hashes the same before and after」「zero still divergent」三句与实测冲突（当下这 135 个里 4 个 disk≠HEAD）。逐条数据 `evidence/r5-e4f0f3c-actual-repair.json` |
| 8 | 主 agent 那次 mvn 越权与撤回 | **自曝与撤回成立，读数未被污染** | 仓库根 `pom.xml` **不存在**（全仓只有 `backend/pom.xml`）⇒ 没有项目就进不了生命周期，`clean` 不可能执行；`backend/target` 仍是 351 文件的完整成品、`~/.m2` 最新 mtime 早于当天；且 T08 三条读数路径**没有一个字节读 `backend/target`**（`run_pg.py:291` 复制时 `ignore_patterns('target')`，`verify.py` 无任何 mtime/时间戳判断）⇒ 即便被清过也不会改变 T08 的退出码。可复核命令见 §8 末 |

复审方：第五轮独立复审 agent（非实施方，非主 agent）
被审对象：
- `47caf6c`（第四轮整改提交）
- `e4f0f3c`（主 agent 自造并自修的仓库级 `.gitattributes` 换行规范化缺陷）
上游判决：`docs/execution/reviews/T08-round4/review.md`（F-R4-01 … F-R4-14）

> 落盘优先于完美。本节以下逐节填写，每完成一节立即写盘。

---

## §0 基线自证

| 项 | 实测 |
| --- | --- |
| `git rev-parse HEAD` | `e4f0f3c131a30f4dba0705d7e167c8eecafd0168`（分支 `main`）——即被审的两笔都已入库，`47caf6c` 是 `HEAD~1` |
| 工作树（开工时） | `M backend/src/test/java/com/example/editorial/identity/T03SessionCookieGuardTest.java`、`M tests/engineering/T03/check_session_cookie.py`、`?? .tmp_state.py`、`?? docs/execution/reviews/T02-round5/`、`?? docs/execution/reviews/T08-round5/`（本目录）、`?? tests/engineering/T03/evidence/config-census.txt`、`?? tests/engineering/T03/evidence/session-cookie-r10.json`。**全部是别的会话的在制品**，我没碰、没提交、没删除 |
| 我未做的事 | 未 `git add`、未 `git commit`、未写 `docs/execution/STATE.json`、未跑 `mvn`（全树）、未写 `backend/target`（`run_pg.py` 用的是它自己的 `.work` 副本）；`git diff --cached` 在我开工前后都只反映他人在制品（我从未执行任何暂存命令） |
| Python | `Python 3.12.14`（派单指定的 `C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`） |
| PowerShell | `5.1.26100.9444`，culture `zh-CN`（故：字节捕获、不用 `[System.IO.*]::`、写盘走 python） |
| `Get-Process postgres` | 开工时 **0 个进程**（无他人集群在跑）；我的 `run_pg.py` 用自己的随机端口集群并在 `finally` 里 `pg_ctl stop`（证据里 `clusterStopped=true`、`clusterStart=pg_ctl`） |
| `tests/engineering/T08/.work/` 基线 | 六个哈希命名根 `336f4ccd…/6621bb23…/8abbdcfd…/9da386b1…/c1277cf0…/d2bdf470…`，与第四轮记录一致 ⇒ **早先会话所有，我不读、不删**；我的运行目录只叫 `r5-*` 或落在 `$env:TEMP\t08r5\` |
| 受控证据目录基线 | `git ls-files tests/engineering/T08/evidence` = **105**，磁盘 `Get-ChildItem -Recurse -File` = **105**（无未跟踪残留）；我在每次 `run_pg` 之后重新计数（见 §6/§13） |
| 临时根 | `$env:TEMP\t08r5\` 开工前 `Test-Path` = **False**，由我创建，结束前删除（§13） |

**我这轮已复现的三条主 agent 读数（独立跑，非照抄）**：

| 命令 | 我的退出码 | 我的读数 |
| --- | --- | --- |
| `python tests/engineering/T08/verify.py` | **0** | `16/16 passed`，逐条 detail 原文见 `evidence/r5-verify-main.txt`（含 `binding evidence … [True, True, True, True] (unit slice 5147 chars, live slice 3688 chars)`、`flat dotted keys inside the case bodies=none`、`inLockOrder applied before lockScope=True`、`evidence default is scratch under --work-root=True`） |
| `python tests/engineering/T02/check_contracts.py` | **0** | `Approved T00 rc.3: 27 hashes verified, no regeneration` |
| `python tests/engineering/T08/run_pg.py --work-root <TEMP 绝对> --evidence-dir <本目录>/evidence --evidence-name r5-main-65 --expect-tests 65` | **0** | `totals 65 / failures 0 / skipped 0`（单元 `28`＋活库 `37`，逐套件读自 surefire 原件）、14 条子命令 `exitCode` 全 `0`、`expectations.problems=[]`、`evidenceLanding={explicitlyChosen: true, insideControlledDirectory: false, directory: docs/execution/reviews/T08-round5/evidence}`、`clusterStopped=true`；V5 指纹 `5eadd5294216…` 与第三/四轮记录一致（冻结迁移未动）。原件：`evidence/r5-main-65.json` + `evidence/r5-main-65-test-results/` |

`--path-selftest` 五种输入的实测见 §6。

**开工后 HEAD 又动了**：`e4f0f3c` → `c55116c`（T02 第五轮复审记录）→ `f5a399a`（`docs(state)`）。我核过 `git diff --name-only e4f0f3c f5a399a`：只有 `docs/execution/STATE.json` 与 `docs/execution/reviews/T02-round5/**` ⇒ **被审的 T08 字节一行未变**，我全部读数仍对应 `47caf6c`+`e4f0f3c` 的入库内容。另记一次我自己造成的口径事故：PowerShell 的 `*>` 重定向写出 UTF-16，所以 `evidence/r5-verify-main.txt` 与 `evidence/r5-reverse-control.txt` 是**转码后的副本**（内容逐行完整，但不是程序原始字节）；需要原始字节请按 §11 第 1 条重跑。

### 0.1 本轮命令台账（退出码一律紧跟命令取）

| 命令（全部我自己执行） | 退出码 | 读数 |
| --- | --- | --- |
| `python tests/engineering/T08/verify.py` | **0** | `16/16 passed` |
| `python tests/engineering/T08/verify.py --reverse-control` | **0** | 66 `[REJECT]` / 8 benign 全绿 / `blind=none, misplaced=none, brittle=none` |
| `python tests/engineering/T02/check_contracts.py` | **0** | 27 hashes verified |
| `python tests/engineering/T08/run_pg.py --work-root <TEMP 绝对> --evidence-dir <我的目录> --evidence-name r5-main-65 --expect-tests 65` | **0** | `totals 65/0/0`（28 单元 + 37 活库）、14 条子命令全 0、`problems=[]`、`clusterStopped=true` |
| `… run_pg.py --path-selftest`（默认 / 仓库外绝对根 / 相对根 / `--evidence-dir 受控目录` / `--work-root 受控目录及其子目录`） | **0**（全部） | 见 §6.2、§6.3 |
| `… r5_gutted_live.py <TEMP> G1`（掏空副本 + 真库整轮） | **0** ❌ | `totals 65/0/0`、`problems=[]` |
| `… r5_gutted_live.py <TEMP> G2` | **0** ❌ | 同上，掏空后的用例确实在 surefire 原件里 |
| `… r5_gate_probe.py A5 E4 A8 G1 G2 B1 B1b B1c` | 0 | 逐条见 §1.1/§1.2/§2.1 |
| `… r5_runner_gate_probe.py`（R1/R2 + 基线） | 0 | 基线 16/16；R1 16/16 ❌；R2 15/16 ✅ |
| `… r5_probe_build.py <TEMP workroot>`（`javac` + `java` 反例探针） | 0（`javac 0`、`java 0`） | 20 条反例结果见 §4.1 |
| `… r5_fidelity.py` / `r5_dupes.py` / `r5_samples.py` / `r5_r4fix_diff.py` / `r5_inventory.py` | 0 | §5、§7、§4.3 |
| `mvn`（任何形式） | **未执行** | 派单禁跑；`backend/target` 未写 |

## §1 F-R4-06 体内证据是否真闭合（A5 掏法 / E4 / A8 良性重写 / 第三种掏法搜寻）

### 1.1 三轮对照的复放（内存重写，不落盘改仓库）

我用 `verify.MUTATIONS` 通道把交付件里的两处用例正文换成四种版本，再跑**全套 16 门**（脚本 `evidence/r5_gate_probe.py`，退出码紧跟命令存下）：

| 对照 | 换进去的东西 | 期望 | 实测 |
| --- | --- | --- | --- |
| **A5**（第四轮掏法：体内证据降级成注释 + 平铺点号键） | 活库用例正文 | 必须红 | **红：14/16**，红门=「provider quota scopes are spelled one way…」＋「acceptance cases still assert what they claim」；detail 原文 `binding evidence …=[True, False, True, False]`、`flat dotted keys inside the case bodies=['live']`、`live slice 4315 chars` |
| **E4**（单元侧同型掏法） | 单元用例正文 | 必须红 | **红：14/16**，同两条门；`=[False, True, True, False]`、`flat dotted keys …=['unit']`、`unit slice 5683 chars` |
| **A8**（良性重写：局部变量接住 `from(env)` 再喂 `service(...)`） | 活库用例正文 | 必须保持绿 | **绿：16/16** ✅ 没有把合法改写误杀 |

结论：第四轮 F-R4-06 要求的「A5 必须红、A8 必须绿」两侧**都成立**，且切片长度（4315/5683）证明它读的是剥掉注释后的**体内**文本，不是装饰。

### 1.2 我找到的第三种掏法：两条都活着（**P2**）

`bound_in()`（[verify.py:730-737](../../../tests/engineering/T08/verify.py#L730-L737)）要求五件事：出现过 `new YamlPropertySourceLoader()`；`.load("…", new ByteArrayResource(VAR.getBytes` 里的 `VAR` 等于体内声明的文本块变量；`document` 正则在体内命中；体内出现字符串 `getPropertySources().add`；体内出现 `BudgetPolicyConfig.from(env)`。平铺键禁令是 `"editorial.cost.provider-quota." in body` 的**子串测试**（[verify.py:751-752](../../../tests/engineering/T08/verify.py#L751-L752)）。这五条**都不检查「解析出来的那批源有没有进到被绑的那个环境」**，子串禁令也**只看得见同一具正文里的字面量**。我据此构造两型（脚本内 `LIVE_G1`/`LIVE_G2`）：

| 掏法 | 内容 | 门层 | 真跑一轮（隔离副本） |
| --- | --- | --- | --- |
| **G1** | 真 loader + 真文档解析进 `r5Decoy` 环境后**丢弃**；再另建 `env`，键名用 `String r5Head="editorial.cost."`、`String r5Quota="provider-quota."` **拼接**出来喂 `service(BudgetPolicyConfig.from(env))` | **绿：16/16** ❌ | `python tests/engineering/T08/run_pg.py … --work-root $env:TEMP\t08r5\gut-G1` → **退出 0**，`totals 65/0/0`，`expectations.problems=[]`（`evidence/r5-gut-g1.json`） |
| **G2** | 同样的诱饵解析；平铺键改由**同文件另一个 helper** `r5FlatQuotaKeys(env)` 写入（helper 不在被检的那具正文里） | **绿：16/16** ❌ | 同上，`gut-G2` → **退出 0**，`totals 65/0/0`；被掏空的 `nestedYamlQuotaIsEnforcedByTheService` 确实出现在 surefire 原件 `TEST-…T08PostgresTest.xml` 里（`evidence/r5-gut-g2-test-results/`） |

也就是说：把「这条用例真的用被 YAML 解析出来的源去绑策略」这件事**整条摘掉**，16 道门全绿、65 条用例（含那条活库用例）全过。第四轮判 F-02 未闭合的理由（「摘空后仍是绿的」）**在这里原样复现**，所以我不能算 F-R4-06 已闭合。

**定级 P2**：门与用例的「嵌套 YAML 绑定」这条断言可以伪绿，且伪绿能穿过一整轮真库运行。不是 P1：生产代码与真实绑定路径本身没坏（我另用直接调 `BudgetPolicyConfig.from` 的反例探针证明语义正确，见 §4），坏的是看守。

### 1.3 我认为够用的收口（供主 agent 参考，非谈判）

1. `bound_in()` 增加数据流一条：`add` 的**目标变量**必须就是 `from(...)` 读的那个变量（G1/G2 都是 `r5Decoy`/helper 写入 `env`，而解析源进的是另一具环境 ⇒ 立刻红）。
2. 平铺键禁令从「体内不得出现该子串」改为「体内不得出现任何写入属性的调用」（`setProperty(`、`withProperty(`，以及**除白名单外**的其它方法调用），使 G1 的拼接与 G2 的 helper 都无处藏。

### 1.4 最小复现命令（主 agent 直接跑）

```powershell
$env:PY='C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
cd E:\project\codex\wxAgent
& $env:PY docs/execution/reviews/T08-round5/evidence/r5_gate_probe.py G1-concatenated-flat-keys G2-helper-flat-keys
# 期望（当前交付件的真实行为）：两条都 "green": "16/16"、"redGates": []
# 收口后应改成：两条都至少 1 道门红
& $env:PY docs/execution/reviews/T08-round5/evidence/r5_gutted_live.py "$env:TEMP\t08r5\gut-G1" G1
# 期望（当前）：退出 0 且 totals 65/0/0；收口后应非 0（或门层先红）
```

## §2 锁序 F-R4-09（ceilings.sort 削弱 / inLockOrder 位置 / 单元用例断言 / 越界措辞）

### 2.1 削弱复放必须红（实测）

| 削弱 | 实测 |
| --- | --- |
| **B1** 删掉 `ceilings = inLockOrder(ceilings);` 这一行 | **红：15/16**，红门「the advisory lock sequence is decided once and watched」，detail `inLockOrder applied before lockScope=False` |
| **B1b** 把 `Comparator.comparing(Ceiling::lockKey)` 改成按 `label()` 排 | **红：15/16**，同门，`sorted by the key it locks=False` |
| **B1c** 锁仍按键排，但 `ledger.lockScope(...)` 传 `label()` | **红：15/16**，同门，`lockScope given lockKey=False` |

第四轮的 B1「14 门 + 57 例全绿」现在被这道门单独盯住，且我用的自建文本（不是它的反向对照条目）也能触发。

### 2.2 应用点确在第一次取锁之前（读码 + 门）

[BudgetService.java:103-110](../../../backend/src/main/java/com/example/editorial/cost/BudgetService.java#L103-L110)：第 103 行 `List<Ceiling> ceilings = ceilings(...)` ⇒ 第 109 行 `ceilings = inLockOrder(ceilings);` ⇒ 第 110 行 `for (Ceiling ceiling : ceilings) ledger.lockScope(ceiling.lockKey());`。门 12 用 `0 <= reserve.find("inLockOrder(ceilings)") < reserve.find("ledger.lockScope(")` 固定这个先后，`lock call sites in reserve=1`（只有一处取锁，不存在第二条绕过排序的路径）。结算路径另有一处 `lockScope("T08|SETTLEMENT|…")`，不在这个预占事务里，不构成乱序源。

### 2.3 单元用例是真断言，不是自证

[CostPricingTest.java:965-995](../../../backend/src/test/java/com/example/editorial/cost/CostPricingTest.java#L965-L995)：夹具 `window(scope, lockKey)` 造的是**真** `BudgetService.Ceiling`（1002-1010 行）。它做四件事——(a) 正序与乱序两具列表过生产的 `inLockOrder` 必须得到同一序列；(b) 该序列等于 `forward.stream().sorted().toList()`，预言是 **String 自然序**，不是再调一次被测比较器；(c) 显式钉住 `T08|PROVIDER-MODEL|… < T08|PROVIDER|…` 这个反直觉事实；(d) 长度 6，且加入第 7 个作用域 `T08|SEARCH|…` 后仍然有序（防「只认识这 6 把键」）。**未见自证结构**（不用被测函数算期望值）。

一条盲点（P3 观察，非新缺陷）：夹具让 `label` 与 `lockKey` 取同一个值，所以**这条用例本身**看不见「按 label 排序」的削弱；该削弱由门 12 抓到（我的 B1b 实测红）。要补就是夹具里把 label 与 key 写成不同串。

### 2.4 措辞越界检查：没有一处声称今天存在死锁

全仓 `死锁|deadlock` 在 T08 交付面只出现 5 处，逐处判定：

| 位置 | 原文要点 | 判定 |
| --- | --- | --- |
| [T08.md:85](../../../docs/execution/reports/T08.md#L85) | 「本轮**不声明今天存在死锁**」 | 合规 |
| [T08.md:93](../../../docs/execution/reports/T08.md#L93) | 「避免跨作用域死锁」＋同段「**本轮没有观测到死锁，也不声明今天存在死锁**——被固定的只是顺序本身」 | 合规（目的是排序的动机，同段已自带免责） |
| `T08-Revision-R4.md:100/101/105/209` | 「不谎称今天存在死锁」「未观测到也不声明存在」＋未证明清单 | 合规 |
| [CostPricingTest.java:958-961](../../../backend/src/test/java/com/example/editorial/cost/CostPricingTest.java#L958-L961) | 「No deadlock is being claimed today and none is claimed by this case」 | 合规 |
| [BudgetService.java:308-317](../../../backend/src/main/java/com/example/editorial/cost/BudgetService.java#L308-L317) | 「…which is the classic shape of a cross-transaction wait cycle. **No deadlock has been observed today and none is claimed**」 | 可接受但措辞偏强：后半句免责到位；前半句把「两笔事务持有的**键集合**随请求形状变化」直接称作等待环的经典形状，严格说集合不同 ≠ 次序反转。建议改成「一旦将来按不同形状加入窗口，就可能出现反转」这种条件句 |

### 2.5 判定

F-R4-09 **闭合**：顺序由一处决定、在第一次取锁前应用、门与用例都真承重、报告未越界。遗留两项进 §10：今天并未观测任何锁序行为（活库没有断言实际取锁次序），以及 2.4 的那句 javadoc 措辞。

## §3 F-R4-01 语义未被偷改（宽窗按 (owner, provider, day) 分区 / 用例真跑两个 Owner / 文档措辞）

### 3.1 代码里宽窗仍按 `(owner, provider, day)` 划分

[BudgetService.java:339-358](../../../backend/src/main/java/com/example/editorial/cost/BudgetService.java#L339-358)：provider 宽窗的 `where` 是 `l.owner_id=? AND l.provider=? AND l.bucket_day=?`，advisory key 是 `T08|PROVIDER|<owner>|<provider>|<day>`；model 窗同理带 `l.owner_id`。类注释 34-42 行明写「every window this service locks and measures is partitioned by `owner_id`, the provider-wide quota window included … whether that limit is one global window or one window per Owner is **the Owner's open decision** … neither the window nor the lock key is to be reinterpreted here」。即：**没有偷偷改成全局帽**，也没有反过来把 SRS 措辞改掉。

### 3.2 用例真跑两个 Owner、第 3 笔两侧都被拒

[T08PostgresTest.java:778-812](../../../backend/src/test/java/com/example/editorial/cost/T08PostgresTest.java#L778-L812) `providerWideQuotaWindowIsPartitionedByOwnerToday`：`EDITORIAL_COST_PROVIDER_QUOTA_MOCK_PROVIDER_MAX_CONCURRENT=2`，先由 `OWNER` 连占 2 笔、第 3 笔 429 `PROVIDER_QUOTA_EXCEEDED`；换成 `OTHER_OWNER` 的文章同样 2 笔放行、第 3 笔 429；`assertEquals(4, holds(), …)` 把「合计 4 笔在飞」钉成数据；末尾另有一条 `SELECT owner_id …` 断言集合恰为 `{OWNER, OTHER_OWNER}`，排除「两个 Owner 其实落在同一行」。我这一轮的真库运行里它确实被执行且通过：`evidence/r5-main-65-test-results/TEST-com.example.editorial.cost.T08PostgresTest.xml` 里有该 `testcase` 节点（`tests="37" failures="0" errors="0"`）。

### 3.3 文档措辞

[T08.md:26](../../../docs/execution/reports/T08.md#L26) 明写「**但这个合并窗口按 `(owner, provider, day)` 划分** … 是两个 Owner 共用一个 provider 凭证时各自 2、合计 4 笔在飞的预占 …「provider 帽是否应跨 Owner 全局生效」是**未定的 Owner 决定**，登记为 `openedBy: T08-REVIEW-4TH` … 本卡不擅自改成全局帽」——如实登记了 SRS:1093 与本卡措辞缺少 Owner 维度这一差异，也把决策悬在 Owner 侧而不是替 Owner 决定。门 11 的 honesty 标记同时要求报告里出现「按 (Owner, Provider, 北京日) 分区」与「待 Owner 确认」两处措辞，删掉即红（该门的反向对照条目在 66 项里）。

判定 **F-R4-01 闭合**：语义没被偷改，行为有活库数据，缺口以未决事项登记而非粉饰。

## §4 四条静默路径变响亮（F-R4-02/03/04/05/10 + InvalidConfigurationPropertyNameException 归一化 + r4fix-65 原件差异）

### 4.1 我自己构造的反例（不读交付用例，直接调装配代码）

我用本轮**自己那轮隔离运行**产出的 `target/classes`（`$env:TEMP\t08r5\workroot\5bcef0e6…\backend\target\classes`）＋ `.tools/t02/m2` 里的 jar，`javac`/`java` 编了一段独立探针 `evidence/R5Probe.java`（构建脚本 `evidence/r5_probe_build.py`，结果 `evidence/r5-behaviour-probe.txt`，`javac exit 0`、`java exit 0`）。**没跑 `mvn`，没碰仓库 `backend/target`**。逐条期望/实测：

| 我构造的形状 | 期望（派单要求） | 实测 |
| --- | --- | --- |
| 前缀多一个字母 `EDITORIAL_COST_PROVIDER_QUOTAS_MOCK_…` | 非 0 / 具名 503 | **503 INVALID_PROVIDER_QUOTA_KEY** ✅ |
| 前缀多两个字母 `…QUOTASS_…` | 同上 | **503 INVALID_PROVIDER_QUOTA_KEY** ✅ |
| 命名空间里带 `quota` 字样但不属于这个子树 `EDITORIAL_COST_QUOTA_MODE` | 说清即可 | **503 INVALID_PROVIDER_QUOTA_KEY**（注释 242-249 行明确写了这条取舍，报告也把它列为请主 agent 决定的运维代价） |
| 标记词内部拼错 `…QUTOA_…` / `…QUOT_…` | 说清即可 | **装配放行、providers 为空**；`unconfigured=refuse` 时在准入点 503 `PROVIDER_QUOTA_NOT_CONFIGURED`（[BudgetService.java:176-183](../../../backend/src/main/java/com/example/editorial/cost/BudgetService.java#L176-L183)），但 `unconfigured=unlimited` 时就是**无声不设帽** |
| env 通道大写段 `…_QUOTA_MOCKPROVIDER_…` | 行为写清 | 放行并绑到小写键 `mockprovider`（与用例声明一致） |
| 文件通道大写段 `editorial.cost.provider-quota.MOCK.max-concurrent` | **必须是归一化 503，不是裸栈** | **503 INVALID_BUDGET_POLICY** ✅（换 `calls-per-day` 叶同样 503） |
| `calls-per-day: 99999999999` | 必须放行（字段是 long） | **OK mock=2/99999999999** ✅ |
| `max-concurrent: 2147483648` | 必须拒而不是截断 | **503 INVALID_BUDGET_POLICY** ✅（`2147483647` 放行） |
| env 形状源里混进点号规范名 | 必须绑上 | **OK mock=7/70** ✅ |
| 同一规范名出现在两个 env 形状源、值相同 | 放行 | 放行 ✅ |
| 同一规范名出现在两个 env 形状源、值**不同** | 说清即可 | 放行并取 precedence 高的一档；[T08-Revision-R4.md:148](../../../docs/execution/reports/T08-Revision-R4.md#L148) 已明写「跨源同名键不拒」是 F-R4-14 的更正，且反向对照第 64 条专门盯这句话被改成「一律拒装配」 |
| 未知叶名 `…_MOCK_MAXCONCURRENCY` / `…_MOCK_SHARDS` | 具名 503 | 均 **503 INVALID_PROVIDER_QUOTA_KEY** ✅ |
| env 通道写 model 级（比 provider.leaf 更深） | 具名 503 | **503 INVALID_PROVIDER_QUOTA_KEY** ✅ |
| 真有 provider 取名 `unconfigured` | 具名 503 | **503 INVALID_PROVIDER_QUOTA_KEY** ✅ |
| `max-concurrent: 0` / `calls-per-day: 0` | 语义分岔保持 | **503 INVALID_BUDGET_POLICY** / **OK mock=9/0** ✅ |
| 开关写非法值 `allow` | 具名 503 | **503 INVALID_BUDGET_POLICY** ✅ |
| 完全不写 `unconfigured` | 具名 503 | **503 QUOTA_NOT_CONFIGURED** ✅ |

**唯一残留**：靠 `contains("quota")` 判近邻，所以把标记词本身拼错（`QUTOA`）不在拦截面内。它今天在默认 `refuse` 下仍然响亮（503 在准入点），只在 `unlimited` 下退化为无声不设帽——而 `unlimited` 本来就是 Owner 主动选择「未列出的 provider 不带 provider 侧帽」。定级 **P3**（写进 §10 未证明 + 建议在注释里把这条边界从「带 quota 字样」收窄为「前缀 edit-distance 1」或直接精确匹配 env 前缀）。

### 4.2 每条静默路径各自有一条 [REJECT] 对照

反向对照逐条实录（我自己跑的 `--reverse-control`，`evidence/r5-reverse-control.txt`）：第 53 条 F-R4-02、第 54 条 F-R4-05、第 55 条未知叶名、第 56 条 F-R4-04 int 通道、第 57 条 F-R4-03 裸栈逃逸、第 52 条 F-R4-11a 拒绝顺序翻面——**六条各自触发、各自具名**，共 66 条全 `[REJECT]`。我另外用自建的削弱文本（`r5_gate_probe.py` 的 S1…S5，不抄它们的靶文本）逐条复放，全部使门 11 变红。

### 4.3 `InvalidConfigurationPropertyNameException` 那次失败的真身

原始 `tests/engineering/T08/evidence/r4fix-65.json`（我没改）第 13 条命令记录里就是：`CostPricingTest.environmentChannelAddressesProvidersInLowerCaseOnly:846 ? InvalidConfigurationPropertyName Configuration property name 'editorial.cost.provider-quota.MOCK.max-concurrent' is not valid`、`Tests run: 65, Failures: 0, Errors: 1`、`BUILD FAILURE`、退出 1，运行目录是 `…\Temp\t08r4fix\outroot\38bc3475…\backend\target\surefire-reports`（即隔离副本，不是仓库 `backend/target`）。我用 `evidence/r5_r4fix_diff.py` 逐字段对比原件与 `r4fix-65-retry.json`：**仅** `failure` 只在原件出现、`expectations/suites/testResults/totals` 只在重试件出现（前者根本没走到那步）、10 个非易变字段一致、`casesOnlyInFirst=[]`、`casesOnlyInSecond=[]`（两侧都是 65 条同名用例）、两次运行的 scratch uuid 不同（`38bc3475…` vs `af9ef8d9…`）⇒ 差异**只在被声称的地方**，没有把失败悄悄换成另一件事。

## §5 数字口径承重（14→16 新增两条真看守 / 44→66 无重复计数 / 57→65 删除 0 改名 0 / 三处同步）

### 5.1 门 14→16：两条真新增，不是一劈二

我把 `fb62212` 与 HEAD 的 `verify.py` 都取出来数：`def check_*` 与 `CHECKS` 表项都是 **14 → 16**，名称集合差 = **`check_advisory_lock_order` + `check_runner_paths`**，旧 14 条一条没改名、没删除。两条新门盯的是**过去没人看的新对象**（锁序、runner 落点），不是把旧门的断言拆开。它们也确实会红：§2.1 的 B1/B1b/B1c 三条自建削弱各只红门 12；反向对照第 47–51、58–60、66 条分别红在门 12/13。

### 5.2 反向对照 44→66：数的是场景，不是拼凑

按名称集合对比 `fb62212` 与 HEAD 的 `reversals()`：**44 → 66，新增 22 条，删除 0 条**；良性探针 5 → 8。我另数了三件事（`evidence/r5-reversal-inventory.json`、`evidence/r5-duplicate-triples.json`）：66 个条目名**无一重复**，展开成 (文件,旧文,新文) 三元组共 69 个，其中 68 个互不相同 ⇒ 只有 **1 个三元组被两个场景共用**：`V5__cost_ledger_pricing.sql` 里那句 `SELECT budget_limit … FOR UPDATE` 的改写，同时是「诱饵注释顶替锁」和「锁挪到聚合之后＋前面留诱饵」两条场景的第一步。两条场景本身不同（后者还多一次搬锁的编辑），所以**不是拿同一刀凑两个数**，但严格讲「66 条减弱」计的是场景数（69 次编辑、68 种编辑），报告没有把这层区分写出来 —— 一句措辞建议，不算缺陷。
逐条实录：`--reverse-control` 我跑出的输出是 66 行 `[REJECT]`、8 行 `[benign ]`，汇总行 `blind=none, misplaced=none, brittle=none`（`evidence/r5-reverse-control.txt`；注意它是 PowerShell UTF-16 转码来的副本，不是程序原始字节，已在 §0 声明）。整轮退出码 **0**。

### 5.3 用例 57→65：0 删除、0 静默改名（我自己比对名字集合）

从 `git show fb62212:…` 与 HEAD 各自抽出 `void xxx(` 名字集合：

| 文件 | 前 | 后 | 新增 | 删除 |
| --- | --- | --- | --- | --- |
| `CostPricingTest.java` | 22 | 28 | `advisoryLockOrderIsTheDictionaryOrderOfLockKeys`、`canonicalQuotaNamesInsideAnEnvironmentShapedSourceAreBound`、`dayCountLeafCarriesTheLongTheRecordStores`、`environmentChannelAddressesProvidersInLowerCaseOnly`、`environmentQuotaPrefixTypoRefusesTheBoot`、`everyUnknownQuotaLeafRefusesTheBoot` | **[]** |
| `T08PostgresTest.java` | 35 | 37 | `providerWideQuotaWindowIsPartitionedByOwnerToday`、`theArticleCeilingSpeaksBeforeTheProviderQuotaWindow` | **[]** |

22+35=57 → 28+37=65，与「每发现一条加一条」的口径一致；删除集合两侧皆空 ⇒ 无「删旧加新」也无改名换数。三条新增用例名在我自己的真库 surefire 原件里都有 `testcase` 节点（§3.2）。

### 5.4 三处同步

`run_pg.py:60 EXPECTED_TESTS = 65` ⇔ `run_pg.py:169 --expect-tests` 的 `default=EXPECTED_TESTS`（不是又写一遍字面量）⇔ `T08.md:12/13` 的「合计 65 项」「默认 `--expect-tests 65`」——**这三处一致**。
但 **`T08.md` 第 6 节参数说明那一行仍写「`--expect-tests`（默认 **57**；44 → 47、47 → 49 …）」** ⇒ 同一份报告里对当前默认值给了两个数（65 与 57），57 是第三轮的旧值。定级 **P3**（文档自相矛盾；门 11 的 honesty 检查盯的是句子标记，不盯这个数字，所以它不会被跑红——正是 F2-05/F-R4-14 那一类「报告与代码不同步」的复发）。修法：那一行改成 65 并把 49→57→65 写成历史，或让门 11 顺手要求报告出现「默认 `--expect-tests 65`」而禁止「默认 **57**」。

顺带一项无足轻重但要说清：`run_pg.py` keep-cluster 分支里 `credentials.txt` 被写了**两遍**（430-434 与 437-441，后者覆盖前者、格式不同，`evidence['credentialsFile']` 也赋值两次）。不影响任何读数（我不带 `--keep-cluster` 跑），P3 清理项。

## §6 F-R4-12/13 工具修复（默认落点 / --path-selftest 三输入 / 攻击落点自检）

### 6.1 不带 `--evidence-dir` 时确实落在 `<work-root>/evidence`

`--path-selftest`（默认参数）实测：`workRoot=E:/project/codex/wxAgent/tests/engineering/T08/.work`、`evidenceDir=…/.work/evidence`、`evidenceDirChosen=false`、退出 **0**。我自己的整轮运行显式点名了 `--evidence-dir docs/execution/reviews/T08-round5/evidence`，JSON 里 `explicitlyChosen=true / insideControlledDirectory=false`，而受控目录 `tests/engineering/T08/evidence` 的文件数在我全部运行前后都是 **105**（= `git ls-files` 的 105），**没有增长**（§0 基线、§13 收尾各数一次）。

### 6.2 三种输入的期望我逐条复现

| 输入 | 期望 | 实测 |
| --- | --- | --- |
| 默认 | 仓库内 `.work` 下 scratch，`explicitlyChosen=false`，退出 0 | ✅ 退出 **0** |
| 仓库外绝对根（`$env:TEMP\t08r5\workroot`） | 第四轮判它「全绿却 exit 1」是缺陷，现应只记 note | ✅ `problems=[]`、`notes=[…a deliberate --work-root, not a defect…]`、退出 **0**（第四轮的 F-R4-13 这一半确实修好了） |
| `--tests CostPricingTest#method` 形状 | 剥掉 `#method` 后再判套件存在性 | ✅ `methodFilterStripped=["CostPricingTest","T08PostgresTest"]` |
| 相对路径根（`.work-r5-tmp`） | 与绝对写法同结果 | ✅ 解析为 `E:/project/codex/wxAgent/.work-r5-tmp`，目录**未被创建**（`Test-Path` False），退出 0 |

**一条没修到的地方（P3）**：`--path-selftest` 校验的 `--tests` 是**硬编码**的字符串（[run_pg.py:210](../../../tests/engineering/T08/run_pg.py#L210)），不是操作者真正传进来的 `args.tests` ⇒ 自检永远看不见我传的方法过滤器，`--path-selftest --tests CostPricingTest#dayCountLeaf…` 输出的 `methodFilterStripped` 仍是那两个类。反向对照第 59 条盯的是「套件检查比原始 `--tests` 值」，所以**真跑**那条路径被固定住了，但**自检声称检查的那条路径不是操作者走的那条**。修法是 `wanted_suites(args.tests)`，另在输出里回显原始输入。

### 6.3 我攻击落点自检的结果

自检的判据是等值而不是包含（[run_pg.py:207](../../../tests/engineering/T08/run_pg.py#L207)、[:460](../../../tests/engineering/T08/run_pg.py#L460)：`evidence_dir == CONTROLLED_EVIDENCE.resolve()`）。于是受控目录的**子目录**不被当作受控目录：

| 我构造的调用（只跑 `--path-selftest`，它一个字都不写） | 实测 |
| --- | --- |
| `--path-selftest --work-root tests/engineering/T08/evidence` | `evidenceDir=…/T08/evidence/evidence`、`evidenceDirChosen=false`、**`problems=[]`、退出 0** |
| `--path-selftest --work-root tests/engineering/T08/evidence/r5-sub` | `evidenceDir=…/evidence/r5-sub/evidence`、`problems=[]`、退出 0 |
| `--path-selftest --evidence-dir tests/engineering/T08/evidence/r5-sub` | `evidenceDir=…/evidence/r5-sub`、`explicitlyChosen=true`、退出 0 |
| `--path-selftest --work-root tests/engineering/T08/.work`（对照，合规） | `evidenceDir=…/.work/evidence`，退出 0 |

三次攻击后我重新数了受控目录：仍是 **105**，且 `r5-sub` 没被创建（`Test-Path` False）——**`--path-selftest` 本身确实不写盘**。但按 [run_pg.py:458-465](../../../tests/engineering/T08/run_pg.py#L458-L465) 同一套算式，真跑一轮就会把 `r5-*.json` 与 `-test-results/` 落到 `tests/engineering/T08/evidence/…` 里面，而同一份 JSON 会自称 `insideControlledDirectory=false`。派单问「能否构造出一次仍然写进受控目录而不被发现的调用」——**能**，就是上面第一/二行。我**没有真的执行那次写入**（硬规则只允许我写 `docs/execution/reviews/T08-round5/`），证据是自检算出的落点原文 + 那 3 行源码 + 门 13 的 detail（`unchosen landing is refused and recorded=True`）。定级 **P3**（要操作者主动把 `--work-root`/`--evidence-dir` 指进受控树才会发生，且同名拒写挡住了覆盖既有证据）。

门 13 自身的两个盲点（我用自己的削弱文本测的，`evidence/r5_runner_gate_probe.py`）：

| 削弱 | 实测 |
| --- | --- |
| R1 把自检判据改成 `if False:`（拒写逻辑摘掉，字符串仍在别处） | **16/16 仍绿** ❌ ⇒ 门看的是「这句话还在」，不是「这条拒写还可达」 |
| R2 把默认落点从 `work_root/'evidence'` 改成 `CONTROLLED_EVIDENCE/'r5'/'evidence'` | **15/16 红**（门 13）✅ ⇒ 默认落点表达式确实在监视面内 |

建议（非谈判）：判据与 JSON 字段都换成**包含**判断（`CONTROLLED_EVIDENCE in evidence_dir.parents or evidence_dir == …`），另加一条反向对照专门把 `and not chosen` 摘掉——那正是 R1 测出来的洞。

## §7 e4f0f3c 证据保真修复（sha256 全量核对 / 提交实际内容 / .gitattributes 规则面）

派单要求抽 3 个文件比 disk-vs-HEAD、抽 2 个比 disk-vs-`fb62212`。我做了**全量**（脚本 `evidence/r5_fidelity.py` + `evidence/r5_dupes.py`，结果 `evidence/r5-fidelity-census.json`、`evidence/r5-duplicate-triples.json`、逐文件抽样 `evidence/r5-fidelity-samples.json`），用 `git cat-file blob HEAD:<path>` 与磁盘字节各算一次 sha256：

| 测项 | 实测 |
| --- | --- |
| `tests/engineering` 下跟踪文件 | 1130 |
| 属「记录型」（evidence / `*-test-results` / output）且跟踪 | **1026** |
| HEAD 字节 ≠ 磁盘字节的记录型文件 | **0** ✅（要求是抽 3 个一致，这里是 1026 个全一致） |
| 同一批在 `fb62212`（修复前）与磁盘分叉的 | **127**（其中 124 个磁盘带 CRLF）——历史仍未改写 ✅ |
| 127 个是否都在 HEAD 变一致 | **是**（`divergentAtPreFixAllFixedAtHead=true`） |
| 磁盘仍带 CRLF 的记录型文件 | **130**（= 124 个分叉过的 + 6 个 47caf6c 新加、入库时规则已修好所以本来就一致的），与主 agent 自述的 130 精确对上 |
| `fb62212` 之后新增的记录型文件 | 17 |
| 磁盘上不存在的记录型文件 | 0 |
| **另扫 `docs/execution` 全树**（message 声称那边「只是靠全局 `* -text` 侥幸幸存」） | 831 个跟踪文件、磁盘带 CRLF **304** 个、disk ≠ HEAD **0** 个 ⇒ 该说法成立 ✅ |
| HEAD 仍分叉的** authored **文件 | 仅 `tests/engineering/T03/check_session_cookie.py`——他人在途修改（`git status` 里的 `M`），不是换行产物 |
| authored `.py/.java/.sql/.md/.yml` 磁盘带 CRLF 的 | 0 |

抽样原文 4 条（`r5-fidelity-samples.json`）：`T08/evidence/main-repro-1-test-results/TEST-…CostPricingTest.xml` 31438 == 31438 == 31438（磁盘无 CR，修复前后都不该分叉——这条**不是矛盾**）；`T05/evidence/…dumpstream` 313 == 313 == 313 同理；**CR 类的正例**是 message 举的那个形状，我在 130 个纯还原项里逐条核到 `313 → 318`（dumpstream）、`335 → 339`（surefire `.txt`）、`899 → 911`（失败摘要 `.txt`）等，还原后 disk == HEAD ✅。**注意**：另两条样本 `T03/evidence/T03SessionCookieGuardTest.txt`（362→363）与 `.xml`（30,449→33,738）在 `fb62212` 的差异**不是**换行造成的，而是 7.3 里那笔被顺手带进去的内容改动，别把它们当换行缺陷的证据。

### 7.1 三处措辞里，两处诚实、一处与事实不符

诚实的两处（逐条我能证实）：「**I did not delete history.** Old commits still carry the normalised blobs, so a reviewer who verifies a recorded digest against an older commit rather than against HEAD will still see a mismatch」——实测 127 个仍在 `fb62212` 分叉 ✅；「Known limitation of the repair: the rules cover the shapes we actually produce today … the real guard belongs in the evidence writing path itself, and I am recording that as an open item rather than pretending the attribute file is exhaustive」✅ 没有假称属性文件穷尽。

**但同一枚提交里有两句与我的实测冲突**（逐文件比对见 7.3）：「`git add --renormalize` to restage **the affected blobs**」「an authored test file hashes the same before and after the command, proving the repair moved the index and not the tree」「the census says 135 staged files now hash identical to their disk bytes, **zero still divergent**」。

### 7.2 新规则覆盖面与 authored 源

`.gitattributes` 现在 15 行，新增 4 条全部 `-text` 且路径受限：`/tests/engineering/**/evidence/**`、`/tests/engineering/**/*-test-results/**`、`/tests/engineering/output/**`（第三条是 PNG 那条的老邻居，本次补的是 output）。用 `git check-attr text eol -- <file>` 实测可达性：

| 文件 | text | eol |
| --- | --- | --- |
| `tests/engineering/T08/verify.py` | **set** | **lf** ✅ 没被顺手免掉规范化 |
| `tests/engineering/T08/run_pg.py` | set | lf ✅ |
| `tests/engineering/T02/check_contracts.py` | set | lf ✅ |
| `tests/engineering/T08/evidence/r5-*.json` 之类记录型 | **unset** ✅ | — |

即：**没有把 authored `.py` 排除在换行规范化之外**，被豁免的只有记录型输出。

### 7.3 我逐个比对了 `e4f0f3c` 改到的 136 个文件的 parent blob 与新 blob（关键发现）

判据：`新 blob 把 CRLF 换成 LF 后 == 旧 blob` 且旧 blob 不含 CR ⇒ 该文件的入库差异**完全**由换行还原解释；否则就混进了别的内容。脚本 `evidence/r5_commit_reality_check.py <rev>`（只读，只调 `git cat-file`），数据 `evidence/r5-e4f0f3c-actual-repair.json`。脚本把 `.gitattributes` 也算进「内容改动」（它本就是规则本体），所以它报 `contentChangeNotLineEndings=6`，剥掉那一项才是下面表格里的 5 项意外内容。
**方法自曝**：这个脚本我第一次写反了判据（拿 parent 去 CR 后比 new），当时得到「136 个全是无法解释」的错误结论；发现方向反了之后改正重测，才得到下面的形状。错误版本没有留下任何引用，此处记录是为了让后来人能看清这条结论是被两次测量收敛出来的。

| 分类 | 数量 | 明细 |
| --- | --- | --- |
| **纯 CR 还原**（即 message 声称的修复本体） | **130** | `tests/engineering/integration/**` 79 个 + `tests/engineering/T08/**` 51 个；**这 130 个现在 disk == HEAD 全成立** ✅ 与「130 of them still carrying CRLF exactly as produced」精确对上 |
| 规则本体 | 1 | `.gitattributes`（应有 ✅） |
| **换行无法解释的真实内容改动** | **5** | 全是 **T03 的在途工作**：authored `check_session_cookie.py` 入库字节 **58,746 → 155,999**（`--numstat` 2,702 增 / 846 删，前后**都不含 CR**）、authored `record_guard_binding.py` **5,392 → 8,078**（106/63，同样不含 CR）、`T03/evidence/T03SessionCookieGuardTest.txt` 362→363、`.xml` 30,449→33,738、`guard-test-binding.json` 2,003→4,920 |
| blob 未变 | 0 | — |

⇒ **两句自述与实测冲突**：

1. 「I used `git add --renormalize` to restage **the affected blobs** rather than touching a single working file」＋「an authored test file hashes the same before and after the command, **proving the repair moved the index and not the tree**」。实测：这枚标着「stop line ending normalisation from rewriting recorded evidence」的提交，把**两个 authored `.py`** 的入库内容改写了共 **+2,808 / −909** 行。机制上说得通：`--renormalize` 对匹配路径是**从工作树重录内容**，路径面一旦盖到 authored 文件，别人未提交的在途代码就会跟着进索引、进提交。我**无法区分**「被 `--renormalize` 扫到」与「提交前早已 staged」——两者结果相同：T03 会话的未完成工作被记进了这枚提交，而 message 说没动 authored 文件。
2. 「the census says 135 staged files now hash identical to their disk bytes, **zero still divergent**」。实测当下：这 135 个里**有 4 个 disk ≠ HEAD**（上面 T03 那 4 件，`record_guard_binding.py` 已一致）。公平地说：这句在提交那一刻**可能**成立，但历史不自证——我看到的只是结果，而 T03 会话此刻仍在编辑（`git status` 里那 4 件都是 `M`），所以它作为**留给后人的证词**已经是假的；真正扛得住的指控是第 1 条那 5 笔内容改动，不是这句的过期。

诚实边界：我没有、也无法证明主 agent 当时用的具体 pathspec；我只证到「差异形状」（130 个纯 CR + 5 个真实内容）与「message 的自述与该形状不符」。

定级 **P2**（F-R5-07），理由：它不改变 T08 的任何测量结论（这 5 个文件与本卡无关），但它把他人未完成的代码以「修换行」的名义写进主线，破坏可审计性与归属；同一手法复用会直接顶掉 T03 自己的提交。要求见 §11 第 9 条（就地更正，不动历史）。



### 7.4 一个必须写清的边界（不是指控）

修复只保证「HEAD 的 blob == 磁盘字节」。任何人对**历史提交**做摘要核对（`git show fb62212:<path>`）仍会拿到被规范化过的字节——这一点主 agent 在 message 里已明写。因此本轮及历轮「用摘要证词」的引用应一律写成「对 HEAD/磁盘取摘要」；`docs/execution/reviews/T08-round4/review.md` 里我上一轮的一些 sha 引述如果指向旧 blob，需按这条口径重读（这是我的口径问题，不是交付缺陷）。

判定：**换行修复本身为真**（1026 个记录型文件 disk==HEAD、127 个历史分叉全部修好、新规则只豁免记录型且没有把 authored `.py` 一并免掉、`I did not delete history` 属实）**；但同一枚提交的自述与实际内容不符 ⇒ 另立 F-R5-07（P2）**，见 7.3。另有一条它自己登记的 open item（守卫应落在写证据的代码里，而不是 `.gitattributes`），与我 §6.3 的「等值而非包含」是同一件事的两端 ⇒ 一并进 §11。

## §8 主 agent 的 mvn 违规自曝与撤回是否成立

**它自曝的事**：`95794bd8` 持有 maven 独占期间，它在仓库根跑了 `mvn clean verify`（漏了 `-f backend/pom.xml`），0.062 秒 BUILD FAILURE，随后在同一会话里撤回了「可能污染了你的读数」这句它先说的话。

**我能证的三件事（都不需要跑 `mvn`）**：

1. **失败机制成立**：全仓只有一个 `pom.xml`，位于 `backend\pom.xml`（`Get-ChildItem -Recurse -Filter pom.xml` 排除 `.work` 后只此一条），仓库根 `Test-Path pom.xml` = **False**。Maven 在项目目录解析失败时**根本不会进入生命周期**，所以 `clean` 这个 goal 不可能被执行——「0.062 秒」与「没 POM 就退场」是一致的，而不是一次跑了一半的构建。
2. **没有落盘痕迹**：`backend/target` 仍然存在且是完整构建成品（**351** 个文件，子目录 `classes/test-classes/generated-sources/maven-status/maven-archiver/surefire-reports` 俱在；最旧文件 2026-10-03，10-08 当天 329 个）。若那次 `clean` 真跑过，目录会被删掉再由后续 goal 重建；`clean` 单独失败也会留下 `Deleting …` 的输出与空的 target。另外用户级 `~/.m2`（它没带 `-Dmaven.repo.local`，若真开始解析依赖会写这里）里 2150 个样本文件的**最新 mtime 是 2026-10-06T16:26:29**，早于今天这次尝试 ⇒ 那次尝试连本地仓库都没碰。
   诚实边界：`backend/target` 归 `95794bd8` 在用（我第一次量到最新 04:32:03，两分钟后再量已是 05:51:54），所以「时间戳早于尝试」这句我只能对它**当时**的观测作部分印证，不能当恒真事实用。真正扛结论的是第 1 条的机制。
3. **读数不可能被污染**：T08 的三条读数路径都不读 `backend/target`——`verify.py` 的门全部读源码/文档/迁移原件（我 grep 过 `getmtime|st_mtime|LastWriteTime`，**0 命中**，即没有任何按时间戳的判断）；`run_pg.py:291` 复制 `backend/` 时 `ignore=shutil.ignore_patterns('target')`，`:375` 只读它自己副本里的 `backend/target/surefire-reports`；`check_contracts.py` 只核 27 个冻结摘要。⇒ 即便共享 `target` 被清过，T08 的三个退出码也不会变。

**撤回是否到位**：到位。它没有把「可能污染」留在文里当免责，而是改口为「无损害」，并且这条改口与我上面三条独立可核。它同时也承认了违规本身（在独占期跑 `mvn`），没有粉饰成「反正没影响所以不算违规」。

判定：**自曝与撤回成立，无读数被污染，无文件受损**。因此我不把它列进 F-R4 缺陷表；只进 §10 一句「本轮再次发生越权跑 `mvn`（虽无损害），纪律项」。可执行的复核命令（给主 agent，不用我代跑）：

```powershell
Test-Path E:\project\codex\wxAgent\pom.xml              # 期望 False（机制成立的前提）
(Get-ChildItem E:\project\codex\wxAgent\backend\target -Recurse -File).Count   # 期望 > 0 且与完整构建一致
Select-String -Path E:\project\codex\wxAgent\tests\engineering\T08\run_pg.py -Pattern 'ignore_patterns'
# 期望命中 shutil.ignore_patterns('target')
```

---

## §9 F-R4-01 … F-R4-14 闭合判定表

| 编号（第四轮定级） | 一句话事项 | 判定 | 我的依据（全部为本轮实测） |
| --- | --- | --- | --- |
| F-R4-01（P2） | 宽窗带 `owner_id`，文档/用例失真 | **关闭** | §3：代码带 `l.owner_id`、活库用例两 Owner/`holds()=4`、`T08.md:26` 明写「待 Owner 决定，本卡不擅自改成全局帽」 |
| F-R4-02（P3） | 近邻 env 前缀静默 | **基本关闭**，残留另编 F-R5-04 | §4.1：`QUOTAS_`/`QUOTASS_` 实测 503；反向对照第 53 条红；但标记词内部拼错仍在拦截面外 |
| F-R4-03（P3） | 大写段逸出裸栈 + 措辞 | **关闭** | §4.1：文件通道大写段实测 **503 INVALID_BUDGET_POLICY**（两条叶各一），env 通道小写约定写进 javadoc 与用例；反向对照第 57/62 条红 |
| F-R4-04（P3） | `calls-per-day` 绑成 int | **关闭** | §4.1：`99999999999` 放行、`2147483648` 拒（不是截断）、`2147483647` 放行；反向对照第 56 条红 |
| F-R4-05（P3） | env 形状源里的点号规范名被丢 | **关闭** | §4.1：实测 `OK mock=7/70`；反向对照第 54 条红 |
| **F-R4-06（P2）** | 体内绑定证据可降级成文本 | **未关闭** ⇒ 新编号 **F-R5-01（P2）** | §1：A5/E4 已红、A8 仍绿，但我另找到 G1/G2 两型掏法，**16 门全绿且真库整轮 65/0/0 退出 0** |
| F-R4-07（P3） | `java_method_body` 数字面量/注释里的花括号 | **关闭** | 切片走 `java_mask` + 等长剥注释；我复放的 8 条良性里「字面量与注释里的花括号落进活库配额用例」保持 16/16；我的 A5/E4 切片长度 4315/5683 正常，无塌缩/吞类 |
| F-R4-08（P3） | 注释说法与字节不符 | **关闭** | [verify.py:329-345](../../../tests/engineering/T08/verify.py#L329-L345) 现点名 F-R4-08 并逐条撤回旧说法；`fb62212` 的提交信息是历史文本，不能改，本轮以代码注释为准 |
| F-R4-09（P3） | 锁序声称无人看管 | **关闭** | §2：B1/B1b/B1c 三条自建削弱各红门 12；`inLockOrder` 在第 109 行应用、第 110 行才取锁；单测预言用 String 自然序而非被测比较器；措辞五处审计未见「今天存在死锁」 |
| F-R4-10（P3） | 未知叶子无看守 | **关闭** | §4.1 三种未知叶形状全部 503；反向对照第 55 条红；我的 S5 自建削弱红 |
| F-R4-11a（P3 文档） | 拒绝顺序写反 | **关闭** | 门 11 `ceilings measured before the quota pass=True (measure@2792, quota@3630)`；反向对照第 52/63 条红 |
| F-R4-11b（P3 覆盖） | 没有用例钉住顺序 | **关闭** | 活库 `theArticleCeilingSpeaksBeforeTheProviderQuotaWindow` 在我的 `r5-main-65-test-results` 里有 `testcase` 节点并通过 |
| F-R4-12（P3 工具） | 默认证据写进受控目录 | **基本关闭**，残留另编 F-R5-02 | §6.1/§6.3：默认落 `<work-root>/evidence`、受控目录须显式点名、落点写进 JSON、受控目录 105 文件未增；但判据是等值不是包含，子目录照样进；且摘掉 `and not chosen` 后门 13 仍 16/16 |
| F-R4-13（P3 工具） | selftest 拒仓库外绝对根、套件检查比原始 `--tests` | **基本关闭**，残留另编 F-R5-03 | §6.2：仓库外绝对根现在 `problems=[]`、退出 0（第四轮实测为退出 1）；`methodFilterStripped` 正确剥 `#method`；但自检吃的是硬编码字符串 |
| F-R4-14（P3 文档） | 「歧义即拒」未限定范围 | **关闭** | [T08-Revision-R4.md:148](../../../docs/execution/reports/T08-Revision-R4.md#L148) 明写「跨源同名键不拒」，我的探针实测与之**一致**（放行并取 precedence）；反向对照第 64 条专门盯这句话被改宽 |

### 本轮新发现

| 编号 | 定级 | 事项与最小复现 |
| --- | --- | --- |
| **F-R5-01** | **P2** | 体内绑定证据仍可整段摘空。G1（诱饵解析 + `r5Head + r5Quota` 拼接平铺键）、G2（同文件 helper 装平铺键）两型都让 16 门全绿，且真库整轮 `65/0/0` 退出 0。命令见 §1.4。收口建议见 §1.3（把「add 的目标变量必须就是 `from(...)` 读的那具环境」与「体内不得出现任何属性写入调用」两条加进 `bound_in`）。 |
| **F-R5-02** | P3 | 落点自检判据 `evidence_dir == CONTROLLED_EVIDENCE.resolve()` 是**等值**（[run_pg.py:207](../../../tests/engineering/T08/run_pg.py#L207)、[:460](../../../tests/engineering/T08/run_pg.py#L460)），故 `--work-root tests/engineering/T08/evidence[/子目录]` 会把证据写进受控目录且 JSON 自称 `insideControlledDirectory=false`（实测 `problems=[]`、退出 0）。配套洞：把判据改成 `if False:`，门 13 仍 **16/16**（我的 R1 实测）。改成包含判断（`CONTROLLED_EVIDENCE in evidence_dir.parents or ==`）并加一条摘除 `and not chosen` 的反向对照。 |
| **F-R5-03** | P3 | [run_pg.py:210](../../../tests/engineering/T08/run_pg.py#L210) 的 `--path-selftest` 把 `--tests` **写死**成 `CostPricingTest#dayCountLeaf…,T08PostgresTest`，校验的不是操作者传的值（实测：我传 `--tests CostPricingTest#…` 自检输出与不传完全一样）。应改用 `wanted_suites(args.tests)` 并回显原始输入。 |
| **F-R5-04** | P3 | 近邻拦截依赖 `lowered.contains("quota")`，标记词自身拼错（`QUTOA`/`QUOT`）落在面外：实测 `unconfigured=unlimited` 下「装配放行 + providers 空 + 无声不设帽」（`refuse` 下则在准入点 503 `PROVIDER_QUOTA_NOT_CONFIGURED`，仍响亮）。修法二选一：env 前缀改成精确匹配 + 显式 edit-distance 判定，或在 javadoc/报告把这条边界按实测写死。 |
| **F-R5-05** | P3 | [T08.md:122](../../../docs/execution/reports/T08.md#L122) 仍写「`--expect-tests`（默认 **57**…）」，与同文件第 13 行「默认 `--expect-tests 65`」及代码 `EXPECTED_TESTS = 65` 自相矛盾。建议让门 11 顺手要求报告出现 65 且不再出现「默认 **57**」。 |
| **F-R5-06** | P3 | [run_pg.py:430-441](../../../tests/engineering/T08/run_pg.py#L430-L441) `--keep-cluster` 分支把 `credentials.txt` 写两遍、`evidence['credentialsFile']` 赋两次（第二次覆盖第一次且格式不同）。纯清洁项，不影响读数。 |
| **F-R5-07** | **P2**（主 agent 仓库级，非本卡代码） | `e4f0f3c` 的自述与实际内容不符：136 个被改文件里 **5 个是换行解释不了的真实改动**，全部是 **T03 会话的在途工作**（`check_session_cookie.py` 入库 58,746→155,999 字节；`record_guard_binding.py` 5,392→8,078；两件前后都不含 CR；另 3 件 T03 证据文件）。而 message 写「restage **the affected blobs** rather than touching a single working file」「an authored test file hashes the same before and after the command」「**zero still divergent**」——三句均被实测推翻（当下这 135 个里 4 个 disk ≠ HEAD）。复现：`git diff --numstat e4f0f3c~1 e4f0f3c -- tests/engineering/T03`，再对每个文件比 parent/新 blob（脚本 `evidence/r5_commit_reality_check.py`，数据 `evidence/r5-e4f0f3c-actual-repair.json`）。 |

不编号的**观察项**（我不据此要求改动，只登记）：① 单测夹具 `window()` 令 `label == lockKey`，所以该用例自身看不见「按 label 排序」（门看得见，已实测）；② [BudgetService.java:308-317](../../../backend/src/main/java/com/example/editorial/cost/BudgetService.java#L308-L317) 的 “classic shape of a cross-transaction wait cycle” 对一个今天并不存在的环略强，同段已自带免责；③「66 条减弱」计的是场景数（69 次编辑、68 种去重后编辑），报告没写这层区分。

## §10 未证明清单

1. **全量 `mvn -B -ntp -o -f backend/pom.xml clean verify`**：本轮我**没跑**（派单禁 `mvn`、`95794bd8` 独占 maven），所以「T08 在整体门禁里不炸」仍只有主 agent 侧的记录支撑。
2. **完整 Spring 组合根**：`editorial.cost.enabled=false`，真实 `application.yml` 经 config-data 加载链与 profile 合并后的最终形状未实测；`refuse` 也没在共享组合根里生效过。（本轮新证据只到「直接调 `BudgetPolicyConfig.from(env)` 的装配层」，即 §4.1 那 20 个反例。）
3. **实际取锁次序没有运行面观测**：门 12 与 `advisoryLockOrderIsTheDictionaryOrderOfLockKeys` 看的是纯函数与文本先后，活库用例没有一条去 `pg_locks` 或按 `pg_advisory_xact_lock` 调用序列取证 ⇒ 「今天真按字典序取锁」是静态推断，不是观测。
4. **F-R5-02 的写入我只证到「自检算出的落点」**：我**没有真的**往受控目录写一个文件（硬规则禁止，且证据目录只增不毁）。要拿实物证据请主 agent 亲跑 §11 的第 4 条命令。
5. **Owner 侧未决**：provider 帽是否跨 Owner 全局生效（F-R4-01 登记为 `openedBy: T08-REVIEW-4TH`）、SRS OQ-09 的示例额度、`unconfigured` 的运维默认值、近邻前缀「响亮拒装配」是否可接受（`T08-Revision-R4.md:223`）。
6. **`unlimited` 与真实部署组合**：§4.1 显示标记词拼错在 `unlimited` 下退化为无声不设帽；我没有、也无法在本轮证明「现实部署里没人会这么配」。
7. **外部投影**：`over_run` 仍无外部投影（AC-28「误差单独报告」只完成一半），属 T10/T11 前置，本卡未证。
8. **真实供应商计费、崩溃恢复/灾备**：未演练、未验证（沿用历轮口径）。
9. **他人残留与在途工作的边界**：我只对自己的目录作保（§13）；六个他人 `.work` 根与其脏文件我一字未读未改。另：F-R5-07 里我**无法证明**主 agent 当时用的 `--renormalize` pathspec 具体是什么（也无从复原提交那一刻的磁盘字节），我能证的只有「该提交实际改到的 136 个文件里 5 个是内容改动而非换行」这一形状，以及「message 用那句话作为 authored 未受影响的**证明**，与该形状不相容」。

## §11 需主 agent 代跑的精确命令（含期望值）

前置：`$env:PY='C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'`，`cd E:\project\codex\wxAgent`。

1. **复现我这轮的读数（整改前基线，必须先与我对表）**
   - `& $env:PY tests/engineering/T08/verify.py` → 期望退出 **0**、`16/16`
   - `& $env:PY tests/engineering/T08/verify.py --reverse-control` → 期望退出 **0**、66 行 `[REJECT]`、8 行 `[benign ]`、汇总 `blind=none, misplaced=none, brittle=none`
   - `& $env:PY tests/engineering/T02/check_contracts.py` → 期望退出 **0**、`27 hashes verified`
2. **F-R5-01 的两种掏法（当前必须绿 ⇒ 收口后必须红）**
   - `& $env:PY docs/execution/reviews/T08-round5/evidence/r5_gate_probe.py G1-concatenated-flat-keys G2-helper-flat-keys`
     当前实测 `16/16` 两条全绿；**整改后期望两条都至少 1 道门红**（最好红在门 11 与门 16）。
   - 再把这两型送进真库：`& $env:PY docs/execution/reviews/T08-round5/evidence/r5_gutted_live.py "$env:TEMP\t08r5\gut-G1" G1` → 当前退出 **0 / 65 全绿**；**整改后期望非 0**。
   - 同时这两型应成为 `MUTATIONS` 里的内置对照：`--reverse-control` 期望变成 **68 条**（66＋2）且仍全 `[REJECT]`。
3. **良性侧不得被我的建议修法误杀**
   - `& $env:PY docs/execution/reviews/T08-round5/evidence/r5_gate_probe.py A8-benign-local` → 期望**继续 16/16 绿**（局部变量接住 `from(env)` 再喂 `service(...)` 是合法重写）。
4. **F-R5-02/F-R5-03（落点与自检）**
   - `& $env:PY tests/engineering/T08/run_pg.py --path-selftest --work-root tests/engineering/T08/evidence`
     当前实测 `problems=[]`、退出 **0**；**整改后期望 `problems` 非空且退出 1**（或至少 `insideControlledDirectory=true`）。
   - `& $env:PY tests/engineering/T08/run_pg.py --path-selftest --work-root tests/engineering/T08/evidence/r5-sub` 同上。
   - `& $env:PY tests/engineering/T08/run_pg.py --path-selftest --tests 'CostPricingTest#someMethod,NotARealSuite'`
     整改后期望 `methodFilterStripped` **回显的是我传进去的值**并因此报 problem，而不是现在这行写死的常量。
   - 摘除判据的反向对照：新增一条把 `and not chosen` 改掉的 `MUTATIONS`，期望 `[REJECT]`（我的 R1 现在测到的是 16/16 绿）。
5. **F-R5-04（标记词拼错）**：把 §4.1 的 `QUTOA_/QUOT_` 两型加进 `CostPricingTest` 的近邻拒绝断言（或把 env 前缀改精确匹配），然后 `run_pg.py --expect-tests 65`（或 66/67，随新增数）→ 期望退出 **0**，且门 11 的 `silent quota paths refused by shape` 由 5 元素变 6/7 元素后仍 True。
6. **F-R5-05/06（文档与清洁）**：`T08.md` 第 6 节那行改成 65（并保留 49→57→65 历史）；`run_pg.py` 删掉 `credentials.txt` 的第二次写入。
7. **全量门禁（我禁跑，你来）**：`mvn -B -ntp -o -f backend/pom.xml clean verify` → 期望退出 **0**，且 `CostPricingTest 28`、`T08PostgresTest 37` 都在通过数里（历轮口径 289/264 一类总数请以你实际读数登记，不要沿用我给的推测值）。
8. **整改后整轮自证**：`& $env:PY tests/engineering/T08/run_pg.py --work-root <绝对隔离根> --evidence-dir tests/engineering/T08/evidence --evidence-name r5fix-<n> --expect-tests <新总数>` → 期望退出 **0**、`expectations.problems=[]`、`evidenceLanding.insideControlledDirectory=true`（这次是显式点名的真身，`explicitlyChosen=true`），并把失败尝试的原件一并入库、**不得覆盖**。
9. **F-R5-07（`e4f0f3c` 的自述与实际不符，就地更正，不动历史）**
   - 先自证我数的形状：`git diff --numstat e4f0f3c~1 e4f0f3c -- tests/engineering/T03` → 期望看到 `2702 846 tests/engineering/T03/check_session_cookie.py`、`106 63 tests/engineering/T03/record_guard_binding.py` 与 3 件 T03 证据文件；再 `git cat-file blob e4f0f3c~1:tests/engineering/T03/check_session_cookie.py` 与新 blob 对比（两者都**不含 CR** ⇒ 与换行还原无关）。
   - 在 `docs/execution/STATE.json` 的本轮条目与 `docs/execution/reports/` 的下一段修订记录里**点名**：`e4f0f3c` 除 130 个纯 CR 还原外，还把 T03 会话 5 个在途文件（含 2 个 authored `.py`）记入了主线提交，归属由 T03 会话后续自行确认；不要沿用「restage the affected blobs / authored 文件前后一致 / zero still divergent」这三句原话。
   - 与 T03 会话对齐那 5 个文件的归属（它们今天仍是 `M`），必要时由 T03 会话重新提交自己的版本。
   - 以后任何 `--renormalize` 必须**限定到证据路径**并且提交前列一遍：`git add --renormalize -- 'tests/engineering/**/evidence/**' 'tests/engineering/**/*-test-results/**' 'tests/engineering/output/**'` 然后 `git diff --cached --name-only` 与 `git diff --cached --numstat | Select-String -NotMatch 'evidence|test-results'`，期望后者**为空**。

## §12 交回命令

我这轮**不需要**主 agent 替我执行任何写入或清理；需要交接的只有三件：

1. 判决与本表（§9/§10/§11）随 `docs/execution/reviews/T08-round5/review.md` 落盘，证据全部在我目录的 `evidence/` 下（含 `r5-main-65.json`、两份掏空副本 `r5-gut-g1.json`/`r5-gut-g2.json` 及其 `-test-results/`、`r5-behaviour-probe.txt`、`R5Probe.java`、各探针脚本与 `r5-r4fix-diff.json`、`r5-fidelity-census.json`、`r5-duplicate-triples.json`）。
2. 若主 agent 采纳 §11 第 2 条，请把「G1/G2 现在是内置对照」的实测输出（66 → 68 条 `[REJECT]`）与整改后的整轮 JSON 一起入库。
3. `docs/execution/STATE.json` 由主 agent 自己写；我不碰。请在本轮台账里如实记：本轮 F-R4-06 **未闭合**、F-R5-01 为 P2；F-R5-07 为**主 agent 自身**的提交归属问题（不是 T08 卡的代码缺陷），需要与 T03 会话对齐那 5 个在途文件的归属后再落账。
4. 我这轮对被审对象**零写入**：被审的 3 个 Java 源文件、2 个测试文件、`verify.py`、`run_pg.py`、两份报告、`.gitattributes` 全部与 `47caf6c`/`e4f0f3c` 入库字节一致（`git status` 里我的痕迹只有 `?? docs/execution/reviews/T08-round5/`）。所有掏空/削弱只存在于内存或已删除的 `$env:TEMP\t08r5\` 副本中；受控证据目录 `tests/engineering/T08/evidence` 全程 105 = 105 未增未改。

## §13 清理自证

| 项 | 结果 |
| --- | --- |
| `Get-Process postgres`（清理前） | **0**（我的集群每次 `pg_ctl stop`，证据里 `clusterStopped=true`） |
| `$env:TEMP\t08r5\`（含 `workroot`、`gut-G1`、`gut-G2`、`probe-classes`） | 已 `Remove-Item -Recurse -Force` ⇒ `Test-Path` = **False** |
| 我可能留在仓库侧的目录 | `.work-r5-tmp` False、仓库根 `target` False、`tests/engineering/T08/evidence/r5-sub` False、`tests/engineering/T08/evidence/evidence` False |
| `tests/engineering/T08/.work/` 内容 | 仍是**六个他人哈希根**（`336f4ccd/6621bb23/8abbdcfd/9da386b1/c1277cf0/d2bdf470`），我没有 `r5-*` 残留、也没读没删它们 |
| 受控证据目录 | `git ls-files tests/engineering/T08/evidence` = **105**，磁盘 = **105**（我全部运行前后各数一次，未增未改未删；本轮所有证据只落我自己的目录） |
| 我的写入范围 | `git status --porcelain` 里属于我的只有 `?? docs/execution/reviews/T08-round5/`；其余 `M/??` 全是 T02/T03 会话的在制品，我未碰 |
| 未执行的动作 | 未 `git add`、未 `git commit`、未写 `docs/execution/STATE.json`、未跑 `mvn`、未写 `backend/target`（探针只读我自己隔离副本里的 `target/classes`） |
| 文本规范 | 我 authored 的 `review.md`、9 个 `.py`、`R5Probe.java`、各 `.json` 均 **无 BOM、LF**；`r5-behaviour-probe.txt`、`r5-probe-javac.log` 与各 `-test-results/` 副本保留程序原字节（`dumpstream`/`.txt` 里的 CRLF 是原始产物，按 §7 的口径**不该**被我改成 LF） |

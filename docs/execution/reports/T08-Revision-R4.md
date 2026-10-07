# T08（成本计量与配额准入）第四轮整改报告

- 被审字节：提交 `37542cb`（含评审方 `docs/execution/reviews/T08-round4/review.md` 与其 `evidence/r4-gutted-*.json`），整改基线为 `fb62212` + `c21e681` 的代码与门
- 整改方：本 agent（实施方，第四轮整改）
- 判决对应：CHANGES_REQUIRED — P2 两条（F-R4-01 / F-R4-06）+ P3 十三条（F-R4-02…F-R4-14，11a/11b 分列）
- 状态：**整改完成，提交主 agent 第四轮复审**（不自评采纳；本报告不构成 T08/AC-28/G1/G2 的通过声明）
- 本轮额外自曝两条：写新用例时**被真实运行否掉的一条断言**（F-R4-03 半边）与它牵出的产品侧归一化缺口，见「附录 A」

## 0. 本轮边界与命令口径

- 只写：`backend/src/{main,test}/java/com/example/editorial/cost/**`、`tests/engineering/T08/**`、`docs/execution/reports/T08*.md`。
- 禁跑 `mvn` 与任何写 `backend/target` 的命令（另一路 T03 整改会话独占）；一切实跑走 `run_pg.py`（隔离副本，`target` 落在副本里）+ `verify.py` + `T02/check_contracts.py`。
- 未碰：`.github/workflows/**`、`tests/engineering/T0{2,3,7}/**`、`backend/src/**/identity/**`、`docs/execution/reviews/**`、`STATE.json`、冻结契约、既有证据（只新增文件，不覆盖）。
- 未执行 `git add`/`git commit`。会话末 `git status --porcelain` 里 T08 侧改动只有：`cost/BudgetPolicy.java`、`cost/BudgetPolicyConfig.java`、`cost/BudgetService.java`、`cost/CostPricingTest.java`、`cost/T08PostgresTest.java`、`tests/engineering/T08/run_pg.py`、`tests/engineering/T08/verify.py`、`docs/execution/reports/T08.md`，新增 `docs/execution/reports/T08-Revision-R4.md` 与 6 个证据文件（`r4-baseline-57.json`、`r4fix-65.json`、`r4fix-65-retry.json`、`r4-gates.json`、`r4-landing-check.json` 及前两者的同名 `-test-results/`）。同表里 `identity/T03SessionCookieGuardTest.java`、`tests/engineering/T03/**`、`docs/execution/reviews/T02-round5/` 是并行会话所有，本轮未读写。
- 自有临时物清理（会话末实测 `Test-Path` 全为 False）：`C:\Users\eie04\AppData\Local\Temp\t08r4fix\`（一次性 `--work-root`：集群数据 + backend 副本 + scratch 证据 + 调试脚本）、`C:\Users\eie04\AppData\Local\Temp\t08r4verify\`（F-R4-12 落点复测那次的 `--work-root`，落点 JSON 已先复制进受控目录存档）、`tests/engineering/T08/.work/r4fix-baseline\`（基线运行的一次性副本）、`.tools/t08compilecheck\`（早先的 javac 试编译根）。**没有删除**不属于自己的东西：`tests/engineering/T08/.work/` 里 6 个 10-07 的 uuid 运行目录与 4 个 `probe*.py`、仓库根 `.work/t02|t03|t08|compile-check|akia*.py` 都留在原处（均在 gitignore 内），若要清请主 agent 决定。收尾时 `Get-Process postgres` 计数为 0（没有留下集群）。
- 每条 F-R4-xx 的口径：**要么响亮拒绝、要么把真实行为钉成用例，且各配一条反向控制**；跑不了的（需要 Owner 决定、需要主 agent 环境跑的）写进「仍未证明」，不冒充跑过。

## 1. 基线（整改前实测，2026-10-08）

| 命令 | 退出码 | 关键读数 |
| --- | --- | --- |
| `python tests/engineering/T08/verify.py` | 0 | 14/14 全绿 |
| `python tests/engineering/T08/verify.py --reverse-control` | 0 | `reverse control: 44 weakenings, 5 benign probes, blind=none, misplaced=none, brittle=none` |
| `python tests/engineering/T08/run_pg.py --work-root <临时绝对根> --evidence-name r4-baseline-57` | 0 | `Tests run: 57`（22 单元 + 35 真实 PostgreSQL），14 条命令全 0 —— 原件 [r4-baseline-57.json](../../../tests/engineering/T08/evidence/r4-baseline-57.json) |
| `python tests/engineering/T02/check_contracts.py` | 0 | `Approved T00 rc.3: 27 hashes verified, no regeneration` |

这组读数与审阅者 §12 的台账一致：**门全绿不等于门在看东西**。本轮所有整改的验收方式都是「先让那条减弱变红，再让等价重写保持绿」。

## 2. 逐条整改（F-R4-01 … F-R4-14）

### F-R4-01（P2）provider 帽按 Owner 分区：文档失真 + 证据空白

- 主 agent 裁定：语义归属（全局帽 vs 每 Owner 帽）转 Owner，本轮**不改语义**，只做「如实写 + 钉住现状」。
- 改了什么：`T08.md` 第 2 节配额行为格与第 2.4 节把宽窗的计量范围写成 `(owner, provider, day)` 并点名 SRS `:1093` 与本卡第 137 行的原话差异（`openedBy: T08-REVIEW-4TH`）；`BudgetPolicy` 类注释补「按 Owner 求和，不是跨所有 Owner」；`BudgetService` 类注释与 `ceilings()` 内注释写明同一事实并指向新用例；新增活库用例 `T08PostgresTest#providerWideQuotaWindowIsPartitionedByOwnerToday`（配额 `(2,30)`，两个 Owner 各压 2 笔在飞 → 第 3 笔两侧都拒；`assertEquals(4, holds())` 钉住「合计 4 笔在飞」；断言窗口带 `owner_id`）。
- 实测退出码：`run_pg.py ... --evidence-name r4fix-65-retry` → **0**（该用例在内，37/37）。第一次尝试 `r4fix-65` → **1**，但失败点不在这条用例（见附录 A）。
- 反向控制：`the report claims the provider window is global across Owners (F-R4-01)` → `[REJECT]`（门 11）。删掉 `BudgetService` 注释里的分区说法、或删掉用例里的双 Owner 结构，都会红：前者由 `honesty[0]` 的代码侧条件守住，后者由门 16 的锚点 `OTHER_OWNER / PROVIDER_QUOTA_EXCEEDED / assertEquals(4, holds()` 守住。
- 良性半边：`the report adds a clause beside the owner-partition marker` → 保持绿（在标记旁追加等价说明不算改口）。
- 未证明：**provider 帽应不应该跨 Owner 全局生效**——这是 Owner/产品决定，本轮只登记不裁决；全局帽形状没有任何用例；真实多凭证（同一 provider 多个 key）场景不存在于当前夹具，`calls-per-day` 的跨 Owner 合计同样没有被度量过。

### F-R4-02（P3）env 前缀多一个字母 ⇒ 静默 `(EMPTY)`

- 改了什么：`environmentQuotaName` 增加「同命名空间 + 含 `quota` 字样 + 不在精确前缀上」⇒ 503 `INVALID_PROVIDER_QUOTA_KEY` 拒装配（`ENVIRONMENT_NAMESPACE`/`ENVIRONMENT_QUOTA_MARKER` 两个常量 + 注释写明这是响亮拒绝的代价：一个拼错前缀的名字现在会让启动失败而不是什么都不做）；新增单元用例 `environmentQuotaPrefixTypoRefusesTheBoot`（同时断言同命名空间里不含 `quota` 的 `EDITORIAL_COST_PROVIDER_CLUSTER_SHARDS` 不受影响，不制造「所有 env 名都拒」的假象）。
- 实测退出码：`r4fix-65-retry` → **0**；`verify.py` → **0**（16/16）。
- 反向控制：`a near-miss env quota name is skipped in silence again (F-R4-02)` → `[REJECT]`（门 11 的形状锚点 `silent_paths[0]`）；另有报告侧一条 `the report drops the two refused silent paths (F-R4-02 / F-R4-04)` → `[REJECT]`。
- 良性半边：不含 `quota` 的同命名空间名字仍可读（同一用例的另一半）；`indexOf`/换行重写类探针全绿。
- 未证明：真实 OS 环境变量注入（当前夹具是 `SystemEnvironmentPropertySource` + 内存 map，不是进程 env）；Boot 完整 config-data 链下该名字是否还会以另一种形态出现。

### F-R4-03（P3）env 段大写被小写入库 ⇒ `providerWideQuota("MOCK")=false` 静默失配

- 主 agent 裁定：判为「边界，写清 + 钉住」，不改行为（拒掉所有大写段等于拒掉环境命名约定本身）。
- 改了什么：类注释与 `environmentQuotaName` 注释写明该通道只寻址全小写 id，并写清两种开关下的后果差异（`refuse` ⇒ 调用处 503；`unlimited` ⇒ 帽静默不落）；新增用例 `environmentChannelAddressesProvidersInLowerCaseOnly` 钉三件事：`EDITORIAL_COST_PROVIDER_QUOTA_MOCK_…` 绑成键 `mock`、`providerWideQuota("MOCK")` 为空、`providers().keySet()=={mock}`。
- 实测退出码：第一次 **1**（我在这条用例里断言「文件通道保留大写」，被 `InvalidConfigurationPropertyNameException` 否掉，见附录 A）；订正后同一命令 **0**。
- 反向控制：`the report says the env channel ignores case (F-R4-03)` → `[REJECT]`；`an unspellable canonical name escapes as a raw Spring stack again (F-R4-03)` → `[REJECT]`（门 11 `silent_paths[4]`）。
- 良性半边：`unconfigured=refuse` 那一半仍走原有拒绝路径，不影响不含 `quota` 的名字；等价重写探针全绿。
- 未证明：带大写的真实 provider id 是否存在于生产配置（本轮只能证明「两条通道都给它不上帽，且 canonical 通道会响亮拒」）；`unlimited` 下该失配的运维后果没有演练。

### F-R4-04（P3）配置面绑 `Integer`，记录字段是 `long`

- 改了什么：新增 `dayCountLeaf(binder, name)` 绑 `Long.class`，`readQuotaLeaf` 的 `calls-per-day` 分支改走它（env 通道与规范通道共用同一读取点，故两侧同宽）；`max-concurrent` 保持 `int` 并在注释写明方向相反的不对称（超过 `2147483647` 是拒绝，不是截断；写数值字面量而非 `Integer.MAX_VALUE` 字样，因为门 9 禁止发明上界）；新增用例 `dayCountLeafCarriesTheLongTheRecordStores`（`99999999999` 绑成功并落进记录；`2147483648` 走 `max-concurrent` 时 503 `INVALID_BUDGET_POLICY`）。
- 实测退出码：`r4fix-65-retry` → **0**。
- 反向控制：`the day leaf is read through the int channel again (F-R4-04)` → `[REJECT]`。
- 良性半边：`calls-per-day: 0` 仍是合法的「当日不放行」（裁决 F-08 的语义未被放宽）；负值仍拒。
- 未证明：`long` 上界本身（`9223372036854775807`）没有测；活库层面对超大日计数的行为只到「绑得进记录」，没有跑一次真实 99 亿次调用。

### F-R4-05（P3）点号规范名放进 env 形状源 ⇒ `getProperty()` 读得到、`from(env)` 读不到

- 改了什么：`environmentQuotaName` 开头加路由——名字已以 `editorial.cost.provider-quota.` 开头就转规范读取器，不再落进大写形状解析分支；注释写明「同一个源不能一半可见一半不可见」；新增用例 `canonicalQuotaNamesInsideAnEnvironmentShapedSourceAreBound`（同一个 `SystemEnvironmentPropertySource` 里点号名与大写名落进同一个 provider map，值不互相吞）。
- 实测退出码：`r4fix-65-retry` → **0**。
- 反向控制：`a canonical dotted name inside an environment-shaped source is dropped again (F-R4-05)` → `[REJECT]`。
- 良性半边：大写形状仍走原分支（既有 `quotaSuppliedThroughEnvironmentStyleNamesBinds` 用例仍绿）。
- 未证明：真实进程 env + Boot relaxed binding 全链（夹具仍是内存源）。

### F-R4-06（P2 主项）体内绑定证据可降级为注释文本（F-02 判未闭合）

- 主 agent 裁定按复审 §3：先剥 Java 注释再判体内证据 + 要求体内真实构造调用 + 把 A5/E4 收进 `MUTATIONS`；良性重写 A8 必须保持绿。
- 改了什么：`verify.py` 新增词法核心 `java_mask`（状态机：代码 / 行注释 / 块注释 / 文本块 / 字符串 / 字符），`strip_java_comments` 改为掩码驱动且**长度保持**（旧正则版删除）；`java_method_body` 的签名搜索与花括号遍历都在剥注释后的文本上做、并在遍历中跳字面量与注释；`java_slice` 用于判定。门 10（AC 锚点）与门 11（配额）现在都在 `java_slice(java_method_body(...))` 上判定：`load("…", new ByteArrayResource(<变量>.getBytes(...)))` 必须是真实构造，且那个 `<变量>` 就是体内 `String x = """` 声明的嵌套文档；`getPropertySources().add` 与 `BudgetPolicyConfig.from(env)` 也必须在代码里；平铺点号键在两个配额用例体内一律禁止（Java 字面量与 YAML 两种形状都算）。门 11 细节新增切片长度读数（单元 5147 / 活库 3688 字符）。
- 实测退出码：`verify.py` → **0**（16/16）；`--reverse-control` → **0**；整改前同一套门对 A5 掏法是绿的（审阅者读数：门 0 + 用例 0 + 退出码 0）。
- 反向控制：`the live case's binding survives only as a comment quoting it (round-4 control A5)` → `[REJECT]`（门 11 + 门 16 双红）；`the live case binds flat dotted keys through a real loader (round-4 control E4)` → `[REJECT]`；第三轮已有的「loader 挪出体内」「体内退回扁平手搓键」两条仍 `[REJECT]`。
- 良性半边：A8「loader 产物先存进局部变量再喂 service」仍绿；`new ByteArrayResource(\n document.getBytes(...))` 换行仍绿；`braces inside a literal and inside a comment join the live quota case` 仍绿（见 F-R4-07）。
- 未证明：词法核心不是完整 Java 解析器（嵌套注释、`@Recursive.annotation"` 这类畸形文本块结束符仍可能骗过它）；本轮没有把门 10/11 改成编译期校验（那需要跑 `mvn`，属主 agent 独占）。

### F-R4-07（P3）`java_method_body` 不跳字面量/注释

- 改了什么：如上，遍历与签名搜索都在掩码文本上做；文档字符串按实测重写（不再声称「只加宽不裁窄」）。
- 实测退出码：`verify.py` → **0**。切片长度实测（临时脚本，只读不写仓库）：活库用例 `nestedYamlQuotaIsEnforcedByTheService` 加 `String r4Closing = "}";` + 注释里的 `{` ⇒ **3688 → 3833 字符**；单元用例加同一个字面量 ⇒ **5147 → 5179 字符**。修复前审阅者的两个反例是裁到 32 与加宽到 54666。
- 反向控制：字面量/注释形状不作为「减弱」，而作为**良性探针**存在（若哪天切片器又把它们当边界，两条探针会红）。
- 良性半边：本轮 8 条良性重写全绿（原 5 条 + 这 2 条 + 1 条报告加句）。
- 未证明：极端文本块（同一段里 `"""\n"""` 连续出现）与转义 `\"` 的组合没有穷举；掩码是单次线性扫描，未做嵌套块注释的递归验证。

### F-R4-08（P3）`verify.py:253-254` 与 `fb62212` 说明两句均被实测推翻

- 改了什么（原位更正，不新增章节掩盖）：`java_mask`/`java_method_body` 的注释按实测重写并写明「长度保持、跳注释与字面量与文本块」；`T08.md` 第 2.4 节把「提交信息 `fb62212` 里同样的措辞」标为历史证据——历史提交文本不回改（禁 `git commit`/`amend`），只在返工记录里订正。本轮同时自曝一处同类失真：`BudgetPolicyConfig` 注释与我第一版用例都写着「文件通道保留大写」，实测不成立，已就地改写（附录 A）。
- 实测退出码：`verify.py` → **0**；`r4fix-65-retry` → **0**。
- 反向控制：报告与注释里的关键说法被反向对照钉住（本轮新增 6 条报告/注释侧减弱，全部 `[REJECT]`）。
- 良性半边：`the F-03 comment rewords itself` 仍绿——注释允许换措辞，不允许丢可核对的标记。
- 未证明：`fb62212` 的提交说明字节未改（本轮无写历史权限）；如果主 agent 要求把订正写进历史，需要由你决定并执行。

### F-R4-09（P3 → 升格为缺陷）锁序防线无人看守

- 主 agent 裁定：删 `ceilings.sort` 后 14 门全绿 + 57 例全绿 ⇒ 声称的防线无看守；修法为直接断言锁序 + 内置反向控制；**不谎称今天存在死锁**。
- 改了什么：`BudgetService` 新增包内静态 `inLockOrder(List<Ceiling>)`（按 `Comparator.comparing(Ceiling::lockKey)` 排序，返回不可变副本；注释写明「没有观测到死锁，也不声明存在死锁，被固定的只是顺序」）；`reserveInTransaction` 在取第一把锁之前调用它（原来的 `ceilings.sort(...)` 从调用点删除）；`Ceiling` 记录由 `private` 降为包内可见，让单元用例能构真实列表；新增 `CostPricingTest#advisoryLockOrderIsTheDictionaryOrderOfLockKeys`——两种构造顺序喂进 `inLockOrder` 得到**同一条序列**、序列等于按 key 排序的期望值、`T08|PROVIDER-MODEL|…` 排在 `T08|PROVIDER|…` 之前（字典事实钉成数据）、再塞一个 `T08|SEARCH|…` 的新 scope 仍落在字典序里。新增**门 12**：只有一处排序入口、按 lockKey、`inLockOrder` 在 `ledger.lockScope(` 之前、`reserve` 内加锁点唯一、六个 scope 的锁键都自带 `T08|<SCOPE>` 前缀、运行时有断言、报告写明字典序。
- 实测退出码：`verify.py` → **0**；`--reverse-control` → **0**（B1 已不是盲点）；`r4fix-65-retry` → **0**（用例真跑过）。
- 反向控制：5 条锁序减弱 + 1 条报告改口，全部 `[REJECT]`：删掉 sort（审阅者 B1）、按 `label` 排、摘掉 `inLockOrder` 调用点、`lockScope(ceiling.label())`、新窗口锁键丢前缀、报告说「按构造顺序」。
- 良性半边：新增一个前缀合规的窗口不会让门红（`key_prefixed` 对每个窗口分别判，不看数量上限）。
- 未证明：**今天是否真的存在死锁**——本轮没有任何一次死锁观测，两条并发事务的 wait-cycle 未在活库里构造出来；两个并发事务在真实集群上的锁序交错没有被度量（现有活库并发用例是单请求路径的 `FOR UPDATE` 闩门）；单元用例断言的是 `inLockOrder` 的输出序列，不是数据库实际获取锁的时序。

### F-R4-10（P3）env 未知叶子改回静默跳过也不会红

- 改了什么：`environmentQuotaName` 的叶子识别补 `} else { throw … INVALID_PROVIDER_QUOTA_KEY }`（未知叶名不再落到下一个名字的读取）；新增用例 `everyUnknownQuotaLeafRefusesTheBoot`（env 通道 `…_MOCK_AVERAGE_LATENCY`、`…_MOCK_MAXCONCURRENT` 均 503；规范通道同一位置仍拒；只写半条叶值仍是 `QUOTA_NOT_CONFIGURED`）。
- 实测退出码：`r4fix-65-retry` → **0**。
- 反向控制：`an unrecognised quota leaf falls through silently again (round-4 control B3)` → `[REJECT]`（门 11 `silent_paths[2]`）。
- 良性半边：已知两叶仍照常绑定；`unconfigured` 保留字仍走必需开关分支。
- 未证明：叶子白名单之外还有多少可读法被 Boot 的 relaxed binding 悄悄归一（本轮只钉住「认不出就拒」，未枚举全部可能拼法）。

### F-R4-11a（P3 文档）默认 `image-units-per-article=4` 下的真实拒绝顺序只躺在返工表

- 主 agent 裁定：`T08-SRS-DEFAULT-CLASH` 判「测试自己的前提」；产品默认值 `BudgetPolicyConfig.java:101`（现为 `count(env, "editorial.cost.image-units-per-article", 4)` 那一行）不动、不判它错；真实拒绝顺序写进行为章节并补用例。
- 改了什么：`T08.md` 第 2 节与第 6 节写明「文章/日帽先测量，provider 配额后测量；同时越界时对外是 409 `QUOTA_EXCEEDED` 而不是 429」；`checkProviderQuota` 的注释写明顺序并指向新用例；活库配额用例 `nestedYamlQuotaIsEnforcedByTheService` 的注释解释夹具为什么把该帽抬到 100（不抬就是文章帽先说话，测不到配额窗）。
- 实测退出码：`r4fix-65-retry` → **0**。
- 反向控制：`the report says the provider quota speaks before the article ceiling (F-R4-11a)` → `[REJECT]`；`the provider quota window is measured before the article and day ceilings (F-R4-11a)` → `[REJECT]`（门 11 的 `rejection_order`：在剥注释的 `reserveInTransaction` 体内比较两个位置的先后）。
- 良性半边：把 `checkProviderQuota(...)` 调用挪到同一遍之后的其它位置（仍在测量遍之后）不会红——门判的是先后，不是行号。
- 未证明：这条顺序是不是产品**应该**的顺序（本轮只钉住现状）；两帽同时命中时告警投递/审计的先后没有度量。

### F-R4-11b（P3 覆盖）该顺序没有用例钉住

- 改了什么：新增 `T08PostgresTest#theArticleCeilingSpeaksBeforeTheProviderQuotaWindow` 三段：文章帽 4 + 宽配额 `(10,30)` ⇒ 第 5 笔 409 `QUOTA_EXCEEDED`；帽抬宽 + 配额 `(2,30)` ⇒ 第 3 笔 429 `PROVIDER_QUOTA_EXCEEDED`；两帽同时命中（文章帽 2 + 配额 `(2,30)`）⇒ 答案仍是 `QUOTA_EXCEEDED`，且 `holds()==2` 说明没有多插一行。
- 实测退出码：`r4fix-65-retry` → **0**（三段全按预期）。
- 反向控制：同 F-R4-11a 两条；锚点组 `the article ceiling speaks before the quota window`（门 16）要求 `IMAGE_GENERATION_ARTICLE, 4L`、`"QUOTA_EXCEEDED"`、`"PROVIDER_QUOTA_EXCEEDED"`、`assertEquals(409` 四枚都在剥注释后的体内。
- 良性半边：断言换行/`assertEquals` 链式换行等价重写仍绿。
- 未证明：金额帽（文章 5 USD / 日 20 USD）与配额帽同时越界时的先后——本轮只测计数帽。

### F-R4-12（P3 工具）`run_pg.py:389` 证据目录硬编码为脚本自己的 `HERE/evidence`

- 改了什么：新增 `--evidence-dir`（默认 `None`）与 `resolve_evidence_dir()`：不给参数时落在 `<work-root>/evidence`（scratch，与 `.work` 同性质）；要写进受控目录必须显式点名。重名拒绝检查、`-test-results/` 副本、最终 JSON 三处都改走该目录；每次运行在 stdout 打印落点，并在 JSON 里写 `evidenceLanding{directory, absolute, explicitlyChosen, insideControlledDirectory}`；`--path-selftest` 增加落点自检——**未经点名却要写进受控目录 ⇒ `problems` 非空 ⇒ 退出 1**。
- 实测退出码：`--path-selftest` → **0**（`evidenceDir=.../.work/evidence`，`explicitlyChosen=false`）；不给 `--evidence-dir` 的真实运行（`--skip-tests`）→ **0**，证据落在临时根下的 `evidence/`（scratch），受控目录未增文件；换根重跑一次量化了「未增」：`t08r4verify` 那次受控目录文件数 **21 → 21**，JSON 里 `evidenceLanding={directory: "C:/Users/.../t08r4verify/evidence", explicitlyChosen: false, insideControlledDirectory: false}`。那份 scratch JSON 事后由我复制存档为 `tests/engineering/T08/evidence/r4-landing-check.json`（`explicitlyChosen=false` 原样保留，它不是交付运行）。显式点名受控目录的交付运行 → **0** 且 `explicitlyChosen=true`。
- 反向控制：`the runner's evidence default points back into the tracked evidence directory (F-R4-12)` → `[REJECT]`（门 13）。
- 良性半边：既有 `--evidence-name` 语义不变；点名受控目录仍被允许（本轮交付证据就是这么写的）。
- 未证明：受控目录**不可写**时的降级路径（沙箱拒绝写时走 `testResultsCopyBlocked` 的旧分支）本轮没有重新触发实测。

### F-R4-13（P3 工具）套件名比对不容方法过滤器；`--path-selftest` 对仓库外绝对根判 1

- 改了什么：新增 `wanted_suites()`——存在性比对前剥掉 `#method`；`--tests` 的 help 写明支持方法过滤器；`--path-selftest` 把「绝对根在仓库外」从 `problems` 改为 `notes`（是运维选择，不是缺陷），并新增方法过滤器自证：`wanted_suites('CostPricingTest#x,T08PostgresTest') != ['CostPricingTest','T08PostgresTest']` 时判 problem。
- 实测退出码：`--path-selftest --work-root C:\Users\eie04\AppData\Local\Temp\t08r4fix\outroot` → **0**（`notes` 一句、`problems=[]`；整改前同命令 **1**）；`--path-selftest --tests CostPricingTest#environmentChannelAddressesProvidersInLowerCaseOnly` → **0**，输出 `methodFilterStripped=["CostPricingTest","T08PostgresTest"]`。
- 反向控制：`the suite-presence check compares raw --tests values again (F-R4-13)` → `[REJECT]`；`--path-selftest refuses an absolute work root outside the repository again (F-R4-13)` → `[REJECT]`（都落门 13）。
- 良性半边：不带过滤器的默认写法完全不变（本轮 14 条命令的真实运行就是 `--tests CostPricingTest,T08PostgresTest`）。
- 未证明：带方法过滤器的**真实 Surefire 运行**没有跑过（跑了就会与 65 项总数闸门冲突，属预期非零）；本轮只证明剥过滤器后的存在性比对不再误判，以及自证检查通过。

### F-R4-14（P3 文档）「歧义即拒」未限定范围

- 改了什么：只改文档。`T08.md` 第 5 节那句改成「**同一个名字在 env 通道里有两种读法**才 503 拒装配」，并明写「名字一自身有两种读法即拒；**跨源同名键不拒**」——文件里 `…mock.max-concurrent=100` 与 env 里 `…MOCK_MAX_CONCURRENT=2` 并存时装配不拒，按属性源 precedence 取值（实测取 2），这是 Spring 常规行为而不是我在猜语义。行为与代码一字未改。
- 实测退出码：`verify.py` → **0**（门 11 `honesty[3]` 要求这句话在场）；`r4fix-65-retry` → **0**（行为未动）。
- 反向控制：`the report widens the ambiguity refusal to duplicate keys across sources (F-R4-14)` → `[REJECT]`。
- 良性半边：句子旁边追加解释性从句不会红（本轮良性探针里有同类形状）。
- 未证明：precedence 的完整矩阵（profile 文件、`config-data` -location 覆写、命令行属性源的相对次序）没有逐一实测；本轮只测了「文件 100 + env 2 ⇒ 取 2 且不拒」这一对。

## 3. 用例数变更明细（0 删除、0 静默改名）

单元 `CostPricingTest` 22 → **28**，活库 `T08PostgresTest` 35 → **37**，合计 57 → **65**。三处同步：`run_pg.py` 的 `EXPECTED_TESTS = 65`（含注释台账，逐条列出这 8 个新名字）、`--expect-tests` 默认值（取 `EXPECTED_TESTS`）、`T08.md` 第 1 节与第 5 节台账。

| 新用例 | 文件 | 钉住哪条 |
| --- | --- | --- |
| `environmentQuotaPrefixTypoRefusesTheBoot` | 单元 | F-R4-02 |
| `environmentChannelAddressesProvidersInLowerCaseOnly` | 单元 | F-R4-03（含附录 A 的订正） |
| `dayCountLeafCarriesTheLongTheRecordStores` | 单元 | F-R4-04 |
| `canonicalQuotaNamesInsideAnEnvironmentShapedSourceAreBound` | 单元 | F-R4-05 |
| `everyUnknownQuotaLeafRefusesTheBoot` | 单元 | F-R4-10 |
| `advisoryLockOrderIsTheDictionaryOrderOfLockKeys` | 单元 | F-R4-09 |
| `providerWideQuotaWindowIsPartitionedByOwnerToday` | 活库 | F-R4-01（`openedBy: T08-REVIEW-4TH`） |
| `theArticleCeilingSpeaksBeforeTheProviderQuotaWindow` | 活库 | F-R4-11a/b |

删除 0 条、静默改名 0 条；既有 57 条一条未动语义（只有注释按 F-R4-08/11a 更正）。逐名清单以 `r4fix-65-retry.json` 的 `suites[].cases` 为准（65 个名字，门 16 的 39 组锚点覆盖其中 AC 承重项，第三轮为 31 组）。

## 4. 反向控制清单变更（44 → 66，良性探针 5 → 8）

新增 22 条减弱，全部 `[REJECT]`，`blind/misplaced/brittle/stale` 全为 none：

- 掏法收编（F-R4-06）：A5 注释装饰、E4 平铺键走真 loader —— 2 条
- 锁序（F-R4-09）：删 sort、按 label 排、摘掉调用点、`lockScope(label)`、锁键丢前缀、报告改口 —— 6 条
- 四条静默路径（F-R4-02/05/10/04）：各 1 条 —— 4 条
- 大写名拒答归一化（F-R4-03）：1 条
- 拒绝顺序（F-R4-11a）：代码翻面 + 报告翻面 —— 2 条
- runner（F-R4-12/13）：默认落点回指受控目录、原始 `--tests` 比对、仓库外根重新判 problem —— 3 条
- 文档诚实性（F-R4-01/03/04/02/11/14）：Owner 全局帽说法、大小写不分说法、静默路径标记删除、跨源同名键写成"一律拒" —— 4 条

新增 3 条良性重写（全部保持绿）：活库配额用例内 `"}"` 字面量 + 注释里的 `{`；单元配额用例内同一字面量；报告在 Owner 标记旁追加等价从句。既有的 A8「局部变量喂 service」等 5 条仍绿。

## 5. 最终实测台账（2026-10-08，本轮结束时）

| 命令 | 退出码 | 读数 |
| --- | --- | --- |
| `python tests/engineering/T08/verify.py` | 0 | 16/16；门 11 细节含 `silent quota paths refused by shape=[True×5]`、`ceilings measured before the quota pass=True (measure@2792, quota@3630)`、`behavior stated where a reader meets it=[True×5]`、切片长度 5147/3688 |
| `python tests/engineering/T08/verify.py --reverse-control` | 0 | `reverse control: 66 weakenings, 8 benign probes, blind=none, misplaced=none, brittle=none` |
| `python tests/engineering/T08/run_pg.py --work-root <仓库外绝对根> --evidence-dir tests/engineering/T08/evidence --evidence-name r4fix-65-retry` | 0 | `Tests run: 65, Failures: 0, Errors: 0, Skipped: 0`（28/28 + 37/37），14 条命令全 0 |
| `python tests/engineering/T08/run_pg.py --work-root C:\Users\eie04\AppData\Local\Temp\t08r4verify --evidence-name r4fix-landing-check --skip-tests`（不给 `--evidence-dir`） | 0 | 证据落 `C:/Users/.../t08r4verify/evidence/`（scratch），`evidenceLanding.explicitlyChosen=false`、`insideControlledDirectory=false`，受控目录文件数 **21→21** 未增；复制存档为 `r4-landing-check.json` |
| `python tests/engineering/T08/run_pg.py --path-selftest`（三种输入） | 各 0 | 见 F-R4-13 |
| `python tests/engineering/T02/check_contracts.py` | 0 | `Approved T00 rc.3: 27 hashes verified, no regeneration` |

同一命令的第一次 65 项尝试退出码 **1**（我自己的断言错），原件 `r4fix-65.json` 保留；本轮**没有**删除任何失败证据。

## 6. 并发干扰登记（非 T08 回归）

- 与 T03 整改会话共用脏工作区。`git status` 全程显示 `backend/src/test/java/com/example/editorial/identity/T03SessionCookieGuardTest.java` 与 `tests/engineering/T03/**` 被并行会话修改；本轮两次整轮运行的 `testCompile` 都成功（`Compiling 101 source files` / `Compiling 36 source files`），**没有出现**审阅者担心的「外来 identity 文件导致副本编译失败」。若后续出现，登记方式：记录时刻 + 命令 + 退出码，排除该文件后重跑，仍单列为外来干扰。
- 本轮未执行 `mvn`、未向 `backend/target` 写入（真实运行走 `run_pg.py` 的隔离副本，`target` 在副本内）。
- 端口/集群：每次运行自建一次性集群，结束时 `terminate`；登记时 `Get-Process postgres` 计数为 0。

## 7. 仍未证明清单

1. provider 帽该不该跨 Owner 全局生效（F-R4-01 的语义决定，Owner 持有）。
2. 今天是否存在可复现的死锁：本轮只把锁序固定并看守，**未观测到**也**不声明**存在死锁；真实并发事务的锁获取时序未在活库层度量。
3. 完整组合根：`editorial.cost.enabled=true` 时 Boot 的 config-data 链、profile 合并、多属性源 precedence 的完整矩阵（本轮只测文件/env 一对）。
4. 真实进程环境变量注入（夹具是 `SystemEnvironmentPropertySource` + 内存 map）。
5. 真实供应商计费、崩溃恢复/灾备、`GET /api/v1/usage` 的 HTTP 端到端。
6. `mvn clean verify` 全量门禁（主 agent 独占，本轮未跑）。
7. 带方法过滤器的真实 Surefire 运行（总数闸门会故意判非零，未跑）。
8. 受控证据目录不可写时的降级分支本轮未重新触发。
9. 金额帽与配额帽同时越界的先后（只测了计数帽）。
10. `verify.py` 词法核心不是完整 Java 解析器：畸形文本块结束符、嵌套块注释这类形状仍可能骗过掩码。

## 8. 需要主 agent 执行/裁决

1. `mvn -o clean verify` 全量门禁（T08 会话禁跑 `mvn`，`backend/target` 由你独占）。
2. **裁决 provider 帽语义**：维持 `(owner, provider, day)` 分区（当前实现与用例）还是改成跨 Owner 全局帽。改语义需要新用例 + 更新 SRS/本卡，我不会替你改。
3. 决定 `EDITORIAL_COST_*` 里含 `quota` 字样的近邻名字「响亮拒装配」是否为可接受的运维代价（F-R4-02 的取舍：一个拼错前缀的环境变量名现在会让启动失败）。
4. 决定带大写的 provider id 是否需要新配置形状（当前两条通道都给不上帽：env 静默小写、canonical 503 拒）。
5. 若你判定「锁序应有真实并发证据」，请在你的环境跑一次两事务并发压测；本轮只交付了静态看守 + 单元序列断言。
6. 请复核本轮 8 条新用例与 22 条新反向对照是否满足你 §3 的最小修法清单；`tests/engineering/T08/evidence/r4-gates.json` 存了逐条 `[REJECT]`/`[benign]` 原文。
7. `git add`/`commit` 与 `STATE.json` 由你执行；本报告不自评采纳。

## 附录 A：本轮被真实运行否掉的一条断言（自曝，非审阅者条目）

第一版 `environmentChannelAddressesProvidersInLowerCaseOnly` 写着「env 通道只认小写，但文件通道保留大写：`editorial.cost.provider-quota.MOCK.max-concurrent` 绑成 `MOCK`」。`run_pg.py ... --evidence-name r4fix-65` 退出码 **1** 否掉了它：

```
org.springframework.boot.context.properties.source.InvalidConfigurationPropertyNameException:
Configuration property name 'editorial.cost.provider-quota.MOCK.max-concurrent' is not valid
  at ...Binder.bind(...)  at BudgetPolicyConfig.quotaLeaf(BudgetPolicyConfig.java:289)
```

准确说法是：**大写段在两条通道都不可寻址**——env 通道静默折成小写（帽落空），canonical 通道被 Spring 的名字文法拒（装配期失败）。第二件事是产品侧缺口：这个拒答当时以**裸栈**形式逃出装配，绕过了第三轮裁决 F-08 建立的「读不进去的额度是结构化 503，不是 stack trace」。两处一起改：`quotaLeaf`/`dayCountLeaf` 一并捕获 `InvalidConfigurationPropertyNameException` ⇒ 503 `INVALID_BUDGET_POLICY`；注释与本卡第 2.4 节按实测改写；用例改成断言那个 503（并断言它**不是**被静默折成 `mock`）。门 11 加了形状锚点，反向对照加了「这条归一化被摘掉 ⇒ 红」。两次运行的原件都在 `tests/engineering/T08/evidence/`（`r4fix-65.json` 失败、`r4fix-65-retry.json` 成功）。

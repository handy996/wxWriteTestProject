# T08 — 第三轮整改报告（T08-Revision-R3）

输入：`docs/execution/reviews/T08-round3/review.md`（verdict **CHANGES_REQUIRED**）与其 `evidence/checks.json`；已下裁决 F-03/F-04/F-05/F-08 与发现 F-01/F-02/F-06/F-07。本轮**不引入新设计**：只按裁决整改 T08 自有文件，不自行批准，不写 `docs/execution/STATE.json`，不执行 `git add`/`commit`。主报告 `docs/execution/reports/T08.md` 已同步外科手术更新（两级语义、env 通道实况、49→57、44+5 门账目；旧文里"本实现不使用 Binder 那条宽松绑定路径"的陈述按实况改写——现在叶值确实经 `Binder` 按规范名读取，这是本轮 F-01 修复的一部分）。

本轮全部实测退出码汇总：

| 命令 | 退出码 | 说明 |
|---|---|---|
| `python tests/engineering/T08/run_pg.py --work-root E:/project/codex/wxAgent/.work/t08/r10b --expect-tests 57 --evidence-name r10-pg` | **0** | 57/57（单元 22 + 活库 35），14 条子命令逐条 0，`expectations.problems=[]` |
| 同命令第一次迭代（`--work-root .../r10 --evidence-name r10-pg-selftest`） | **1** | 自家新用例数值缺陷（见 F-02/§3 说明），证据保留不删 |
| `python tests/engineering/T08/run_pg.py --work-root .work/t08/r10-relative --expect-tests 57 --evidence-name r10-pg-relative-work-root` | **0** | **相对** `--work-root` 整轮实测（F-07 的行为半）：与绝对写法同结果，证据完整写出 |
| `python tests/engineering/T08/run_pg.py --path-selftest` 与 `--path-selftest --work-root .work/t08/r10-selftest-probe` | **0 / 0** | 默认/相对两种输入的解析自检（不启动集群），输出在 `r10-gates.json` |
| `python tests/engineering/T08/verify.py` | **0** | 14/14（检查项数不变，第 11/14 项内容重写） |
| `python tests/engineering/T08/verify.py --reverse-control` | **0** | `44 条减弱全部 REJECT，blind=none, misplaced=none；5 条良性重写全部保持绿，brittle=none` |
| `python tests/engineering/T02/check_contracts.py` | **0** | `Approved T00 rc.3: 27 hashes verified, no regeneration` |
| `python .work/t08/r10-controls/control_runner.py C1 C2 C3` | **0**（包装）；每次控制运行各 **1**（预期红） | 三个运行时控制各自把已修复代码在 `.work` 副本里改回旧行为，红必须**恰好**落在指定用例上，见第 5 节 |
| （主 agent 集成时代跑）`mvn -B -ntp -o clean verify` | **0** | 289 项 / 0 失败 / 147 跳过，记录在提交 `fb62212` 的信息里；非本卡亲跑，§7-1 按实况保留这一层区别 |

## 1. 改动文件清单

主代码（`backend/src/main/java/com/example/editorial/cost/`）：

- `BudgetPolicy.java` — 裁决 F-03/F-04/F-05/F-08 的落点：`scope()` 成为唯一拼法并做 id 字符集拒（F-05）；单条 `providerQuota()/quotaScope()` 拆成 `modelQuota(provider, model)`（精确 `containsKey`，无回退）与 `providerWideQuota(provider)`（F-03/F-04）；`ProviderQuota` 紧凑构造器守卫 `maxConcurrent < 1 || callsPerDay < 0`（F-08）。
- `BudgetPolicyConfig.java` — F-01/F-08/F-04/F-05：`quotas()` 逐 `EnumerablePropertySource` 枚举，`SystemEnvironmentPropertySource` 走独立 env 形状分支、其余走规范点号分支，两分支都只做形状解析、叶值一律经 `Binder.get(configurable).bind(规范名, Integer.class)`；env 歧义（`_` 双读法、多段中间名）当场 503；`quotaLeaf()` 捕获 `BindException | ConversionFailedException` 归一化为 503 配额配置错误（F-08，原来是 Spring 原始转换异常逃逸出装配）；负值拒、`max-concurrent: 0` 拒、`calls-per-day: 0` 放行（F-08）；带点 model id 的 model 级键维持响亮拒绝（F-04 现状裁决，代码注释标明 `entries[]` 属 Owner）。
- `BudgetService.java` — F-03/F-06：`ceilings()` 按两个 Optional **各自建窗**（`if (modelEntry.isPresent())` / `if (wideEntry.isPresent())`），锁标签改走 `String.join`，本文件不再出现 `provider + "|" + model` 拼接（F-06 的模块唯一性由此可扫）；`checkProviderQuota` 把 `quota()!=null` 的**全部**窗口逐个测量——`max-concurrent` 对 model 窗数该 model 的活预占、对 provider 窗数该 provider 跨 model 之和，`calls-per-day` 各按各自窗口的当日计数，任何一窗越界即 429 `PROVIDER_QUOTA_EXCEEDED`。

测试（`backend/src/test/java/com/example/editorial/cost/`）：`CostPricingTest.java`（18→22）、`T08PostgresTest.java`（31→35），逐用例见第 3 节。

自检与 runner（`tests/engineering/T08/`）：`verify.py` — 第 11 项重写（全 `cost/**` 剥注释扫描、两级形状/env/归一化/零语义锚点、F-02 的**方法体内**绑定判定）、第 14 项锚点 22→31 组、`reversals()` 30→44（新增 14 + 重靶 2）、新增 `benign_probes()` 5 条与 `brittle` 判定、模块扫描改用 `strip_java_comments`；`run_pg.py` — F-07（`resolve_work_root` 启动即绝对化、`inside_repo` 替代裸 `relative_to`、`--path-selftest`），`EXPECTED_TESTS` 49→57 并在注释里按发现名列出每条新用例。

报告：`docs/execution/reports/T08.md`（更新）、本文件（新增）。证据：见第 6 节。

## 2. 逐条整改

### F-01（P2）env 变量通道静默丢配额

缺陷：`SystemEnvironmentPropertySource` 回答规范点号名，但旧枚举只认原始键名字面以 `editorial.cost.provider-quota.` 开头的条目——env 注入的配额**一条都枚举不到**，配上 `unconfigured=unlimited` 时整个供应商侧静默无限，装配照样成功。

修法：属性源类型判定 `environmentShaped = source instanceof SystemEnvironmentPropertySource`；env 形状键（`EDITORIAL_COST_PROVIDER_QUOTA_<provider>_<leaf>`）自研枚举、歧义即拒（`_` 同时代表 `.` 与 `-`，`A_B_C` 有两种读法 → 503 `INVALID_PROVIDER_QUOTA_KEY`，**猜等于错**）；虚线叶名（`MAX_CONCURRENT`/`CALLS_PER_DAY`）与规范虚线名经 `Binder` 绑定探针实测等价——**探针结论**：`Binder.mapOf` 在虚线前缀下看不见 env 形状键，所以采用"自研枚举 + 逐规范名 `Binder.bind`"。model 级 env 键因此整体不可表达，与 F-04 的"配置形状不变"一致，注释标出。

实测：新用例 `quotaSuppliedThroughEnvironmentStyleNamesBinds` 在整轮运行绿（退出码 0）；控制 C1（副本里把枚举摘回只认字面点号名）**退出码 1** 且恰好这一条变红——这是派发要求的"reverting enumeration → 用例 RED"的运行时半，静态半由反向对照第 30 条（"literal dotted names only"→REJECT）承担。

### F-02（P2）绑定证据可被悄悄摘除

缺陷：第 11 项旧判定是整文件级子串——审阅者 V6 演示把 loader 挪进辅助方法、或在断言用例里追加第二条手搓 `service(policy(...))` 覆盖绑定结果，门照样绿。

修法：`java_method_body()` 切出两条 YAML 用例的**方法体**，loader/`document.getBytes`/`ByteArrayResource`/`from(env)` 必须出现在体内；活用例体内 `service(` 计数恰好 1 且参数必须是 `from(env)` 的结果（内联，或经一个直接由 `BudgetPolicyConfig.from(env)` 赋值的局部变量）；体内禁 `new BudgetPolicy(`/`policy(wideCaps`/扁平 `editorial.cost.provider-quota.` 键。测试侧同步改造：单元用例不再从辅助方法拿环境；活用例文档数值改为 4/26 + 1/9 并断言 `activePolicy` 两级的这四数——文件内**任何**手搓策略都不含它们。

三探针（反向对照 #39/#40/#41）：loader 挪出单元用例体 → REJECT；单元体内退回手搓扁平键 → REJECT；活用例长出第二条手搓 `service(...)` → REJECT。

良性重写探针（新机制，与减弱相反方向）必须**保持绿**，本轮 5 条（第 4 节全列），其中两条直接护航本项：活用例经局部变量中转 `service(...)`、`activePolicy` 断言链换行——等价重构不惩罚，这是判定"证据在体内"而非"拼写硬编码"的分界。

### F-06（P2）"全模块唯一 join"只扫两个文件

修法：joined 正则的扫描集从两个文件改为 `cost/**` 全部 19 个源文件，并**先剥注释**（按代码判定，不按散文——首轮全模块扫描正是被 `BudgetService` 注释里的字面 `provider + "|" + model` 绊出第二命中，这个事故本身证明扫描已覆盖到服务文件；`BudgetService` 本轮也因此改走 `String.join`）。

承重证明：反向对照 #37"把第二个 join 藏进 `BudgetService`"→ REJECT；旧的 2 文件扫描对同一条减弱**结构性失明**（该文件当时不在扫描集内）——这条即 F-06 的本体。诚实边界（列入第 7 节）：文本扫描跟的是 `provider`/`model` **变量名**，异名变量的拼接不在其视野；补位是 `config_keys_by_scope` 逐位点锚、两条窗口 SQL 锚与运行时用例。

### F-07（P3）相对 `--work-root` 吞掉成功轮

修法：`resolve_work_root(raw, HERE)` 启动即 `.resolve()`（无论相对/绝对，集群目录、副本目录都在解析后的根下）；证据展示统一走 `inside_repo()`（在仓库内记仓库相对形态、在外记绝对，finally 不再可能因 `relative_to` 抛 ValueError）；新增 `--path-selftest`：用**真实运行同一**解析函数打印 `workRoot/runDirectoryShape/relativeInput/problems`，不启动任何东西。

实测：两种输入的自检各退出码 0（输出已入 `r10-gates.json`）；整轮相对写法运行**退出码 0**、57/57、`isolatedWork` 记为 `.work/t08/r10-relative/<run>`——旧行为"14 条命令全绿 → finally 炸 → 退出码 1 无证据"在行为层被否定。

### 裁决 F-03（两级都生效、较严者胜）代码与行为落地

`BudgetPolicy` 不再有"解析出一个 quota"的说法：`modelQuota()` 精确等值回答 model 条目（含裁决：无前缀匹配——反向对照 #34 专门禁 `startsWith` 回潮），`providerWideQuota()` 回答 provider 条目；`ceilings()` 两级**各建各窗**（存在才建，两个 advisory lock 都进 sorted lockKeys，宽窗测量在宽窗锁之后——审阅者 V1 的竞态形状不存在）；`checkProviderQuota` 遍历全部 quota 窗口，并发与日数**各自计数、各自拒绝**。活库新用例：`looserModelEntryCannotLiftTheProviderCeiling`（provider=2/model=5，第三笔实测 429——修订前此处正是审阅者放行的第 3 笔）、`providerDayWindowClosesBeforeTheLooserModelDayWindow`（(3,2) 与 (5,5) 并存，provider 日数先关）；单元 `bothQuotaLevelsAnswerTheirOwnEntries`。控制 C2（`.limit(1)` 收平）退出码 1、红恰为两条活库用例。

### 裁决 F-04（带点 id：现状）

配置形状不变；model 级带点键仍响亮 503（装配期、`INVALID_PROVIDER_QUOTA_KEY`）；provider 级对带点 id 的计量由"审阅者探针"升格为交付用例：`dottedModelIdIsMeteredInTheProviderWindow`（活库实测 `gpt-4.1` 在 provider 合并窗里数并发）+ 单元把 `scope("mock","gpt-4.1")` 钉成数据。`entries[]` 备选形状留给 Owner（代码注释 + 主报告复核点 (9)）。

### 裁决 F-05（id 字符集）

`scope()` 入口拒绝 `[A-Za-z0-9._-]` 之外（含 `|`/空格）；键存侧拒绝 `.`/首尾 `|`/`||`/多段。`separatorBearingIdsAreRefusedNotCollided` 覆盖 `scope("p|q",null)`、`scope("p","q|r")`、`scope("p","q r")`、`{p|q:…, p:{q:…}}` 混合撞键文档与 stored `"p||q"`。

### 裁决 F-08（叶值归一化与两个零）

非数字/负数 → 503 `INVALID_BUDGET_POLICY`（含捕获 `ConversionFailedException`，反向对照 #32 守住异常不再逃逸）；`max-concurrent: 0` = 永久卡死 → 拒装配（#33 + 控制 C3）；`calls-per-day: 0` = 当日不放行 → 合法，活库用例断言首笔即 429 且 `rows()==0`、装配不因它 503。

## 3. 用例数逐用例名增减（49 → 57）

**新增 8，删除 0，改名 0**；`EXPECTED_TESTS`/`--expect-tests` 默认/主报告 §5 三处同步 57。

单元 `CostPricingTest` 18→22：

| 新用例名 | 钉住 |
|---|---|
| `quotaSuppliedThroughEnvironmentStyleNamesBinds` | F-01 env 通道生效 + 半 scope 拒 + 歧义拒 |
| `quotaLeavesAreNormalisedAtAssembly` | F-08：`"three"`/`-1`/`max-concurrent 0`/构造器 `(0,5)` 各 503；`calls-per-day 0` 绑得出条目 |
| `bothQuotaLevelsAnswerTheirOwnEntries` | F-03 两级各答各条目 + F-04(b) 带点 id 无前缀命中 + V4 精确匹配 |
| `separatorBearingIdsAreRefusedNotCollided` | F-05 |

活库 `T08PostgresTest` 31→35：

| 新用例名 | 钉住 |
|---|---|
| `looserModelEntryCannotLiftTheProviderCeiling` | F-03 provider 帽不被宽松 model 条目抬走 |
| `providerDayWindowClosesBeforeTheLooserModelDayWindow` | F-03 两级日数各按各自窗口检查 |
| `zeroCallsPerDayClosesTheDayButNotTheBoot` | F-08 `calls-per-day: 0` |
| `dottedModelIdIsMeteredInTheProviderWindow` | F-04(b) provider 级计量带点 id |

同名改写 5（旧断言依赖被裁决拆掉的 API 或旧证据形状）：`budgetPolicyCeilings`、`budgetPolicyOverrides`、`modelLevelQuotaReachesTheLookupThatReadsIt`（`providerQuota` → `modelQuota`/`providerWideQuota`）；`quotaWrittenAsNestedYamlBindsTheScopeTheLookupReads`、`nestedYamlQuotaIsEnforcedByTheService`（绑定证据进方法体 + 两级数值断言，后者数值 3/30+1/30 → 4/26+1/9 并在文档内显式声明 `image-units-per-article: 100`）。57 − 8 新增 − 5 改写 = **44 项逐字未动**，`r10-pg.json` 的逐用例名单可机器比对。

过程坦白（失败迭代与集成方的追问）：整改后**第一次**整轮运行退出码 **1**——`nestedYamlQuotaIsEnforcedByTheService` 期望第四笔 `second-model` 撞 provider 帽，实测先撞了文档未声明的 `image-units-per-article` SRS 默认帽 4（`QUOTA_EXCEEDED` ≠ `PROVIDER_QUOTA_EXCEEDED`）。顺序本身就是实现行为：文章计数帽在主循环先于配额窗口检查。这是自家新用例数值设计缺陷，不是被测代码缺陷；修法为**只在该测试自己的 YAML 文档里**把该帽声明为 100，失败原件保留不删（`r10-pg-selftest.json` + 同名 `-test-results/`）。主 agent 集成时如实把这一改动登记为开放问题 **T08-SRS-DEFAULT-CLASH**（P3，交第四轮复审判定"改测试前提"还是"产品语义问题"——即默认 4 单位下图片密集型调用会被日计数帽拒，这在真实部署里是否恰当属 Owner）；实施方立场：本用例的判定对象是配额两级绑定，文章级计数帽是无关前提，文档声明它只是让前提显式化——但**默认值的现实影响我没有证据回答**，该问题不自证关闭。

## 4. 反向对照与良性重写探针

44 条减弱逐条 REJECT（`blind=none, misplaced=none`），完整名单见 `r10-gates.json` 的 `--reverse-control` 输出。本轮新增 14 条 + 重靶 2 条：

| # | 减弱（回归形状） | 对应 |
|---|---|---|
| 29 | env 通道不再识别（`environmentShaped = false`） | F-01 |
| 30 | 枚举退回只认字面点号键 | F-01（派发要求的控制之静态半；运行时半 = 控制 C1） |
| 31 | 歧义 env 名改猜不拒 | F-01 |
| 32 | 不可读叶值以原始 `ConversionFailedException` 逃逸 | F-08 |
| 33 | `max-concurrent: 0` 被接受（永久卡死） | F-08 |
| 34 | model 键改前缀匹配 | 审阅者 V4 |
| 35 | provider 条目不再建自己的窗 | F-03 |
| 36 | model 条目不再建自己的窗 | F-03 |
| 37 | 第二个 `provider + "\|" + model` 藏进 `BudgetService` | F-06（承重证明） |
| 38 | stored 点号检查摘除 | F-05 |
| 39 | loader 挪出单元用例体 | F-02 A 探针 |
| 40 | 单元体内退回手搓扁平键 | F-02 |
| 41 | 活用例长出第二条手搓 `service(...)` | F-02 B 探针 |
| 42 | 测试侧 env 源退化（不再经 addFirst 注入） | F-01/第 14 项 |
| 19/24（重靶） | 写侧退回点号路径 / 两级收平 `.limit(1)` | 原靶串在本轮代码里已不存在，改锚现行形状的等价破坏 |

**良性重写 5 条，全部保持全绿（`brittle=none`）**：①`stored.contains(".")`→`indexOf(".") >= 0`；②活用例 `service(...)` 经一个局部变量中转；③单元 loader 循环参数逐行换行；④`BudgetService` 的 F-03 注释改写；⑤`activePolicy` 断言链换行。第④条同时证明第 11 项的模块扫描只判代码不判散文。

自我纠盲（如实记录）：本轮反向对照**第一次跑抓到过一个真盲区**——#19 退回 `path[0] + "." + path[1]` 当时逃过基于 `provider…model` 字样的 join 正则（变量名变了、`writers >= 2` 仍成立），补 `config_keys_by_scope` 逐位点锚后才 REJECT。44 这个数是过程产物，不是拍的。

## 5. 运行时控制（`.work` 副本，原件零触碰）

机制沿用审阅者 `variant_runner.py` 的形状：复制 `backend/` + runner 到 `.work/t08/r10-controls/<C>/`，只改副本源码，跑 `--tests <单套件> --expect-tests <该套件数> --evidence-name control`，解析 surefire XML 判定"退出码非 0 且红名单恰好覆盖 mustRed"。报告 `r10-controls.json` + `r10-controls-test-results/{C1,C2,C3}/` 原件已交付：

| 控制 | 改回的旧行为 | 结果 |
|---|---|---|
| C1 | `quotas()` 只认字面点号枚举（摘掉 env 通道） | 退出码 **1**；红 = `quotaSuppliedThroughEnvironmentStyleNamesBinds`（22 项中恰 1 红） |
| C2 | `checkProviderQuota` 收平为第一窗（`.limit(1)`） | 退出码 **1**；红 = `looserModelEntryCannotLiftTheProviderCeiling`、`providerDayWindowClosesBeforeTheLooserModelDayWindow`（35 项中恰 2 红） |
| C3 | `ProviderQuota` 守卫放回 `< 0`（接受 max-concurrent 0） | 退出码 **1**；红 = `quotaLeavesAreNormalisedAtAssembly`（22 项中恰 1 红） |

## 6. 本轮交付证据（`tests/engineering/T08/evidence/`，全部 BOM-free / LF）

| JSON | 同名原件目录 | 内容 | 退出码 |
|---|---|---|---|
| `r10-pg.json` | `r10-pg-test-results/` | 整改后整轮 57 项真实 PG | 0 |
| `r10-pg-selftest.json` | `r10-pg-selftest-test-results/` | 同一轮第一次：57 run/1 failure（§3 过程坦白） | 1 |
| `r10-pg-relative-work-root.json` | `r10-pg-relative-work-root-test-results/` | F-07 相对路径整轮实证 | 0 |
| `r10-controls.json` | `r10-controls-test-results/{C1,C2,C3}/` | 三个运行时控制的判定与 surefire 原件 | 各控制 1（预期红） |
| `r10-gates.json` | —（静态门，无 surefire） | `verify.py`、`--reverse-control`、`check_contracts.py`、`--path-selftest`×2 的完整 stdout 与退出码 | 全部 0 |

## 7. 仍未证明清单

1. **全量 `mvn -o clean verify`（本卡自身沙箱）**：我未跑（共享 `backend/target` 归主 agent，我只在隔离副本里跑定向 surefire）。该项已由**主 agent 在集成提交 `fb62212` 的提交信息中实测记录**：`mvn -B -ntp -o clean verify` 退出码 0、289 项 / 0 失败 / 147 跳过（281+8 恰为本轮 8 个新用例，+4 跳过为其中活库那半）。这是集成方的记录，不是我的自证，也不覆盖第四轮可能要求的复跑。
2. **真实 Spring 组合根**：应用从未以 `editorial.cost.enabled=true` 完整启动；`GET /api/v1/usage` 的 HTTP 端到端未实测（依赖 T03 身份链、T09 执行作用域）。
3. **配置合并面**：env 通道实证到 `SystemEnvironmentPropertySource` + 真 `Binder` 一层；真实部署里 env 与其它属性源/profile 的**合并顺序**效应（同名键谁赢）未证。
4. **`CostPorts.Executions` 无生产绑定、`over_run` 无外部投影、告警无生产 sink**：T09/T10/T11 前置，非 T08 完成项（与历轮相同）。
5. **裁决本身待 Owner 签字**：`unconfigured` 取值、`entries[]` 是否取代点号键、env 歧义即拒的能力边界——本轮按裁决实现，未替 Owner 决定任何一项。
6. **F-06 扫描的文本性**：变量名异形的第二个拼接、`String.join` 形态的 scope 键构造，正则不可见；位点锚与运行用例是补位不是完备证明。
7. **锁序约定**：`T08|PROVIDER-MODEL…` < `T08|PROVIDER|…` 靠标签字典序，未写成断言；并发用例覆盖行为不覆盖序。
8. **崩溃恢复/灾备、真实供应商计费**：未演练、未验证。
9. **单次运行**：57/57 是本轮一次实测记录，非统计稳定性声明；时序敏感用例复跑若红先对照 `r10-pg.json` 的 timeSeconds 基线。

## 8. 需要主 agent 代跑/代决清单（提交时的状态）

- ~~`mvn -o clean verify` 全量门禁~~：**已履行**——主 agent 在集成提交 `fb62212` 记录实测 exit 0（289/0/147）；第四轮若要求复测仍由其执行。
- ~~git 提交本轮整改与 evidence~~：**已履行**——fb62212（35 个文件，含本报告的初版与我后续报告改写的差异留在工作区）。
- ~~清理条目 `git mv`~~：主 agent 已在台账 protocol 里把该教训写成规则（"派单里的清理动作必须先核是否已被跟踪"），round3 遗留物保持未动。
- 剩余：第四轮复审（agent-c62923dd，已在跑）覆盖 §7 全部条目与本文件自审，并裁决 **T08-SRS-DEFAULT-CLASH**（§3 过程坦白：默认 `image-units-per-article=4` 与测试前提改 100 的关系是产品语义问题，不是我的自证范围）；`docs/execution/STATE.json` 由主 agent 维护（我从未写入）；Owner 侧待决见 §7-5。

## 9. 派发卡清理项的处置（偏离说明）

派发卡要求把中断会话遗留（`docs/execution/reviews/T08-round3/evidence/` 的 4 个探针文件与 `tests/engineering/T08/evidence/r3-review.json(+test-results)`）移入 `.work/t08/r3-legacy/`。开工前核对：这些文件**已全部被 git 跟踪**（`git ls-files` 命中，主 agent 已把第三轮审阅证据入库），`git status` 在两个目录下无任何未跟踪条目。移动/删除跟踪文件 = 篡改已交付的审阅历史，且超出"实现方不碰 git、不写他人路径"的边界。**处置：一律未动。**该结论如实回呈：若仍需清挪，请主 agent 执行或明示裁决。我自己的实验件全在 `.work/`（gitignored，未被任何交付文件引用为证据）：`r10-probe/`（Binder/Config 探针与离线 javac）、`r10-controls/`（控制脚本与运行副本）、`r10-gate-capture/`（门输出捕获与组装脚本），可随意丢弃，无跟踪依赖。

## 10. 与第三轮复核点的对账

| 复核点 | 状态 |
|---|---|
| F-01 env 通道（P2） | 修（§2 F-01）；用例绿 + 控制 C1 恰好红 + 静态 #29/30/31 REJECT |
| F-02 绑定证据进体内（P2） | 修（§2 F-02）；体内判定 + #39/40/41 REJECT + 良性②⑤保持绿 |
| F-03 两级都生效（裁决） | 落（§2 F-03）；窗口各建各量 + #24/35/36 REJECT + 控制 C2 + 两条活库新用例 |
| F-04 带点 id 现状（裁决） | 维持并升格为用例（§2 F-04）；`entries[]` 留 Owner |
| F-05 字符集（裁决） | 落（§2 F-05）；`separatorBearingIdsAreRefusedNotCollided` + #38 |
| F-06 全模块扫描（P2） | 修（§2 F-06）；`cost/**` 剥注释扫描 + #37 承重 REJECT |
| F-07 相对 work-root（P3） | 修（§2 F-07）；启动即绝对化 + `--path-selftest` + 整轮相对实测 0 |
| F-08 叶值归一化/零语义（裁决） | 落（§2 F-08）；#32/33 + 控制 C3 + 单元/活库双侧用例 |

本报告不自行声明 PASS 或 G1/G2；所有"绿"均指本轮沙箱实测退出码，终审权属主 agent 的独立复审。

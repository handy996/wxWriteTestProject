# T08 — 第三轮整改报告（对照 `docs/execution/reviews/T08-round3/review.md`）

日期：2026-10-08。输入：第三轮独立复审 verdict **CHANGES_REQUIRED**（`docs/execution/reviews/T08-round3/review.md` + `evidence/checks.json`），裁决 F-03/F-04/F-05/F-08 与发现 F-01/F-02/F-06/F-07。本报告只记录"按已下裁决整改 + 本轮自测证据"，不自行批准 T08、不声明任何跨任务门禁通过，`docs/execution/STATE.json` 未触碰、未执行任何 `git add`/`commit`。所有改动留在工作区待主 agent 审阅。

主报告 `docs/execution/reports/T08.md` 已按本轮裁决外科手术式同步（第 2.1 节第 6 条、第 2.2 节、§5 计数与新增实测行、§6.5 与"未证明事项"段——其中"本实现不使用 Binder 那条宽松绑定路径"一句是本轮必须改掉的错误陈述，现在按实测能力边界重写）。

## 1. 逐条整改（P2 → P3），每条带本轮实测退出码

### F-01（P2）env 通道静默丢配额 → 宽松绑定枚举，歧义即拒

**缺陷**：`SystemEnvironmentPropertySource` 会用 `EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MAX_CONCURRENT` 回答规范点号名，但 `quotas()` 只按字面 `editorial.cost.provider-quota.` 前缀匹配枚举到的原始键名——从环境变量注入配额时枚举**一条都不认**，`providers={}` + 开关若为 `unlimited` 即全部供应商静默无限，装配照样成功。

**修法**（`BudgetPolicyConfig.quotas()`）：
- 每个 `EnumerablePropertySource` 先判定 `environmentShaped = source instanceof SystemEnvironmentPropertySource`，走 `environmentQuotaName()`（`EDITORIAL_COST_PROVIDER_QUOTA_` 前缀、`_` 分段的形状解析），其余源保持 `canonicalQuotaName()`（原规范点号规则不变，第三轮不得改配置形状）；
- 两条分支都只做**形状解析**，值一律经 `Binder.get(configurable).bind(<规范点号名>, Integer.class)` 读取（`.work` 探针实测：Spring 的 `Binder.mapOf` 在虚线前缀下看不见 env 形状键，"自研枚举 + 逐名 bind"是探明后的选择，探针输出在 `.work/t08/r10-probe/`）；
- env 形状的**能力边界**：`_` 同时代表 `.` 与 `-`，`A_B_C` 有两种读法（provider `A` 的 model `B_C`？provider `A_B` 的 model `C`？）——中间段多于一个 token 直接 503 `INVALID_PROVIDER_QUOTA_KEY`，**拒装配而不是猜**；model 级 env 名因此整体不可表达，与 F-04 的裁决一致（配置形状不变，注释已标）。

**实测**：新用例 `CostPricingTest#quotaSuppliedThroughEnvironmentStyleNamesBinds`（provider 级 env 键绑定生效断言"不是 unlimited"、半条 scope 报 `QUOTA_NOT_CONFIGURED`、`..._MOCK_MODEL_MAX_CONCURRENT` 报 `INVALID_PROVIDER_QUOTA_KEY`）在整轮运行中绿：`run_pg --expect-tests 57` **退出码 0**。
**运行时控制**（只在 `.work` 副本里把枚举摘回"只认字面点号名"）：C1 **退出码 1**，且变红的恰好只有 `quotaSuppliedThroughEnvironmentStyleNamesBinds`（其余 21 项全绿）——这条用例是真的咬在修复上。原件：`tests/engineering/T08/evidence/r10-controls.json` + `r10-controls-test-results/C1/`。

### F-02（P2）绑定证据可被悄悄摘除 → 判定进用例方法体 + 良性重写探针

**缺陷**：`verify.py` 旧第 11 项对 YAML 绑定只查**整文件级**子串（loader 出现一次、`from(env)` 出现等），审阅者 V6 证明：把 loader 调用挪进辅助方法、或在用例里追加第二条手搓 `service(policy(...))` 覆盖绑定结果，门照样绿。

**修法**（`verify.py` 第 11 项）：
- 断言范围收紧到**断言所在的两个方法体**（`java_method_body` 切出 `quotaWrittenAsNestedYamlBindsTheScopeTheLookupReads` 与 `nestedYamlQuotaIsEnforcedByTheService`）：体内必须同时出现 `new YamlPropertySourceLoader()`、`document.getBytes`、`new ByteArrayResource(`、`BudgetPolicyConfig.from(env)`；活用例体内 `service(` 恰好一处、其参数必须是 `from(env)` 的结果（内联、或经一个直接由 `BudgetPolicyConfig.from(env)` 赋值的局部变量——两种等价拼法都接受），且体内不得出现 `new BudgetPolicy(`/`policy(wideCaps`/扁平 `editorial.cost.provider-quota.` 键；单元用例体内同样禁扁平手搓键。
- 测试文件同步改造：单元用例原先"从 `yaml(...)` 辅助方法拿环境"改为**体内自己加载**；活用例 `nestedYamlQuotaIsEnforcedByTheService` 的文档数值改成本文件任何手搓策略都不存在的 4/26 与 1/9，并新增 `activePolicy.providerWideQuota/modelQuota` 四条数值断言——绑定证据从此不可冒充。
- **良性等价重写探针**（`benign_probes()`，与反向对照同一套机制、方向相反）：等价改写必须保持全绿，防门硬编码到拼写。本轮 5 条：①`stored.contains(".")`→`stored.indexOf(".") >= 0`；②活用例 `service(BudgetPolicyConfig.from(env))` → 局部变量中转；③loader 循环参数换行；④`BudgetService` 里 F-03 注释改写；⑤`activePolicy` 断言链换行。实测全部 stayed green（`brittle=none`）。

**实测**：`verify.py` **退出码 0**；`--reverse-control` **退出码 0**，其中本轮新增的 F-02 三探针——"loader 挪出单元用例体"、"单元体内退回手搓扁平键"、"活用例长出第二条手搓 `service(...)`"——逐条 **REJECT**（把审阅者 V6 的装饰形状与 A1 变形都做成了减弱条目）。

### F-03（裁决，代码半）两级语义定死为"两级都生效、较严者胜"

**裁决落实**：`BudgetPolicy` 不再有"解析出一个 quota"的 API——删掉 `providerQuota()/quotaScope()`，改为 `modelQuota(provider, model)`（`providers.containsKey(scope(provider, model))`，**精确等值**、无回退）与 `providerWideQuota(provider)`（`containsKey(scope(provider, null))`），各答各的条目、谁也不遮蔽谁；`BudgetService.ceilings()` 对两个 Optional **各自建窗**（model 条目存在→加 model 窗口；provider 条目存在→加跨 model 合并窗口），`checkProviderQuota` 把 `quota()!=null` 的窗口**全部**过一遍：并发数与日调用数都按各自窗口计，任何一窗越界即 429。审阅者 V1 的"覆盖两级的 overlay"变体当时 49/49 全绿还暴露了它的竞态（读宽窗不持宽窗锁）——本实现里两个窗口都是 `ceilings` 里已加锁的成员，宽窗测量在宽窗锁之后。

**新用例**：单元 `bothQuotaLevelsAnswerTheirOwnEntries`（两级各答各条目 + `mock-model-v2` 无前缀命中 + 带点 id 无 model 级条目）；活库 `looserModelEntryCannotLiftTheProviderCeiling`（provider=2/model=5：前两笔绿、**第三笔 429**，修订前这里正是审阅者实测放行的第 3 笔）、`providerDayWindowClosesBeforeTheLooserModelDayWindow`（provider (3,2) 与 model (5,5) 并存，provider 日数先关）、`nestedYamlQuotaIsEnforcedByTheService` 的跨 model 计数从 3 改为 4 并保留 model 级 1 的先拒。
**实测**：整轮 `run_pg` **退出码 0**；运行时控制 C2（服务退回 `.limit(1)` 单窗） **退出码 1**，变红恰好 `looserModelEntryCannotLiftTheProviderCeiling` + `providerDayWindowClosesBeforeTheLooserModelDayWindow` 两条。静态侧三条减弱（`.limit(1)` 收平、两个 `if (...isPresent())` 各删一支）全部 REJECT。

### F-04（裁决）带点 model id 维持现状

形状不变：model 级带点键在装配期响亮拒绝（`INVALID_PROVIDER_QUOTA_KEY`，既有路径，本轮未动配置形状——`entries[]` 属 Owner）；provider 级对带点 id 的计量从"审阅者探针"升格为**交付代码里的用例**：`dottedModelIdIsMeteredInTheProviderWindow`（活库：`gpt-4.1` 三笔并发在 provider=2 处拒第三笔）+ `scope("mock","gpt-4.1") == "mock|gpt-4.1"` 与 `modelQuota("mock","gpt-4.1").isEmpty()` 钉成数据（`bothQuotaLevelsAnswerTheirOwnEntries`）。`BudgetPolicyConfig` 注释标明这是被裁决的能力边界。

### F-05（裁决）分隔符/字符集

`scope()` 段字符集 `[A-Za-z0-9._-]`（`Pattern SEGMENT_SHAPE`，`|`/空格/其它字符在**拼键入口**即 503），键存侧维持并加强 `stored` 检查（点号、首尾 `|`、`||`、多段）。审阅者演示的 `{p|q: [...], p: {q: [...]}}` 撞键混合文档现在装配期拒——`separatorBearingIdsAreRefusedNotCollided` 同时断言 `scope("p|q", null)`、`scope("p", "q|r")`、`scope("p", "q r")` 拒绝与混合文档拒绝。减弱对照"stored 点号检查摘除"REJECT。

### F-06（P2）"全模块唯一 join"的扫描只覆盖 2 个文件

**修法**：joined 正则的扫描对象从 `policy + config` 改为 **`cost_sources()` 全 19 个文件**，并先 `strip_java_comments`（按代码判定，不按注释文本——首轮全模块扫描就是被 `BudgetService` 注释里那句"provider + "|" + model"绊出第二个命中，这恰好说明扫描现在真的覆盖到了）。`BudgetService` 本轮改走 `String.join("|", ...)` 建锁标签，模块内 `provider … model` 拼接只剩 `scope()` 一处。
**承重证明**：反向对照新增"把第二个 join 藏进 `BudgetService`"（`String shadowScope = provider + "|" + model;`）→ **REJECT**；旧的 2 文件扫描对同一条减弱是瞎的（该文件不在扫描集内），这半句就是 F-06 的本体。
**诚实边界**：文本扫描跟的是 `provider`/`model` **变量名拼写**——若将来有人用别的变量名拼同类作用域键，正则看不见；锚点 `config_keys_by_scope`（写侧三处逐位点）与"窗口 SQL 双 where + `if (...isPresent())`"锚点是在文本正则之外的补位。这条列入"仍未证明清单"。

### F-07（P3）相对 `--work-root` 吞掉成功轮

**修法**：`resolve_work_root()` 启动即 `.resolve()`；证据路径展示统一走 `inside_repo()`（相对仓库根就记相对、在外面就记绝对，finally 永不因路径形状抛 ValueError）；新增 `--path-selftest` 旗标（不启动任何东西，用与真实运行**同一个** `resolve_work_root` 证明"相对输入 → 绝对运行目录 → 在仓库根之内"）。
**实测**：`--path-selftest --work-root .work/...` 与默认形态各 **退出码 0**（输出在 `r10-gates.json`）；整轮 `--work-root .work/t08/r10-relative` 真实跑 **退出码 0**、57/57、证据完整写出（`isolatedWork` 为仓库相对形态记录），对照旧行为"14 条命令全绿→finally 炸→exit 1 无证据"。

### F-08（P3）叶值归一化与两个"零"

非数字/负数叶值经 `quotaLeaf()` 的 `catch (BindException | ConversionFailedException)` 归一化为 503 `INVALID_BUDGET_POLICY`（旧行为：`"2, five"` 以 Spring 原始栈逃逸，响亮但不是 PUBLIC_FAILURE）；`ProviderQuota` 紧凑构造器 `maxConcurrent < 1` 拒（`max-concurrent: 0` = 永久卡死，配置错误）、`callsPerDay < 0` 拒、`callsPerDay == 0` **合法**（当日不放行）。行为半由活库 `zeroCallsPerDayClosesTheDayButNotTheBoot` 钉住（首笔即 429、`rows()==0`），装配半由 `quotaLeavesAreNormalisedAtAssembly` 钉住（"three"/`-1`/`0`/直接构造 `(0,5)` 各 503，`calls-per-day: 0` 绑得出条目）。控制 C3（放回 `< 0`）**退出码 1**、变红恰为该装配用例。

## 2. 本轮运行证据（`tests/engineering/T08/evidence/`，JSON + 同名 `-test-results/` 原件）

| 文件 | 内容 | 退出码 |
|---|---|---|
| `r10-pg.json` + `r10-pg-test-results/` | 整轮 57 项（22+35）真实 PG，`--work-root` 绝对形态 | 0 |
| `r10-pg-selftest.json` + `r10-pg-selftest-test-results/` | 本轮**第一次**整轮：57 run/1 failure——`nestedYamlQuotaIsEnforcedByTheService` 的第四笔先撞 `image-units-per-article` 默认帽 4（报 `QUOTA_EXCEEDED` 非 `PROVIDER_QUOTA_EXCEEDED`），自家新用例数值选错，文档显式声明该帽后绿 | 1（如实保留） |
| `r10-pg-relative-work-root.json` + 同名 `-test-results/` | F-07 的相对路径整轮实证 | 0 |
| `r10-controls.json` + `r10-controls-test-results/{C1,C2,C3}/` | 运行时控制三件（只在 `.work` 副本回退旧行为） | 各 1（预期红） |
| `r10-gates.json` | `verify.py`、`--reverse-control`、`check_contracts.py`（T02 脚本，只读执行）、`--path-selftest` ×2 的完整 stdout 与退出码 | 全部 0 |

## 3. 用例数逐用例名增减（49 → 57）

`run_pg.py` 的 `EXPECTED_TESTS` 默认与 `--expect-tests`、主报告 §5 已同步为 57（`CostPricingTest` 22 / `T08PostgresTest` 35）。

**新增 8（无改名、无删除）**：

| 侧 | 用例名 | 对应条目 |
|---|---|---|
| 单元 | `quotaSuppliedThroughEnvironmentStyleNamesBinds` | F-01 |
| 单元 | `quotaLeavesAreNormalisedAtAssembly` | F-08 |
| 单元 | `bothQuotaLevelsAnswerTheirOwnEntries` | F-03 / F-04(b) / V4 |
| 单元 | `separatorBearingIdsAreRefusedNotCollided` | F-05 |
| 活库 | `looserModelEntryCannotLiftTheProviderCeiling` | F-03 |
| 活库 | `providerDayWindowClosesBeforeTheLooserModelDayWindow` | F-03 |
| 活库 | `zeroCallsPerDayClosesTheDayButNotTheBoot` | F-08 |
| 活库 | `dottedModelIdIsMeteredInTheProviderWindow` | F-04(b) |

**同名但内部改写**（旧断言依赖被裁决删除的 API 或证据形状）：`budgetPolicyCeilings`、`modelLevelQuotaReachesTheLookupThatReadsIt`、`budgetPolicyOverrides`（`providerQuota` → `modelQuota`/`providerWideQuota`）；`quotaWrittenAsNestedYamlBindsTheScopeTheLookupReads`（loader/字节/`from(env)` 进体内）；`nestedYamlQuotaIsEnforcedByTheService`（数值 3/30,1/30 → 4/26,1/9，新增 `activePolicy` 绑定数值断言与 `image-units-per-article` 显式帽）。其余 39 项逐字未动（`r10-pg.json` 与 `r3-implementer` 系 evidence 的 suites[].cases 名单可比对）。

## 4. 反向对照 / 良性探针计数与结果

- 减弱条目 **30 → 44**（本轮新增 14 条 + 2 条重靶：`reader joins` 的靶串改到 `scope()` 现存那行、`perModel` 靶失效后换成 `.limit(1)` 收平）。`--reverse-control` **退出码 0**，`blind=none, misplaced=none`。
- 良性重写探针 **5 条，`brittle=none`**（清单见 F-02 修法）。
- 过程坦白：本轮反向对照**第一次跑抓到过一个真盲区**——"写侧退回 `path[0] + "." + path[1]`"当时逃过基于 `provider…model` 字样的 join 正则（`writers >= 2` 仍成立），补逐位点锚点 `config_keys_by_scope` 后该条变 REJECT；这条经历说明 44 不是拍的数。

## 5. 派发卡清理项的处置（偏离说明）

派发卡要求把中断会话遗留的 `docs/execution/reviews/T08-round3/evidence/{R3Probe.java, java-probe-output.txt, weakening_probe.py, srs_and_ceiling_probe.py}` 与 `tests/engineering/T08/evidence/r3-review.json(+test-results)` 移入 `.work/t08/r3-legacy/`。开工前核对：这些文件**已被主 agent 提交为跟踪内容**（`git ls-files` 命中；`git log` 显示 round-3 评审记录已入库），移动它们 = 删除跟踪文件，超出实现方权限且会弄脏审阅证据。**处置：一律未动**；审阅者的 `r3-review-c/d` 系列同样未碰。若仍需清挪，请主 agent 自己 `git mv`（一条命令的事，但必须由持有 git 的人做）。

我自己的实验件都在 `.work/`（gitignored）：`r10-probe/`（Binder/Config 探针与离线 javac 输出）、`r10-controls/`（控制脚本与运行副本）、`r10-gate-capture/`。未删除——它们已被 evidence 引用路径指名，且 `.work` 本就不入库；主 agent 若判定要清，`git clean -fdx .work` 级别即可，无跟踪依赖。

## 6. 仍未证明清单（诚实边界，不口头补洞）

1. **全量 `mvn -o clean verify` 未跑**（共享 `backend/target` 归主 agent）：本轮只在 `run_pg` 的隔离副本里跑了定向 surefire（57 项）。281/143 级别的门禁矩阵需主 agent 代跑。
2. **真实 Spring 组合根从未启动**：`editorial.cost.enabled=false`；嵌套 YAML/env 通道都是"真 loader + 真 Binder + 真环境对象"级实证，不是完整 Boot 上下文；`GET /usage` 的 HTTP 端到端仍未实测（依赖 T03 身份链与 T09 执行作用域）。
3. **`CostPorts.Executions` 无生产绑定**、`over_run` 无外部投影、告警投递无生产 sink——T09/T10/T11 前置，非 T08 完成项（与第 2 轮同）。
4. **裁决 F-03/F-04 的开关与形状本身待 Owner 签字**：`unconfigured` 取值、`entries[]` 是否取代点号键、env 通道"歧义即拒"的能力边界（本报告按裁决实现，未替 Owner 决定）。
5. **F-06 扫描的文本性**：join 正则跟 `provider`/`model` 变量名拼写；异名拼接或 `String.join` 形态的第二个作用域键拼法不在其视野内（`config_keys_by_scope` 与运行时用例是补位，不是完备证明）。
6. **锁序推理依赖标签前缀字典序**（`T08|PROVIDER-MODEL…` < `T08|PROVIDER|…`）：成立且由 `ceilings.sort` 统一，但那是实现内约定，未写成断言——并发用例（1+34）覆盖的是行为不是序。
7. **崩溃恢复/灾备、真实供应商计费**：与历轮相同，未演练、未验证。
8. **单次运行**：57/57 绿是本轮一次实测记录，非统计稳定性声明（`lastBalanceSingleWinner` 这类并发用例历史上偶发过时序敏感，主 agent 复跑若见红请先看 `r10-pg.json` 的 timeSeconds 基线）。

## 7. 需要主 agent 代跑的清单

- `mvn -o clean verify`（或既有门禁矩阵）确认 281/143 不退化；
- `git add/commit` 本整改与 evidence（我不碰 git）；
- 若采纳 §5 的偏离处置，更新派发卡的清理条目；
- 第四轮复审建议覆盖：`r10-controls.json` 的三个 mustRed 名单是否成立、44 条反向对照是否有新的 STALE、以及 `nestedYamlQuotaIsEnforcedByTheService` 数值改写后是否仍与手搓策略互斥（4/26,1/9 在本文件唯一性）。

## 8. 改动文件清单（本轮全部写入）

跟踪文件（修改）：`backend/src/main/java/com/example/editorial/cost/BudgetPolicy.java`、`BudgetPolicyConfig.java`、`BudgetService.java`；`backend/src/test/java/com/example/editorial/cost/CostPricingTest.java`、`T08PostgresTest.java`；`tests/engineering/T08/verify.py`、`run_pg.py`；`docs/execution/reports/T08.md`。
跟踪路径下的新文件：`docs/execution/reports/T08-Revision-R3.md`（本文件）、`tests/engineering/T08/evidence/` 下 §2 表列的 JSON 与目录。
冻结契约、迁移草案/V5、`STATE.json`、其它任务目录与审阅者证据：未触碰（`check_contracts.py` 退出码 0 在 `r10-gates.json` 里）。

# T08（成本计量与配额准入）独立复审 — 第四轮

- 复审方：本 agent（独立复审方，第四轮；前两派单 agent-c62923dd / agent-84592013 启动即失败、零工件）
- 被审字节：提交 `fb62212`（代码 5 个 + `tests/engineering/T08/verify.py`、`run_pg.py` + `evidence/r10-*.json`）、`c21e681`（整改报告 v2）
- 判决：**CHANGES_REQUIRED**
- 状态：完成（七项逐条落盘，全部为实测；未复现的项在 §10 明列）

摘要（判由，细节在对应小节）：

1. 三条裁定我独立检验后**全部接受**：① 两级都生效、较严者胜（真库 7 条自建跨 model 探针 + 交付用例，§1/§5）；② 含点 model id 维持装配期响亮拒绝＝能力边界（§1/§5，`dottedModelIdIsMeteredInTheProviderWindow` 与我的混窗探针两侧闭合）；③ id 段 `[A-Za-z0-9._-]+`、含 `|` 即拒（§5 的 `separatorBearingIdsAreRefusedNotCollided`，我的 B5 削弱能让第 11 门红）。
2. 第三轮八条发现里 **F-01 / F-03 / F-04 / F-05 / F-06 / F-07 / F-08 关闭**，**F-02 未关闭**（换了摘法：注释装饰 + 手搓平铺键后 14 门全绿且真库 57 例全绿，§3）。
3. 新发现 **P2 两条**：F-R4-01（provider 窗带 `owner_id` ⇒ 一条 provider 帽按 Owner 数放大，文档与用例双双失真）、F-R4-06（体内绑定证据可降级为文本，第 10/11 门都只查子串）。**P3 十三条**：被测代码 6、门实现 2、文档与覆盖 3、交付工具面 2（逐条见 §9）。
4. 我没有把"跑不了"当缺陷：`mvn` 全量、真组合根、profile 合并顺序都在 §10/§11 明列为"未由本复审复现，交主 agent"，退出码台账见 §12。

> **本次为中断会话的续跑。** 中断前（约 01:44）只完成到：本骨架落盘 + 第一次 `run_pg.py` 基线跑（`--evidence-name r4-main`，退出码 **0**，57 项 / 0 失败 / 0 跳过 = 单元 22 + 活库 35，14 条子命令逐条 0，`expectations.problems=[]`）。续跑者对该继承测量**重新核对了字节**而非照抄：直读 `r4-main.json` 原文确认 `exitCode:0`、两套件计数与逐用例名单（8 个新用例名 `bothQuotaLevelsAnswerTheirOwnEntries`、`quotaSuppliedThroughEnvironmentStyleNamesBinds`、`quotaLeavesAreNormalisedAtAssembly`、`separatorBearingIdsAreRefusedNotCollided`、`looserModelEntryCannotLiftTheProviderCeiling`、`providerDayWindowClosesBeforeTheLooserModelDayWindow`、`zeroCallsPerDayClosesTheDayButNotTheBoot`、`dottedModelIdIsMeteredInTheProviderWindow` 全部在列、无删除、无改名），并核对其 `inputFingerprints` 里 V5 = `5eadd5294216d82ec4f4fd57b501975f4bd82a743403e1b861f8bfbaedff86fd`，与第三轮已入库指纹一致（冻结迁移字节未动）。
>
> **违规自报（结构性观察，非被审缺陷）**：`run_pg.py` 把证据路径硬编码为 `HERE / 'evidence'`（`run_pg.py:389`，无 `--evidence-dir` 开关），所以本会话的 `r4-main.json` + `r4-main-test-results/` 曾落在我的目录**之外**的受控目录 `tests/engineering/T08/evidence/`。二者是本会话自造的**未跟踪**文件（`git ls-files` 核对为空），不是受控源、不是冻结证据；处置见 §12 末段：先逐字节复制进本目录 `evidence/`、sha256 逐只核对一致（`e23425821c0f…185b9f04` 与 5 个 surefire 文件全 `match=True`，脚本 `evidence/r4_preserve_controlled.py`），**再**删除我在受控目录下留下的那两个条目，删除后 `Test-Path` 双双 `False`、`git status --porcelain` 在 `tests/engineering/T08/` 下无条目。后续 9 次运行全部把 `run_pg.HERE` 指到本审查目录，未再污染受控目录。
>
> 我的临时物只有 `tests/engineering/T08/.work/r4-*`（`r4-pg`、`r4-rel`）与 `$env:TEMP\` 下的 `t08r4\`、`t08r4-rel\`、`r4-rel-workroot\`，交付前已全部删除并逐个证明 `Test-Path` 为 `False`；六个哈希命名工作根（`336f4ccd…`/`6621bb23…`/`8abbdcfd…`/`9da386b1…`/`c1277cf0…`/`d2bdf470…`）经时间戳（10-07 11:24 → 23:02）与 `evidence/` 中 `main-repro-*`、`t08-r2-*`、`r3-main-repro-49` 的落盘时间一一对应，判定为**集成方/前轮会话的目录，不是我的**：本轮不读其内容作证据、不清理。


## 0. 方法与约束

- 只写 `docs/execution/reviews/T08-round4/`。
- 禁跑 `mvn` 与任何写 `backend/target/` 的命令；全量 verify 归主 agent（其自报 exit 0、289 项 / 0 失败 / 147 跳过），列入"未由本复审复现"。
- 削弱/变异/临时库只在本 agent 的 `tests/engineering/T08/.work/r4-*` 或 `$env:TEMP\t08r4\` 内做，结束前自删并证明。
- 主 agent 三条裁定独立检验，不默认正确：① 两级限额都生效、较严者胜；② 含点 model id 维持装配期响亮拒绝（能力边界）；③ id 段必须匹配 `[A-Za-z0-9._-]+`，含 `|` 即拒。

## 1. provider 封顶是否真跨 model（裁定 ① 的实证）

结论：**成立（真跨 model）**，但发现一条同族的新缺口：**provider 窗口按 owner 分区**，`maxConcurrent=N` 实际是"每 Owner 每 Provider 每天 N"，两 Owner 实测放行 4 笔（配置写的是 2）。定为 **F-R4-01 · P2**。

### 我跑了什么

自建配置 provider=2 / modelA=5 / modelB=5（**两条 model 条目都放宽**，比交付用例只放宽一条更严的形状），在真实 PostgreSQL 上跑我自己写的 7 条探针用例（`evidence/r4_probe_methods.java`，只注入 `%TEMP%\t08r4\scratch\backend` 里的副本，受控源零改动），经 `run_pg.py` 的隔离副本执行（`evidence/r4_probe_runner.py`，monkeypatch `ROOT/HERE/MIGRATIONS`，集群与 surefire 全在仓库外）：

```
python docs/execution/reviews/T08-round4/evidence/r4_probe_runner.py C:/Users/eie04/AppData/Local/Temp/t08r4/scratch all r4-probe-cross-model
```

surefire 原件（`%TEMP%\t08r4\scratch\.work\a17e2d41…\backend\target\surefire-reports\TEST-com.example.editorial.cost.T08PostgresTest.xml`）：

```
suite tests=7 failures=0 errors=0 skipped=0
  pass r4ProbeThreeCallsOnOneModelWithBothEntriesLoose     (A,A,A → 第 3 笔拒)
  pass r4ProbeInterleavedAthenBthenA                       (A,B,A → 第 3 笔拒；随后 B 也拒)
  pass r4ProbeInterleavedAABB                              (A,B,B,A → 第 3、4 笔拒)
  pass r4ProbeProviderWindowSpansArticles                  (provider=2 跨两篇文章 → 第 3 笔拒)
  pass r4ProbeDottedAndPlainShareOneProviderWindow          (dotted 行与普通行同窗 → 第 3 笔拒)
  pass r4ProbeProviderDayCountIsCrossModel                 (日数 2 跨 model 计数 → 第 3 笔拒)
  pass r4ProbeProviderWindowOwnerPartition                 (见下)
```

`run_pg.py` 侧 14 条子命令全部退出码 0（含 maven 那条：`Tests run: 7, Failures: 0`，`BUILD SUCCESS`），证据 `evidence/r4-probe-cross-model.json`；**外层退出码是 0**（脚本自己解析 XML，不受 runner 的套件名闸门影响）。

判据（代码形状，与实测一致）：`BudgetService.java:311-317` 的 provider 窗 `where` 是 `l.owner_id=? AND l.provider=? AND l.bucket_day=?`，**不含 model**；`CostLedger.java:85` 的 `holds` 是同一 SQL 里的 `count(*) FILTER (... status='RESERVED')`，所以跨 model 累加发生在数据库，不是 Java 侧计数。三种交错形状 + 跨文章 + 混合带点 id 全部按 provider 帽拒，**没有一种被放行**，所以"第 3 笔必须被拒且拒因归 provider 级"这条**成立**：以 (2,5,5) 的形状，第三笔在 model 窗（2<5）不可能拒，只有 provider 窗（2>=2）会拒，`429 PROVIDER_QUOTA_EXCEEDED` 的归因由数值唯一确定。裁定 ① 我独立接受。

### F-R4-01（P2）provider 窗口带着 `owner_id`，等于把一条 provider 上限按 Owner 数量放大

最小复现：`r4ProbeProviderWindowOwnerPartition`（`policy(provider=(2,30))`，Owner1 两篇 hold 放行，Owner2 两篇 hold 放行，用例 stdout 实测记录）：

```
R4-OWNER-PARTITION live holds on provider=mock-provider with maxConcurrent=2 -> 4
```

即配置写 2、库里同时有 **4** 笔 live 预占。期望（按交付文档的字面语义）/实际：期望"provider 条目量该 provider 全部 model 的合并窗口"＝该 provider 的合并窗；实际是 `(owner, provider, day)` 的合并窗。锁键同样带着 owner（`BudgetService.java:312-314`），所以两个 Owner 的准入在 provider 窗上**根本不互斥**。

为什么这是缺陷而不是"另一种合法设计"：

1. 本卡**自己**在 `docs/execution/reports/T08.md:51` 用的推理是"过去 provider 级条目在 `owner+provider+model+day` 窗口上度量，等于把一条 provider 上限按 model 数量放大"——同一句话把 owner 换成 model 就正好命中现在的形状；修法文档只讲"窗口跟着条目层级走"，层级里从没提 owner。
2. `BudgetPolicy.java:18-23`、`BudgetService.java:142-151` 的 javadoc 与 `T08.md:26/66/137` 全部只说"该 provider 全部 model 的合并窗口"，**没有一处声明按 Owner 分区**。
3. 被测代码与文档**没有任何一条用例**用第二个 Owner（`T08PostgresTest.java:67` 只有一个 `OWNER` 常量，全部配额用例单 Owner），所以这个维度在证据上是空白：既没钉住"按 Owner"，也没钉住"全局"。
4. SRS 32.2（`docs/AI-Editorial-Agent-SRS-v1.0.md:1093`）写的是"Provider 实际限额独立配置并读取返回头，达到预算/并发/速率中任何一个上限都应暂停新调用。**禁止通过多 Key 绕过供应商限流**"。provider 的"实际限额"是供应商账号（凭据）的属性，不是内部 Owner 的属性；多 Owner 共用一个供应商凭据时，按 Owner 分区的强制效果就是**超订供应商真实限额**，与被禁止的形状同类（不是同一动作，但同一后果）。

缓解与定级依据（如实）：SRS OQ-18（`:1290`）当前默认"单用户、2 篇并发"，且计划用户量本身未关（"产品/运维 / 压测前"），所以**今天现役部署不会触发**；这也是我不定 P1 的原因。但它是 F-01/F2-01 同族（"配了不完全生效"）的第三形态，且是**响亮失败都没有**的那一种。

要求（整改或登记，二选一，不替 Owner 决定语义）：
- 要么把窗口与锁键的 owner 维度去掉（provider 级＝真·全局，model 级＝`(owner?, provider, model, day)`——注意去掉 owner 后必须同时决定 model 窗是否也去掉，否则两级维度不一致），补两条用例（第二 Owner 的第 N+1 笔必拒；以及锁键形状的用例），并把改动写进 `T08.md` 与 javadoc；
- 要么**显式声明现状**：`T08.md`、`BudgetService.ceilings()` javadoc 写明"provider 级配额按 `(owner, provider, day)` 计量，多 Owner 共用一个供应商凭据时实际上限按 Owner 数放大"，并加一条用例把这个语义钉成数据（我给的 `r4ProbeProviderWindowOwnerPartition` 就是现成的形状），同时把它列为 Owner 待决项与 `entries[]` 一起裁。

我倾向后者作为本轮最小整改（语义归属是 Owner 的决定，文档失真与证据空白是我的判定范围）。

### 顺带（不是缺陷，工具形状）

`run_pg.py:338-342` 的套件名校验拿 `--tests` 原文比对，所以 **Surefire 方法过滤器（`T08PostgresTest#m1+m2`）无法与 `--expect-tests` 同时用**：14 条子命令全 0、surefire 7/0/0，runner 仍以 `no Surefire report for T08PostgresTest#…` 判 1 并不写 `-test-results` 目录。我这轮靠直接读工作目录里的 surefire 原件绕开（见上），**没改脚本**。建议（P3，工具）：wanted 比对先用 `split('#')[0]` 取类名。

## 2. 宽松绑定的新静默路径

结论：**"歧义即拒"在 env 通道自身名称的多读法上成立（实测），拼错叶名也响亮；但找到 3 条新的静默/失真路径**，另有一条实测把报告的一处措辞证伪为"不是缺陷但文档会误导"。

复现命令（一条）：

```
python docs/execution/reviews/T08-round4/evidence/r4_env_probe_build.py     # → EXIT=0，逐行结果见 evidence/r4-envprobe-transcript.txt
```

（javac/java 用 `.tools/t02/jdk-21.0.12.1+1`，classpath = 我隔离副本的 `target/classes` + m2 全部 212 只 jar；不碰 `backend/target`。）

### 2.1 逐问实测答案

| 问 | 探针 | 实际（退出码 0 的 transcript 行） | 判定 |
| --- | --- | --- | --- |
| env 通道现在生效吗 | A1 | `BOOT OK providers={mock=2/5}` | F-01 修复成立 |
| 只写一条叶 | A2 | `REFUSED 503 QUOTA_NOT_CONFIGURED` | 响亮 ✓ |
| 叶名拼错 `MAX_CONCURENT` | B1 | `REFUSED 503 INVALID_PROVIDER_QUOTA_KEY` | 响亮 ✓ |
| 未知叶 `..._FOO` / `..._MIN_CONCURRENT` | B3/B5 | `REFUSED 503 INVALID_PROVIDER_QUOTA_KEY` | 响亮 ✓ |
| 只有叶没有 provider | B4 | `REFUSED 503 INVALID_PROVIDER_QUOTA_KEY` | 响亮 ✓ |
| **前缀拼错** `EDITORIAL_COST_PROVIDER_QUOTAS_…`（多一个 s） | **B2** | **`BOOT OK providers={(EMPTY)}` + `unconfigured=UNLIMITED`** | **静默 ⇒ F-R4-02** |
| `_` 双读法（`OPEN_AI`＝`open-ai` 还是 `open.ai`） | C1 | `REFUSED 503 INVALID_PROVIDER_QUOTA_KEY` | "歧义即拒"成立 |
| model 级走 env | C2 | `REFUSED 503 INVALID_PROVIDER_QUOTA_KEY` | 响亮 ✓（与裁决 ② 一致） |
| **env 段大小写**：`..._QUOTA_MOCK_…` 而真实 provider id 是 `MOCK` | **D1/D2** | **`providers={mock=2/5}`；`providerWideQuota("MOCK")=false`、`("mock")=true`** | **静默失配 ⇒ F-R4-03** |
| 值非数字 `three` | E1 | `REFUSED 503 INVALID_BUDGET_POLICY` | F-08 归一成立，无异常冒爆 |
| 负值 / `max-concurrent=0` / 空值 | E2/E3/E6 | 各 `REFUSED 503 INVALID_BUDGET_POLICY` | 响亮 ✓ |
| `calls-per-day=0` | E4 | `BOOT OK providers={mock=2/0}` | 合法"当日关闭" ✓ |
| **`calls-per-day=99999999999`（超 int）** | **E5** | **`REFUSED 503 INVALID_BUDGET_POLICY`** | 响亮但**类型自相矛盾** ⇒ F-R4-04 |
| YAML 与 env 同名不同值（文件 100 / env 2） | F1 | `BOOT OK providers={mock=2/2}`，**不拒**，取 env | 见 2.2：不是缺陷，是措辞会误导 |
| env 形状键放进非 env 类型的源 | G1/G2 | 忽略；且 `getProperty(规范名)=null` | **与 Spring 一致**，不是缺陷 |
| **点号规范名放进 env 类型的源** | **H1/H2** | **`getProperty()=2` 能读到，但 `from(env)` 给 `(EMPTY)`** | **静默丢 ⇒ F-R4-05** |
| 开关本身走 env | I1 | `providers={mock=2/5} unconfigured=REFUSE` | ✓ |

### 2.2 新发现

**F-R4-02 · P3 · env 前缀拼错＝静默全空，F-01 的形状在"差一个字符"处仍然活着。** 复现：上表 B2。期望（按本轮声称"响亮失败"）：装配期拒绝；实际：装配成功、`providers={}`、配 `unconfigured=unlimited` 时所有 provider 不限。判据：`BudgetPolicyConfig.java:181` `if (!lowered.startsWith(ENVIRONMENT_QUOTA_PREFIX)) return;`——env 分支对"看着像但拼错"的前缀直接静默返回，而同一个方法对拼错的**叶名**是响亮 `throw`（`:193-195`）。这不是"任何配置系统都无法识别拼错的键"那种不可为：该源**已经**被识别为 env 类型、已经在循环里逐条看名字，一条 `startsWith("EDITORIAL_COST_PROVIDER_QUOT")` 的前缀邻域检查就能把它变成响亮失败（叶名分支正是这么做的）。最小修法（任一）：env 分支对"以 `EDITORIAL_COST_PROVIDER_QUOTA` 开头但不等于规范前缀（大小写无关）"的键当场 503；或补一条用例把这个静默形状钉住并写进 `T08.md` 的启用前置条件（"配额走 env 时前缀拼错不会有任何提示，请核对启动日志/`GET /usage`"）。定 P3 而非 P2 的理由：需要人**同时**犯拼写错并选择 `unlimited`；F-01 当时是**正确拼法**被丢，所以是 P2。

**F-R4-03 · P3 · env 通道把 provider id 强制小写，与 `scope()` 允许大写字母、账本按原样比较之间不对称，结果静默失配。** 复现：D1/D2（配置写 `EDITORIAL_COST_PROVIDER_QUOTA_MOCK_…`，provider 实际叫 `MOCK` → 键存成 `mock`，运行期 `providerWideQuota("MOCK")` 为空 → 该 provider 不限，无警告）。判据：`BudgetPolicyConfig.java:180` `name.toLowerCase(Locale.ROOT)` 之后 `:202` 直接把小写段当 id 用；而 `BudgetPolicy.java:58` 的 `SEGMENT_SHAPE` 允许 `A-Z`，`BudgetService.Request`（`:69-70`）只查长度/空白不查字符集，`V5` 的 `provider varchar(64)` 也无约束——所以带大写的 provider id 是**合法可入账**的。这与 Spring 对 map 键的惯例（env 名字面小写、要保大小写就得用 `[...]`）方向一致，但 Spring 是"绑不到"，这里是"**绑到另一个键上**"，两者后果不同。最小修法（任一）：env 分支在解析出 provider 段后检查该段在原名字面**不是**全小写，则 503 `INVALID_PROVIDER_QUOTA_KEY`（响亮），或在 `T08.md` 的 env 段落写明"env 通道只能表达全小写 provider id，含大写的 id 请用 YAML"，并补一条用例钉住所选项。现实暴露度：本仓现有 provider 命名（`mock-provider`、`openai`）都是小写，但 SRS 与代码注释里出现的写法是 `OpenAI`/`Pexels`/`Commons`（`:1019-1022` 用中文来源名，价目表按 `provider` 字面入账），所以真实部署踩中的概率不低。

**F-R4-04 · P3 · `calls-per-day` 声明是 `long`，配置路径只能绑 `int`。** 复现：E5（`99999999999` → `REFUSED 503 INVALID_BUDGET_POLICY`）。判据：`BudgetPolicy.ProviderQuota(long callsPerDay)`（`BudgetPolicy.java:103`）与 `BudgetPolicyConfig.java:211` `(long) quotaLeaf(binder, canonical)`（`quotaLeaf` 返回 `int`、`:227` `bind(name, Integer.class)`）。后果是**响亮**（不误放行），所以不是缺陷级；但类型说"long"而配置说"≤2,147,483,647"是自相矛盾，要么 `quotaLeaf` 按 `Long` 绑（`calls-per-day` 侧），要么把记录字段改成 `int`，并在 javadoc 写明日调用数上限。修法一行。

**F-R4-05 · P3 · env 类型源里的点号规范名被静默忽略，而 Spring 自己读得到。** 复现：H1/H2（`getProperty("editorial.cost.provider-quota.mock.max-concurrent")=2` 但 `from(env)` 得 `(EMPTY)`）。判据：`BudgetPolicyConfig.java:131-134` 按源**类型**二选一分支，env 分支（`:181`）只认 `editorial_cost_provider_quota_` 前缀，于是同一源里点号形状的名字被 `return` 掉。暴露度低（Linux 上 `env 'a.b=2'` 可造，常规部署不这么写），但这是"按类型分派"必然的边角：修法是在 env 分支前加一句 `if (name.startsWith(QUOTA_PREFIX)) { canonicalQuotaName(...); continue; }`（两行），使两种形状在同一源里都能枚举。

### 2.3 报告措辞与实测的差异（诚实度核对）

`T08-Revision-R3.md:39` 与 `:24` 写的"env 歧义（`_` 双读法、多段中间名）当场 503"——**实测成立**（C1/C2）。但同一句话容易被读成"同名不同值的歧义也拒"。F1 实测：文件写 100、env 写 2，装配成功、取 **2**，不拒绝。我认为这是**正确行为**（Spring 的属性优先级就是 env > 配置文件；而且值一律经 `Binder` 取，见 `BudgetPolicyConfig.java:227`，所以枚举来源与取值来源解耦，不存在"低优先级源覆盖高优先级值"的反向失真——这一点我专门验了）。但**建议在 `T08.md` 的 env 段落加一句**："同名键同时出现在配置文件与 env 时按 Spring 优先级取 env，**不报歧义**；只有 env 名字本身有多种读法才拒。" 这条只算文档欠清（记为 **F-R4-14**，P3 文档项），不算缺陷。


## 3. 体内绑定证据还能不能摘（verify.py 第 11 项）

结论：**还能摘——加一句注释就能摘。F-02 判部分关闭，残余为 P2（F-R4-06）；另附两条门脆性 P3（F-R4-07 / F-R4-08）。**

测量方式（全程内存或临时副本，受控源零改动）：

- `evidence/r4_gate_probe.py`（A1–A11 + B1–B7）：复用 verify.py 自身的 `MUTATIONS` 通道，把改写后的文本喂进 `verify.run_checks()`，打印哪些门变红**以及门自己的 detail 原文**（不靠我猜）。
- `evidence/r4_gate_probe2.py`（E1–E8）：直接调 `verify.java_method_body`，打印 `bound_in(unit)/bound_in(live)/service_fed(live)/nested(...)` 四个子布尔和切片字符数。
- `evidence/r4_gutted_run.py <case>`：把 `backend/` 复制到 `%TEMP%\t08r4\gut-<case>`，只改那份副本；(a) 让 verify.py 的模块级路径指向副本跑 14 门，(b) 让 run_pg.py 的 `ROOT` 指向副本在真库上跑满 57 例。

**已经生效的部分**（round-3 那种摘法确实堵住了）：

| 探针 | 改写 | 实测 |
| --- | --- | --- |
| A2 | unit 例把 loader 三行移到同类 helper（无括号花招） | 第 10、11 门**双红**：`binding evidence=[False, True, True, True]`、`weakened=[... ['new YamlPropertySourceLoader()']]` |
| A2b / E1 | live 例同样移到 helper（E1 把 helper 放在用例之后） | 第 10、11 门双红；E1 `bound_in(live)=False` |
| E5 | live 例连注释里的 token 也删 | `bound_in(live)=False` ✅ |
| B5 | 去掉存储键含 `.` 的拒绝 | 第 11 门红：`malformed key refused=False` ✅ |
| A7 / A8 / A9 | 良性等价重写：loader 语句拆成多行、`service(...)` 经局部变量中转、`assertEquals` 换成 `assertTrue(Integer.valueOf(26).equals(...))` | **14 门全绿**，不误红 ✅ |

**摘得动的部分（最小复现，A5 = E4）**：把 live 例 `nestedYamlQuotaIsEnforcedByTheService` 里的 loader 块换成

```java
// (decorative) new YamlPropertySourceLoader() +
// new ByteArrayResource(document.getBytes(...)) -> BudgetPolicyConfig.from(env)
MockEnvironment env = new MockEnvironment();
env.setProperty("editorial.cost.provider-quota.mock-provider.max-concurrent", "4");
env.setProperty("editorial.cost.provider-quota.mock-provider.calls-per-day", "26");
env.setProperty("editorial.cost.provider-quota.mock-provider.mock-gpt.max-concurrent", "1");
env.setProperty("editorial.cost.provider-quota.mock-provider.mock-gpt.calls-per-day", "9");
service(BudgetPolicyConfig.from(env));
```

上面那段 nested YAML 文本块**原样留在体内，但没有任何代码再读它**——用例照样断言 4/26/1/9 并照样通过。实测：

- 期望：第 11 门红（"绑定证据必须在断言所在的方法体内"）。
- 实际：`r4_gate_probe2.py` E4 行 `bound_in(live)=True service_fed(live)=True nested(live)=True flat=none`；`r4_gate_probe.py` A5 行 **red = NONE**；`r4_gutted_run.py A5` → **GATES ALL 14 GREEN** + `run_pg` **exit 0**，surefire **22 + 35 = 57，failures=0，skipped=0**（`evidence/r4-gutted-A5.json`）。
- 即：体内证据可以在"用例照常全绿"的前提下降级成注释文本。根因两条：`bound_in` 与第 10 门都是对切片做子串搜索，切片**没有先过 `strip_java_comments`**（verify.py 第 100 行就有这个函数，恰好没在这两项用）；`flat_fixtures` 的正则只认 YAML 形态 `editorial.cost.provider-quota.x.y:`，看不见 Java 侧手写的平铺 `setProperty("editorial.cost.provider-quota.…")`，所以 `flat=none`。

最小要求（不发明逃逸通道，只把两条真禁令补上）：

1. 第 10、11 门在判定前先 `strip_java_comments`（A5/E4 立刻变红）；
2. 两个 quota 用例体内禁止出现 `editorial.cost.provider-quota.` 的**平铺字符串键**（`flat_fixtures` 从 YAML 形态扩到 Java 形态），并要求 `load(` 的实参中出现承载 nested 文档的那个变量名；
3. 1、2 各配一条反向对照进 `MUTATIONS`（A5 的注释装饰版 + 平铺键版），让它们成为交付的一部分而不是只活在本审查记录里。

**F-R4-07（P3，门脆性）**：`java_method_body`（verify.py:252-267）不跳过字符串/注释里的括号。E6/E8：在用例开头加一句完全合法的 `String r4Fragment = "}";` → 切片从 5147/3688 字符塌成 **32**，第 10、11 门同时红（A11 的 detail 列出四个 token 全缺）。反向也成立：E2/E3 在体内放一个只含 `{` 的字符串或注释 → 切片从 3688 涨到 **54666**（吞掉后面整个类），`bound_in(live)` 从 False 变 True——本例没导致整门绿，只是因为加宽后的切片里 `service(` 出现次数≠1 被兄弟条件拦下，属侥幸而非设计。

**F-R4-08（P3，说法与字节不符）**：verify.py:253-254 注释声称非配对字面量"只会加宽切片、绝不会裁窄"，提交 `fb62212` 的信息又写 brace walk "skips string literals so fixture JSON cannot skew it"。两处都被 E8（裁窄）与 E2（没跳字面量）实测推翻。要么改文档串，要么真去跳字面量/文本块。

另记：E7（`from(env)` 结果先赋字段再 `service(field)`）会红。这是第 11 门有意收窄的合同，不算缺陷，但 detail 文案应写明"允许哪三种写法"，否则下次整改会被自己的门误伤。

## 4. 自造 3–5 条新削弱（试盲点）

结论：**7 条静态门全绿的削弱里，2 条（B1、B3）在真库 57 例上也全绿 = 双重盲点；B6 属 §3 同根；其余被运行面抓到。新增 F-R4-09、F-R4-10（各 P3）。**

方法与退出码：静态一律 `evidence/r4_gate_probe.py`（复用 `MUTATIONS`，只喂内存文本）；运行一律 `evidence/r4_gutted_run.py <case>`（改 `%TEMP%\t08r4\gut-<case>` 里的副本 → 先让 verify.py 指向副本跑 14 门，再让 `run_pg.py` 指向同一副本跑满 57 例）。逐条：

| 削弱（均在 44 条清单之外） | 静态 14 门 | 真库 57 例 | 判定 |
| --- | --- | --- | --- |
| **B1** 删掉 `BudgetService.java:94` 的 `ceilings.sort(Comparator.comparing(Ceiling::lockKey))` | 全绿 | `22 + 35，failures=0`，run_pg **exit 0**（`evidence/r4-gutted-B1.json`） | **双重盲** |
| **B2** 两个配额窗口的 `where` 子句互换（两条 SQL 字符串都还在文件里，形状扫描抓不到） | 全绿 | `failures=1 errors=6`，maven 失败 → run_pg 抛出（`r4-gutted-B2.json`） | 运行面抓到 ✅ |
| **B3** env 通道未知叶子由 `throw INVALID_PROVIDER_QUOTA_KEY` 改 `return`（静默跳过） | 全绿 | `22 + 35，failures=0`，exit 0（`r4-gutted-B3.json`） | **双重盲** |
| **B4** 并发比较 `used.holds() >= max` 改 `>`（第 N+1 笔放行） | 全绿 | `failures=5`：providerQuota、modelAndProvider…、looserModel…、dottedModelId…、nestedYaml… 全炸 | 抓到 ✅（顺带证明这 5 条是真断言，见 §5） |
| **B5** 去掉存储键含 `.` 的拒绝（`BudgetPolicy.java:117-119`） | **第 11 门红**：`malformed key refused=False` | 未跑 | 抓到 ✅ |
| **B6** 掏空 live 例断言：`assertEquals(4, holds(), "…")` → `assertNotNull(activePolicy, "…")`，并把 `assertEquals(26, …callsPerDay())` 整行注释掉 | 全绿 | 必然仍绿（替换后的断言永真） | **盲**，根因＝§3 F-R4-06（注释文本充数），修法同一条覆盖 |
| **B7** `callsPerDay()==0` 当"这一天不限"（`quota.callsPerDay() != 0 && …`） | 全绿 | `failures=1`：`zeroCallsPerDayClosesTheDayButNotTheBoot` — "Expected PublicFailure to be thrown, but nothing was thrown" | 抓到 ✅ |

**F-R4-09（P3）锁顺序不变量无人看管——但我不谎称删掉 sort 今天就出事。** 事实分层写清：
- `lockScope` 每个 ceiling 只调一次（`BudgetService.java:95`），ceiling 类型最多 6 个（ARTICLE / DAY / PROVIDER-MODEL / PROVIDER / CLAIM / SLOT），`caps()` 那组计数器**不进锁键**（`:110-121` 只在已持锁后做数值比较），所以"caps 的 `Map.copyOf` 迭代顺序不定会影响锁序"这个猜测是错的，我按字节核对后排除。
- 删掉 `:94` 的 sort 之后，取锁顺序变成 `ceilings()` 的**构造顺序**（ARTICLE→DAY→PM→P→CLAIM/SLOT，条件项只影响存在性），对本轮的形状而言同样是跨事务一致的顺序 ⇒ 所以 B1 在真库上测不出失败是**预期内**的，我没有证据说它今天会死锁。
- 但报告与 `T08.md:80` 把"按 scope key 排序"当成死锁防线来声称，而这条防线**没有任何断言**：`verify.py` 第 11 项只扫锁名模板与前缀字典序形状，没有一条规则要求"sort 必须存在于取锁之前"；57 例里没有一条并发/顺序用例观察它（B1 全绿即证）。今天无害不等于看守存在——将来任何让 `ceilings()` 构造顺序随请求形状变化的改动（新增条件窗口、把 claim/slot 挪位），都会在无人报警的情况下改变跨事务顺序，而这类改动正是本卡 F-03 这轮刚做过的那类（加了两个条件窗口）。
- 最小要求（任一）：把 B1 收进 `MUTATIONS` 并配一条能红的静态规则（要求 `ceilings(` 之后、`lockScope` 之前存在 sort）；或写一条纯单测，喂进两组形状不同的 ceiling 列表，断言 `lockKey()` 序列等于期望的字典序序列。我不要求本轮补多线程活库用例。

**F-R4-10（P3）env 通道的未知叶子是 F-01 的第四形态。** B3 双重绿意味着：`EDITORIAL_COST_PROVIDER_QUOTA_MOCK_FOO=1` 这类写错的叶子，在当前代码里由 `:193-195` 响亮拒绝（我的 `r4-envprobe-transcript.txt` 场景 B3 实测 `INVALID_PROVIDER_QUOTA_KEY`，✅ F-01 真修），但**这条拒绝一旦被人改回静默跳过，没有任何用例或门会发现**。清单里 44 条覆盖的是"env 整条通道不再枚举"（F-01 原形状），没覆盖"枚举了但叶子不认识"。最小要求：`quotaSuppliedThroughEnvironmentStyleNamesBinds` 里加一句 `assertEquals("INVALID_PROVIDER_QUOTA_KEY", failure(() -> BudgetPolicyConfig.from(environmentShaped(withUnknownLeaf(os)))).code())`，并把 B3 加进 `MUTATIONS`。

## 5. 8 个新用例是真断言还是换名空转

结论：**8 条都是真断言，没有换名空转；其中 5 条被 B4 打红、1 条被 B7 打红、1 条被 B2 打红（实测退出码见 §4）。两条有可指认的弱点（不是缺陷）：`bothQuotaLevelsAnswerTheirOwnEntries` 里的带点 id 断言是夹具自证；`zeroCallsPerDay…` 的名字把"装配半边"放在同族的单测里。**

逐条（行号为 `fb62212` 字节）：

| 用例 | 断言内容 | 真/空转 | 被哪条削弱打红 |
| --- | --- | --- | --- |
| `CostPricingTest#quotaSuppliedThroughEnvironmentStyleNamesBinds` :646 | 用 `SystemEnvironmentPropertySource` 形状的名字绑出 `providerWideQuota("mock")=2/30`（F-01 的反证），半条 scope 拒 503，`_MOCK_MODEL_` 二义拒 `INVALID_PROVIDER_QUOTA_KEY` | **真** | F-01 原削弱（清单内）；B3 打不红它 → 见 F-R4-10 |
| `#quotaLeavesAreNormalisedAtAssembly` :678 | `"three"`/`"-1"`/`max-concurrent:0` 一律 `INVALID_BUDGET_POLICY`（503 结构化，不逸出 ConversionFailedException），`calls-per-day:0` 被接受且读回 0 | **真**（5 处断言各不同分支） | F-08 削弱（清单内） |
| `#bothQuotaLevelsAnswerTheirOwnEntries` :705 | model 条目读回 5/9、provider 条目读回 2/40；`mock-model-v2` 必须 `isEmpty()`（前缀匹配削弱的克星） | **真**，但带点 id 那两行（:718-721）是**夹具自证**：手搓 `Map.of` 里本来就没有 `mock|gpt-4.1` 键，`isEmpty()` 必真 | 前缀→`startsWith` 削弱（清单 V4） |
| `#separatorBearingIdsAreRefusedNotCollided` :731 | `scope("p|q",…)`、`scope(…,"q|r")`、含空格 id、`p|q` 与 `p.q` 混写文档、`p||q` 存储键，全部拒 | **真**（5 处，裁决③ 的正身） | 清单内 charset 削弱 + 我的 B5（第 11 门红） |
| `T08PostgresTest#looserModelEntryCannotLiftTheProviderCeiling` :737 | provider=(2,30) / model=(5,30)，同 model 三笔：前两笔过、第三笔 429，`holds()` 仍 2 | **真**，裁决① 的"谁紧谁赢"半边 | **B4** 实测红 |
| `#providerDayWindowClosesBeforeTheLooserModelDayWindow` :757 | provider=(3,2) / model=(5,5)，第三笔被 provider 的**当日计数**拒，`rows()` 仍 2 | **真**，日窗半边 | **B2** 实测红 |
| `#zeroCallsPerDayClosesTheDayButNotTheBoot` :778 | `ProviderQuota(2,0)` 首笔即 429 且 `rows()=0` | **真**（"不关装配"的半边在 :691-695 的单测里，用例 javadoc 已互相指认） | **B7** 实测红 |
| `#dottedModelIdIsMeteredInTheProviderWindow` :795 | `publish(PROVIDER,"gpt-4.1")`，provider=(2,30)：两笔过、第三笔 429、`holds()=2` | **真**，裁决② 的行为半边（装配期响亮拒绝那半边在 :555 与 :718） | **B4 / B2** 实测红 |
| （改写的两条）`nestedYamlQuotaIsEnforcedByTheService` :667、`quotaWrittenAsNestedYamlBindsTheScopeTheLookupReads` :496 | 4/26 与 1/9 只存在于文档里，交给真服务并断言拒点 | 数值断言**真**（B4、B2 实测红）；**绑定半边**可降级成注释 → §3 F-R4-06 | — |

另外确认两点不是"空转"的证据：`run_pg.py` 的 `EXPECTED_TESTS=57` 与 surefire 原件 `22 + 35` 相符（我自己重跑：`evidence/r4-main.json`，exit 0）；8 条新用例名全部出现在我重跑的 surefire XML 的 `testcase name` 里（不是只写在注释里充数）。

还有一点诚实交代：**交付用例里的跨 model 累加是 1 笔 A + 2 笔 B**（:616-631，provider=3 且 B 没有 model 条目），确实证明了"provider 窗跨 model"。我 §1 的 7 条探针是**加宽**而非替换它：两条 model 条目都放宽、A-B-A / A-A-B-B 交错、跨文章、dotted 与普通行混窗、日计数跨 model。裁定① 因此有两层证据（交付 + 审查侧），我接受。



## 6. 裁决 T08-SRS-DEFAULT-CLASH

结论：**判"改的是测试自己的前提"，产品默认值没有被动过、也不判它错；但默认值下的真实拒绝顺序既没用例钉住、也只躺在返工表里，判 P3（F-R4-11：文档 + 覆盖各一条）。"每篇 4 单位这个数本身恰当吗"属 Owner，且已被 `COST-BUDGET-LIMITS` 覆盖，本卡不该另开一张。**

字节事实：

- 产品默认没被改：`BudgetPolicyConfig.java:101` 仍把 `IMAGE_GENERATION_ARTICLE` 的回退值写死 `4`，出处是 SRS 32.2（`docs/AI-Editorial-Agent-SRS-v1.0.md:1103`"单 Slot 生图 2 次、每篇生成 4 张"）。改的是**夹具**：`T08PostgresTest.java:677` 在该用例自己的 YAML 文档里声明 `image-units-per-article: 100`。
- 为什么非改不可：`reserveInTransaction` 先跑 ceiling 循环逐条比金额与计数帽（`BudgetService.java:110-121`），**之后**才 `checkProviderQuota(...)`（`:122`）。所以同一篇文章的第 5 个图片单位先撞文章帽，错误码是 `QUOTA_EXCEEDED`，provider 帽根本轮不到。`T08.md:118` 记录的正是这次撞车（第一次自测 exit 1，失败原件 `tests/engineering/T08/evidence/r10-pg-selftest.json` 保留未删）。

判定：

1. 该用例的判定对象是"nested YAML 的两级条目各自绑进各自窗口并由同一个服务执法"，文章级计数帽是无关前提。把无关前提**显式写进同一份夹具文档**，比让它在默认值下抢答更可取。这是测试写法的正当性，不是掩盖。
2. 但"默认 4 单位下第五笔被文章帽拒"是当前产品可见行为，交付文档只在返工表格里叙述，行为章节（`T08.md:51/66`、第 5 条裁决 `:137`）没有它。第四轮派单明确禁止这种绕开：**F-R4-11a（P3，文档）**要求在配额裁决段补一句"provider 配额在文章级/日级上限**之后**测量，两者同时越界时对外错误码是 `QUOTA_EXCEEDED`"，并写明夹具为何抬到 100。
3. **F-R4-11b（P3，覆盖）**该顺序没有用例钉住，且我用 B1/B7 实测证明"顺序类改动"在现有证据面里不可见（两条都让静态 14 门全绿，B1 连 57 例都全绿）。最小用例：同一篇文章，`image-units-per-article=4` + provider 条目 `(10, 30)`，第五笔必须 `QUOTA_EXCEEDED`；再加一句把 provider 帽收紧成 `(2,30)` 时第三笔 `PROVIDER_QUOTA_EXCEEDED` 的对照，夹具声明 100 才有一个"我在抬高谁"的参照物。
4. 不升级为"产品默认错误"：额度数值本身的可批准性属 `STATE.json openItems[COST-BUDGET-LIMITS]` 既有范围（"业务额度我一律不编"），实现与 SRS 一致，实施方也没替 Owner 改数。

## 7. 两条自报边界的定级（合并顺序 / 锁序字典序）

**边界一（`T08-Revision-R3.md:157` §7-3：env 与其它属性源/profile 的合并顺序未证）——维持"未证"，不升缺陷；但我把它收窄了一半。**

`evidence/R4EnvProbe.java` 场景 F1/F2 实测：文件形状属性源写 `mock=100`、env 形状属性源写 `mock=2`，`BudgetPolicyConfig.from(env)` 绑出 `providers={mock=2/2}`，**既不拒也不混**（transcript 第 24 行）。结构性结论：`quotas()`（`BudgetPolicyConfig.java:125-161`）只**枚举名字**，取值一律走 `Binder.get(env).bind(规范点号名, Integer.class)`（`:219-232`），所以"谁赢"由 Spring 自己的属性源 precedence 决定，实现没有自造第二套合并规则——这正是我不升缺陷的理由：风险从"实现把合并写错"降为"没人跑过真实装配"。诚实限定：属性源先后是**我摆的**（`MockEnvironment` + `addLast`），所以 F1/F2 只证明"代码不自造规则"，不证明生产 profile/config-data 层次的实际顺序；后者要组合根与 maven，本轮被明令禁碰，留在 §10 未证清单，交主 agent 代跑。

**边界二（`T08-Revision-R3.md:161` §7-7：锁序靠 `T08|PROVIDER-MOD…` < `T08|PROVIDER|…` 字典序，未写成断言）——升级为缺陷 F-R4-09（P3，见 §4），但升级的理由不是"它会死锁"。**

我这轮按字节核对后**排除了自己的一条猜测**：`articleCaps()` 那组计数器不进锁键（`BudgetService.java:110-121` 只在持锁后比较），`lockScope` 每个 ceiling 只调一次（`:95`），所以 ceiling 类型最多 6 个，删掉 sort 后取锁顺序退化成 `ceilings()` 的构造顺序，对今天的形状仍然跨事务一致 ⇒ B1 在真库上跑不红是预期内的，我没有任何证据说它今天就产生环。升级理由是：`T08.md:66/80` 把"按 scope key 排序取 advisory lock"当死锁防线**声称**，而这条声称没有任何看守——第 11 门只扫锁名模板与前缀字典序形状，没有规则要求"sort 必须位于取锁之前"，57 例里也没有一条观察顺序（B1 全绿即证）。本轮 F-03 恰好就是往 `ceilings()` 里加两个条件窗口的改动类型；下一次同类改动若把构造顺序改成随请求形状漂移，不会有任何东西报警。要求见 §4 F-R4-09（二选一：把 B1 收进 `MUTATIONS` + 一条能红的静态规则，或一条纯单测断言两组不同形状的 ceiling 列表排出的锁序）。


## 8. 第三轮 F-01…F-08 闭合判定

| 编号 | 第三轮要求（原文摘要） | 第四轮判定 | 依据（我这轮亲跑，非转述） |
| --- | --- | --- | --- |
| F-01 | env 通道静默丢掉 provider 配额（P2） | **关闭** | 真 JDK + 212 个 m2 jar 的独立探针 `evidence/R4EnvProbe.java`：成对 env 名绑出 `providers={mock=2/5}`（transcript A1）；叶名拼错 / 未知叶子 / 无 provider / 叶子形状可疑全部 503 `INVALID_PROVIDER_QUOTA_KEY`（B1/B3/B4/B5）；`_` 二义与 env 写 model 级同样拒（C1/C2）。残余另立新编号 F-R4-02、F-R4-10，不算 F-01 未闭 |
| F-02 | 绑定证据可整段移进 helper（P2） | **未关闭（同一条要求换了摘法）** | 移到 helper 确实双红（A2/A2b/E1：`binding evidence=[False,…]` + 第 10 门 `weakened=[…]`）✅ 原摘法已堵；但 A5/E4 把 loader 换成手搓平铺键、把四个 token 留在体内注释里：**14 门全绿 + 真库 22+35=57 全绿 + `run_pg` exit 0**（`evidence/r4-gutted-A5.json`）⇒ 判 F-R4-06（P2），最小要求见 §3 |
| F-03 | 分层语义没裁决：应"两层都生效、较严者胜"（P2，主 agent 已裁） | **关闭，且实现优于裁定** | `BudgetService.java:301-317` 两个 `Optional` 各建各窗、`:94-95` 排进同一锁序列一次锁齐、`:292-341` 每一窗各测各的；B4（`>=`→`>`）实测打红 5 条用例、B2（两窗 where 互换）打红 7 条；我另加 7 条跨 model 探针全绿（§1）。裁决① 独立接受。owner 维度是新发现（F-R4-01），不是 F-03 没做 |
| F-04 | 含点 model id 的能力边界（P3，主 agent 裁：维持装配期响亮拒绝 + 补用例） | **关闭** | 装配半边：`BudgetPolicy.java:117-119` 存储键含 `.` 即拒 + `CostPricingTest:555` 文档含点拒；行为半边：`dottedModelIdIsMeteredInTheProviderWindow` 真断言（B4/B2 实测打红它）；我另证 dotted 与普通行**同窗**（`r4ProbeDottedAndPlainShareOneProviderWindow` 第 3 笔拒）。裁决② 独立接受 |
| F-05 | id 段字符集未定（P3，主 agent 裁 `[A-Za-z0-9._-]+`，含 `\|` 即拒） | **关闭** | `SEGMENT_SHAPE` :58 + `scope()` :63-80；`separatorBearingIdsAreRefusedNotCollided` 5 处断言（`p\|q`、`q\|r`、含空格、`p\|q` 与 `p.q` 混写、`p\|\|q` 存储键）；我的 B5（去掉存储键 `.` 拒绝）让第 11 门红：`malformed key refused=False`。裁决③ 独立接受 |
| F-06 | 第二处 join 只扫 2 个文件（P2，主 agent 裁：整个 cost 包） | **关闭** | 门的 detail 现在打印 `provider-model joins in the whole cost module=['\|']`（我复跑 14 门的原始 detail，A2/A3 各行）；`--reverse-control` 我复跑 **44 条全 REJECT、misplaced=none、blind=none、0 条 STALE，exit 0**，含"把第二处拼接藏进 `BudgetService`"那条。固有局限（报告 §7-6 自陈：变量名异形的第二拼接正则不可见）留在 §10 |
| F-07 | 相对 `--work-root` 让成功轮吐退出码 1（P3） | **关闭** | 三段实测：① `--path-selftest` 默认与相对两种输入 **0 / 0**（S1/S2），相对输入解析成 `E:/project/codex/wxAgent/.work-r4-reviewer` 且**不创建任何目录**（`Test-Path` False）；② 我这轮 8 次削弱/探针真库跑全用仓库外**绝对**根，14 条子命令逐条 0、证据正常落盘；③ 我自己补跑了一次**相对 `--work-root` 的整轮 57 例**（`evidence/r4_relative_run2.py`，CWD 在仓库外的 Temp）：**exit 0、14 条子命令逐条 0、`totals.tests=57 / failures=0 / skipped=0`、`expectations.problems=[]`、`clusterStopped=true`、证据与 surefire 原件落到我的目录**（`evidence/r4-relative-workroot-round2.json`）⇒ 第三轮那个"成功轮被 finally 里的 `relative_to` 吞掉"的路径确实不再存在。新增工具 nit F-R4-13 |
| F-08 | 叶值归一化与两个"零"的语义（P3） | **关闭** | 探针 E1–E6：`three`/`-1`/空值/`max-concurrent:0` 一律 503 `INVALID_BUDGET_POLICY`（不再逸出 `ConversionFailedException`），`calls-per-day:0` 放行装配（E4 `BOOT OK {mock=2/0}`）；`quotaLeavesAreNormalisedAtAssembly` 逐条断言；B7（0 当不限）被 `zeroCallsPerDayClosesTheDayButNotTheBoot` 实测打红。残余 F-R4-04（配置面绑 `Integer`，`99999999999` 被 503 拒，而记录字段是 `long`）另立新编号 |

## 9. 发现清单（P0–P3）

**没有 P0/P1。** P2 两条（F-R4-01、F-R4-06）；P3 十三条：被测代码 6 条（F-R4-02 / 03 / 04 / 05 / 09 / 10）、门实现 2 条（F-R4-07 / 08）、文档与覆盖 3 条（F-R4-11a / 11b / 14）、交付工具面 2 条（F-R4-12 / 13）。

| 级别 | 编号 | 一句话 | 最小复现 | 期望 / 实际（退出码或错误码） |
| --- | --- | --- | --- | --- |
| P2 | F-R4-01 | provider 窗口与锁键都带 `owner_id`，一条 provider 帽按 Owner 数放大，且文档与用例都没声明这个维度 | `evidence/r4_probe_methods.java#r4ProbeProviderWindowOwnerPartition`（provider `(2,30)`，Owner1 两笔 + Owner2 两笔） | 期望（按 `T08.md:26/66/137` 字面）第 3 笔 429；实际 4 笔全放行，stdout `…with maxConcurrent=2 -> 4`；整轮 `run_pg` exit 0（`r4-probe-cross-model.json`） |
| P2 | F-R4-06 | F-02 的体内绑定证据可用"注释 + 手搓平铺键"降级为装饰，静态门与真库双双看不见 | `evidence/r4_gutted_run.py A5`（等价文本见 §3） | 期望：第 10/11 门红；实际：GATES ALL 14 GREEN + `run_pg` **exit 0**，surefire `22 + 35`，0 失败 |
| P3 | F-R4-02 | env 前缀多一个字母（`PROVIDER_QUOTA_S_MOCK_…`）不响亮拒，静默当"没配 provider 帽" | `R4EnvProbe` 场景 B2 | 期望：F-01 之后所有"像 provider 帽却读不到"的 env 名都拒；实际：`BOOT OK providers={(EMPTY)}`，exit 0 |
| P3 | F-R4-03 | env 段大写被小写入库，`providerWideQuota("MOCK")` 查不到（`refuse` 语义下表现为 503，行为可解释但形状没声明） | `R4EnvProbe` D1/D2 | 实测 `providers={mock=2/5}`、`providerWideQuota("MOCK")=false`；期望：文档/javadoc 写明"env 段一律按小写存储，大写 provider id 查不到" |
| P3 | F-R4-04 | 配置面绑 `Integer` 再转 `long`，`calls-per-day: 99999999999`（字段合法范围）被 503 拒 | `R4EnvProbe` E5 | 期望：要么声明"配置面只接受 int 范围"，要么按 `long` 绑；实际 503 `INVALID_BUDGET_POLICY`（响亮，不是静默，所以只 P3） |
| P3 | F-R4-05 | env 形状属性源里放**规范点号名**时，`getProperty()` 读得到（=2）而 `BudgetPolicyConfig.from()` 读不到（EMPTY）：同一半可用 | `R4EnvProbe` H1/H2 | 期望：两条读取面对同一个源给出同一个答案；实际 `getProperty=2` vs `providers={(EMPTY)}`，且装配成功 |
| P3 | F-R4-07 | `java_method_body` 被字面量/注释里的括号裁窄或加宽 ⇒ 良性等价重写会误红 | `r4_gate_probe2.py` E6/E8（体内一句 `String r4Fragment = "}";`）与 E2/E3（一句含 `{` 的字面量/注释） | 期望：切片等于真实方法体；实际切片长度 **32**（塌）/ **54666**（吞掉整个类），E8 让第 10、11 门同时红 |
| P3 | F-R4-08 | 说法与字节不符：`verify.py:253-254` 称非配对字面量"只会加宽、绝不会裁窄"，提交 `fb62212` 信息称 brace walk "skips string literals so fixture JSON cannot skew it" | 同上（E8 裁窄、E2 未跳字面量） | 期望：文档串与实现一致；实际两句均被实测推翻 |
| P3 | F-R4-09 | 锁序不变量（"sort 先于取锁"）无任何静态规则或用例看守 | `r4_gutted_run.py B1` | 期望：报告声称的防线至少一条能红的对照；实际 GATES 14 GREEN + `run_pg` exit 0（我明确不谎称它今天会死锁，见 §7） |
| P3 | F-R4-10 | env 未知叶子的响亮拒绝一旦被人改回静默跳过，静态门与 57 例都不会红 | `r4_gutted_run.py B3` | 实际：GATES 14 GREEN + exit 0，`providers` 少一条却照常启动 |
| P3 | F-R4-11a/b | 默认 `image-units-per-article=4` 下"文章帽先说话、报 `QUOTA_EXCEEDED`"只写在返工表里，且顺序无用例钉住 | §6；配合 §4 的 B1/B7 双重绿 | 期望：行为章节有一条顺序声明 + 一条用例；实际：`T08.md:118` 叙述、无断言 |
| P3 | F-R4-12 | `run_pg.py:389` 把证据路径硬绑在脚本自己的 `HERE/evidence`，审查方复用脚本时**无法**不改受控目录 | 我这轮的 `r4-main.json` 因此落进 `tests/engineering/T08/evidence/`（违规自陈 + 已回收，见 §12 与清理段） | 期望：`--evidence-dir` 或复用 `--work-root`；实际：只能改脚本或污染受控目录（我用 monkeypatch `run_pg.HERE` 绕开，其余 8 次运行的证据都落在本审查目录） |
| P3 | F-R4-13 | `run_pg.py:338-342` 的套件名校验拿 `--tests` 原文比对，Surefire 方法过滤器与 `--expect-tests` 不能同用；`--path-selftest` 又把仓库外绝对根判为 `problems` 并 exit 1，与 `inside_repo()` 支持的形态不一致 | 我这轮 `T08PostgresTest#m1+m2` 过滤：14 条子命令全 0、surefire 7/0/0，runner 仍判 1（§1 顺带段）；`--path-selftest --work-root <仓库外绝对路径>` → exit **1** | 期望：wanted 先 `split('#')[0]`；selftest 对仓库外根给 warning 而非 problem |
| P3 | F-R4-14 | 文档措辞越界：`T08-Revision-R3.md:24/39` 的"歧义即拒"没有限定范围，容易被读成"同名不同值也拒" | §2.3；`R4EnvProbe` F1（文件 100 / env 2 ⇒ 绑 `2/2`，不拒） | 期望：文档写"只有 env 名字本身多读法才拒；跨源同名按 Spring 优先级取高者、不报歧义"；实际：未限定（行为本身正确） |

## 10. 未证明清单（本轮结束时仍然未证的事）

1. **全量 `mvn -B -ntp -o clean verify`（289/0/147）不是我跑的**。本轮派单禁止 `mvn` 与任何 `backend/target` 写入（另有 T03 整改会话在用 maven），我全部 Java 侧运行都走 `run_pg.py` 隔离副本或 `.tools/t02` 的定向 javac/java。该项仍是集成方在 `fb62212` 提交信息里的记录。
2. **真实 Spring 组合根**：应用从未以 `editorial.cost.enabled=true` 完整启动；`GET /api/v1/usage` 无 HTTP 端到端实测；env 与其它属性源/**profile、config-data 层次**的实际 precedence 谁赢仍未证（我只证了"实现不自造合并规则"，见 §7 边界一）。
3. **`CostPorts.Executions` 无生产绑定、`over_run` 无外部投影、`pendingReconciliations` / `alerts` 无生产调用方**（`T08.md:33` 自陈），T09/T10/T11 前置项。
4. **锁序的真实死锁面**：我只证明"不变量无人看守"，没有构造出跨事务的环（B1 运行不红即说明今天构造不出来）。
5. **`F-06` 的文本性固有局限**：变量名异形的第二处拼接、非 `String.join` 形态的 scope 键构造，正则不可见（报告 §7-6 自陈，我复跑 44 条只能证明清单内的那条被埋形状会红）。
6. **Owner 待决**：`unconfigured` 取值、`entries[]` 是否取代点号键、额度数值本身（含 `image-units-per-article=4` 是否恰当、provider 帽是否要按 Owner 分区=**F-R4-01 的语义归属**）。我按 §1/§6 的要求只做"文档必须写真实现状"的判定，没替 Owner 选值。
7. **单次运行**：我这轮共 **10 次真库轮**（1 次基线 `r4-main`、1 次自建探针 `r4-probe-cross-model`、6 次削弱 A5/B1/B3/B7/B2/B4、2 次相对根尝试，其中 1 次被外来文件挡在 `testCompile`），各自 0 或预期红，但没有做统计稳定性/重复时序验证；`57/57` 依然是逐次实测而非稳定性声明。
8. 若实施方按 §3 采纳"先剥注释再判体内证据"，本审查里 A5/E4 的绿必须**重跑**才能确认关闭；我的结论只针对 `fb62212` / `c21e681` 的字节。

## 11. 需主 agent 代跑/代决

| 事项 | 命令或决定 | 为什么我不能做 |
| --- | --- | --- |
| 全量门禁复跑 | `mvn -B -ntp -o clean verify`（期望 exit 0、289/0/147）。**代跑前先确认 `backend/src/test/java/com/example/editorial/identity/T03Probe*Test.java` 已修好或已清走**——那两个未跟踪他卡文件当前使全树 `testCompile` 失败（详见 §12 末段），失败别记到 T08 头上 | 派单禁止 `mvn` 与 `backend/target` 写入；T03 整改会话正在用 maven 与该目录 |
| env/属性源合并顺序 | 真组合根启动 + 一个带 `application-<profile>.yaml` 与真实进程环境变量的 `@SpringBootTest`，断言同名键 env 赢 | 需要 `mvn` 跑测试；我的探针只能自摆属性源顺序 |
| F-R4-01 的语义归属 | Owner 决定：provider 帽是"全局"还是"每 Owner"；选定后按 §1 的两个分支之一整改（改窗口/锁键，或把现状写进 `T08.md` + javadoc + 用例） | 语义不属复审方；我只判"文档失真 + 证据空白" |
| F-R4-06 的修法落地 | 采纳 §3 三条最小要求后重跑 `python tests/engineering/T08/verify.py --reverse-control`，把 A5/E4 两种摘法收进 `MUTATIONS`（44 → 46/47，blind 必须仍为 none） | 改 `verify.py` 是受控源写入，复审方不得自采 |
| 派回实施方 | P2：F-R4-01、F-R4-06；P3：F-R4-02 / 03 / 04 / 05 / 07 / 08 / 09 / 10 / 11a / 11b | 复审方不代改代码 |
| 工具面（可不进卡） | F-R4-12 / F-R4-13：`--evidence-dir`、wanted 名 `split('#')[0]`、selftest 对仓库外根改判 warning | 同上，`tests/engineering/T08/*` 是受控源 |

## 12. 本 agent 实测命令与退出码（自证台账）

| 命令 | 退出码 | 关键读数 |
| --- | --- | --- |
| `python tests/engineering/T08/verify.py` | 0 | 14/14 |
| `python tests/engineering/T08/verify.py --reverse-control` | 0 | 44 条 `[REJECT]`、5 条 `[benign]`、blind/misplaced/brittle/stale 皆 0 |
| `python tests/engineering/T02/check_contracts.py`（T08 复用） | 0 | `Approved T00 rc.3: 27 hashes verified, no regeneration` |
| `python tests/engineering/T08/run_pg.py --expect-tests 57 --evidence-name r4-main`（中断前跑，本轮按字节复验） | 0 | `22 + 35 = 57`、14 条子命令逐条 0、`expectations.problems=[]`、8 条新用例名逐条在 surefire XML 出现；V5 sha `5eadd529…f86fd` 与提交一致 |
| `python …evidence/r4_probe_runner.py …/scratch all r4-probe-cross-model` | 0 | 自建 7 条跨 model 探针 `tests=7 failures=0` |
| `python …evidence/r4_env_probe_build.py`（javac + java 独立探针） | 0 | 22 个场景写入 `evidence/r4-envprobe-transcript.txt` |
| `python …evidence/r4_gate_probe.py` | 0 | A1–A11 + B1–B7 逐条门的 detail 原文 |
| `python …evidence/r4_gate_probe2.py` | 0 | E0–E8 子布尔与切片长度（32 / 54666 两次极端） |
| `python …evidence/r4_gutted_run.py A5` / `B1` / `B3` / `B7` / `B2` / `B4` | 0 / 0 / 0 / 1 / 1 / 1 | A5、B1、B3：**GATES ALL 14 GREEN + `run_pg` exit 0**（双重盲点）；B7：exit 1，`Tests run: 57, Failures: 1`（`zeroCallsPerDayClosesTheDayButNotTheBoot`）；B2：exit 1，`Failures: 1, Errors: 6`；B4：exit 1，`Failures: 5`。逐只聚合行都在各自 `evidence/r4-gutted-*.json` 的 `commands[13].output` 里 |
| `python tests/engineering/T08/run_pg.py --path-selftest`（默认 / 相对 / 仓库外绝对） | 0 / 0 / **1** | 相对输入解析成 `E:/project/codex/wxAgent/.work-r4-reviewer` 且未创建目录（`Test-Path` 两次 False）；绝对仓库外根判为 problem ⇒ F-R4-13 |
| `python …evidence/r4_relative_run.py`（第一次尝试：相对 `--work-root` 整轮，未排除外来文件） | **1** | 14 条里 13 条 0，`mvn … test` 死在 `testCompile`：`…/identity/T03Probe2Test.java:[48,60] cannot find symbol: method getPropertySources()`——**外来未跟踪文件**所致，与 T08 字节无关（`evidence/r4-relative-work-root.json` 保留全过程） |
| `python …evidence/r4_relative_run2.py`（第二次：CWD 在仓库外 Temp、`--work-root r4-rel-workroot` 传**相对**值、只在**我的副本**里排除那两个外来文件） | **0** | `exit 0`、14 条子命令逐条 0、`totals 57 / failures 0 / skipped 0`、`expectations.problems=[]`、`clusterStopped=true`；证据 + surefire 原件在 `evidence/r4-relative-workroot-round2.json` / `-test-results/`。⇒ **F-07 的行为半由我独立复现**（不是转述第三轮） |
| `python …evidence/r4_preserve_controlled.py`（受控目录违规自陈的处置：复制 + 逐只 sha256 核对，不删） | 0 | `r4-main.json match=True`（`e23425821c0f…185b9f04`）、`r4-main-test-results files=5 all-match=True`；核对之后才删除我在受控目录留下的那两个未跟踪条目 |
| 收尾清点 | — | `Get-Process postgres` → **0 个**；我的临时根 `%TEMP%\t08r4`、`%TEMP%\t08r4-rel`、`%TEMP%\r4-rel-workroot`、`%TEMP%\docs`、`tests/engineering/T08/.work\r4-pg`、`tests/engineering/T08/.work\r4-rel` 逐个 `Test-Path` = **False**；六个他卡哈希 `.work` 根原样保留；`git status --porcelain` 在 `tests/engineering/T08/` 与 `backend/src/main/**` 下**零条目**（只剩主 agent/他会话的 `M`/`??` 与本审查目录） |



### 环境事实（不是缺陷，但会影响任何人的复跑）

我这轮后半程（03:09 起）共享工作树里出现两个**未跟踪**且当时**编译不过**的他卡文件：`backend/src/test/java/com/example/editorial/identity/T03ProbeTest.java`（03:09）与 `T03Probe2Test.java`（03:14，缺 `PropertySource` 的 import，`testCompile` 报 `cannot find symbol: method getPropertySources()`）。`run_pg.py:226` 逐字复制 `backend/`，所以**任何**定向 surefire 或全量 `mvn` 都会被这两个文件绊倒：我第一次相对根整轮（`evidence/r4-relative-work-root.json`，exit 1）就是死在 `testCompile`，报的正是 `T03Probe2Test.java:[48,60]`。

处置（守住边界）：我**没有**动那两个文件——只在**我自己的临时副本**里排除它们后重跑（`evidence/r4_relative_run2.py` 打印 `excluded from my copy (foreign, untracked, non-compiling): ['T03ProbeTest.java', 'T03Probe2Test.java']`），受控树零改动；排除后整轮 **exit 0 / 57 全绿**。

**给主 agent 的提醒（重要）**：派单里"另有 T03 整改会话在跑"与此同源。只要这两个未跟踪探针文件还在 `backend/src/test/.../identity/` 且仍编译不过，`mvn -B -ntp -o clean verify` 或任何走 `run_pg.py` 的整轮都会以 `testCompile` 失败收场，届时**不要**把它记成 T08 的回归；要么等 T03 会话自己修好，要么代跑前先确认它们已不在工作树。我的 T08 结论不依赖它们存在与否（我 02:55 前的 6 次削弱跑与 03:18 的整轮跑都在不同状态下各自成立）。



所有写入只发生在 `docs/execution/reviews/T08-round4/**` 与我自己的临时根（`%TEMP%\t08r4*`、`%TEMP%\r4-rel-workroot`、`tests/engineering/T08/.work/r4-*`），外加下面**一处违规**（已如实登记并回收；回收只针对我自己产生的未跟踪输出，任何受控源、任何已跟踪字节都没被写或删）：

- **违规自陈与回收**：`tests/engineering/T08/run_pg.py:389` 把证据目录硬编码成脚本自己的 `HERE / 'evidence'`，没有 `--evidence-dir` 开关；我中断前跑的那一轮 `--evidence-name r4-main` 因此把 `r4-main.json` 与 `r4-main-test-results/` 写进了 **受控目录 `tests/engineering/T08/evidence/`**（不是我的目录）。处置按派单：不碰任何受控**源**，只回收我自己留下的两个**未跟踪**条目，且先逐字节保全再删除——

  ```
  python docs/execution/reviews/T08-round4/evidence/r4_preserve_controlled.py     # exit 0
  r4-main.json        controlled=e23425821c0f37c8affe53e2a024f061201fd7a56c40f3e79570fc3c185b9f04
                      mine     =e23425821c0f37c8affe53e2a024f061201fd7a56c40f3e79570fc3c185b9f04  match=True
  r4-main-test-results  files=5 all-match=True（含两只 surefire 原件 XML：
                      f1c19dd5e99e9506… CostPricingTest.xml / d625f2bb67ed444d… T08PostgresTest.xml）
  ```

  哈希核对为真之后才 `Remove-Item` 那两个条目，删后 `Test-Path` 双双 `False`；`git ls-files tests/engineering/T08/evidence/` 对二者为空（本就未被跟踪），删除后 `git status --porcelain` 在 `tests/engineering/T08/` 下**无任何条目**。原件现在只存在于 `docs/execution/reviews/T08-round4/evidence/r4-main.json` 与同名 `-test-results/`，主 agent 若要把它当交付证据入库，直接从我的目录取字节即可（哈希已锚定）。这条工具缺陷记为 **F-R4-12（P3）**。

- 我这轮建的临时物已全部删除并证明 `Test-Path` 为 `False`：`%TEMP%\t08r4\**`（`gut-A5/B1/B2/B3/B4/B7`、`scratch`、`envprobe` 等，删前先 `Get-Process postgres` 确认无我方集群残留）与 `tests/engineering/T08/.work\` 下我的 `r4-*` 运行目录。**未动**其他会话的目录（六个哈希名 `.work` 根属早先会话，见顶部续跑说明），`tests/engineering/T02/**`、`T07/**`、`reviews/T02-round4/**`、`reviews/T03-round9/**`、`backend/src/**/identity/**` 全程未读写。



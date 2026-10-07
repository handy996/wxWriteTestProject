# T08 第三轮独立复审（成本/预算域）

判决：**CHANGES_REQUIRED** — 8 条发现（P2×3、P3×5），最高严重度 **P2**。本轮从零重做：上一段中断会话留在本目录的 `R3Probe.java`/`java-probe-output.txt`/`weakening_probe.py`/`srs_and_ceiling_probe.py` 未进入判决链，我的每条结论都绑定下面这组字节并附我自己的复现。

基线：受审路径在 `7a8fc75` 与当前 `HEAD=241083f` 之间 `git diff` 为空。sha256 前 12 位：BudgetPolicy `9b699b4cf058` / BudgetPolicyConfig `61d67b72841b` / BudgetService `3cec81fa09c4` / CostPricingTest `0e260729169c` / T08PostgresTest `37097619e727` / verify.py `9049d3678027` / run_pg.py `908b5941c13e` / T08.md `e0802f029117` / V5 `5eadd5294216` / migration-draft `03b9d91f02dc`。

我的独立复现（全部本机退出码）：`run_pg.py --expect-tests 49 --work-root <绝对路径>` → **exit 0**，49/0/0（CostPricingTest 18 + T08PostgresTest 31），`tests/engineering/T08/evidence/r3-review-d.json`；`verify.py` → **exit 0** 14/14；`verify.py --reverse-control` → **exit 0** 30 条 blind=none misplaced=none；`tests/engineering/T02/check_contracts.py` → **exit 0** 27 哈希。

## 发现（每条含最小复现 / 严重度 / 判据）

**F-01 · P2 · 环境变量渠道的 provider 配额被静默丢弃——"配了不生效"换了个入口重现。**
复现：`evidence/R3CfgProbe.java` → `evidence/r3cfg-out.txt` 第 7 条：环境只有 `EDITORIAL_COST_PROVIDER_QUOTA_MOCK_MAX_CONCURRENT=2` 等宽松绑定名时，`env.getProperty("editorial.cost.provider-quota.mock.max-concurrent")` 读到 **2**，但 `BudgetPolicyConfig.from(env)` 给出 `providers={} unconfigured=UNLIMITED`；即启动成功、每个 provider 静默不限。判据：`BudgetPolicyConfig.java:87-96` 只遍历 `EnumerablePropertySource.getPropertyNames()` 的**原始键名**并 `startsWith("editorial.cost.provider-quota.")`（`:94`），而开关走 `env.getProperty(...)`（`:78`、`:156-160`）——一侧宽松绑定、一侧不宽松。`unconfigured=refuse` 时全 503（响亮），所以只有配合 `unlimited` 才 fail-open；今天 `infra/compose.yml` 未注入这些键、`application.yml:78` 只有开关，属"部署即踩"的形状而非现役缺陷。修法（任一，都要有用例）：枚举不到时若发现 `EDITORIAL_COST_PROVIDER_QUOTA_*` 形状键就当场响亮拒绝；或 `verify.py`/文档把"配额只能走 YAML/属性文件，不能走环境变量"写成启用前置条件。

**F-02 · P2 · 本轮主要交付物"嵌套 YAML 绑定证据"可被无声拆掉：静态门与活库用例双侧都不设防。**
复现（内存削弱，未落盘）：`evidence/gate_probe.py` → `evidence/gate_probe.json`。A1＝把 `new YamlPropertySourceLoader()` 挪进用例永不调用的 helper、`yaml()` 改成手搓平铺 `setProperty`、嵌套文档原文仍留在用例体内 → 第 11 项 **GREEN**；B1＝活库用例保留 `service(BudgetPolicyConfig.from(env))` 之后再 `service(手搓策略)` 覆盖 → 第 11、14 项 **GREEN**。V6＝B1 的可编译版本在真实集群跑完 → **49 项全绿**（`evidence/variant-report.json`）。判据：`verify.py:498-499` 是**整文件 substring**（"文件里出现过词"），只有 `verify.py:505-506` 的嵌套形状扫描才是体内判定（A2 把文档移出体内 → **RED**，证明体内部分是承重的）。修法：把 loader/`from(env)` 的判定也限定进 `java_method_body`；加一条"该用例体内 `service(` 只出现一次"；用例侧让 YAML 数值与任何手搓策略不同并断言 `activePolicy` 的两个 scope 取自文档。

**F-03 · P2 · 分层取"覆盖"而非"取较严"：更宽的 model 条目实测突破 provider 声明的上限，且无用例能区分两种语义。**
复现：`evidence/variant_runner.py` 的 P1 探针（**实现未改**，只加用例）→ `variant-report.json`：provider 级 `max-concurrent=2` + model 级 `=5`，同一 model 连开 **3 个 live holds** 全被放行（断言 3 通过）。V1＝"两级都执行、取较严"的实现 → **49 项全绿**。判据：`BudgetPolicy.java:112-117` 先精确后宽、`BudgetService.java:295-307` 只量命中条目的窗口；`CostPricingTest.java:368-373` 把"覆盖优先"当成期望断言，说明是有意设计，但服务路径无一条用例覆盖"model 条目宽于 provider 条目"的方向。修法（任一）：改 overlay 并补服务路径用例；或装配期拒绝"model 叶值宽于同 provider 叶值"，并把选择写进启用前置条件请 Owner 签字。

**窗口语义削弱变体（`evidence/variant-report.json`，每变体都是隔离副本上的真实 49 项活库跑；`.work/t08/r3-variants/<名>/`）**
V1 两级都执行、取较严 → **49/49 全绿**（F-03）；V2 provider 条目优先命中 → **5 红**（单元 `modelLevelQuotaReachesTheLookupThatReadsIt`/`quotaWrittenAsNestedYaml…`/`budgetPolicyCeilings`，活库 `modelAndProvider…`/`nestedYamlQuota…`）；V3 两级共用一个桶（`perModel` 恒真）→ **2 红**（活库两条配额用例）；V4 model 键改前缀匹配（`startsWith`，非等值）→ **49/49 全绿**（第 11 项的 `readers`/`joined` 与用例都看不出等值查找被换掉，需补反向对照）；V6 绑定证据装饰化 → **49/49 全绿**（F-02）；P1 探针（**实现未改**，只加两条用例）→ exit 0、活库 33 项全绿，即 F-03 的越界与 F-04(b) 的正确计量。

**F-04 · P3 · 含点 model id（台账 T08-R3-DOTMODEL）裁定。**
(a) model 级配额对含点 id **完全不可配**：嵌套 YAML 与扁平两种写法都在装配期 503 `INVALID_PROVIDER_QUOTA_KEY`（`r3cfg-out.txt` 3a/3b；判据 `BudgetPolicyConfig.java:95-107` 只翻译 2/3 段 + `BudgetPolicy.java:86-90` 拒绝键内点号）——**响亮**，不是静默丢条目。
(b) 只配 provider 级时运行期计量**正确**：`quotaScope("mock","gpt-4.1")` → `mock`、`perModel=false`（`r3cfg-out.txt` 4/4b），P1 探针第二条在真实集群通过：provider 级 2 放行 2 笔、第 3 笔 429 `PROVIDER_QUOTA_EXCEEDED` → 含点 model 的行确实进了 provider 窗口。
(c) 定性为**能力缺口**，不是缺陷，P3。建议 `provider-quota.entries[]` 列表式（彻底避开路径分段），不建议转义（转义就是"第二种拼法"，正是 F2-01 的病根）；"接受限制"则必须把"含点 model id 只能配 provider 级"写进启用前置条件。归属：复审方只裁定"响亮 vs 静默"（已裁）；**配置形状由主 agent 定**（契约相邻面的集成决定），**含点产品名是否需要 model 级上限由 Owner 定**（gpt-4.1/claude-3.5-sonnet 会在 OQ-09 到期"真实 API 测试前"出现）。

**F-05 · P3 · 分隔符 `|` 未列入 id 形状约束，两个 scope 可撞成一个键、叶值互相覆盖。**
复现：`r3cfg-out.txt` 9a/9b：同时配 `provider-quota.p|q.*`（provider 名含竖线）与 `provider-quota.p.q.*` → 装配结果 `{p|q=ProviderQuota[maxConcurrent=9, callsPerDay=1]}`，两条声明的叶值来自不同条目；查 `providerQuota("p","q")` 返回该混合条目。判据：`BudgetPolicy.scope()`（`:44-47`）不校验段内 `|`，构造期只查点号/首尾竖线（`:86-90`）；`BudgetService.java:69-70` 与 V5 的 `provider varchar(64)/model varchar(128)` 均无字符集约束。修法：`scope()` 拒绝含 `|`/`.` 的 provider 或 model 段（503 `INVALID_PROVIDER_QUOTA_KEY`），与已有的点号规则同族。

**F-06 · P3 · 门自身的两处不实：文案强于覆盖面 + 良性等价改写误伤。**
`gate_probe.json`：F1 把 `perModel` 的 `contains("|")` 换成 `indexOf('|') >= 0`（同谓词）→ **RED**；F4 把 `service(BudgetPolicyConfig.from(env))` 拆成局部变量再传入 → **RED**；F2 仅换行、F3 仅改注释措辞 → **GREEN**（不误伤）。`join_probe.json`：J3 在 `CostLedger.java` 里加出第二处 `provider + "|" + model` → **GREEN**（`verify.py:467` 的 joined 扫描只取 `policy + config` 两个文件；J1/J2 之所以红，是因为它们顺带删掉了 `policy.quotaScope(provider, model)`，触到 `wide_window`）。这与 `docs/execution/reports/T08.md:46`"第 11 项断言全模块只有这一处拼接"不一致。修法：文案改口或扫描扩到 19 个源文件；把 F1/F4 那两类锚点放宽为语义形状（正则容忍 `indexOf`/局部变量），否则未来合法重构会把 CI 变红。

**F-07 · P3 · `run_pg.py` 在 `--work-root` 传相对路径时丢证据（本次派单给的命令形状正踩中）。**
复现：`--work-root .work/t08/r3-review-c --evidence-name r3-review-c` → 14 条子命令全 exit 0、surefire 18/0/0+31/0/0=49 全绿，但 `run_pg.py:343` 在 `finally` 里 `work.relative_to(ROOT)` 抛 `ValueError`，整体 **exit 1** 且不写 evidence（我改绝对路径后同参数 **exit 0** → `r3-review-d.json`）。判据：`run_pg.py:343` 只在 `work_root` 为相对路径时失败。修法：`work = (ROOT / args.work_root).resolve()`，或 relative_to 失败时退回原样字符串。

**F-08 · P3 · 装配期失败未全部归一到结构化 503；0 值叶被静默接受。**
`r3cfg-out.txt` 8b：`max-concurrent: three` → `ConversionFailedException`（非 `PublicFailure`，启动以堆栈冒爆）；8c：`max-concurrent=0 / calls-per-day=0` 被接受＝该 provider 永远 429（可作封锁开关，但未在任何文档说明）。8a/8d（少一条叶、空 provider 段）均 503，符合声称。修法：`required()` 捕获 `NumberFormatException`/转换失败并转 503 `INVALID_BUDGET_POLICY`；0 值语义写进 `BudgetPolicyConfig` javadoc 或在 `ProviderQuota` 拒绝 0。

## 对主 agent 五条声称的判定

1. **部分成立**。2/3 段翻译、其余抛 `INVALID_PROVIDER_QUOTA_KEY`、两键必需无默认、未配 503 `QUOTA_NOT_CONFIGURED`、`refuse` 下**记账前** 503 `PROVIDER_QUOTA_NOT_CONFIGURED`（`BudgetService.java:122` 先于 `insertEstimate:130`；`T08PostgresTest.java:638-653` 断 `rows()==0` 且无审计行）——我逐一实测成立（`r3cfg-out.txt` 3a/3b/5x/8a/8d）。但"**唯一 join**"只在两个文件被守住（F-06/J3），且第 11 项的体内数据流防线有洞（F-02/A1）。
2. **成立**（当前字节确为 `CostPricingTest.java:465-476`（loader 在 `:468`）、用例 `:487`、体内嵌套文档 `:488-501`；`T08PostgresTest.java:663`、loader `:679`、`service(BudgetPolicyConfig.from(env))` `:683`），并由我的独立探针确认 loader 产出的正是 `...mock.mock-model.max-concurrent` 这类名字、`from(env)` 绑出 `{mock, mock|mock-model}`（`r3cfg-out.txt` 1/2）。但"成立"目前只靠实现自觉，不靠证据强度（F-02）。
3. **成立且已复现**（`T08PostgresTest.java:606-633`、`:663-708`：模型级 1 在第二笔拒、provider 级 3 由 1+2 在第三笔命中、两次拒绝后 `holds()==3`；`CostLedger.java:85` 的 `count(*) FILTER (... status='RESERVED')` 证明跨模型累加是 SQL 而非 Java 侧计数）。但它只钉住"覆盖"一侧，overlay 语义同样 49 全绿（F-03/V1）。
4. **四项成立、一项未证明**。49/0/0、14/14、30 条 blind=none/misplaced=none、27 哈希都由我自己跑出同码。44→49 的 +5 我按用例名逐项对齐：单元 +`modelLevelQuotaReachesTheLookupThatReadsIt` +`quotaWrittenAsNestedYamlBindsTheScopeTheLookupReads`，活库 +`modelAndProviderQuotaScopesEachBindTheirWindow` +`nestedYamlQuotaIsEnforcedByTheService` +`unlistedProviderFollowsTheStatedQuotaPolicy`，**无删除**（比对 `t08-r2-main-repro.json` 与 `r3-review-d.json` 的 suites）。`mvn clean verify` 的 281/0/143 我未复现（backend/target 归主 agent，禁跑）→ 见请求代跑。
5. **成立**。V5 `5eadd5294216…` 与第二轮 `t08-r2-main-repro.json` 内嵌指纹逐字节相同；`005872f` 的文件清单不含这两份；`git log -1` 均为 `849d784`；剥头 3 行正文 13119B 与草案相等、CR 字节 0。FOR UPDATE 位置我**不用 verify.py**自证：`t08_admit_estimate` 体内锁语句偏移 243 < 聚合 `INTO occupied` 偏移 604，函数内 `FOR UPDATE` 仅 1 处且落在该语句内，`IF NOT FOUND` 紧随（`join_probe.json.v5Lock`）。

## 未证明清单（不构成本轮缺陷，但不得当作已完成）

`mvn clean verify` 全量 281/143；真实 Spring 组合根在 `editorial.cost.enabled=true` 下的完整装配与 `GET /usage` HTTP E2E（身份游标）；`over_run` 外部投影、`pendingReconciliations`/`alerts` 生产调用方、`CostPorts.Executions` 绑定（仍属 T09/T10/T11 前置）；F-03 的分层语义与 F-04(c) 的配置形状均未获 Owner 签字。另：`--reverse-control` 只要求"该条点名的检查里至少一条红"，不要求全部红——门自身这条弱标准值得在下一版写明。

## 请求主 agent 代跑（我这边跑不了或禁跑）

1. `mvn -B -ntp -o -f backend/pom.xml "-Dmaven.repo.local=.tools/t02/m2" clean verify` — 期望 exit 0、281 项、0 失败、143 跳过（唯一我没复现的声称）。
2. 若采纳 F-03 的 P1 两条探针用例（我的可编译版在 `.work/t08/r3-variants/P1/backend/src/test/.../T08PostgresTest.java`，`providerQuota`/`holds` 全部复用现有 helper）：`python tests/engineering/T08/run_pg.py --expect-tests 51 --evidence-name r3-fix-51`。
3. F-01/F-02/F-03/F-05/F-06 各自补反向对照后：`python tests/engineering/T08/verify.py --reverse-control`（期望新增条数、blind=none、misplaced=none）。
4. 复跑请用绝对 `--work-root` 或省略该参数（F-07）；派单原文给的相对形状会 exit 1 且不落证据。

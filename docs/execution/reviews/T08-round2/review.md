# T08 第二轮独立复审（F-01/F-02 整改复验）

- 判决：**CHANGES_REQUIRED**——两条 P1（F-01、F-02）**均判 CLOSED**；本轮因新发现 F2-01（P2）与四条 P3 返修，不推翻 P1 闭合。复审方不自签采纳。
- 被审字节：整改 `849d784`（T08 侧 cost 包 + V5 触发器 + tests/engineering/T08 + 台账/两报告更正）、实施+集成 `b3a909d`；复审前 HEAD `23c6c2c`，工作树对已跟踪文件干净。复审进行期间，并行的 T03-round6 agent 改动了两个 **T03 域**已跟踪文件（`identity/T03Configuration.java`、`tests/engineering/T03/check_session_cookie.py`，属其任务范围，非本复审所动）；**T08 域字节全程零改动**，该 diff 出现后本复审的 `verify.py` 仍 13/13（exit 0）、`check_contracts.py` 仍 27/27（exit 0）。
- 复审者：独立复审 agent-2（与实施方、集成方、第一轮复审方均无上下文共享；两份 T08 报告与 STATE 只当主张清单）。日期 2026-10-07；机器可读证据：[evidence/checks.json](evidence/checks.json)。

## 0. 独立复现（全部本轮实测；§3 的 F-08 行亦为当前字节下复跑）

| # | 命令 | 期望 | 实测 |
|---|---|---|---|
| 1 | `python tests/engineering/T08/verify.py` | 13/13 | **exit 0**，`13/13 passed`（逐项 PASS 行含 `drifted=none, undocumented fallbacks=none, required-without-default=[max-calls, reconciliation-stale], refuses 503=True, OQ-09 open=True`、`lock precedes aggregate=True, overstated claims=none`、`weakened=none`） |
| 2 | `python tests/engineering/T08/verify.py --reverse-control` | 18/18 REJECT | **exit 0**，18 条减弱逐条 `[REJECT]`，`blind=none, misplaced=none`；变异只改内存（脚本无任何写盘调用，`MUTATIONS` 在 `finally` 清空） |
| 3 | `python tests/engineering/T02/check_contracts.py` | 27/27 | **exit 0**，`Approved T00 rc.3: 27 hashes verified, no regeneration` |
| 4 | `python tests/engineering/T08/run_pg.py --evidence-name t08-r2-reviewer2` | 44/0/0 | **exit 1**：`PermissionError [WinError 5]` 于 `tests/engineering/T08/.work/<uuid>` mkdir（`run_pg.py:117`）。与第一轮复审 §0-1 同一环境边界（低完整性令牌无写权限），按派发说明**不记为缺陷**、未重试；`mvn` 一律未跑（并行复审方争用） |
| 5 | `git show -s b3a909d` | 原句仍在 | 提交信息原文仍含 `no invented business limits, so enabling the domain fails closed`，历史未被改写；该句仅在 `T08-Integration` §7 被明文撤回 |

## 1. F-01（额度默认值与表述相反）——**CLOSED**

**数值面对照（逐条，用定点检索，未读 SRS 全文）**：`BudgetPolicyConfig.java:47-55` 的八个回退值为 30 / 40_000 / 3 / 1 / 2 / 4 / `"20.000000"` / 80；SRS `:1103` 原文"默认每文章总检索 query 上限 30、正文模型输出总 token 上限 40,000、单 Claim query 上限 3、自动编辑循环 1、单 Slot 生图 2 次、每篇生成 4 张"、`:1099`"日预算示例 20 USD"、`:1143`"预算 >80%"——**八条全对得上，无一编造**。每篇 5 USD 不进配置（是 `article_job.budget_limit` 行值，V5:86 读它）。`provider-quota` 缺项=不设限（:80-85 注释与代码一致），`max-concurrent/calls-per-day` 负值仍 503 `INVALID_BUDGET_POLICY`。

**必需项真的无默认（读代码路径，不信注释）**：`max-calls-per-article` 与 `reconciliation-stale-minutes` 走 `statedCeiling`（:46/:57），缺键 → `PublicFailure(503,"QUOTA_NOT_CONFIGURED")`（:107-111）。装配可达性：`CostConfiguration:31` 在 `@ConditionalOnProperty(editorial.cost.enabled=true)` 的 eager `@Bean` 里调 `BudgetPolicyConfig.from(env)`——启用态缺键即 bean 创建失败、上下文拒绝启动。单测锁形：`CostPricingTest#undocumentedCeilingsHaveNoDefault`（裸 `MockEnvironment` → 503+码字；只配其一仍拒；负值 → `INVALID_BUDGET_POLICY`）。第一轮"生产路径不可达"的 `QUOTA_NOT_CONFIGURED` 现在有真实装配期路径。

**闸门自证（第 9 项能否拒绝三类削弱）**：`check_documented_ceilings` 从 SRS 行本身解析六个数（锚点漂移直接 `SystemExit`，见 `documented_ceilings()`:337-351）、逐键比对代码 fallback、`extra` 拒绝给未写明项编默认、daily/alert 分别对读 `:1099`/`:1143`、`stated=={两项}`、OQ-09（`:1281` 实测"示例 5/20 USD"，仍 OPEN）必须保持未关闭、application.yml 不得出现任何额度键。反向对照第 1-5 条（改 daily→999、改 alert→70、改 tokens→40001、整行删掉 AUTO_EDIT_LOOP、给 max-calls 编 64）**全部 REJECT**——第一轮 M12 的盲区已闭合，"改一个数字/删一个数字/给未写明项编默认"三类都真被拒。

**表述面**：T08.md §2(:26)/§4.1(:55)/§6(:94) 已是"8 个文档值回退 + 2 个必需否则拒启"的实况；Integration §2.2 自我更正 + §7 明文撤回原句；STATE `tasks.T08`、`openItems[COST-BUDGET-LIMITS]`、`pendingReviewCommit` 三处同口径，且后者明写"历史提交不改写"。`grep 不编|fails closed|必然启动失败…` 全 `docs/execution` 命中的现势句子要么被限定在 `application.yml` 范围内（属实，check 11 守着），要么是被标注为撤回的引文。残留一处措辞不准 → F2-03。

## 2. F-02（AC-28 DB 层保证超出实现）——**CLOSED**（活库重跑除外，见 §5）

**锁序与语义（V5:81-94 亲读）**：`t08_admit_estimate` 现先 `SELECT budget_limit … FOR UPDATE`（:86，未命中行 → 23503），**后**聚合占用（:88-90，COUNTED 口径与服务侧 `CostLedger:35-36` 逐字一致），再 `occupied+NEW.amount>limit → 23514`（:91）。READ COMMITTED 下成立的理由：触发函数内每条 SQL 各取语句级新快照；文章行锁持有到事务结束，第二个并发直插必然 (a) 若先到：拿锁→聚合→插入→提交，(b) 若后到：`FOR UPDATE` 等待对方**提交**，解锁后其聚合是锁后才开始的**新语句**，取新快照 → 看到对方已提交的 RESERVED 行 → 23514。同语句多行 INSERT 也安全（后续行的聚合可见本事务前面已插行，且同一把行锁）。每触发器至多锁一行 → 无环；settle 的 ACTUAL 插入在 :85 提前返回不碰文章锁，与服务 advisory 之间无交叉等待。

**并发对抗用例是真刀**（`concurrentBypassWritersCannotOversubscribe`:432-452 + `bypassInsert`:459-501）：两个**独立** runtime 连接（`runtimeSource.getConnection()` 各一）、`autoCommit=false`、每会话先 `SHOW session_replication_role` **断言 == "origin"**（replica 会禁触发器即空炮，:462-465 直接失败退出）——**不是**用 replica 播种的那条管理连接；`CyclicBarrier(2)` 同发放、`pg_sleep(0.4)` 把已插未提交事务按住强制两读重叠；断言的是 **`committed` 计数恰 1**（:447-448，"at most one"）+ 另一侧 `"23514"` + `occupied=1.000000` + `rows=1`，不止步于错误码。`lastBalanceSingleWinner`:357-395：`ready(2)/start(1)` 闩真接上（`attempt()` 先 `countDown` 后 `await`，超时返回 `LATCH_TIMEOUT` 会污染 outcomes 被 :382 抓住），**10 轮**，每轮断言 winners==1、BUDGET_EXCEEDED、reserved=1.000000、1 行、告警数据与 1 条审计。

**三处注释已降级**：V5:76-80（"repeats the article ceiling **and nothing else**…those bind the service path alone"）、`CostLedger:24-31`、`BudgetService:22-32`（"a bypassing writer meets the article ceiling and nothing else"）。`verify` 第 10 项禁三个旧 over-claim 短语且要求"service path"字样在场，反向对照第 7/17/18 条（拆锁、草案漂移、注释回吹）REJECT。

**修前红是真的、且绑字节**：`evidence/t08-r1-baseline-gap-pre-fix.json` 命令退出序列含 mvn **exit 1**，失败恰为 `concurrentBypassWritersCannotOversubscribe:448 … [committed, committed] expected:<1> but was:<2>`（修前字节上两个直插真都提交、超订 2.0 USD），`clusterStopped=true`、`failure=RuntimeError`、内嵌 V5 sha256 `f71f7a49…4806` 与第一轮复审实测的 b3a909d 旧字节指纹**相同**——红绑在修前字节上。修后 `t08-r2-main-repro.json`：totals 44/0/0、`expectations.problems=[]`、`clusterStopped=true`、名单含 bypass/single-winner/audit 用例（仍是主 agent 记录，本轮由 §5 命令补独立活跑）。

## 3. 上一轮 P2/P3 复验

- **F-03 CLOSED**：V5/注释均明写 DB 只兜文章上限（见上）；T08.md §3 同步。
- **F-04 CLOSED（走替代路径）**：T08.md §2/§4.2(c) 改为"误差单独报告只完成一半，外部投影待 T10/T11"；登记面在报告未在 STATE → 并入 F2-04。
- **F-05 CLOSED（代码/报告面）**：`CostPorts:58` 注释明言静默丢弃是 known gap；T08.md §4.2 登记三件 T10/T11 前置；STATE 台账面未见 → F2-04。（`noAlerts()` 计数指标属"建议"，未做，不改判。）
- **F-06 CLOSED**：(a) `noAudit()` 工厂已删，全 `src/main` grep 仅剩注释文本（verify:222-223 剥注释后扫，反向对照第 12 条在 `CostPorts` 复活它被 REJECT——第一轮"换文件不响"的盲区补上）；(b) `T08PostgresTest:276/1184` 反射取生产 `CostIntegration.costAudit` bean 跑真实 `JdbcAuditSink`，断言 2 行/两哈希 NULL/23514/42501（锚点项含 `productionAuditPort`），改成 `Object.class`/关守卫被反向对照 13/14 REJECT；(c) identity/cursor-key 两条启用前置写进了 T08.md §4.1，STATE 未见 → F2-04。
- **F-07 CLOSED**：`--reverse-control` 存在且本轮亲跑 18/18；M12/M13/M15 对应位（额度、`require(true,`、掏空断言/拆闩）全覆盖，第 10/11 项已升级为结构性断言（`require\(!env.getProperty…` 模式 + 方法体 token 表）。
- **F-08 CLOSED**：`run_pg.py:281-296` 对 failures/tests/skipped/缺报告四类问题 `raise RuntimeError` 且拒写证据；证据名撞车 :106 拒写。小瑕疵：修前那次实为"命令失败 RuntimeError"截停（证据里没有 `totals/expectations` 键），"修前/修后两次运行都受这条约束"一句偏松——结果更强（红了照样落盘取证），仅记措辞。
- **F-09 CLOSED（可证部分）**：`CostPricingTest:447` 断默认端口 503 码字；`T08PostgresTest:506-517` 在真实库上以 `CostPorts.unavailableExecutions()` 跑 reserve → 503 且 0 行 0 审计。Spring 装配态真实启动未测——与主 agent 一致地未证明，已由 COST-HTTP-E2E/Integration §6 登记，非新缺口。
- **F-10 CLOSED（文档化路径）**：`BudgetService:97-102` 在重放代码上方明记不对称与调用方义务，T08.md §2 同步；rc.3 无请求摘要字段，改契约非 T08 权限。
- **F-11 CLOSED**：T08.md §3 现字节（13,119B 对 13,119B、CR=0）经本轮 check 4 独立复测成立；`Money` 12 位整数的表述已订正；verify docstring 不再声称 CRLF。
- **F-12 未闭合**：见 F2-05。

## 4. 新发现

**F2-01 · P2 · model 级 provider-quota 经配置路径被静默忽略（fail-open），两处文档键名还各说各话**
`BudgetPolicyConfig.quotas()`（:61-88）把 `editorial.cost.provider-quota.mock.mock-model.max-concurrent` 的 scope 取为 `"mock.mock-model"`（`lastIndexOf('.')` 前段），而 `BudgetPolicy.providerQuota()`（:63-65）查找 `provider + "|" + model` 再 `provider`——`"mock|mock-model"` 永不命中；类 javadoc :35 教的 `[_<model>]` 下划线写法同样永不命中。**配置正确拼写的 model 级上限会被无声丢弃**（比拒绝更危险的方向）。`budgetPolicyOverrides`（:410-434）只测了 provider 级（`quota("mock",…)` 命中 `get("mock")`），config 路径的 model 级零覆盖，verify 第 9 项也不扫 `quotas()`。T08.md:55 又写作 `{max-concurrency,daily-calls}`——照抄会撞 `INVALID_PROVIDER_QUOTA_KEY`（这反而是响的）。缓解：功能门默认关、yml 无该键、provider-quota 属"未定项"。requiredFix：scope 归一（如 `_`→`|` 或直接按 `provider|model` 文档化）、补一条 config 路径 model 级覆盖断言（含"配了却不生效必须红"的反向控制）、订正 T08.md:55 与 STATE 的键名。

**F2-02 · P3 · verify 第 10 项的锁序判定可被诱导读过**
`locked_first` 用 `function.find("FOR UPDATE") < function.find("INTO occupied")`（:404-405）——取**首次出现**。若有人在聚合前塞一段含 "FOR UPDATE" 的诱饵文本而把真锁挪到聚合后，该项仍绿（字节等值只约束 draft↔V5 同改同版，不锁语义）。现字节经本轮亲读序对（V5:86 先、:88 后）。建议改为断言**正则匹配到的锁语句**的结束位置 < 聚合起始位置，并配"诱饵+挪锁"变异。

**F2-03 · P3 · Integration §2.2 括注"BudgetPolicy:58 由不可达变为可达"不准**
生产装配期真正新可达的是 `BudgetPolicyConfig.statedCeiling:109`；`from()` 恒填满 7 个 Counter，`BudgetPolicy.cap()` 的 :58 在产线路径**依旧不可达**（仅测试直构/部分 caps 时可达，如 T08PostgresTest:555-559）。结论（503 路径真实存在）为真，出处指错了行。同句在 `CostPricingTest:379-381` 的表述是准确的。

**F2-04 · P3 · F-05/F-06 要求的 STATE 台账登记未落**
第一轮点名"把『AlertSink 未绑定期间告警不落任何介质』与『identity/cursor-key 两条启用前置』写进 STATE 台账"；现只在 T08.md §4 与 Integration §2.3。STATE 是"唯一状态入口"，启用态前置条件应进 `COST-BUDGET-LIMITS`/`COST-HTTP-E2E` 文本。

**F2-05 · P3 · F-12 延续：整改字节仍无作者级边界**
`849d784`（作者 `Codex`）一个提交混装 T08 整改、T03 闸门加固与两份复审记录；实施方/主 agent 归属只能再度采信报告自述。历史提交不可改写，此后整改请拆提交或在报告逐文件署方。另 T08.md §2 表"AC-28 最终对账误差"行首列重复、尾部多出一组重复验证入口单元格（表形破损，顺手提）。

## 5. 本轮未证明 / 需要主 agent 代跑

- **未证明**：`run_pg.py --expect-tests 44` 活库独立重跑（WinError 5，§0-4）；`mvn clean verify` 与 `formal.py`（禁跑/争用）；装配态（cost+identity enabled）真实 Spring 启动与 `GET /usage` HTTP 端到端（与主 agent 均未证明，已登记）；rc.3 reserve/settle 契约原文逐条比对（仅 27 哈希 + 字段闸门）；并发论证的活库复证（§2 为静态语义 + 修前红/修后绿两份跟踪证据，非本轮实跑）；真实供应商计费、灾备。
- **请代跑（需写权限会话）**：`python tests/engineering/T08/run_pg.py --expect-tests 44 --evidence-name t08-r2-reviewer2-replay`——预期 exit 0、totals 44/0/0、`expectations.problems=[]`、`clusterStopped=true`，证据自动落 `tests/engineering/T08/evidence/`。此项通过不改变 F2-01 的 P2 返修义务。

## 6. 判决说明

F-01：数值八条对齐 SRS 原文、两条必需键的 503 拒绝启动路径真实可达、第 9 项对三类编造/删改实证拒绝、表述面（除 F2-03 一处括注）与 b3a909d 撤回纪律全部核实——**CLOSED**。F-02：锁序正确且 READ COMMITTED 语义论证成立、对抗用例三要件齐备（origin 断言、独立连接、断提交数）、闩真接 10 轮、注释降级带禁语闸门、修前红绑旧字节入库——**CLOSED**。判 CHANGES_REQUIRED 仅因 F2-01（P2）与 F2-02…F2-05（P3）：一处配置期 fail-open 的配额解析缺陷与四处台账/闸门/署面残项；两条 P1 的闭合不因返修重开。本复审不自签采纳。

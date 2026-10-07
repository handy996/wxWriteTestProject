# T08 第一轮独立复审（预算 / 价格 / 用量 / 对账）

- 判决：**CHANGES_REQUIRED**
- 被审提交：`b3a909d0200769ac1940838849702a5f9bd258ad`（实施 + 主 agent 集成合一）；复审前工作树 `git status` 干净
- 复审者：独立复审 agent-1（与实施方、集成方无上下文共享；两份 T08 报告只当主张清单使用）
- 复审日期：2026-10-07；机器可读证据：[evidence/checks.json](evidence/checks.json)
- 复审脚本（同目录，零依赖，只读；未 `git add`/`commit`，未跑 `mvn`）：[check_gates.py](check_gates.py)、[check_boundary.py](check_boundary.py)、[check_reverse_control.py](check_reverse_control.py)

## 0. 独立复现结果

| # | 命令 | 期望 | 实测退出码 | 结论 |
|---|---|---|---|---|
| 1 | `python tests/engineering/T08/run_pg.py --evidence-name t08-r1-reviewer1` | 0 / totals 40-0-0 | **1** | **未复现**：`PermissionError [WinError 5]` 于 `.work/<uuid>` mkdir；工具链（initdb/psql/java/mvn）在 line 101-103 检查全部通过后才会走到这里，故阻塞点是本会话子进程**低完整性令牌（S-1-16-4096）无写权限**，工作区内外一律拒绝（`--work-root` 逃逸同样不可用）。会话禁止申请提权，复审方无法修复 |
| 2 | `python tests/engineering/T08/verify.py` | 11/11 | 0 | **复现** `T08 static checks: 11/11 passed` |
| 3 | `python tests/engineering/T02/check_contracts.py` | 27 hashes / 0 | 0 | **复现** `Approved T00 rc.3: 27 hashes verified, no regeneration` |
| 4 | `check_boundary.py`（git blob + 工作树字节） | 逐字节等同 | 0 | **复现并加强**：见下 |

第 4 项实测（`git show` blob 与工作树双份）：V5 blob 13125B `sha256=f71f7a49…4806`，草案 13108B `sha256=b6ae88ba…0014`，工作树与提交字节完全一致；两者首 3 字节 `2d 2d 20`（**无 BOM**，与 V4 参照一致），CR 字节 **0**，CRLF **0**，LF 176；剥掉各自头 3 行后正文 **12774B 对 12774B，原始字节相等**，正文 sha256 同为 `80df4652…0226`；版本化迁移恰为 V1–V5（无第 6 个）；V5 `CREATE TABLE` 只有 `cost_ledger`+`cost_pricing_version`，`ALTER/DROP/TRUNCATE` 计数 0，对非 cost 表的写入 0；`cost_ledger|cost_pricing_version` 字样在其他迁移中出现 0 次（仅 V5 内 42 次）；`application.yml` 差异为 `+2/-0` 行，只加 `editorial.cost.enabled: ${EDITORIAL_COST_ENABLED:false}`。

## 1. 发现（P1×2、P2×5、P3×5）

**F-01 · P1 · 生产路径里确实编了额度，且台账主张与代码相反**
`BudgetPolicyConfig.from()`（:30-40）为 10 个键写死回退值：`max-calls-per-article 64`、`search-queries-per-article 30`、`model-output-tokens-per-article 40000`、`queries-per-claim 3`、`auto-edit-loops-per-article 1`、`image-units-per-slot 2`、`image-units-per-article 4`、`daily-budget "20.000000"`、`alert-percent 80`、`reconciliation-stale-minutes 30`。`CostPricingTest#budgetPolicyCeilings`（:342-351，`@DisplayName` 自称 "Ceilings default to the documented SRS limits"）还把这套值锁成断言。后果：T08.md §4.1「SRS 参考值只存在于测试夹具与本报告中，不是生产默认」**为假**；§2「缺配置报 503 `QUOTA_NOT_CONFIGURED`」在生产装配路径**不可达**（`BudgetPolicy:58` 只在 caps map 缺键时抛，而 config 永远填满 7 个键）；Integration §2.2 与 `STATE.json openItems[COST-BUDGET-LIMITS]`「业务额度我一律不编／缺键必然 fail-closed 启动失败」在额度维度**为假**——开关打开后预算会以未经 Owner 批准的 20 USD/日生效（启动失败其实只来自 `AUDIT_CURSOR_KEY` 与 `AuditSink` 两个不相干条件）。反向控制 M12 证明 `verify.py` 第 9 项对 `BudgetPolicyConfig` 完全失明（daily-budget 改成 999.000000、搜索上限改成 1000000，11 项仍全绿）。缓解：默认开关关闭、数值可溯 SRS 32.2/34、方向偏保守（限支出而非放开）。
requiredFix：二选一并留痕——(a) 删掉数值回退，缺键即 `BudgetPolicyConfig` 抛 503（与主张一致）；(b) Owner 书面批准把 SRS 参考值当生产默认，并同步更正 STATE.json/T08.md/T08-Integration 三处表述。无论哪条，`verify.py` 第 9 项必须扩扫 `BudgetPolicyConfig.java` 的 `count(env, …, <数字>)`/`getProperty(…, "<数字>")` 回退，使 M12 从 BLIND-SPOT 变 REJECTS。

**F-02 · P1 · AC-28 的"数据库也守上限"说法超出实现，并发证据只是跑过一次**
锁序本身成立：`BudgetService:89-91` 按 `Ceiling::lockKey`（`T08|ARTICLE|`、`T08|CLAIM|`、`T08|DAY|`、`T08|PROVIDER|`、`T08|SLOT|` 的字符串全序）排序后逐个取 `pg_advisory_xact_lock`，全序对所有事务一致 → reserve↔reserve 无环；settle 只取 `T08|SETTLEMENT|<id>`（:186）+ 头行 `FOR UPDATE`（`CostLedger:126`），且不取任何 ceiling 锁 → reserve 不锁已有行，settle/reserve 之间也无环。**问题在 DB 守卫**：`t08_admit_estimate`（V5:85-88）用普通聚合 `SELECT coalesce(sum(amount)…) FROM cost_ledger WHERE article_id=NEW.article_id`，无 `FOR UPDATE`、无 advisory lock。READ COMMITTED 下两个并发直插各自动作快照都看不到对方未提交的行 → 双双通过 → 超订。因此 V5:76-77、`CostLedger:28-29`、`BudgetService:27-28` 三处「a writer that skipped the lock still cannot oversubscribe」**只对串行写入者成立**，并发绕过者并不被 DB 挡住。测试侧：`admissionCeilingIsADatabaseRule`（:369-385）只证明单条直插 23514；`lastBalanceSingleWinner`（:331-357）是 2 线程**跑一次**，且 `ready`/`start` 两个闩从未被 `attempt()` countDown/await（:337-343 对比 :359-365）→ 同步是装饰，也未能区分"单赢家"来自 advisory 锁还是触发器。
requiredFix：(a) 在触发器内对文章作用域加锁（`PERFORM pg_advisory_xact_lock(<与 T08|ARTICLE|<uuid> 同键>)` 或 `SELECT … FOR UPDATE` 文章行），使 DB 规则在并发下也成立；(b) 补一个"两会话绕过服务并发直插、要求至多一个提交"的对抗用例，并把闩修正 + 循环若干次；(c) 若 (a) 不做，就把三处注释与 T08.md §3 措辞降级为"串行绕过写者的兜底"，不得继续作为 AC-28 的 DB 层证明。

**F-03 · P2 · 服务与 DB 是两套上限覆盖面（文章一致，其余只在服务侧）**
文章上限两侧同源同式：服务 `used.occupied()+estimate > article.limit()`（:103）与触发器 `occupied+NEW.amount>limit_amount`（V5:85-88）都取 `article_job.budget_limit`，且 COUNTED 口径逐字一致（`CostLedger:33-34` 对比 V5:85-86），结算行 `amount=settled` 与头行镜像一致 → 无数字漂移（这是正面结论）。但**日预算、6 类次数上限、Provider 并发/日调用**只有服务侧实现，DB 无任何 CHECK/触发器兜底；状态机两侧一致（`ReservationStatus:12-16` 对比 V5:109-111）。
requiredFix：要么把 owner/day 聚合同样加进 admit 触发器（`cost_ledger_day` 索引已具备，代价小），要么在 V5 注释与 T08.md §3 明确"DB 只兜文章上限"，避免后续任务把它当全量不变量。

**F-04 · P2 · `over_run` 只写不读，AC-28"最终对账误差单独报告"无对外报告路径**
列存在（V5:54）并写入（`CostLedger:174-178`），`Reservation.overRun` 只在 Java 对象里；冻结 `BudgetReservation` 10 字段与 `UsageSummary` 11 字段都没有 overRun（反向控制 M01 证明往 `Reservation.wire` 加字段会被闸门拒绝，闸门是对的），而 `reportedAmount()`（:46-48）在 SETTLED 行**用结算额覆盖预估额**，客户端连差值都推不出来；`UsageService.alerts()` 也不含它。故 T08.md §2「差额写入 over_run 并…单独报告」目前只有 JUnit（`overRunIsBookedAndReported:911`）看到。
requiredFix：给出真实读取路径（结算告警载荷带 overRun、或 `pendingReconciliations` 返回体带 overRun 并被 T10/T11 消费），并新增/更正一条 OPEN 项；否则把该句改为"账本记录 + 服务侧可读，对外报告待 T10"。

**F-05 · P2 · 告警与对账队列在生产里无人调用（报告面是 fail-open 的）**
`grep` 全仓 `backend/src/main`：`BudgetService.pendingReconciliations`（:314）与 `UsageService.alerts`（:82）**只被测试调用**；`CostConfiguration:46-48` 默认绑 `CostPorts.noAlerts()`（静默丢弃）；`CostController` 只映射 `GET /usage`（冻结契约使然）。UNKNOWN 的预算永久占用（设计如此，`unknownKeepsTheHold:507-540` 证明占用不释放、仅 reconcile 可关）叠加"队列无读者"，意味着现实后果是**预算被永久占住且没有任何自动可见的告警**；重放幂等成立（`bySettlementKey`+`requestHash` 比对，`Settlement:89-100`）。
requiredFix：在 T09/T10 派发卡写明调用点（谁、多久一次读队列），并把"AlertSink 未绑定期间告警不落任何介质"写进 STATE 台账；同时建议 `noAlerts()` 至少计数并暴露一个可读指标，避免"零读者"与"零告警"无法区分。

**F-06 · P2 · 审计决定可接受，但有三处必须修的缺口（含删兜底的装配影响）**
判断依据：`audit_log.before_hash/after_hash` 是 `char(64)`+`^[a-f0-9]{64}$`、`detail` 被 CHECK 锁成 `'{}'`（V1:16-30，且 `auditRowsLandInTheAuditTableThroughTheRealSink:1076-1085` 以 23514 实测），因此金额**不可能**进审计列，集成方改传 `null` 是唯一不动已批准 V1/契约的做法；金额事实仍在 `cost_ledger`（append-only、无 DELETE 授权、三守卫），审计行带 `article_id`+`entity_id`=预占 id 可回溯 → **不构成审计事实缺失**，属可接受取舍。
缺口：(a) `CostPorts.noAudit()`（:66）仍在，是静默吞审计的死工厂，而 `verify.py` 只扫 `CostConfiguration`/`BudgetService`（M08 只在 `CostConfiguration` 里加回兜底才被拒），换个文件复活兜底闸门不响；(b) PG 侧"闭环"用的是测试自建的镜像守卫 `realAuditSinkPort()`（:260-269），不是生产 `CostIntegration`，M14 证明把生产守卫改成 `if (false …)` 后 11 项静态检查全绿 → 生产适配器 × 真实库的组合从未被执行过（只有 `CostAuditWiringTest` 的内存 sink 覆盖）；(c) 删兜底对启动的影响：`AuditSink` 只由 `T03Configuration:27`（`editorial.identity.enabled=true`）提供，cost 侧全部 `@ConditionalOnProperty(editorial.cost.enabled=true)`，与 `VersionIntegration:24`/`ArticleIntegration` 同构 → **不会让任何现有装配路径启动失败**（无任何测试或配置现时启用 cost），但新耦合是"启用 cost 需同时启用 identity"，加上 `UsageService:39` 要求 ≥32 字符 cursor key，启用态实际有两条与预算无关的启动前置条件。
requiredFix：删 `CostPorts.noAudit()`（或改为抛错）；`T08PostgresTest` 改用 `new CostIntegration().costAudit(sink)` 跑同一断言；在 COST-BUDGET-LIMITS 台账补写 identity/cursor-key 两条前置条件。

**F-07 · P2 · `verify.py` 没有自证反向控制，4 类削弱它看不见**
`check_reverse_control.py`（内存变异，运行后全部输入文件 sha256 不变）：**11/11 定向削弱被目标检查拒绝**（M01-M11：加/改 DTO 字段、削 V5 CHECK、加第 3 张 cost 表、加 DELETE 授权、`Money` 引入 double、审计带回金额、`CostConfiguration` 复活 noAudit、cost 反向 import audit、yml 编日预算、锚点改名），**4/4 削弱后 11 项仍全绿**：M12 额度默认值、M13 `StartupPolicy` 付费调用守卫改成恒真（第 10 项只 grep 属性名，属近恒真断言）、M14 审计形状守卫停用、M15 `assertEquals(1, winners)` 掏空成 `assertTrue(true)`（第 11 项只验方法名存在，不验断言）。违反 STATE 协议「校验器要自证有效」。
requiredFix：给 `verify.py` 加 `--reverse-control`（内存变异，遵守「变异只能改内存」），至少覆盖 M12/M13/M15，并把第 10 项从"字符串存在"升级为对 `require(!env.getProperty("editorial.providers.paid-calls-enabled"…)` 的结构性断言。

**F-08 · P3 · `run_pg.py` 记录 totals 但不校验 totals**
:260-271 只求和写入证据，`exit_code = 0`；surefire 用 `-Dsurefire.failIfNoSpecifiedTests=false`，且 `T08PostgresTest` 受 `T08_REAL_PG` 门控 → 0 项或 26 项 skipped 的"空跑"仍会退出 0，"40/0/0"靠人读 JSON 而非闸门。
requiredFix：加 `--expect-tests 40 --expect-skipped 0`（不符即非零退出并拒写证据），让"40"由脚本自己守住。

**F-09 · P3 · `Executions` 的 fail-closed 只有代码阅读依据，没有任何断言**
`CostPorts.unavailableExecutions()`（:60-62）确为抛 503 `EXECUTION_SCOPE_NOT_READY`、不返回空作用域，且在任何账本写入之前（`BudgetService:79`，早于 :121 的 insert），`@ConditionalOnMissingBean`（`CostConfiguration:39-41`）保证未绑定即取此默认 → 设计成立。但全仓 `backend/src/test` 无一处引用 `unavailableExecutions` 或 `EXECUTION_SCOPE_NOT_READY`（`T08PostgresTest` 注入自己的 map 假件，测的是 404 `EXECUTION_NOT_FOUND`）。
requiredFix：加一条零依赖单测断言默认端口抛 503 且码字正确；再加一条装配测试（cost enabled + identity enabled）证明 `BudgetService` 能建且 reserve → 503，不产生任何 `cost_ledger` 行。

**F-10 · P3 · reserve 重放不比对请求内容，与 settle 不对称**
同 `idempotency_key` 换不同用量仍返回旧预占（`BudgetService:94-95`；测试 :389-398 用 1 单位再发 4 单位并断言"不重算更大"），而 settle 比对 canonical `requestHash`（:190-191 → 409 `SETTLEMENT_CONFLICT`）。契约没有 reserve 的 HTTP 面，但 T09 会直接调端口。
requiredFix：要么按 settle 同法比对请求摘要并 409 `IDEMPOTENCY_CONFLICT`，要么在 `CostPorts`/T09 派发卡明确"键必须由请求摘要派生"。

**F-11 · P3 · 报告文字与当前字节不符的两处陈旧陈述**
T08.md §3/§5 仍写「实测草案为 LF、V5 为 CRLF（12,774B 对 12,947B，173 个 CR）」——本次实测两者均 LF、CR=0、正文 12774=12774 且原始字节相等（返工后的事实）；`verify.py:92-93` 的 docstring 也仍称 "the installed migration was written with CRLF"。另 T08.md §2 称 `Money` 拒绝"超出 int32 金额"，实际上限是 12 位整数（`Money:17-18`，与 `numeric(18,6)` 精确对齐，这点是好的）。
requiredFix：把两处叙述改成本轮字节事实（保留返工历史另段说明），并订正 int32 措辞。

**F-12 · P3 · 实施与集成压成同一提交，边界不变量无法按作者核验**
`b3a909d` 含 120 个 A + 2 个 M（M 恰为 `application.yml` 与 `STATE.json`），其中 `tests/engineering/integration/evidence/**` 等属集成侧产物。按协议「任务卡写入之外被改动的文件直接判 CHANGES_REQUIRED」，本次无法从单一提交区分"实施方改了哪些、主 agent 加了哪些"，只能采信报告自述（这正是本复审要防的事）。
requiredFix：实施提交与集成提交分离（或主 agent 在集成报告里逐文件署方），使边界闸门可按作者复核。

## 2. 八个必答问题的结论（依据见上）

1. **并发与锁序**：锁序单一、无环（见 F-02 正面论证）；但 AC-28 的 DB 兜底不是并发防线、测试只跑一次且闩失效 → F-02。
2. **触发器与服务一致性**：文章上限两侧同源同式（无数字漂移，F-03 前半为正面）；绕过服务的**串行**直插确被 23514 拒（实测 SQLSTATE 断言 :381），DELETE/UPDATE 由授权 42501（:967-970 用消息文本而非 SQLSTATE，属弱断言），并发直插则可超订 → F-02/F-03。
3. **UNKNOWN 语义**：先提交再 409 的实现正确（`reportUnresolved:179-183` 在 `tx.execute` 之后抛），预算确实被占住直到 reconcile，重放幂等成立；但"有真实报告路径"只在测试与无人调用的服务方法里 → F-04/F-05。
4. **审计决定**：**可接受**，非事实缺失（金额在账本、审计带标识符可回溯、schema 本就不允许金额）；须修 F-06 的三缺口；删兜底不破坏任何现有装配路径（无任何路径启用 cost；identity 与 cursor-key 才是前置条件）。
5. **不镜像 `article_job` 金额列**：理由成立且与本仓闸门一致——T06 投影守卫确实存在（V3:54 用 `summary->>'budget'` 与 `budget_limit` 比对，镜像会连带改 summary），`lock_version`/ETag 由 T06 拥有；账本聚合口径（`CostLedger:79-96`）自足。代价是 F-04 的读路径缺口，不构成本项反对理由。
6. **`Executions`/`AlertSink` fail-closed**：Executions 真 fail-closed（503，不返回空作用域）但零测试 → F-09；AlertSink 是静默默认，属 fail-open 的报告面 → F-05。
7. **反向控制有效性**：`CostAuditWiringTest` 三项含 7 类载荷拒绝 + 不回显被拒值（真否定）；PG 侧否定用例多为 SQLSTATE/消息级真断言（23514/42501/权限、不可变、终态唯一事实）；`verify.py` 有效但**自证缺失**，4 类削弱不可见 → F-07；`run_pg.py` 不自校验 totals → F-08。
8. **额度缺失处理**：`application.yml` 干净（+2 行、无任何额度键，实测 `applicationYmlInventedBudgetKeys=[]`）；**但**额度数值以硬编码默认值进入生产路径 → F-01（越权项，已记发现）。

## 3. 复审方未证明的部分

- **40/40 真实 PostgreSQL 全套**（本会话子进程无写权限，见 §0 第 1 行；`totals` 由主 agent 证据 `main-repro-2.json` 声称，复审方不予采信）。因此：触发器实跑、并发单赢家、授权矩阵、审计落库形状这些"需要活库"的断言，本轮只做了**代码与 SQL 静态论证**，F-02 的并发超订也未做经验复现（推理依据是 READ COMMITTED 语句级快照，需活库证实）。
- `mvn clean verify`（265 项）与 `formal.py` 核心套件未重跑（禁止事项 + 争用 `backend/target`）。
- `GET /api/v1/usage` 真实 HTTP 端到端、启用态组合根启动：与主 agent 一致地未验证（COST-HTTP-E2E 仍 OPEN）。
- rc.3 冻结契约中 reserve/settle 端口的原文适用性未逐条比对（只用了 `check_contracts.py` 的 27 哈希 + `verify.py` 的 DTO 字段闸门）。
- 真实供应商计费、崩溃恢复：未涉及。

## 4. 判决说明

设计主干（单锁序、append-only 账本、DEFERRABLE 一致性触发器、十进制金额、冻结 DTO、最小授权、UNKNOWN 保占、结算不因预算失败、不镜像 `article_job`、不编 `application.yml` 额度）经独立静态复核**成立**；提交字节层面（V5↔草案、无 BOM/CR、V1–V5、只两张 cost 表）**已逐字节证明**。判决 CHANGES_REQUIRED 的依据是 F-01（生产额度默认值与台账主张相反）与 F-02（AC-28 的 DB 兜底并发论证超出实现、缺对抗性证据）两条 P1，加上 F-03–F-07 五条 P2；本复审不自签采纳，采纳由主 agent 与人工批准决定。

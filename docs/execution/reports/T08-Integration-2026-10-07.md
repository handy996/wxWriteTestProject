# T08 集成记录 2026-10-07 — 主 agent 侧决定、缺陷与复现

角色：T08 由上下文隔离的实施子 agent（`8224880b`）交付；**集成与本轮全部决定由主 agent 完成**；**尚无独立复审**，因此本记录不构成批准，T08 状态为 `INTEGRATED_UNREVIEWED`。基线 `bb45244`（HEAD 当时的已复审链见 `STATE.reviewedBaselineCommit`）。

## 1. 我对交付方主张的核验（不采信自述）

| 交付方主张 | 我的验证 | 结果 |
|---|---|---|
| 未改任何已跟踪文件 | `git diff --name-only` / `--cached` | 0 / 0，仅 4 项未跟踪 ✓ |
| rc.3 未动 | 我复跑 `tests/engineering/T02/check_contracts.py` | exit 0，`27 hashes verified` ✓ |
| `verify.py` 9/9 | 我复跑 | 交付时 9/9 ✓；集成后按其真实断言现为 **11/11 exit 0** |
| 39/39 测试 | 读 `evidence/t08-checks.json` 的 argv/退出码 + surefire 摘要 | 14+25=39、0 失败 ✓（补审计项后为 40） |
| PG 夹具已停 | `Get-Process postgres`、端口 55432 探测 | 进程 0、端口不可连 ✓ |

## 2. 第 4 节 7 项待决事项，我的答复

1. **Flyway 全局版本号**：分配 **V5**，安装为 `backend/src/main/resources/db/migration/V5__cost_ledger_pricing.sql`，正文与其草案**原始字节等同**。首轮集成时的数字是 12,774 = 12,774；第一轮复审的 F-02 修复同时改动了草案与安装版（触发器加 `FOR UPDATE`），现在两者仍是剥头 3 行后逐字节等同：**13,119 B**，`sha256(正文)=22d7fad3117ddd38ac9d…`，草案全文件 13,453 B / V5 全文件 13,470 B（差 17 B 是我那三行头注释更长），CR=0、无 BOM。这条等同性由 `verify.py` 第 4 项以**不归一化换行**的方式机器断言，不再靠我口头声明。
2. **`editorial.cost.*` 配置键**：只加功能开关 `editorial.cost.enabled: ${EDITORIAL_COST_ENABLED:false}`。**我在这里写错了，据第一轮复审 F-01（P1）更正**：原文"业务额度我一律不编……启用 cost 必然启动失败"与代码相反，而且同一个假说法被我写进了提交 `b3a909d` 的提交信息与 `openItems[COST-BUDGET-LIMITS]`。实况是 `BudgetPolicyConfig` 有 10 个键，其中 **8 个的回退值等于 SRS 已文档化的示例值**（`docs/AI-Editorial-Agent-SRS-v1.0.md:1099` 日预算示例 20 USD、`:1103` 每文章检索 30 / 输出 token 40,000 / 单 Claim 3 / 自动编辑 1 / 单 Slot 生图 2 / 每篇 4、`:1143` 预算 >80% 告警），所以只加开关就能启动。这些数**不是实施方编造**——我先前把"不编额度"当成自己的功劳，是核实不足：我读了 `application.yml`（确实干净，+2 行）却没读 `BudgetPolicyConfig`，而后者才是生效路径。整改后：SRS 未写明的 `max-calls-per-article` 与 `reconciliation-stale-minutes` 不再有默认值，缺键在配置装配期 503 `QUOTA_NOT_CONFIGURED`（`BudgetPolicy:58` 由不可达变为可达），`verify.py` 第 9 项改为直接对读 `BudgetPolicyConfig.java` 与 SRS 原文，少一个/多一个/改一个都会红。真正待 Owner 签字的是 SRS `:1281` 的 **OQ-09**（"每篇/每天成本上限？示例 5/20 USD"，仍 OPEN）：文档给了示例值不等于产品批准了生产值。
3. **端口绑定**：`CostPorts.Audit` **已绑定**（新增 `bootstrap/CostIntegration.java`，写法对齐 `VersionIntegration:24`，`entityType=COST`）。`CostPorts.Executions` 与 `CostPorts.AlertSink` **保持未绑定**：前者等 T09 的 `agent_execution`/`tool_execution`，后者等 T10/T11 人工任务队列，任何绑定都必须是真实作用域而非编造。同时**删除** `CostConfiguration` 的 `noAudit()` 兜底：启用 cost 而无审计链将在启动期失败，不再静默丢审计事实。
4. **FK**：`cost_ledger.execution_id/claim_id/slot_id` 保持无 FK，等 T09/T10 落表后集成（符合 T00 契约"FK 在 T06/T10 后集成"）。
5. **`article_job` 金额列镜像**：**不镜像**。账本是唯一事实源；写这两列会 bump `lock_version`/ETag 并触发 T06 投影守卫，属跨任务放大改动面。
6. **价格发布运维入口**：缺口保留（runtime 只有 SELECT，写入属 migrator）。登记到 T10 之后的受控运维命令，已并入 `openItems[COST-BUDGET-LIMITS]` 的 Owner 待决清单。
7. **`WAITING_MANUAL` 归属**：确认属工作流侧（T10/T11）。T08 只提供 refusal code 与告警数据，不推进文章状态——这个边界是对的。

## 3. 集成中发现的两个真实缺陷

**(a) 金额被塞进审计哈希列**（交付方代码，我改）。`BudgetService:126` 传 `estimate.text()`、`:211` 传 `estimatedAmount().text()/settled.text()` 到 `before_hash`/`after_hash`。而 `audit_log` 两列是 `char(64)` + CHECK `^[a-f0-9]{64}$`，`detail` 被 CHECK 锁成 `'{}'`（无处安放），所以一旦审计链真接上，**第一次预占就会 23514 失败**。修法：金额不进审计（事实留在 `cost_ledger`，审计带 `article_id`/`entity_id` 可回溯），适配器加**形状守卫**（非 64 位小写十六进制即抛，且不回显被拒值以免入日志），并补 `CostAuditWiringTest`（3 项，含 5 类非哈希载荷必须被拒且不得触达 sink）。交付方随后在 SQL 层闭环：`T08PostgresTest#auditRowsLandInTheAuditTableThroughTheRealSink` 以运行角色绑真实 `JdbcAuditSink` 跑真实 reserve+settle，断言恰好 2 行、两哈希 NULL、`detail='{}'`，并断言 `0.034200` 当 hash、金额塞 `detail` 均 23514，运行角色 DELETE/UPDATE 均 42501 无残行。

**(b) 我自己引入的 BOM 与 CRLF**（已修）。我用 PowerShell `Set-Content -Encoding UTF8` 安装 V5，留下 `EF BB BF` BOM 和 176 个 CRLF；对照 `V4` 首 3 字节为 `2D 2D 20`、CRLF 为 0。`.gitattributes` 的 `/backend/** text eol=lf` **只规范换行，BOM 属于内容会被原样提交**，Flyway 首行会变成 `\ufeff--`。交付方的检查如实报了 LF/CRLF 差异（12,774B 对 12,947B、173 个 CR），但没人查 BOM。已重写为无 BOM + LF（前 3 字节 `2D 2D 20`、CRLF=0，正文原始字节相等），**并用修正后的文件重跑全部验证**——因为我此前那次 40/40 复现跑的是带 BOM 的旧文件，不重跑就等于主张与字节不符。

## 4. 集成后验证（均我亲自执行）

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python tests/engineering/T08/run_pg.py --evidence-name main-repro-2` | 0 | `totals={tests:40, failures:0, skipped:0}`，surefire 14+26；`mode=REAL_POSTGRES_INSTALLED_MIGRATIONS`（应用安装版 V1–V5，非草案）；`costTriggers` 3 个就位；随机端口 5465，`clusterStopped=true`；密码在证据内 REDACTED |
| `python tests/engineering/integration/formal.py --include-review-regressions --evidence-name t08-integration-core-v5lf` | 0 | 真实 PG + 真实 HTTP Session/CSRF 套件全绿，Flyway 干净库应用 V1–V5 |
| `mvn -B -ntp -o -f backend/pom.xml clean verify`（JDK 21） | 0 | BUILD SUCCESS，**265 项 0 失败 0 错误**（138 项 PG 门控离线跳过） |
| `python tests/engineering/T08/verify.py` | 0 | 11/11，含"只有功能开关、无编造额度、只绑 `CostPorts.Audit`、runner 已跟踪"与 V5↔草案字节比对 |
| `python tests/engineering/T02/check_contracts.py` | 0 | 27/27，无再生成 |
| `python tests/engineering/T03/check_session_cookie.py` | 0 | PASS（R04 闸门未受本次集成影响） |

环境事实：默认 `JAVA_HOME` 是 Zulu 17，被 enforcer 正确拦下（要求 [21,22)），须用仓库自带 `.tools/t02/jdk-21.0.12.1+1`。

## 5. 清理与残留

删除交付方无法删的三处未跟踪产物（删前逐一打印内容确认目标）：`tests/engineering/T08/build_classpath.py`（被 `run_pg.py` 取代的脚手架）、`backend/src/test/java/.../T08PostgresTest.java.evidence-note.txt`（自述 STRAY）、`tests/enginee…le`（文件名含 U+2026，实为它写错路径的 `.gitignore` 错位产物；正确的 `tests/engineering/T08/.gitignore` 已另行交付）。删后 `verify.py` 仍 11/11，无断言依赖被删文件。

## 6. 本次未证明（复审与后续必须知道）

- `GET /api/v1/usage` 的**真实 HTTP 端到端**未跑（登记 `openItems[COST-HTTP-E2E]`）；启用 cost 的组合根启动亦未跑，因为它需要第 2 节的产品额度。
- 完整多域套件仍因 T10/T11 未装而部分失败（`MULTI-DOMAIN-SUITE`），本轮用的是 core 套件 + T08 自有 runner。
- 崩溃灾备、真实供应商计费、`mvn verify` 在 CI 上的表现均未验证。全程离线 mock，无伪造探测。
- **T08 无独立复审**：本文与代码改动都出自"实施方＋集成方"同一侧，须由第一轮独立复审按边界差异复核，重点：advisory lock 顺序与死锁论证、BEFORE-INSERT 触发器与服务上限的一致性（绕过服务直接 INSERT 必须 23514）、UNKNOWN "先提交账本再回 409" 的语义是否可接受、幂等结算重放、`over_run` 单独报告路径、以及**审计只存 id/哈希、金额不进审计**这一决定是否被认可。

## 7. 第一轮复审结论与我的错误更正（同日补记）

复审方 `4e7342ba`（上下文隔离，与实施方和我均无关）判 **CHANGES_REQUIRED**：P1×2、P2×5、P3×5，交付在 `docs/execution/reviews/T08-round1/`。它对我做的审计取舍给出**可接受**结论（金额本就进不了 `char(64)`+hex CHECK 的审计列，`detail` 又被 CHECK 锁成 `{}`，事实链在 append-only 账本里），但抓到两条我漏掉的：

**F-01（P1）打的是我，不是实现。** `BudgetPolicyConfig:30-40` 十个键里 **8 个有回退值**，所以"打开开关也起不来"根本不成立。我核对 SRS 后确认那些值是**文档化示例值**（`:1099` 日预算示例 20 USD、`:1103` 的 30 / 40,000 / 3 / 1 / 2 / 4、`:1143` 预算 >80%），实施没有编造；**错在我的核实方式**——我读了 `application.yml`（确实只有开关）就断言"额度一个都没编"，却没读真正生效的 `BudgetPolicyConfig`。同一个假说法进了 `b3a909d` 的提交信息、本文件第 2 节和 `openItems[COST-BUDGET-LIMITS]`。提交信息不可改写，**在此明文撤回该句**，以本节与更正后的台账为准。教训已写进协议：功能开关的 fail-closed 语义要看**读取配置的那段代码**，不是看配置文件里有没有那个键。

**F-02（P1）。** `t08_admit_estimate` 的占用聚合原先既不 `FOR UPDATE` 也不取 advisory lock，READ COMMITTED 下两个绕过服务的并发直插互不可见 → 双双通过 → 超订；而三处注释把这事写成了"AC-28 的 DB 层不变量"。实施方选修法 (a)：先 `SELECT budget_limit … FOR UPDATE` 锁文章行再聚合（现 V5 第 86 行），并补两个 `session_replication_role=origin` 裸连接的并发对抗用例（断言恰好 1 提交、另 1 个 23514、占用 1.000000/1 行）；注释同步降级为"只复述文章上限，日预算/次数/Provider 配额属服务路径"。**修前的红是实测不是推理**：`tests/engineering/T08/evidence/t08-r1-baseline-gap-pre-fix.json`（mvn 命令退出码 1，命令退出序列 `[0,0,0,0,0,1,…]`，`clusterStopped=true`），我从被忽略的 `.work` **提升到跟踪路径**——留在 `.work` 里的失败记录对复审方等于不存在。`lastBalanceSingleWinner` 原先 `ready/start` 两个闩从未 `countDown/await`（同步是装饰），现已接上并跑 10 轮。

其余条目（死工厂 `noAudit()`、审计用例改走生产 `CostIntegration`、`over_run` 无外部投影、告警与 `pendingReconciliations` 无生产调用方、503 `EXECUTION_SCOPE_NOT_READY` 断言、`--expect-tests` 总数闸门、报告陈旧数字）见 `docs/execution/reviews/T08-round1/review.md` 与 `docs/execution/reports/T08.md`。我还纠正了自己一次误判：`CostPorts.java:72` 里 `noAudit` 只剩注释文字（"故意不提供 noAudit 工厂"），工厂确已删除——我最初的 grep 太粗，`verify.py:223` 是先剥 Java 注释再检查的。

整改后我的复现：`run_pg.py --expect-tests 44` → **44/0/0**（16 + 28）、`expectations.problems=[]`、`mode=REAL_POSTGRES_INSTALLED_MIGRATIONS`、`clusterStopped=true`，证据 `evidence/t08-r2-main-repro.json`；`verify.py` **13/13**；`verify.py --reverse-control` **18/18 REJECT（blind=none, misplaced=none）**；`check_contracts.py` **27/27**；草案与 V5 剥头 3 行后**原始字节仍相等**（13,119 B，sha `22d7fad3117ddd38ac9d…`，CR=0、无 BOM）。第二轮复审**尚未开始**，所以 T08 现在是 `CHANGES_REQUIRED（整改待复）`，不是 PASS。

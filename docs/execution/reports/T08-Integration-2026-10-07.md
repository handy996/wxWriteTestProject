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

1. **Flyway 全局版本号**：分配 **V5**，安装为 `backend/src/main/resources/db/migration/V5__cost_ledger_pricing.sql`，正文与其草案**原始字节等同**（12,774 = 12,774），仅替换头 3 行注释。
2. **`editorial.cost.*` 配置键**：只加功能开关 `editorial.cost.enabled: ${EDITORIAL_COST_ENABLED:false}`。**业务额度我一律不编**（daily-budget、各类次数/单元上限、alert-percent、provider-quota 均不写入）。缺键 fail-closed 是正确设计；数值属产品 Owner 决定，已登记 `openItems[COST-BUDGET-LIMITS]`，在拿到数值前启用 cost 必然启动失败——这是预期行为，不是缺陷。
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

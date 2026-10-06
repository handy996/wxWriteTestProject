# T05 第二轮独立审核

日期：2026-10-04（Asia/Hong_Kong）。对象：当前工作区的第一轮整改。上轮：[T05-Review-v1.0.md](T05-Review-v1.0.md)。

**结论：PASS。T05-R01–R07 全部 CLOSED；本轮没有发现需要整改的新增实现、测试或交付缺陷。结论覆盖 T05 当前工作区的任务实现及本轮整改验收，不代表 T03 已获批准、全 CI/G1、后续文章工作流集成或生产上线通过。**

## 1. 审核对象、依据及变更范围

- 分支仍为 `appmod/java-upgrade-20261003114404`；HEAD 仍为 `b115a4022375675c7cbff536b239508db8f3f4e1`，上一提交 `74c2525`。T05 原始实现与整改均未提交，没有可分别指代两者的 Git commit。
- [before.json](T05-round2/before.json) 固定本轮开始的 **777 个既有 Git 可见文件**的 SHA-256、Git 状态、分支与 HEAD；不能用 HEAD 单独标识审核对象。
- 对照第一轮 `after.json`：**14 个既有文件改变**，均在 T05 自有实现、资源、测试、迁移草案、测试编排及交付报告中；新增 SkillConfigDiff、三个测试类、整改报告/检查脚本与作者新证据。对照清单另包含第一轮自身报告和证据，它们在第一轮指纹中被有意排除，不应误算成实施 agent 新增的业务修改。详见 [input-comparison.json](T05-round2/input-comparison.json)。
- 作者 `revision-v1-final-checks.json` 声明的 **51/51 源码/资源/测试指纹与当前工作区匹配**。T02/T03/T04 的既有实现、共享构建、CI、根配置及正式迁移未因本次整改改变。
- 依据沿用第一轮 SRS/任务卡、共享所有权、rc.3 OpenAPI/Schema/端口/状态/表权限/hash/事务约定、ADR-001/004/005，以及第一轮七项关闭条件；新增读取 [T05-Revision-v1.0.md](../reports/T05-Revision-v1.0.md) 和更新后的交付报告，但没有让作者报告改变验收边界。
- 正式批准指纹 **27/27 匹配**，没有运行契约生成器；未发现新增适用 AGENTS.md。本轮不重读无关归档或重新审核其他任务。

## 2. 待修复问题

**无。** 本轮没有 OPEN 的 T05 阻断项，不新增问题编号，也不把其他任务的既有 CI/环境问题包装成 T05 缺陷。

## 3. 第一轮问题关闭情况

第一轮六个独立反例源 `T05-round1/ReviewCases.java` 在本轮隔离副本中**原样追加执行**，六项全部通过。旧版失败证据继续引用第一轮的固定工作区及真实运行记录，不声称本轮重新获取或运行了一个并不存在的旧 T05 提交。本轮同时阅读并运行作者新增的正反向回归，避免仅凭旧反例返回成功就关闭整个问题。

| 编号 | 状态 | 实现与关闭证据 |
|---|---|---|
| **T05-R01 / P1** | **CLOSED** | Writer 使用 `WriterOutput`，Reviewer 使用 `ReviewOutput`，Revision 使用 `writer/itemDecisions` 与 `itemId/disposition/reason`；Skill 清单同步。四个 Prompt 的名称、引用、输出层次与冻结定义一致，持久化包装字段明确由服务端提供。除项目单测外，本轮导出单测实际使用的四份固定样例，用 **CI 固定版本 jsonschema 4.26.0 / Draft202012Validator / FormatChecker** 独立验证：四份正例通过，每个顶层必填字段缺失及混入 `meta` 均按相应规则拒绝。未知 `$ref` 也有拒绝测试。证据：`standard-schema.json`、`model-samples.json`、PromptContractTest XML、第一轮 Writer 反例本轮通过。没有把样例通过称为真实模型质量通过。 |
| **T05-R02 / P1** | **CLOSED** | 三个触发器在所有状态固定 `id/created_by/created_at`；发布后通过整行 JSON 比较减去明确允许变化的列来保护内容和审计元数据。位置：`tests/engineering/T05/migration-draft.sql:87、92、111、116、135、140`。运行账号改三表主键均拒绝；扩展回归逐项修改内容、版本、创建/发布元数据，检查 **SQLSTATE P0001 与对应不可变错误信息**，并核对原行未变。合法草稿编辑、Skill 发布/退休、Policy 退休仍成功，历史读取保留。没有仅接受任意异常作为关闭证据。 |
| **T05-R03 / P2** | **CLOSED** | `CursorCodec.java:19–20、28` 签发和验证均使用编码后的 payload；`SkillService.java:148、164` 将规范化 status 纳入签名内容。真实 HTTP 正常下一页可读，Skill/版本以 limit=1 完整遍历集合，无重复和游标循环；篡改、跨 Owner、跨 status、跨 Skill 的游标均按预期错误码拒绝。第一轮正常翻页前置断言与后续过滤检查均通过，不再依赖“所有游标都失败”的假阳性。 |
| **T05-R04 / P2** | **CLOSED** | `SkillConfigValidator.java:63–65` 要求输出名称存在且与精确 Prompt 的 `$ref` 一致。作者夹具现在使用各 Agent 真实输出类型。不存在名称、存在但错绑另一输出类型在创建/编辑中返回 422 `PROMPT_OUTPUT_SCHEMA_INVALID`，数据库无非法新增/编辑；直接布置旧非法草稿后发布也按同一原因拒绝并保持 DRAFT。第一轮未知名称反例通过。 |
| **T05-R05 / P2** | **CLOSED** | `SkillService.java:142` 改用相应版本状态的 `EXISTS` 筛选，不依赖 activeVersionId，也不因多版本重复身份。真实测试覆盖纯草稿、已发布与多草稿并存、退休后状态；三种状态的逐页 HTTP 结果与独立数据库集合相等，另一个 Owner 的列表保持隔离。第一轮草稿反例通过。 |
| **T05-R06 / P2** | **CLOSED** | `PromptService.java:59`、`PolicyService.java:45` 分别按数字 major/minor/patch 降序并限制一行。两种服务的 `1.0.9 → 1.0.10 → 1.9.0 → 1.10.0 → 2.0.0 → 10.0.0` 回归通过，旧 ID 返回原版本；第一轮两个 1.0.10 断言均通过。 |
| **T05-R07 / P2** | **CLOSED** | 已提供 `SkillConfigDiff` 和 `SkillService.diff(actor, fromVersionId, toVersionId)`（第 199 行），先验证两个版本的 Owner，再要求同 Skill，返回精确版本 ID 与 JSON Pointer 差异。新增/删除/修改、数组顺序、路径转义、显式 null、相同配置及发布版/草稿对比均通过；任一输入越权均 404，不同 Skill 拒绝。没有新增或修改冻结 HTTP 端点，作为下游可复用内部比较服务满足本项关闭条件。 |

详细方法清单与计数见 [summary.json](T05-round2/summary.json)，真实运行日志和 JUnit 结果见 [host-current.json](T05-round2/evidence/host-current.json)、[host-current-test-results](T05-round2/evidence/host-current-test-results/)。实际执行的追加测试源保存在 [ExecutedT05PostgresTest.java](T05-round2/ExecutedT05PostgresTest.java)。

## 4. 独立验证、迁移及测试质量

| 检查 | 实测结果 | 证据 |
|---|---|---|
| 全新隔离副本 clean 编译及相关测试 | **50 执行 / 50 通过 / 0 failure、error、skipped；Maven 和编排器退出 0** | evidence/host-current.json、9 个测试类 XML |
| 其中业务回归 | 原有 31 项 + 作者新增 12 项 + 第一轮独立反例 6 项 = **49 项通过**；另 1 项仅导出实际样例供标准校验，不把导出当成额外业务验收 | summary.json |
| 标准 Schema 交叉核验 | 固定 jsonschema 4.26.0；四个模型输出正例及逐字段缺失/服务端包装负例通过 | standard-schema.json |
| 空库初始化 | 真 PG 17.11、真实 Flyway/T02 权限回调、T03 V1 草案 + T05 V2 草案；基线及四表初始化成功 | host-current.json |
| 带数据的依赖草案升级 | **1 项通过，退出 0**：先仅迁移至 T03 V1，写入既有用户行，再迁移 T05 V2；原行与 V1 完整 history 行不变，四张新表出现；再次 migrate 执行 0 项且全部 history 不变 | [upgrade.json](T05-round2/evidence/upgrade.json)、[ReviewMigrationUpgradeTest.java](T05-round2/ReviewMigrationUpgradeTest.java)、upgrade-test-results/ |
| 冻结契约指纹 | **27/27，退出 0** | checks.json |
| CI 同版本完整 Gitleaks | 8.30.1，退出 1；仅 **6 项已有 T02 指纹误报**，T05 和本轮审核证据零新增 | checks.json、gitleaks-findings.json |
| Git 空白检查 | 退出 0 | checks.json |
| 结束完整性/清理 | 777 个既有文件未变；三个本轮 PG 目录均无运行服务器；两次宿主测试端口可重新绑定；精确清理本轮数据库副本及临时校验器目录 | after.json、summary.json |

工具：Temurin JDK `21.0.12.1+1`、Maven `3.9.11`、PostgreSQL `17.11`、Python `3.12.14`、Gitleaks `8.30.1`、jsonschema `4.26.0`。沿用冻结构建依赖，不改 pom/锁文件或安装正式迁移。

主要复现命令（从项目根目录）：

```powershell
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' docs/execution/reviews/T05-round2/run_review.py --include-review-cases --evidence-name host-current
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' docs/execution/reviews/T05-round2/run_review.py --upgrade-only --evidence-name upgrade
```

如复现，请使用新的 evidence-name 保留已有记录。标准 Schema 校验需在本轮 `.work/schema-tools` 临时目录安装 CI 固定版本 jsonschema 后执行 `verify.py`；本次已清理该临时依赖，安装日志保存在 `schema-install-host.log`。

编排器经过阅读：复制 backend 时排除 target，真实启动本次 PG，使用真实身份/会话/CSRF/幂等路径。仍仅在副本中施加第一轮已说明的 T03 身份接线；报告与测试输出重定向到本轮目录，不运行作者会写回其 evidence 的检查脚本。实际 Maven 参数、工具版本、退出码及脱敏输出均在 JSON 记录中。没有复用旧构建、旧 XML 或旧运行日志作为本轮成功证据。

升级测试补的是**当前依赖草案到新增 T05 草案的真实数据保留路径**，没有伪造一个已批准的上一 T05 发布版。当前 T05 尚未正式合入，所以本次修改的是草案，不是改写已部署 Flyway 历史。正式集成版本上的升级与全局 FK 装配见下一节，不能被本测试自动替代。

沙箱第一次启动 PostgreSQL 因 restricted token 失败（`evidence/current.json`），按权限流程重试后成功；标准校验器在当前 Python 中缺失，sandbox 下载被网络权限拒绝，获准后只安装至本轮目录并成功运行。未把这两类环境失败归因于实现。没有收费 Provider 调用。

## 5. 保留的集成限制与范围说明

1. **正式集成仍需 T03 批准和主 agent 装配**：T03 当前仅有工作区实现/迁移草案，其损坏接线 patch 仍通过隔离副本的显式接线绕过。T05 正式全局迁移版本号、后置 FK、统一运行配置及“上一正式集成应用版本→新版本”升级尚无验收证据。它们是正式集成关口的条件，不能冒称已经完成；也不因当前尚无正式 T05 发布版而重新打开本轮已验证的草案修复。
2. **旧测试库不会被资源文件修改自动修好**：现有 seed 按自然键保留已发布版本，整改报告已明确不原地覆盖旧 Prompt/Skill。如果某环境已装入第一轮基线，发布升级必须新增不可变版本并显式接线，不能直接复用本轮空库结果。正式发布前需针对该实际部署基线设计和验证升级。当前没有已批准的这类正式部署对象，本轮不虚构其历史。
3. **T06/T11 集成未执行**：StyleSnapshot 组装、Owner 主动更换文章 Skill、新 generation/fencing/失效事务尚待后续装配。`ConfigChangeSink.InMemory` 仍是事件收集替身，不证明可靠投递、事务回滚隔离或崩溃恢复。更新后的交付报告已纠正“无替身”和“发布/退休即改变旧文章运行”的描述。单纯发布新 Skill 不得影响旧文章，仍为后续 AC-02 的必要集成验证。
4. **对象及真实模型边界不变**：PolicySnapshot.rules 的 ObjectRef 与 T04 实际读取适配未验证；本轮不测试 S3、真实 Provider、完整 Prompt Injection/工具权限、QA/审批/导出或人工内容质量。样例 Schema 通过不等于真实模型能力通过。未要求 T05 提前实现其他领域表或流程。
5. **整体 CI 没有通过**：完整 Gitleaks 再次仅命中 T02 既有 6 项指纹误报（不是发现真实凭证）。T02 最新 CHANGES_REQUIRED、T04 最新 S3 环境 BLOCKED 状态没有被本轮改变。依赖清单/CI 未因 T05 整改变化，未重跑无关远程依赖漏洞服务、前端、Docker 或压力测试。本报告的 PASS 只属于 T05 本轮范围。

## 6. 后续验收条件与收尾

没有要求实施 agent 再改一次的 T05 OPEN 项；后续若继续改动本轮受审源码、资源或迁移草案，应固定新的文件指纹，并按实际改动复核相关问题。正式集成时需补 T03 批准基线、全局迁移/FK/配置装配、适用部署版本升级，以及 T06/T11 的换 Skill 事务验证；这些条件不由本报告自动批准。

本轮没有修改业务实现、冻结契约、已有迁移、作者测试或历史证据，没有提交/合并/切换共享工作区。结束时 [after.json](T05-round2/after.json) 确认全部 **777 个既有文件内容未变**、HEAD/分支未变；[summary.json](T05-round2/summary.json) 记录临时服务均已停止，仅清理本轮创建的资源。

# T02 扫描整改与 T03–T07 正式集成记录

日期：2026-10-06（Asia/Hong_Kong）。本记录属于主集成版本，不改写各任务作者报告或独立审核结论。

## 版本边界

- 集成前的共享工作区已单独固定为提交 `ab956ec38406958a9428c0f189bc53f683e018ba`。它保存 T02 整改、T03–T07 交付、受审源码、草案、报告及历史成功/失败证据；该提交不表示 T03/T04/T07 已获完整验收。
- 正式迁移依次为 `V1__identity_audit_idempotency.sql`、`V2__skill_prompt_policy.sql`、`V3__article_job_version.sql`、`V4__change_proposal.sql`。各文件与上述提交中对应任务的迁移草案 **Git blob 字节一致**。T05 原工作树草案为 CRLF，Git 按既有 `.gitattributes` 保存为 LF；正式 V2 固定为该审核提交中的 LF 字节。不能在部署后改写 V1–V4，应通过新版本迁移修正。
- T06 的已受审 `ArticleService` 和共享 `CanonicalRequest` 原版保留在上述提交。正式集成版分别严格采用 T07 已复审的 `t06-extension.patch` 和 T06 的 `shared-integration.patch` 所声明变换。`ArticleIntegration`、`VersionIntegration` 与两份受审组合根文件字节一致。`verify_boundaries.py` 逐字节复核上述关系、T02 原迁移及旧 `r01-integrity.json` 均未变。集成版是新的版本，T06 原 PASS 不自动扩张至该版本。
- T03 原 `shared-integration.patch` hunk 损坏，不能直接应用；本次在 `SkeletonConfiguration` 中按身份启用标志停用临时拒绝链，并在 `application.yml` 配齐 T03 参数。集成路径由真实 HTTP Session/CSRF 测试覆盖。
- 本次集成还对四个 T07 具体 PG 测试类显式加环境门禁，避免 Maven 默认测试在没有 PG 时启动 Spring；T04 独立 HTTP 测试使用明确的测试用凭证和高优先级启用标志，以满足 T02 启动策略。原测试字节仍可在集成前提交取得，这些测试改动属于本次集成版本。

## 扫描整改和组合根

T02 R02 的 6 项均为旧 `r01-integrity.json` 中经过核对的文件 SHA-256。仅在该文件路径且 match 包含这六个精确值时豁免；默认 Gitleaks 规则和其他路径保持有效。没有重写原指纹清单或第二轮失败证据。使用仓库 `scan_secrets.py`、Gitleaks 8.30.1 和完整 Git 可见文件集复扫，退出 0、0 告警。历史 T04 测试对象 UUID 的原精确例外保持原样。

组合根安装在 `bootstrap/`，通过 `EDITORIAL_IDENTITY_ENABLED=true`、`EDITORIAL_STORAGE_ENABLED=true`、`EDITORIAL_ARTICLE_ENABLED=true`、`EDITORIAL_VERSION_ENABLED=true` 显式启用 T03 身份、T04 存储、T06 文章和 T07 版本。须同时提供有效 `APP_ORIGIN`、Owner 初始化凭证、数据库三角色凭证和 `AUDIT_CURSOR_KEY`，并继续只选择 T02 的单一运行 profile（如 `mock`）。默认骨架仍由 T02 的拒绝链处理。T10/T11 及引用验证的缺失适配仍返回明确未就绪错误，不能将此版本当作完整编辑工作流。

## 实测结果

| 检查 | 结果 | 记录 |
|---|---|---|
| Java 21 正式源码打包 | 81 个生产源文件编译，退出 0 | 本轮 Maven 离线 `package -DskipTests` |
| 默认后端测试路径 | **219 项：109 通过、110 按真实 PG 条件跳过，0 失败/错误**；退出 0 | Maven 离线 `test`，工作区临时目录；真实 PG 项另见下方两轮 |
| 正式 V1–V4 空库、组合根、HTTP Session/CSRF、Local ObjectStore | **73/73**，失败/错误/跳过均 0；PostgreSQL 清理退出 0 | [最终运行记录](../../../tests/engineering/integration/evidence/formal-clean-post-ci.json) 和同名 JUnit 目录 |
| V1–V3 既有用户、Skill、文章和 Original 数据升级至正式 V4 | **1/1**，旧行及旧 Flyway history 不变，二次迁移 0；清理退出 0 | [最终升级记录](../../../tests/engineering/integration/evidence/formal-upgrade-post-ci.json) 和同名 JUnit 目录 |
| T05 独立真实 PG/HTTP 回归 | T05 **24/24**，另 4 项 T07 边界测试通过；清理退出 0 | [运行记录](../../../tests/engineering/integration/evidence/formal-skill-01.json) 和同名 JUnit 目录 |
| 受审边界、冻结契约、密钥、空白 | 逐字节边界检查通过；T00 rc.3 **27/27**；完整 Gitleaks **0 告警**；`git diff --check` 通过 | `verify_boundaries.py`、`check_contracts.py`、`scan_secrets.py` |

上述 PG 运行使用隔离的随机数据库集群和本地对象目录；测试中的 T10/T11 事务参与者与引用适用性替身仍为替身。首次沙箱运行因 Windows restricted token 无法启动 PG，后续在宿主隔离运行并保存 [失败记录](../../../tests/engineering/integration/evidence/formal-clean-01.json)。一次将 T03/T04/T05 所有历史测试夹具并入同一数据库的探索运行有 **129 项中 9 失败、7 错误**，主要是 T03 fixture 路由与真实文章路由冲突、T04 最小手建 schema 与正式 V1 schema 不同及测试间数据干扰；保留 [原始记录](../../../tests/engineering/integration/evidence/formal-all-domains-01.json)，不把它计为通过，也不以改写旧测试掩盖差异。正式组合根的 T03 会话、审计、幂等及 T04 Local 存储已由上述 73 项真实跨域测试覆盖。

## 未闭合条件

- T03 尚无独立批准记录；本次验证其接线与组合行为，不替它补签审核。T04 真实私有 S3 桶端到端验收仍 BLOCKED。当前 T07 组合根仅允许 Local 后端执行版本写入；S3 事务内对象提交问题及真实桶验证仍待处理。
- T07 代码整改复审通过，但 CR-T07-01 仍 OPEN：冻结 Diff 最多返回 1,000 项，而合法 AST 可有 30,000 块；超限返回 `DIFF_TOO_LARGE`，不能宣称任意合法版本 Diff 的 AC-19 完整通过。
- T10/T11 的真实 generation/fencing、可靠失效与崩溃恢复，T16/T19 Claim/Slot 引用适用性、QA/Approval/导出联动均未实现。本轮没有真实收费 Provider 调用，也没有远端 GitHub Actions 运行或生产上线批准。
- 旧 canonical 非 BMP/控制字符历史数据及幂等 hash 的兼容盘点尚未完成；已存不可变行不得原地改写。正式部署前须核实既有数据和调用方。集成配置须按环境补齐凭证与 Local 存储路径；未提供时不应启用四项集成开关。

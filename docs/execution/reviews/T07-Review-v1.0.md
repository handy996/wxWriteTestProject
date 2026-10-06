# T07 第一轮独立审核

结论：**CHANGES_REQUIRED（需修改）**。日期：2026-10-06（Asia/Hong_Kong）。本轮发现 **2 项 P2 问题，均以独立测试复现**；T07 暂不批准。另保留已登记的 CR-T07-01 容量契约缺口，不能将“任意合法版本 Diff”标为完整验收通过。

## 1. 审核对象与基线

审核当前共享工作区的 [T07 交付报告](../reports/T07.md)、版本/提案代码、迁移草案、T06 扩展和组合根补丁。HEAD 为 `b115a4022375675c7cbff536b239508db8f3f4e1`，并非 T07 交付提交。本结论绑定 [input-snapshot.json](T07-round1/input-snapshot.json) 的 21 项 `reviewedFiles`。

独立核对：1,151 个既有输入未变；T06 第四轮 26 条受审指纹记录未变（对应 20 个不同文件）；21 项 T07 交付指纹匹配。结束复核见 [summary.json](T07-round1/summary.json)。本轮只新增审核报告、脚本、反例和执行证据，没有改动实施代码、作者证据、历史审核结论或冻结契约，没有安装共享补丁、分配正式迁移编号或提交 Git。

## 2. 必须修改的问题

### T07-R01 · P2 · 保留候选的 stale 没有传递给通用引用解析

位置：[t06-extension.patch](../../../tests/engineering/T07/t06-extension.patch:29)；关联原服务 [ArticleService.resolve](../../../backend/src/main/java/com/example/editorial/article/job/ArticleService.java:228) 和 [Ownership.require](../../../backend/src/main/java/com/example/editorial/shared/Ownership.java:23)。

T07 扩展首次创建 `meta.stale=true` 的保留候选，但没有同步扩展 T06 的 `VERSION` 引用解析。现有 resolver 仅以 `article_job.deletion_pending` 填充 `ArtifactRef.stale`，忽略版本自身的持久化 stale。因此，同一个版本经详情读取明确为 stale，经 `Ownership.require(..., newCommit=true)` 却作为有效输入通过。冻结 `ports.json` 明确要求拒绝 stale 输入的新提交，同时允许历史读取。

独立反例 `reviewRetainedVersionMustBeStaleForNewCommit` 先通过真实版本服务持久化保留候选，确认返回的 `meta.stale=true`，再使用真实 T06 resolver 和 shared Ownership 校验：历史读取通过符合预期，要求新提交时本应返回 `409 STALE_INPUT`，实际没有抛错。执行来源使用已披露的 T10 事务替身；版本持久化、resolver 和 Ownership 均为真实实现。

影响是通用新提交引用边界不能区分已标记过期的候选与有效版本。本轮没有据此宣称未就绪的导出/审批模块已发生错误放行，也没有发现晚到结果直接覆盖人工头；已验证的“不可覆盖头”测试仍通过。

修复要求：通过最小 T06 扩展补丁，把版本的持久化 stale 与删除状态正确传给适用的版本引用解析；核对 `VERSION_OBJECT` 的对应引用语义。不得直接覆盖已批准 T06 原文件。补充真实 resolver 回归：过期候选新提交拒绝、历史读取仍可用、正常有效版本不受影响、删除守卫保留。显式人工接受提案应继续走其专用前置校验并创建新版本，不应简单封禁一切候选读取。

### T07-R02 · P2 · usedClaimIds 在暂存后的提交事务中漏检

位置：[VersionService.java](../../../backend/src/main/java/com/example/editorial/article/version/VersionService.java:81)，关联第 64 行及 [VersionPorts.References](../../../backend/src/main/java/com/example/editorial/article/version/VersionPorts.java:21)。

`commit` 在事务外遍历 `WriterOutput.usedClaimIds` 并调用引用适用性校验；对象暂存完成、重新取得文章锁之后，只通过 `validate(contentAst, ...)` 复核正文块中的 `claimRefs`。冻结 Schema 和当前代码允许某个已用 Claim 仅在 `usedClaimIds` 中出现，例如标题使用的事实。若该 Claim 在暂存期间失效，最终事务不会再查询它，仍可追加版本、移动头并记录执行完成。这违反该端口自身“提交锁内再次校验”的约定，也与全部输出引用需要校验的要求不符。

独立反例 `reviewUsedClaimMustBeRecheckedAfterStaging` 使用合法 WriterOutput：一个 used Claim、正文无 claimRefs。引用适用性替身在准备前允许该 Claim，实际 Local staging 完成后切换为失效；真实 Store、版本事务和持久化路径继续执行。本应抛出 `STALE_INPUT` 并保持业务结果不变，实际提交成功，`assertThrows` 失败。这证明 T07 没有再次调用校验端口；它不是 T16 已完成或真实 Claim 数据库失效传播的证据。

修复要求：最终提交事务内、任何版本/工作头/执行结果写入之前，对完整 `usedClaimIds` 再次执行引用适用性校验，兼顾每次重新暂存后的提交尝试，不仅校验 AST 子集。保留执行结果幂等重放的既定顺序。补充屏障用例，验证失效 Claim 被拒绝，版本、头、提案状态、审计及执行完成记录不发生部分提交；同时验证未失效引用正常成功。

两项原始反例均保存在 [ReviewVersionBoundaryTest.java](T07-round1/ReviewVersionBoundaryTest.java)。[独立执行记录](T07-round1/evidence/review-regressions.json) 和 [JUnit](T07-round1/evidence/review-regressions-test-results/TEST-com.example.editorial.article.version.ReviewVersionBoundaryTest.xml) 记录 **2 tests / 2 failures / 0 errors / 0 skipped，Maven 退出 1**。失败原因均为预期拒绝而实际未拒绝，不是环境或编译失败。后续修复请另建证据，不覆盖本轮失败记录。

## 3. 独立验证结果

| 检查 | 本轮实际结果 |
|---|---|
| 交付方用例独立 clean test | **67/67 通过**，0 failure/error/skipped；T07 19 项，T06/共享及前三轮原始 Markdown 回归 48 项 |
| 审核新增边界反例 | **2/2 失败**，对应 R01/R02，不能计入通过结果 |
| 含 T03/T05/T06 旧数据的迁移升级 | **1/1 通过**，0 failure/error/skipped |
| 实际响应标准 JSON Schema | **11/11 通过**，jsonschema 4.26.0，Draft 2020-12 + FormatChecker |
| T00 rc.3 冻结保护 | **27 项通过** |
| T06 扩展、T07 组合根、T06 共享 patch 可应用性 | 全部通过；只在隔离副本接线，未合入共享源码 |
| Git diff 空白检查 | 通过 |
| Git 可见文件密钥扫描 | Gitleaks 退出 **1**，仅 T02 原有 6 条指纹误报，新增 0；不是整体 CI 通过 |
| 输入/交付完整性 | 既有输入、T06 受审记录和 T07 21 项交付指纹均未变 |
| 临时 PostgreSQL | 三次运行均已成功停止，最后 pg_ctl stop 退出 0；隔离副本保留在本轮忽略目录 `.work/` |

证据：[67 项运行](T07-round1/evidence/author-tests.json)、[升级运行](T07-round1/evidence/upgrade.json)、[契约/Schema/扫描/完整性检查](T07-round1/evidence/checks.json)、[结束汇总](T07-round1/summary.json)。校验器中的 `failures=[]` 仅表示上述基础检查及两组预期成功运行通过，**不包含独立反例，不代表 T07 通过**。

测试运行于独立 PostgreSQL、真实 HTTP Session/CSRF、Local ObjectStore，使用交付声明的 T10/T11 事务参与者替身；R02 另加入明示引用适用性替身。沿用披露的 T03 损坏接线补丁等价转换、T06 canonical 修补、T06/T07 组合根及 T06 接口扩展。每组记录含实际命令、退出码、执行副本指纹、样本与 JUnit。审核包装器只重定向工作和证据目录、加入审核测试及选择测试集，没有替换生产算法或降低原断言。

复跑审核反例（仓库根目录，需要允许启动本机临时 PostgreSQL，使用新的 evidence-name）：

```powershell
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' docs/execution/reviews/T07-round1/run_review.py --regression --evidence-name review-after-fix
```

## 4. 尚未闭合的验收边界

**CR-T07-01 保持 OPEN。** 冻结 ContentAst 最多 30,000 块、Diff.blocks 最多 1,000 项且无分页；当前算法还输出标题、副标题及未变化块，超过容量返回 422。交付已明确登记，没有截断结果或擅改冻结契约，这点处理可接受；但“任意合法版本 Diff”的需求仍未闭合。后续需由主 agent/T00 给出容量/分页或需求范围的正式决定，实施方不得自行放宽冻结 hash。本轮不把这一已披露的契约冲突冒充为新的未披露代码缺陷，也不批准完整 AC-19。

缺失 T10/T11 真实适配时明确拒绝、Local 存储限制及其他依赖边界与派发卡一致，不仅因为这些已授权替身/缺依赖拒绝而退回。仍未证明真实调度 fencing、可靠失效/outbox、Claim/Slot 适用性、QA/Approval/导出联动、真实 S3 提交和崩溃恢复。T03 正式批准/共享接线、canonical 历史兼容、T37 删除屏障及正式迁移编号也不在本轮获批范围。

下一轮须关闭 R01/R02，保留原始反例并补足修复回归；凡修改 T06 扩展，复跑相关 T06 已通过测试和 patch/契约/扫描检查。当前 T06 第四轮 PASS 仍只绑定其原受审字节，不能自动延伸到本次尚未批准的组合。

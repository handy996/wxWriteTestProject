# T07 第二轮独立审核

日期：2026-10-06（Asia/Hong_Kong）。结论：**本轮整改复审 PASS；T07-R01、T07-R02 关闭，当前代码审核 OPEN 项为 0。** 本轮未发现新增代码问题。

**T07 完整验收尚未批准。** CR-T07-01（合法大容量 AST 与 Diff 返回容量冲突）仍为 OPEN，“任意合法版本 Diff”及完整 AC-19 不能标为通过。真实跨域依赖、正式接线、整体 CI、G2 和生产上线也不随本轮通过。

## 1. 受审范围与完整性

本轮审核 [T07-Revision-v1.0](../reports/T07-Revision-v1.0.md) 对第一轮两项问题的修复。当前 HEAD 仍为 `b115a4022375675c7cbff536b239508db8f3f4e1`，交付为共享工作区文件，不是新的 T07 提交。

核对修订输入的 1,437 个文件，既有文件仅以下四项发生已声明修改：VersionService.java、extend_t06.py、t06-extension.patch、integration.py。修订声明的 7 项文件指纹全部匹配；结合第一轮未改文件，本轮受审交付共 24 项，绑定 [input-snapshot.json](T07-round2/input-snapshot.json) 的 `reviewedFiles`。

原 T06 第四轮 26 条受审指纹记录保持不变；第一轮审核报告、原始反例及失败证据均未覆盖。检查了补丁文本与生成器结果、实际执行副本的一致性；第一轮反例逐字复制到隔离副本，断言未修改。结束复核见 [summary.json](T07-round2/summary.json)。

本轮只新增审核方报告、包装脚本和证据，未修改实施源码或作者材料，未安装共享补丁、执行正式迁移或提交 Git。

## 2. 问题关闭依据

### T07-R01：关闭

T06 扩展补丁现在使 `VERSION` 引用的 stale 取文章删除状态与版本持久化 `meta.stale` 的逻辑或。真实 Ownership 在新提交引用过期候选时返回 `409 STALE_INPUT`，历史读取仍可进行。第一轮原始反例 `reviewRetainedVersionMustBeStaleForNewCommit` 独立复跑通过。

新增回归使用真实 PostgreSQL、T06 resolver、shared Ownership 和 Local ObjectStore，确认有效 Original 可作为新输入、保留候选的 VERSION 历史读取暴露 stale、新提交拒绝；候选实际物理对象仍完成 COMMITTED 登记且字节一致。删除状态对 Original/候选的 VERSION 和 VERSION_OBJECT 新引用都保持拒绝。原有提案接受测试继续通过：人工按专用前置条件接受候选后创建新的有效版本，没有直接修改旧候选。

本轮接受 `VERSION_OBJECT` 的限定解释：它服务于历史字节的物理引用提交，不表示正文能作为新的业务输入。真实 ObjectStore.commitReference 会执行 newCommit 校验，若不区分两者，过期候选自身的历史存储会被阻断。当前补丁继续对物理引用执行删除守卫；后续业务适配必须使用 VERSION 校验正文适用性，不能以 VERSION_OBJECT 代替。

### T07-R02：关闭

[VersionService 的实际差异](T07-round2/VersionService.diff) 在最终事务取得文章锁、执行检查和已有结果重放之后，新增完整 `usedClaimIds` 的引用复核。该检查在 append、moveHead、提案失效和 execution.complete 之前，并位于每次重新暂存后的提交路径内。原有 AST 引用校验保留。

第一轮原始反例 `reviewUsedClaimMustBeRecheckedAfterStaging` 独立复跑通过。新增边界回归进一步证明：

- 仅存在于 usedClaimIds 的 Claim 在 staging 后失效，返回 STALE_INPUT；Job、版本、提案、文章级审计、执行完成和失效参与者业务快照均未改变。
- 同一执行在引用恢复适用后可以成功提交，并正确固定执行结果、失效旧提案。
- 注入一次 RESTAGE_REQUIRED 后，第二次 staging 的引用失效仍被识别，业务快照保持不变。
- staging 后另一提交已完成同一执行时，最终事务先重放该结果；新增校验不会制造重复版本或打断这个既有重放分支。

引用适用性和调度仍使用明示替身，证明的是 T07 的端口调用、锁内次序和原子边界，不是实际 T16 失效传播或 T10 调度已实现。本轮也不扩张结论为所有尚未实现依赖下的幂等语义保证。

## 3. 独立验证

| 检查 | 结果 |
|---|---|
| 隔离 clean test | **73/73 通过，0 failure/error/skipped** |
| 原交付回归 | 67 项通过，其中 T07 19 项，T06/共享及历史 Markdown 反例 48 项 |
| 第一轮原始反例 | **2/2 通过**，源码字节与第一轮一致 |
| 新增修订边界回归 | **4/4 通过**，按方法筛选，未重复计算继承的测试 |
| 实际响应标准 Schema | **11/11 通过**，jsonschema 4.26.0、Draft 2020-12、FormatChecker |
| 冻结契约保护 | T00 rc.3 **27 项通过** |
| 补丁可应用性 | T06 扩展、T07 组合根、T06 共享补丁均通过；实际 T06 执行副本与补丁生成结果一致 |
| Git diff 空白检查 | 通过 |
| Git 可见文件密钥扫描 | Gitleaks 退出 **1**，仅 T02 原有 6 条指纹误报，新增 0；不代表整体 CI 通过 |
| 迁移升级 | 本轮迁移及组合根未改，沿用第一轮审核方独立 **1/1** 成功证据，**未在本轮重复执行或计入 73 项** |
| 清理 | 本轮临时 PostgreSQL 已停止，pg_ctl stop 退出 0；隔离副本保留在本轮 `.work/` 忽略目录 |

证据：[运行与命令记录](T07-round2/evidence/current.json)、[JUnit](T07-round2/evidence/current-test-results/)、[Schema/契约/扫描检查](T07-round2/evidence/checks.json)、[结束汇总](T07-round2/summary.json)。升级复用来源为[第一轮独立升级记录](T07-round1/evidence/upgrade.json)，检查记录中的 `prior-upgrade` 明确对应该历史运行。

使用真实 PostgreSQL、HTTP Session/CSRF、Local ObjectStore，以及交付声明的 T10/T11 事务参与者与引用适用性替身。保留原先披露的 T03 损坏补丁等价接线、T06 canonical 修补及 T06/T07 组合根，全部只应用于隔离副本。审核包装器仅重定向工作与证据目录；执行副本指纹和转换说明均记录在运行证据中。

复跑命令（仓库根目录，需本机临时 PostgreSQL 启动权限，使用新的 evidence-name）：

```powershell
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' docs/execution/reviews/T07-round2/run_review.py --include-review-regressions --evidence-name next-review
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' docs/execution/reviews/T07-round2/verify_review.py --run next-review --upgrade prior-upgrade --evidence-name next-checks
```

## 4. 后续验收边界

CR-T07-01 仍需主 agent/T00 正式决定容量、分页或需求范围。本轮接受交付方明确拒绝超容量 Diff、保留契约缺口的处理，没有批准它等价满足“任意合法版本 Diff”，也未授权实施方自行改冻结 Schema/hash。

T10/T11 真 fencing/可靠失效、T16/T19 Claim/Slot 适用性、QA/Approval/导出联动、S3 事务提交、崩溃恢复、T03 正式接线和 canonical 历史兼容等原有限制继续保留。T06 原 PASS 仍只绑定原受审字节；本次只证明新增补丁在已披露组合和回归范围内通过，不代表共享生产接线已合入。

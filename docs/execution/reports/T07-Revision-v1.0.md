# T07 第一轮审核整改交付

日期：2026-10-06（Asia/Hong_Kong）。回应 [T07-Review-v1.0](../reviews/T07-Review-v1.0.md) 的 **T07-R01 / P2、T07-R02 / P2**。状态：**提交主 agent 独立复审**，不自行关闭审核项或批准 T07/G2。CR-T07-01 保持 OPEN，未改冻结契约或宣称“任意合法版本 Diff”完整验收。

## 1. R01：版本引用正确暴露持久化 stale

通过 [t06-extension.patch](../../../tests/engineering/T07/t06-extension.patch) 扩展 `ArticleService.resolve`：`VERSION` 的 `ArtifactRef.stale` 取 `article_job.deletion_pending OR article_version.document.meta.stale`。真实 shared Ownership 在 `newCommit=true` 时据此返回 **409 STALE_INPUT**；历史读取 `newCommit=false` 仍可使用同一不可变版本。正常 Original/有效版本的行为保持不变。

`VERSION_OBJECT` 是 T06/T04 内部的物理对象引用，hash 对应完整存储 JSON，负责把包括过期候选在内的历史字节登记为已提交对象；它不表示正文可作为新业务输入。因此该种引用仍由 deletion_pending 控制，不附加正文语义 stale。否则候选会在自身 ObjectStore.commitReference 时被拒绝，无法按要求保存历史。新业务输入必须解析 `VERSION`，不能拿 `VERSION_OBJECT` 替代版本适用性校验。删除状态对两种引用的新提交都继续生效。

补丁生成器 [extend_t06.py](../../../tests/engineering/T07/extend_t06.py) 对原 resolver 字节增加精确匹配检查，输入不同即失败。**已批准 T06 原源码、T03 Ownership 与 T04 存储源码均未修改**；变更只应用在隔离测试副本，仍需主 agent 审核合入。

新增真实 PG/Local/resolver 回归覆盖：有效版本的新引用通过；候选 VERSION 历史读取返回 stale、新提交拒绝；候选实际对象成功 COMMITTED 且字节一致；删除后 Original 和候选的 VERSION/VERSION_OBJECT 新提交均被拒绝。原有显式接受提案测试保持通过：可读取候选，专用前置校验后创建新的有效版本，不直接把过期候选改为有效。

## 2. R02：最终事务复核完整 usedClaimIds

[VersionService.java](../../../backend/src/main/java/com/example/editorial/article/version/VersionService.java) 在最终提交事务中、取得文章锁并检查执行后，遍历完整 `WriterOutput.usedClaimIds` 再次调用 References，随后保留原 AST claimRefs 校验。位置在任何 append、moveHead、提案失效或 execution.complete 之前；每次 RESTAGE_REQUIRED 后的提交尝试都会重新经过校验。

已完成执行的 resultVersion 重放判断仍在新增校验之前。没有把原本能够重放的已完成结果转成一次新提交，也没有改动 ETag/base/fence 顺序。

新增具名引用适用性替身与真实 PG/Local 组合测试：

- Claim 仅出现于 usedClaimIds、正文无 claimRefs；真实 staging 完成后将适用性切为失效，提交返回 STALE_INPUT。对比完整业务快照，Job、版本、提案及其状态、文章级审计、执行结果和失效参与者测试行均未改变。独立 OBJECT_STAGED 元数据和可回收暂存对象不被冒称为业务成功。
- 同一执行在引用恢复适用后正常提交；提案按新头失效，执行 result_id 固定为新版本。
- 注入一次 RESTAGE_REQUIRED，第二次 staging 后引用失效，证明每个提交尝试都复核完整引用，不只复核第一次。
- 在 staging 后由另一提交完成同一执行，再使引用失效；外层请求重放已有结果，未追加重复版本，也未在重放前重新校验。

引用有效性、重新暂存竞争和 T10/T11 参与者仍是明示测试替身。本次证明 T07 正确调用和原子边界，不代表真实 T16 Claim 失效传播、调度或可靠 outbox 已实现。

## 3. 实际结果与证据保护

| 检查 | 结果 |
|---|---|
| [隔离 clean test](../../../tests/engineering/T07/evidence/revision-v1-first.json) | **73/73 通过，0 failure/error/skipped**：原交付 67、第一轮原始反例 2、新增边界回归 4。Maven/runner 均退出 0，临时 PostgreSQL stop 退出 0。 |
| T06 受影响回归 | 原 48 项全部通过，包含 AST、真实 PG/HTTP/Local、前三轮原始 Markdown 反例、删除协议替身及共享 canonical。 |
| [JUnit](../../../tests/engineering/T07/evidence/revision-v1-first-test-results/) | 原始 ReviewVersionBoundaryTest 2/2、新增 T07RevisionBoundaryTest 4/4；按方法过滤，未把继承的作者测试重复计数。 |
| 标准 Schema / 冻结保护 / patch | 11 份真实样本通过；T00 rc.3 27 项保护；T06 扩展/T07 组合根/T06 共享 patch 可应用；Git diff 空白检查通过。详见下面修订检查。 |
| 原输入与审核证据 | [revision-v1-input.json](../../../tests/engineering/T07/evidence/revision-v1-input.json) 固定开工时 1,437 个文件。只修改四个已明确列出的实施文件；原报告、原始审核反例及 2/2 失败证据、T06 受审原文件均保持原字节。 |
| 密钥扫描 | Gitleaks 原配置、Git 可见文件扫描退出 1，仅 T02 既有 6 条指纹误报；本轮新增 0。不宣称整体 CI 通过。 |
| 迁移升级 | 本轮未改迁移或组合根，未重复执行升级；保留此前 [upgrade-final.json](../../../tests/engineering/T07/evidence/upgrade-final.json) 的 1/1 证据，明确不是本轮新执行。 |

最终 [revision-v1-checks.json](../../../tests/engineering/T07/evidence/revision-v1-checks.json) 记录允许变更列表、历史证据保护、原始审核反例逐字复制、补丁与实际执行副本一致性、修订文件指纹及子命令退出码；其 [delivery 检查](../../../tests/engineering/T07/evidence/revision-v1-checks-delivery.json) 保存完整契约/Schema/扫描结果。指纹全部使用 path/sha256 分字段。原 T07.md 及上一轮 final-checks 没有重写，新结论绑定本修订证据。

本轮修改的既有文件只有：VersionService.java、extend_t06.py、t06-extension.patch、integration.py。新增 T07RevisionBoundaryTest.java、verify_revision.py、本修订报告及新证据。没有提交 Git，没有改主 agent 审核结论，没有安装共享补丁。

复现命令（仓库根目录，需要本机临时 PostgreSQL 启动权限；使用新的 evidence-name）：

```powershell
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' tests/engineering/T07/integration.py --include-review-regressions --evidence-name revision-reviewer-run
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' tests/engineering/T07/verify_revision.py --run revision-reviewer-run --evidence-name revision-reviewer-checks
```

工具及隔离接线沿用原交付。runner 复制未修改的第一轮审核反例到新副本并执行；原 `docs/execution/reviews/T07-round1/` 内无任何写入。检查器严格传播子命令失败，并验证两项原反例和四项新增回归的实际 JUnit，不能因基础检查通过而漏计反例失败。

## 4. 复审范围

R01/R02 的修复和自测已交付，请主 agent 独立复审后决定是否关闭。CR-T07-01、大 Diff 的 422 边界、T10/T11/T16/T19 真适配、S3 事务提交、QA/Approval/导出联动、崩溃恢复、T03 正式接线及 canonical 历史兼容限制均未被本轮测试解除。T06 第四轮 PASS 仍仅绑定其原受审字节。

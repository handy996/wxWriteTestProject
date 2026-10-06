# T07 第二轮审核后修复交付

日期：2026-10-06（Asia/Hong_Kong）。针对 [T07-Review-v2.0](../reviews/T07-Review-v2.0.md) 唯一剩余的 CR-T07-01，提供可读取完整合法大版本差异的分页接口。T07-R01、T07-R02 已由审核方关闭，本轮未再修改其实现或审核证据。本报告是实施方交付记录，不自行宣布 CR-T07-01、完整 AC-19、G2 或上线通过。

## 修复与版本边界

[增量决议](../contracts/CR-T07-01-diff-pages-v1.1.md) 保留冻结的 `GET /api/v1/articles/{id}/diff` 与原 `Diff` 响应：超过 1,000 行继续明确返回 `422 DIFF_TOO_LARGE`。新增 `GET /api/v1/articles/{id}/diff/pages`、[DiffPage v1.1 Schema](../../schemas/diff-page-v1.1.schema.json) 和 [增量 OpenAPI](../../api/diff-pages-v1.1.openapi.yaml)。单页最多 100 行；客户端沿 `nextCursor` 读取至 `null` 即得到完整差异。行顺序保持 title、subtitle、目标版本块、源版本已删除块。两端各 30,000 块时最多 60,002 行。

`VersionDiff` 建立源块位置索引和删除列表，按页构造差异行；旧路由继续按同一顺序生成不超过 1,000 行的冻结响应。`VersionService` 先按调用者身份读取两份不可变版本，再验证游标；签名游标绑定 Owner、文章、两个版本及页大小。没有新增迁移或数据库写入。

以集成基线提交 `5413cf4` 为本轮起点，改动仅限 T07 Diff 实现与对应测试、上述增量契约、校验器、证据和本报告。已批准的 T00 rc.3 文件及哈希、T06 原受审文件、T07 两轮审核原件均未覆盖。本轮交付应作为独立提交保留这一边界。

## 验证

| 检查 | 结果 |
|---|---|
| 最大合法 AST 单元回归 | 源、目标各 30,000 个互异块；冻结接口明确拒绝超容量，分页的 `totalBlocks=60002`，首、中、末页顺序与内容正确。 |
| [真实 PostgreSQL/HTTP 集成](../../../tests/engineering/integration/evidence/t07-diff-page-01.json) | **75/75 通过，0 failure/error/skipped**；临时 PostgreSQL 停止成功。以 Session/CSRF 保存超过 1,000 行的版本，逐页读完 1,004 行且无重复，验证旧接口错误、游标签名篡改、版本及页大小重绑、跨 Owner 隐藏。实际响应保存在 [DiffPage.json](../../../tests/engineering/integration/evidence/t07-diff-page-01-samples/DiffPage.json)。 |
| [Schema/OpenAPI/冻结保护](../../../tests/engineering/T07/evidence/diff-page-v1.1-check-final.json) | 标准 Draft 2020-12 Schema 验证实际 HTTP 响应；OpenAPI 3.1 校验通过；T00 rc.3 **27/27** 哈希一致。复跑工具为 [verify_diff_page.py](../../../tests/engineering/T07/verify_diff_page.py)。 |
| 全量后端默认测试 | **222 项，0 failure/error，112 skipped，BUILD SUCCESS**。跳过项为需正式 PostgreSQL 环境的测试；上述隔离集成已单独运行并计入 75 项。 |

隔离集成沿用已合入的 T03–T07 组合根，使用真实 PostgreSQL、HTTP Session/CSRF 和 Local ObjectStore。T10/T11 生产参与者尚未安装，相关事务测试使用显式替身；因此本轮不能扩张为真实跨域接线、可靠失效或生产部署的通过证据。

## 待独立复审

请审核方核对增量契约是否足以关闭 CR-T07-01，并复核最大容量、分页完整性、游标作用域和旧接口兼容。原 [T07-Review-v2.0](../reviews/T07-Review-v2.0.md) 的完整验收未批准结论在独立复审前仍有效。T10/T11/T16/T19、QA/Approval/导出联动、S3 事务提交和崩溃恢复等原有依赖不因本修复自动关闭。

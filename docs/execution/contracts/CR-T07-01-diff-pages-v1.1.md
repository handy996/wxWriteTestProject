# CR-T07-01：大容量版本 Diff 分页扩展

状态：**已实现，待独立复审**。决议日期：2026-10-06（Asia/Hong_Kong）。本文件是 T00 rc.3 之后的增量契约，不修改 `T00-rc3-approval.json` 所批准的文件或哈希。

## 决议

保留原 `GET /api/v1/articles/{id}/diff` 和冻结 `Diff` 结构。它对超过 1,000 行的结果继续返回明确的 `422 DIFF_TOO_LARGE`，不会静默截断。新增 `GET /api/v1/articles/{id}/diff/pages`，响应为 [DiffPage v1.1](../../schemas/diff-page-v1.1.schema.json)，接口参数及错误见 [增量 OpenAPI](../../api/diff-pages-v1.1.openapi.yaml)。客户端需要完整查看大版本差异时使用新路由，沿 `nextCursor` 读取至 `null`。

Diff 行顺序固定：title、subtitle、目标版本的块顺序、源版本中已删除的块顺序。每页 1–100 行，`offset` 从 0 开始，`totalBlocks` 最多 60,002（两端各 30,000 块加两条标题锚点）。两版本 ID 指向不可变行；签名游标绑定 Owner、文章、from、to 和 limit。跨 Owner 或文章的版本仍先按现有所有权规则隐藏，再检查游标。

分页避免把最多 60,002 条文本差异一次性放入冻结的 1,000 项响应。实现按需构造当前页的行，旧块位置用索引映射，避免对最大合法 AST 的平方级比较。此扩展不改数据库、现有版本行、T00 rc.3 文件或旧路由的返回体。

## 兼容与验收边界

旧客户端无需改动即可继续读取不超过 1,000 行的 Diff；对大差异仍会收到既有显式错误。新客户端可读取完整行集，但必须支持分页。CR-T07-01 是否作为完整 AC-19 的正式关闭证据，仍须独立审核本增量契约及真实 HTTP/最大容量回归；本实施记录不自行改写 [T07 第二轮审核](../reviews/T07-Review-v2.0.md) 的结论。

# T06 第一轮审核整改交付

日期：2026-10-05（Asia/Hong_Kong）。针对 [T06-Review-v1.0](../reviews/T06-Review-v1.0.md) 的 T06-R01、T06-R02；状态为**提交独立复审**，不自行批准 T06、G1/G2 或上线。原审核报告与失败证据保持原样；[初版交付报告](T06.md)保留当时的结果。

## 整改结果

| 审核项 | 修改与验证 |
|---|---|
| T06-R01 / Markdown 嵌套强调 | `ArticleAst.inlineSegment` 按实际分隔符长度递归识别 `*`/`**`/`***` 及对应下划线形式；内层 marks 按可读文本的 Unicode 码点偏移合并。三重强调生成 bold 和 italic 两种 marks，长度检查基于去除标记后的 AST 文本。转义和未配对的字面星号保持正文字符，超过 3 个连续强调符明确拒绝。新增嵌套、三重强调、边界、转义、字面字符与码点偏移单测，并通过真实 HTTP 创建验证保存后的 Original。|
| T06-R02 / 指纹误报 | 将 `input-baseline.json` 的 820 条文件指纹由“路径作键、hash 作值”转换为 `{path,sha256}` 分字段记录，哈希值与顺序未重新生成；更新校验器读取方式和复验输出路径。Git 可见文件复扫：T06 新增告警 **0**。扫描整体仍退出 1，只有既有 T02 `r01-integrity.json` 的 6 条指纹误报，本任务没有修改 T02 证据或放宽扫描规则。|

## 实际验证

- [真实 PG/HTTP/Local 完整回归](../../../tests/engineering/T06/evidence/revision-v1-final.json)：34/34 通过，0 failure/error/skip；包含新增 Markdown 原文创建测试。临时 PostgreSQL 停止成功。
- [审核方原始 3 个解析反例的复跑输出](../../../tests/engineering/T06/evidence/revision-v1-review-cases.txt)：3/3 通过，0 failure/error/skip；使用审核方 `ReviewArticleAstTest.java` 的未修改副本在本次隔离构建运行，未覆盖原始失败记录。
- [既有数据升级回归](../../../tests/engineering/T06/evidence/revision-v1-upgrade.json)：1/1 通过；临时 PostgreSQL 停止成功。
- [交付校验与复扫](../../../tests/engineering/T06/evidence/revision-v1-final-checks.json)：820 个输入基线文件无变化，冻结契约 27/27、共享 patch 可应用、diff 空白检查与两份实际响应 Schema 均通过；[逐条扫描结果](../../../tests/engineering/T06/evidence/revision-v1-final-checks-gitleaks-findings.json)仅 6 条 T02 既有误报。扫描退出 1 已明确保留，不称为整体 CI 通过。
- [修订文件指纹](../../../tests/engineering/T06/evidence/revision-v1-fingerprints.json)逐项记录本次修改的源码、测试、校验器和基线文件的 SHA-256，供复审核对。

复现命令（仓库根目录，使用现有 Python 运行时；PG 步骤需允许启动本机临时实例）：

```powershell
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' tests/engineering/T06/integration.py --evidence-name revision-v1-final
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' tests/engineering/T06/integration.py --upgrade-only --evidence-name revision-v1-upgrade
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' tests/engineering/T06/verify_delivery.py --evidence-name revision-v1-final-checks
```

独立反例的复跑方式：先从第一条命令的 evidence JSON 读取 `isolatedWork`，将 `docs/execution/reviews/T06-round1/ReviewArticleAstTest.java` 复制到隔离 backend 的同包测试目录，再用同一离线 Maven 仓库执行 `-Dtest=ReviewArticleAstTest`；保留完整 Maven 输出于上述证据。没有修改共享装配、正式迁移或任何冻结契约。T03 共享 canonical 修复和 composition root 仍按初版共享 patch 提请主 agent 审阅，外部依赖边界不因本次整改而改变。

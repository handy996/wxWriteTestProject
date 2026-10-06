# T06 第二轮审核整改交付

日期：2026-10-05（Asia/Hong_Kong）。回应 [T06-Review-v2.0](../reviews/T06-Review-v2.0.md) 唯一仍开放的 **T06-R01 / P2**。本次提交独立复审，不自行批准 T06、整体 CI、G1/G2 或上线。首轮、第二轮的审核报告和失败证据均保持原样；[上一轮整改报告](T06-Revision-v1.0.md)保留当时的结果。

## 修复内容

`ArticleAst.inlineSegment` 现在按当前层级所需数量消费闭合星号或下划线，剩余符号继续交给外层。对于紧贴正文、同时具备开闭条件的较长符号串，先尝试开启内层强调；行尾的共用闭合符则逐层消费。三重强调拆成 bold 和 italic 两个嵌套层，分别尝试两种闭合顺序，允许内层闭合后外层尾段为空。解析出的文本和 marks 均以 Unicode 码点偏移计算；不会全局删除星号。未闭合的三重强调及超过三个连续强调符明确拒绝。

补充测试覆盖 `*a **b***`、`**a *b***`、`***a* b**`、`***a** b*`、下划线变体、紧邻正文的闭合符、转义/字面星号、非 BMP 码点偏移，以及可读文字 98/30,000 字边界。真实 HTTP 创建测试验证不足 100 字返回 422 且 `article_job` 无新增业务行；合法共用闭合符的 Original 保存后，其文本、marks 和 plainText 与预期一致，并成功创建恰好 30,000 字的原文。

## 验证与证据

| 验证 | 实际结果 |
|---|---|
| [隔离 PG/HTTP/Local clean test](../../../tests/engineering/T06/evidence/revision-v2-final.json) | **43/43 通过**，0 failure/error/skip：作者 AST 13、真实 PG/HTTP/Local 18、删除协议 2、T03 canonical 4、两轮审核原始反例各 3。临时 PostgreSQL 停止成功。两份审核测试仅复制到隔离构建，源码未改。|
| [两轮审核反例独立复跑](../../../tests/engineering/T06/evidence/revision-v2-review-cases.json) | 6/6 通过，0 failure/error/skip；[JUnit 结果](../../../tests/engineering/T06/evidence/revision-v2-review-test-results/)保留。|
| [既有数据升级](../../../tests/engineering/T06/evidence/revision-v2-upgrade.json) | 1/1 通过，临时 PostgreSQL 停止成功。|
| [交付校验与密钥扫描](../../../tests/engineering/T06/evidence/revision-v2-final-checks.json) | 820 个输入基线文件未变；冻结契约 27/27、共享 patch 可应用、diff 空白检查和两份实际响应 Schema 检查均通过。T06 新增扫描告警 0；[扫描结果](../../../tests/engineering/T06/evidence/revision-v2-final-checks-gitleaks-findings.json)仅既有 T02 的 6 条指纹误报，扫描整体仍退出 1。|
| [修订文件指纹](../../../tests/engineering/T06/evidence/revision-v2-fingerprints.json) | 本轮修改的源码、测试、隔离编排器、校验器和报告的 SHA-256，供复审核对。|

首次本轮本地回归暴露空外层尾段和紧贴正文的较长开符判断问题，记录于 [revision-v2-first.json](../../../tests/engineering/T06/evidence/revision-v2-first.json)，随后修正；该失败证据没有改写。第二轮审核方 R02 已关闭；本次没有改动指纹数据格式、T02 原证据或共享扫描规则。共享 canonical/接线补丁、正式迁移编号和外部领域适配依赖仍按初版交付报告处理。

复现命令（仓库根目录，使用现有 Python 运行时；PG 测试需允许启动本机临时实例）：

```powershell
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' tests/engineering/T06/integration.py --include-review-regressions --evidence-name revision-v2-final
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' tests/engineering/T06/integration.py --upgrade-only --evidence-name revision-v2-upgrade
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' tests/engineering/T06/verify_delivery.py --evidence-name revision-v2-final-checks
```

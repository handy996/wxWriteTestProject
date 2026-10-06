# T06 第三轮审核整改交付

日期：2026-10-05（Asia/Hong_Kong）。回应 [T06-Review-v3.0](../reviews/T06-Review-v3.0.md) 仍开放的 **T06-R01 / P2**；T06-R02 保持关闭。本次交主 agent 独立复审，不自行批准 T06、整体 CI、G1/G2 或上线。前三轮审核原始测试及失败证据保持原样。

## 修复内容

`ArticleAst` 的强调分隔符判断现在同时考虑左右两侧的 Unicode 空白、标点/符号和待闭合的同类分隔符层级。位于中文句号、逗号前的 `***` 可逐层闭合；与后续正文紧邻时，恰好覆盖当前层级的分隔符也优先闭合。较长符号串只有在具备开启条件时才尝试成为内层强调。截取剩余闭合符时沿用整组符号左侧的正文字符判断，避免把前一颗星号误当作正文标点。转义和字面字符仍保留，未闭合三重强调及超过三个连续强调符仍明确拒绝。

新增表驱动 AST 回归：单、双、三重强调、两种嵌套方向及下划线变体，逐一验证行尾、空白前、中文句号/逗号前和与后文相邻的纯文本、mark 类型与码点范围。另验证非 BMP 字符偏移和转义字面星号。真实 HTTP 创建测试覆盖 `***强调***。` 与 `*a **b***，后文`，读取持久化 Original 检查纯文本和 marks。前两轮的 98/30,000 字边界与无新增业务行测试保持通过。

## 实际验证

| 检查 | 结果 |
|---|---|
| [隔离 PG/HTTP/Local clean test](../../../tests/engineering/T06/evidence/revision-v3-first.json) | **48/48 通过**，0 failure/error/skip：作者 AST 14、真实 PG/HTTP/Local 19、删除协议替身 2、T03 canonical 4、三轮审核原始反例各 3。临时 PostgreSQL 停止成功；审核测试源码仅复制到隔离构建。|
| [既有数据升级](../../../tests/engineering/T06/evidence/revision-v3-upgrade.json) | 1/1 通过，临时 PostgreSQL 停止成功。|
| [交付校验与 Git 可见文件扫描](../../../tests/engineering/T06/evidence/revision-v3-final-checks.json) | 820 个输入基线文件无变化；冻结契约 27/27、共享 patch 可应用、diff 空白检查、两份实际响应 Schema 检查通过。T06 新增告警 0；[扫描明细](../../../tests/engineering/T06/evidence/revision-v3-final-checks-gitleaks-findings.json)仅 T02 既有 6 条指纹误报，扫描整体仍退出 1。|
| [本轮修订文件指纹](../../../tests/engineering/T06/evidence/revision-v3-fingerprints.json) | 记录源码、测试、隔离编排器、校验器与本报告的 SHA-256，供独立复审。|

原有共享 canonical/接线补丁、正式迁移编号及 T07/T10/T11/T37 等跨域适配边界未因本轮修改而改变。没有修改审核报告、历史失败证据、T02 原证据或共享扫描规则。

复现命令（仓库根目录；PG 测试需允许启动本机临时实例）：

```powershell
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' tests/engineering/T06/integration.py --include-review-regressions --evidence-name revision-v3-first
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' tests/engineering/T06/integration.py --upgrade-only --evidence-name revision-v3-upgrade
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' tests/engineering/T06/verify_delivery.py --evidence-name revision-v3-final-checks
```

# T01 数据与评测协议（rc.2修订）

本轮修复依据T00-T01-Review-v1.0的R06。旧合成集、空白标注和原结果保留；新代表性候选见representative-v1/README.md。任何候选均未完成人工金标，真实模型/费用评测未执行。

## 数据分层

旧tests/fixtures/index.json是20篇同构工程回归集，datasetVersion=1.0.0-rc.1，不再由完整runner重生成。新tests/fixtures/representative-v1/index.json为五类各4篇独立情境、200主要候选，datasetVersion=representative-v1.0.0-rc.1，contractVersion=1.0.0-rc.2。两个manifest独立；不把目录分类标签或合成建议答案当人工代表性/正确性证明。

使用依据为本任务原创虚构测试内容，无第三方全文复制。所有自然人角色未指派，标注UNREVIEWED。标注者必须通读补漏、保留限定条件/来源/反证/同源关系，再独立填表并复核分歧。代表性审核、双人身份和证据由项目负责人安排；开发agent不伪填。真实三次模型调用等待T08/T09、凭证、确认预算和成本门禁。

## rubric editorial-quality-v2

Analyzer与编辑质量是两套独立记录，不能用编辑的主题保真替代Analyzer的核心论点准确度。

| 记录 | 必填内容 | 每次完整20篇的门槛 |
|---|---|---|
| analyzerScores | articleId、coreThesisScore（整数1–5）；真实模式还需reviewerId/evidenceRef/status=REVIEWED | coreThesisScore≥4的篇数/20≥90%，即至少18篇 |
| editorialScores | articleId、scores五维、keyThesisReversed（显式bool）；真实模式还需reviewerId/evidenceRef/status、逐维dimensionEvidence及thesisReversalEvidence | 每篇五维等权平均，再对20篇等权平均≥4.0；任意一篇反转关键论点即失败 |
| 成本记录 | articleId及entries，每条idempotencyKey/kind/amount/currency/pricingVersion | 实际/估算/未知分列，未决不能当已结清 |
| 事实匹配 | 逐预测matchedGoldId及人工匹配证据 | recall≥95%、precision≥90%、无CRITICAL漏检、无错误SUPPORTED/未裁决支持 |

五个编辑维度严格对应SRS38末尾：THESIS（主题保真）、STRUCTURE（结构）、INFORMATION_DENSITY（信息密度）、TITLE_CONSISTENCY（标题一致性）、MOBILE_READABILITY（移动阅读）。不额外混入维度来稀释这个均值。每项1=重大问题、2=明显缺陷、3=基本可用需改、4=准确清楚仅小修、5=准确完整表达自然。逐维证据需定位原文/当前稿；论点反转检查也须给理由/定位，不能只填空的false。

缺Analyzer、缺任一维度、缺论点反转bool/真实证据时退出2（BLOCKED_INCOMPLETE_EVIDENCE）；资料齐全但低于门槛则正常计算退出0并将相应gates和allRunThresholdsMet设为false。4.0、18/20属于通过边界；3.99、17/20失败。即使均分5，任意反转仍失败。输出分列facts/analyzer/editorial/cost四个gates，每组都通过才thresholdsMet=true，三次皆通过才allRunThresholdsMet=true。acceptancePassed始终false，保留主agent最终审核。

## 命题指标与三次运行

TP只能由经复核的一对一主要Claim匹配贡献；重复提取计FP，跨文章/未知ID/重复预测ID拒绝。预测MINOR不抵消主要Claim漏检。空预测precision=0。CRITICAL漏检逐条列ID/原文/整改要求，即使总体95%达标也不放行。金标CONTRADICTED/UNVERIFIABLE/PARTIAL/REQUIRES_REVIEW被标SUPPORTED逐例计错；无金标匹配的SUPPORTED单列未裁决。

三次各完整20篇，datasetHash/goldHash/model/promptHash/skillHash/policyHash/parametersHash相同；输出各次及min/median/max。账本金额Decimal六位USD，ACTUAL/ESTIMATED/UNKNOWN分开，不将推理token重复收费。实际成本报告三次总额与每篇中位/p95/最大；这些是冻结集结果，不宣称现实零幻觉。

## 输入格式和可运行入口

evaluate.demo_bundle()给出完整格式。顶层mode=REAL/MOCK/SYNTHETIC_ORACLE，真实包goldStatus=ADJUDICATED并提供independenceEvidence。每gold含reviewA/B（不同reviewerId、decision、reviewedAt、evidenceRef）、adjudicator/adjudicationEvidence/status。预测含matchReviewStatus=REVIEWED、matchReviewer/matchEvidence。scores之外必须额外提供analyzerScores；旧版仅七维编辑THESIS的输入会被拒绝，不能静默迁移成分析评分。

运行：
```powershell
python tests/evaluation/T01/verify.py
python docs/evaluation/evaluate.py --input path/to/reviewed-bundle.json --output path/to/report.json
```

runner保留旧数据，生成独立representative-v1并测试R06边界。rc2-demo仍是基于旧工程回归集的三个合成预测，为工具测试故意注入漏检/重复/错误支持，成本0且没有模型调用。它不是新代表性集或真实模型的质量成绩。完整stdout/退出码见execution/reports/T00-T01-command-log.json。

## 可重复与人工证据保护

旧build_fixtures.py仅为rc.1历史生成器，人工填写后拒绝覆盖；当前runner不调用它。新build_representative.py只允许首次或相同字节生成，任何已有资料差异直接拒绝。资料修订需要新datasetVersion、保留旧标注/结果和映射。目录随机顺序只是盲标准备，A/B答案隔离仍由组织者管理。

许可oracle可离线执行，Provider/并发/QA夹具是未集成场景。真实图库、水印字体/像素、Worker/DB竞争、备份恢复、NFR和安全HTTP验收由领域与T36/T37完成。本工具只验证字段及引用完整性，不能验证填入的人是否真实独立，也不能代审证据是否可靠。

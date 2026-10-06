# T02 第二轮审核

- 审核日期：2026-10-03（Asia/Hong_Kong）。
- 审核对象：HEAD `b115a4022375675c7cbff536b239508db8f3f4e1` 加当前工作区 R01/B01 整改；整改尚未提交。
- 当前分支：`appmod/java-upgrade-20261003114404`。本轮未切换分支、创建提交或修改交付实现。
- **结论：CHANGES_REQUIRED。第一轮 R01、B01 均关闭；新增 1 项 P2，完整 Gitleaks 检查失败，需修正后复审。**

## R02 — [P2] 新指纹清单触发 Gitleaks，阻断 CI

定位：[指纹生成器第 35 行](../../../tests/engineering/T02/revision_integrity.py#L35)，输出为 [r01-integrity.json](../../../tests/engineering/T02/evidence/r01-integrity.json)；CI 调用点为 [.github/workflows/ci.yml 第 55 行](../../../.github/workflows/ci.yml#L55)。

生成器使用文件路径作为 JSON 键、SHA-256 作为值。含 `password` 或 `secret` 的路径与高熵值出现在同一赋值行，触发已配置 Gitleaks 8.30.1 的 `generic-api-key` 规则。本次按交付扫描器、交付配置和完整 Git 可见文件集复跑，**退出码 1、命中 6 项**，均位于 `r01-integrity.json` 的第 67、110、111、115、124、125 行。扫描器包含未跟踪交付文件，故能在当前未提交状态复现；把整改文件提交后，CI 同样会纳入扫描并在该步骤失败。

六个值均已重新计算并核对为相应文件的 SHA-256，**属于误报，不是发现了真实凭证泄露**。但误报尚未被当前配置处理，不能将简化模式扫描退出 0 视为完整 CI 扫描通过。整改报告仅补跑了 `secret_scan.py`，该工具与 CI 随后运行的 `scan_secrets.py`/Gitleaks 不同。

证据：[完整扫描运行记录](T02-round2/gitleaks-run.json)、[脱敏命中清单](T02-round2/gitleaks-findings.json)。审核包装器 [run_gitleaks.py](T02-round2/run_gitleaks.py) 仅将结果输出改到审核目录，不改变扫描输入、规则或退出码。

修复建议与验收：

1. 调整指纹生成器及其生成清单，例如采用分行的 `path`、`sha256` 字段记录，避免把含敏感词的文件名作为凭证状赋值键；或使用经核对、范围精确的误报例外。不要豁免整个 evidence 目录，也不要忽略扫描退出码。
2. 在全部交付证据生成完毕后，用 CI 同一套 Gitleaks 版本和配置扫描完整交付，要求退出 0；同时保持现有真实凭证检测规则有效。
3. 更新整改报告和指纹清单，保留本轮失败记录，明确最终成功扫描所对应的交付内容。仅重跑简化模式扫描不足以关闭 R02。

## 第一轮问题复核

| 项目 | 结论 | 独立验证 |
|---|---|---|
| R01 函数默认权限未撤销 | CLOSED | 全局默认撤权在 beforeMigrate 执行；版本迁移内探针即时断言拒绝。旧函数 PUBLIC 权限被清理，显式重载授权保留；新函数未授权拒绝、授权后成功，重启保持 |
| B01 容器验收缺口 | CLOSED | 正常宿主 Docker 可用；直接 Compose 与实际 dev.py up/down/up 两条路径均从新卷运行成功，最终仅清理自己的项目容器、卷和临时凭证文件 |

旧版升级不是伪造历史：已核对导出的 19 个 backend 文件与 b115a40 一致，旧 JAR 只包含原迁移；实测先复现旧版未授权执行成功，再升级修复版并验证拒绝。原迁移源码字节和已有 history 行未变，升级后第二次启动完整 history 不变。旧应用在升级前停止。

容器测试确认页面和 actuator/API 代理、backend UID 10001、只读根文件系统、数据行与迁移历史持久化、函数显式授权保留、新函数默认拒绝、越权 SQL 拒绝，以及 prod/mock 以 `T02_PROFILE` 非零退出。两轮结束后各自容器列表和项目卷列表均为空。测试没有调用收费 Provider。

## 本轮实测与边界

| 检查 | 结果 | 证据 |
|---|---|---|
| 后端 clean verify | PASS，20 项单测，退出 0 | [构建记录](T02-round2/backend-build-final.json) |
| 真实 PG 17.11 / JVM 旧版升级 | PASS，28 项检查，退出 0 | [摘要](T02-round2/upgrade-run.json)、[SQL/进程/清理记录](T02-round2/upgrade-integration.json) |
| 直接 Compose 冷启动和 down/up | PASS，退出 0 | [独立记录](T02-round2/compose.json) |
| 实际开发入口 up/down/up | PASS，退出 0 | [独立记录](T02-round2/entrypoint.json) |
| 已批准契约指纹 | PASS，27 项一致 | T00 rc.3 基线检查；本轮无契约变更 |
| 作者整改指纹清单 | PASS，117 项一致 | [本轮快照](T02-round2/review-state.json) |
| 简化密钥模式扫描 | PASS，退出 0 | [记录](T02-round2/secret-patterns.json) |
| 完整 Gitleaks | FAIL，退出 1，6 项误报 | R02；不能据此宣称 CI 通过 |
| Git 空白检查 | PASS | `git diff --check` |

本轮针对整改验证，没有重新运行不变的前端本机构建、24 项离线契约测试或在线依赖公告查询；Docker 构建复用了可用缓存。本机 Maven 为离线构建，CycloneDX 明确跳过，不代表重新生成了 SBOM。依赖定义及锁文件没有变化。作者另交付的空库 24 项测试记录已核对指纹；本轮独立空库验证采用 Docker，独立版本迁移顺序验证包含在 28 项升级检查中。

首次审核包装器使用相对 Maven 路径被 Windows 命令解释拒绝，保留 [失败记录](T02-round2/backend-build.json)；改为绝对路径后成功，未修改应用规避失败。远端 GitHub Actions 仍未执行；本轮 Gitleaks 的确定失败已经足以阻止其完整通过。

## 审核状态与交接

第一轮报告及多数审核证据在本轮开始时已不在原路径；上一轮会话中的 R01/B01 结论仍可核对，整改报告也记录了这一工作区变化。本轮不推断删除原因，也未冒充原件重新生成历史证据。

本轮结论绑定当前 117 项交付指纹，后续提交必须包含已审核的整改文件，不能只引用仍未包含修复的 b115a40。R02 关闭前，T02 保持 CHANGES_REQUIRED；T00 rc.3 批准不变，T01 人工证据、G1 其他模块及生产上线就绪状态均不由本轮关闭。

审核仅新增本报告和 `T02-round2/` 下证据。交付源码、作者原证据和冻结契约保持原样。

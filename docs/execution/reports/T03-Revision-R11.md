# T03 第十一轮整改与集成记录

2026-10-09 整理。依据 `docs/execution/reviews/T03-round10/review.md` 的 D-1、D-2、D-3 整改，并在本报告更正 D-4…D-6 的口径。实现已集成，独立复审与人工批准未完成，不构成 T03 / AC-28 / G0 / G1 / G2 通过声明。

## D-1：限定载荷审计的主张

`load_bearing_audit.py` 采用复审允许的方案 (a)：只对已登记判据逐条列出桩和看守结果，不声称覆盖所有判据。普通审计登记 54 项，而 gate 有 83 个 `raise Rejected` 位置；两个计数并非一一对应，也不是覆盖率分母。`construct_reason` 是诊断措辞项，不归入独立看守。

已有 `load-bearing-audit-r11.json` 完整记录了 54 项：46 own-witness、3 shared-witness、4 benign-half、1 declared-diagnostic，无 unwatched。其 gate 指纹属于 CI 修复前的版本，不能替代当前字节的结果。

已有 `load-bearing-audit-r11-canary.json` **仅有 36/57 行，缺少 selfTest 结论**，属于未完成产物。本次保留原字节用于追溯，不把它列为通过证据，也不根据缺失字段推断退出码。`session-cookie-r10b.json`、`r10c.json` 同样作为历史证据入库，不冒充本轮运行。

集成时在当前 gate 上完整补跑 `--self-test`：57/57 行；前 54 项仍为 46 + 3 + 4 + 1；三个 canary 均被列为 unwatched，`missed=[]`、`detectorIdle=false`，**实际退出 1，符合故意红控的期望**。证据为 `r11-integration-canary.json` 和 `r11-integration-canary.txt`。这仍不证明登记表完备，也不是独立复审。

## D-2：先校验，再发布证据

记录器现在从构建目录检查 Maven 退出码、XML 的失败/错误/跳过、必需产物、census、角色与用例数，组装记录和摘要；检查通过后才写临时文件并逐件替换目标。失败运行不会先覆盖已接受的受控证据。

新增 `test_recorder.py`，注入子进程结果和隔离目录中的真实格式 XML/census，检查七种拒绝情形：非零退出、failures、errors、skipped、缺少产物、无效 census、XML 计数不符。2 个测试方法 / 7 个子场景全部通过，证据目录逐字节不变。拆分后的 T03 记录器配合 CI 修改前的 gate 也通过同组测试，证明该提交不依赖后续 CI 接口。

这组回归使用模拟 Maven 结果，证明拒绝发布行为；没有重跑“旧记录器 + 真实失败 Java 测试”的前后对照。正向真实运行由后续 CI 修复的 Windows/Linux 各 15 项测试及同次证据检查支持，见 `CI-Portability-20261009.md`。

逐文件 rename 只保证单个文件原子替换，**不是整组证据的事务**。I/O 失败仍可能留下 `.part` 或混合代际文件；本次修正文档中过强的原子性描述。并发发布和 I/O 故障恢复尚未验证，CI 使用独立运行目录降低交叉写入风险。

## D-3…D-6：更正说明

- 非契约 Cookie 名由 `T03Configuration.verifySessionCookieContract` 的第一条 `if` 拒绝；第二条检查 prod 安全属性。未为文案更正改变产品行为。
- YAML 文本普查仍参与归因，不能声称已从判据中移除。复杂形状的实际解析结果依赖 binder 证书；文本普查与证书各自仍有边界。
- 绑定记录有 10 个输入，`census` 已包含其中，不是额外第 11 项。
- 正式集成入口是 `tests/engineering/integration/formal.py`；历史 Cookie 检查记录从 r04 起，未存在 r01…r03。旧提交 `cc91998` 的措辞更正为：15 条 error 中只有 3 条含原始 ApplicationContext 文案，不能声称每条都是独立装配失败；历史提交本身不改写。

## 可复跑命令

从仓库根运行，并为每次输出选择新文件名。`--self-test` 的成功检测结果是退出 1；退出 3 表示漏报 canary，退出 2 表示基线失败或拒绝覆盖。

```sh
python tests/engineering/T03/test_recorder.py
python tests/engineering/T03/load_bearing_audit.py --output .work/t03-r11-replay-audit.json
python tests/engineering/T03/load_bearing_audit.py --self-test --output .work/t03-r11-replay-canary.json
python tests/engineering/T03/check_session_cookie.py --output .work/t03-r11-replay-agreement.json
```

审计仍需仓库固定工具链及依赖缓存，gate 会重新核对本地工具链指纹。跨平台复跑应先按 CI 报告生成同次证据，不能直接复用另一操作系统的 JDK 指纹。

## 证据与剩余工作

新增集成证据只追加；历史受控 XML、绑定记录和 census 未覆盖。入库前按分组索引逐件比较预期字节。T03 提交只包含校验顺序、审计脚本、拒绝发布测试及说明；共享记录器的 `--evidence-dir` 和相对命令记录随后进入 CI 提交。

原报告骨架提到一次被作者主动取消的开发运行（`--output $env:TEMP\t03-r11-scratch\dev-audit.json`）；不将其退出状态当作闸门结果。骨架中的“工具越界”小节没有现场内容，本次没有足够证据补写事件细节，也不沿用“从未越界”之类声明。

仍待：独立第十一轮复审与新桩验证、真实失败 Java 运行的前后对照、I/O/并发发布故障验证、正式 harness 来源标记、依赖扫描缺 SBOM 的具名诊断，以及 T03 人工批准。载荷审计不可据登记表自证完整性。

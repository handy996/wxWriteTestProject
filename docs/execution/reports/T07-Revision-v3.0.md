# T07 修订 v3.0 — 关闭 T07-R03（增量契约鉴权声明）

日期：2026-10-06（Asia/Hong_Kong）。作者状态：**整改自测完成，待主 agent 第四轮复审**；不自行关闭 T07-R03，不自行宣布 CR-T07-01 关闭或 T07/G1/G2 通过。

## 问题与依据

[T07-Review-v3.0](../reviews/T07-Review-v3.0.md) 的 T07-R03（P2）：[diff-pages-v1.1.openapi.yaml](../../api/diff-pages-v1.1.openapi.yaml) 既无根级/操作级 `security`，也无 `components.securitySchemes`；独立按该增量文档生成客户端的 agent 无法从机器可读配置获知必须携带登录 Session，实际会收到 401。本次改动范围为该文件、`tests/engineering/T07/verify_diff_page.py` 和一份新证据；**未修改生产源码、迁移、T00 rc.3 冻结契约与任何历史审核材料**。

## 改动

- 增量 OpenAPI 增加根级 `security: [{session: []}]` 与 `components.securitySchemes.session`；scheme 取值为 `type: apiKey` / `in: cookie` / `name: EDITORIAL_SESSION`，与冻结契约 [openapi.yaml](../../api/openapi.yaml)（第 13–17 行与 `components.securitySchemes`）**字典全等**，未附加 description 等额外字段以免破坏等值比较。放在根级复用 OpenAPI 继承语义，与冻结文档风格一致。
- 校验器 `verify_diff_page.py` 新增 `session_authentication()`：按**操作级优先、否则根级**解析每个操作的有效 security，要求等于冻结契约的 `[{"session": []}]`，并逐一校验被引用 scheme 的 `type/in/name`。有效 security 解析方式与复审方 [check_review.py](../reviews/T07-round3/check_review.py) 第 44–48 行一致，因此第四轮可独立复算。
- 校验器新增 `negative_control()`：对同一文档分别施加深拷贝变异——删除根级 security、删除 session scheme、把 `in` 改为 `header`、把 security 置为空列表——**四种弱化都必须被拒绝**，否则校验器自身报错退出。仅追加断言而不证明其能失败，不足以关闭"现有校验器不能捕获该问题"这一项。

## 实测命令与退出码

| 检查 | 结果 | 记录 |
|---|---|---|
| `verify_diff_page.py --sample …/DiffPage.json --output …/diff-page-v1.1-check-r03.json` | **退出 0** | Draft 2020-12 校验实际响应样本、OpenAPI 3.1 结构校验、鉴权一致性、4 项反向控制全部拒绝 |
| 内嵌 `check_contracts.py` | **退出 0**：`Approved T00 rc.3: 27 hashes verified, no regeneration` | 冻结契约未被改动 |
| 复审方判定式独立复算 | **SECURITY_MATCHES_FROZEN = True** | 期望 `[{'session': []}]`／实际相同；期望与实际的 scheme 字典一致 |
| 样本输入完整性 | 样本 SHA-256 `648337fc…18ae7`，与作者上轮记录逐字节一致 | [diff-page-v1.1-check-final.json](../../../tests/engineering/T07/evidence/diff-page-v1.1-check-final.json) |

新证据：[diff-page-v1.1-check-r03.json](../../../tests/engineering/T07/evidence/diff-page-v1.1-check-r03.json)（含增量 OpenAPI 与被引用冻结 OpenAPI 的 sha256、有效 security 观测值、反向控制清单）。文件名 `declaredAt=root`、`method=GET`、`effectiveSecurity={"session":[]}`。

## 未运行的检查及原因

- **后端与迁移测试未重跑**：本轮未改 `backend/` 任何文件。服务端登录限制与真实 HTTP 匿名 401、登录成功分页回归的行为由 `c12738f` 的第三轮记录支撑（正式组合根隔离 clean test **78/78**，含复审方 `ReviewDiffHttpTest` 的匿名 401 与跨文章拒绝）。
- **复审方 `check_review.py` 不可直接复跑作为关闭证据**：它绑定 `input-snapshot.json` 中 1,737 个跟踪文件的指纹（第 50–52 行），而本次恰好在其中两个文件上改动，按其设计必然报告 `tracked inputs changed`。第四轮需以新快照运行；`evidence/checks.json` 的 `assert not out.exists()` 亦要求新证据名。
- 未做任何真实收费 Provider 调用，未启动 Docker 拓扑，未连接真实 S3。

## 已知问题与边界

- T07-R03 关闭以第四轮复审为准。CR-T07-01 的正式确认同样待该复审：分页容量功能本身已有 601 页 / 60,002 行逐行验证，但在 R03 关闭前不宣称 AC-19 对任意合法版本 Diff 完整通过。
- T04 真实私有 S3 端到端验收（B01/R04）仍 BLOCKED；T03 仍无独立批准记录；T07 组合根仍仅允许 Local 后端执行版本写入。
- **沙箱失败记录（保留，不覆盖）**：校验器首次运行在落盘证据处失败，`PermissionError: [Errno 13]`，因受限令牌仅允许子进程写仓库根目录（`docs/execution/`、`tests/engineering/T07/evidence/` 均拒写）；随后在宿主权限下以新证据名重跑并退出 0，首次输出未计入通过结果。

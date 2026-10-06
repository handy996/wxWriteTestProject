# T07 派发任务卡：版本、Diff、恢复和修改提案

你是 wxAgent 的 T07 实施 agent。请实际完成实现、测试和交付报告，交主 agent 独立审核，不自行批准 T07 或阶段门禁。本次任务基于当前共享工作区；先记录输入指纹，不要只检出旧 HEAD 开始实现。

## 输入与必读材料

项目根目录：`E:/project/codex/wxAgent`。先查阅适用 AGENTS.md（若有），再阅读：

- `E:/project/codex/wxAgent/docs/AI-Editorial-Agent-SRS-v1.0.md`：§14–16、§24、§29、AC-19/20/23/25。
- `E:/project/codex/wxAgent/docs/AI-Editorial-Agent-Execution-Plan-v1.0.md`：T07 任务卡、目录/表所有权、跨域装配规则。
- `E:/project/codex/wxAgent/docs/execution/reviews/T00-rc3-approval.json`、`E:/project/codex/wxAgent/docs/api/openapi.yaml`、`E:/project/codex/wxAgent/docs/schemas/editorial.schema.json`、`E:/project/codex/wxAgent/docs/execution/contracts/ports.json`、`E:/project/codex/wxAgent/docs/execution/contracts/ownership-and-fk.md`、适用 ADR 和 T00 rc.3 向量。以批准记录判断冻结状态，不因旧文件仍写 REVIEW_CANDIDATE 就改契约。
- `E:/project/codex/wxAgent/docs/execution/reviews/T06-Review-v4.0.md` 及其关联指纹；T06 当前交付已 PASS，R01/R02 均关闭。
- `E:/project/codex/wxAgent/docs/execution/reports/T06.md`、最新修订报告，以及实际 T03 身份/幂等/审计、T04 存储、T05 配置、T06 ArticleService/ArticleAst/ArticlePorts 源码与测试。

T06 PASS 仅限受审文件。T03 仍缺正式批准基线/完整接线，T04 真实 S3 证据有独立限制，共享 canonical 与 composition root 补丁尚未正式合入；T10/T11 真正的 generation、fencing、失效实现尚未就绪。核实当前文件是否已有变化，按实际结果记录，不把替身当真实依赖。

## 实施范围与写入边界

拥有目录：

- `E:/project/codex/wxAgent/backend/src/main/java/com/example/editorial/article/version/`
- `E:/project/codex/wxAgent/backend/src/main/java/com/example/editorial/article/proposal/`
- 对应 backend 测试目录、`E:/project/codex/wxAgent/tests/engineering/T07/`
- `E:/project/codex/wxAgent/docs/execution/reports/T07.md`

拥有 `change_proposal` 基础表。ArticleJob/ArticleVersion 属于 T06，版本写入必须经其受控入口，不得从 T07 直接更新工作头、绕过权限或新造一套版本表。跨域只走应用服务/端口；迁移以 T07 草案交付，由主 agent 分配正式全局版本。

不要覆盖共享配置、已执行迁移、冻结契约、他人工作区修改、作者历史证据或审核报告。需要 T06/共享变更时，提供原因、兼容影响和最小 patch，在隔离副本中应用并验证后交主 agent 审核。不要因为需扩展上游接口就停在计划或留 TODO：把可审阅补丁与完整验证做好。不得修改 frozen hash 迎合实现。

## 必须完成的工作

1. **版本读取与人工保存。** 按 `/api/v1` 下冻结路由实现 `GET/POST /articles/{id}/versions`、`GET /articles/{id}/versions/{versionId}`。使用 ArticleVersionPage、SaveVersionRequest、ArticleVersion 的准确字段及返回头；分页游标签名、绑定 Owner/文章/过滤和稳定排序。人工保存创建 MANUAL 新版本，Original/历史不覆盖；保留可对应的稳定 blockId，拆分/合并分配新 ID 并验证 BlockMapping，不靠旧字符偏移猜位置。title/subtitle、AST、纯文本、marks、claims/slots、Unicode span 与 canonical hash 必须一致，拒绝跨文章或无法验证的引用。

2. **任意版本 Diff。** 实现 `GET /articles/{id}/diff?from=…&to=…`，准确返回冻结 Diff。验证两版本同 Owner/同文章，覆盖标题/副标题、正文增删改、块顺序、拆合映射和 marks。结果可重复，纯文本/码点位置不被 UTF-16 偏移污染，不通过回读当前工作头替代指定历史版本。

3. **恢复为新版本。** 实现 `POST /articles/{id}/restore`，使用 RestoreRequest，创建 RESTORE 新行：parent 为请求提交时的当前头、restoredFrom 为被恢复版本、versionNo 单调递增。历史完整保留，不恢复旧 QA/审批有效性，不继承旧使用依据为自动放行。特别注意：当前 T06 prepareVersion 没有 restoredFrom 参数且硬编码 null，必须用最小受控接口扩展 patch 解决，不能篡改 staging 后的 JSON 使其与已存对象/hash 不一致。

4. **提案生命周期。** 实现 `GET /articles/{id}/proposals`、`POST /proposals/{id}/accept`、`POST /proposals/{id}/reject`，分别遵循 ProposalPage、BaseVersionRequest、ReasonRequest、ArticleVersion、DispositionResult 等冻结契约。accept 携带冻结要求的 If-Match；reject 按当前契约不额外强加 If-Match。提供给上游生成模块的提案入库应用端口，固定其 baseVersion/来源/内容及必要关联，不擅自增加公开创建路由。提案创建/拒绝不改变正文；接受必须验证当前 base、状态与 Owner，同一提案即使用不同幂等 key 并发接受也只能产生一次业务结果。拒绝必须有理由，失效或已处置提案不得再次改变头。T17 等模块负责收费生成，本任务不调用真实 LLM 或实施重写生成器。

5. **并发、AI 结果与失效事务。** 实现冻结 `VersionCommand.commit` 的 T07 应用边界；人工提交前，在同一事务锁定文章、核对 ETag/base、使旧执行 fencing 失效、追加版本/移动头、触发所需失效、写审计和幂等结果。缺 If-Match=428、旧值=412、base/状态冲突=409；总顺序保持鉴权→幂等重放→新命令前置条件。晚到 AI 结果保存为候选/历史并暴露冲突，不覆盖人工头，不伪装成功提交当前头。当前 T06 prepare/append 只允许 current base，必须明确区分“提交当前头”和“保留旧执行候选”的受控路径；不得把旧 base 偷换成当前 base，或绕过真实 fence/deletion/CANCELLED 守卫。保留原执行所用输入/配置快照，不把最新 Skill 当作旧 AI 结果的来源。

6. **存储、编号与失败恢复。** 继续遵守事务外 staging、事务内业务行/引用/审计/幂等及提交验证；失败不得留下半成品业务结果。检验版本号在并发 staging、人工保存及候选追加时的唯一性/递增，不能只依赖无锁 `max+1`。不能在持有业务事务期间发起对象网络 IO，不将失效回调的进程内收集器说成可靠事件投递。

## 未完成依赖的处理

定义清晰的 T10/T11 协作端口与事务契约，真实适配缺失时生产行为必须明确拒绝（503/FEATURE_NOT_READY 或冻结的依赖错误），不得用默认 no-op 返回成功。可以使用明确标注的事务参与者替身，验证 T07 原子提交/回滚、旧 fence 冲突和不可覆盖语义；必须说明尚未证明真实调度/可靠 outbox/崩溃恢复。真实查询和不依赖缺失能力的功能应实际完成，不能把整个模块做成 503 占位。

上游参考/依赖状态的缺口需登记并提供可执行接入方案。对任何需要受控 T06 扩展的部分，交付最小 patch、隔离接线及相应 T06 回归；不得修改已批准生产文件后仍声称 T06 基线未变。

## 验证要求

- 真实 PostgreSQL + HTTP Session/CSRF + Local ObjectStore 的隔离 clean test，验证准确 DTO、状态码、ETag、幂等与数据库结果，输出样本另用标准 JSON Schema 校验器验证。
- 覆盖人工保存/任意两版 diff/RESTORE/提案接受拒绝，Original 与历史不可改，同文章 FK、跨 Owner/跨文章隐藏、无效引用、CANCELLED 和 deletion_pending。
- 覆盖缺/旧 ETag、base 冲突、鉴权早于重放、重放早于 ETag；同 key 并发保存、不同 key 并发接受同一提案、人工修改与晚到 AI 冲突、版本号竞争。
- 通过故障注入证明对象暂存/引用提交、fencing/失效参与者、审计或幂等记录失败时，头/版本/提案处置状态不出现部分成功。替身和真实组件在证据中逐项标明。
- 恢复只生成新版本，不自动恢复旧 QA/批准/使用依据；用真实已存在适配或明示替身验证，缺依赖的生产行为单独测试拒绝。
- 空库迁移及含既有 T03/T05/T06 数据的升级；不更改旧行或已执行迁移。若修改上游补丁，针对实际影响复跑 T06 已通过用例（含三轮原始 Markdown 反例），保持其有效。
- 跑冻结 27 项保护、Git 可见文件密钥扫描、diff 空白检查和 patch 可应用性检查。T02 既有 6 条指纹误报单列，T07 不得新增扫描告警；指纹用 path/sha256 分字段保存。

不要使用证据收集器自身退出 0 代替失败子命令；不要将 skip/mock 声称为真实集成成功。隔离运行的输入、副本变换、工具版本、命令/退出码、JUnit、Schema 样本和实际结果均应可追溯，停止临时数据库并保留证据。不要覆写前三轮失败记录来“转绿”。

## 交付

形成 `E:/project/codex/wxAgent/docs/execution/reports/T07.md`：逐项映射需求/AC、列出文件或限定提交、输入与交付指纹、真实结果、失败/未执行/替身、迁移与共享 patch、T06 接口扩展的影响、T10/T11 接入条件及剩余限制。记录当前共享脏工作区，若提交只提交本人拥有的文件，绝不整体暂存他人改动。

完成后在本任务给出报告路径和审核入口，状态为“提交主 agent 独立审核”。不要自行批准验收或修改主 agent 的审核结论。

# T05 首轮审核整改报告

日期：2026-10-04（Asia/Hong_Kong）。依据：[T05-Review-v1.0](../reviews/T05-Review-v1.0.md)。

作者结论：R01–R07 已完成实现修复及回归验证，提交复审；不代替独立审核结论，不声明完整 CI、G1 或生产验收通过。

## 整改与验证对应

| 审核项 | 修复 | 验证 |
|---|---|---|
| R01 Prompt 输出契约 | Writer 改为 `WriterOutput`，Reviewer 改为 `ReviewOutput`；Revision 顶层仅含 `writer/itemDecisions`，意见字段为 `itemId/disposition/reason`。同步 Skill 清单，说明模型输出与服务端 ArticleVersion/ReviewReport 包装的边界。不存在的 `$ref` 明确拒绝 | 四个 Prompt 的名称、引用、绑定一致；固定输出样例逐一通过冻结 Schema；缺必填、错误嵌套字段、持久化包装混入与未知引用均拒绝；原审核 Writer 反例通过 |
| R02 发布后不可变 | 三个数据库触发器改为完整行对比并显式列出可变列。所有状态下 `id/created_by/created_at` 不可变；Skill/Policy 发布后仅允许合法 `status` 转换及 `updated_at/lock_version`；Prompt 发布后仅允许后两项。其他内容和发布审计元数据被冻结 | 运行账号三表改主键均被拒；内容、版本、创建和发布元数据篡改均明确得到触发器 `P0001`，原行保持不变。合法草稿编辑、Skill 发布/退休、Policy 退休继续成功。审核主键反例通过 |
| R03 游标 | 签发与验证均签名 Base64 payload；Skill 游标升级为 v2，包含 Owner 与规范化 status。版本游标保持 Owner/Skill 绑定 | HTTP Skill/版本逐页遍历与完整集合相等，无重复；正常下一页成功；篡改、跨 Owner、跨筛选、跨 Skill 使用被拒。审核游标反例通过 |
| R04 输出 Schema 绑定校验 | 名称必须存在于冻结 `$defs`，且等于精确 Prompt 的 `$ref`；创建、编辑、发布共用验证；修正作者夹具的四种实际输出类型 | 不存在名称及 Analyzer 错绑 `WriterOutput` 均在创建、编辑被 422 拒绝且不持久化。模拟旧草稿后发布被 `PROMPT_OUTPUT_SCHEMA_INVALID` 拒绝，状态仍为 DRAFT；审核反例通过 |
| R05 状态筛选 | 通过相应状态版本的 `EXISTS` 筛选 Skill 身份，不依赖活动指针，也不因多个匹配版本重复身份 | 只有草稿、已发布与草稿并存、多草稿、已退休、Owner 隔离及单项分页覆盖；三种状态完整遍历均与数据库集合一致；审核草稿反例通过 |
| R06 最新版本选择 | Policy/Prompt 查询按 major/minor/patch 分别转为 numeric 排序，并只取最新发布版本 | 覆盖 `1.0.9 → 1.0.10 → 1.9.0 → 1.10.0 → 2.0.0 → 10.0.0`，旧版本按 ID 仍可读；审核语义版本反例通过 |
| R07 版本 diff | 新增 `SkillConfigDiff`，经 `SkillService.diff(actor, fromVersionId, toVersionId)` 比较两个精确配置版本；先分别校验 Owner，再要求同一 Skill；允许比较已发布版与待发布草稿。返回版本 ID、差异种类、JSON Pointer 路径及 before/after | 新增/删除/修改、数组顺序、路径转义、显式 null、相同配置、发布版与草稿比较均覆盖；任一输入版本越权均 404，不同 Skill 为 422。未新增冻结 HTTP 端点 |

diff 中对象字段按名称排序，数组按索引比较；结果用于展示配置差异，不是可直接应用的 JSON Patch。新增/删除端的缺失值为 Java null，显式 JSON null 保持 NullNode。

## 实际执行结果与证据

最终从全新隔离 backend 副本执行 `clean test`，真实 PostgreSQL 17.11、真实 HTTP/会话/CSRF/幂等路径：**49 项，49 通过，0 失败、0 错误、0 跳过**。

- 原有 31 项（14 离线 + 17 PG/HTTP）通过。
- 新增 12 项（5 离线 + 7 PG/HTTP）通过。
- 保留的 6 个独立审核反例，原源码原样注入隔离副本执行，全部通过；未修改原审核证据。
- 正式批准契约 27/27 指纹一致，运行时 Schema 与批准文档字节一致。
- `git diff --check` 通过；T05 业务源、资源与测试指纹见检查证据。
- 无收费 Provider 调用。数据库最终停止成功。

证据：

- [最终命令、退出码、脱敏日志](../../../tests/engineering/T05/evidence/revision-v1-final.json)
- [测试明细、契约检查及源码指纹](../../../tests/engineering/T05/evidence/revision-v1-final-checks.json)
- [PG/HTTP 测试 XML](../../../tests/engineering/T05/evidence/revision-v1-final-test-results/TEST-com.example.editorial.editorial.skill.T05PostgresTest.xml)
- [Prompt 契约测试 XML](../../../tests/engineering/T05/evidence/revision-v1-final-test-results/TEST-com.example.editorial.editorial.skill.PromptContractTest.xml)
- [清理记录](../../../tests/engineering/T05/evidence/revision-v1-cleanup.json)

首个沙箱启动受限令牌错误保存在 `revision-v1.json`；获得权限后宿主隔离执行成功。`revision-v1-host.json` 保存首轮 48 项成功结果；补充合法草稿编辑/政策退休正向用例后最终 49 项成功，未覆盖首轮记录。

复现命令（项目根目录，需本机允许启动临时 PostgreSQL）：

```powershell
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' tests/engineering/T05/integration.py --evidence-name revision-v1-final --include-review-cases
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' tests/engineering/T05/check_revision.py revision-v1-final
```

## 范围与尚未完成的集成

此次仅修改 T05 自有实现、资源、测试、迁移草案及报告。工作区既有 T02/T03/T04 修改保留；没有提交、切分支、安装正式迁移或改冻结 OpenAPI/Schema、公共 DTO、根构建与路由。

1. 验证方式仍是隔离副本中接入 T03 身份配置与 V1 草案，再安装 T05 V2 草案。T03 尚未正式合入，因此未验证从上一正式集成版本保留数据升级。当前修正的是尚未正式发布的基线资源；不会在现存数据库中原地改写已发布 Prompt/Skill。若已有环境使用旧基线，正式升级必须新增不可变版本并显式接线，不能以本轮空库测试代替升级验收。
2. `ConfigChangeSink.InMemory` 明确记录为事件收集替身，未证明回滚隔离、提交后可靠投递或崩溃恢复。发布/退休 Skill 不能自动改旧文章任务；Owner 主动更换文章 Skill 的事务、新 generation、失效传播归 T06/T11，仍待集成。
3. 历史读取允许 RETIRED；新建文章或主动切换必须由调用方要求 PUBLISHED。StyleSnapshot 由 T06 组装，PolicySnapshot.rules 的 ObjectRef 与 T04 读取适配尚未实测。
4. 固定输出样例通过 Schema 不等于真实模型或 AC-27 全链路通过。未调用真实 Provider，也未执行正式 QA/批准/导出流程。
5. 本轮未重跑无关前端、Docker/S3、完整 Gitleaks 或全 CI；上一审核记录的 T02 扫描指纹误报及 T04 S3 环境限制不在本次修复范围内。

原交付报告中“无替身”、发布事件直接触发新 generation，以及子集校验器支持范围的过度描述已同步更正。

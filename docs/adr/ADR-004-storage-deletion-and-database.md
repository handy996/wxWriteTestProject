# ADR-004：数据库权限、环形 FK、明确删除

本轮修订：具体线格式/生命周期以 ADR-005 为准；删除journal与恢复以 ADR-006 为准。旧段落描述的未定事项已在这两份候选中补设计，仍待复审。
状态：REVIEW_CANDIDATE；变更申请 CR-T00-001/003，尚无已执行迁移。

`tables.json` 的普通 prerequisites 为建表 DAG，先按拓扑建立基础表，再通过 ALTER 安装 deferredForeignKeys。每个有 articleId 的对象具有 UNIQUE(article_id,id)，跨对象 FK 使用复合键；不能只验证 UUID 存在。自引用 parent/restoredFrom 要求同文章且版本号更小，应用与数据库约束共同保证。JSON/polymorphic 引用由受控写入口和约束触发器处理，记录保留引用，不伪装成原生 FK。

article_job.original/current 在创建事务内暂可空，插入 Original 后回填；延迟到提交的 constraint trigger 检查两者非空、Original.kind=ORIGINAL 且属于本文章。普通 NOT NULL 无法实现此流程。插入/更新均触发，防止后续设置 NULL。完整可执行 SQL 由 T06 交给主 agent 分配 Flyway 版本；本卡的 migration-draft.sql 仅为约束方案，未在 PostgreSQL 运行。

运行角色对不可变产物仅 SELECT/INSERT；可变表按 lock_version 更新并审计；配置草稿可编辑，发布后由触发器锁住内容，仅允许受控退休状态。image_selection 仅开放 active 列更新。审计仅追加。运行账号无 DDL、全局 DELETE 或绕过触发器权限；迁移账号和 retention_worker 分开。业务服务须通过各表拥有者写入口，不将权限模型当作模块边界的替代。

归档只是 archivedAt，不清数据。CR-T00-001 提议 GET `/articles/{id}/deletion-impact` 返回绑定 lockVersion 的 impactHash、版本/审批/对象数量、保留字段和 hold；POST `/articles/{id}/deletion` 提交 impactHash+reason，要求 If-Match 和幂等，在同事务取消运行并 fencing，异步清除正文、对象、个人数据。预览 15min 失效，过期/不匹配 409/412；未知保留要求或有效 hold 返回 DELETION_HOLD，不悄悄归档代替。删除中的文章禁止新命令。


对象采用 stage -> hash/size verify -> DB reference commit -> mark complete。每 24h 后仅清理超过 TTL 且任何当前/历史引用均不存在的孤儿。明确删除通过 retention 服务有序解除引用，不靠宽泛 CASCADE 误删别的文章。签名 URL 5min，授权后发放。SafeFetch 只 HTTPS，DNS 解析后绑定已检查公网地址，每跳重查，阻断私网/环回/链路本地/metadata、IPv6 与混淆 IP，最多 5 跳，不携带认证 cookie 到重定向目标。

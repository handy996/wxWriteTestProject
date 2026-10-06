# T02 数据库与迁移边界

`backend/docker/bootstrap.sql` 仅由数据库管理员在**空数据库**执行一次：创建三个独立角色、两个 schema、撤销 PUBLIC 的数据库/公共 schema 权限。运行角色与迁移角色不互相继承；retention 角色没有登录权限和任何领域授权，留待 T37 的受控删除路径。

应用启动只用 Flyway。`R__t02_schema_permissions.sql` 是可重复的基础权限收紧脚本，不含领域表，不占用主 agent 的全局 V 序号。它只撤销默认/公共授权和运行账号 DDL 权限，不一刀切撤销既有配置草稿表的 UPDATE。运行账号不拥有 schema、表或函数；迁移账号持有 DDL。

R01 增量修复保留上述已执行脚本原字节，新增以下两步，不分配全局 V 序号：

- `beforeMigrate__t02_function_defaults.sql` 在每次 Flyway migrate 的版本迁移之前，以迁移角色撤销**当前数据库全局**默认函数 EXECUTE，并清除 editorial 中叠加的 schema 默认授权。新函数必须逐个显式 `GRANT EXECUTE ... TO editorial_runtime`；禁止通过默认权限批量授权运行账号。
- `R__t02_function_permissions.sql` 在 history 中记录一次增量修复：仅撤销 editorial 内、editorial_migrator 所有的已有例程的 PUBLIC EXECUTE（包含 ACL 为 NULL 的默认授权）。按完整参数签名处理重载；保留已有 runtime 显式授权，不碰其他 owner/schema 或表、列权限。RESTRICT 遇到依赖时失败，不使用 CASCADE 扩大撤权。

原因与顺序依据：[PostgreSQL 17 默认权限](https://www.postgresql.org/docs/17/sql-alterdefaultprivileges.html)、[Flyway 回调事件](https://documentation.red-gate.com/flyway/reference/callback-events)。schema 级 REVOKE 不能抵消全局默认，修改默认权限也不会追溯修改旧函数。因此不能只依赖最后执行的 repeatable。回调自身不写 history；新增 repeatable 及部署文件指纹提供审计证据。领域迁移不得重新开放 PUBLIC 或默认批量 EXECUTE；有意提供的能力须使用对象级显式授权。

升级时先停止旧应用，再以修复版执行迁移；新应用 readiness 放行前完成已有函数修复。需事先核对依赖 PUBLIC 的调用，必要时在相应领域迁移显式授予最小权限。修复不能保护仍在运行的旧进程；不要并行运行旧版完成滚动升级。其他所有者/其他 schema 的函数不属于本脚本处理范围，应由其所有者审核。不要回滚到会重新引入宽泛默认权限的旧初始化流程。

新业务迁移采用 `V<主agent分配序号>__<领域>_<意图>.sql`。作者交付草案，主 agent 检查 T00 的表所有权、FK 拓扑和延迟约束后分配版本。已经执行并合入的迁移不得改写；更正必须新增版本。建表和权限在同一版本中交付：不可变产物 SELECT/INSERT、可变表按需要 UPDATE、selection 仅 UPDATE(active)、发布内容触发器保护、审计只追加。不得全局授权所有表 UPDATE 或 DELETE；运行账号不继承迁移或 retention 角色。

Flyway history 独立放在 `editorial_migrations`，运行账号既没有 schema USAGE，也没有 history 表读写权限。应用固定 `ddl-auto=validate`、`sql.init.mode=never`、`clean-disabled=true`、`baseline-on-migrate=false`，空库之外禁止隐式 baseline。`DatabaseRolePolicy` 在 readiness 放行前查询有效角色/权限，防止 JDBC URL 中凭证或数据库角色成员关系绕过用户名配置。

T02 未安装 T00 的 `migration-draft.sql`，没有提前创建任何领域表或 FK。集成测试仅在新建测试数据库内临时创建 `t02_permission_probe` 验证默认权限和显式列授权，最后删除。

函数回归另有 `tests/engineering/T02/fixtures/function-order/V1__t02_function_order_probe.sql`，只通过测试命令的额外 filesystem location 加载，**不打包进应用，不是全局 V1 分配**。它在版本迁移内部立即断言默认拒绝，能检测把修复错误放到 repeatable 阶段的回归。`integration.py --legacy-jar <b115a40.jar> --evidence-name <name>` 从真实旧版升级，验证旧 history 不变、旧函数撤权、显式重载授权保留、新函数先拒绝后授权，以及重启后权限继续有效。

恢复与回滚：本次无业务数据迁移。不要用 Flyway clean 或降权回滚已授权领域权限来恢复业务。已有部署升级失败应停止应用、保留历史表和日志，由主 agent 修正新迁移；有业务数据后按 T37 的备份恢复和保留删除手册执行。禁止因密码改变而删除数据库卷。

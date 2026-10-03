# T02 数据库与迁移边界

`backend/docker/bootstrap.sql` 仅由数据库管理员在**空数据库**执行一次：创建三个独立角色、两个 schema、撤销 PUBLIC 的数据库/公共 schema 权限。运行角色与迁移角色不互相继承；retention 角色没有登录权限和任何领域授权，留待 T37 的受控删除路径。

应用启动只用 Flyway。`R__t02_schema_permissions.sql` 是可重复的基础权限收紧脚本，不含领域表，不占用主 agent 的全局 V 序号。它只撤销默认/公共授权和运行账号 DDL 权限，不一刀切撤销既有配置草稿表的 UPDATE。运行账号不拥有 schema、表或函数；迁移账号持有 DDL。

新业务迁移采用 `V<主agent分配序号>__<领域>_<意图>.sql`。作者交付草案，主 agent 检查 T00 的表所有权、FK 拓扑和延迟约束后分配版本。已经执行并合入的迁移不得改写；更正必须新增版本。建表和权限在同一版本中交付：不可变产物 SELECT/INSERT、可变表按需要 UPDATE、selection 仅 UPDATE(active)、发布内容触发器保护、审计只追加。不得全局授权所有表 UPDATE 或 DELETE；运行账号不继承迁移或 retention 角色。

Flyway history 独立放在 `editorial_migrations`，运行账号既没有 schema USAGE，也没有 history 表读写权限。应用固定 `ddl-auto=validate`、`sql.init.mode=never`、`clean-disabled=true`、`baseline-on-migrate=false`，空库之外禁止隐式 baseline。`DatabaseRolePolicy` 在 readiness 放行前查询有效角色/权限，防止 JDBC URL 中凭证或数据库角色成员关系绕过用户名配置。

T02 未安装 T00 的 `migration-draft.sql`，没有提前创建任何领域表或 FK。集成测试仅在新建测试数据库内临时创建 `t02_permission_probe` 验证默认权限和显式列授权，最后删除。

恢复与回滚：本次无业务数据迁移。不要用 Flyway clean 或降权回滚已授权领域权限来恢复业务。已有部署升级失败应停止应用、保留历史表和日志，由主 agent 修正新迁移；有业务数据后按 T37 的备份恢复和保留删除手册执行。禁止因密码改变而删除数据库卷。

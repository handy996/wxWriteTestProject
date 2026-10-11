# AI Editorial Agent

T02 工程骨架：一个 Java 21 / Spring Boot 3.5 application、PostgreSQL / Flyway、Vue 3 / TypeScript。只提供启动状态页，没有文章业务能力。**内部编辑草稿，尚未完成事实与版权核查；不能批准或正式导出。**

开发契约为主 agent 已审核的 `1.0.0-rc.3`，证据见 [T00 审核记录](docs/execution/reviews/T00-rc3-approval.json)。首次输入基线为 `74c25251248752205f82d6c909fb3815b08fd8e9`。不重新生成或修改已审核公共契约。

## 一条开发启动入口

前置：Docker Engine / Docker Desktop 已启动，Docker Compose v2 或兼容新版，以及 Python 3.12+。在项目根目录执行：

```sh
python backend/scripts/dev.py up
```

首次运行生成被 Git 忽略的 `infra/.env`，为数据库管理员、迁移账号、运行账号各生成不同随机密码。随后构建镜像、从空库初始化、执行 Flyway，并等待数据库相关 readiness。成功后访问 **http://127.0.0.1:8080**。初次构建需要访问软件仓库；这不调用模型或其他收费 Provider。缺少 Docker、构建失败或 readiness 超时都会非零退出。

```sh
python backend/scripts/dev.py logs
python backend/scripts/dev.py down
```

`down` 保留数据库卷。再次 `up` 应复用数据库和已执行迁移。不要手动删除数据卷来掩盖迁移失败。已有卷不会因修改 `.env` 自动轮换密码，需要部署管理员按数据库流程轮换。

隔离测试可指定 `--env-file <临时文件>` 和环境变量 `COMPOSE_PROJECT_NAME`，避免复用开发配置或数据库卷；正常开发无需指定。

也可复制 `infra/env.example` 到 `infra/.env`，填入三个不同的至少 16 字符密码，然后直接使用 Compose：

```sh
docker compose --env-file infra/.env -f infra/compose.yml up -d --build
```

数据库与后端没有发布宿主端口，网页只绑定本机。该 Compose 是开发入口；HTTPS、生产 secrets、备份、保留删除及正式部署由 T37 集成，不以 `prod` 配置名代表生产已就绪。

## 配置与能力状态

| 配置 | 行为 |
|---|---|
| `mock`（默认） | 显示 mock 模式；尚无任何 Provider adapter，四项真实能力均不可用 |
| `dev` | 不启用 mock；缺失能力明确显示，不能调用真实 Provider |
| `prod` | 拒绝混入 mock、自动建表、关闭 Flyway 等配置；安全 Cookie 开启 |
| `editorial.providers.paid-calls-enabled=true` | 所有模式均拒绝启动，直到 T08/T09 经主 agent 集成预算与调用门禁 |

本骨架只暴露 `/actuator/health`、`/actuator/health/readiness` 与无敏感信息的 `/actuator/info`。info 的 `available=false` 表示尚未接入；mock 不会伪装 text/vision/search/generation 成功。业务 API 默认拒绝访问，T03 接管身份验证，T30 接管 router/client/store；本任务没有创建根路由或业务 API。

环境变量 `DB_URL`、`DB_RUNTIME_PASSWORD`、`DB_MIGRATION_PASSWORD` 用于后端。账号名固定为 `editorial_runtime` 和 `editorial_migrator`。Flyway 使用独立账号和 `editorial_migrations` schema；业务 schema 为 `editorial`。运行账号无建表、临时表、删除、历史迁移表或迁移角色权限。新领域表默认不授权，由各表迁移显式授权。详见 [迁移约定](backend/src/main/resources/db/README.md)。

## 本机构建和验证

安装 Java 21、Maven 3.9.11、Node 24.15.0、npm 11.12.1。版本及来源见 [依赖记录](backend/DEPENDENCIES.md)，前端使用锁文件安装。

```sh
mvn -B -ntp -f backend/pom.xml clean verify
npm --prefix frontend ci
npm --prefix frontend run build
python -m pip install -r tests/contracts/T00/requirements.txt
python tests/engineering/T02/check_contracts.py
python -m unittest discover -s tests/contracts/T00 -v
node tests/contracts/T00/hash-vector-js.cjs
python tests/engineering/T02/check_contracts.py
python tests/engineering/T02/secret_scan.py
python tests/engineering/T02/scan_secrets.py --gitleaks /path/to/gitleaks
python tests/engineering/T02/dependency_scan.py
npm --prefix frontend audit
```

契约测试仅使用冻结夹具和离线参考实现，不能证明领域服务集成。不要运行 T00 的生成器来“修复”指纹差异。Maven 漏洞检查仅将 SBOM 中包名与版本发往公共 OSV API，任何匹配或服务不可用均失败；npm audit 同样不能用忽略退出码冒充通过。

无 Docker 时，安装带 `initdb/pg_ctl/psql/createdb` 的 PostgreSQL **17.11** 完整二进制，可验证真实数据库和打包应用：

```sh
python tests/engineering/T02/integration.py --pg-bin /path/to/postgresql/bin --java /path/to/java
```

该测试新建独立临时集群、随机密码和本机端口，验证空库启动、第二次启动、权限和生产配置反例，最后停止自己的进程。临时数据保留在被忽略的 `tests/engineering/T02/.work/`，不包含用户文章。不要指向已有生产集群。完整容器测试为 `python tests/engineering/T02/compose_smoke.py`，只清理自身随机项目和卷。

审核整改回归：`integration.py` 可增加 `--legacy-jar <审核版本b115a40的JAR> --evidence-name <新记录名>` 验证真实升级；默认也会检查新函数默认拒绝、显式授权成功和重启保持。`python tests/engineering/T02/compose_smoke.py --entrypoint` 则实际调用开发入口 `up → down → up`，检查数据、迁移历史、页面/API 代理、函数权限和生产 mock 拒绝，最后删除自身测试卷。两个容器测试均使用本机 18080 端口，请顺序运行。

CI 已接入构建、类型检查、契约指纹/回归、Gitleaks、依赖扫描与 Compose 启动测试。当前交付的实际运行结果、失败记录和待集成项见 [T02 报告](docs/execution/reports/T02.md)，由主 agent 审核，不代表最终验收。

CI 还会实际执行 T08 成本测试：使用 Compose 中固定摘要的 PostgreSQL 镜像创建独立临时容器，应用正式迁移，要求 28 项单元测试和 37 项数据库测试全部执行、零失败、零跳过，并在结束时删除自己的测试容器。默认 Maven 构建仍会跳过需要真实数据库的测试，不能单独替代这一步。安装仓库固定的 Maven/JDK、准备好 `.tools/t02/m2` 离线依赖缓存后，本地可复跑：

```sh
python tests/engineering/T08/run_pg.py --docker --expect-tests 65 --expect-skipped 0
```

Cookie 检查在 CI 中先执行当前守卫测试，再验证本次生成的证据；命令记录使用仓库相对路径，Maven 启动器按 Windows/Linux 选择，JDK 指纹来自同一次运行。证据保存到独立目录，不覆盖历史受审记录：

```sh
python tests/engineering/T03/record_guard_binding.py --jdk .tools/t02/jdk-21.0.12.1+1 --evidence-dir .work/ci/t03
python tests/engineering/T03/check_session_cookie.py --evidence-dir .work/ci/t03 --output .work/ci/t03/agreement.json
```

CI 将上传 Cookie 检查记录、T08 运行记录和 Surefire 原始结果。测试数量变化时，须同步审核更新 `--expect-tests`，不能通过允许跳过来满足计数。

各项扫描独立执行；已有构建成功时，后续 npm、Gitleaks 控制、Compose 和失败报告探针会继续运行，任何真实门禁失败仍使流水线失败。探针只在隔离副本新增 1 条必败 JUnit 用例，要求运行器返回失败并保留原始 XML；它不计入正常成本测试的 65 项。上传步骤使用 `always()`，同时收集原始报告目录作为复制失败时的后备路径。

Compose 的后端镜像使用仓库根作为构建上下文，`backend/Dockerfile.dockerignore` 仅放行源码和冻结测试输入。手工构建请在仓库根执行 `docker build -f backend/Dockerfile .`，使容器中的契约夹具测试也实际执行。T02 完整控制还需要历史基线提交，CI 因此使用完整历史检出。

本次验证结果和未闭合事项见 [CI 修复记录](docs/execution/reports/CI-Portability-20261009.md)。离线 Maven 构建不生成 SBOM；依赖扫描须在在线 `verify` 生成清单后执行。

2026-10-11 的 [干净 GitHub Actions 验收](docs/execution/reports/CI-Acceptance-20261011.md) 已完成：Cookie、成本 65 项零跳过、构建/Compose、密钥/npm 扫描及失败报告下载通过；Maven OSV 两项公告仍阻塞整条流水线，按用户决定另行 [Boot 4 迁移](docs/execution/plans/Boot4-Migration.md)。

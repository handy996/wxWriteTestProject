# CI 可移植性与数据库自动执行

本次交付把 CI 修复与已有 T02 R06、T03 R11 整改分开提交。T03 记录器的“先校验再发布”属于 R11；相对命令记录、平台启动器、独立证据目录属于 CI 修复。T08 第六轮复审目录仍在工作区，未作为本次交付提交。

## 变更

- Cookie 命令按其所属仓库根归一化，兼容历史 Windows/Linux 绝对路径与新相对路径；仍拒绝外部依赖目录、错误 Maven 版本、额外参数和伪执行命令。
- CI 在线构建后，重新执行 15 项守卫测试并记录当前 JDK、Surefire 与输入指纹，再检查同一次运行的证据。历史受审记录不被覆盖。
- T08 新增 Docker PostgreSQL 入口，复用 Compose 固定摘要镜像，使用临时密码、随机本机端口和正式迁移；要求 28 项单元 + 37 项数据库测试全部执行、零失败、零跳过。原生 PostgreSQL 入口保留。退出时删除本次容器及匿名卷。
- CI 上传 `.work/ci` 下的 Cookie、成本记录和 Surefire 原件。运行器还检查必需测试类及 XML 声明数与实际 testcase 数的一致性。

## 已验证

2026-10-08 的实测原件已按字节复制到 `tests/engineering/CI/evidence/20261009/`，`manifest.json` 记录原路径、交付路径、大小和摘要。原件内的绝对路径属于当时隔离运行，不是后续复跑路径。

| 验证 | 实测结果 | 入库证据 |
|---|---|---|
| Windows Cookie | 15 项，失败/错误/跳过均 0；106 负向拒绝、36 良性通过 | `windows-cookie/` |
| Linux `/workspace` Cookie | 15 项，失败/错误/跳过均 0；106 负向拒绝、36 良性通过 | `linux-cookie/` |
| Docker PostgreSQL | 65 项，零失败/错误/跳过，容器已清理 | `docker-cost.json` 与 XML |
| 原生 PostgreSQL | 最终 runner 65 项，零失败/错误/跳过，集群已停止 | `native-cost.json` 与 XML |
| 新增可移植性与 PG 判定回归 | Windows/Linux 均 9 项通过 | `linux-validation.log.txt`；Windows 结果见本次集成记录 |
| T08 静态与反向控制 | 16/16；77 削弱拒绝、8 良性通过；blind/misplaced/brittle 均 none | 两份 `*-checks` / `*-controls` 日志 |

2026-10-09 集成补验：Windows 11 个回归测试方法通过（上述 9 项 + 记录器 2 方法/7 子场景），当前 workflow 下 Cookie gate 为 106/36；T02 结构 19/19、控制 223/223、零 NOTE；冻结契约 27 哈希一致；自有扫描与完整 Gitleaks 扫描退出 0、零命中。结果见 `integration-checks.json`、`integration-cookie.json` 和同目录日志。T03 审计补跑与故意红控的退出码另见 R11 报告。

Docker 实跑早于 `judge_suites` 提取及 testcase 数检查；最终 runner 已由原生 PostgreSQL 实跑和 5 项判定回归覆盖。此后记录器仅修正原子发布的注释边界，并新增拒绝发布回归测试；未改变已验证的正常运行路径。

## 复跑

从仓库根目录运行；先安装 CI 固定工具链并通过在线 Maven `verify` 准备 `.tools/t02/m2`。Windows Maven 使用 `mvn.cmd`，Linux 使用 `mvn`；以下 Python 入口会选择平台启动器。

```sh
python tests/engineering/T03/test_recorder.py
python tests/engineering/T03/test_portability.py
python tests/engineering/T08/test_pg_runner.py
python tests/engineering/T03/record_guard_binding.py --jdk .tools/t02/jdk-21.0.12.1+1 --evidence-dir .work/replay-cookie
python tests/engineering/T03/check_session_cookie.py --evidence-dir .work/replay-cookie --output .work/replay-cookie/agreement.json
python tests/engineering/T08/run_pg.py --docker --work-root .work/replay-cost --evidence-name replay-cost --expect-tests 65 --expect-skipped 0
```

输出目录与名称应为本次新建，避免覆盖历史结果。记录器针对多个文件的替换不是事务；使用独立目录隔离不同运行。

## 尚未验证或仍待处理

- 未执行远端 GitHub Actions：仓库没有配置 remote。Linux 实测使用项目固定摘要 Maven 镜像，其实际 JDK 为 Temurin 21.0.9；workflow 指定 21.0.12.1。它证明 Linux 路径与证据流程可用，不等于配置工具链下整条 Actions 已通过。
- 在线依赖扫描、SBOM、前端和 Compose 完整工作流没有在本次重新验收。离线 Maven 不生成 SBOM，不能据此声称依赖扫描通过；`dependency_scan.py` 缺件诊断仍待整改。
- T08 YAML 绑定来源判据仍有绕过问题：已有 T1/T3 探针能通过静态门。65 项数据库测试通过不证明绑定来源主张闭合；第六轮复审与后续整改仍待完成。
- T02/T03 独立复审、T03 人工批准、T04 真实私有桶等原有门槛未关闭；本次不提升 G0/G1/G2 状态。

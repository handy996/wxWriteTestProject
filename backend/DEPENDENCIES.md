# T02 版本与维护来源（2026-10-03）

| 组件 | 锁定版本 | 维护 / 发布来源与边界 |
|---|---|---|
| Java | Eclipse Temurin 21.0.12.1+1 | [Adoptium releases](https://adoptium.net/temurin/releases/?version=21)，Windows/CI 压缩包均校验官方 SHA256；容器另按摘要固定 |
| Maven | 3.9.11 | [Apache Maven](https://maven.apache.org/download.cgi)，Maven Central 压缩包及 SHA512 |
| Spring Boot | 3.5.16 | [3.5 系统要求](https://docs.spring.io/spring-boot/3.5/system-requirements.html)，保持 SRS 的 Boot 3.5；不因能下载就宣称当前免费维护或已购买商业支持 |
| PostgreSQL | 17.11 | [PostgreSQL 17 发布说明](https://www.postgresql.org/docs/17/release.html)，Compose 固定官方镜像摘要；测试使用相同主/补丁版本 |
| Node / npm | 24.15.0 / 11.12.1 | [Node 发布目录](https://nodejs.org/download/release/v24.15.0/)、npm 官方 registry；package engines、CI 和构建镜像一致 |
| Vue / Pinia / Element Plus | 3.5.43 / 4.0.3 / 2.14.7 | 官方 npm 包的精确版本，完整传递依赖见 frontend/package-lock.json |
| Vite / plugin-vue | 8.3.2 / 6.0.9 | 官方 npm 包；构建验证通过 |
| TypeScript / vue-tsc | 5.9.3 / 3.3.12 | 首测 TypeScript 7.0.2 与 vue-tsc 不兼容，保留失败证据后固定兼容版本 |
| Gitleaks | 8.30.1 | [官方发布](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1)，Windows/Linux 下载 SHA256 校验 |

Maven 传递依赖由 Boot BOM 管理，构建后产生 `target/sbom/application.json`，与 IDE 可能清理的中间 classes 目录分离。T02 首次扫描发现默认 BOM 中五个组件有公告匹配，在同一兼容分支固定以下安全补丁并重建复扫：

| 覆盖属性 | 最终值 | 修复依据 |
|---|---|---|
| log4j2.version | 2.25.5 | [Apache 公告](https://logging.apache.org/security.html#CVE-2026-49844) |
| jackson-bom.version | 2.21.7 | [Jackson databind 官方仓库](https://github.com/FasterXML/jackson-databind)、[Jackson core 官方仓库](https://github.com/FasterXML/jackson-core)，相关公告及范围见证据 |
| tomcat.version | 10.1.60 | [Apache Tomcat 10 公告](https://tomcat.apache.org/security-10.html) |
| postgresql.version | 42.7.13 | [pgJDBC 公告](https://github.com/pgjdbc/pgjdbc/security/advisories/GHSA-j92g-9f8w-j867) |

完整匹配与修复范围见 [公告核对记录](../tests/engineering/T02/evidence/advisory-review.json)，本次实际解析的 78 个组件另存为 [SBOM 证据](../tests/engineering/T02/evidence/resolved-maven-sbom.json)。没有忽略漏洞匹配，也没有启用收费安全服务；公开 OSV/npm 数据库仅表示查询时已知公告，不能证明没有未知漏洞。扫描服务不可用时 CI 失败。

容器基础镜像在 Dockerfile/Compose 中固定 tag + 多架构清单 SHA256；登记在 [工具来源](../tests/engineering/T02/evidence/tool-sources.json)。摘要避免 tag 漂移，但不会自动取得未来补丁。上线前由主 agent/T37 复核 Boot 3.5 支持来源、所有系统镜像漏洞及更新策略。本次没有采购商业支持或进行真实生产部署。

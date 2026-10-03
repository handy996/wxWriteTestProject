# ADR-006：删除日志独立于业务备份的恢复屏障

状态：REVIEW_CANDIDATE / `1.0.0-rc.2`。闭环CR-T00-003；没有新增第39张领域表，也未部署外部存储。

## 保存位置、内容、权限与保留

现有WorkflowExecution/Step保存删除命令及本地进度，AuditLog保存最小操作引用，二者不作为恢复后防复活的唯一来源。另由T04/T37部署**独立恢复域**的私有删除journal（独立bucket/账号或独立持久卷，不在应用DB/对象的整套回滚清单内）。目录按deploymentId/sequence组织，幂等键为deletionId+phase，顺序追加，记录类型采用DeletionJournalEntry。索引/head、签名密钥版本及签名校验信任根也不得从被回滚数据库恢复。

记录只有随机deployment/article/deletion UUID、REQUESTED/PURGE_COMPLETED、时间、序号、前项hash、签名和retainUntil，无姓名、原文、联系方式、来源摘录、普通用户认证令牌。数据加密保存；删除写入服务只追加/查幂等，恢复角色只读，独立保留角色按政策清理；业务Owner不能列举其他删除记录。请求身份在原业务审计留最小化证据，不在journal重复保存可直接识别内容。

研发默认journal最少保留45天（30天备份窗口+恢复/排障余量），且**所有含该文章的可恢复备份都已到期或安全销毁之前不得清理**。备份延长/离线副本未核销会同步延长journal；无法证明无旧备份时保留并触发保留待办，不允许例行TTL先删。生产最终保留期/hold仍由OQ-16责任人确认；未确认不得宣称生产删除策略已验收。清理后保留签名范围检查点，恢复不得越过覆盖下界。

## 命令与失败顺序

1. 影响预览、Owner、ETag、impactHash、hold校验后，在业务短事务写入幂等删除命令并fencing/禁止新写。外部journal IO不占DB事务。
2. 将REQUESTED追加至独立journal，获取签名回执并保存至本地命令，**成功持久化后才返回202**。同deletionId重试取同回执。如果journal不可用，返回503 DELETION_JOURNAL_UNAVAILABLE且删除不执行，原命令保留等待/对账；幂等记录不得把尚未登记的命令重放成202成功。
3. 先登记REQUESTED再清理正文/对象/个人数据，全部活跃库与对象引用处理完成后追加PURGE_COMPLETED，才将operation标SUCCEEDED。若DB在外部登记后崩溃，独立journal仍要求删除，恢复worker按articleId/deletionId幂等重建进度。追加完成失败时不对用户假报删除完成。
4. 已接受删除不得自动撤销。hold必须在登记前解决；后续法律保留冲突进入受控人工流程，不能悄悄删掉外部journal以恢复正文。已计费调用仍结算最小账目，晚到输出不得重新建被删正文。

## 从早于删除的备份恢复

应用恢复后保持maintenance模式，Worker/导出/用户查询均不开放。从**独立journal服务**读取当前签名head和备份捕获的journal序号，验证部署身份、链完整性、覆盖起点和每段签名。即使旧数据库完全没有删除命令，也会看到备份之后的REQUESTED。重放全部相关删除（包括只有REQUESTED尚无COMPLETED的条目），对缺失文章视作幂等成功，清理恢复的正文/对象和查询缓存。

所有序号已验证到当前head、没有缺口、所有删除均落实后，记录RestoreBarrier；再次读取head，若前进则继续重放，最后用恢复锁/只读窗口切换对外服务。`restore_allowed`只验证这些边界条件，真实锁和签名实现在T04/T37。journal不可访问、head验证失败、备份早于覆盖下界、缺序号、仍有未重放删除时**禁止开放服务**，不能拿旧DB的“没有删除记录”作为通过理由。

## 待真实集成证据

需要T04/T06/T10/T37在独立存储故障、追加成功DB失败、备份在删除前、journal有缺口、并发新增删除、延长备份保留六类场景验证。当前仅交付Schema、顺序协议和拒绝开放的mock反例；签名、WORM/权限、对象清理和真实恢复耗时均未测试。此设计待主agent复审，不冒充灾备验收。

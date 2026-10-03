# 表归属及 FK 图（候选）

完整字段/索引/权限见 tables.json；实线是普通建表依赖，虚线是后置安装的延迟 FK。运行时引用环不等于模块编译环。

| 表 | 唯一拥有者 | 运行时写权限 |
|---|---|---|
| app_user | T03 | OPTIMISTIC_LOCK_AND_AUDIT |
| editorial_skill | T05 | OPTIMISTIC_LOCK_AND_AUDIT |
| editorial_skill_version | T05 | DRAFT content editable; published content immutable; retire status only |
| policy_version | T05 | DRAFT editable; published rules immutable; retire status only |
| prompt_version | T05 | DRAFT editable; published templates immutable |
| article_job | T06 | OPTIMISTIC_LOCK_AND_AUDIT |
| article_version | T06 | INSERT_ONLY |
| analysis_result | T12 | INSERT_ONLY |
| rewrite_plan | T13 | INSERT_ONLY |
| fact_claim | T16 | INSERT_ONLY |
| fact_verification | T17 | INSERT_ONLY |
| source | T15 | OPTIMISTIC_LOCK_AND_AUDIT |
| source_snapshot | T15 | INSERT_ONLY |
| claim_source | T17 | INSERT_ONLY |
| review_report | T14 | INSERT_ONLY |
| review_item | T14 | OPTIMISTIC_LOCK_AND_AUDIT |
| change_proposal | T07 | OPTIMISTIC_LOCK_AND_AUDIT |
| image_slot | T19 | OPTIMISTIC_LOCK_AND_AUDIT |
| image_candidate | T24 | OPTIMISTIC_LOCK_AND_AUDIT |
| image_asset | T23 | OPTIMISTIC_LOCK_AND_AUDIT |
| image_variant | T23 | INSERT_ONLY |
| image_generation | T25 | OPTIMISTIC_LOCK_AND_AUDIT |
| license_metadata | T22 | INSERT_ONLY |
| image_selection | T24 | Only active may UPDATE; new caption/variant/license -> new row |
| license_manifest | T26 | INSERT_ONLY |
| release_candidate | T27 | INSERT_ONLY |
| qa_report | T27 | INSERT_ONLY |
| human_review | T28 | INSERT_ONLY |
| manual_task | T11 | OPTIMISTIC_LOCK_AND_AUDIT |
| workflow_execution | T10 | OPTIMISTIC_LOCK_AND_AUDIT |
| workflow_step_execution | T10 | OPTIMISTIC_LOCK_AND_AUDIT |
| agent_execution | T09 | OPTIMISTIC_LOCK_AND_AUDIT |
| tool_execution | T09 | OPTIMISTIC_LOCK_AND_AUDIT |
| cost_ledger | T08 | OPTIMISTIC_LOCK_AND_AUDIT |
| idempotency_record | T03 | OPTIMISTIC_LOCK_AND_AUDIT |
| export_artifact | T29 | OPTIMISTIC_LOCK_AND_AUDIT |
| audit_log | T03 | INSERT_ONLY |
| provider_config | T09 | OPTIMISTIC_LOCK_AND_AUDIT |

```mermaid
graph LR
  editorial_skill --> app_user
  editorial_skill_version --> editorial_skill
  editorial_skill_version --> policy_version
  editorial_skill_version --> prompt_version
  article_job --> app_user
  article_job --> editorial_skill_version
  article_version --> article_job
  article_version --> app_user
  workflow_execution --> article_job
  workflow_step_execution --> workflow_execution
  agent_execution --> workflow_step_execution
  agent_execution --> prompt_version
  tool_execution --> agent_execution
  tool_execution --> workflow_step_execution
  analysis_result --> article_version
  analysis_result --> editorial_skill_version
  analysis_result --> agent_execution
  rewrite_plan --> article_version
  rewrite_plan --> analysis_result
  rewrite_plan --> agent_execution
  review_report --> article_version
  review_report --> agent_execution
  review_item --> review_report
  review_item --> article_version
  change_proposal --> article_version
  source --> article_job
  source_snapshot --> source
  fact_claim --> article_version
  fact_verification --> fact_claim
  fact_verification --> policy_version
  claim_source --> fact_verification
  claim_source --> source_snapshot
  image_slot --> article_version
  image_asset --> article_job
  image_variant --> image_asset
  image_candidate --> image_slot
  license_metadata --> image_candidate
  license_metadata --> image_asset
  image_generation --> image_slot
  image_generation --> image_asset
  image_generation --> agent_execution
  image_selection --> image_slot
  image_selection --> image_asset
  image_selection --> image_variant
  image_selection --> license_metadata
  image_selection --> app_user
  license_manifest --> article_version
  license_manifest --> policy_version
  release_candidate --> article_version
  release_candidate --> license_manifest
  release_candidate --> editorial_skill_version
  qa_report --> release_candidate
  human_review --> release_candidate
  human_review --> qa_report
  human_review --> app_user
  manual_task --> article_job
  manual_task --> workflow_execution
  cost_ledger --> article_job
  idempotency_record --> app_user
  export_artifact --> release_candidate
  export_artifact --> human_review
  audit_log --> app_user
  article_job -.-> article_version
  article_job -.-> workflow_execution
  article_job -.-> analysis_result
  article_job -.-> review_report
  article_job -.-> qa_report
  article_job -.-> release_candidate
  article_version -.-> article_version
  article_version -.-> agent_execution
  editorial_skill -.-> editorial_skill_version
  editorial_skill_version -.-> editorial_skill_version
  image_candidate -.-> license_metadata
```

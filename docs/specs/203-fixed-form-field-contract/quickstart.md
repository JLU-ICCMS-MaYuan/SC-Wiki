# 操作与验证

## 标准键变更

先对照data-model.md及backend/data/scientific_form_contract.v1.json审查字段。更改键、类型或含义须有用户审查的Issue/Spec变更登记；升级清单及锁定摘要，并保持Go内嵌副本一致。人工扩展通过页面人工入口新增，模型不能代办。

运行 npm run test:field-contract --prefix frontend、npm run test:form-contract --prefix frontend、npm run test:form-contract:mutation --prefix frontend，并执行受影响Python/Go回归及前端构建。证据与旧失败见validation.md。

## 本机迁移

专用入口scripts/migrate_fixed_form_contract.py只接受127.0.0.1:3307/scwiki。SCWIKI_FORM_CONTRACT_RESOLUTIONS仅在存在已逐条核对的声子冲突决议时设置，路径指向私有JSON；不得给未解决冲突生成默认选项。

1. 两项代码先完成验证。在本机原生环境暂停经PID/进程组核实的Python、Go、上传worker和其他写入入口；等执行作业及数据库事务结束，保留未来重试记录。
2. 使用项目Conda Python执行专用工具并指定--output，得到真实SQL/Redis备份、JSON精确数字补档、隔离恢复/迁移报告。不要使用业务库做测试写入。
3. 确认报告passed，且implementation指纹和冲突依据未变化；在同一停写窗口执行--apply-local --preflight-report 对应报告路径 --output 新私有备份目录。
4. 实际SQL提交成功后同步已有草稿缓存；复查数量、科学值、来源、谱、结构和历史保护摘要，验证保存重读。
5. 恢复先前确实运行的服务，检查Python/Go健康接口和前端。本机已执行头是204；源码的并行160头明确暂缓，不执行其他任务迁移。更新受测结构清单必须来自隔离演练，不得删除核验绕过失败。

本次真实回退备份：.data/backups/issue203-204-local-applied/。其目录700，SQL、原JSON及缓存600，均不提交Git。原始解析制品及历史快照不清理。

## MySQL DDL失败恢复

失败后保持停写并保存现场，不依赖ROLLBACK撤回DDL。使用已核对本次备份在空隔离库恢复，先调用scripts.local_deploy.storage.restore_mysql，再调用scripts.migrate_fixed_form_contract.restore_exact_json恢复exact-json.json，核对备份前inventory一致；本轮已真实演练。

业务库若需要恢复，也必须在持续停写且确认目标仍为上述授权实例时，以完整备份恢复其原有结构和数据，再恢复upload-cache.json中的原缓存及有效期，最后核对迁移头、数量和全部保护摘要，才恢复写入。不能仅导入SQL而漏掉精确JSON补档或让旧缓存覆盖数据库。不在失败后stamp，不修改旧迁移补救。

## 当前边界

新完整宿主可看到“材料状态类型”，用户旧现场及失败预览尚未实际复现。真实PDF字段和结构归属重跑不等于整篇上传成功；远程Spec、CI和阿里云未经本次授权执行。

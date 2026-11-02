# 实施任务

- [x] T001 归档原话、两张原图与开源/官方入口研究（US4）。
- [x] T002 实现内容分类与单原文入口（US1/US2，FR-001至003）；UI/API例证见 quickstart.md。
- [x] T003 实现官方RSS目录、Crossref范围/词形修正和OpenAlex可选Key（US3，FR-004/005/007）；真实源样本已保存。
- [x] T004 实现部分成功保存与有界重试，并验证完整成功水位（FR-006）；Python专项通过。
- [ ] T005 Python/Go/前端专项、隔离页面与真实源验证已完成；外站原文直达待用户浏览器确认，不因应用侧通过而勾选整项。
- [x] T006 更新Overview/README及旧#88替代说明，纳入本任务独立提交并回写Issue。

后续目标环境与可选Key实际接入均未确认，不在已完成运行操作范围内；本地代码完成与完整上线验收分别记录。

顺序T001→T002/T003→T004→T005→T006；不执行未确定目标环境的重启、批量回填或发布。

## US5 增量任务

- [x] T007 扩大氢相关检索与候选入口，保存摘要及可用关键词；真实 DOI 可进入候选（FR-009）。
- [x] T008 新增候选表迁移及三态模型相关性判断，只将 related 发布到资讯（FR-010/011）。
- [x] T009 接入短批 Worker，验证指纹去重、更新重判、过期结果、失败恢复和重试上限（FR-012）。
- [x] T010 真实样本、默认模型、隔离迁移和资讯回归，记录未验证范围（SC-005至007）。
- [x] T011 更新 Overview/验证记录并回写 Issue；仅提交本次文件，不推送或部署（SC-008）。

US5验收依据：relevance-validation.md及assets/verification/relevance-*；业务迁移/部署与本轮新增文档远程链接仍未执行，原T005保持未完成。


## 本机迁移补充任务

目标已明确为本机原生 `127.0.0.1:3307/scwiki`。以下更新原先“目标未确认、业务迁移未执行”的当前结论，历史记录不改写。

- [x] T012 在私有备份与隔离恢复中验证 `alembic/versions/20261102_0160_news_candidates.py`，比较全部既有数据与结构，记录 `local-migration-validation.md`（FR-014、SC-009）。
- [x] T013 只增加候选表结构描述并更新 `scripts/local-deploy-schema.json`、`scripts/local-deploy-versions.json`、`scripts/local-deploy-macos.json`，准确执行本机资讯迁移并严格核验（FR-015、SC-010）。
- [x] T014 恢复已核实的资讯进程，验证本机资讯 API 与服务健康，清理隔离库，同步 Overview/Issue 并仅提交本次文件（FR-016、SC-010）。

顺序 T012 → T013 → T014。不得把本机完成宣称为 Git 推送、远程部署或原 T005 全部通过。

T012-T014证据：local-migration-validation.md及assets/verification/local-migration.json；73张既有业务表保持，实际双头/严格核验/健康通过，101项资讯与48项部署回归通过、11项跳过。Go因启动时读取迁移头清单一并重启。原T005保持未完成；Git提交按仓库自动提交要求执行。

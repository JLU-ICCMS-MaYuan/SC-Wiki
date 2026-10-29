# 实施任务：检索双视图与详情导航

输入：[Spec](spec.md)、[Plan](plan.md)、[Research](research.md)、[数据模型](data-model.md)、[契约](contracts/search-results.md)。用户已授权开始实现；勾选以validation.md中的本地证据为准，远程链接／推送／部署另列。

## 阶段1：实施基线

- [x] T001 重新读取#178全部产物、#32／49／56／59／142／171／174相关规格，审阅技术Plan及筛选真实字段映射，完成实施基线核对；远程链接保留为关闭门待核验，不擅自推送。
- [x] T002 在tests/03_data_search_and_database_discovery/search-results-browser.mjs建立固定1论文／8状态／12Tc及无Tc／独立模型／多页夹具，先验证当前布局、旧表计数和返回故障。

## 阶段2：服务端集合

- [x] T003 [US1] 在goserver/handlers/search_results_test.go新增状态、论文distinct／多页／同状态多Tc／跨状态假命中测试，确认旧查询不能满足需求。
- [x] T004 [US1] 在goserver/handlers/search_results.go与goserver/main.go实现新结果接口、稳定排序、真实计数及页级摘要，不依赖当前Tc一页。
- [x] T005 [US2] 在goserver/handlers/search_results_test.go及隔离MySQL用例覆盖无Tc、独立结构来源、已关联去重、current／approved revision、不同身份公开边界。
- [x] T006 [US2] 在backend/api/structural_records.py及对应backend/tests/test_structural_records.py实现独立模型服务端过滤与准确计数，保持原详情和其他消费者契约。

## 阶段3：同页双视图

- [x] T007 [US1] 在frontend/src/lib/searchNavigation.ts及tests/03_data_search_and_database_discovery/search-navigation.test.tsx实现URL规范化、双视图页码、旧地址兼容和非法值恢复行为。
- [x] T008 [US1] 在frontend/src/pages/SearchPage.tsx和frontend/src/components/SearchResults.tsx实现右上同页切换、默认论文和状态列表；移除旧Tc表与局部记录详情，避免影响正式论文／图表。
- [x] T009 [US2] 在frontend/src/components/PaperStructuralCollection.tsx及SearchResults.tsx实现独立结构区、状态模型入口去重和来源论文新标签，维持无模型时真实缺失。
- [x] T010 [US1] 在tests/03_data_search_and_database_discovery/search-results.test.tsx覆盖同页切换／计数／筛选保留／空错重试／快速切换迟到响应。

## 阶段4：返回恢复与链接

- [x] T011 [US3] 在frontend/src/lib/searchNavigation.ts实现同源return校验，PaperDetailPage.tsx／StructuralRecordPage.tsx／PaperEditView.tsx按合法来源恢复，清理固定上传约束。
- [x] T012 [US3] 在tests/03_data_search_and_database_discovery/search-navigation.test.tsx及search-results-browser.mjs覆盖新开／刷新／前后退／来源丢失／外站绕过，正式路由验证视图与页码。
- [x] T013 [US4] 在AppShell.tsx、MyPapersList.tsx、UploadPage.tsx、AdminPage.tsx、share.tsx、community的EntryCard.tsx／ModelAnswerCard.tsx按Spec矩阵改原生新标签；同一文件串行，保护未保存表单。
- [x] T014 [US4] 在tests/02_identity_governance/sidebar-navigation.test.tsx及相关上传／社区宿主测试覆盖全部新标签和维持例外，验证#171认证复用。

## 阶段5：评论退役

- [x] T015 [US4] 在PaperCommunity.tsx／CommentPanel.tsx及SystemCommunityPage.tsx、SearchPage.tsx、share.tsx、DiscussionPage.tsx、DiscussionAnswerPage.tsx核对并移除评论／回复与体系入口，保留AI问题／答案和引用。
- [x] T016 [US4] 在goserver/handlers/community_entries.go及相关按ID／写入处理退役评论和回复接口，不改历史数据；通知失效目标给清晰反馈。
- [x] T017 [US4] 在goserver/handlers/community_test.go及tests/07_researcher_community_forum相关用例验证旧客户端评论读取／发布／编辑／回复被拒绝，AI、引用、非评论通知正常，审核意见不受影响。

## 最终阶段：验证与文档

- [x] T018 执行Go及隔离MySQL、前端宿主、适用两项form-contract、既有受影响回归和生产构建，在本目录validation.md记录命令／源码／结果／基线差异。
- [x] T019 执行1400px／390px真实路由浏览器验收，逐条SC-001～009留存标签、地址、截图和请求证据，不以静态文本断言替代。
- [x] T020 功能实现后使用overview-maintainer更新搜索／论文结果／社区Overview和README使用说明，按#178同步#15取舍及其他关联约束，不自动关闭旧Issue。
- [ ] T021 本地FR／SC收敛和任务范围提交见validation.md；远程Spec链接实际访问仍待授权推送后核验，Issue保持OPEN。此项部分完成，不以本地交付代替远程关闭门。

## 依赖与执行顺序

T001→T002→T003→T004；T005验证T004并阻断T006后对外集成；T007→T008→T009／T010；T011→T012；T013→T014；T015→T016→T017；最后T018→T019→T020→T021。同一共享文件不得交叉写入，未完成前置不继续假定契约有效。

## 需求覆盖

| 来源 | 任务 | 证据计划 |
| --- | --- | --- |
| FR-001～002；SC-001 | T002、T007～010 | 新结果标签与同页切换 |
| FR-003～005、007、010～011、017；SC-002～003 | T003～006 | 未分页参考集合、MySQL与审核权限 |
| FR-006、018；SC-008 | T002、T008、T019 | 旧表退役与真实宽窄屏 |
| FR-008～009；SC-006 | T005～006、T009、T019 | 无状态模型／不同300GPa入口 |
| FR-012～013、019；SC-005 | T007、T010～012 | URL、迟到响应、合法return |
| FR-014～015；SC-004 | T013～014、T019 | 导航完整矩阵 |
| FR-016；SC-007 | T015～017 | 评论读写退役与AI回归 |
| FR-020；SC-009 | T018～021 | 请求无科学写入、合同／基线与文档收敛 |

## MVP与增量

先交付有真实集合查询的同页默认论文／状态切换，再接结构与返回，最后矩阵和评论退役；每项经过独立验收。完整Feature只有全部验收及文档关闭门满足才可关闭，不能以MVP替代其余已采纳范围。


## 执行证据

T001～T020对应实现、测试和文档证据统一见[validation.md](validation.md)及其实际日志／浏览器／基线文件；没有用源码字符串断言替代交互和查询。T021保留远程文档链接门，不自动推送或关闭。

# 实施任务：本地模型 Demo

输入：[Spec](spec.md)、[Plan](plan.md)、[Research](research.md)、[数据与接口](contracts/demo.md)。

## 准备与真实推理

- [x] T001 在 `demo/scripts/prepare.py` 获取固定版本原始数据、结构、索引和完整 CSO 权重，逐对象校验，并保留许可证。
- [x] T002 在 `demo/inference.py` 实现真实结构推理和公开参数模型；在 `demo/tests/validate_models.py` 与作者结果及公开公式对照，验证新输入和非法输入。

## US1：训练数据可下载、可溯源

- [x] T003 [US1] 在 `demo/catalog.json` 和 `demo/server.py` 实现数据清单、只读预览和白名单原文件下载；校验大小与摘要，缺失时不返回伪文件。
- [x] T004 [US1] 在 `demo/src/App.tsx` 展示相邻模型与数据、下载／原网址／许可／版本／数据边界，提供复制与预览。

## US2／US3：两类分组与真实结果

- [x] T005 [US2] 在 `demo/src/App.tsx` 接入真实模型运行、按模型显示结果和错误，保留原站估算入口。
- [x] T006 [US3] 在 `demo/src/styles.css` 完成桌面和窄屏布局，标明输入差异、外推边界与未接入状态。

## 验收与交付

- [x] T007 在 `demo/tests/browser.cjs` 实际访问本地服务，验证运行、下载字节、原始链接、错误与移动端；保存 Demo 验证记录。
- [x] T008 在 `quickstart.md` 与 `docs/overview/07_AI_Assisted_Tc_Estimation/README.md` 回写实际使用方式和边界；核对 Issue、任务范围并只提交本次文件。

## 依赖与覆盖

T001 → T002／T003 → T004／T005 → T006 → T007 → T008，执行时不并行修改同一文件。T001／003／004 覆盖 FR-002／003／014–016、SC-001／002／008；T002／005 覆盖 FR-005／007／008／010、SC-003–005；T004／006 覆盖 FR-004／006／009／013、SC-006／007／009；T007／008 覆盖 FR-001／011／012／017、SC-010。

本任务表仅技术拆解；完整功能状态以 Issue #162 为准，不因 Demo 完成关闭完整 Feature。

## 验证依据与后续边界

T001：固定 Git blob 校验、100 权重与原数据实际获取；T002：assets/demo-model-validation.json 的三样本近似回归、训练 RMSE、新输入与失败边界；T003–T007：assets/demo-browser-validation.json 的真实推理、五个文件完整下载、复制／预览／移动端验证；T008：Quickstart、Overview 和 Issue 最新说明。T001 只表示已取得文件的准备完成，不把 Xie 2022 上游失败算作下载通过。

- [ ] T009 补齐 Xie 2022 原始训练 ZIP（demo/scripts/prepare.py），按发布方 MD5 核验并用原始表复现；当前外部存储 503，已在 Demo 显示缺口。
- [ ] T010 后续完成完整网站接入、原有经验模型校准数据核查与独立科学评测；保持 Issue #162 OPEN，不以本地 Demo 完成替代。

- [x] T011 在 `demo/src/main.tsx` 复用 `frontend/src/theme.ts`，统一 `demo/src/styles.css` 和品牌呈现；`demo/tests/browser.cjs` 比较当前主站实际样式并验证原交互，覆盖 FR-018／SC-011。

- [x] T012 在 demo/src/App.tsx、styles.css 中集中右侧来源、实现等高并移除预览，在 demo/server.py 退役废弃接口；浏览器检查全部模型卡片几何与下载，覆盖 FR-019 至 FR-021、SC-012／013。
- [x] T013 核查 model-name-source.md 所列论文，更新 demo/catalog.json 的模型原称，通过 demo/vite.config.mjs 和 App.tsx 复用原接口，实现当前页上传与结果；真实 API 对照和窄屏验收覆盖 FR-022／SC-014。

- [x] T014 在 demo/src/App.tsx 收敛“论文链接／原始网站”文字入口、移除裸网址与许可版本、合并同仓库重复入口；浏览器验证 FR-023／024、SC-015。
- [x] T015 在 demo/scripts/prepare.py 和 catalog.json 生成并展示一份 BETE 数据整包；assets/demo-bundle-validation.json 验证 1212 个作者原文件、806 个结构及来源说明，真实浏览器下载验证 FR-025／SC-016。

- [x] T016 在 demo/inference.py、demo/src/App.tsx 中实现默认内容识别、上传／粘贴恢复 auto、明确格式不匹配错误与结果格式标记；使用用户原文 demo/tests/fixtures/MgB2.POSCAR 和 tests/structure-format.cjs 验证 FR-026／027、SC-017／018。

# 实施任务：上传校对页全部折叠与展开

**输入**：[spec.md](spec.md)、[plan.md](plan.md)、[research.md](research.md)。业务数据模型和API不变。

## 准备

- [x] T001 创建#141、核对用户确认及原话，建立本目录需求、计划、研究、检查表和原图归档。

## US1／US2：两层统一控制（P1）

- [x] T002 在`frontend/src/context/MaterialStateControlsContext.ts`与`frontend/src/pages/UploadPage.tsx`提供顶部槽位及窄屏布局。
- [x] T003 在`frontend/src/components/MaterialStatesEditor.tsx`复用按钮，通过Portal接入顶部，统一控制材料卡片及物性模块。
- [x] T004 在`tests/01_decentralized_uploading/upload-expand-collapse-all.test.tsx`验证两层切换、输入保留、重复操作、空状态及隔离；运行相关回归、构建和浏览器验收。

## 收尾

- [x] T005 更新`README.md`、上传Overview、`validation.md`及本目录检查表；核对增量并回写Issue；Git提交号在提交成功后追加到Issue。

## 依赖与执行顺序

按T001→T002→T003→T004→T005串行；同一共享文件保留原改动。US1/US2共用一个处理函数。

## 需求覆盖

T002覆盖FR-001/006；T003覆盖FR-002～005；T004验证SC-001～003；T005完成文档及交付。任务仅记录技术拆解，未完成协作状态以#141为准。

# 实施计划：核对进度
**Issue**：[#168](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/168)
**日期**：2026-10-28
**Spec**：[spec.md](spec.md)

## 摘要与技术上下文
React 19/TypeScript 5.6/MUI 7，Python FastAPI、Redis/RQ及现有数据库。pytest与Vitest、Playwright验证。目标是现有网页共用核对流程，不部署。每次准备请求使用独立随机标识，服务端在原同步流程的完成边界记录少量状态，前端并行轻量轮询；不把整个科学快照放入进度接口。
## 质量门
| 来源 | 要求 | 满足方式 |
|---|---|---|
| AGENTS | mayuan、范围隔离、自动提交 | 分支检查、明确路径暂存、保留既有拖动参数 |
| Spec | 真实百分比 | 服务端准备事件与现有批次计数 |
| #147 | 不改变审核语义 | 只插入进度观察和取消检查 |
| 文档门 | 用户确认与远程链接 | 已确认；远程链接仅待推送的交付门，未经授权不推送 |
## 文档结构
本目录包含Spec、Plan、Research、数据模型、contracts/progress.md、Tasks、Quickstart、需求检查与验证记录。
## 源代码结构
- backend/ingest/evidence_progress.py：独立准备状态、取消与请求绑定。
- backend/api/evidence.py：在summary/jobs/submit-check插入完成事件和进度读/取消路由。
- frontend/src/lib/evidenceProgress.ts：准备请求轮询、流程百分比。
- frontend/src/components/EvidenceWorkflow.tsx：绑定运行身份、渲染和终态。
- frontend/src/i18n/{zh,en}/evidence.ts：当前阶段与完成说明。
- tests/01_decentralized_uploading/：行为和HTTP/浏览器验证。
## 设计
准备请求以可选progress_id关联当前用户命名空间；独立GET只返回阶段，DELETE写取消墓碑。Redis原子检查防止迟到请求覆盖取消。原科学接口权限与版本检查保留，旧调用不传标识时保持原返回契约。
每个前端运行持有独立取消回调，关闭、重试和换目标时抑制旧响应；准备未完成时按服务端阶段更新，进入后台任务后按20+floor(75*完成/总数)显示，最终响应成功校验后100%。完成短暂呈现后沿原流程关闭，不新增确认按钮。
## 需求映射
| 来源 | 设计及数据来源 | 任务 | 验证 |
|---|---|---|---|
| FR-001/002，SC-001/002 | 准备检查点+批次计数 | T002–T004 | HTTP检查点与前端数值 |
| FR-003/004/005，SC-003 | 用户命名空间、取消墓碑、运行身份、最终响应 | T002–T004 | 取消竞态、失败、重试 |
| FR-006，SC-004 | 共用MUI、i18n | T004–T006 | 浏览器宽窄屏、英文与ARIA |
## 阶段与依赖
文档→测试及准备状态→接口接线→前端→集成验证→Overview与本地提交；共享文件串行。
## 复杂度说明
同步准备请求在返回前无法靠原任务轮询观测，因此加入独立、短期Redis进度，不改后台科学任务的所有权；拒绝计时伪进度及为展示进度重复读取科学来源。

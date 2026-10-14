# 正式四工具流程契约

关联 [实施计划](../plan.md)、[数据模型](../data-model.md)。FR-015–018、SC-010/011。

## 唯一入口与历史读取

POST /api/upload-tasks 接受 parser_profile 缺省/null/complementary，固定创建 complementary。其他新方案返回 422，内部创建同样拒绝其他值。PDF 正文与补充使用四工具；TXT/MD/结构附件保留原路由。旧任务 GET 和保存不重写 parser_profile，不自动重解析。

角色不明确时沿 needs_role_review 门暂停，上传者携带 expected_revision 确认完整角色表后复用同源制品。重试必须经过 retry API，不能直接把 failed 改为运行状态。

## 解析运行

MinerU 全文 basic OCR；Docling 处理表格页；Marker 处理公式/图像、损坏或空文字页。补强裁剪真实 PDF 并映射回原页。组件失败不换其他全篇方案。默认子进程超时 900 秒，最大 1800 秒；取消/超时先 SIGTERM，10 秒仍未退出则终止进程组。Marker finally 清理本次模型服务。

GROBID 调用本机 processFulltextDocument，禁用外部 consolidation。header 与 back/listBibl 分别消费；无参考表时不把 header 当自引。不可用保留状态/诊断和题录缺口。GROBID HTTP 取消在请求前后检查，单次请求最长 90 秒。

## DeepSeek 与来源

共享 JSON 调用显式 thinking.type=disabled、max_tokens=65536，记录 usage/finish_reason；截断拒绝，失败原始响应保留。Marker use_llm=False 不关闭本地 VLM。四个解析工具本地运行，DeepSeek 接收选中 IR 做科学提取与字段核对。

GROBID 题录确定性覆盖模型同字段，记录冲突及 XPath/坐标。缺字段沿原文提取和审核补缺，不编造期刊或页码。只取有效主文题录，引用继续按 DOI/唯一标题年份匹配，不由模型生成引用边。

quote_id 与本次 block_id 一致且引用同文件/页，服务器展开原文，不接受同时改写引句。传统 quote 同样严格定位。数值/范围/条件继续经科学契约、Claim、覆盖和提交前语义核对。
原文明示值与压力的唯一对应可以确定性补足空压力并拆分状态，绑定规则和原输入保留在 `_pressure_bindings`；不以稳定区间替代记录压力，无法唯一判断仍留空或拒绝。

## 草稿与正式记录

保存保留服务器 bibliography_sources/conflicts/parsing_conflicts，界面以安全文字显示差异。未定位候选和未覆盖结果不能伪装 ready。正式提交保持待审，文档和区域来源在同一事务绑定正式文件；批准/向量发布继续使用现有审核入口。

# 上传与搜索接口契约

## 创建、上传与启动

- POST /api/upload-tasks：新增可选 defer_parsing 布尔值，默认 false，兼容旧调用。
- 新网页发送 true；所有文件完成后保持 uploading，不自动模型调用。页面此时显示浅度、深度两个选择。
- POST /api/upload-tasks/{task_id}/finalize：可选 JSON parsing_mode=shallow/deep。新延后任务必须选择；旧调用缺省 deep。
- 同一原子操作固定模式并取得一次入队权；已启动任务不允许用不同模式重试改变路径。任务 DTO 返回模式与等待选择状态。

## 草稿和提交

- 浅度读取现有草稿 GET，编辑复用 /api/rag/evidence/draft-state 和 PATCH /api/rag/evidence/draft 的纯存储能力，不读取核对结果或执行核对；服务端保留流程绑定，只接受论文级内容，拒绝科学实体。
- 浅度 POST submit 不要求 evidence_job_id 或 expected_evidence_version；服务端根据任务及流程识别浅度。深度继续要求原核对条件。
- 浅度返回 paper_id 和 review_status=published；失败恢复 ready 并保留草稿；重复请求按 upload_task_id 幂等。
- published 仅表示直接收录，无审核人或人工审核事件。

## 搜索与详情

沿用 POST /api/papers/search/results，论文视图包含符合条件的 published 论文。
元素／化学式沿现有三种集合匹配；论文级索引来自 research_materials。Keyword 可匹配标题、DOI等论文信息。
压强、Tc和代表Tc条件不匹配无科学字段论文；论文计数与分页在并集去重后进行；状态视图不创建状态。
网站增加可达的论文信息检索入口，允许无元素条件的标题／DOI查询。
GET /api/papers/{id} 对访客公开 published 详情和原文件；UI显示“直接收录”，不显示审核通过。

## 权限边界

普通用户不得伪造浅度绑定为深度绕过审核，不获得全站目录创建或其他任务访问权。
未选择模式的任务不能启动。RAG、结构及物性检索保留原审核公开规则。

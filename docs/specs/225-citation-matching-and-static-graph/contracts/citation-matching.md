# 引用匹配接口

GET /api/upload-tasks/{task_id}/citation-matching：沿用所有者/现有管理员权限，先鉴权，只读已保存citation_matching，不调用模型。无任务404、无权403、尚无快照409 citation_matching_not_ready；源已变化标stale。返回{ok:true,data:{version,status,paper,references,downstream,source_signature,...}}。

references含原reference_index/原文、matched_paper（可空）和decision。downstream仅含实际命中当前论文的库内来源，按稳定ID去重。

模型返回程序给定键的对象，例如 `{"matches":{"0":{"paper_id":1204,"reason":"书目身份一致"},"2":{"paper_id":null,"reason":"候选无法确定"}}}`。键是本批在输入列表中的位置；程序逐键限定候选ID或null，全部键必填并禁止额外键。严格检查完整性、候选归属和当前身份；非法结果不修补、不当作成功缓存。每批最多16条，固定使用LLM2；模型版本标记同时进入实际请求正文和持久缓存键。

前端/upload/tasks/:taskId/citation-matching独立页；链接target=_blank、rel=noopener noreferrer。桌面三列，窄屏按左中右顺序；命中填色，未命中保留，不加高亮。

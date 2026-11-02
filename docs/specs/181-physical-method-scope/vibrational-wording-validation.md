# 简谐同义写法与 CaH6 重解析验证

## 已确认修复

对应 FR-017/018、SC-009/010。仅将新提取候选的 `harmonic approximation` 归一为 `harmonic`，原始响应和逐字证据保留；错误提示区分未知写法与 DFT/HF/DFPT 错类。没有增加其他科学同义词或放宽作用域门。

## 来源与运行边界

- 原任务：`4d95a4d2565049b6b30a3659cdd054b8`，原来在第 3 步失败，草稿为空表单；重试前再次核对草稿哈希及持久化草稿。
- 主文 `2012 CaH6-王晖.pdf`，SHA-256：`5a8f5279732264dc218b9ab865778768e37623127b8bd64bbce6135da101c8da`。
- 补充 `2012 CaH6--suppliment-王晖.pdf`，SHA-256：`630283a3cbfb7d8fb8624c957de2b9958f9ece57a28b3a78830647b32535d348`。
- 两份 PDF 通过存储层实际读取并核验；复用同哈希已成功的 IR，不宣称重新执行文字提取。主文第 4 页实际包含 “The calculation of the EPC is based on the harmonic approximation”。
- 原任务、空草稿和原解析制品已备份至本机 `.local/private-investigation-backups/4d95a4d2565049b6b30a3659cdd054b8-20261102T184102/`，不提交论文全文或模型凭据。
- 真实重解析使用原 `server:LLM2 / gpt-6.1-sol` 配置；调用正式 `retry_upload_task` 处理函数，保留所有者和失败状态检查，返回 202。这是处理函数调用，不是经过 HTTP 登录认证的端到端测试。
- 新 RQ 作业：`23b35c2a-4b2b-4f44-8d75-565e4b8fe310`。运行本机当前共享工作树，包含其他任务的 #203/#204 改动；本次提交只包含简谐修复，不能将整次运行归因于本次独立提交。

## 回归结果

1. 新增 14 项字段测试：修复前 4 失败、10 通过；修复后 14 通过。仅本次增量投影到 HEAD 的隔离副本同样 14 通过。
2. 两份原始失败响应（首次、纠错）经原始输入构建来源范围，走 `normalize_extraction(..., form_parameters=True)` 均通过：3 个材料状态、4 处 `harmonic`；归档原响应字节未改变。这是固定重放，与新的模型调用分开记账。
3. 表单契约 11 文件、132 项通过；变异门正确检出四宿主 8 项注入故障。
4. 相邻 Python 测试：当前共享树 42 通过、4 失败；将本次两个共享模块替换为修改前快照后，同环境基线 28 通过、4 失败。两次均使用 `DATABASE_URL=sqlite://`，失败名称和异常一致，无本次新增失败，不宣称相邻套件全绿。

相邻既有失败：旧 `extensions` 预期产生 `KeyError`；旧作用域测试预期 `method_category_mismatch` 而实际 `scope_ambiguous`；旧入口测试缺少隔离数据库表 `scientific_upload_drafts`；旧跨阶段 HF 关联预期 1 项而实际 0 项。未修改这些测试或扩大修复。

## 真实重解析结果

主文的新调用已完成，调用耗时约 98.6 秒，首次响应即返回 4 处 `harmonic`，正式分段校验通过。新制品位于任务目录 `chunks/3e5b50037c1c468694d7307c5650b8ba/extraction_attempts/00000/bf078c1168bf4999b1c2caf929cb46c2/`。

补充资料首次新调用耗时约 215.2 秒，校验报告：`payload：模型输出了未登记科学字段：description, pressure_ambiguity`。出错位置为 `material_states[0].property_modules[0].records[0].payload`，内容是 tI10-CaH4 费米能级态密度及其 50/150 GPa 归属疑问。它不是本次简谐同义词问题；压力是否确实含混尚未完成原图复核，不能把模型疑问当成论文结论。

补充资料的新制品目录为 `chunks/97758e92bd30496392518eec35b5bd7b/extraction_attempts/00000/225b73aa34cb45edbaa5e0e38a939f9d/`。现有管线自行执行一次契约纠错，未添加额外重试。发现后已向用户询问：先核对原图与上下文并展示方案，或停在本次简谐修复；未自行扩修。整篇后处理、草稿保存重读和科学验收尚未完成。

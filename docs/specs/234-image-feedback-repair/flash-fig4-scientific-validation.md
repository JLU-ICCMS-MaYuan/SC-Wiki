# Flash Fig.4科学读数与前置验收收尾

## 真实结果

原PDF SHA256：bf0725bea058339b814489fe213ec8285a0fca01eb5143da95254330eea06846。Flash始终为server:LLM1/deepseek-flash；本轮业务文献仍保留server:LLM2/gpt-6.1-sol和同一任务，浏览器模型未切换。

本轮flash-fig4-current-03由原PDF真实新调用13次，形成38条图4读数：10条H-derived DOS、10条lambda、18条Tc。PrH9两条Tc无可辨柱，仍未读，未补零。ScH6为300 GPa，DOS约0.0156、lambda约1.30、Tc约99/86 K、mu*=0.1/0.13。独立原始位图参照逐点核验数值、原柱横坐标/材料、压力、mu和单位，38条均零错误。

后续复用同原PDF/模型/provider和逐核心源码SHA一致的本轮有效IR，另发2次同Flash实际请求，完成正式normalize_extraction、assemble_candidates、fill_scientific_forms及JSON保存重读。scientific-verdict.json和form-scientific-verdict.json均passed，ScH6四字段及共同lambda真实归属、原图来源、约数与空物理uncertainty保留。

## 原因与通用修复

01/02在盘点阶段把三个面板重复填成相同外框；原page_inventory保护仍原样拒绝。补齐#234前置盘点反馈：错误页由原模型用实际600 DPI原图/图注重读，具体重复索引/坐标和无标签像素框候选随反馈提供；有效页面保持，重复无新依据停止，复用13动作预算，严格JSON错误不当几何问题重试。

旧Flash即使合法JSON仍仅6个候选，多处数字/材料柱错误。image_geometry只返回像素测得的轴线、刻度、色块、候选框和分辨率；不返回材料、物理量、单位、mu或科学数值。原模型判读标签与条件并选真实数据，原标定/柱边程序计算。当前crop和附加上下文分别声明region_id和坐标系，旧动作缓存保留，按几何版本读取当前事实。生产没有材料名单或论文值，源码中无本篇数值硬编码。

## 科学验收依据

测试专用fig4_pixel_reference.py核对原始879×632位图的印刷刻度和材料/图例标签，按基线连接的色柱独立测量；图例不当柱。3个原位图像素加刻度拟合残差为固定容差，不按模型自报大精度扩大。没有用正文或其他模型答案反推轴。旧Flash6候选检出39问题；同一参照也核验了已留存GPT38结果。测试参照只作断言，不进入模型提示或生产填写。

图示约数与正文精确陈述仍分别保留原来源；这不是选择所有场景“图优先”或“文优先”的新规则。

## 脚本故障及复用边界

03读图完成后，新增验收脚本的换行转义错误导致SyntaxError；原log和summary保留。仅修测试验证代码并编译，未改原响应或读图核心实现。flash-fig4-current-03-postprocess在核验原PDF/model/provider和backend逐文件SHA后复用成功IR，不把它算作第二次新提取；后续提取/填写回答真实新调用。旧检查点缺端点摘要已在resume.json披露，未伪造核验；本轮沿原LLM1配置，不主动换端点。

## MySQL与旧失败

9861300e已补原六项MySQL与七项过期夹具。本任务又以独立MySQL8.4.2实例复核79项、零跳过，覆盖原6项；使用随机端口60439及issue137_test_fe6fe4b20e18，未用业务3307，进程已停、目录已移除。当前旧失败和准入三文件16 passed，不再只单列为未处理。

对应原始日志mysql-current-verification/、old-seven-current-verification.log。最终Flash源码后独立MySQL又跑79项、零跳过；共享及独立源码140项、四宿主233、12变异、字段契约与编译通过。两次私有MySQL均停止且临时数据实际移除，不把跳过当通过。

## 仍未完成

这些是隔离前置门，不是整篇业务。原任务d789acceee124022b3257f84780d1156、Job2a43b499…仍保留，尚未送审、没有PaperID。接下来从原任务网页续跑：CeH10源条件交接、完整整理/字段审核/谱/引用、送审、真实拒绝/返修重提、通过日志批准、探索与正式库核验。排障轮全程通过后才按精确ID留证清理，再以相同原文件完成无需debug的最终五阶段。

完整证据：tests/TestForRealScenario/runs/20261110-peng2017-workflow-debug-01/。远程未push，四个Issue保持OPEN；官方OpenAI账号实调仍未覆盖。

补充边界：Flash对PrH9只能稳定给出无可定位独立值、value=null；其“截断/图例遮挡”因果措辞没有由原图证明，作为模型观察保留，不写成物理事实。38个可读数据的像素/材料/条件门通过，不表示所有自然语言诊断均可靠；PrH9不补零，范围排除规则不变。原复核flash-prh9-reason-check.json留证。

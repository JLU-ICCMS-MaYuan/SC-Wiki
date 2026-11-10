# 验证步骤：以PDF与版本化定位重建裁剪并供快照及RAG复用

本文件为当前可复核验收路径。已运行的范围、结果与未通过层见validation.md；命令不代表所有层自动通过。

## 前置条件

使用mayuan且按共享工作区隔离；Python使用项目环境`/Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python`，前端使用兼容Node运行时。测试用临时目录、内存/隔离数据库；原PDF按真实SHA核验，保留用户稿。每个任务起始固定一个支持图片的主模型，不新设Qwen/4090部署。

## 分层执行

1. 固定反例：从原失败/误裁建立能失败的测试；模拟响应只验证协议，不能替代真实像素或模型。
2. 真实PDF：从正文/SI及必要上下文生成区域，检查首次整图完整图注、局部区域、300/600 DPI、坐标、位图限制；图/表/文字/公式分别验收。
3. 实际API：在独立隔离任务分别验证已配置GPT/Flash，每个任务内部模型不变；核对实际图像输入、工具调用编号、回执、发送尺寸和未在提示出现的图像事实。
4. 自动修正：注入缺图例/错裁剪/柱内部采样失败等明确问题，要求实际工具动作及新依据；不能只看最终数值是否“像对”。
5. 正式后处理：受影响字段重新科学提取/整理/核对及保存重读，检查值、单位、材料、压力、物相、μ*和原图来源。程序积分与结构展开各自验证。
6. 恢复与复用：临时错误按#224五次规则，已成功面板不重跑；清理测试缓存后按同一定位重建，不调用模型找位置；旧快照不读取新版；RAG权限反例独立验证。

## 定向测试命令

```bash
DATABASE_URL="sqlite:///:memory:" PYTHONDONTWRITEBYTECODE=1 "/Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python" -B -m pytest -q -p no:cacheprovider \
  "backend/tests/test_pdf_regions.py" \
  "tests/01_decentralized_uploading/test_issue114_storage_regions.py" \
  "tests/01_decentralized_uploading/test_manuscript_handoffs.py" \
  "tests/05_rag_question_answering/test_visual_source_reuse.py"
```

上述路径本轮已存在并运行；完整509项回归路径及测试日志见共享验收证据。测试进程同时设置隔离JWT_SECRET_KEY和SC_WIKI_DATA_DIR，不能指向业务数据库。

科学共享路径实施后必须运行：

```bash
npm run test:field-contract --prefix "frontend"
npm run test:form-contract --prefix "frontend"
npm run test:form-contract:mutation --prefix "frontend"
```

## 记录与判定

记录原件SHA、源码/差异、模型及协议、图像摘要/尺寸/定位、提示/算法版本、复用与新请求、实际用量/耗时、失败/修正动作和层级结论。失败响应固定重放、真实新提取、保存重读、完整五阶段分别计数；未推送、未部署、未批准不宣称对应结果。

来源真实缺失保留无法确定；固定接口错误明确停止；技术故障不冒充论文未报告。验收不得以增超时、放宽断言、隐藏缺项或硬编码论文值通过。

## 真实Y-H局部回归

运行tests/TestForRealScenario/run_visual_sources_validation.py，分别传入--pdf原件路径、--model实际模型名和--output不存在的新目录；脚本每个任务固定一个模型，仅使用原PDF第4页，验证ScH6标量、正式normalize/候选组装/填写及JSON保存重读。目录不可覆盖，不访问业务草稿。此脚本会真实调用已配置模型并产生用量；结果不等于整篇解析或批准。

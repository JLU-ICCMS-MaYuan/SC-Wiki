# 验证步骤：统一固定视觉主模型的看图工具回执与实际图片传递

本文件是未来可执行验收路径，**本轮未执行应用测试、真实模型或业务验收**。实际命令与回执在实施时填入validation.md，不提前声称通过。

## 前置条件

使用mayuan且按共享工作区隔离；Python使用项目环境`/Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python`，前端使用兼容Node运行时。测试用临时目录、内存/隔离数据库；原PDF按真实SHA核验，保留用户稿。每个任务起始固定一个支持图片的主模型，不新设Qwen/4090部署。

## 分层执行

1. 固定反例：从原失败/误裁建立能失败的测试；模拟响应只验证协议，不能替代真实像素或模型。
2. 真实PDF：从正文/SI及必要上下文生成区域，检查首次整图完整图注、局部区域、300/600 DPI、坐标、位图限制；图/表/文字/公式分别验收。
3. 实际API：在独立隔离任务分别验证已配置GPT/Flash，每个任务内部模型不变；核对实际图像输入、工具调用编号、回执、发送尺寸和未在提示出现的图像事实。
4. 自动修正：注入缺图例/错裁剪/柱内部采样失败等明确问题，要求实际工具动作及新依据；不能只看最终数值是否“像对”。
5. 正式后处理：受影响字段重新科学提取/整理/核对及保存重读，检查值、单位、材料、压力、物相、μ*和原图来源。程序积分与结构展开各自验证。
6. 恢复与复用：临时错误按#224五次规则，已成功面板不重跑；清理测试缓存后按同一定位重建，不调用模型找位置；旧快照不读取新版；RAG权限反例独立验证。

## 推荐定向测试命令（实施后）

```bash
DATABASE_URL="sqlite:///:memory:" PYTHONDONTWRITEBYTECODE=1 "/Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python" -B -m pytest -q -p no:cacheprovider \
  "backend/tests/test_image_reading.py" \
  "backend/tests/test_pdf_review_tools.py" \
  "backend/tests/test_llm_request_paths.py" \
  "backend/tests/test_spectra.py" \
  "backend/tests/test_structure_reading.py"
```

上列包含未来拟新增测试路径，路径存在和测试实现须在任务T001核对；本次不执行这些命令，不把拟新增文件当现有覆盖。

科学共享路径实施后必须运行：

```bash
npm run test:field-contract --prefix "frontend"
npm run test:form-contract --prefix "frontend"
npm run test:form-contract:mutation --prefix "frontend"
```

## 记录与判定

记录原件SHA、源码/差异、模型及协议、图像摘要/尺寸/定位、提示/算法版本、复用与新请求、实际用量/耗时、失败/修正动作和层级结论。失败响应固定重放、真实新提取、保存重读、完整五阶段分别计数；未推送、未部署、未批准不宣称对应结果。

来源真实缺失保留无法确定；固定接口错误明确停止；技术故障不冒充论文未报告。验收不得以增超时、放宽断言、隐藏缺项或硬编码论文值通过。

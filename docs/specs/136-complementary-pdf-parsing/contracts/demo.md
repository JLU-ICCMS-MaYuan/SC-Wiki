# 独立 demo CLI 与报告契约

关联 [实施计划](../plan.md) 和 [数据模型](../data-model.md)。

## 输入与运行入口

`python -m scripts.complementary_pdf_demo.run --case <json> --output <directory> [--stage parse|extract|report|all] [--run-dir <existing-run>] [--marker-python <python>] [--timeout <seconds>]`。

默认 stage 为 all，创建唯一运行目录；后续 extract/report 通过 run-dir 读取同一来源版本，失败的模型尝试必须保留。parse 阶段可显式使用 `--resume-parsing`，校验成功产物哈希并归档旧失败后重跑，报告记录复用。默认 Python 为项目环境，Marker 独立环境路径由参数指定。模型使用既有默认配置，不向用户暴露产品解析器选择；stage 仅为开发实验的可恢复执行入口。

输入清单不含密钥和参考答案。禁止输出目录覆盖输入文件。输入路径、角色、摘要、依赖或参数错误非零退出；解析一路失败仍保存其他路和报告，但整体失败，不产生伪成功。

## 产物

`manifest.json`；`<engine>/<file_id>/{raw.json,ir.json,run.json,stdout.log,stderr.log}`；`complementary/<file_id>/{ir.json,routing.json}`；`extractions/<arm>/` 下保存请求、原始响应、表单、验证和失败尝试；`report.json` 与 `index.html`。具体引擎的额外图片/Markdown 作为原始产物保留。

报告四臂为 docling/mineru/marker/complementary；没有对应成功输出的臂标失败，不能把空列表当成功。模型信息记录 provider/model、温度、提示词哈希、预算和真实 usage（若有）；禁止保存 API Key、授权头或完整环境变量。

## 下游提取与来源

统一使用项目领域契约和表单定义；跨文档字段同时带 file_id 和各自 1 起始 PDF 页码。模型只能读取当前臂提供的来源；核对参考不进入 prompt。科学值不由汇总器重新生成；结构候选由独立来源提取并显示缺失项，未证实完整晶胞不声称已有可用结构。

定位失败、模型返回无效 JSON、预算超限和契约不通过均留存原始结果与错误。允许同一参数的有限重试；不能换模型、删问题字段或拼补 JSON 后冒充原始成功。

报告分别记录共享科学记录契约、已核实的表单枚举/参数表达约束和引句定位；不声称已在生产数据库的全部发布定义下验收。未通过的原始候选仍可按表单层级查看。`evaluate.py` 是独立的生成后评测入口，使用明确来源/摘要的参考清单，不属于模型输入。

## HTML 行为

离线打开可查看四路表单、来源及原始字段；可筛选差异、查看未覆盖项、添加核对状态/理由、导出和重新导入同一运行的核对 JSON。原文与模型文字安全转义；不执行其脚本或远程请求。失败、未知、未核对与不适用分别展示，统计明确给出总数和分母。图像支持查看原 PDF 区域与页；谱线数据由 #137 承接。

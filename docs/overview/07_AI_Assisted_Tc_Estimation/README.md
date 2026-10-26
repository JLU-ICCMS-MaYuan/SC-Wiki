# AI 辅助 Tc 估算

## 功能边界

主站 `/tc-predict` 按常压 BCS 超导体和高压氢化物提供多模型预测、原始训练数据下载及来源。支持结构输入、EPC 参数和原有 CONTCAR／电子 PDOS 方法；结果按固定高度横条展示，详情按需展开。

该能力由代码明确标记为实验页面，不代表经过科学验证的通用预测模型，也不会自动把结果写入主业务数据库。

## 小功能目录

| 小功能 | 职责 | 依赖 |
| --- | --- | --- |
| [CONTCAR/PDOS Tc 估算](contcar-pdos-tc-estimation.md) | 解析文件、计算耦合与返回估算结果 | pymatgen、NumPy |
| [本地主站多模型预测](model-lab-demo.md) | 两类分组、真实模型推理、原始数据下载及来源 | 主站 API、隔离 Python、BETE-NET／SISSO |

## 功能组成

```text
AI 辅助 Tc 估算
├── CONTCAR/PDOS Tc 估算
└── 本地主站多模型预测
```

## 关联关系

前端 `/tc-predict` 页面提交 CONTCAR 和多个 PDOS 文件，后端验证必要文件并计算结构及电子特征，最后返回 Tc 估算值。该流程与主材料检索和 RAG 数据相互独立。

主站通过原生 Vite 5173 → Go 8080 → FastAPI 8000 提供预测。BETE 在独立解释器子进程执行，不依赖 5189／8192 Demo 服务；原模型 Tc assessment model 在同页调用已有 API。当前验证目标为本地主站，没有执行阿里云发布，不写业务数据库。

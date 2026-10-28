# 实施计划

Issue：[ #172 ](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/172)，日期：2026-10-28；依据 [Spec](spec.md)。

## 摘要与技术上下文

Python 3.12／Pydantic 2 后台，React 19／TypeScript 5.6 前端；pytest、Vitest。正式数据协议仍为现有记录 JSON，不迁移数据库。目标为当前源码与本地隔离验证，不自动重跑业务任务。性能目标是不重复整篇工具解析及无关字段模型提取。

## 数据事实来源与组件职责

- `domain_extraction.normalize_extraction` 是新结构化候选的唯一标准化入口；在任何方法/原文条件检查前规范和验证条件扩展。
- `property_extensions.py` 增加只用于新提取的有界整理器：空字典/空值转空数组；本次精确的 electron_phonon/phonon_method 文本分组转现有键值记录；其他对象不猜测，不递归拍平；数组项必须是带有效 key 的对象，已知条件扩展必须带计算阶段，防止绕过原文检查。保持原输入及元数据。
- `condition_rules.py` 继续负责原文依据，不删除或绕过规则；整理不授予 supported/human_confirmed。
- `calculation_methods.py` 在共享提示词明确数组格式、声子方法名称及内部阶段保留。缓存提示词摘要自然使旧提取缓存不命中。
- `CalculationConditionFields`、`SchemaDrivenRecordForm` 与相关字段展示复用声子方法显示名称；用户显式 name_raw 保留，自动名称统一简化。计算归属内部键不迁移。
- 字段验证从已校验 PDF 来源的 IR/文字重新调当前任务模型，使用生产标准化、组装、草稿归一化及保存重读；对输入范围和未执行步骤留档。固定失败响应离线重放另行保留。

## 质量门

| 约束 | 满足方式 | 状态 |
|---|---|---|
| 用户已确认草案 | 当前“执行”，原话见 Spec | 通过 |
| mayuan、隔离并行改动 | 每次写入核对分支，显式路径暂存 | 执行中 |
| 不扩大重试 | 不修改 _read_chunk 的重试次数和捕获范围 | 设计通过 |
| 不补猜科学条件 | 保留原文过滤和 QE 正反例 | 待实测 |
| 远程文档 | 未推送时仅登记路径，不关闭 Issue | 待推送验证；不阻止已授权单项实现 |

## 产物与源码结构

本目录包含 spec、plan、research、data-model、contracts/extraction、quickstart、tasks、checklists/requirements、validation 和 assets。源码触点为 backend/ingest/{property_extensions,domain_extraction,calculation_methods}.py、前端相关字段名称展示、tests/01_decentralized_uploading/ 的字段回归及 scripts/ 的定向验证入口；规则写入 AGENTS.md，最终事实回写上传 Overview。

## 映射与执行顺序

| 需求／标准 | 设计与任务 | 验证 |
|---|---|---|
| FR-001/002，SC-001 | T002/004 名称与来源保留 | 真实表单编辑、保存重开 |
| FR-003/004，SC-002/003 | T002/003 新提取边界标准化 | 失败响应与格式反例 |
| FR-005，SC-004 | T002/003 原文规则不变 | QE 泛函正反例 |
| FR-006/007，SC-005 | T005/006 字段重跑与规则 | 真实模型、保存重读、验证报告 |

按 T001→T002→T003/T004→T005→T006→T007 串行推进。本次不委派子代理。

## 取舍

不取消科学检查、不全量吞异常、不通用递归拍平任意 JSON、不改变用户历史数据。少量显式兼容是为覆盖已确认真实失败；未识别结构仍失败。

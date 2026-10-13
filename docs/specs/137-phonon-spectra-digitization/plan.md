# 实施计划

**Issue**：[ #137](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/137)

**日期**：2026-10-13

**Spec**：[spec.md](spec.md)

## 摘要

实现配置驱动的半自动数字化：核验输入 → 提取原生图 → 线性轴标定 → 颜色掩膜及图例排除 → 按频率逐行/列读取轨迹 → 有界重建 → 独立物理诊断 → 离线 HTML 和 JSON/CSV。不引入三引擎或生产写入。

## 技术上下文

Python 3.12 / NumPy / Pillow / PyMuPDF；结构核验使用 ASE/spglib。来源为本机已上传 PDF；输出位于 Git 忽略的 demo/phonon-spectra/，代码、案例配置和测试位于 scripts/phonon_spectra_demo/。HTML 使用原生浏览器 SVG、Canvas 和下载接口，无外部服务。首例 984×1246 位图、两物相八条曲线；复用现有运行时，不设未经验证的性能承诺。

## 质量门

| 来源 | 要求 | 处理 |
|---|---|---|
| 用户后续指令 | 独立开始 #137 demo | 不等待 #136；不扩展到生产 |
| AGENTS.md | mayuan、只提交本次文件 | 每次写入核对分支，定向暂存 |
| Spec | 归一化和人工输入不伪装 | 明示条件候选、未核对、点状态 |
| Overview | 正式科学数据需原事务与审核 | 本轮不调用业务 API |
| 文档远程链接 | 未推送不宣称可访问 | 保留未完成，不自行推送 |

## 产物及职责

Spec 目录保存 spec、plan、research、data-model、quickstart、tasks、checklists、contracts 与 validation。scripts/phonon_spectra_demo/ 的 digitize.py 负责数学及提取，build_demo.py 负责 I/O 与产物，template.html 负责呈现，cases/h3s-2014.json 保存人工标定与参考。demo 产物可重建，不提交原论文全文。

## 需求到设计

| 来源 | 实现 | 验证 |
|---|---|---|
| FR-001/003，SC-001 | 哈希、图像定位、状态清单 | 原 PDF 与输出来源复核 |
| FR-002，SC-002/006 | 颜色掩膜、轴拟合、有界重建 | 合成图与原图叠加 |
| FR-004，SC-003 | 结构还原、总 DOS 统一比例 | 原胞计数、积分、阻止未核对采用 |
| FR-005，SC-004 | α²F 积分和误差诊断 | 已知函数与正文独立比较 |
| FR-006/007，SC-005 | 离线 HTML 与导出 | 浏览器、JSON/CSV 往返 |
| FR-008，SC-007 | 强色优先、暗色色差补读、图框平台延续 | 灰轴/虚线合成图、新旧观测逐点不变、真实八曲线连续性 |

## 阶段与复杂度

先固定来源与契约，再实现提取及测试，再生成实测和浏览器验收。只有案例标定包含 H3S 特定坐标，算法不读正文参考答案。原始/重建/归一化三层是防止推断被误当观测所必需；不增加服务、数据库或通用任务编排。

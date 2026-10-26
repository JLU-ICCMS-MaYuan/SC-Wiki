# 姜博文论文中的模型称呼核查

核查日期：2026-10-26。用户要求使用论文中的模型名称描述，并将原页面能力接入当前 Demo。

- 论文：Bowen Jiang 等，*Data-driven search for high-temperature superconductors in ternary hydrides under pressure*。
- 期刊与定位：Physical Review B **111**, 054505（2025），第 054505-6 页，II.C 节。
- [原始论文](https://doi.org/10.1103/PhysRevB.111.054505)；[出版方 PDF](https://journals.aps.org/prb/pdf/10.1103/PhysRevB.111.054505)。
- 核查方式：读取出版方 PDF 正文，并渲染、查看第六页，确认名称、公式与系数所在段落。

作者原文称呼为 **“Tc assessment model”**，用于笼状超氢化物的初步 Tc 评估。正文将电子 PDOS 与 H–H 距离组合成经验因子 **E_couple**，通过线性拟合估计 Tc；没有在此段另设一个专用缩写名称。

| 论文内容 | 当前实现核对 |
| --- | --- |
| 有效 H–H 距离上下限 0.98、1.28 | `COUPLING_RANGE = (0.98, 1.28)` |
| 斜率 16370.6，截距 24.7 | `SLOPE1 = 16370.6`、`SLOPE2 = 24.7` |
| Tc = A × E_couple + B | 当前接口返回 `predicted_tc`，其中 `f2_value` 对应现有实现的耦合描述量 |

因此目录显示名采用 **Tc assessment model**，说明采用“基于氢子晶格与电子 PDOS 的 Tc 评估”。`legacy` 只保留为内部稳定 ID，不出现在展示名称中。代码链接明确标为“本站实现”，不冒充作者原始开源软件。

本轮只核对来源、名称和上述公式参数，并复用当前接口，不重新拟合或改变算法。原始训练数据文件及再分发授权仍待核实，不能因为找到论文就声称数据已可下载。

# 谱线人工编辑 Demo 与联动调参

## 功能说明与边界

这是 #161 的独立本机交互 Demo，演示 α²F 与声子 DOS 的原图标定、点编辑和局部联动，尚未接入正式谱详情或 SC-Wiki 数据库。保存写入当前浏览器的 Demo 草稿，不调用模型重提取、不导出文件、不代表科学采纳。

正式谱集合、提取运行及审核流程见 [声子谱与提取质量](data-structure-and-form-mapping.md#声子谱与提取质量137)。本页的交互说明仅适用于独立 Demo。

## 当前编辑能力

- 从“02 · 原图与提取结果”的编辑按钮进入全屏工作区，默认允许 X/Y 两方向拖动，也可锁定为只改幅值。
- 加点、删点、框选、坐标输入、缩放和平移共用原图像素坐标；新点自动选中，右侧显示频率、幅值、像素 X/Y 和距当前零频线的距离。
- 描线顺序与数值表的频率排序分开，补点连接附近线段或端点；删除保留断口，旧局部回折可以显式修正并撤销。
- 当前标定轴、已有识别刻度与人工零频标记分别展示。α²F 图的累计 λ 刻度只作参考，不用作 α²F 幅值；PhDOS 缺少数字幅值刻度时使用相对像素并标明边界。
- 撤销、重做、恢复原始样本和本机保存相互区分；旧草稿读取不会自动覆盖原存储。

## 手动调整联动比例

唯一调参入口是 [dragInfluence.ts](../../specs/161-spectrum-manual-editor-demo/demo/src/dragInfluence.ts) 顶部的 `DRAG_INFLUENCE`。界面说明和实际拖动使用同一配置。

| 参数 | 含义 | 怎么调整 |
| --- | --- | --- |
| `coreNeighbors` | 按描线顺序，每侧明显跟随的邻点数 | 正整数；减小后主要影响区更局部 |
| `edgeWeight` | 主要影响区最外侧邻点的跟随比例 | 在 `(0, 1]` 内；增大使附近点跟随更强 |
| `decayLength` | 核心区外的指数衰减长度，单位为点数 | 必须大于 0；减小则衰减更快，增大则影响更远 |
| `minWeight` | 极小影响的截断比例 | 大于 0 且小于 `edgeWeight`；增大后更远的点更早停止移动 |

以距离选中点的描线序号差 `d` 计：核心区权重为 `1 − (1 − edgeWeight) × d / coreNeighbors`，外侧为 `edgeWeight × exp(−(d − coreNeighbors) / decayLength)`。选中点始终 100% 跟随；低于 `minWeight` 的权重不再参与。断口和其他分波不参与当前曲线的联动。

2026-10-26 核对的**用户本地调参记录**为 `coreNeighbors=2`、`edgeWeight=0.3`、`decayLength=1`、`minWeight=0.1`。它不是仓库通用默认值，实际运行以当前文件为准。这组值使第 1、2、3 个邻点分别约跟随 65%、30%、11.04%，第 4 个开始停止；两侧都有足够连续点时最多移动 7 个点（包含选中点）。

调整前先保存页面里未保存的选点，再修改代码、保存并刷新 Demo。参数只影响以后的拖动，不自动改动已经保存的坐标。错误参数或过大的影响范围会报错；权重表仅在加载配置时生成，拖动中复用，不逐帧重新计算指数。

## 保存后的零频位置检查

点击“保存调整”成功后返回详情，程序会按本次保存的数据自动检查零频位置。刷新或重新打开时从保存记录重新检查，不沿用可能已经过期的通过标记。

| 状态 | 含义与下一步 |
| --- | --- |
| 零频位置核对完成 | 已有显式原图零频位置记录，且当前曲线的已确认点仍在该零频线上 |
| 尚未确认原图零频位置 | 仅有识别或蓝色标定线；对照原图后可点击“确认蓝色零频线与原图一致”，也可重新在图上标记 |
| 已有零频点，等待人工确认 | 数据中已有位于零频线的点；点击“继续核对”选中它，再确认该点，无需删除重画 |
| 缺少位于零频线上的有效点 | 显示最近点的频率和像素距离；需对照原图调整或补选，程序不自动补造零点 |

PhDOS 分别检查所有已有分波，全部完成才显示整体完成。图上原有标线与零频补点操作可直接作为依据，不要求重复确认。移动、删除已确认零点或修改标定后，下一次保存会重新判定；只改其他点不会无故使零频确认失效。

“继续核对”打开对应曲线并选中候选点或最近点。确认现有蓝线和现有点只记录用户明确操作，不改变坐标；这些操作可撤销，点击保存后才写入本机草稿。未完成不妨碍保存有效草稿；保存失败则留在编辑器，不报告新的完成结果。

完成只表示零频位置与选点的一致性，不代表整谱已采纳、幅值刻度正确、全频域完整或积分可计算。位置比较只容忍 `1e-4` 源像素的舍入误差，不会把普通近零点直接改成零点。

## 运行与代码依据

从仓库根执行 `npm --prefix docs/specs/161-spectrum-manual-editor-demo/demo run dev`，默认访问 [本机 Demo](http://127.0.0.1:5187/)。运行与完整操作见 [使用说明](../../specs/161-spectrum-manual-editor-demo/quickstart.md)。

- [编辑核心](../../specs/161-spectrum-manual-editor-demo/demo/src/engine.ts)：像素映射、描线连接、联动与历史。
- [画布](../../specs/161-spectrum-manual-editor-demo/demo/src/SourceCanvas.tsx)、[页面与本机保存](../../specs/161-spectrum-manual-editor-demo/demo/src/App.tsx)。
- [调参测试](../../specs/161-spectrum-manual-editor-demo/demo/tests/dragInfluence.test.ts)、[浏览器验证](../../specs/161-spectrum-manual-editor-demo/demo/tests/browser.cjs)。
- [保存后零频检查](../../specs/161-spectrum-manual-editor-demo/demo/src/zeroCheck.ts)、[检查面板](../../specs/161-spectrum-manual-editor-demo/demo/src/ZeroFrequencyCheck.tsx)、[验收记录](../../specs/161-spectrum-manual-editor-demo/zero-review-validation.md)。
- [Issue #161](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/161)、[Spec](../../specs/161-spectrum-manual-editor-demo/spec.md)。

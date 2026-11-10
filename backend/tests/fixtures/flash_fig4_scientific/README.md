# Fig.4科学验收参照

pixel-reference.json来自本轮原PDF原始879×632位图。刻度值/标签和材料顺序由原图核对，程序采样基线连通柱，排除独立图例色块；没有用正文结果或其他模型答案反推坐标。数值容差固定为3个原始位图像素及刻度拟合残差，不采用模型自报精度扩大容差。PrH9两个Tc无可辨柱，不能填零。

old-flash-facts.json为此前6条未通过的真实候选，保留原数字/坐标，用于检出数值、柱归属和漏读；不是正确科学样本。参照只用于本篇测试，生产实现没有论文值或材料名单。

旧候选夹具只投影验收所需字段，数字/坐标/单位保持原值；完整原件仍在docs/specs/232-complete-pdf-regions/evidence/20261110-implementation/yh-LLM1-normalized-hints/ir.json，不以该投影冒充完整原响应。

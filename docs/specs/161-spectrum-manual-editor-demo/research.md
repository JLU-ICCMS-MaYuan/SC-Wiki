# 设计依据与取舍

- 正式详情入口在 frontend/src/pages/SpectrumDetailPage.tsx，图像面板在 SpectrumDetailView.tsx；本次只复刻隔离 Demo。
- SpectrumFigure.tsx 已使用 SVG 与来源像素保持比例。继续使用 SVG，便于精确选点和共享变换；不引入大型绘图库。
- PropertySpectrumPoint 的 frequency_pixel/amplitude_pixel 提供来源坐标；既有 calibration PUT 会重提取，不能拿来实现本次手动点保存。因此 Demo 不调用该接口。
- #137 首版明确不提供逐点编辑；#161 是新增能力，不改变 #137、#154、#155 的旧验收。
- α²F 既有样本 amplitude 标尺可能来自 λ；恢复像素只使用 snapshot.amplitude_pixel，绝不据此宣称 α²F 幅值已标定。Demo 初始幅值采用相对像素。
- PhDOS 使用同一真实来源图的固定示例点，构造图例误识别与零频缺失练习；并记录取点算法和注入位置，不能当作真实重新提取验收。
- 采用平滑紧支撑权重而非全局样条：影响范围清楚、保留尖峰、不改范围外点。
- 默认联动只改幅值，数值输入用于精确修改当前单点；二维拖动单独开启。
- 删除显式断段；不自动跨缺口插值。新增落在片段内部时按频率插入，否则新建片段。
- 本机存储仅用于 Demo 草稿；未来数据库契约另行设计。保留来源、原始结果、改后点和编辑记录，为后续设计提供实际样例。

# 数字化 demo 接口

`python scripts/phonon_spectra_demo/build_demo.py --config <JSON> --pdf <正文> --supplement <补充> --output <目录>`

输入清单必须指定原文件哈希、图所在页/区域、预期图片尺寸、线性坐标标定点、曲线颜色及图例排除区域。原 PDF 路径由命令传入，不把本机绝对路径写入数据导出。错误哈希、错误尺寸、退化坐标、非线性坐标、不存在图像、源文件位于输出目录内等须明确拒绝。

当前输入标定值须表示普通频率 THz；其他频率/波数单位需要先明确转换后再提供配置，不自动猜测。首版每个状态要求至少一条 DOS 投影、一条 α²F 和一条累计 λ，正文参考 λ/ωlog 由独立案例参考提供；不宣称已支持所有图表组合。JSON 同时保存完整标定清单；CSV 将原图幅值单位与归一化单位分列，并记录原胞原子数、模式数目标和未批准状态。

输出：index.html（离线图表与下载）、spectra.json、points.csv、figure.png、report.json。离线 HTML 不请求业务 API，不加载外部脚本；导出与页面使用同一数据源。重复运行只重建本目录这些指定产物，不递归删除目录。未知曲线缺口保留 null，诊断失败不伪装为完整数据。

H/S 投影权重和共尺度未证实时不生成 accepted 归一化。即使展示 3N 条件预览，training_ready 仍为 false。review_status 不由下载行为改变。

断点修复版本以 provenance.algorithm_version=chromatic_recovery_v2 标识。补读到的真实暗色点仍为 observed，同时 detection_mode=chromatic_recovery；图框平台端点使用 edge_continuation，原始观测为空。图表、JSON 和 CSV 使用同一完整序列，不允许仅在 SVG 上跳过 null 连线。无依据长缺口仍保留 null。

精度核验版本为 precision_audit_v3，兼容原始曲线数据。可选 zero_reference_band_thz 必须由原图核对，并通过至少五个带色行、窄带和近零轴检查；不满足则 candidate.status=unavailable，不自动选择其他频段。新增“α²F（零基线候选）”查看项与 CSV 候选列，原始曲线入口继续有效。累计谱核验保留单调修正幅度和遗漏低频范围，不写回原曲线；所有候选仍待科学复核。

scientific_audit_v4 使用修正的分段线性精确积分。可选 --scientific-review 加载已完成审阅 JSON，必须匹配当前数据指纹，且明确保留定量限制。页面展示复核已完成的用途分级，CSV 同步审阅状态，不把它转为 training_ready=true。新数据不会自动继承旧审阅。

# 开源常规超导 AI 模型调研

核查日期：2026-10-26（Asia/Shanghai）。对应 [Issue #162](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/162) 与 [Spec 草稿](spec.md)。

## 结论

优先进入制品复现核查的是 **BETE-NET** 和 **JARVIS/ALIGNN 超导模型**。前者提供不同输入层次的等变图网络集成，后者提供直接 Tc 与 α²F 两条结构预测路径。它们有明确的代码许可、公开训练数据来源和发布的权重入口，但本次没有完成真实推理，不能写成“已可部署”。

若希望增加独立方法，**Xie 等人的 SISSO 符号回归**值得作为“已有电子–声子参数 → Tc”的轻量候选。其中 **2022 年公式及开放训练表**是高压组值得优先复现的方向，论文单独验证了氢化物；它不替代“结构 → 电子–声子参数”的模型。较新的 81 样本 SISSO 工作也开放代码和数据，但适用域、输入量及完整系数需要继续核定。

**BEE-NET（2026）不是 BETE-NET（2024 预印本／2025 正式论文）的别名。** BEE-NET 学术上很有价值，当前公开仓库的许可和完整数据／权重下载仍有缺口，先不纳入严格条件已通过的名单。

用户已选择“两类分组提供”。常压组建议核验 BETE-NET-CSO、ALIGNN-Tc、ALIGNN-α²F，这是两个模型家族、三个推理路径；CPD／FPD 与 SISSO 是有额外输入时的备选。高压组保留原经验估算，新增模型按压力及高频谱覆盖另行筛选。具体名单尚未被用户选定，不能将常压推荐原样搬到高压组。

## 核查标准与证据等级

“常规”指电子–声子机制，并不等于“常压”，也不等于数据集删除铜氧化物和铁基后剩下的所有样本。

| 维度 | 必须核查的事实 |
| --- | --- |
| 模型开放 | 官方代码、明确许可、可用权重或可执行训练路线；源码可见不自动等于开源授权 |
| 数据开放 | 实际用于训练的输入、标签、处理规则、划分及许可；不能仅指向一个名称相同的大数据库 |
| 物理适用性 | 配对机制、结构／成分／谱输入、压力、维度、温度区间、μ*、标签由实验还是理论产生 |
| 工程可用性 | 下载内容、依赖版本、推理入口、制品大小、运行资源、错误处理及复现结果 |
| 比较有效性 | 相同材料状态、相容单位和目标定义；区别数据域、额外输入与测试集重叠 |

本轮证据以论文原文、作者仓库、GitHub 文件树、DataCite／Materials Cloud／UCI 官方数据记录为主。广泛检索并不保证穷尽全部模型，也没有把二手榜单作为通过依据。

证据记录区分：①发布方声明；②直接读取源码／元数据／小文件；③完整下载并校验；④真实推理；⑤本站独立性能评估。本次主要完成①②，未完成④⑤。大制品下载超时与 Figshare 空响应详见 [核验记录](validation.md)。

## 候选总表

| 候选 | 输入 → 输出 | 代码及数据 | 权重／训练情况 | 本轮判断 |
| --- | --- | --- | --- | --- |
| BETE-NET-CSO | 晶体结构 → α²F，再得到 λ、ωlog、ω₂、Tc | Apache-2.0；同仓库数据库、结构和索引 | 100 个权重，约 1.97 GB；训练和预测 notebook | 优先复现；数据版本／索引对应需核实 |
| BETE-NET-CPD | 结构＋粗网格逐原子投影声子 DOS → 同上 | 同一开放仓库 | 100 个权重，约 1.97 GB | 有所需声子输入时考虑 |
| BETE-NET-FPD | 结构＋细网格逐原子投影声子 DOS → 同上 | 同上 | 100 个权重，约 1.97 GB | 输入成本更高，非首批默认 |
| ALIGNN-Tc | 晶体结构 → Tc | NIST 使用条款；JARVIS-SuperconDB 为 CC BY 4.0 | 官方注册 `jv_supercon_tc_alignn` 权重入口 | 优先复现；下载、权重条款及数据版本待核实 |
| ALIGNN-α²F | 晶体结构 → 100 维谱，再积分计算参数与 Tc | 同上 | `jv_supercon_a2F_alignn` | 适合与直接 Tc 对照；同模型家族 |
| Xie／SISSO（2019） | 已有电子–声子参数 → Tc 解析表达式 | Apache-2.0；AllenDynes 数据和模型系数同仓库公开 | 无神经网络权重；训练输入、候选表达式及系数公开 | 轻量独立方法候选，需核定论文最终表达式 |
| Xie／SISSO（2022） | λ、ωlog、ω₂、μ* → Tc 解析表达式 | 工作流代码 Apache-2.0；Materials Cloud 训练表和回归日志亦为 Apache-2.0 | 论文最终公式公开；归档含两轮 SISSO 输入输出 | 高压组优先复现的参数模型；不等于结构直推 |
| 可解释 SISSO（81 样本） | λ、ωlog、成分／密度等 → 实验 Tc 拟合 | MIT；`1_Dataset/data.csv` 实际可读取 | SISSO 原始输出、交叉验证和分析 notebook | 研究备选，不能当作只需结构的模型 |
| BEE-NET（2026） | 结构或结构＋粗声子 DOS → α²F／Tc | 代码可见但未找到明确仓库许可；原始数据 CC BY 4.0 | README 声称有完整数据和集成，但核心文件不在 Git、未查到 Release 下载 | 暂缓，补许可和实际制品入口 |
| Hamidieh XGBoost | 化学式派生 81 特征 → Tc | GPL-3.0；UCI 数据 CC BY 4.0 | `tc.RData`、R 训练／推理脚本 | 开放性较好，但混合机制；只能作为另标的通用基线 |
| DeeperBand／BNAS | 电子能带／VASP 输出 → Tc | 软件 MIT；README 对内容声明 CC BY 4.0 | 提供模型／训练集下载命令，未验证下载制品 | 补充候选，未证实常规专用及数据完整性 |
| SODNet（NeurIPS 2024） | 有序／无序晶体结构 → Tc | 未发现明确仓库许可证；含 ICSD 来源结构 | 有数据及训练／推理脚本，未验证可用预训练制品 | 暂缓；源码公开和 ICSD 派生文件出现不足以通过许可门 |
| S2SNet（IJCAI 2022） | 晶体结构，预训练后超导判别等 | 未发现明确仓库许可证；依赖 SuperCon＋Materials Project | Google Drive 权重入口、部分数据文件 | 暂缓；完整预训练数据、许可和目标语义需核查 |
| Konno 周期表深度学习（2021） | 化学式 → 超导筛选／Tc | 代码可见；作者明确不提供 SuperCon 核心训练数据 | 提供处理与模型代码 | 不满足本轮“实际训练数据开放”的核查要求 |
| GuidedMatDiffusion | 条件 Tc → 生成晶体结构 | 公开实现及 Hugging Face 模型／数据入口 | 本轮未深入核验许可和制品 | 任务不同，不能直接作为 Tc 回归对比模型 |

## BETE-NET：最值得优先复现的独立模型家族

- [正式论文](https://www.nature.com/articles/s41524-024-01475-4)：2025-01-09 发布；[2024 预印本](https://arxiv.org/abs/2401.16611)。
- [官方仓库](https://github.com/henniggroup/BETE-NET)，核查提交 `56bc783908a60e8a15e31b60018e6f3c3e48f593`。
- [Apache-2.0 许可证](https://github.com/henniggroup/BETE-NET/blob/56bc783908a60e8a15e31b60018e6f3c3e48f593/LICENSE)。仓库统一许可，未见数据单独例外声明；后续制品归档时保留声明。
- [训练数据](https://github.com/henniggroup/BETE-NET/blob/56bc783908a60e8a15e31b60018e6f3c3e48f593/database.json)、[结构](https://github.com/henniggroup/BETE-NET/tree/56bc783908a60e8a15e31b60018e6f3c3e48f593/structures)、[划分](https://github.com/henniggroup/BETE-NET/tree/56bc783908a60e8a15e31b60018e6f3c3e48f593/indices)。
- [CSO 预测示例](https://github.com/henniggroup/BETE-NET/blob/56bc783908a60e8a15e31b60018e6f3c3e48f593/notebooks/Pred_CSO.ipynb)、[CPD 预测示例](https://github.com/henniggroup/BETE-NET/blob/56bc783908a60e8a15e31b60018e6f3c3e48f593/notebooks/Pred_CPD.ipynb)。

论文报告 818 个动力学稳定材料，80%／20% 划分，100 个 bootstrap 网络集成；结构模型报告 Tc MAE 2.5 K，引入声子信息后报告 2.1 K。这是原论文数据域内的结果，不能换算成 SC-Wiki 高压氢化物精度，也不能直接与其他论文 MAE 排名。

源码确认 CSO 关闭电子和声子 DOS 嵌入；CPD 开启声子 DOS 嵌入、关闭电子 DOS。CPD 使用 `Ph_2x2x2_interpolated_Site_Proj_DOS`，FPD 使用细网格逐原子投影。这里的声子 DOS 与网站 `PDOS_H.dat` 的电子 PDOS 含义不同，材料总声子 DOS 也不等价。

谱预处理网格是 `np.arange(0.25, 101, 2)`，共 51 点，单位 meV；高压氢化物可能有高于该范围的振动，不能把截断谱的积分当成完整谱。预测 notebook 使用 μ*=0.09 的 Tc 公式，并将 meV 的频率量转换为 K；应复现实际代码约定，不擅自换成另一种 Allen–Dynes 修正公式后继续引用原模型误差。

依赖包括 Python 3.9、PyTorch 1.10、e3nn 0.4.2、PyTorch Geometric 2.0.2 和编译扩展。代码有 CPU／CUDA 分支，但本轮没有测延迟、内存或 GPU 需求。每变体权重约 1.97 GB 是文件树大小相加，**不是运行显存或内存**。完整集成与单模型或缩减集成不能共享未经复验的性能声称。

发现的复现缺口：

1. 当前文件树为 806 个 CIF；完整训练索引 651 行、测试索引 173 行。直接把索引值作为 CIF 文件名时，训练有 15 个、测试有 3 个找不到对应路径。
2. notebook 使用 `read_json` 后 `dropna`，索引可能涉及版本、清洗或标签含义。尚未完整读取数据库证明正确映射，因此这里只记录差异，**不宣称已证明数据泄漏或整个模型损坏**。
3. `database.json` 为 89,104,840 字节，单 CSO 权重为 19,684,470 字节（GitHub 文件树元数据）；本次整文件下载超时，未完成哈希校验或权重加载。
4. 新样本推理需拆出不依赖真实目标标签的输入构图；原 notebook 面向带标签评估集，不能原样当成网站接口。

## JARVIS／ALIGNN：直接 Tc 与谱预测两条路径

- [论文](https://www.nature.com/articles/s41524-022-00933-1)。
- [NIST 官方仓库](https://github.com/usnistgov/alignn)，核查提交 `f2366daa3413d28a825b46e34d001b5549b05a40`。
- [使用条款](https://github.com/usnistgov/alignn/blob/f2366daa3413d28a825b46e34d001b5549b05a40/LICENSE.rst)明确许可使用、复制、修改、派生和分发并保留声明。GitHub 标为 `NOASSERTION` 不代表没有许可；不能误标为 MIT。
- [官方预训练注册表](https://github.com/usnistgov/alignn/blob/f2366daa3413d28a825b46e34d001b5549b05a40/alignn/pretrained.py)。
- [JARVIS-SuperconDB](https://doi.org/10.6084/m9.figshare.21370572)，[DataCite 许可元数据](https://api.datacite.org/dois/10.6084/m9.figshare.21370572)确认为 CC BY 4.0；这是数据记录许可，不是借用论文许可。

| 路径 | 官方名称 | 权重入口 | 输出 |
| --- | --- | --- | --- |
| 直接 Tc | `jv_supercon_tc_alignn` | [Figshare 38789199](https://figshare.com/ndownloader/files/38789199) | 1 维 Tc |
| 谱预测 | `jv_supercon_a2F_alignn` | [Figshare 38801886](https://figshare.com/ndownloader/files/38801886) | 100 维 α²F |

论文的机器学习使用 626 个动力学稳定样本，测试集为 5%；直接 Tc MAE 1.84 K，谱预测后计算 Tc 为 1.39 K。μ*=0.09，谱范围描述为 0–100 meV、1 meV 间隔。最终网格端点与零频处理必须从制品配置复核，不能仅凭文字猜测 100／101 个点。

JARVIS 数据加载器 `supercon_3d` 指向 1058 条记录的 `jarvis_epc_data_figshare_1058.json`，`supercon_2d` 是另一组 161 条记录。**公开库总数不等于原模型训练数；二维库也不能自动当作三维权重训练集。** 需要锁定原训练筛选、标签及切分，不能只下载最新库即宣布原论文可复现。

官方注册表还提供电子 DOS 和 Debye 温度模型；它们是筛选辅助量，不单独算新增 Tc 模型。ALIGNN 框架本身也不等于所有其支持的材料性质都可预测超导。

本次 Figshare API 返回 403，权重直链返回 HTTP 202 且正文 0 字节。DataCite 和官方源码可核查公开声明与许可，但下载未成功。下一阶段须核定实际权重文件、权重对应许可、配置及依赖；不把空响应计作下载成功。

另外检索到 `atomgptlab/alignn` 的后续维护版本，但本次不以新版实现直接替换上述旧权重运行代码。锁定兼容版本后再考虑升级。

## SISSO：输入条件不同的轻量对照

### Xie 等人 2019 年的符号回归

[官方工具与数据](https://github.com/henniggroup/symbolic-regression-utilities)，提交 `11cf1f31888afe3a29140557dc7b3871102b8204`，Apache-2.0。

README 明确关联 *Functional Form of the Superconducting Critical Temperature from Machine Learning*（Phys. Rev. B，2019）。[AllenDynes 数据目录](https://github.com/henniggroup/symbolic-regression-utilities/tree/11cf1f31888afe3a29140557dc7b3871102b8204/datasets/AllenDynes)提供 `data.csv`、`train.dat`、`SISSO.in`、候选表达式和系数。

数据列为 `material,t_c,w,l,m`，可读取 Ta、Sn、Pb、Nb、MgB₂ 等记录。这条路线对已有电子–声子参数产生 Tc 表达式，不需要大 GPU；正式接入前仍须将最终论文表达式与系数、输入单位、训练／测试选择逐项对应，不能从成千上万个候选中任挑一个并声称是作者最终模型。

### 81 个常规超导体的可解释模型

[官方仓库](https://github.com/HerzainR/Superconductivity-through-interpretable-ML)，提交 `84a63c80416e50686a2914e6fcd1636aa44d5f85`，MIT。

[实际数据](https://github.com/HerzainR/Superconductivity-through-interpretable-ML/blob/84a63c80416e50686a2914e6fcd1636aa44d5f85/1_Dataset/data.csv)实读为 81 行材料、45 列；标签是实验 Tc，含 λ、ωlog、密度及元素统计描述符，最大值为 38.4 K。[分析 notebook](https://github.com/HerzainR/Superconductivity-through-interpretable-ML/blob/84a63c80416e50686a2914e6fcd1636aa44d5f85/3_Data_analysis/superconductivity_SISSO.ipynb)说明均值 4.30 K、最大值 MgB₂ 约 38 K；最优超参数的留一法 MAE 约 2.913 K。

它需要 λ 等并非从简单上传结构即可获得的量。表达式中含密度分母，因此还需明确奇点附近的失败边界。数据来自 SuperCon／3DSC 映射和电子–声子参数，仓库 MIT 不能自动替代所有上游数据条款；后续需归档来源许可与最终模型系数。该工作未被本轮认定为高压氢化物模型。

## 高压组补充：Xie 2022 年公式与专用候选

用户选择两类分组后，补查了高压专用仓库和论文，不能把低温模型的物理条件直接迁移。

### Xie 2022：公开训练表，氢化物作为外推检验

- [正式论文](https://www.nature.com/articles/s41524-021-00666-7)，实际发表于 2022-01-25，不能仅按 DOI 中的 2021 判断发表年份。
- [Materials Cloud 数据归档](https://archive.materialscloud.org/records/skdzy-kyx54)，DOI 为 [10.24435/materialscloud:68-6p](https://doi.org/10.24435/materialscloud:68-6p)。
- [数据元信息](https://archive.materialscloud.org/api/records/skdzy-kyx54)明确记录文件适用 Apache-2.0；代码工作流指向前述 Apache-2.0 的 `henniggroup/symbolic-regression-utilities`。
- `data_tables.zip`：429059 字节，发布方 MD5 `86c68504d1780b6fc7eaccbd4116706c`。
- `sisso_runs.zip`：7810599 字节，发布方 MD5 `80c0ecb90d72b6dbb31dbeb82c10e0ab`。

归档说明明确包含实际模型输入、修正因子、Tc 标签／预测和两轮 SISSO 输入输出。论文使用人工构造谱及实材料派生参数，报告生成 2819 个多峰人工谱，并单独考察 13 个氢化物；正文明确氢化物未进入训练，用于外推验证。它是对已有 EPC 参数的学习公式，不是从结构自动预测 EPC 的网络。

输入为 λ、ωlog、ω₂、μ*，输出按论文式（6）—（8）由 McMillan 项及两个学习修正因子得到 Tc。应沿用具体公式、单位和定义，不能混同 2019 年版本，也不能将两个修正因子拆成两个独立模型。

论文一处写原始数据可按请求提供，而 Data availability 和归档明确公开的是**训练所需描述符表、Tc 与回归日志**。因此可核查“参数级模型训练数据已发布”，不能扩张为“所有原始 DFT／α²F 文件均已完整开放”。本次归档 API 和许可成功读取，但两个 ZIP 内容请求均出现 curl 56，未实读表内划分或复现公式数值；上线前需校验完整包与训练／测试映射。

这一路线适合高压组中已经有 α²F 或 λ、ωlog、ω₂ 的用户。若用户只有结构＋电子 PDOS，就不能假装这些额外参数已经存在。氢化物外推实验有针对性，但 13 个材料并不证明所有压力和非谐体系都适用。

### 高压结构／DOS 候选当前缺口

| 候选 | 可读内容 | 未通过项 |
| --- | --- | --- |
| [Hydride-Tc-Predictor](https://github.com/chen121760/Hydride-Tc-Predictor) | 2026 年论文关联、`vasprun.xml` 解析及符号公式 | 未见代码许可或实际训练数据 |
| [Ca–Mg–H 符号预测器](https://github.com/slenderrlrl/Details-of-the-predictor) | 模型表达式及脚本；README 声称使用 h、M、P、μ* | 默认分支只有三文件、无许可／训练数据；README 引用的 `model.py` 与实际脚本名不同，h 的定义仍是占位说明；Zenodo 归档尚未核查，不据仓库缺口断言所有发布渠道均无数据 |
| [pred_hydrides_tc_by_ML](https://github.com/takuyanin/pred_hydrides_tc_by_ML) | `main.py` 及若干 CSV | 无明确许可，README 只有标题，训练数据来源、单位和论文对应未说明 |

本轮尚未核实一个同时满足全部条件、可直接用结构或现有电子 PDOS 替代 EPC 参数、且已证明适用于高压组的新增模型。保留缺口比把通用 SuperCon 或常压模型改名为高压模型更符合用户条件。

## BEE-NET：论文很新，当前发布缺口须明确

- [2026 年论文](https://www.nature.com/articles/s41524-026-01964-8)。
- [官方仓库](https://github.com/henniggroup/BEE-NET)，提交 `f21c260a9117830f2d74f2c5ac844ab671c0c606`。
- [原始数据](https://archive.materialscloud.org/records/3kbt5-r3n56)与[机器可读记录](https://archive.materialscloud.org/api/records/3kbt5-r3n56)：CC BY 4.0，约 7000 个电子–声子计算；压缩原始归档总计约 51.6 GB。

作者 README 报告实际使用 5241 条，测试 1049 条、训练池 4192 条；CSO／CPD 各 100 个模型；报告 Tc MAE 1.20／0.87 K。论文也报告筛选及实验验证，但这些事实不能代替本站对新样本的性能验证。

当前仓库有结构与索引，README 明确写 `database.json` 和 `models/` 不在 Git。默认分支文件树未找到明确 LICENSE、核心数据库或权重，Release 列表为空，README 未给相应直接下载入口。原始归档存在并不证明处理后 5241 条训练数据和权重已可取得。

尤其不能把 BETE-NET 的 Apache-2.0 自动套到 BEE-NET，也不能把论文的开放访问许可套到未单独授权的代码。结论为“有潜力、开放条件待补齐”，不是“作者一定不愿开源”。

## 为什么其他常见候选不放进首批专用模型

### Hamidieh XGBoost：开放，但不是常规专用

[作者代码](https://github.com/khamidieh/predict_tc)采用 GPL-3.0，含约 20.6 MB 的 `tc.RData` 和 R 训练脚本；README 明确数据、辅助函数和预测用法。依赖 R、XGBoost、CHNOSZ。[UCI 数据](https://archive.ics.uci.edu/dataset/464/superconductivty+data)有 21263 行、81 特征，CC BY 4.0。

材料覆盖混合机制；纯成分不能区分同组成的不同结构和压力状态。可考虑在单独标注的“通用成分基线”中使用，但不能据此宣称新增常规超导专用模型；本轮没有实际加载 R 制品。

### DeeperBand：有开放声明，补核输入与训练域

[代码](https://github.com/ljcj007/DeeperBand)、[论文](https://arxiv.org/abs/2409.07721)。README 声明软件 MIT、内容 CC BY 4.0，提供 `deeperband download --models` 和 `--training`。还依赖能带计算及标准化；不能把任意 `vasprun.xml` 当成已满足原模型输入。

本轮核实 README 和论文摘要，没有下载训练集或权重，也没有证实专用于电子–声子机制。作为补充方向保存，不进入严格门已通过名单。

### SODNet／S2SNet

[SODNet](https://github.com/pincher-chen/SODNet)的数据说明：SuperCon 清洗得 11949 个超导材料，与 208425 个 ICSD 结构匹配并补入文献富氢结构，形成 1578 条结构与 Tc 配对。数据范围并非单一机制，默认分支未见许可证。ICSD 来源必须核验再分发权利。

[S2SNet](https://github.com/zjuKeLiu/S2SNet) README 描述 SuperCon／Materials Project 配对和全 Materials Project 预训练，指标包括分类准确率／AUC。不能把分类指标当作 Tc 回归误差；部分 NPY／CSV 和 Drive 链接不能单独证明完整训练数据及其许可。

### Konno 模型

[官方仓库](https://github.com/tomo835g/Deep-Learning-to-find-Superconductors) README 明确说明因 NIMS 限制不提供超导核心数据，只提供从 SuperCon 预处理的代码。不能用另一个公开 SuperCon CSV 冒充作者实际训练集。故不满足本轮严格条件。

### 其他研究方向

- [Hydride-Tc-Predictor](https://github.com/chen121760/Hydride-Tc-Predictor)：2026 年高压氢化物符号回归工具，输入 `vasprun.xml`，输出含压力和 DOS 描述符的 Tc；代码仓库仅四个条目，未见明确许可和训练数据。物理方向贴合，但当前不合格，不能因输入类似现有功能就接入。
- [GuidedMatDiffusion](https://github.com/paprakash/GuidedMatDiffusion)：有模型和训练集入口，但任务是按目标属性生成结构；不直接占用 Tc 预测器名额。
- [Materials Cloud 常规超导归档](https://archive.materialscloud.org/records/3kbt5-r3n56)：适合未来独立训练与基准构建，数据集本身不算另一个可部署模型。
- [HTSC-2025](https://github.com/xqh19970407/HTSC-2025)：140 条常压高 Tc 候选的评测数据方向，不是预训练预测器；理论预测标签不能当实验 Tc，使用前仍需核验许可与训练集重叠。
- 通用 CGCNN、MEGNet、M3GNet、CHGNet、MatterSim 等框架或材料势，若没有明确超导任务、权重和相应开放训练集，不列作已经可部署的超导模型；McMillan／Allen–Dynes 公式和 Eliashberg 求解器也不伪装成 AI 模型。

## SC-Wiki 接入建议及比较边界

以下是供后续 Plan 采用或调整的技术建议，尚未实施，也不把建议写成当前功能事实。

1. **保留现有路径**：当前输入 CONTCAR＋电子 PDOS、固定参数与返回字段完整保留；如展示来源，诚实标注当前校准数据尚未核实。
2. **模型元数据与执行分开**：统一展示名称、家族、版本、许可、训练域、输入要求；运行时只调用已完成核验的模型。
3. **隔离依赖**：BETE 的旧 PyTorch／e3nn／PyG 与 ALIGNN／DGL 不直接挤入网站主环境；实现阶段按部署目标选择隔离进程或服务，调研阶段不预设必须 Docker。
4. **按输入能力分组**：结构模型一组，逐原子投影声子 DOS 增强模型一组，已有 λ／ωlog 的参数模型一组。额外信息量必须明示。
5. **数据与权重可追溯**：锁提交、哈希、许可证和训练划分；研究报告不携带大型外部数据副本进业务 Git。
6. **科学条件保持独立**：固定 Tc 权重不能通过改一个 μ* 文本框改变模型含义；只有谱后处理或参数公式支持的条件才可调整。
7. **公平验证**：先复现原项目样本，再验证不含在各自训练集中的共同材料；按化学体系、结构、压力分组排查泄漏。不同模型输出分歧不是自动不确定度。
8. **高压氢化物单独处理**：核对高频谱、非谐效应、结构压力及训练覆盖。不把只在低 Tc 数据集获得的小 MAE 当作数百 K 氢化物可靠性。

部署验收分为“来源和许可核查”“真实推理可用”“独立性能评估”“指定环境上线”四类证据。本轮完成的是调研与需求草稿，其他类别保持未完成。

## 决策记录

| 建议 | 理由 | 备选与条件 |
| --- | --- | --- |
| 优先核验 BETE-NET-CSO | 独立架构、结构输入、训练代码／数据／权重公开 | 索引与制品核验失败时暂缓，不用未经说明的缩减版替代 |
| 同时核验 ALIGNN-Tc／α²F | 官方入口明确，可比较直接回归与谱后处理 | Figshare 获取和原训练筛选未解决前不宣称可用 |
| CPD／FPD 放在额外输入分组 | 可能提高域内预测，但需逐原子声子 DOS | 没有该输入时不触发、不补造，也不主动重算声子 |
| SISSO 作为独立轻量方法备选 | 开放解析表达式及数据，便于解释 | 需要已知 EPC 参数、单位和完整系数 |
| 高压组优先复现 Xie 2022 参数模型 | 训练表和日志许可明确，论文有独立氢化物检验 | 先解决归档下载并复现公式；不替代结构／PDOS 直接预测需求 |
| 暂缓 BEE-NET 与高压专用新工具 | 当前许可或发布制品不完整 | 补齐公开证据后重审，不能借另一仓库许可 |

未决事项在 GitHub Issue 和 Spec 中协作；本报告不作为独立待办或 Issue 状态副本。

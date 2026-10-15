# 验收步骤：表格超导参数与共用条件

**状态**：后续实施用验证指南。下列新增测试和记录文件尚未创建，命令不是本轮已运行的结果。

## 前置条件与执行边界

1. 已有明确的代码实施授权，读取已确认 Spec、Plan、Research、数据模型、契约和 Tasks。分支为 `mayuan`，先记录工作树与已提交制品来源，保留其他任务改动。
2. 使用项目现有 `sc-wiki` Python 3.12 环境、前端依赖与任务 LLM 配置；不输出密钥，不更换默认模型或解析引擎。
3. 准备 La–Sc–H 主文与 SI 原 PDF，核对 DOI、文件 hash、有效角色和页码。新建隔离验收任务，不覆盖截图对应的历史人工草稿。
4. MySQL 验证使用明确的独立测试 schema 和测试账号；新测试仅在设置 `SCWIKI_ISSUE139_TEST_DATABASE_URL` 时启用，测试自身须检查 MySQL 方言和测试库标记，拒绝默认业务库。未准备时记录未执行，不使用当前业务库代替。
5. 浏览器与真实解析需要当前本地服务可用。只在验收环境新建记录，避免改写现有论文；数据库迁移和部署不在本需求内。

## 独立科学预期

下表来自当前已有主文解析文本，仅是待原 PDF 核对的初始预期；T001 完成人工核对并记入 `tests/fixtures/issue139/expected-table.json` 后才可作为验收基准，不从模型输出反向生成答案。

| 近似 | 压力 GPa | λ | ωlog K | Tc K | 表注 μ* 顺序 |
| --- | ---: | ---: | ---: | --- | --- |
| 谐 | 290 | 3.56 | 865 | 311–339 | 0.16→0.1 |
| 谐 | 300 | 3.34 | 968 | 303–329 | 0.16→0.1 |
| 谐 | 350 | 2.20 | 1294 | 266–294 | 0.16→0.1 |
| 非谐 | 150 | 3.94 | 745 | 281–311 | 0.16→0.1 |
| 非谐 | 167 | 3.73 | 794 | 285–316 | 0.16→0.1 |
| 非谐 | 200 | 3.21 | 965 | 291–325 | 0.16→0.1 |
| 非谐 | 250 | 2.89 | 1075 | 296–331 | 0.16→0.1 |
| 非谐 | 300 | 2.61 | 1165 | 293–330 | 0.16→0.1 |

Methods 原文核验重点：结构优化／电子结构的 VASP、PBE、850 eV 及 Γ 中心网格分辨率；声子／EPC 的 QE、DFPT、90 Ry／720 Ry、24×24×24 k 网格与 6×6×6 q 网格；SSCHA 的超胞、80 Ry、3×3×3 k 网格、2×2×2 动力学矩阵及插值后的 6×6×6 网格。每项记录具体适用阶段与范围，不把该清单无条件套到每条 Tc。未读到展宽时留空。AIMD 的 Γ 采样不能填为 EPC 的 k 网格。

## 分层自动回归

从仓库根目录执行。新增测试必须先实现，并验证它们确实收集到用例；文件不存在或全部跳过不能算通过。

```bash
conda run -n sc-wiki python -m pytest   "tests/01_decentralized_uploading/test_issue139_scientific_context.py"   "tests/01_decentralized_uploading/test_issue139_table_parameters.py"   "tests/01_decentralized_uploading/test_issue139_workflow.py" -q

conda run -n sc-wiki python -m pytest   "tests/01_decentralized_uploading/test_issue114_domain_extraction.py"   "tests/01_decentralized_uploading/test_legacy_scientific_assembly.py"   "backend/tests/test_property_record_conditions.py" -q

npm --prefix "frontend" run test:upload-ui --   "tests/01_decentralized_uploading/issue139-parameters.test.tsx"
```

预期：表格包、逐结果参数、字段别名、配对、阶段、范围例外、推断标签、指纹、重试及缓存用例都通过；故意破坏来源、上下文或关系的反例被拒绝或明确待核对，而非静默补值。

## 隔离 MySQL 往返

在测试专用环境安全提供 `SCWIKI_ISSUE139_TEST_DATABASE_URL`，不将连接串写入仓库、日志或报告，然后执行：

```bash
conda run -n sc-wiki python -m pytest   "tests/01_decentralized_uploading/test_issue139_persistence.py" -q
```

测试要覆盖实际 API／保存服务链而非仅序列化字典，验证草稿保存重开、正式提交、返修、导出、元数据与证据保持、权限和版本冲突。每个测试清理自己创建的隔离数据。SQLite 用例只能作为快速机械回归，不能代替此边界。

## 真实解析与浏览器核验

1. 从正常上传入口新建主文＋SI 任务，确认有效角色；使用任务当前模型完成解析，保留真实调用及未读／失败窗口账本。
2. 按原始表行身份核对 8 行，分别检查 λ、ωlog、Tc、μ* 与近似；不把两个 300 GPa 结果合并。截图对应行必须是 3.94、745 K、281 K↔0.16、311 K↔0.1。
3. 展开计算条件与原文证据，验证 QE 的 EPC 网格、SSCHA 超胞网格、VASP 结构优化参数分别可解释；依据不够的共用参数不能被写成直接作者逐条报告。
4. 核对所有直接值与共用关系说明：每个字段指向实际表行／表注／Methods；来源能定位不等于科学语义已通过。
5. 记录未填项及原因，特别是展宽、未知单位、仅有未配对范围、冲突及未读窗口。不要把未知误差或调用用量记为零。
6. 保存并重新打开，比较值、单位、阶段、关联和证据；修改或清空一个字段并重开，旧值不能恢复，旧来源说明不能沿用为新值的已核对依据。
7. 验证重复点击／重试不生成重复记录、不覆盖人工内容；保留每次实际版本与独立尝试，不批量改历史任务。

## 证据记录与通过标准

实施阶段在 `validation.md` 写明运行时间、源码提交／工作区差异、环境、模型、来源文件 hash、测试命令与收集／通过／跳过数、原文逐行对照、实际浏览器截图路径、MySQL 库的非敏感标识、调用数／耗时／可得 token 用量及所有未完成项。

SC-001～005 分别列实际结果与证据位置；8 行漏行和错挂为 0，阶段混用、误覆盖及编造为 0，保存重开保持一致。模拟通过、PDF 解析成功或表单非空都不能单独证明需求验收。远程 Spec／图片未推送或实际 URL 不可访问时链接门继续未完成，Issue 保持 OPEN。

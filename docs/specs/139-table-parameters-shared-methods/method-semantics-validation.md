# US4：计算方法语义修正验收

日期：2026-10-20；关联[#139](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/139)。用户已确认增量并回复“开始”。

## 修复结果

- 根因是READ提示词和缺漏检查明确把DFPT要求为electronic_method，关联补充示例及独立预期表也沿用该错误。现统一纠正为声子／电声耦合方法，不把错误归咎于用户输入。
- `calculation_methods.py`集中字段语义与明确类别错置判断；不采用DFT/HF封闭白名单。两种提取入口、全文READ、关联补空、建议与核对复用，遵循DRY和职责分离。
- DFPT使用已有`calculation_conditions.extensions`及`electron_phonon.phonon_method`，不增加数据库迁移或固定表单字段。原文只报告DFPT时不自动猜DFT；HF与其他阶段的DFT各自保留。
- 上下文版本升级v5、分段缓存版本升级13，旧提取缓存不继续复用。读取旧核对时按当前类别重新检查，原DFPT值与引句仍保留，但旧支持、错误接受及理由不再授予通过资格；正确DFT候选可以继续接受。
- 只在新提取及核对/建议边界增加语义检查；未批量改写历史值，不改用户已经填写的DFT，未改变来源关联继承机制。

## 自动化证据

独立目录从原始HEAD归档，仅叠加本次源代码、夹具和测试；排除工作区已有的角色识别和提取质量改动。

- 新增`test_calculation_method_semantics.py`：32项通过。覆盖DFT、HF及其他电子理论；DFPT、有限位移、软件及泛函误填；混合描述；READ纠错；实际领域和旧文本提取入口；旧缓存过期；阶段扩展、补空保护及JSON重读；历史支持与错误接受撤回；正确候选和无关科学字段保持。
- 独立副本8份相关测试共99项通过，包含上下文、建议生产链、表格参数、领域提取、来源核对、建议门禁和字段设置。工作区此前同范围在新增3项入口测试前为98项通过；两者数量不同源于工作区另有其他任务测试增量，不能混算为本次提交。
- Python编译与Git差异空白检查通过。只出现既有spglib、SWIG及crypt弃用提示。
- 固定的模型响应仅用于机械契约回归；不把它作为真实论文语义的证据。

命令：设置进程级`DATABASE_URL=sqlite:///:memory:`和测试专用`JWT_SECRET_KEY`，用项目Python执行`python -m pytest`，目标为本新增文件及test_issue139_scientific_context.py、test_issue139_workflow.py、test_issue139_table_parameters.py、test_issue114_domain_extraction.py、test_property_evidence.py、test_evidence_proposals.py、backend/tests/test_scientific_field_settings.py。未执行生产数据库迁移或真实论文提交。

## 真实Methods在线验证

当前服务端deepseek-v4-pro读取原任务主文中的电子结构与声子Methods连续段落，经真实`build_context → read_context`和原文定位校验，得到：

| 类别 | 结果 | 所属阶段 |
| --- | --- | --- |
| 电子结构理论 | DFT | structural_relaxation |
| 交换关联泛函 | PBE | structural_relaxation |
| 软件 | VASP | structural_relaxation |
| 软件 | Quantum ESPRESSO | electron_phonon |
| 声子方法 | DFPT | electron_phonon |

原文直接把DFT/PBE与VASP结构优化／电子性质计算联系，DFPT与QE声子/EPC联系。本次不把结构优化PBE无条件搬到EPC阶段，也不改写用户已填的DFT。

本次窗口complete=true、gaps=[]；核验运行前后原任务草稿完全一致。设置与制品哈希见[在线验证摘要](assets/method-semantics-live-validation.json)；完整原文与模型响应留在本地.data制品目录，不加入Git。

较大Methods窗口的首次尝试中，模型输出了没有有效来源的μ*，两次尝试均被拒绝并保留失败制品。相关方法段落验证成功不等于完整新上传管线已重新验收；没有降低原文门槛来制造成功。

## 需求覆盖与交付边界

FR-012/013、SC-006由共享类别判别、两入口、READ→阶段补空及真实方法段落覆盖；FR-014/015、SC-008由旧核对/接受测试、正确候选保留、补空不覆盖和JSON重读覆盖；FR-016、SC-007由仅DFPT不造DFT、HF分阶段及真实Methods覆盖。未重新跑真实账号的MySQL完整提交链，持久化合同及数据库结构不变。

IMG-004原图已按字节归档并解码查看，324×180，哈希见Spec。原有未提交改动保留。本次只在mayuan提交自身增量，不推送、不批量修复旧草稿；远程新版Spec与附件待推送后核验，Issue保持开放。

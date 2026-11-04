# 数据与接口登记

科学表单标准键、类型、单位及锁定摘要不变。材料状态仍为material_states，结构仍为S.structure，标量结果仍为property_modules.records。模型规划的states/assignments是内部控制协议，不是业务表单的新字段；服务器生成稳定身份。暂填归属的疑问进入既有generation_issues及字段来源核对，不能授予人工确认。

## 谱标定与数值版本
- CurveCalibration.color增加black，包含黑灰像素；可选trace_anchors为原图[x,y]观察锚点，仅选择实际像素分支，不生成幅值。
- PanelCalibration增加可选kind（phonon_dos/alpha2f）及assignment_reason。无曲线时必须有明确目标类型；非法轴标定不采纳，但保留已验证的目标身份和材料归属。
- 算法版本为spectra-production-state-first-v3。黑灰图框附近的长线及触边、短细且未进入图内的刻度被排除；连续进入图内的真实轨迹保留。无法分辨的像素保留缺失，不因移除刻度进行伪插值。
- 当前谱集合和运行仍使用SpectrumCollection/SpectrumRun，质量、原像素、候选与版本各自保存；无需新增数据库表或迁移。

## 自动谱与中断恢复
自动谱执行位于上传ready之前。发现运行的calibration_json记录automatic_upload_job_id，用于程序执行归属，不是科学标定键，也不发送给数值标定校验。手动入队会清理旧执行归属，不能继承旧父job。

父Worker失败只结束该父job拥有的自动谱，迟到的旧job回调不能覆盖新轮次。失败任务已完成全部字段核对、原稿未被人工改动且剩余阶段为谱时，重试只续跑谱；其他失败仍走完整原流程。retry是状态迁移参数，不持久化；续跑通过extracting入口开始新一轮计时，再显示实际的spectra预览阶段。遵循#170：失败旧轮次耗时保留为证据，重试新轮次单独计时。

## 显示和删除
同目标刷新不清空旧列表；终态无自动查询，冻结历史无当前谱请求。无曲线的目标谱按类型显示在对应材料状态，非目标空记录不出现在末尾。只有累计λ时不得借超导族kind显示为已有α²F数值。删除整份上传稿时，在同一目标范围删除其谱集合和运行，保留其他任务及共享图片。

## 单记录纠正的内部协议

record_assignments为受限模型控制数组，条目仅有candidate_state_key、module_key、record_key、target_index、status、source_ids、reason。未覆盖的记录沿原父assignments去向；指定记录仅有一个纠正去向，完整复制原科学值和稳定身份，并追加由当前来源目录取回的原文依据。状态和属性记录仍使用既有业务结构，标准科学字段、契约摘要、数据库结构均不变。

规划请求和响应分别保存，原始提取仍留档，可追溯初始候选、引用图页、纠正理由及输出。规划的supported/uncertain是候选归属判断，不是字段科学通过或人工确认；最终选择的引用仍由既有统一核对及正式交接保存。

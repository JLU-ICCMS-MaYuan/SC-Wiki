## 最新：自动谱与引用已完成，Safari 已保存重读，待 LaH₉ 同压物相拆分

任务 `d789acceee124022b3257f84780d1156`，Job `e7f9b20c-7799-4e6e-bce9-a033cb0e343d` 已 FINISHED。Safari 18044 核验原用户邮箱和模型后正常继续；实际同一自动谱运行 `3fbd8275b41042b397a9484e629fabb7` 由新 Job 接手。29/29 分段和 26/26 组共 52 状态保留，原模型和文件不变。谱数据库重读为 SI 第 14 页 4 面板、8 曲线、零技术错误；图注与坐标的 α²F 定义及两排压力归属仍待核对。引用匹配 completed，69 条。网页普通读稿、实际保存和再次打开均已留证。

按正文 Fig.1(c)，网页补填 YH₉@150 GPa 的 P6₃/m（176），更正 LaH₆@100 GPa 为 R-3m（166）；只读库和网页重开一致。CeH₁₀@200 GPa 仍 Fm-3m，用户指定的 ScH₆@300 GPa 确实仍 Im-3m（229），留作退回后的真实返修项。图谱标题现为 Predicted Room-Temperature Superconductivity in YH10 and Hydrogen Clathrates of Rare-Earth Hydrides，保留待退回的用户指定标题更改。

送审前阻塞：用户明确确认 LaH₉@50 GPa 拆成 P6₃/mmc 正文物性（Fig.4 Tc/DOS 及同组 λ、μ*）与 Cc 的 SI 表 S1 结构。现有草稿一张 Cc 卡同时持有两组数据。真实状态规划响应已把 Fig.4 和 S1 合到 Cc，正式请求原页未带正文 Fig.1(c) 所在第 2 页；随后结构归属按 Cc 挂表 S1，不是保存把两张状态合在一起。#136、#227、#204 已要求物相和来源隔离。现有界面证实当前 Cc 结构只有下载、恢复待确认等入口，物性表单无保留身份和来源的跨卡移动；当前 canonical 结构的恢复动作也不产生可重新分配的候选。不用手抄、改库或替换来源来拆分。

[合并证据与网页重读](ready-and-phase-audit.json)。当前仍阶段一，DOI 10.1103/PhysRevLett.119.107001，未送审、无正式 Paper ID。阶段二至五未执行，未清理重传，未推送或部署。应从本草稿继续，完成正确拆分并核对受影响字段，再进五阶段和最终无调试复测。

## 最新：谱声明修复f1dbb583后续跑发现旧running，已补恢复逻辑

原Task d789acceee124022b3257f84780d1156，上一Job2692ef85-d839-4007-b08e-bb4403648ad3 failed/automatic_spectra_incomplete，observe-20261110T235604582175Z.json。旧谱运行3fbd8275b41042b397a9484e629fabb7 running，实查其父Job862cbf40 FINISHED，非真实执行。补同Task当前自动谱只恢复已核实结束父Job、暂停控制信号结清本父谱，不接管运行中/未知父任务或手动谱。旧回归先检出，114通过1个MySQL竞争条件在SQLite跳过、3定向通过。下一步提交后通过Safari继续实际消费谱，不改DB状态、不重传；52状态已保存，仍无正式PaperID，阶段二至五未执行。用户已确认ScH6条件式返修，详下文。

## 最新：用户已确认ScH6真实返修项；52状态完成后谱503格式故障已修复验证

Task仍d789acceee124022b3257f84780d1156，Job862cbf40-6dab-4c37-9b5e-50fd29c7c18f已保存26/26组52状态，automatic_spectra因明确report_spectrum_calibration数组schema错误被网关包装503，5次后按规则paused，未收到输出。五份失败保留issues/spectrum-wire-schema/。当前没有正式PaperID，阶段二至五未执行。

用户原话“采用，并作为材料级返修项（推荐）”：若最终稿ScH6@300 GPa仍Im-3m，管理员真实退回后Tc/DOS归属改P63/mmc；正文Fig1(c)及SI S28(f)证据，Tc约99/86和原来源不改，300晶胞不借200/350；若已正确不写坏。论文级图谱标题仍High-throughput Study on Rare-earth Clathrate Hydride High-temperature Superconductors。笼型标签继续核对；CeH10@200 Fm-3m用户确认保持。其他相图差异依原文和既有人审，不加产品特例。

已实现谱同类型定长tuple的等价items/min/max传输、明确schema拒绝503不重试；真FigS15暴露面板级物理单位错提前整批拒绝，恢复原逐面板反馈与已有不完整保留，明确α²F单位/α²F/ω不确定不积分。共享/独立225、四宿主233、12变异和字段契约通过。原正文1页非谱零面板、SI14真FigS15四面板，原模型LLM2/gpt-6.1-sol、原源、正式谱engine、隔离保存重读通过；α²F未确认且积分不可用。非整篇谱或业务完成。docs/specs/233-unified-image-tool/spectrum-wire-validation.md。下一步提交本次代码及证据，Safari原任务继续，不重传；其余已保存同版本组应复用，仍需全谱/引用/ready和真实五阶段及最终无debug复测。

## 最新：第5组已越过旧图读阻塞并真实保存，继续第6/26组；ScH6科学返修选项待用户答复

Task d789acceee124022b3257f84780d1156，现Job862cbf40-6dab-4c37-9b5e-50fd29c7c18f，代码5d400eab，LLM2/gpt-6.1-sol及原文件/端点/hash保持，正常Safari18044继续，无重传。29/29和覆盖通过；正文最后窗口首次规范值与value_kind不符，由既有一次纠正通过，未加新轮次。新规划52状态26组（原54/27）；全稿输入签名因原页/来源变化未直接复用旧整组检查点，重新处理有实际新模型调用。前8持久快照和旧核对记录均保留，新旧按相同材料/压力/相对照主要Tc、DOS、μ配对、方法原名一致；LaH9@50状态内部key有变化，整树并不一致，不声称完整复用。原/新快照及实际调用账本见issues/retired-chart-scope/。按#230实际持久表ScientificUploadDraft和tc_contexts.map_draft重读，Redis旧缓存不能验收解析中间保存。

第5组两轮新填写、5个原候选完整去向、实际原Claim门通过、8批字段核对与持久保存重读已通过，现累计10状态且第6组reviewing。CeH10@200 Fm-3m，Tc58/49 K为Fig.4读图约数；DOS现主值仍空，Fig.4 H贡献及S33未标相同投影的两个原记录约.0228各归档，不当相同物理量也不随机选首条。核对结果67 supported、23 missing、6 uncertain，零技术错误；有待人校对并不假称均科学通过。旧v8未出现在当前记录，实际保存与检查点一致，bbox序列化微差披露。见live-group-0004-filling.json/live-group-0004-persisted-reread.json。

科学人工QA见issues/scientific-scope-audit/scope-audit.md：原图实际看过正文Fig1(c)及SI21/23/26。当前IR有效Fig.4 38图读、ScH6@300持久Tc/DOS/λ/μ和约数/原图来源通过独立像素参照（非物相验收）。现ScH6@300自动稿Im-3m不合Fig1(c)具体压力P63/mmc及SI S28(f)P63/mmc@300，已用request_user_input_async询问是否按P63/mmc修并作为真实材料返修项（若最终稿仍错），未获答复；不要假定推荐已批准，不依赖此决策的解析继续。原计划图谱标题High-throughput Study on Rare-earth Clathrate Hydride High-temperature Superconductors及指定笼型标签仍核验，已正确不可改坏。LaH6@100图1(c)R-3m（S1R-3c是150），LaH9@50图1(c)P63/mmc与S1 Cc结构不能按同压合并，YH9@150图1(c)P63/m与高压P63/mmc不同，待最终稿核查并按既有科学人审处理；不加产品规则/单篇特例。正文Fig.4 H贡献DOS和SI S33 200GPa电子DOS不同口径。

#136评论6779252569、#233评论6779253338，均OPEN、未push/部署。watch_current.py只读进度，当前session6047可继续等；watch-progress.jsonl保留状态变化。最终仍须所有26组、谱/引用、ready普通网页重读和人工校对/保存/送审，再超管真实拒绝、原用户两项返修重提、日志批准、YH10探索与正式库核验；完整排障轮之后精确ID留证清理重传同原文件，完成无需debug的完整五阶段。当前无正式PaperID，阶段二至五未执行，不能宣布完成。

## 最新：5d400eab已提交，原任务正常网页续跑新Job862cbf40

当前Task d789acceee124022b3257f84780d1156、Job862cbf40-6dab-4c37-9b5e-50fd29c7c18f（不要再跟踪已失败90a96895）。Safari18044重核myth620137018@163.com/用户/gpt-6.1-sol/同Task+文件后正常点击继续，无重传。observe-20261110T210344985344Z.json reading 4/29、chunk_extraction正文3/4页receiving、无processing_error，provider/input/endpoint hash不变。必要新图片/上下文窗口实际重提，其他签名复用，统计应按新Job开始时间区分。后续核验前8持久状态及有效结果与persisted-prefix-before.json.gz保持，不直接替换引用编号或回填隔离答案。

源码修复5d400eab、首组保存记录0c48b473、原备用文段74b56bae、结构预算/38→1完整报告214ee6ef。当前backend代码已提交且复核同隔离真实模型指纹。旧图读v8已从scope发现及旧检查点恢复过滤；共享/独立120、原SI带完整tc_material_scope新Gpt提取/normalize/定位/保存重读及5原页600DPI通过。四宿主初次232+1失败保留，单例及完整233重跑通过，12变异/字段契约通过；未改超时/断言、未改科学字段/模型/96k/10Worker。相关docs/specs/136-complementary-pdf-parsing/retired-chart-scope.md。

只读观察watch_current.py可重新运行（上个session30661已在90a96895失败后退出）；它只get_state、5秒检查/45秒心跳，日志watch-progress.jsonl。下一步继续全29分段与整理/组处理，不能只看到ready就结束。仍阶段一，无正式PaperID，阶段二至五全未执行；完整排障轮五阶段后要精确ID清理重传一轮无需debug完整五阶段，保留最终正式论文。Safari旧17885多同URL不要用，Chrome1758018018账号mayuan_mark@163.com需操作前重核。所有业务变更走网页。

## 最新：第5组旧图读回灌已修复，独立120/真实SI新提通过，待提交并原任务继续

业务Task d789acceee124022b3257f84780d1156，Job90a96895-4f0d-40a7-8cee-5f77beace08d已failed/summarizing/material_filling，第5/27组“原候选来源未读取或不存在”；前4组8状态已持久保存，前8状态快照/阶段检查点和失败报告保留issues/retired-chart-scope/。新Job尚未点击继续，无正式PaperID，阶段二至五全未执行。observer最后observe-20261110T202353806180Z.json。

不同于前次真实Marker原文：此次原候选CeH10@200 DOS引用旧v8 chart-reading-8787c5…（已selected_for_reading=false、superseded_by=v10），inventory_scope_sources的found及prepare_source_handoff旧scope_source_blocks恢复未过滤派生，重新把它交进新提取。当前共享is_original_block只按chart_reading/chart_unresolved区分原始识别/派生，Marker仍原文；补源发现/对齐/检查点恢复过滤派生，审计source-scope-handoff-v2失效旧请求，既有来源门不放宽。也将遗留1.4倍原页图片统一到现有pdf_regions 600DPI取源，记实际定位/DPI/hash，原图分片仍既有机制，96k/模型/10Worker不改。

当前源码尚未提交仅本任务extraction_sources.py、image_catalog.py、scientific_form_filling.py（共用predicate）及test_extraction_source_handoff.py和136/233/Overview文档。共享/独立120通过、字段契约/12变异通过。四宿主初次232pass/1返修attention断言失败（未改FE，完整失败存档），不放宽断言，单例1pass（14筛选未运行）/完整233重跑pass。Bandit/pip_audit先前均缺，未新增依赖/改SQL。

真实同原SI窗口最新代码隔离新模型已通过（issues/retired-chart-scope/verify_live.py）：LLM2/gpt-6.1-sol/同endpoint hash，tc_material_scope按真实业务完整传入，旧chunk种子只用于找回原依据，原页2/3/24/26/33全600dpi；旧v8从新适用条件与当前Ce引用排除，新DOS .0228、初始phase null，未借R-3m声子；正式normalize/定位/类型/保存JSON重读通过，无业务写入。source_files指纹与当前代码一致，不是旧AI重放。真实业务还须新填写/科学核对/保存，不能以隔离结果结束。

接下来提交合理验证的本任务检查点（不含其他工作），Safari18044/account+Task按URL重新核验用户邮箱/模型/DOI/文件后正常继续，记录新Job。重点核验前8状态及有效审核结果/模型调用复用（前8快照persisted-prefix-before.json）；不要手动换旧引用编号或回填隔离答案，不清理重传。查看ScientificUploadDraft持久中间稿并展开tc_contexts，不能用Redis旧paper-only缓存验收中间保存，ready后普通网页读稿另核验。

记录工具watch_current.py已编译运行过，只读跟踪每5秒、45秒心跳并写watch-progress.jsonl，无业务操作；当前session30661已在failed后正常退出。下一Job可重新启动，先active-task.json更新JobId。还有完整排障轮五阶段及精确ID留证清理后同源无debug完整复测，当前均不可称完成。

## 最新：90a96895原Job第1组真实填写/来源门/核对/持久在线保存重读通过，继续第2组

当前Task仍d789acceee124022b3257f84780d1156，Job90a96895-4f0d-40a7-8cee-5f77beace08d，代码74b56bae，原LLM2/gpt-6.1-sol及原文件/哈希未改。第1/27组3次真实新填写、10原候选去向、原Marker2块已读和Claim来源门成功；9批107supported无review_error，material_batch.completed_states=2，已进入第2/27组，目前reviewing 4/9，无processing_error。须继续到所有27组、谱/引用和最终ready；阶段二至五仍全未执行，无正式PaperID。

第一组保存核验曾读错对象：get_draft在无ScientificWorkDraft时读Redis旧paper-only缓存，得0材料。#230 plan明确组完成保存到ScientificUploadDraft，SQL中实际54个状态框架与前2个完整数据。只读从该正式持久表用tc_contexts.map_draft展开，共同参数/主要值及所有来源身份/引句等与检查点一致，仅source bbox JSON浮点表示差异，未加产品容差或改数据。ready后普通读稿与网页还需再核验，不把解析中缓存不同直接当新bug。见issues/cited-alternative-source/live-group-0000-persisted-reread.json。

主要当前数据：YH10@400 Fm-3m Tc303/287 K、lambda2.41、mu .1/.13、DOS.0201；ScH6@300 Im-3m Tc约99/86 K、mu .1/.13、DOS.0156、GPT图读lambda约1.32（不是独立Flash1.30的同次精确值）。method_code unknown但method_raw Eliashberg equation完整，未擅自补未报告各向性。不要只看method_code或某空列断言方法丢失。

新增源修复真实验证记录已写docs/specs/136-complementary-pdf-parsing/cited-original-handoff.md，整体Issue仍OPEN；136评论6776166237，210评论6776167118。当前未提交只本轮active/case/CONTINUATION及该验证文档；源码已74b56bae，不push/部署。Safari18044、Chrome1758018018每次按URL重枚举并核验邮箱/角色/Task/论文，不能沿旧tab号。旧Safari17885同URL重复不得用。后续读checkpoint只读material-stage.json；其draft与正式ScientificUploadDraft展开对照，不用旧Redis缓存验收组保存。

## 最新：74b56bae已提交，原任务网页再次续跑到第1组新填写

备用原文交接代码/测试/文档已提交74b56bae，随后工作区干净，未push/部署。Safari18044重新按URL核验myth620137018@163.com、gpt-6.1-sol及同Task/文件名后正常点击继续。新Job90a96895-4f0d-40a7-8cee-5f77beace08d，observe-20261110T184714227046Z.json已summarizing/scientific_form_filling requesting，29/29、coverage_checked、旧错误清空，前置同请求完整响应快速复用。本次字段新填写/核对/保存尚待验收，不以代码/固定源通过作完成。

Task仍d789acceee124022b3257f84780d1156、原模型/输入/端点哈希相同。新Job必须跟踪material_batch index/total/completed_states与processing_error，不止看models活动；之前来源门失败时model_activity为completed但任务failed。阶段二至五仍全未执行，无正式PaperID。其余完整排障轮与最终无debug重测要求照旧。

## 最新阻塞及修复：第1/27组已引用Marker备用原文未交接，固定源与回归完成待网页续跑

Task d789acceee124022b3257f84780d1156、Job414a7e57-44b0-49d1-952d-026b9099d86a已failed/summarizing，processing_error=第1/27组填写未完成：原候选来源未读取或不存在，0组完成，无正式PaperID。最后业务observe-20261110T181452845222Z.json。前面已完成29/29、54状态规划、结构分配；CeH10@200真实规划结果Fm-3m，13原来源独立保留S31 R-3m声子，证据issues/phase-handoff/business-*。

已定位并实现普通旧要求交接修复：两个原候选引用正文第4页Marker真实原文块d4668…/c56f…，IR selected_for_reading=false只是未选主干，前面显式Claim可定位，后面form_sources只提供主干导致原候选来源门拒绝。没有关闭保护。scientific_form_filling._referenced_original_views仅对当前material_states明确引用、同file/page/version/hash/quote的原始备用块补入只读视图，排除chart_reading/chart_unresolved，不改原IR和主备路由；upload_jobs材料来源调用传references。其他form_sources默认行为不变。

实际同PDF/SI哈希/原IR/真实失败固定验证15个必要来源由缺2→0，目录1144→1146、预读19852字符；无新模型调用。共享/独立87、四宿主233、12变异、字段契约、compile/diff通过。旧四工具重试夹具在独立未改HEAD失败，改为部分输出后连接中断+次轮连接错误+末轮完整严格schema；不改产品非法JSON立即停止。其独立/data目录问题也通过tmp_path隔离修正；初次失败保留。详细docs/specs/136-complementary-pdf-parsing/cited-original-handoff.md、issues/cited-alternative-source/。

当前这批修复尚待提交（mayuan）；只有本任务prod2文件、测试/fixtures、136/210文档及Overview/本轮记录，保留共享变化。接下来按root要求提交合理验证的检查点，再Safari18044实际核验账户/模型/DOI/Task，点击正常继续并记录新Job。需要真实新模型填写、原Claim/字段核对、保存和重读验证，不能以固定源验证宣称业务通过。所有早前源模型调用可按同请求缓存合法复用，统计新/复用范围。

仍需完整排障轮五阶段，再按精确ID清理重传并完成无需debug完整五阶段，保留最终论文。阶段二至五仍全未执行，不得宣布完成。原纸名/哈希/用户和超管及返修要求见下文与case；图谱标题目标High-throughput Study on Rare-earth Clathrate Hydride High-temperature Superconductors。若笼状标签已正确，不能故意改坏制造返修。

## 最新业务进展：原Job已完成29/29分段并进入结构优化/材料整理

observe-20261110T180324089749Z.json：Task d789acceee124022b3257f84780d1156、Job414a7e57-44b0-49d1-952d-026b9099d86a，status/stage=summarizing、reading_state=coverage_checked、29/29、无processing_error，当前structure_optimization receiving。此次实际结构报告call-4/call-6均36条（业务收录范围），已越过原预算与覆盖阻塞；独立无范围SI验证38→38另计，不能混成同一层证据。正文/SI新结构读取后本轮分段0→29已观察。

调用账本events.jsonl按2026-11-10T17:35:10Z之后区分completed/reused；已留call-counts-*.json，requesting有预算准备/实际尝试双事件不能当调用次数。runtime原图事件文件会覆盖同迭代名并保留旧高编号，读取时需按本Job开始mtime/运行器generation识别，不凭残留文件计新请求。Safari当前已能读取真实动态，曾后台标签JS慢，选中本轮隔离窗口标签后恢复；原生window18044 URL需每次重枚举，禁止固定tab号。Chrome1758018018仍account。

源码214ee6ef，续跑记录233f7f62，未push/部署；原业务模型/哈希不变。当前仍阶段一，待完整整理/谱/引用/字段核对和草稿保存，再科学校对送审，之后真实两项退回、返修重提、带日志批准、YH10探索/正式库核验。完整排障轮后才能精确ID清理并同源重传完成无需debug的完整五阶段；无正式PaperID，阶段二至五全未执行。

## 最新：214ee6ef已提交，原任务已Safari正常续跑

Task d789acceee124022b3257f84780d1156，新Job414a7e57-44b0-49d1-952d-026b9099d86a，真实Worker已消费、正文structure_reading requesting。原模型LLM2/gpt-6.1-sol、input/endpoint hash和两个原文件未改；29/29是前轮分段保留，不冒充本轮重提。实际observe-20261110T173528305816Z.json、浏览器操作JSONL有证据。Safari18044/account/任务页已重新核验用户邮箱、模型、文件名和DOI；曾account标签变/upload，已重新按URL枚举导航恢复，不能沿旧标签号。Chrome1758018018超管账号已核验但阶段二仍未进入。

修复与验证已提交214ee6ef，工作区随后干净；#224评论6774504936，#234评论6774505838，均OPEN、未push/部署。原SI新GPT7调用、报告38→38、32有效6疑点、CIF/JSON重读与最新源码固定重放通过，共享/独立118、233表单、12变异、字段契约通过。请继续当前业务Job及完整五阶段，不再次重传。阶段二至五仍全部未执行，无正式PaperID。前文“待点击继续”已被本节取代。

## 最新：结构预算与38→1覆盖故障已修复验证，待原任务网页继续

本轮Task仍d789acceee124022b3257f84780d1156，业务Job29ef38d7-65c0-42b0-b4c3-04ad63549d45仍failed/structure_reading；尚未再次点击继续，无正式PaperID，阶段二至五全未执行。Safari18044与Chrome1758018018账号均重新核验；Safari任务页先前显示旧状态，普通刷新后正确显示失败及继续解析，未重复上传。

新增修复：结构两个工具的长block_id枚举改现有source_id精确别名执行前还原，当前观察仅在与最近原生工具回执全值相等时引用。真实失败112249→87621估算token，96k/原文/8图/10历史保持。其后同GPT隔离真实SI发现38条被1条局部报告覆盖；已补完整报告覆盖检查、同条件独立来源一对一与无进展识别，原13动作/科学校验不变。第二轮同LLM2/gpt-6.1-sol 7次新模型，两份报告均38条，32有效/6真实疑点，JSON/CIF重读通过。最新加严覆盖源码逐次请求/历史/结果固定重放完全一致，不将重放当新模型。代码期间唯一额外差异是同条件来源检查加严，已如实披露，见issues/structure-budget/latest-source.json。

共享和独立HEAD加本任务覆盖源码各118通过，四宿主Node22 233、12变异、字段契约通过；Node26 localStorage12环境失败、缺测试配置的初始2失败、首轮脚本tuple/JSON比较失败均保留。前置Flash/MySQL/旧七失败已有3d080211和0d919fcb，原79MySQL与16旧回归不冒充此次SQL重跑。未推送/部署/改模型/改业务草稿。详docs/specs/224-resumable-model-requests/structure-request-validation.md，证据issues/structure-budget/。

接下来仅提交本任务明确文件，Safari18044核验账号、模型、Task身份后点击正常“继续解析”，记录新Job并核验Worker实际消费。之后坚持完整排障轮五阶段，再精确ID清理重测一轮无需debug五阶段，保留最终正式论文。不可把当前隔离成功算整篇或业务完成。

## 最新：Flash/MySQL/旧失败前置已完成提交，原gpt任务已真实网页续跑

当前Task d789acceee124022b3257f84780d1156，新Job29ef38d7-65c0-42b0-b4c3-04ad63549d45。实际Safari新隔离窗口18044（17885现有同URL两个标签所以不用），account重核myth620137018@163.com用户、头部openAI/gpt-6.1-sol后正常继续；超管Chrome1758018018仍/account，使用前再核验。每次按实际URL与window重新枚举，不沿标签序号。当前真实Job已消费、SI13页请求已送模型并接收，暂无processing_error；29/29为前轮候选，当前前置图源仍进行，实际重提/复用待账本核验。没有重复上传或业务回填。

3d080211已本地提交Flash前置收尾：原模型Flash13次原PDF新图读38条/同原位图独立参照全部0偏差，ScH6 DOS.0156/lambda1.30/Tc99/86、mu=.1/.13/300GPa；01/02重复框失败保留，03图读后测试验证代码转义失败保留，修纯测试验证并编译，核心backend SHA一致才复用有效IR，另2次Flash真实normalize/assemble/fill/JSON重读完成，Sc四字段共同lambda/约数/图源保持。独立像素参照测试专用，不进生产/模型提示。PrH9无独立可定位值空着，其遮挡/截断措辞未证实，仅保留模型观察，不当物理事实。详FLASH-FIG4-VALIDATION.md及docs/specs/234-image-feedback-repair/flash-fig4-scientific-validation.md。

当前/独立140项、四宿主233、12变异、字段契约通过；私有MySQL两次79项零skip（原6涵盖），业务库未使用、进程停止临时数据移除；旧失败当前16pass。b1348ad5目录/原文上下文修复已提交，原225154token目录1308压至215/70814，原文/图片不删。#232—235已更新评论6773336250/6773337290/6773338239/6773339319，继续OPEN，未push、官方OpenAI实际账号仍未覆盖。

未提交剩余仅本轮阶段记录/既有Ce源交接验证docs（136/211）及helper，注意只纳入本任务，source code应已全部提交。接下来必须继续完整业务：解析/整理/字段审核/谱/引用→用户校对保存送审→超管真实两项退回→原用户修改重提→具体通过日志批准→探索YH10命中本轮与正式库主要数据/方法真实所有权及来源核验。排障轮完整五阶段后才能精确ID留证清理，再同原文件最终无debug完整五阶段并保留最终正式论文；不能以这些前置通过结束。

当前无正式PaperID，阶段2—5全未执行。输入文件/角色/SHA/DOI在case。图谱标题目标High-throughput Study on Rare-earth Clathrate Hydride High-temperature Superconductors；五类笼状结构现有ID1，草稿已正确不可故意造改，届时需实际找真实返修项。CeH10@200GPa Tc/DOS最终Fm-3m用户已确认，声子R-3m证据独立；当前既有23fd2125源交接会在续跑把S1原文交给误提SI窗口，不放开跨物相保护，隔离probe已phase=null及正式normalize/JSON重读通过。实际业务纠正仍待核验，不能把隔离答案写回。

## 最新用户追加要求及已通过前置：先Flash科学验收/MySQL/七项旧失败，再继续原文献完整黑盒

用户已明确答复：本任务接手，并先完成Flash Fig.4科学读数、原6项MySQL及7项旧基线，再继续黑盒。因此此前“等待共享归属确认”已失效。共享基线71b02686、MySQL/旧失败修订9861300e已由原任务提交。本任务独立目录/原文上下文修复b1348ad5已经提交（102共享/独立，233表单，12变异、字段契约；真实SI13页5条读数及IR重读）。当前原业务Task仍d789acceee124022b3257f84780d1156、Job2a43b499…failed预算错误，尚未再次点击继续，遵守先完成前置，不删除/重传。

Flash实际模型server:LLM1/deepseek-flash独立于原文献gpt-6.1-sol，浏览器模型未切换。新flash-fig4-current-01/02因盘点3面板重复同外框失败，已保留。当前未提交普通实现补齐：backend/ingest/discovery_feedback.py及chart_reading接线（旧page_inventory保护原样，错误页原模型+实际600DPI整图/图注重读，成功页面不重问，无新依据停止，复用13动作预算）；image_geometry.py提供无科学标签的像素框/轴/刻度/色块候选，image_reading/image_feedback接线帮助原模型定位，程序不赋材料、物理量或科学数值。

flash-fig4-current-03已13次同Flash新模型实际读取原PDF Fig4，38事实、ScH6 DOS.0156、lambda1.3、Tc99/86与mu=.1/.13、300GPa。新测试专用fig4_pixel_reference.py按原始879×632位图已核对刻度/材料标签/基线连通柱建立独立参照（无GPT投票、无正文反推轴；3原位图像素容差不看模型自报精度），全部38条数值/柱归属/压力/mu/单位0错误。PrH9 Tc不可辨保留未读，不填0。旧Flash6事实被严格参照检出39问题；旧GPT38事实通过同参照。原图与参考JSON在run，生产无论文名单/预期值。

03随后验收脚本的字面换行转义错误使后处理前SyntaxError，原失败留log；仅修测试验证代码并compile，核心backend源码未改。为不重发13次有效读图，run_visual_sources_validation.py增加--resume-ir守卫原PDF/模型/provider/逐核心文件SHA，flash-fig4-current-03-postprocess复用该IR，科学提取和正式normalize/assemble/fill另发2次同Flash真实调用，保存重读完成，scientific-verdict.json和form-scientific-verdict.json均passed/issues[]，Sc四字段/共用lambda/约数/原图来源完整。端点旧检查点没有摘要，resume.json如实披露，没有伪造；本轮沿同一LLM1，原业务模型/端点未切换。

MySQL已用当前码重新启动私有临时MySQL8.4.2（127.0.0.1:60439，issue137_test_fe6fe4b20e18，绝非业务3307）：mysql-current-verification/pytest.log 79 passed零跳过，涵盖原6项；result.json business_database_used=false/server_stopped=true，目录实际已移除。七项旧夹具已986修，当前另跑test_property_field_review+test_structure_request_redundancy+test_mysql_isolation，old-seven-current-verification.log 16 passed。

当前在收尾新geometry/discovery/科学参照的既有回归、四宿主/字段/变异与独立源码，然后更新232—234对应Spec/验证/Overview并仅提交本任务hunks（注意他人可能仍改同文档；code源当前只本任务修改，已提交源均不含他人未提交）。之后实际Safari17885重新核验账号与任务点击继续，记录新Job及实际v10；原gpt Task从原状态继续，现行CeH10源交接会让初始DOS不借声子R-3m，用户已确认Tc/DOS最终Fm-3m，声子证据独立。前置局部通过不代替业务。

原五阶段与跨轮规则不变：先排障轮完整上传解析/送审→超管真实拒绝→同用户两项修改重提→通过日志批准→探索YH10命中本轮及正式库/来源/方法真实归属核验；完整排障通过才精确ID留证清理，再同原文件最终无需debug完整五阶段并保留正式记录。当前正式PaperID仍无，阶段2—5全未执行。图谱标题返修目标用户已指定；材料五类笼状结构，已正确不能造改，具体返修需草稿实际核实。

## 最新阻塞：v10全量图像对象目录超本地预算，已提问修复归属

当前Task d789acceee124022b3257f84780d1156，Job2a43b499-c176-4a94-8dfd-11a291d32160已failed，SI13页chart_reading在发模型前ContextBudgetError；不是503。原29段未删除，当前仍阶段1无PaperID，不能点击未修原请求反复试。已通过request_user_input_async询问：由负责232—235的任务修（需用户给任务名并授权消息），或本任务接手必要共享实现并提交。尚未得到答复，不能发消息给其他任务。

实际失败225154估算tokens，payload.available_objects含1308对象（319827字符）及原文source_pages50273字符，7个工具schema还重复所有block_id。离线严格父表包含探针：排除已退出当前选择/派生读数目录，并将805个有同页、bbox完整包含父表的单元格入口收拢到父表，保留无父表/越界单元格能力；215目录项，预算70814<96000，全文和图片逐值不变。尚未改生产代码或发模型，不能宣称修复通过。issues/image-catalog-budget/含failure、catalog-probe、strict-parent-probe、805cell-parent映射、blocked-state及本地完整failed-request.json.gz。完整大请求不提交，轻量证据可以。

目录/动作涉及其他任务尚未提交的新文件backend/ingest/image_feedback.py、image_reading.py及review_tool_contract新接线，依赖pdf_regions等未提交实现。无法把这几行独立提交而不带入整组新文件，须遵守AGENTS只提交本任务边界；不要擅自接管或重置对方代码。后续若用户授权接手，按需求/实现/失败先红后绿/原PDF受影响调用真实验证；不能提高96000预算、删正文/SI科学依据或把旧AI答案回填。

此前CeH10初猜保护已调查：原29/29与coverage complete后，SI DOS借用声子R-3m触发规划保护。既有23fd2125源交接隔离正式_read_chunk新模型返回物相null，normalize/来源/JSON重读通过，9既有回归通过；用户已确认Tc/DOS最终Fm-3m，声子R-3m依据独立保留。该隔离探针未传整篇tc_material_scope，只证明物相源交接，不算整篇规划通过；已另存PHASE-HANDOFF.md及verify_phase_handoff_live.py。新Job在新读图v10前置预算处失败，实际业务尚未再次走到该纠正窗口。

仍需完整排障五阶段→精确ID留证清理→相同原PDF最终无调试五阶段。用户Safari17885（/account重核myth620137018@163.com用户），超管Chrome1758018018使用前重核；每次按URL枚举。已修复提交b62b3946分片、4adc30d1柱边、9619fd05断流；记录提交fd38249d/2637ecb0。共享232—235源码保留未混入。图谱标题和五类笼状结构返修目标在case，草稿已正确不能造改；当前无草稿最终核验/送审。

## 最新：CeH10旧初猜保护触发，既有源交接验证后网页续跑

当前Task仍d789acceee124022b3257f84780d1156，新Job2a43b499-c176-4a94-8dfd-11a291d32160（Safari17885实际点击继续，账号重核myth620137018@163.com）。先observe，不重复续跑。此前073d351d已实际29/29、正文/SI coverage complete、requires_human=false；状态规划因CeH10@200GPa初始电子DOS借了S31声子R-3m，拟按S1改Fm-3m时，被现行跨物相保护拒绝。守卫正确，本次没有改生产代码或放宽保护。

已对照#211 2026-11-10原确认与23fd2125既有机制：inventory_scope_sources能将S1等同SI原文交回误提SI窗口2。隔离verify_phase_handoff_live.py经正式_read_chunk/normalize/来源校验/JSON候选保存重读，新模型返回CeH10物相null，不再借声子；用户已明确Tc/DOS最终采用Fm-3m，声子R-3m独立保留。隔离结果不写业务、不拿旧答案当新提取；探针没有传整篇tc_material_scope，不能当整篇范围/规划通过。量值图源和未改文字复用，物相新判断。既有handoff在真实任务下一轮正常执行；若磁盘读图版本变化，需记录实际加载版本与重跑范围，不乱删任务。

失败规划请求/响应、原SI候选已gzip备份issues/phase-handoff/，隔离模型及产物在live/，报告live-summary.json。当前依旧阶段1未送审，无PaperID。完整排障五阶段→精确ID留证清理→同原文件无调试最终五阶段规则不变。图谱标题与五类笼型结构返修条件在case；如新稿已正确不得造改。前三修复b62b3946/4adc30d1/9619fd05已提交，其他共享#232—235源码持续保留，不纳入本任务提交。

## 最新实际版本说明：当前Job加载v8，磁盘已变v9

最新Job仍073d351d-afb7-4ad8-9ab7-c04695f8b6a3。9619fd05后真实网页继续，运行器重新加载了并行#232—235的未提交新图像/反馈代码，实际请求reader_version=scientific-chart-reading-v8（generation10），磁盘随后已v9；不能把当前磁盘版本当作已运行版本。原26/29候选未删，但新图源会使部分签名失效；实际复用/重跑必须据请求账本和新候选统计，不能宣称只补3段。

生产v8正文38条/3未读说明（PrH9两不可辨点+同一限制说明），YH10 mu=.13约287K精度8K，另两个YH9图约267/252及YH10绿色309均约数，原文精确276/253/303/287应由既有整理/科学核对处理。SI图复读已结束，当前重新结构读取正文1—3页；暂无processing_error，仍阶段1无PaperID。最新观察observe-20261110T124630702442Z.json。完整共享工作区补丁只保留本地issues/stream-incomplete/shared-worktree-at-resume.patch.gz，不提交他人源码；实际模型请求本身及原PDF来源均保留。

后续仍须原任务继续完整排障五阶段，再精确ID清理并同原文件最终无调试五阶段。复用信息见下文，原用户Safari17885、超管Chrome1758018018；每次按URL重新枚举账号/任务，勿重复续跑或上传。#224已更新评论6767489951，本轮EOF修复不含并行Responses/原生图片适配。

## 最新：26/29断流误判已修复，正常网页继续同一任务

Task仍d789acceee124022b3257f84780d1156，最新Job 073d351d-afb7-4ad8-9ab7-c04695f8b6a3；Safari隔离17885，account标签被切换过，已新开/account重新核验myth620137018@163.com用户；Chrome1758018018超管待后续使用前重核。所有动作重新按URL枚举，别复用标签号。

旧Job4fbb0c76完成26/29后，SI32—34页响应4367字符在row_index字段名中间结束，SDK finish_reason=None，被旧JSON兜底当完整严格结构错误。原失败a841dc4b…留model-runtime，夹具backend/tests/fixtures/model_stream_incomplete/。9619fd05补ModelIncompleteStreamError（HTTP协议错误），只在上传Chat路径已输出但无正常完成原因时按现有5次恢复；正常stop非法JSON/字段、length/content_filter仍停止，半截绝不补写。用户后来已明确5次上限，原话见224spec，本次不改。

最终原HEAD夹具3失败/4通过；修复独立本次hunk投影56、共享56、四宿主233、12变异、字段契约通过；原失败窗口同模型/同端点/同输入/schema新请求一次成功并严格校验/JSON保存重读，无业务回填。最初全复制llm入口混入并行#233未提交Responses导入导致独立22失败，已单列；正确投影按本次hunk构建，不纳入他人代码。提交仅2生产文件4处小hunk+测试/224/205/Overview/证据。其余#232—235已有大量共享接线（包括llm.py中Responses/能力、原生图像工具/谱/RAG）仍未提交，完整保留，后续检查git状态勿混入。

已真实Safari点击继续：新Job073d351d…，仍原文件/角色/模型、26个完整分段保留。先observe当前状态及实际新job消费，从未完成部分继续；不要重复点击、上传或清理。完整五阶段尚未送审，无PaperID，DB之前按DOI无本轮论文。

本轮仍排障轮，最终必须全部五阶段→留证精确ID清理→同原文件最终无调试五阶段，不能以局部修复结束。图谱标题返修目标High-throughput Study on Rare-earth Clathrate Hydride High-temperature Superconductors；用户指定五类笼型结构，现有目录ID1笼状结构。部分当前提取已识别clathrate，最后草稿若都正确不能故意造改，届时需实事求是审查真实返修项。CeH10@200GPa Tc/DOS按用户确认Fm-3m，声子R-3m独立保留。

前两修复b62b3946保600DPI无损分片、4adc30d1柱边亮度，正文生产v7已38条、YH10蓝~287K±8K、旧199K退出当前来源；SI生产31条，2未读说明是S14 YH9/YH10 DOS未直接给pressure/spacegroup，留空，不自编。正文/完整来源、新重提、固定回放及隔离证据各自保留。运行记录fd38249d已提交。

## 最新：柱边亮度故障已修复，v7正文真实读取已通过，继续SI

同Task d789acceee124022b3257f84780d1156，最新Job 4fbb0c76-4fee-45a9-8936-5ac2d44eebba，Safari17885/Chrome1758018018。先observe实际状态；不要重复上传。4adc30d1修复bar_edge同色像素亮度高于内部样本时被误断：实际YH10 μ*=.13旧模型定位y269正确，程序误停网格为~199K。故障先4失败，修复后独立源码及共享各75项、四宿主233/12变异/字段契约通过。原PDF同失败Tc面板全新模型18条标定及IR保存重读，YH10蓝约287K精度7K；PrH9两未读保留，绿约309±6K与正文303K由既有科学核对处理，不能把约数当精确原值。未回填旧AI答案。

此前b62b3946无损分片已在实际主文三面板及SI完整读图成功；图像超限不再出现。新的发现是像素追踪，不是503。旧Job afd55be5已通过正常网页停止，RQ STOPPED；网页回执超时后重新加载正常读状态收敛paused，未重复操作。现已实际Safari点击继续，生产v7三个新请求均完成且零失败，正文38条、PrH9两真实未读，YH10蓝约287K精度8K已保存到当前IR；旧199K派生来源selected_for_reading=false。当前继续SI13页。v7版本/reader_version已使旧错误覆盖及精读缓存重新读取；原失败和旧来源保留。只提交chart_reading的版本/请求版本两处，其余#232共享600 DPI/区域接线仍未提交并保留。完整证据issues/bar-grid-occlusion/和docs/specs/227-scientific-chart-reading/bar-shading-fix.md。

当前仍阶段1未送审，无正式PaperID，最新DB同DOI无记录。必须继续完整排障五阶段，之后精确ID清理并同原文件最终无调试五阶段；不能局部通过当完成。正文/SI角色与哈希、图谱标题及五类笼型结构返修目标见case，已正确不可人为改坏制造返修。实际草稿和科学依据核验后才能送审。

## 最新：600 DPI图像单图容量已修复，已正常网页续跑

Task仍d789acceee124022b3257f84780d1156，当前Job afd55be5-3113-453b-9098-f9e813c1a668；Safari旧窗口关闭后新隔离窗口17885（account重核myth620137018@163.com用户），Chrome超管1758018018仍保留。每次先重新枚举URL，不能使用旧7839/17122。

旧Job42538417在正文第4页读图被上游503拒收：上下文图5100×6600=33120个32像素块，超过单图30000；精读图未超，非JSON或SI文本超限。5次未输出后paused。用户已明确采用保留600 DPI的重叠无损分片方案。b62b3946仅本任务模块/入口/回归/文档及轻量证据，不提交#232共享实现；#227评论6765877993。分片在归档/预算/缓存前保存原图编号与像素映射，不缩图、不换模型、不改科学契约。

故障回归先失败；独立HEAD投影49、共享相邻75、四宿主233、12变异、字段契约通过。隔离原PDF3面板新模型38有效、PrH9两条真实未读/3上下文，正式标定及IR保存重读通过；Bandit模块缺失未执行，未改依赖。原始失败及完整请求仍在业务model-runtime，隔离证据issues/image-patch-limit/，报告docs/specs/227-scientific-chart-reading/image-patch-limit.md。

真实Safari已点击继续，新Job被Worker消费；实际新生产请求已确认3附件及IMAGE_TILE_MANIFEST，首面板已完成/零失败；不是把隔离结果回填到业务。下一步观察当前Job直到ready/真实阻塞，核对正文/SI、科学字段和来源，再送审→超管两真实返修项拒绝→用户修改重提→通过日志批准→探索YH10及正式库只读核验。当前仍阶段1无PaperID，完整黑盒未完成。排障轮完整五阶段后才按ID留证清理并同原文件重测最终无调试五阶段。

共享#232—235仍在实施，本任务不能把其未提交代码纳入自身提交或写成全部完成；本轮真实验证明确记录运行时共享源码差异。不要改原PDF/科学值、删本轮任务、重复上传、直接API/SQL代办业务。

## 最新：新轮裁剪说明误报已修复并在同任务续跑

当前Task仍d789acceee124022b3257f84780d1156。首Job完成29/29后，因为λ中面板裁剪外的DOS/Tc上下文说明被一律当chart_unresolved，来源覆盖失败。已留证、按#227 FR011修复，未删任务/重上传。

本地e6ca4863：读图v5只读当前目标，notes固定{scope:target|context,reason}，上下文保留在coverage.context_notes但不当失败，真目标/逐点未读仍保留；无结果也无目标未读理由（包括空面板）拒绝。科学表单字段/锁摘要、标定、审核规则及科学核对轮次不变。旧v4响应不改，历史数值回放使用从旧HEAD保存的严格v4schema快照（仅测试，不是生产降级）。71相关及独立投影71、四宿主233、字段契约、12变异、静态编译/Bandit通过。

原PDF隔离真实新读36有效/3上下文/4真实未读（含ScH6新坐标错误）如实记录，不当整图通过。实际Safari17122点击继续，同一Task新Job4e6bcc0e-5f7a-4c96-9a5e-079790a2f079；业务真实v5正文38有效/3上下文，仅PrH9两条真实未读，ScH6实际成功，SI也完成。当前workflow_selection，无错误，下一步结构/分段提取→覆盖/整理/字段审核/谱/引用→用户校对送审。先observe.py核验最新再动作。

本轮已发生调试，是排障轮。必须五阶段通关→完整留证后按精确Task/PaperID清理→同原文件新上传最终无调试完整五阶段→保留最终正式论文。不得本次修复后中途删稿。新轮仍未送审，无正式PaperID；返修目标：用户指定High-throughput Study on Rare-earth Clathrate Hydride High-temperature Superconductors（图谱标题字段），材料structure_families选现有ID1笼状结构（用户确认5类phase均笼型），具体实际原值待草稿，已正确不能造改。

窗口Safari17122，任务URL http://127.0.0.1:5173/upload/tasks/d789acceee124022b3257f84780d1156，account核验myth620137018@163.com；Chrome1758018018 account超管mayuan_mark@163.com。旧7839多个upload页面勿用，URL/tab每次重枚举，operate模块ROOT设本run。本run observe.py及verify_formal.py已能只读新Task，不要用旧02观察器。旧02已备份并精确清理，不恢复。

新问题证据issues/chart-target-scope/，真实失败IR/覆盖/原响应、实际新模型/回放/静态分别保留。#227评论6763486395。应用JSON修复9e58ca05仍有效（已有JSON提示不改字节），结构读取已在真实新轮正常完成过，非仅API探针。大旧tar204MB保留本地不放Git。

## 最新真实状态优先

JSON修复已提交9e58ca05，实际新上传Task d789acceee124022b3257f84780d1156、Job a90b6d55-4966-4377-b8fc-8326ec8af960。文件已由正常Safari拖放组件上传并服务器SHA/大小/角色全部核验，实际scwiki-upload Worker已消费，queue0。不要再attach/再创建上传。新case/active-task.json已更新，observe.py只读新Task；verify_formal.py为本轮冻结只读核验，待有PaperID再用。当前处于paper_info_extraction，无错误，先observe当前状态再操作。

Safari当前本轮隔离窗口17122（不是7839），任务页URL http://127.0.0.1:5173/upload/tasks/d789acceee124022b3257f84780d1156，/account已核验myth620137018@163.com用户，Chrome1758018018 /account超管mayuan_mark@163.com。每次按URL重新枚举，标签会变；旧7839有多个upload页面不是本轮操作窗口，保留不用。

原文件输入Event辅助在新页未被组件接收，业务尚未启动；已改测试helper为正常拖放入口、等待React提交，不改产品。scenario.py添加method可选input/drop，attach_inputs.py目前使用drop。两份文件已正常上传且精确哈希符合，证明真实字节。需要仅提交本测试辅助及实际运行记录，不把此误记产品字段故障。

最终仍必须排障轮五阶段完整→留证按ID清理该轮表单/正式论文/解析→同文件新上传无调试最终轮五阶段→保留最终正式记录。当前只阶段1解析中，没有正式PaperID/送审。用户标题和笼型结构返修条件见case。旧02已清理不能恢复，其证据完整tar本地保留。

# Y-H文献通用流程黑盒

最新用户要求以tests/TestForRealScenario/document-upload-blackbox-workflow.md执行：先完整排障五阶段，再留证按精确ID清理该轮表单/正式论文/解析数据，原文件新上传无调试五阶段通过后才结束，最终轮保留正式论文。旧历史保留current-task要求已由这次新流程更新。

开始前已按明确授权备份并后台仅清理02b23f7c5e524f8ba718f48d92a07f75，paused/无正式PaperID；其余三历史task已不存在不操作。归档previous-task-evidence.tar.gz含5616成员/204038350字节，backup/cleanup manifest及result证明原文件和3篇独立正式论文保留。归档本地保留，不放Git大二进制。

当前尚无新Task，旧02不可恢复。Safari7839的http://127.0.0.1:5173/upload已通过正常组件装入正文+SI真实字节（attach_inputs.py执行完毕），尚未点击开始上传。不要重复attach，先读UI已选列表。Safari/account核验myth620137018@163.com用户；Chrome隔离1758018018 /account核验mayuan_mark@163.com超级管理员。每次交互按实际URL重新枚举（operate模块ROOT设本目录），不沿旧tab索引。

代码JSON请求修复已验证但正在准备提交：backend/rag/llm.py只给缺JSON提示的系统消息补句，已有合规消息字节不变；public入口在预算/归档/缓存前处理，transport幂等，json_schema/原生工具/本地固定字段校验均保留。真实旧503请求仅加JSON、同模型/输入/工具，serverLLM2/gpt-6.1-sol首尝试返回合法read_original_page native调用；未执行工具，不是整篇通过。新5回归及后端66通过/1真实隔离Redis条件跳过，四宿主233、字段契约、12变异通过。暂停测试组合导入顺序故障HEAD同组合复现，夹具显式绑定同存储已修正。未改变5次暂停规则。

依赖安全扫描非全通过：锁/清单无变更，前端6项（4低2中），本机后端14包108条通告；Bandit1个旧LOW assert和HEAD相同。无依赖升级；安全审查security-review.json。官方文档HTTP403未获取，不伪称已读；官方SDK实际类型和实际请求序列化已检。

用户明确图谱标题返修目标：High-throughput Study on Rare-earth Clathrate Hydride High-temperature Superconductors（仅knowledge_graph_title，不是文献title）。材料返修依据用户最新确认：Fm-3m YH10/CeH10/LaH10、P63/mmc YH9/CeH9都是笼型结构，用现有structure_families。新草稿原值正确不能造改，需选具体真实待改状态。CeH10@200GPa Tc/DOS采用Fm-3m已由用户确认，R-3m声子来源独立保留。未授权添加新科学键。

输入case.json仅本轮数据，正文/SI原路径在../20261106-peng2017/sources，哈希角色不变，DOI10.1103/PhysRevLett.119.107001、检索YH10。当前case记录phases全部未执行。下一步完成本轮源码/证据自动多行本地提交（不push）→核验当前上传文件/邮箱/模型→网页开始上传→记录新Task/Job/角色哈希→完整五阶段，故障留证调查修复后当前步骤续跑，不能每修一次删稿。当前排障轮完整通过后才跨轮清理与最后新上传无调试。

分支mayuan，写入/提交前核验。当前工作区只有本轮rag/llm.py、JSON新测试、暂停测试夹具及对应205/224/Overview/报告文档；不要纳入不属于本任务的后续共享改动。运行代码需Python=/Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python、PYTHONPATH=.，load_dotenv但不读/记录任何凭据。模型和所有业务通过真实Safari/Chrome，不API/SQL代办；只读调查和明确清理例外允许。旧run的observe.py仍指02，不要直接用它观察新任务。

// 只读说明：当前代码事实与讨论方案分开，不连接真实任务或模型。
(() => {
  'use strict';
  const root = document.querySelector('#review-audit');
  if (!root) return;
  const modules = [
    {
      id:'reading', label:'解析与提取', owner:'01 去中心化上传 / 解析与草稿',
      title:'OCR 读字、模型读懂、依据定位是不同工作',
      summary:'先给模型带身份的原文与上下文。归纳允许换一种说法，支撑材料仍应回到这篇论文。',
      example:'论文不必出现 calculation 这个数据库枚举词。模型可根据研究目的和结果归为计算类；依据应指向相应原文。stabilizes 与 PDF 中 stabi- lizes 的差异说明文字表示不一致，不能单凭这一点归咎 OCR 或模型。',
      cause:'当前提取阶段已经使用文档身份、候选验证和部分工具补查；后期字段依据没有完整复用同一定位结果。',
      change:'建议模型首次阅读时就选择文件、页／块及支撑内容，同时保存与当前值绑定的说明。后续从相同证据身份读取上下文，减少重新手写引句与重新定位。',
      limit:'22项定位失败并非全是模型推断：前轮快照12项为归纳字段、10项为事实／数值字段。归纳也不能省略支撑依据；不是所有定位失败都能归因断词。',
      refs:[['#120 字段分级与归纳要求','../../specs/120-upload-llm-extraction-quality/spec.md'],['#128 理论类型的全文归纳','../../specs/128-fulltext-theoretical-subtype/spec.md'],['文档工具与预算','../../specs/114-multimodal-pdf-upload-agent/contracts/agent-tools.md']],
      current:[
        ['解析工具','读取正文及补充材料','文字、表格、页和块','complementary_pdf 组合工具形成 Document IR（带文件与区域身份的中间文档）。这一步成功不代表科学结论已通过。'],
        ['LLM','按窗口提取候选','保留材料、条件与依据','_read_chunk 让模型提取候选；程序校验值的格式及依据身份。'],
        ['程序 / 必要 LLM','早期候选失败才补查','文档工具的现有入口','已有 repair_claims 可让模型选择读页、搜索、读区域等工具，有行动及重试预算，只给同值候选补可靠依据。'],
        ['程序','交给后期整理与核对','后期失败没有接回此处','CaH6 当前保留的早期7条 Claim 为 validated，未见 agent_calls.json。后来的字段引句失败发生在另一阶段；不能据此声称这个补查循环已经处理过它们。',true]
      ],
      proposed:[
        ['建议 / LLM','首次阅读就选依据身份','同时理解并保留上下文','让模型读取来源时返回真实来源编号及相关范围，程序展开成文件、页／块和原始内容，不让模型凭记忆重写引句。'],
        ['建议 / 程序','以原始来源建立绑定','值、条件、理由与位置一起保存','确定同一材料、压力、方法和当前来源版本；保留原文件与原始文本，不通过改写原件消除差异。'],
        ['建议 / 程序','后续复用同一证据','核实身份，不重复猜位置','已核实的来源绑定可复用；归纳值按语义核对，不能要求当前归纳文字逐字出现在论文。'],
        ['建议 / 程序 + LLM','缺口才定向补查','仍未解决再交人','首次就建立定位，失败补查作为恢复路径；不能保证所有模型一次成功，也不为得到通过无限询问。']
      ]
    },
    {
      id:'judgment', label:'字段核对', owner:'01 去中心化上传 / 字段核对与科学整理',
      title:'能自动纠正的错值，与模型暂时没完成工作，要分开',
      summary:'不支持不一定能推导唯一正确答案；不确定和缺少依据，也不一定马上需要人。',
      example:'若AI草稿把150 GPa这一行的Tc错填为200 GPa那一行，而原表能唯一确定正确对应，建议在交给用户前纠正并核实新值。若论文有两种方法或多个μ*，不能只因旧值不支持就任选一个替换。CaH6那12项已有值，是后续核对批次出现异常。',
      cause:'evaluate_batch 要求覆盖全部输入键；缺 results 数组或漏键可抛 ValueError。generate_upload_suggestions 捕获批次异常后统一记录 unchecked；现有日志只记异常类型，无法确定该次具体是哪一处。',
      change:'建议解析自检对系统自己的草稿做有依据且唯一的纠错，并保存改前、改后及原因；不能覆盖用户修改或已确认值。对暂时缺证、歧义先查上下文；对响应缺键只补失败项，保存具体错误、已有有效项和有限重试结果。',
      limit:'发现旧值错误不等于知道新值。La–Sc–H 的历史人工确认和正式提交修复不是同源码、同模型、同输入的对照实验；不能推导“CaH6一定是模型退步”。该次 ValueError 的具体分支仍未证实。',
      refs:[['#120 模型提炼与纠错','../../specs/120-upload-llm-extraction-quality/spec.md'],['#176 固定表单科学整理','../../specs/176-scientific-form-filling/spec.md'],['La–Sc–H 人工状态修正边界','../../specs/147-two-stage-field-review/approval-submit-validation.md']],
      current:[
        ['LLM','字段批 × 来源窗口','不是每字段固定一次调用','generate_upload_suggestions 分批调用 evaluate_batch，返回字段状态、理由、依据和候选；需要归纳时按科学语义判断。'],
        ['程序','检查模型返回是否完整','缺数组、漏键可抛异常','没有 results 列表可抛 invalid result schema；结果键不齐可抛 incomplete result schema。底层已有部分网络／JSON重试，但不会因此补齐这里漏掉的业务字段。'],
        ['当前断点 / 程序','批次异常统一记未完成','值保留，具体异常信息不足','CaH6 worker只保留 batch=4 type=ValueError；数据库12项显示模型技术失败。不能由此认定12个值全错，也不能精确归因漏键还是其他 ValueError。',true],
        ['程序','合并结果、复核条件','部分条件会再次调用模型','聚合相关来源；必要计算条件按最终值再检查适用范围。当前通用补空不覆盖非空值；单字段核对候选仍须主动应用，并非所有明确错值都自动纠正。']
      ],
      proposed:[
        ['建议 / LLM + 程序','在系统草稿内自检纠错','确认唯一依据和对应条件','只对系统尚未交给用户的草稿，按原表或明确上下文纠正有唯一答案的错误，记录变化并核实最终值。'],
        ['建议 / LLM + 工具','歧义与缺证先补查','先尽系统职责','比较方法、μ*、压力、正文与SI。没有查到不等于论文没有；技术异常先恢复，不能当作科学歧义。'],
        ['建议 / 程序','保留成功项，补失败项','给出可追踪错误与有限重试','分别记录返回结构错误、缺哪些键、来源不可读和模型判断歧义，避免一个键缺失抹掉整个批次的有效工作。'],
        ['建议 / 用户','仅处理系统仍无法确定的项','在所属字段侧栏决定','补查后仍有相互矛盾依据、范围歧义或无可靠支撑时，标清疑问与已读来源，交用户判断。有效最终值不在提交时无理由重核。']
      ]
    },
    {
      id:'location', label:'来源定位', owner:'01 去中心化上传 / 字段来源与原 PDF 复核',
      title:'断点在“用第二套文字匹配撤回模型通过”',
      summary:'验证证据真实性有必要；把连续引句搜不到直接变成审核未完成，而且没有恢复路径，这个实现不合理。',
      example:'引句是 stabilizes above pressure 150 GPa.，原 PDF 文字层是 stabi- lizes above pressure 150 GPa.。模型已认同150 GPa，程序没有处理该断词，随后把 supported 改成 unchecked。这不是模型没看懂压力。',
      cause:'correct_pdf_source_pages 对适用PDF结果读取文字层、整理空白并 page.count；没有唯一命中或块来源时，原supported会变为unchecked。它既不按归纳字段分流，也不安排LLM阅读该页上下文继续核实。',
      change:'建议把来源绑定提前到首次模型阅读，复用经核实的文件／页／块；显示高亮失败与科学结论分开。依据身份本身确实无效时保留待解决状态，定向调用现有工具和模型补查，成功才发布当前结果。',
      limit:'不赞成删除全部PDF依据检查，也不能凭模型说已看过就通过。高亮裁剪失败不应自动否定可靠依据；文件不对、依据确实找不到或适用范围冲突则必须处理。该能力接线是建议，本页没有修复后台。',
      refs:[['#109 来源真实性与侧栏','../../specs/109-field-evidence-and-ai-suggestions/spec.md'],['#114 文档依据契约','../../specs/114-multimodal-pdf-upload-agent/contracts/claim-evidence.md'],['当前原PDF检查节点','#pdf']],
      current:[
        ['LLM / 程序','前面已给出支持意见','基于解析文本及归纳理由','checked_result 先处理模型状态与当前来源；归纳文字不必等于原文，理由及支撑仍需校验。'],
        ['当前断点 / 程序','再用原PDF文字层匹配','不是新的模型语义核对','current_pdf_results 又用 PyMuPDF 查连续引句；页面断词和OCR排版差异可能与前面使用的文本不同。此处有有效块来源的保留分支，但这些失败引句未带块身份。',true],
        ['当前断点 / 程序','定位失败就撤回支持','supported → unchecked','当原结果支持、未找到有效位置且依据全属PDF，代码自动保留 model_opinion 再改状态。原意是阻止虚构出处；这里把表示差异和依据无效混合了。',true],
        ['当前断点 / 提交流程','没有定向补查便返回','稍后提交仍要求通过','这个函数没有重读上下文或调用LLM的分支。页面可以保留提取值与历史模型意见，但没有可提交资格，不等于“根本没结果”。',true]
      ],
      proposed:[
        ['建议 / 首次模型阅读','内容判断同时选择依据','先定位，不等最终失败','优先让模型引用本次输入的来源编号，程序展开原文、页／块并核实身份。这里是源头接线；失败后的补查只是恢复。'],
        ['建议 / 程序','复用可靠来源身份','显示定位与科学含义分开','来源绑定有效时不因高亮渲染或另一版文字搜索失败撤回科学意见；检查文件哈希、真实块及当前适用范围。'],
        ['建议 / 程序 + LLM','有缺口就定向查原页','修排版，读上下文，找支撑','程序先处理可确定的排版差异，再把问题、对应页和上下文交给模型及现有文档工具。程序核实返回位置，没有凭模型承诺直接放行。'],
        ['建议 / 程序','发布最终结果或明确疑问','避免隐藏的未完成状态','事实与归纳各按其依据规则产生有效资格；仍无法确定的字段在侧栏展示具体原因、补查情况和处理入口。']
      ]
    },
    {
      id:'submission', label:'提交与派生', owner:'01 提交送审 / 02 论文审核与批准',
      title:'最后是收齐结果，不能用它替代前面的纠错与补查',
      summary:'通过结果按版本复用；派生字段跟随真正的输入更新。技术未完成不能被人工修改筛选条件遗落。',
      example:'Im-3m可查得229号和立方晶系，CaH6可数出2种元素。但仍需确认这些输入属于论文当前状态。前轮9项派生中4项跟随定位失败，5项跟随批次技术异常，不是9项都因PDF文字定位失败。',
      cause:'提交的模型目标目前只选需核对的人工修改；最终gate却仍要求适用字段有有效通过。未修改但因系统故障未完成的字段可能被跳过处理而继续阻塞。required表示必须有有效结论，不表示当前还没审核。',
      change:'建议解析阶段先完成自检闭环，未解决项明确进入对应字段侧栏；技术恢复有明确入口。提交直接复用当前有效结果，只处理真实变化或明确需恢复的项；输入确认后自动更新其确定性派生。',
      limit:'保存草稿、字段通过、提交pending和管理员approved是不同动作。保留已提取值与部分结果不代表全链完成；未完成也不等于系统没有展示任何内容。不能通过把全部unchecked一律设supported来收尾。',
      refs:[['#147 三个模型入口与复用','../../specs/147-two-stage-field-review/review-flow.md'],['#169 有效通过不重复请求模型','../../specs/169-field-ai-candidates/spec.md'],['批准前检查程序图','pdf-approval-check-flow.html']],
      current:[
        ['程序','读取已保存的字段结果','按内容、来源与范围校验版本','有效同版本通过直接复用；不为已经通过的字段重新归纳、生成或审核。'],
        ['当前断点 / 程序','模型只处理必要人工修改','系统遗留未完成可能被跳过','enqueue_review 的submit筛选附加 human_modified。没有人工修改不是不能提交的业务原因，只解释了为什么此分支没有安排补处理。',true],
        ['程序','空间群与元素计数跟随输入','确认输入后才承认派生','apply_derived 由空间群符号派生编号和晶系，由化学式派生元素种类数；输入未通过会带来连带等待。'],
        ['程序 / 数据库','汇总资格，才提交事务','未完成与未通过都会拦截','gate 的最后检查不再解决科学问题。字段都合格后还须成功保存pending论文或执行管理员批准事务。']
      ],
      proposed:[
        ['建议 / 解析与恢复','先把系统工作做完整','留下可解释的完成或待处理项','技术失败、定位缺口和科学歧义分别处置；不能以“用户没修改”为由让系统遗留问题失去处理路径。'],
        ['建议 / 程序','更新真实依赖的派生结果','不扩大成全表重新核对','来源输入通过后重新确认对应派生结果，其他无关字段保持；不要求用户重复审核确定性换算。'],
        ['建议 / 提交程序','复用有效结果，检查变化','不是固定再读一遍PDF','已完成自检且未变化的有效值直接复用；用户修改、依据或相关范围变化才按实际范围核对。'],
        ['建议 / 数据库','收齐有效结果后保存','整篇批准仍独立','最终程序检查权限、版本、格式与事务，保留原有数据完整性；不再以不透明的额外文字匹配隐藏撤回结果。']
      ]
    },
    {
      id:'presentation', label:'字段侧栏', owner:'01 上传校对 / 02 审核表单的共用字段侧栏',
      title:'结果和疑问落在字段侧栏；导航不等于另一套审核',
      summary:'当前红色谓词排除unchecked，造成阻断与可见提示脱节。本次用户要求取消独立待处理导航，图中把它明确列为新调整。',
      example:'字段可已有150 GPa和“模型认为一致”的历史意见，却因定位待解决而失去通过资格。用户需要在压力字段侧栏直接看到这个差别，不能只在提交时收到“尚未通过审核”。',
      cause:'EvidenceFieldMarkers 的问题谓词排除 pending_review、stale、unchecked。独立待处理导航源码确实存在，#109 source-review-presentation 也写过保留它；不能说它从未有文档依据。',
      change:'按本次明确意见，建议移除独立待处理按钮及弹窗，字段标记定位侧栏。侧栏直接列当前值、依据、模型意见、技术进度、尚存疑问与可执行动作，区分内容不支持与系统未完成。',
      limit:'本次没有删除真实产品的按钮或修改标红规则；仅更新图示。历史Spec保留旧约束作为记录，本次取舍不能写成旧需求从未存在。系统有部分结果，不等于它已完成核对或该值已可提交。',
      refs:[['#109 原侧栏规则与独立导航','../../specs/109-field-evidence-and-ai-suggestions/source-review-presentation.md'],['#147 人工决定与结果状态','../../specs/147-two-stage-field-review/approval-submit-consistency.md']],
      current:[
        ['程序','读取摘要与字段详情','已提取值和部分判断可显示','草稿ready只说明可以校对。字段详情仍可能是科学通过、未通过、技术未完成或结果过期。'],
        ['当前断点 / 界面','红色标记排除未完成项','无红色不保证能提交','evidenceProblem只计特定科学问题状态；unchecked等阻断项没有进入同一标记范围，造成用户看到的状态不完整。',true],
        ['当前界面','独立按钮打开导航弹窗','条目继续打开字段侧栏','这不是另一套科学审核，但确实是一层额外导航。#109历史展示Spec写明保留；本次用户明确提出不要它。'],
        ['用户','进入字段侧栏查看','处理入口已有，原因仍需清楚','来源、AI理由、人工决定和历史都在侧栏。不能用技术细分把需要处理的字段表现为已无问题。']
      ],
      proposed:[
        ['建议 / 程序','给每字段完整处理结果','包括真正未完成的原因','既保留模型科学意见，也记录依据状态、技术错误及补查经过，让人知道是值有问题还是系统没做完。'],
        ['建议 / 界面','问题直接标到对应字段','未完成也应有清楚提示','不把所有失败称为科学错误；如果需要用户介入，字段必须有可见提示与明确原因。'],
        ['建议 / 产品调整','去掉独立待处理导航','沿字段进入同一侧栏','本次要求的界面删减，尚未落地。不新增顶部问题内容堆积；无法定位字段时须修正稳定身份和入口。'],
        ['建议 / 用户','只判断仍不能自动解决的项','人工处理后复用有效结果','用户可以认可、拒绝或补充依据；系统能唯一纠正的自有草稿错误先自动处理，已经完成且未变化的值不反复要求人判断。']
      ]
    }
  ];
  const byId = new Map(modules.map(module => [module.id,module]));
  let mode = 'current', selected = 'location';
  const get = id => document.getElementById(id);
  const moduleButtons = new Map();
  function setText(id,value) { get(id).textContent = value; }
  function selectStep(index,buttons) {
    const module = byId.get(selected), step = module[mode][index];
    buttons.forEach((button,i) => button.setAttribute('aria-pressed',String(i===index)));
    setText('audit-step-owner',step[0]);setText('audit-step-title',step[1]);setText('audit-step-detail',step[3]);
  }
  function render() {
    const module = byId.get(selected);
    root.dataset.mode=mode;
    for (const [id,button] of moduleButtons) button.setAttribute('aria-pressed',String(id===selected));
    document.querySelectorAll('[data-audit-mode]').forEach(button => {
      const active=button.dataset.auditMode===mode;
      button.setAttribute('aria-selected',String(active));button.tabIndex=active?0:-1;
    });
    get('audit-panel').setAttribute('aria-labelledby',`audit-${mode}-tab`);
    setText('audit-module-owner',module.owner);setText('audit-module-title',module.title);
    setText('audit-module-summary',module.summary);setText('audit-example',module.example);
    setText('audit-root',module.cause);setText('audit-change',module.change);setText('audit-limit',module.limit);
    setText('audit-mode-notice',mode==='current'?'当前实现：红色节点表示已查到的断点；点击步骤可查看具体行为。':'建议流程：本次仅讨论与绘图，尚未实施；不表示后台已经具有这些能力。');
    const buttons=[];
    get('audit-flow').replaceChildren(...module[mode].map((step,index) => {
      const item=document.createElement('li'),button=document.createElement('button');
      button.type='button';button.className=step[4]?'audit-problem':'';
      button.setAttribute('aria-controls','audit-step-title audit-step-detail');
      for (const [tag,text] of [['small',step[0]],['strong',step[1]],['span',step[2]]]) {
        const child=document.createElement(tag);child.textContent=text;button.append(child);
      }
      buttons.push(button);button.addEventListener('click',()=>selectStep(index,buttons));
      item.append(button);return item;
    }));
    get('audit-references').replaceChildren(...module.refs.map(([label,href]) => {
      const item=document.createElement('li'),link=document.createElement('a');
      link.href=href;link.textContent=label;item.append(link);return item;
    }));
    selectStep(0,buttons);
  }
  modules.forEach((module,index) => {
    const button=document.createElement('button');button.type='button';button.dataset.auditModule=module.id;
    const number=document.createElement('small');number.textContent=`模块 ${String(index+1).padStart(2,'0')}`;
    const label=document.createElement('strong');label.textContent=module.label;button.append(number,label);
    button.addEventListener('click',()=>{selected=module.id;render()});
    moduleButtons.set(module.id,button);get('audit-modules').append(button);
  });
  document.querySelectorAll('[data-audit-mode]').forEach(button => {
    button.addEventListener('click',()=>{mode=button.dataset.auditMode;render()});
    button.addEventListener('keydown',event => {
      if (!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
      event.preventDefault();
      mode=event.key==='Home'?'current':event.key==='End'?'proposed':mode==='current'?'proposed':'current';
      render();get(`audit-${mode}-tab`).focus();
    });
  });
  render();
})();

// 只读说明：当前代码事实与讨论方案分开，不连接真实任务或模型。
(() => {
  'use strict';
  const root = document.querySelector('#review-audit');
  if (!root) return;
  const modules = [
  {
    "id": "reading",
    "label": "解析与提取",
    "owner": "01 去中心化上传 / 02 审核共享流程",
    "title": "从已核验原文形成字段结果",
    "summary": "事实和归纳保留依据；使用来源编号，避免模型重写引句。",
    "example": "CaH6的stabilizes与PDF文字层stabi- lizes不同；额外复查已删除，提取来源验证保留。",
    "cause": "当前实现见各步骤；旧行为只在历史对照中展示。",
    "change": "#184、#188、#190、#191已完成本地实现。#192是独立目标，不属于本次交付。",
    "limit": "旧草稿状态未批量改写，未代替提交或批准；未推送部署。工具预算和科学门禁继续保留。",
    "refs": [
      [
        "当前字段自动处理说明",
        "field-review-automation.md"
      ],
      [
        "实现验证",
        "../../specs/184-simplify-field-review/validation.md"
      ]
    ],
    "current": [
      [
        "解析工具",
        "读取正文与附件",
        "保留文件、页／块身份",
        "复用经哈希核实的文字，不复用旧字段答案冒充重新提取。"
      ],
      [
        "LLM",
        "提取及归纳",
        "科学内容按语义判断",
        "读取上下文；归纳文字不要求逐字出现在论文。"
      ],
      [
        "程序",
        "绑定真实来源引用",
        "不补写科学值",
        "已知文件／页／块身份可补齐冗余quote_id，未知块仍拒绝。"
      ],
      [
        "程序 / LLM",
        "进入自检与补查",
        "不是固定三次调用",
        "按字段批和来源窗口执行；通过结果不重复补查。"
      ]
    ],
    "proposed": [
      [
        "旧流程",
        "读取原文",
        "解析器与模型",
        "读取、提取与候选验证。"
      ],
      [
        "旧流程",
        "早期候选补证",
        "仅部分IR候选",
        "部分候选失败才使用工具。"
      ],
      [
        "旧流程",
        "后期字段核对",
        "另一套引句表示",
        "又生成文字引句。"
      ],
      [
        "旧断点",
        "再次原PDF匹配",
        "已被184删除",
        "文字表示不同可撤回通过。",
        true
      ]
    ]
  },
  {
    "id": "judgment",
    "label": "字段核对",
    "owner": "01 去中心化上传 / 02 审核共享流程",
    "title": "先纠正系统自己的唯一错误",
    "summary": "候选有来源、类型正确且答案唯一，最终值重新核实后才应用。",
    "example": "本轮CaH6隔离副本设为二维，系统依据原文纠正为三维并保存重读；真实草稿未改。",
    "cause": "当前实现见各步骤；旧行为只在历史对照中展示。",
    "change": "#184、#188、#190、#191已完成本地实现。#192是独立目标，不属于本次交付。",
    "limit": "旧草稿状态未批量改写，未代替提交或批准；未推送部署。工具预算和科学门禁继续保留。",
    "refs": [
      [
        "当前字段自动处理说明",
        "field-review-automation.md"
      ],
      [
        "实现验证",
        "../../specs/188-automatic-extraction-correction/validation.md"
      ]
    ],
    "current": [
      [
        "LLM",
        "识别错误与唯一候选",
        "替代仅补空限制",
        "旧值错误不等于候选正确；当前条件必须唯一对应。"
      ],
      [
        "程序",
        "检查来源类型与身份",
        "严格绑定当前字段",
        "完整字段路径仅映射同一字段的合法相对路径，不能跨字段写入。"
      ],
      [
        "LLM / 程序",
        "核实最终值后应用",
        "不伪造人工审核",
        "在副本应用并重新核对，通过才写入，失败保留原值。"
      ],
      [
        "程序",
        "保护人工内容与依赖",
        "只保存最终有效结果",
        "人工改过或确认过不自动覆盖；相关范围变化不继承旧资格。"
      ]
    ],
    "proposed": [
      [
        "旧流程",
        "只核对旧值",
        "候选限补空",
        "非空错误只有失败意见。"
      ],
      [
        "旧断点",
        "有效候选被丢弃",
        "完整与相对路径不一致",
        "程序丢弃同字段候选。",
        true
      ],
      [
        "旧流程",
        "用户逐项处理",
        "系统尚未自纠",
        "可解决的问题也交人。"
      ],
      [
        "旧断点",
        "提交才发现未解决",
        "缺少自纠闭环",
        "没有最终值重新核实。",
        true
      ]
    ]
  },
  {
    "id": "location",
    "label": "来源定位",
    "owner": "01 去中心化上传 / 02 审核共享流程",
    "title": "额外 PDF 引句复查已删除",
    "summary": "提取验证、模型科学判断、首页题录核验和按需预览保留。",
    "example": "该层已删除，不等于取消全部来源校验；伪造提取引句仍拒绝，首页题录回归通过。",
    "cause": "当前实现见各步骤；旧行为只在历史对照中展示。",
    "change": "#184、#188、#190、#191已完成本地实现。#192是独立目标，不属于本次交付。",
    "limit": "旧草稿状态未批量改写，未代替提交或批准；未推送部署。工具预算和科学门禁继续保留。",
    "refs": [
      [
        "当前字段自动处理说明",
        "field-review-automation.md"
      ],
      [
        "实现验证",
        "../../specs/184-simplify-field-review/validation.md"
      ]
    ],
    "current": [
      [
        "LLM / 程序",
        "按当前来源判断内容",
        "服务器编号展开原文",
        "事实与归纳仍按科学含义核对，虚构出处不能通过。"
      ],
      [
        "已删除",
        "不再额外扫描PDF引句",
        "没有改名重建",
        "删除实现和调用，不以连续文字搜索撤回supported。"
      ],
      [
        "保留",
        "标题作者首页核验",
        "不扫描其他字段",
        "直接调用pdf_front_matter，已批准历史不批量改写。"
      ],
      [
        "程序",
        "按版本保存及复用",
        "真实失败仍阻断",
        "权限、版本、来源与决定继续检查。"
      ]
    ],
    "proposed": [
      [
        "旧流程",
        "模型认为通过",
        "有原文和理由",
        "已经给出支持。"
      ],
      [
        "旧断点",
        "再扫PDF文字层",
        "连续匹配",
        "排版差异可导致失配。",
        true
      ],
      [
        "旧断点",
        "撤回通过",
        "变为unchecked",
        "不等于科学不通过。",
        true
      ],
      [
        "旧断点",
        "没有补查便返回",
        "提交仍要求通过",
        "没有红色却不能提交。",
        true
      ]
    ]
  },
  {
    "id": "submission",
    "label": "提交与派生",
    "owner": "01 去中心化上传 / 02 审核共享流程",
    "title": "复用有效结果，必要项才核对",
    "summary": "已有科学不通过不因补查技术异常被抹去，派生项仍跟随输入。",
    "example": "Im-3m确认后可派生229及立方晶系；历史43项不是本次被批量修正。",
    "cause": "当前实现见各步骤；旧行为只在历史对照中展示。",
    "change": "#184、#188、#190、#191已完成本地实现。#192是独立目标，不属于本次交付。",
    "limit": "旧草稿状态未批量改写，未代替提交或批准；未推送部署。工具预算和科学门禁继续保留。",
    "refs": [
      [
        "当前字段自动处理说明",
        "field-review-automation.md"
      ],
      [
        "实现验证",
        "../../specs/184-simplify-field-review/validation.md"
      ]
    ],
    "current": [
      [
        "程序",
        "检查权限格式版本",
        "权限不由模型判断",
        "检查可操作性、格式及当前内容和来源版本。"
      ],
      [
        "程序",
        "复用同版本通过",
        "零重复模型请求",
        "内容、依据、范围未变化时直接沿用。"
      ],
      [
        "LLM / 工具",
        "处理必要未解项",
        "只核对实际目标",
        "必要修改和主动核对可补查；背景不扩成目标。"
      ],
      [
        "程序 / 数据库",
        "汇总后保存",
        "批准仍独立",
        "未完成不提交；旧草稿不自动授予通过。"
      ]
    ],
    "proposed": [
      [
        "旧流程",
        "读取结果",
        "按版本判断",
        "有效结果可复用。"
      ],
      [
        "旧流程",
        "必要修改调用模型",
        "仅人工修改",
        "系统遗留未完成可能被跳过。"
      ],
      [
        "旧流程",
        "派生项跟随输入",
        "不另造依据",
        "等待输入核验。"
      ],
      [
        "旧断点",
        "统一阻断提示",
        "原因展示不足",
        "对应问题不完整。",
        true
      ]
    ]
  },
  {
    "id": "presentation",
    "label": "字段侧栏",
    "owner": "01 去中心化上传 / 02 审核共享流程",
    "title": "四类状态直接进入所属侧栏",
    "summary": "主表单只留简短状态，完整原因与恢复操作在对应侧栏。",
    "example": "四类完整宿主和Chromium路由验证：技术失败字段可见，进入自身侧栏不产生模型任务。",
    "cause": "当前实现见各步骤；旧行为只在历史对照中展示。",
    "change": "#184、#188、#190、#191已完成本地实现。#192是独立目标，不属于本次交付。",
    "limit": "旧草稿状态未批量改写，未代替提交或批准；未推送部署。工具预算和科学门禁继续保留。",
    "refs": [
      [
        "当前字段自动处理说明",
        "field-review-automation.md"
      ],
      [
        "实现验证",
        "../../specs/191-field-sidebar-status/validation.md"
      ]
    ],
    "current": [
      [
        "界面",
        "区分四类状态",
        "通过、处理中、待核对、失败",
        "实际执行才是处理中，pending_review不是正在运行。"
      ],
      [
        "界面",
        "标到对应字段",
        "无独立待处理导航",
        "删除按钮与弹窗，旧未匹配字段保留紧凑可达入口。"
      ],
      [
        "侧栏",
        "解释疑问或技术故障",
        "已有版本意见有标识",
        "失败给重试指引，只读不引导无权限操作。"
      ],
      [
        "界面 / 程序",
        "有效通过后复用",
        "不靠颜色改变资格",
        "通过不重复确认；修改后仍有待核对提示，不在输入时调用模型。"
      ]
    ],
    "proposed": [
      [
        "旧流程",
        "读取摘要",
        "可能含unchecked",
        "未完成仍可能有值。"
      ],
      [
        "旧断点",
        "排除未完成标记",
        "提示阻断脱节",
        "看似正常却不能提交。",
        true
      ],
      [
        "旧导航",
        "打开待处理弹窗",
        "额外选择",
        "再进入字段侧栏。"
      ],
      [
        "旧流程",
        "笼统待确认",
        "技术原因遮住",
        "没有清楚恢复说明。"
      ]
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
    setText('audit-mode-notice',mode==='current'?'当前实现：点击步骤查看职责与边界；旧断点仅在历史对照中展示。':'实施前流程：仅作历史对照，不表示当前行为。');
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

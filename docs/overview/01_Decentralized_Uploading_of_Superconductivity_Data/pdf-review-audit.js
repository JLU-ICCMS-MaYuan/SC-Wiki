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
    "change": "#194统一模型核对与有效复用；#195同步只读预览，均已本地实现和范围验证。",
    "limit": "原用户草稿保留，不代审或批准；未推送部署。实际验证范围见本地验收。",
    "refs": [
      [
        "当前实现与职责",
        "field-review-automation.md"
      ],
      [
        "统一核对验收",
        "../../specs/194-unified-model-review/spec.md"
      ],
      [
        "预览同步验收",
        "../../specs/195-parsing-preview-sync/spec.md"
      ]
    ],
    "current": [
      [
        "解析工具",
        "读取正文及附件",
        "保留来源与版本",
        "初次提取和科学整理保留原有职责。"
      ],
      [
        "模型",
        "提取和整理",
        "字段及必要上下文",
        "不能将阶段框数理解成固定模型请求次数。"
      ],
      [
        "程序",
        "发布只读阶段快照",
        "题录与材料分区",
        "已有内容及时展示，题录空列表不清空科学数据。"
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
    "summary": "同一模型流程完成查证、补查及唯一自纠，按最终值保存。",
    "example": "本轮CaH6隔离副本设为二维，系统依据原文纠正为三维并保存重读；真实草稿未改。",
    "cause": "当前实现见各步骤；旧行为只在历史对照中展示。",
    "change": "#194统一模型核对与有效复用；#195同步只读预览，均已本地实现和范围验证。",
    "limit": "原用户草稿保留，不代审或批准；未推送部署。实际验证范围见本地验收。",
    "refs": [
      [
        "当前实现与职责",
        "field-review-automation.md"
      ],
      [
        "统一核对验收",
        "../../specs/194-unified-model-review/spec.md"
      ],
      [
        "预览同步验收",
        "../../specs/195-parsing-preview-sync/spec.md"
      ]
    ],
    "current": [
      [
        "程序",
        "复用有效结果并分批",
        "保护人工内容",
        "同一内容、依据和范围直接复用，不重复发模型请求。"
      ],
      [
        "模型",
        "统一查证与自纠",
        "定位、值和适用关系",
        "模型自行补查和核实最终值，真实分歧才交人。"
      ],
      [
        "程序",
        "按最终版本保存",
        "逐批保留成功项",
        "只校验身份、类型、权限和版本，处理失败不伪装成科学问题。"
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
    "example": "CaH6的0 . 0 3与0.03 Å^-1由模型结合原始SI核实；读取身份和来源版本仍由程序绑定。",
    "cause": "当前实现见各步骤；旧行为只在历史对照中展示。",
    "change": "#194统一模型核对与有效复用；#195同步只读预览，均已本地实现和范围验证。",
    "limit": "原用户草稿保留，不代审或批准；未推送部署。实际验证范围见本地验收。",
    "refs": [
      [
        "当前实现与职责",
        "field-review-automation.md"
      ],
      [
        "统一核对验收",
        "../../specs/194-unified-model-review/spec.md"
      ],
      [
        "预览同步验收",
        "../../specs/195-parsing-preview-sync/spec.md"
      ]
    ],
    "current": [
      [
        "模型",
        "选择来源与定位",
        "当前正文和附件",
        "文件、块或页位置有问题时，模型借助工具重新定位。"
      ],
      [
        "程序",
        "返回实际读取资料",
        "有限只读工具",
        "只接受本任务可读来源身份，不按文本写法重新裁决科学支持。"
      ],
      [
        "模型",
        "结合原文或原页查证",
        "保留真实出处",
        "同形与否不决定科学真假，不能捏造未读取原文。"
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
    "change": "#194统一模型核对与有效复用；#195同步只读预览，均已本地实现和范围验证。",
    "limit": "原用户草稿保留，不代审或批准；未推送部署。实际验证范围见本地验收。",
    "refs": [
      [
        "当前实现与职责",
        "field-review-automation.md"
      ],
      [
        "统一核对验收",
        "../../specs/194-unified-model-review/spec.md"
      ],
      [
        "预览同步验收",
        "../../specs/195-parsing-preview-sync/spec.md"
      ]
    ],
    "current": [
      [
        "程序",
        "检查权限、格式和版本",
        "最终批准独立",
        "有效同版本结果直接复用。"
      ],
      [
        "模型",
        "仅核对必要变化",
        "统一工具循环",
        "未完成或真实变化项按已有触发条件进入模型流程，输入及普通保存不调用。"
      ],
      [
        "程序",
        "汇总并事务提交",
        "不伪造科学通过",
        "已成功结果保留，技术未完成与科学分歧分别显示。"
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
    "change": "#194统一模型核对与有效复用；#195同步只读预览，均已本地实现和范围验证。",
    "limit": "原用户草稿保留，不代审或批准；未推送部署。实际验证范围见本地验收。",
    "refs": [
      [
        "当前实现与职责",
        "field-review-automation.md"
      ],
      [
        "统一核对验收",
        "../../specs/194-unified-model-review/spec.md"
      ],
      [
        "预览同步验收",
        "../../specs/195-parsing-preview-sync/spec.md"
      ]
    ],
    "current": [
      [
        "界面",
        "显示阶段只读预览",
        "题录与材料分区",
        "科学结果及时更新，ready后取正式可编辑草稿。"
      ],
      [
        "字段",
        "展示当前核对状态",
        "通过、未完成及分歧",
        "通过无需重复人工确认，技术失败保留具体原因。"
      ],
      [
        "侧栏",
        "按字段查看和处理",
        "保留既有布局",
        "主动操作仅当前字段，旧意见不冒充当前版本结论。"
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

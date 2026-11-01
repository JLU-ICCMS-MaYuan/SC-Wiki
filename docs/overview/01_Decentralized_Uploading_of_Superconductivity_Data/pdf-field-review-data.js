// 当前字段规则与来源索引；退役字段不作为新字段契约。
window.SC_WIKI_FIELD_REVIEW_CATALOG = {
  "date": "2026-11-01",
  "revision": "196-200-local-validation",
  "profiles": {
    "parser": {
      "label": "解析器专门路径",
      "model": "GROBID 解析参考文献；不由逐字段 LLM 猜造引用。",
      "candidate": "不走通用科学字段候选补空；保留原引文与匹配状态。",
      "required": "解析状态独立保存；引用图不凭模型的 builds_on 文本制造引用边。",
      "flow": [
        [
          "参考文献表",
          "原 PDF"
        ],
        [
          "GROBID 解析",
          "TEI 与原始引文"
        ],
        [
          "结构与匹配",
          "按标识核对"
        ],
        [
          "保存引用事实",
          "保留状态"
        ],
        [
          "查询引用图",
          "不代替论文批准"
        ]
      ]
    },
    "bibliography": {
      "label": "题录归并 / 程序字面核验",
      "model": "默认 required=false，不进入解析后的必需科学字段生成批。人工实际改动后仍按当前修改、来源与提交规则处理，不能理解为任意修改永久免审。",
      "candidate": "先用 GROBID 主文题录与同源核验资料归并；通用候选不能充当作者或出版资料事实。",
      "required": "标题等格式必填仍由 _validate_draft 检查；题录不默认要求逐字段补科学证据。已定位首页字面事实可由程序核实。",
      "flow": [
        [
          "主文首页",
          "出版资料"
        ],
        [
          "题录归并",
          "GROBID 优先"
        ],
        [
          "身份与字面",
          "来源可核实？"
        ],
        [
          "保存元数据",
          "分歧另留痕"
        ],
        [
          "实际修改后",
          "按修改规则检查"
        ]
      ]
    },
    "semantic": {
      "label": "共用语义核对",
      "model": "在对应来源和当前语义上下文中调用共享 evaluate_batch / checked_result；并非每个字段都有独立模型或独立专用算法。不能只定位到原句就断言分类或归纳正确。",
      "candidate": "通用补空保留；解析系统草稿有唯一、实际来源支持的候选时，核实最终值后纠正。人工修改或确认不自动覆盖；主动候选应用与整篇批准分开。",
      "required": "有实际值且适用时参与核对；合法可选空值与未完成读取不同。修改内容、来源或真实依赖使旧结果失效。",
      "flow": [
        [
          "本文有效来源",
          "明确适用对象"
        ],
        [
          "提取或归纳",
          "类型 / 语言检查"
        ],
        [
          "语义及依据",
          "能支持当前值？"
        ],
        [
          "候选按规则",
          "保留或补空"
        ],
        [
          "保存字段结果",
          "按版本复用"
        ]
      ]
    },
    "special": {
      "label": "专门生成 + 共用复核",
      "model": "先执行本字段的专门生成与来源检查，再经共享字段核对。专门过程成功不自动替代后续提交及整篇批准。",
      "candidate": "优先尊重专门过程的来源和候选规则；专门排除的字段不使用通用 _fill_empty_fields 强行补值。",
      "required": "以专门过程状态、当前值和当前来源版本为准；失败保留诊断或原候选供人工处理。",
      "flow": [
        [
          "全文有效来源",
          "按本字段读取"
        ],
        [
          "专门生成",
          "格式与来源门"
        ],
        [
          "专属依据",
          "满足本字段要求？"
        ],
        [
          "共用字段复核",
          "保存状态 / 理由"
        ],
        [
          "绑定当前版本",
          "留痕供提交"
        ]
      ]
    },
    "fact": {
      "label": "事实 / 数值共享核对",
      "model": "字段值、单位、所属材料与状态一起进入共享核对；先验证类型和来源定位，再判断原文是否支持当前科学含义。",
      "candidate": "科学子项不走通用建议补空；Methods 关联可按白名单和真实适用范围补空。原有非空值不被通用候选覆盖。",
      "required": "实际有值的科学叶子按适用规则核对；状态关联不等于依赖整张表，真实依赖变化才失效。",
      "flow": [
        [
          "当前材料原文",
          "记录及条件对应"
        ],
        [
          "类型与格式",
          "数值 / 单位检查"
        ],
        [
          "数值及语义",
          "原文支持当前项？"
        ],
        [
          "候选有限处理",
          "核实唯一候选；保护人工"
        ],
        [
          "保存字段结果",
          "值与来源版本"
        ]
      ]
    },
    "derived": {
      "label": "条件成立时程序派生",
      "model": "满足派生条件时由确定性程序重算，并依赖输入字段的有效结果；不是让模型再猜一个数。条件不成立时按实际代码回退普通断言或报告不一致。",
      "candidate": "派生结果不由通用候选生成。先修真实输入，再重新读取或计算派生值。",
      "required": "派生项有独立身份及明确依赖；生成阶段不按普通科学项重新向模型提问。不能借输入未通过来给派生项授信。",
      "flow": [
        [
          "确定的输入",
          "化学式 / 符号等"
        ],
        [
          "程序派生",
          "查表或单位换算"
        ],
        [
          "输入与结果",
          "规则条件满足？"
        ],
        [
          "关联输入核对",
          "不独立猜值"
        ],
        [
          "保存派生结果",
          "输入变更则失效"
        ]
      ]
    },
    "structure": {
      "label": "结构模型整体核对",
      "model": "可建模解析、文件真实性与科学归属分别判断；结构数值不经通用建议重新生成。来源不足时按实际人工来源规则处理。",
      "candidate": "只保留符合结构完整性和校验规则的模型候选；提交前分配到对应材料状态并明确确认。",
      "required": "结构文件及归属是审核对象；晶格量可从同一已核对结构派生，不能当作多个互不相关的独立猜测。",
      "flow": [
        [
          "论文表或附件",
          "完整结构输入"
        ],
        [
          "结构解析",
          "格式 / 几何 / 哈希"
        ],
        [
          "完整与归属",
          "可建模且对应？"
        ],
        [
          "确认模型候选",
          "保留真实来源"
        ],
        [
          "保存模型及派生",
          "绑定材料状态"
        ]
      ]
    },
    "structure-part": {
      "label": "结构内部量 / 依赖整体",
      "model": "不是按每个原子坐标单独请求 LLM；由结构文件整体断言承担来源和归属，明确拆出的晶格派生项依赖结构文件结果。",
      "candidate": "不生成猜测坐标、元素或晶格量。完整结构文件更新后重新解析对应量。",
      "required": "按结构整体身份或明确派生依赖管理，不能把每个展示量都算作单独人工审核。",
      "flow": [
        [
          "同一结构模型",
          "结构文件及归属"
        ],
        [
          "结构解析或派生",
          "读取指定内部量"
        ],
        [
          "模型与输入",
          "当前版本有效？"
        ],
        [
          "依赖结构结论",
          "不逐原子猜测"
        ],
        [
          "展示或保存量",
          "随结构版本更新"
        ]
      ]
    },
    "condition": {
      "label": "按软件 / 阶段核对条件",
      "model": "共享模型判断事实与适用范围，程序校验材料、物相、软件、阶段、完整来源和冲突；白名单规则全部满足才允许规则支持。",
      "candidate": "仅按明确事实与适用范围补空，不跨软件或跨阶段搬参数。无报告参数留空，泛函尤其不能从 VASP 推给 QE。",
      "required": "按当前条件上下文和来源完整性判断，不以整条 Methods 出现同名参数就授予通过。",
      "flow": [
        [
          "Methods 或表注",
          "事实 + 范围依据"
        ],
        [
          "绑定软件阶段",
          "材料 / 物相对应"
        ],
        [
          "完整且无冲突",
          "白名单规则满足？"
        ],
        [
          "允许才补空",
          "保留推断身份"
        ],
        [
          "按最终值复核",
          "保存规则版本"
        ]
      ]
    },
    "metadata": {
      "label": "身份 / 定义 / 结构校验",
      "model": "用于对象身份、定义、引用或保存控制，不因它出现在数据结构里就给它单独发科学核对请求。",
      "candidate": "不生成或猜测数据库身份和定义版本；由服务端与发布定义解析。",
      "required": "不作为普通科学断言，但身份无效、定义校验和不一致或引用不存在会阻止保存。",
      "flow": [
        [
          "服务端身份或定义",
          "非论文科学数值"
        ],
        [
          "归属与版本检查",
          "格式及引用校验"
        ],
        [
          "对象是否合法",
          "发布定义一致？"
        ],
        [
          "绑定正确目标",
          "不让模型编造"
        ],
        [
          "保存或拒绝",
          "保留当前输入"
        ]
      ]
    },
    "spectrum": {
      "label": "独立谱处理合同",
      "model": "曲线识别、像素提取、质量和积分走独立谱流程，不能把曲线有数据当作论文科学值已确认。",
      "candidate": "候选曲线、采样范围、幅值依据和质量信息单独保留；不通过通用字段候选捏造缺失幅值或端点。",
      "required": "α²F / phDOS 不要求先逐谱人工采纳才送审；公共谱发布资格与论文送审仍分开，其他字段门禁不变。",
      "flow": [
        [
          "图像与轴信息",
          "原图 / 来源归属"
        ],
        [
          "曲线及质量检查",
          "独立谱合同"
        ],
        [
          "计算条件",
          "量纲与标定足够？"
        ],
        [
          "仅计算可计算项",
          "缺条件不编造"
        ],
        [
          "保存曲线与质量",
          "不自动授予公开资格"
        ]
      ]
    }
  },
  "fields": [
    {
      "id": "paper_references[*]",
      "label": "参考文献解析",
      "path": "paper_references[*]",
      "group": "参考文献",
      "mode": "parser",
      "read": "原 PDF 的 References，经 GROBID TEI biblStruct 与正文引用锚点解析。",
      "checks": [
        "记录 GROBID 成功、不可用或解析不完整状态。",
        "解析原始引文、DOI、标题、作者、年份及引用目标；匹配服务使用保存的字段。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "GROBID 不可用、TEI 不完整或文献身份无法匹配。"
      ],
      "fixes": [
        "检查 GROBID 状态及 fulltext.tei.xml / document.json；先确认参考文献表是否被正确读取。",
        "引用匹配与解析状态分别检查，不让 LLM 猜造缺失引用。"
      ],
      "example": "例：参考文献解析完成37条，不等于37篇都已匹配为数据库内论文。",
      "scope": "专门过程",
      "errorCodes": [
        "unavailable",
        "解析不完整",
        "匹配未完成"
      ],
      "failureRoute": "记录解析或匹配未完成，不造引用",
      "sources": [
        {
          "path": "backend/ingest/grobid_document.py",
          "line": 69,
          "symbol": "extract_document"
        },
        {
          "path": "backend/ingest/grobid_document.py",
          "line": 32,
          "symbol": "parse_document"
        },
        {
          "path": "backend/services/citation_graph.py",
          "line": 85,
          "symbol": "parse_grobid_tei"
        }
      ]
    },
    {
      "id": "paper.title",
      "label": "标题",
      "path": "paper.title",
      "group": "论文题录",
      "mode": "bibliography",
      "read": "GROBID teiHeader/titleStmt/title；原论文标题保持来源语言。",
      "checks": [
        "采用正文文件的 GROBID 题录，保留与提取候选的分歧及来源。",
        "不默认进入 required 科学字段生成批；有 verified_front_matter 且字面覆盖当前值时可由程序核实。",
        "标题是文献身份的一部分，不能取参考文献题名或 SI 通用标题代替。"
      ],
      "dependencies": [
        "本字段及其首页来源；作者角色不由数组位置代替。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先确认主文与SI角色，再查看GROBID的teiHeader/title及原PDF首页；不要拿参考文献题名修正本篇标题。",
        "若误选题录，查grobid_document.apply_bibliography及文件身份；只修标题和真实依赖，不覆盖人工草稿。"
      ],
      "example": "例：原论文标题保留原文；图谱科学标题是另一个归纳字段。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "publication_verified",
        "identity_mismatch",
        "user_review"
      ],
      "failureRoute": "保留题录差异并查同源出版依据",
      "sources": [
        {
          "path": "backend/ingest/grobid_document.py",
          "line": 32,
          "symbol": "parse_document"
        },
        {
          "path": "backend/ingest/grobid_document.py",
          "line": 130,
          "symbol": "apply_bibliography"
        },
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 102,
          "symbol": "field_records"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 337,
          "symbol": "deterministic_results"
        }
      ]
    },
    {
      "id": "paper.authors",
      "label": "作者",
      "path": "paper.authors",
      "group": "论文题录",
      "mode": "bibliography",
      "read": "当前论文首页的 作者，优先 GROBID；原始候选与题录来源分别保留。",
      "checks": [
        "采用正文文件的 GROBID 题录，保留与提取候选的分歧及来源。",
        "不默认进入 required 科学字段生成批；有 verified_front_matter 且字面覆盖当前值时可由程序核实。",
        "作者列表及作者角色分别定位；不能仅有姓名就推定通讯或共同第一作者角色。"
      ],
      "dependencies": [
        "本字段及其首页来源；作者角色不由数组位置代替。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：作者存在两个来源候选时保留差异，而不是按解析器多数票批准。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "publication_verified",
        "identity_mismatch",
        "user_review"
      ],
      "failureRoute": "保留题录差异并查同源出版依据",
      "sources": [
        {
          "path": "backend/ingest/grobid_document.py",
          "line": 32,
          "symbol": "parse_document"
        },
        {
          "path": "backend/ingest/grobid_document.py",
          "line": 130,
          "symbol": "apply_bibliography"
        },
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 102,
          "symbol": "field_records"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 337,
          "symbol": "deterministic_results"
        }
      ]
    },
    {
      "id": "paper.co_first_authors",
      "label": "共同第一作者",
      "path": "paper.co_first_authors",
      "group": "论文题录",
      "mode": "bibliography",
      "read": "分段提取的作者角色证据与首页作者标注，角色与普通 authors 分开。",
      "checks": [
        "依据作者角色标注与分段提取的角色证据；普通GROBID作者列表本身不证明共同第一或通讯角色。",
        "不默认进入 required 科学字段生成批；有 verified_front_matter 且字面覆盖当前值时可由程序核实。",
        "作者列表及作者角色分别定位；不能仅有姓名就推定通讯或共同第一作者角色。"
      ],
      "dependencies": [
        "本字段及其首页来源；作者角色不由数组位置代替。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：共同第一作者存在两个来源候选时保留差异，而不是按解析器多数票批准。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "publication_verified",
        "identity_mismatch",
        "user_review"
      ],
      "failureRoute": "保留题录差异并查同源出版依据",
      "sources": [
        {
          "path": "backend/ingest/upload_jobs.py",
          "line": 81,
          "symbol": "CHUNK_SYSTEM_PROMPT"
        },
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 102,
          "symbol": "field_records"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 337,
          "symbol": "deterministic_results"
        }
      ]
    },
    {
      "id": "paper.corresponding_authors",
      "label": "通讯作者",
      "path": "paper.corresponding_authors",
      "group": "论文题录",
      "mode": "bibliography",
      "read": "分段提取的作者角色证据与首页作者标注，角色与普通 authors 分开。",
      "checks": [
        "依据作者角色标注与分段提取的角色证据；普通GROBID作者列表本身不证明共同第一或通讯角色。",
        "不默认进入 required 科学字段生成批；有 verified_front_matter 且字面覆盖当前值时可由程序核实。",
        "作者列表及作者角色分别定位；不能仅有姓名就推定通讯或共同第一作者角色。"
      ],
      "dependencies": [
        "本字段及其首页来源；作者角色不由数组位置代替。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：通讯作者存在两个来源候选时保留差异，而不是按解析器多数票批准。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "publication_verified",
        "identity_mismatch",
        "user_review"
      ],
      "failureRoute": "保留题录差异并查同源出版依据",
      "sources": [
        {
          "path": "backend/ingest/upload_jobs.py",
          "line": 81,
          "symbol": "CHUNK_SYSTEM_PROMPT"
        },
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 102,
          "symbol": "field_records"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 337,
          "symbol": "deterministic_results"
        }
      ]
    },
    {
      "id": "paper.journal",
      "label": "期刊名",
      "path": "paper.journal",
      "group": "论文题录",
      "mode": "bibliography",
      "read": "当前论文首页的 期刊，优先 GROBID；原始候选与题录来源分别保留。",
      "checks": [
        "采用正文文件的 GROBID 题录，保留与提取候选的分歧及来源。",
        "不默认进入 required 科学字段生成批；有 verified_front_matter 且字面覆盖当前值时可由程序核实。"
      ],
      "dependencies": [
        "本字段及其首页来源；作者角色不由数组位置代替。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：期刊存在两个来源候选时保留差异，而不是按解析器多数票批准。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "publication_verified",
        "identity_mismatch",
        "user_review"
      ],
      "failureRoute": "保留题录差异并查同源出版依据",
      "sources": [
        {
          "path": "backend/ingest/grobid_document.py",
          "line": 32,
          "symbol": "parse_document"
        },
        {
          "path": "backend/ingest/grobid_document.py",
          "line": 130,
          "symbol": "apply_bibliography"
        },
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 102,
          "symbol": "field_records"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 337,
          "symbol": "deterministic_results"
        }
      ]
    },
    {
      "id": "paper.year",
      "label": "年份",
      "path": "paper.year",
      "group": "论文题录",
      "mode": "bibliography",
      "read": "GROBID 出版日期，并结合 publication_year 的原 PDF 与同身份出版资料核验；独立解析差异分类已撤销，不生成责任分类待办。",
      "checks": [
        "采用正文文件的 GROBID 题录，保留与提取候选的分歧及来源。",
        "不默认进入 required 科学字段生成批；有 verified_front_matter 且字面覆盖当前值时可由程序核实。",
        "同源 PDF、DOI、标题与出版年份核验一致才采用 verified 结果；下载/打印年份不是发表年份。",
        "在线与正式卷期年份歧义保留 user_review，不伪造核实。"
      ],
      "dependencies": [
        "本字段；年份核验还依赖同源文件、DOI和标题身份。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "对照首页出版日期与下载/打印日期，检查同源哈希、DOI及标题身份。",
        "查publication_year.verify_document_year的verified/ambiguous/identity_mismatch原因；不能跳过身份检查直接取Crossref年份。"
      ],
      "example": "例：2021是下载日期，不能因此覆盖论文真实出版年份2012。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "publication_verified",
        "identity_mismatch",
        "user_review"
      ],
      "failureRoute": "保留题录差异并查同源出版依据",
      "sources": [
        {
          "path": "backend/ingest/grobid_document.py",
          "line": 32,
          "symbol": "parse_document"
        },
        {
          "path": "backend/ingest/grobid_document.py",
          "line": 130,
          "symbol": "apply_bibliography"
        },
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 102,
          "symbol": "field_records"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 337,
          "symbol": "deterministic_results"
        },
        {
          "path": "backend/ingest/publication_year.py",
          "line": 70,
          "symbol": "verify_document_year"
        }
      ],
      "flow": [
        [
          "主文出版资料",
          "排除下载日期"
        ],
        [
          "核对同源身份",
          "标题与DOI一致"
        ],
        [
          "年份口径",
          "核验能成立？"
        ],
        [
          "采用或保留歧义",
          "保留原候选"
        ],
        [
          "保存题录诊断",
          "改值后旧证失效"
        ]
      ]
    },
    {
      "id": "paper.issue_number",
      "label": "期号",
      "path": "paper.issue_number",
      "group": "论文题录",
      "mode": "semantic",
      "read": "当前论文原文身份及Crossref正式题录，区分早期版页码和正式页码。",
      "checks": [
        "模型按原文DOI和标题核实正式题录后补空。",
        "外部来源保留链接，不冒充PDF引句；卷号为文本，不能套用几何体积枚举。"
      ],
      "dependencies": [
        "本字段及其首页来源；作者角色不由数组位置代替。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：期号存在两个来源候选时保留差异，而不是按解析器多数票批准。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "publication_verified",
        "identity_mismatch",
        "user_review"
      ],
      "failureRoute": "保留题录差异并查同源出版依据",
      "sources": [
        {
          "path": "backend/ingest/grobid_document.py",
          "line": 32,
          "symbol": "parse_document"
        },
        {
          "path": "backend/ingest/grobid_document.py",
          "line": 130,
          "symbol": "apply_bibliography"
        },
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 102,
          "symbol": "field_records"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 337,
          "symbol": "deterministic_results"
        },
        {
          "path": "backend/ingest/bibliography_lookup.py",
          "symbol": "lookup",
          "line": 8
        }
      ]
    },
    {
      "id": "paper.volume",
      "label": "卷号",
      "path": "paper.volume",
      "group": "论文题录",
      "mode": "semantic",
      "read": "当前论文原文身份及Crossref正式题录，区分早期版页码和正式页码。",
      "checks": [
        "模型按原文DOI和标题核实正式题录后补空。",
        "外部来源保留链接，不冒充PDF引句；卷号为文本，不能套用几何体积枚举。"
      ],
      "dependencies": [
        "本字段及其首页来源；作者角色不由数组位置代替。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：卷号存在两个来源候选时保留差异，而不是按解析器多数票批准。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "publication_verified",
        "identity_mismatch",
        "user_review"
      ],
      "failureRoute": "保留题录差异并查同源出版依据",
      "sources": [
        {
          "path": "backend/ingest/grobid_document.py",
          "line": 32,
          "symbol": "parse_document"
        },
        {
          "path": "backend/ingest/grobid_document.py",
          "line": 130,
          "symbol": "apply_bibliography"
        },
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 102,
          "symbol": "field_records"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 337,
          "symbol": "deterministic_results"
        },
        {
          "path": "backend/ingest/bibliography_lookup.py",
          "symbol": "lookup",
          "line": 8
        }
      ]
    },
    {
      "id": "paper.pages",
      "label": "起始页码 / 页码范围 / 文章编号",
      "path": "paper.pages",
      "group": "论文题录",
      "mode": "semantic",
      "read": "当前论文原文身份及Crossref正式题录，区分早期版页码和正式页码。",
      "checks": [
        "模型按原文DOI和标题核实正式题录后补空。",
        "外部来源保留链接，不冒充PDF引句；卷号为文本，不能套用几何体积枚举。"
      ],
      "dependencies": [
        "本字段及其首页来源；作者角色不由数组位置代替。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：页码存在两个来源候选时保留差异，而不是按解析器多数票批准。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "publication_verified",
        "identity_mismatch",
        "user_review"
      ],
      "failureRoute": "保留题录差异并查同源出版依据",
      "sources": [
        {
          "path": "backend/ingest/grobid_document.py",
          "line": 32,
          "symbol": "parse_document"
        },
        {
          "path": "backend/ingest/grobid_document.py",
          "line": 130,
          "symbol": "apply_bibliography"
        },
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 102,
          "symbol": "field_records"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 337,
          "symbol": "deterministic_results"
        },
        {
          "path": "backend/ingest/bibliography_lookup.py",
          "symbol": "lookup",
          "line": 8
        }
      ]
    },
    {
      "id": "paper.doi",
      "label": "DOI",
      "path": "paper.doi",
      "group": "论文题录",
      "mode": "bibliography",
      "read": "当前论文首页的 DOI，优先 GROBID；原始候选与题录来源分别保留。",
      "checks": [
        "采用正文文件的 GROBID 题录，保留与提取候选的分歧及来源。",
        "不默认进入 required 科学字段生成批；有 verified_front_matter 且字面覆盖当前值时可由程序核实。",
        "归一化 DOI，并区分主文自身 DOI 与参考文献 DOI；正式提交另有重复论文校验。"
      ],
      "dependencies": [
        "本字段及其首页来源；作者角色不由数组位置代替。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：正文首页 DOI 与参考文献 DOI 要分开识别。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "publication_verified",
        "identity_mismatch",
        "user_review"
      ],
      "failureRoute": "保留题录差异并查同源出版依据",
      "sources": [
        {
          "path": "backend/ingest/grobid_document.py",
          "line": 32,
          "symbol": "parse_document"
        },
        {
          "path": "backend/ingest/grobid_document.py",
          "line": 130,
          "symbol": "apply_bibliography"
        },
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 102,
          "symbol": "field_records"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 337,
          "symbol": "deterministic_results"
        }
      ]
    },
    {
      "id": "paper.abstract",
      "label": "论文摘要",
      "path": "paper.abstract",
      "group": "论文叙述",
      "mode": "fact",
      "read": "优先主文题录的原摘要，原语言保留。",
      "checks": [
        "GROBID 误混入引言时，仅在同源独立版面块证实关键词边界后截取。",
        "不得当成 AI 自由改写字段；与 summary 的英文编号总结分开。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查原PDF摘要结束位置及GROBID是否串入引言。",
        "核对_bounded_abstract是否真的找到同源版面关键词边界；没有证据时不以固定字数裁断摘要。"
      ],
      "example": "例：论文摘要改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/grobid_document.py",
          "line": 100,
          "symbol": "_bounded_abstract"
        },
        {
          "path": "backend/ingest/grobid_document.py",
          "line": 130,
          "symbol": "apply_bibliography"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "paper.summary",
      "label": "论文总结",
      "path": "paper.summary",
      "group": "论文叙述",
      "mode": "special",
      "read": "主汇总候选经过 choose_summary / valid_summary 专门检查。",
      "checks": [
        "3–5条连续编号、逐行英文完整句；拒绝明显摘要复写。",
        "摘要≥70英文词时，总结词数须大于摘要且不超过1.5倍；句子相似度另有检查。",
        "不合格在既有预算内定向重试，保存尝试与失败原因。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先区分格式失败和科学内容错误；查summary_attempts与valid_summary的编号、语言、词数及摘要复写检查。",
        "若句子科学归属错，检查全文候选、原摘要及choose_summary输入，不通过删掉原文证据来降低相似度。"
      ],
      "example": "例：论文总结改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "专门过程",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/paper_summary.py",
          "line": 37,
          "symbol": "valid_summary"
        },
        {
          "path": "backend/ingest/paper_summary.py",
          "line": 70,
          "symbol": "choose_summary"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ],
      "flow": [
        [
          "全文与原摘要",
          "当前论文结果"
        ],
        [
          "主汇总候选",
          "专门格式校验"
        ],
        [
          "编号及复写",
          "不符则定向重试"
        ],
        [
          "共用语义复核",
          "保留原文依据"
        ],
        [
          "保存总结结果",
          "与abstract分开"
        ]
      ]
    },
    {
      "id": "paper.methodology",
      "label": "研究方法",
      "path": "paper.methodology",
      "group": "论文叙述",
      "mode": "semantic",
      "read": "主汇总对本文实际方法的英文归纳。",
      "checks": [
        "不能把引用他人的方法当作本文实际执行。",
        "语义及可定位来源检查，不与每条计算软件、泛函或声子方法字段混成一项。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：研究方法改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/upload_jobs.py",
          "line": 162,
          "symbol": "SUMMARY_SYSTEM_PROMPT"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        },
        {
          "path": "backend/ingest/language_contract.py",
          "line": 37,
          "symbol": "validate_draft_generated_english"
        }
      ]
    },
    {
      "id": "paper.key_finding",
      "label": "核心发现 / 主要发现",
      "path": "paper.key_finding",
      "group": "论文叙述",
      "mode": "semantic",
      "read": "主汇总对本文核心结果和发现的英文归纳。",
      "checks": [
        "需要当前论文自己的结果依据，不把前人结果或研究背景当本文发现。",
        "共用 synthesis 检查；没有专门独立 key_finding 算法可保证科学正确。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：核心发现 / 主要发现改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/upload_jobs.py",
          "line": 162,
          "symbol": "SUMMARY_SYSTEM_PROMPT"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "paper.research_motivation",
      "label": "研究驱动力 / 研究动机",
      "path": "paper.research_motivation",
      "group": "论文叙述",
      "mode": "special",
      "read": "从本文研究缺口、目标及开展研究的原因提炼。",
      "checks": [
        "1–3条连续编号英文动因，逐行显示，总词数不超过300。",
        "按来源编号取回原句，不改写公式或跨文件拼句。",
        "不是结论和分类理由；先核验初始值，不满足时定向读有效全文。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "核查内容是在讲研究缺口和目标，还是把本文结果当成动机。",
        "查research_motivation的来源编号、逐条依据和choose_motivation失败原因；不要手抄公式替换有效source_id。"
      ],
      "example": "例：研究驱动力 / 研究动机改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "专门过程",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/research_motivation.py",
          "line": 48,
          "symbol": "valid_motivation"
        },
        {
          "path": "backend/ingest/research_motivation.py",
          "line": 128,
          "symbol": "choose_motivation"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ],
      "flow": [
        [
          "研究缺口与目标",
          "全文有效来源"
        ],
        [
          "初始动因审定",
          "必要才重新生成"
        ],
        [
          "动因与来源",
          "不是论文结论"
        ],
        [
          "编号与语义核对",
          "来源编号取原文"
        ],
        [
          "保存动因理由",
          "绑定当前值"
        ]
      ]
    },
    {
      "id": "paper.keywords_tags",
      "label": "关键词",
      "path": "paper.keywords_tags",
      "group": "论文叙述",
      "mode": "special",
      "read": "优先主文作者原列 Keywords；找不到可靠列表时才读取有效正文归纳。",
      "checks": [
        "作者原词与顺序保留，必须能定位原文列表。",
        "AI提炼要覆盖有效全文，给出具体选词依据和可定位代表来源；生成词用英文。",
        "初始全文归纳合格可复用，否则定向提炼3–8词；失败保留状态，不把未读当无关键词。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先查主文是否有作者原列关键词和可定位列表。",
        "若没有，查看keyword_assessment的kind、覆盖窗口和失败原因；全文未读完不能冒称论文没有关键词。",
        "词项不合适时查看select_keywords的专门候选及字段来源，不只把摘要关键词再当全文提炼。"
      ],
      "example": "例：主文作者列有关键词时保留作者原词；只有无可靠作者列表时才走AI全文提炼。",
      "scope": "专门过程",
      "candidate": "专门流程管理本字段的值、理由和来源；通用 _fill_empty_fields 明确跳过。字段设置的主动候选仍按当前侧栏应用与版本确认流程处理。",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/keyword_extraction.py",
          "line": 70,
          "symbol": "_author_list"
        },
        {
          "path": "backend/ingest/keyword_extraction.py",
          "line": 123,
          "symbol": "select_keywords"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ],
      "flow": [
        [
          "主文关键词栏",
          "先找作者原列"
        ],
        [
          "可靠原列优先",
          "否则全文提炼"
        ],
        [
          "出处与覆盖",
          "作者词或归纳？"
        ],
        [
          "保留对应类别",
          "不通用强补空"
        ],
        [
          "保存专门依据",
          "改值失效"
        ]
      ]
    },
    {
      "id": "paper.paper_type",
      "label": "论文整体类型",
      "path": "paper.paper_type",
      "group": "科学分类",
      "mode": "semantic",
      "read": "全文分段候选及主汇总对本文性质的归纳。",
      "checks": [
        "按 theoretical / experimental / review / unknown 等当前契约表示；提交检查必要选择。",
        "共用 synthesis 判断本文实际内容；不是看软件名或某个关键词就分类。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：论文整体类型改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/upload_jobs.py",
          "line": 162,
          "symbol": "SUMMARY_SYSTEM_PROMPT"
        },
        {
          "path": "backend/api/rag.py",
          "line": 485,
          "symbol": "_validate_draft"
        },
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 43,
          "symbol": "SYNTHESIS_FIELDS"
        }
      ]
    },
    {
      "id": "paper.theoretical_subtype",
      "label": "理论二级类型",
      "path": "paper.theoretical_subtype",
      "group": "科学分类",
      "mode": "special",
      "read": "理论论文的主要贡献：calculation / method / theory。",
      "checks": [
        "非理论论文清空此项。",
        "先审定主汇总的分类、理由与本文贡献证据；不合格才定向读全文。",
        "至少有摘要、结果、讨论或结论来源；只见 Methods 或软件名不能通过。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "打开代表性摘要/结果/讨论/结论依据，比较主要贡献属于calculation、method还是theory。",
        "若只引Methods或软件名，查assess_candidate的贡献来源门及classify的全文输入；不要新增一条软件名到类型的直接映射。"
      ],
      "example": "例：使用 VASP 算材料性质通常不能据此判为“提出新方法”；需比较本文主要贡献。",
      "scope": "专门过程",
      "candidate": "专门流程管理本字段的值、理由和来源；通用 _fill_empty_fields 明确跳过。字段设置的主动候选仍按当前侧栏应用与版本确认流程处理。",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/theoretical_subtype.py",
          "line": 47,
          "symbol": "assess_candidate"
        },
        {
          "path": "backend/ingest/theoretical_subtype.py",
          "line": 71,
          "symbol": "classify"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ],
      "flow": [
        [
          "全文实际贡献",
          "结果/讨论等"
        ],
        [
          "首轮候选审定",
          "必要才重读全文"
        ],
        [
          "贡献证据",
          "不只看Methods"
        ],
        [
          "保留当前分类",
          "冲突则待核对"
        ],
        [
          "保存专门分析",
          "同源当前版本"
        ]
      ]
    },
    {
      "id": "paper.superconductor_kind",
      "label": "超导类型",
      "path": "paper.superconductor_kind",
      "group": "科学分类",
      "mode": "semantic",
      "read": "论文级超导体类别的全文语义判断。",
      "checks": [
        "未知也进入模型核对；结合本文配对机制判常规或非常规，保留推断与依据。",
        "不单凭计算方法名或化学式分类；依据不足保持未知。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：超导类型改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/upload_jobs.py",
          "line": 1462,
          "symbol": "_normalize_draft"
        },
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 43,
          "symbol": "SYNTHESIS_FIELDS"
        },
        {
          "path": "backend/api/rag.py",
          "line": 485,
          "symbol": "_validate_draft"
        }
      ]
    },
    {
      "id": "paper.material_families",
      "label": "材料家族",
      "path": "paper.material_families",
      "group": "科学分类",
      "mode": "special",
      "read": "论文研究材料、主文分类证据与当前目录选择。",
      "checks": [
        "有专门全文分类步骤；只给软件名或模糊领域名不能代替材料家族。",
        "核对当前选择及来源；新名称是待确认候选，不因输入自动成为已批准目录。",
        "_fill_empty_fields 排除此字段。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "核对当前研究材料与实际目录选择；不要用结构家族或超导类型代替材料家族。",
        "查看material_family_assessment及_classify_material_family_draft；候选未确认时保留状态，不靠通用补空强行填目录。"
      ],
      "example": "例：材料家族改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "专门过程",
      "candidate": "专门流程管理本字段的值、理由和来源；通用 _fill_empty_fields 明确跳过。字段设置的主动候选仍按当前侧栏应用与版本确认流程处理。",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/upload_jobs.py",
          "line": 1603,
          "symbol": "_classify_material_family_draft"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 1155,
          "symbol": "_fill_empty_fields"
        },
        {
          "path": "backend/services/classification_catalog.py",
          "line": 275,
          "symbol": "save_paper_material_families"
        }
      ]
    },
    {
      "id": "paper.research_materials",
      "label": "研究材料汇总",
      "path": "paper.research_materials",
      "group": "科学分类",
      "mode": "semantic",
      "read": "由实际材料状态的材料名或化学式组装论文级研究材料。",
      "checks": [
        "当前互补解析以材料状态组装并去重，不能由概要捏造未收录材料。",
        "核对依赖实际材料集合，修改无关叙述不应清空所有材料结果。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：研究材料汇总改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/upload_jobs.py",
          "line": 1855,
          "symbol": "_process_upload_task"
        },
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 19,
          "symbol": "PAPER_FIELDS"
        }
      ]
    },
    {
      "id": "paper.knowledge_graph_title",
      "label": "图谱科学标题",
      "path": "paper.knowledge_graph_title",
      "group": "论文叙述",
      "mode": "semantic",
      "read": "主汇总从本文核心贡献生成英文短标题，不是原论文 title 的替代值。",
      "checks": [
        "汇总提示词要求10–15个英文词；生成语言契约拒绝中日韩字符。",
        "当前没有单独的图谱标题词数强制校验函数；词数不能冒充已经由程序硬门禁保证。",
        "共用 synthesis 核对需要具体语义与可定位依据，不能只因题目流畅而通过。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "确认此处是图谱贡献短标题，而不是原文标题；有中文生成值时先查language_contract。",
        "若过长或内容跑题，查SUMMARY_SYSTEM_PROMPT的10–15英文词及核心贡献要求；当前没有独立词数硬校验，不把它说成已保证。",
        "已保存值不合适时在本字段侧栏改值并说明理由，再核对新版本，不改论文原文title来迁就。"
      ],
      "example": "例：把原标题原样复制到图谱短标题并不能证明它正确概括了本文贡献；10–15词是提示词要求，不是已发现的专门词数硬校验。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/upload_jobs.py",
          "line": 162,
          "symbol": "SUMMARY_SYSTEM_PROMPT"
        },
        {
          "path": "backend/ingest/language_contract.py",
          "line": 37,
          "symbol": "validate_draft_generated_english"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ],
      "flow": [
        [
          "本文核心贡献",
          "有效全文候选"
        ],
        [
          "主汇总生成",
          "英文短标题"
        ],
        [
          "语义与依据",
          "不是词数硬门"
        ],
        [
          "候选受限应用",
          "不覆盖非空值"
        ],
        [
          "保存短标题",
          "区别原文title"
        ]
      ]
    },
    {
      "id": "material_states[*].material_name",
      "label": "材料名",
      "path": "material_states[*].material_name",
      "group": "材料状态",
      "mode": "semantic",
      "read": "材料在原文中的名称、样品或具体组分描述。",
      "checks": [
        "材料名和化学式至少填一项；只有名称不能伪造可解析化学式。",
        "核对当前状态归属，不把同名不同相或不同压强合并。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：材料名改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 164,
          "symbol": "state_records"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].material",
      "label": "化学式",
      "path": "material_states[*].material",
      "group": "材料状态",
      "mode": "fact",
      "read": "原文明确完整化学式或能够唯一解析的组成。",
      "checks": [
        "支持括号分组及Unicode下标；不完整或有歧义的式子不能截成另一种化学式。",
        "元素种类数由解析后不同元素集合计算；化学式变更影响其真实依赖。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：化学式改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 164,
          "symbol": "state_records"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].material_dimensionality",
      "label": "材料维度",
      "path": "material_states[*].material_dimensionality",
      "group": "材料状态",
      "mode": "semantic",
      "read": "本文对结构维度的实际描述与模型。",
      "checks": [
        "按当前维度目录及共用语义判断；不能从超导类型直接推算材料维度。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：材料维度改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 164,
          "symbol": "state_records"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].pressure_value_gpa",
      "label": "压强 / 标准压强",
      "path": "material_states[*].pressure_value_gpa",
      "group": "材料状态",
      "mode": "semantic",
      "read": "原始压强及原单位；或直接报告的状态压强。",
      "checks": [
        "模型结合当前原文、计算及查表依据查证，不因派生而跳过。",
        "核对当前材料、压力及具体结果，保存并复用通过结论。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先区分物性测量/计算压强、材料稳定区间和结构表压力，不按相同材料名合并。",
        "检查pressure_raw与pressure_unit_raw，确认单位换算与范围表示；不要取范围端点冒充单值。",
        "错挂状态时修正当前记录所属条件，再按真实依赖复核，不恢复整份旧草稿。"
      ],
      "example": "例：压强 / 标准压强改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "条件化程序规则",
      "errorCodes": [
        "unchecked",
        "来源输入未通过"
      ],
      "failureRoute": "检查真实输入；不满足则不能当派生通过",
      "sources": [
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 164,
          "symbol": "state_records"
        },
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 230,
          "symbol": "converted_state_value"
        }
      ]
    },
    {
      "id": "material_states[*].pressure_min_gpa",
      "label": "压强下界",
      "path": "material_states[*].pressure_min_gpa",
      "group": "材料状态",
      "mode": "fact",
      "read": "状态自身的真实压强范围。",
      "checks": [
        "下界与上界共同核对，不能把相稳定压强区间当测量点。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先区分物性测量/计算压强、材料稳定区间和结构表压力，不按相同材料名合并。",
        "检查pressure_raw与pressure_unit_raw，确认单位换算与范围表示；不要取范围端点冒充单值。",
        "错挂状态时修正当前记录所属条件，再按真实依赖复核，不恢复整份旧草稿。"
      ],
      "example": "例：压强下界改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 164,
          "symbol": "state_records"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].pressure_max_gpa",
      "label": "压强上界",
      "path": "material_states[*].pressure_max_gpa",
      "group": "材料状态",
      "mode": "fact",
      "read": "与下界同一状态和同一物理含义的范围端点。",
      "checks": [
        "核对范围顺序、单位与状态归属，不按高低端点猜数据所属相。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先区分物性测量/计算压强、材料稳定区间和结构表压力，不按相同材料名合并。",
        "检查pressure_raw与pressure_unit_raw，确认单位换算与范围表示；不要取范围端点冒充单值。",
        "错挂状态时修正当前记录所属条件，再按真实依赖复核，不恢复整份旧草稿。"
      ],
      "example": "例：压强上界改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 164,
          "symbol": "state_records"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].temperature_value_k",
      "label": "温度 / 标准温度",
      "path": "material_states[*].temperature_value_k",
      "group": "材料状态",
      "mode": "derived",
      "read": "原始温度和明确单位。",
      "checks": [
        "支持K、摄氏和华氏的明确换算，容差按当前程序检查。",
        "没有明确原始温度及单位时不自动默认0K。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：温度 / 标准温度改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "条件化程序规则",
      "errorCodes": [
        "unchecked",
        "来源输入未通过"
      ],
      "failureRoute": "检查真实输入；不满足则不能当派生通过",
      "sources": [
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 164,
          "symbol": "state_records"
        },
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 230,
          "symbol": "converted_state_value"
        }
      ]
    },
    {
      "id": "material_states[*].magnetic_field_t",
      "label": "磁场",
      "path": "material_states[*].magnetic_field_t",
      "group": "材料状态",
      "mode": "fact",
      "read": "当前材料状态实际磁场条件。",
      "checks": [
        "核对量纲和状态归属，不从“零场超导”背景文字补值。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：磁场改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 164,
          "symbol": "state_records"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].reported_space_group_symbol",
      "label": "空间群符号",
      "path": "material_states[*].reported_space_group_symbol",
      "group": "材料状态",
      "mode": "fact",
      "read": "对应材料、物相和结构优化工作流的原文符号。",
      "checks": [
        "保留原报告符号，查表是否能唯一对应群号。",
        "不能仅凭相近压力把一个相的符号挂到另一个相。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：空间群符号改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 164,
          "symbol": "state_records"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].reported_space_group_number",
      "label": "空间群编号",
      "path": "material_states[*].reported_space_group_number",
      "group": "材料状态",
      "mode": "semantic",
      "read": "已报告标准符号的国际表对应编号。",
      "checks": [
        "模型结合当前原文、计算及查表依据查证，不因派生而跳过。",
        "核对当前材料、压力及具体结果，保存并复用通过结论。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先核对报告符号及国际表对应；编号冲突时不能拿查表结果悄悄覆盖原始输入。",
        "如果符号或材料状态错挂，修正实际所属状态后重建相关来源，而不是清空其他状态核对。"
      ],
      "example": "例：空间群编号改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "条件化程序规则",
      "errorCodes": [
        "unchecked",
        "来源输入未通过"
      ],
      "failureRoute": "检查真实输入；不满足则不能当派生通过",
      "sources": [
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 164,
          "symbol": "state_records"
        },
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 217,
          "symbol": "derived_symmetry_value"
        }
      ]
    },
    {
      "id": "material_states[*].crystal_system",
      "label": "晶系",
      "path": "material_states[*].crystal_system",
      "group": "材料状态",
      "mode": "semantic",
      "read": "报告空间群符号及标准群号对应；无唯一对应时按原文字段处理。",
      "checks": [
        "模型结合当前原文、计算及查表依据查证，不因派生而跳过。",
        "核对当前材料、压力及具体结果，保存并复用通过结论。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查空间群符号是否能唯一查表，并确认晶系与该群号对应。",
        "无唯一符号依据时不能伪称派生值；回到原文或结构模型核对该状态。"
      ],
      "example": "例：晶系改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "条件化程序规则",
      "errorCodes": [
        "unchecked",
        "来源输入未通过"
      ],
      "failureRoute": "检查真实输入；不满足则不能当派生通过",
      "sources": [
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 164,
          "symbol": "state_records"
        },
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 217,
          "symbol": "derived_symmetry_value"
        }
      ]
    },
    {
      "id": "material_states[*].state_kind",
      "label": "材料状态类型",
      "path": "material_states[*].state_kind",
      "group": "材料状态",
      "mode": "semantic",
      "read": "状态属于计算、实验等实际上下文。",
      "checks": [
        "按材料状态保存；不凭有Tc数值就猜测测量或预测。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：材料状态类型改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 164,
          "symbol": "state_records"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].structure_optimization",
      "label": "结构优化方法",
      "path": "material_states[*].structure_optimization",
      "group": "材料状态",
      "mode": "special",
      "read": "原文实际结构优化及对应材料、压力和结果。",
      "checks": [
        "静态、准简谐、SSCHA三类；未知保留unknown。",
        "SSCHA或0K字样不能单独证明优化；不再保存八项详情。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "由模型读取真实结构优化段落并判断当前状态，不按声子方法名代填。"
      ],
      "example": "固定几何的SSCHA声子计算不自动成为量子非谐结构优化；QHA体积自由能最小化可发生在0 K。",
      "scope": "专门过程",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/state_optimization.py",
          "line": 72,
          "symbol": "resolve_candidates"
        },
        {
          "path": "backend/ingest/state_optimization.py",
          "line": 276,
          "symbol": "assemble_candidates"
        },
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 164,
          "symbol": "state_records"
        }
      ]
    },
    {
      "id": "material_states[*].structure_families",
      "label": "结构家族",
      "path": "material_states[*].structure_families",
      "group": "材料状态",
      "mode": "semantic",
      "read": "该材料状态的结构原型、家族描述或可靠模型依据。",
      "checks": [
        "可多选目录项；与论文级材料家族分开。",
        "不由一个晶系名直接补猜结构家族。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：结构家族改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 164,
          "symbol": "state_records"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].condition_note",
      "label": "状态条件说明",
      "path": "material_states[*].condition_note",
      "group": "材料状态",
      "mode": "semantic",
      "read": "当前状态的范围、物相或适用条件补充。",
      "checks": [
        "共用语义核对，保留与具体状态的绑定。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：状态条件说明改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 164,
          "symbol": "state_records"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].note",
      "label": "材料状态说明",
      "path": "material_states[*].note",
      "group": "材料状态",
      "mode": "semantic",
      "read": "不属于其他专门字段的状态描述。",
      "checks": [
        "不以说明文字代替有独立字段的数值、单位和方法。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：材料状态说明改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 164,
          "symbol": "state_records"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].pressure_raw",
      "label": "原始压强",
      "path": "material_states[*].pressure_raw",
      "group": "材料状态",
      "mode": "fact",
      "read": "原文压强写法与区间表达。",
      "checks": [
        "保留原始表示，不能为了表单方便把范围压成标量。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先区分物性测量/计算压强、材料稳定区间和结构表压力，不按相同材料名合并。",
        "检查pressure_raw与pressure_unit_raw，确认单位换算与范围表示；不要取范围端点冒充单值。",
        "错挂状态时修正当前记录所属条件，再按真实依赖复核，不恢复整份旧草稿。"
      ],
      "example": "例：原始压强改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 164,
          "symbol": "state_records"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].pressure_unit_raw",
      "label": "原始压强单位",
      "path": "material_states[*].pressure_unit_raw",
      "group": "材料状态",
      "mode": "fact",
      "read": "与原始压强同一来源的单位。",
      "checks": [
        "单位未知时保留缺失，不猜GPa；单位变更会改变标准量依赖。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先区分物性测量/计算压强、材料稳定区间和结构表压力，不按相同材料名合并。",
        "检查pressure_raw与pressure_unit_raw，确认单位换算与范围表示；不要取范围端点冒充单值。",
        "错挂状态时修正当前记录所属条件，再按真实依赖复核，不恢复整份旧草稿。"
      ],
      "example": "例：原始压强单位改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 164,
          "symbol": "state_records"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].temperature_raw",
      "label": "原始温度",
      "path": "material_states[*].temperature_raw",
      "group": "材料状态",
      "mode": "fact",
      "read": "本文实际测量或计算状态的温度。",
      "checks": [
        "不把退火温度或合成温度误挂到物性测量状态。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：原始温度改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 164,
          "symbol": "state_records"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].temperature_unit_raw",
      "label": "原始温度单位",
      "path": "material_states[*].temperature_unit_raw",
      "group": "材料状态",
      "mode": "fact",
      "read": "与原始温度绑定的单位。",
      "checks": [
        "未报告单位不猜测，换算依赖本字段。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：原始温度单位改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 164,
          "symbol": "state_records"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].calculation_context",
      "label": "状态级计算条件（兼容入口）",
      "path": "material_states[*].calculation_context",
      "group": "材料状态",
      "mode": "condition",
      "read": "历史状态级计算上下文。",
      "checks": [
        "独立字段拆分会继续拆到实际叶子；不能用整组对象通过覆盖全部子项。",
        "实际新物性条件优先归对应记录与计算阶段。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先检查此参数所属材料、物相、软件和计算阶段，回看同一表行/表注或Methods原句。",
        "查看scientific_context.json中的关联、fact_evidences、scope_evidences与gaps，以及condition_window/rule_review是否完整且当前有效。",
        "原文未报告则留空；泛函尤其不得从另一软件推算。若阶段或软件错误，修正关联范围，不把所有条件一起重置。"
      ],
      "example": "例：状态级计算条件（兼容入口）改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "条件化程序规则",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 164,
          "symbol": "state_records"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].experimental_context",
      "label": "状态级实验条件（兼容入口）",
      "path": "material_states[*].experimental_context",
      "group": "材料状态",
      "mode": "fact",
      "read": "历史状态级实验上下文。",
      "checks": [
        "同样按现有键分解核对，不把整个条件块视为一个免审字段。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：状态级实验条件（兼容入口）改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 164,
          "symbol": "state_records"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].element_count",
      "label": "元素种类数",
      "path": "material_states[*].element_count",
      "group": "材料状态",
      "mode": "semantic",
      "read": "从当前完整化学式提取不同元素集合。",
      "checks": [
        "模型结合当前原文、计算及查表依据查证，不因派生而跳过。",
        "核对当前材料、压力及具体结果，保存并复用通过结论。"
      ],
      "dependencies": [
        "当前状态的 material 化学式；无化学式则依据实际断言来源。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先检查当前完整化学式是否解析正确，例如括号分组和Unicode下标。",
        "有化学式时修正输入并重新计算元素集合；无化学式时核对元素数断言来源，不伪造公式让它成为派生通过。"
      ],
      "example": "例：CaH6 的元素种类是Ca与H两种，不是7个原子。",
      "scope": "条件化程序规则",
      "errorCodes": [
        "unchecked",
        "来源输入未通过"
      ],
      "failureRoute": "检查真实输入；不满足则不能当派生通过",
      "sources": [
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 164,
          "symbol": "state_records"
        },
        {
          "path": "backend/ingest/scientific_drafts.py",
          "line": 19,
          "symbol": "count_formula_elements（导入入口）"
        }
      ]
    },
    {
      "id": "material_states[*].structure / structure_candidates[*].structure_text",
      "label": "晶体结构文件及归属",
      "path": "material_states[*].structure / structure_candidates[*].structure_text",
      "group": "晶体结构",
      "mode": "structure",
      "read": "原文完整结构表、原始CIF/POSCAR附件或已确认的结构候选。",
      "checks": [
        "完整可建模才保留模型，缺关键参数或原子位置的观测不当作完整结构。",
        "解析结构格式和哈希；上传候选需分配到状态并确认。",
        "验证文件真实性不等于证明物理模型对当前材料状态适用。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：只给空间群和晶格常数、没有原子位置，不应自动建成完整可下载结构。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留候选，处理结构完整性与归属",
      "sources": [
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 260,
          "symbol": "structure_record"
        },
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 307,
          "symbol": "augment_upload"
        },
        {
          "path": "backend/services/structure_candidates.py",
          "line": 108,
          "symbol": "validate_structure_text"
        }
      ]
    },
    {
      "id": "structure.structure_format",
      "label": "结构格式",
      "path": "structure.structure_format",
      "group": "晶体结构",
      "mode": "structure-part",
      "read": "已解析且有明确来源的同一结构文件。",
      "checks": [
        "按实际CIF/POSCAR解析，不能把POSCAR原文当作CIF。",
        "明确拆出的体积、原子数与晶格参数依赖结构文件核对；其他内部展示量不凭名称冒充独立字段审核。"
      ],
      "dependencies": [
        "同一结构文件、状态归属及当前结构哈希。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：结构格式改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "整体结构或依赖结构的派生量",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "回到当前结构文件核对",
      "sources": [
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 260,
          "symbol": "structure_record"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        }
      ]
    },
    {
      "id": "structure.structure_hash",
      "label": "规范结构哈希",
      "path": "structure.structure_hash",
      "group": "晶体结构",
      "mode": "structure-part",
      "read": "已解析且有明确来源的同一结构文件。",
      "checks": [
        "由结构规范表示计算，不信任浏览器自报哈希。",
        "明确拆出的体积、原子数与晶格参数依赖结构文件核对；其他内部展示量不凭名称冒充独立字段审核。"
      ],
      "dependencies": [
        "同一结构文件、状态归属及当前结构哈希。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：规范结构哈希改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "整体结构或依赖结构的派生量",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "回到当前结构文件核对",
      "sources": [
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 260,
          "symbol": "structure_record"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        }
      ]
    },
    {
      "id": "structure.volume",
      "label": "晶胞体积",
      "path": "structure.volume",
      "group": "晶体结构",
      "mode": "structure-part",
      "read": "已解析且有明确来源的同一结构文件。",
      "checks": [
        "由解析后的同一结构计算，与结构文件结果绑定。",
        "明确拆出的体积、原子数与晶格参数依赖结构文件核对；其他内部展示量不凭名称冒充独立字段审核。"
      ],
      "dependencies": [
        "同一结构文件、状态归属及当前结构哈希。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：晶胞体积改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "整体结构或依赖结构的派生量",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "回到当前结构文件核对",
      "sources": [
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 260,
          "symbol": "structure_record"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        }
      ]
    },
    {
      "id": "structure.atom_count",
      "label": "原胞 / 晶胞原子数",
      "path": "structure.atom_count",
      "group": "晶体结构",
      "mode": "structure-part",
      "read": "已解析且有明确来源的同一结构文件。",
      "checks": [
        "从当前结构表示读取原子数；不把化学式比例直接当原胞N。",
        "明确拆出的体积、原子数与晶格参数依赖结构文件核对；其他内部展示量不凭名称冒充独立字段审核。"
      ],
      "dependencies": [
        "同一结构文件、状态归属及当前结构哈希。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：原胞 / 晶胞原子数改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "整体结构或依赖结构的派生量",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "回到当前结构文件核对",
      "sources": [
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 260,
          "symbol": "structure_record"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        }
      ]
    },
    {
      "id": "structure.elements",
      "label": "结构元素集合",
      "path": "structure.elements",
      "group": "晶体结构",
      "mode": "structure-part",
      "read": "已解析且有明确来源的同一结构文件。",
      "checks": [
        "从结构文件原子元素读取，与材料化学式的组成语义分别检查。",
        "明确拆出的体积、原子数与晶格参数依赖结构文件核对；其他内部展示量不凭名称冒充独立字段审核。"
      ],
      "dependencies": [
        "同一结构文件、状态归属及当前结构哈希。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：结构元素集合改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "整体结构或依赖结构的派生量",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "回到当前结构文件核对",
      "sources": [
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 260,
          "symbol": "structure_record"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        }
      ]
    },
    {
      "id": "structure.cell_matrix",
      "label": "晶格矩阵",
      "path": "structure.cell_matrix",
      "group": "晶体结构",
      "mode": "structure-part",
      "read": "已解析且有明确来源的同一结构文件。",
      "checks": [
        "从结构模型的当前晶胞表示读取，不独立向模型猜矩阵。",
        "明确拆出的体积、原子数与晶格参数依赖结构文件核对；其他内部展示量不凭名称冒充独立字段审核。"
      ],
      "dependencies": [
        "同一结构文件、状态归属及当前结构哈希。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：晶格矩阵改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "整体结构或依赖结构的派生量",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "回到当前结构文件核对",
      "sources": [
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 260,
          "symbol": "structure_record"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        }
      ]
    },
    {
      "id": "structure.fractional_positions",
      "label": "原子分数坐标",
      "path": "structure.fractional_positions",
      "group": "晶体结构",
      "mode": "structure-part",
      "read": "已解析且有明确来源的同一结构文件。",
      "checks": [
        "坐标作为结构整体几何的一部分，不按每个原子独立发LLM请求。",
        "明确拆出的体积、原子数与晶格参数依赖结构文件核对；其他内部展示量不凭名称冒充独立字段审核。"
      ],
      "dependencies": [
        "同一结构文件、状态归属及当前结构哈希。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：原子分数坐标改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "整体结构或依赖结构的派生量",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "回到当前结构文件核对",
      "sources": [
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 260,
          "symbol": "structure_record"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        }
      ]
    },
    {
      "id": "structure.cell_parameters.a",
      "label": "晶格常数 a",
      "path": "structure.cell_parameters.a",
      "group": "晶体结构",
      "mode": "structure-part",
      "read": "当前规范结构文件的解析晶格参数。",
      "checks": [
        "作为明确结构派生子项保存独立身份，dependency 指向结构文件。",
        "参数数值与晶胞表示绑定；结构输入变化后需重新解析。"
      ],
      "dependencies": [
        "结构文件及其当前表示，不是另一个不相关模型。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：晶格常数 a改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "回到当前结构文件核对",
      "sources": [
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 260,
          "symbol": "structure_record"
        }
      ]
    },
    {
      "id": "structure.cell_parameters.b",
      "label": "晶格常数 b",
      "path": "structure.cell_parameters.b",
      "group": "晶体结构",
      "mode": "structure-part",
      "read": "当前规范结构文件的解析晶格参数。",
      "checks": [
        "作为明确结构派生子项保存独立身份，dependency 指向结构文件。",
        "参数数值与晶胞表示绑定；结构输入变化后需重新解析。"
      ],
      "dependencies": [
        "结构文件及其当前表示，不是另一个不相关模型。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：晶格常数 b改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "回到当前结构文件核对",
      "sources": [
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 260,
          "symbol": "structure_record"
        }
      ]
    },
    {
      "id": "structure.cell_parameters.c",
      "label": "晶格常数 c",
      "path": "structure.cell_parameters.c",
      "group": "晶体结构",
      "mode": "structure-part",
      "read": "当前规范结构文件的解析晶格参数。",
      "checks": [
        "作为明确结构派生子项保存独立身份，dependency 指向结构文件。",
        "参数数值与晶胞表示绑定；结构输入变化后需重新解析。"
      ],
      "dependencies": [
        "结构文件及其当前表示，不是另一个不相关模型。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：晶格常数 c改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "回到当前结构文件核对",
      "sources": [
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 260,
          "symbol": "structure_record"
        }
      ]
    },
    {
      "id": "structure.cell_parameters.alpha",
      "label": "晶格角 α",
      "path": "structure.cell_parameters.alpha",
      "group": "晶体结构",
      "mode": "structure-part",
      "read": "当前规范结构文件的解析晶格参数。",
      "checks": [
        "作为明确结构派生子项保存独立身份，dependency 指向结构文件。",
        "参数数值与晶胞表示绑定；结构输入变化后需重新解析。"
      ],
      "dependencies": [
        "结构文件及其当前表示，不是另一个不相关模型。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：晶格角 α改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "回到当前结构文件核对",
      "sources": [
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 260,
          "symbol": "structure_record"
        }
      ]
    },
    {
      "id": "structure.cell_parameters.beta",
      "label": "晶格角 β",
      "path": "structure.cell_parameters.beta",
      "group": "晶体结构",
      "mode": "structure-part",
      "read": "当前规范结构文件的解析晶格参数。",
      "checks": [
        "作为明确结构派生子项保存独立身份，dependency 指向结构文件。",
        "参数数值与晶胞表示绑定；结构输入变化后需重新解析。"
      ],
      "dependencies": [
        "结构文件及其当前表示，不是另一个不相关模型。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：晶格角 β改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "回到当前结构文件核对",
      "sources": [
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 260,
          "symbol": "structure_record"
        }
      ]
    },
    {
      "id": "structure.cell_parameters.gamma",
      "label": "晶格角 γ",
      "path": "structure.cell_parameters.gamma",
      "group": "晶体结构",
      "mode": "structure-part",
      "read": "当前规范结构文件的解析晶格参数。",
      "checks": [
        "作为明确结构派生子项保存独立身份，dependency 指向结构文件。",
        "参数数值与晶胞表示绑定；结构输入变化后需重新解析。"
      ],
      "dependencies": [
        "结构文件及其当前表示，不是另一个不相关模型。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：晶格角 γ改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "回到当前结构文件核对",
      "sources": [
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/scientific_evidence.py",
          "line": 260,
          "symbol": "structure_record"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[electronic_properties].records[*].name_raw",
      "label": "电子性质 · 性质名称",
      "path": "material_states[*].property_modules[electronic_properties].records[*].name_raw",
      "group": "电子性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "名称需与实际物理量一致，不能把不同量仅因单位相近合并。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 电子性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[electronic_properties].records[*].value_kind",
      "label": "电子性质 · 值类型",
      "path": "material_states[*].property_modules[electronic_properties].records[*].value_kind",
      "group": "电子性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "number / range / text / boolean 与实际规范值槽位必须一致；不能标量和范围同时启用。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 电子性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[electronic_properties].records[*].value_raw",
      "label": "电子性质 · 原始值",
      "path": "material_states[*].property_modules[electronic_properties].records[*].value_raw",
      "group": "电子性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "保留原始文字或数值表达，不用方法描述替代科学结果。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 电子性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[electronic_properties].records[*].value_number",
      "label": "电子性质 · 单值",
      "path": "material_states[*].property_modules[electronic_properties].records[*].value_number",
      "group": "电子性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "仅在number表示时使用；核对同一材料、条件与量纲下的数值。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 电子性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[electronic_properties].records[*].value_min",
      "label": "电子性质 · 范围下界",
      "path": "material_states[*].property_modules[electronic_properties].records[*].value_min",
      "group": "电子性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "range需同时有两端且下界不大于上界；不把不同物理条件下的数值拼成一个范围。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 电子性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[electronic_properties].records[*].value_max",
      "label": "电子性质 · 范围上界",
      "path": "material_states[*].property_modules[electronic_properties].records[*].value_max",
      "group": "电子性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "与下界同一条记录、同一物理量，不能跨条件拼范围。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 电子性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[electronic_properties].records[*].value_text",
      "label": "电子性质 · 文本结果",
      "path": "material_states[*].property_modules[electronic_properties].records[*].value_text",
      "group": "电子性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "只用于文本型结果，不把计算方程名称填成Tc结果。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 电子性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[electronic_properties].records[*].value_boolean",
      "label": "电子性质 · 布尔结果",
      "path": "material_states[*].property_modules[electronic_properties].records[*].value_boolean",
      "group": "电子性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "仅用于boolean语义，不能把unknown强行写false。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 电子性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[electronic_properties].records[*].uncertainty",
      "label": "电子性质 · 不确定度",
      "path": "material_states[*].property_modules[electronic_properties].records[*].uncertainty",
      "group": "电子性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "有值时不可为负；保留原文定义与置信或误差含义。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 电子性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[electronic_properties].records[*].unit_raw",
      "label": "电子性质 · 原始单位",
      "path": "material_states[*].property_modules[electronic_properties].records[*].unit_raw",
      "group": "电子性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "与原始值及归一化口径绑定，不能丢掉per spin、per atom或per volume。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 电子性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[electronic_properties].records[*].canonical_unit",
      "label": "电子性质 · 规范单位",
      "path": "material_states[*].property_modules[electronic_properties].records[*].canonical_unit",
      "group": "电子性质",
      "mode": "metadata",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "由当前定义及换算语义管理；Tc要求K，不能任意把原单位文字替换成规范值。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "例：同一状态的 电子性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[electronic_properties].records[*].method_code",
      "label": "电子性质 · 方法代码",
      "path": "material_states[*].property_modules[electronic_properties].records[*].method_code",
      "group": "电子性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "使用当前记录类型及发布定义允许的方法，不猜测缺失方法。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 电子性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[electronic_properties].records[*].method_raw",
      "label": "电子性质 · 原文方法名",
      "path": "material_states[*].property_modules[electronic_properties].records[*].method_raw",
      "group": "电子性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "保存原文表述，与代码枚举分开，未知枚举仍保留原文。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 电子性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[electronic_properties].records[*].criterion_code",
      "label": "电子性质 · 判据代码",
      "path": "material_states[*].property_modules[electronic_properties].records[*].criterion_code",
      "group": "电子性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "只用适用的判据；实验电阻起始、零电阻等不可混为同一Tc。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 电子性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[electronic_properties].records[*].criterion_raw",
      "label": "电子性质 · 原始判据说明",
      "path": "material_states[*].property_modules[electronic_properties].records[*].criterion_raw",
      "group": "电子性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "保留原文判据及上下文，不由方法名称推出判据。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 电子性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[dynamical_properties].records[*].name_raw",
      "label": "动力学性质 · 性质名称",
      "path": "material_states[*].property_modules[dynamical_properties].records[*].name_raw",
      "group": "动力学性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "名称需与实际物理量一致，不能把不同量仅因单位相近合并。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 动力学性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[dynamical_properties].records[*].value_kind",
      "label": "动力学性质 · 值类型",
      "path": "material_states[*].property_modules[dynamical_properties].records[*].value_kind",
      "group": "动力学性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "number / range / text / boolean 与实际规范值槽位必须一致；不能标量和范围同时启用。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 动力学性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[dynamical_properties].records[*].value_raw",
      "label": "动力学性质 · 原始值",
      "path": "material_states[*].property_modules[dynamical_properties].records[*].value_raw",
      "group": "动力学性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "保留原始文字或数值表达，不用方法描述替代科学结果。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 动力学性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[dynamical_properties].records[*].value_number",
      "label": "动力学性质 · 单值",
      "path": "material_states[*].property_modules[dynamical_properties].records[*].value_number",
      "group": "动力学性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "仅在number表示时使用；核对同一材料、条件与量纲下的数值。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 动力学性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[dynamical_properties].records[*].value_min",
      "label": "动力学性质 · 范围下界",
      "path": "material_states[*].property_modules[dynamical_properties].records[*].value_min",
      "group": "动力学性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "range需同时有两端且下界不大于上界；不把不同物理条件下的数值拼成一个范围。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 动力学性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[dynamical_properties].records[*].value_max",
      "label": "动力学性质 · 范围上界",
      "path": "material_states[*].property_modules[dynamical_properties].records[*].value_max",
      "group": "动力学性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "与下界同一条记录、同一物理量，不能跨条件拼范围。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 动力学性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[dynamical_properties].records[*].value_text",
      "label": "动力学性质 · 文本结果",
      "path": "material_states[*].property_modules[dynamical_properties].records[*].value_text",
      "group": "动力学性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "只用于文本型结果，不把计算方程名称填成Tc结果。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 动力学性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[dynamical_properties].records[*].value_boolean",
      "label": "动力学性质 · 布尔结果",
      "path": "material_states[*].property_modules[dynamical_properties].records[*].value_boolean",
      "group": "动力学性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "仅用于boolean语义，不能把unknown强行写false。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 动力学性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[dynamical_properties].records[*].uncertainty",
      "label": "动力学性质 · 不确定度",
      "path": "material_states[*].property_modules[dynamical_properties].records[*].uncertainty",
      "group": "动力学性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "有值时不可为负；保留原文定义与置信或误差含义。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 动力学性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[dynamical_properties].records[*].unit_raw",
      "label": "动力学性质 · 原始单位",
      "path": "material_states[*].property_modules[dynamical_properties].records[*].unit_raw",
      "group": "动力学性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "与原始值及归一化口径绑定，不能丢掉per spin、per atom或per volume。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 动力学性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[dynamical_properties].records[*].canonical_unit",
      "label": "动力学性质 · 规范单位",
      "path": "material_states[*].property_modules[dynamical_properties].records[*].canonical_unit",
      "group": "动力学性质",
      "mode": "metadata",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "由当前定义及换算语义管理；Tc要求K，不能任意把原单位文字替换成规范值。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "例：同一状态的 动力学性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[dynamical_properties].records[*].method_code",
      "label": "动力学性质 · 方法代码",
      "path": "material_states[*].property_modules[dynamical_properties].records[*].method_code",
      "group": "动力学性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "使用当前记录类型及发布定义允许的方法，不猜测缺失方法。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 动力学性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[dynamical_properties].records[*].method_raw",
      "label": "动力学性质 · 原文方法名",
      "path": "material_states[*].property_modules[dynamical_properties].records[*].method_raw",
      "group": "动力学性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "保存原文表述，与代码枚举分开，未知枚举仍保留原文。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 动力学性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[dynamical_properties].records[*].criterion_code",
      "label": "动力学性质 · 判据代码",
      "path": "material_states[*].property_modules[dynamical_properties].records[*].criterion_code",
      "group": "动力学性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "只用适用的判据；实验电阻起始、零电阻等不可混为同一Tc。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 动力学性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[dynamical_properties].records[*].criterion_raw",
      "label": "动力学性质 · 原始判据说明",
      "path": "material_states[*].property_modules[dynamical_properties].records[*].criterion_raw",
      "group": "动力学性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "保留原文判据及上下文，不由方法名称推出判据。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 动力学性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[thermodynamical_properties].records[*].name_raw",
      "label": "热力学性质 · 性质名称",
      "path": "material_states[*].property_modules[thermodynamical_properties].records[*].name_raw",
      "group": "热力学性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "名称需与实际物理量一致，不能把不同量仅因单位相近合并。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 热力学性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[thermodynamical_properties].records[*].value_kind",
      "label": "热力学性质 · 值类型",
      "path": "material_states[*].property_modules[thermodynamical_properties].records[*].value_kind",
      "group": "热力学性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "number / range / text / boolean 与实际规范值槽位必须一致；不能标量和范围同时启用。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 热力学性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[thermodynamical_properties].records[*].value_raw",
      "label": "热力学性质 · 原始值",
      "path": "material_states[*].property_modules[thermodynamical_properties].records[*].value_raw",
      "group": "热力学性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "保留原始文字或数值表达，不用方法描述替代科学结果。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 热力学性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[thermodynamical_properties].records[*].value_number",
      "label": "热力学性质 · 单值",
      "path": "material_states[*].property_modules[thermodynamical_properties].records[*].value_number",
      "group": "热力学性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "仅在number表示时使用；核对同一材料、条件与量纲下的数值。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 热力学性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[thermodynamical_properties].records[*].value_min",
      "label": "热力学性质 · 范围下界",
      "path": "material_states[*].property_modules[thermodynamical_properties].records[*].value_min",
      "group": "热力学性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "range需同时有两端且下界不大于上界；不把不同物理条件下的数值拼成一个范围。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 热力学性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[thermodynamical_properties].records[*].value_max",
      "label": "热力学性质 · 范围上界",
      "path": "material_states[*].property_modules[thermodynamical_properties].records[*].value_max",
      "group": "热力学性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "与下界同一条记录、同一物理量，不能跨条件拼范围。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 热力学性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[thermodynamical_properties].records[*].value_text",
      "label": "热力学性质 · 文本结果",
      "path": "material_states[*].property_modules[thermodynamical_properties].records[*].value_text",
      "group": "热力学性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "只用于文本型结果，不把计算方程名称填成Tc结果。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 热力学性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[thermodynamical_properties].records[*].value_boolean",
      "label": "热力学性质 · 布尔结果",
      "path": "material_states[*].property_modules[thermodynamical_properties].records[*].value_boolean",
      "group": "热力学性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "仅用于boolean语义，不能把unknown强行写false。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 热力学性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[thermodynamical_properties].records[*].uncertainty",
      "label": "热力学性质 · 不确定度",
      "path": "material_states[*].property_modules[thermodynamical_properties].records[*].uncertainty",
      "group": "热力学性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "有值时不可为负；保留原文定义与置信或误差含义。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 热力学性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[thermodynamical_properties].records[*].unit_raw",
      "label": "热力学性质 · 原始单位",
      "path": "material_states[*].property_modules[thermodynamical_properties].records[*].unit_raw",
      "group": "热力学性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "与原始值及归一化口径绑定，不能丢掉per spin、per atom或per volume。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 热力学性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[thermodynamical_properties].records[*].canonical_unit",
      "label": "热力学性质 · 规范单位",
      "path": "material_states[*].property_modules[thermodynamical_properties].records[*].canonical_unit",
      "group": "热力学性质",
      "mode": "metadata",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "由当前定义及换算语义管理；Tc要求K，不能任意把原单位文字替换成规范值。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "例：同一状态的 热力学性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[thermodynamical_properties].records[*].method_code",
      "label": "热力学性质 · 方法代码",
      "path": "material_states[*].property_modules[thermodynamical_properties].records[*].method_code",
      "group": "热力学性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "使用当前记录类型及发布定义允许的方法，不猜测缺失方法。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 热力学性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[thermodynamical_properties].records[*].method_raw",
      "label": "热力学性质 · 原文方法名",
      "path": "material_states[*].property_modules[thermodynamical_properties].records[*].method_raw",
      "group": "热力学性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "保存原文表述，与代码枚举分开，未知枚举仍保留原文。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 热力学性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[thermodynamical_properties].records[*].criterion_code",
      "label": "热力学性质 · 判据代码",
      "path": "material_states[*].property_modules[thermodynamical_properties].records[*].criterion_code",
      "group": "热力学性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "只用适用的判据；实验电阻起始、零电阻等不可混为同一Tc。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 热力学性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[thermodynamical_properties].records[*].criterion_raw",
      "label": "热力学性质 · 原始判据说明",
      "path": "material_states[*].property_modules[thermodynamical_properties].records[*].criterion_raw",
      "group": "热力学性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "保留原文判据及上下文，不由方法名称推出判据。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 热力学性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[superconductive_properties].records[*].name_raw",
      "label": "超导性质 · 性质名称",
      "path": "material_states[*].property_modules[superconductive_properties].records[*].name_raw",
      "group": "超导性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "名称需与实际物理量一致，不能把不同量仅因单位相近合并。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 超导性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[superconductive_properties].records[*].value_kind",
      "label": "超导性质 · 值类型",
      "path": "material_states[*].property_modules[superconductive_properties].records[*].value_kind",
      "group": "超导性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "number / range / text / boolean 与实际规范值槽位必须一致；不能标量和范围同时启用。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 超导性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[superconductive_properties].records[*].value_raw",
      "label": "超导性质 · 原始值",
      "path": "material_states[*].property_modules[superconductive_properties].records[*].value_raw",
      "group": "超导性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "保留原始文字或数值表达，不用方法描述替代科学结果。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 超导性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[superconductive_properties].records[*].value_number",
      "label": "超导性质 · 单值",
      "path": "material_states[*].property_modules[superconductive_properties].records[*].value_number",
      "group": "超导性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "仅在number表示时使用；核对同一材料、条件与量纲下的数值。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 超导性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[superconductive_properties].records[*].value_min",
      "label": "超导性质 · 范围下界",
      "path": "material_states[*].property_modules[superconductive_properties].records[*].value_min",
      "group": "超导性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "range需同时有两端且下界不大于上界；不把不同物理条件下的数值拼成一个范围。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 超导性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[superconductive_properties].records[*].value_max",
      "label": "超导性质 · 范围上界",
      "path": "material_states[*].property_modules[superconductive_properties].records[*].value_max",
      "group": "超导性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "与下界同一条记录、同一物理量，不能跨条件拼范围。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 超导性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[superconductive_properties].records[*].value_text",
      "label": "超导性质 · 文本结果",
      "path": "material_states[*].property_modules[superconductive_properties].records[*].value_text",
      "group": "超导性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "只用于文本型结果，不把计算方程名称填成Tc结果。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 超导性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[superconductive_properties].records[*].value_boolean",
      "label": "超导性质 · 布尔结果",
      "path": "material_states[*].property_modules[superconductive_properties].records[*].value_boolean",
      "group": "超导性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "仅用于boolean语义，不能把unknown强行写false。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 超导性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[superconductive_properties].records[*].uncertainty",
      "label": "超导性质 · 不确定度",
      "path": "material_states[*].property_modules[superconductive_properties].records[*].uncertainty",
      "group": "超导性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "有值时不可为负；保留原文定义与置信或误差含义。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 超导性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[superconductive_properties].records[*].unit_raw",
      "label": "超导性质 · 原始单位",
      "path": "material_states[*].property_modules[superconductive_properties].records[*].unit_raw",
      "group": "超导性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "与原始值及归一化口径绑定，不能丢掉per spin、per atom或per volume。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 超导性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[superconductive_properties].records[*].canonical_unit",
      "label": "超导性质 · 规范单位",
      "path": "material_states[*].property_modules[superconductive_properties].records[*].canonical_unit",
      "group": "超导性质",
      "mode": "metadata",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "由当前定义及换算语义管理；Tc要求K，不能任意把原单位文字替换成规范值。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "例：同一状态的 超导性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[superconductive_properties].records[*].method_code",
      "label": "超导性质 · 方法代码",
      "path": "material_states[*].property_modules[superconductive_properties].records[*].method_code",
      "group": "超导性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "使用当前记录类型及发布定义允许的方法，不猜测缺失方法。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 超导性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[superconductive_properties].records[*].method_raw",
      "label": "超导性质 · 原文方法名",
      "path": "material_states[*].property_modules[superconductive_properties].records[*].method_raw",
      "group": "超导性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "保存原文表述，与代码枚举分开，未知枚举仍保留原文。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 超导性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[superconductive_properties].records[*].criterion_code",
      "label": "超导性质 · 判据代码",
      "path": "material_states[*].property_modules[superconductive_properties].records[*].criterion_code",
      "group": "超导性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "只用适用的判据；实验电阻起始、零电阻等不可混为同一Tc。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 超导性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "material_states[*].property_modules[superconductive_properties].records[*].criterion_raw",
      "label": "超导性质 · 原始判据说明",
      "path": "material_states[*].property_modules[superconductive_properties].records[*].criterion_raw",
      "group": "超导性质",
      "mode": "fact",
      "read": "当前模块的具体记录及绑定的原文、方法和材料状态。",
      "checks": [
        "保留原文判据及上下文，不由方法名称推出判据。",
        "共享记录不变量和发布的定义版本先做程序检查；科学含义由实际独立叶子断言核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：同一状态的 超导性质 名称改变，不应把其他状态的全部数值、单位核对清空。",
      "scope": "明确记录叶子；适用性取决于记录类型",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 181,
          "symbol": "_validate_value_shape"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_evidence.py",
          "line": 500,
          "symbol": "checked_result"
        }
      ]
    },
    {
      "id": "electronic_properties.records[property_code=band_gap]",
      "label": "带隙 Eg / band gap",
      "path": "electronic_properties.records[property_code=band_gap]",
      "group": "电子性质",
      "mode": "fact",
      "read": "当前材料、压力、方法和结构状态下的带隙原文。",
      "checks": [
        "PDF自动提取支持band_gap，与N(EF)分开注册到电子性质。",
        "名称、值、值类型、单位及上下文分别展开核对，不能只给整条记录一个结论。",
        "当前通用代码不等于已经存在专门的带隙物理求解器。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：带隙记录里出现harmonic字段，并不自动证明带隙计算采用谐波近似；应核查该字段是否真的适用。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/domain_extraction.py",
          "line": 22,
          "symbol": "canonical_electronic_property"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        }
      ]
    },
    {
      "id": "electronic_properties.records[property_code=dos_fermi]",
      "label": "费米能级态密度 N(EF) / DOS",
      "path": "electronic_properties.records[property_code=dos_fermi]",
      "group": "电子性质",
      "mode": "fact",
      "read": "本文不同位置的DOS原始记录、单位、归一化与自旋口径。",
      "checks": [
        "同一状态只保留一个当前DOS记录，多个来源原值进入来源归档。",
        "数值、单位、per spin和归一化不一致保留冲突，不能简单平均或覆盖。",
        "当前值为空可能是待选择来源的合法中间状态，不等于模型认为DOS为零。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "两个原文来源数值或单位口径不同。",
        "来源归档格式不合法或当前选择尚未明确。"
      ],
      "fixes": [
        "在DOS来源侧栏逐项比较当前值、原始数值和单位口径。",
        "明确采用的当前值并保存依据，不删除其他原始来源。"
      ],
      "example": "例：states/eV/spin 与 states/eV 的数值不同，不能直接当成同一个科学数值。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/fermi_dos.py",
          "line": 58,
          "symbol": "has_conflict"
        },
        {
          "path": "backend/ingest/fermi_dos.py",
          "line": 67,
          "symbol": "normalize_records"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        }
      ]
    },
    {
      "id": "predicted_tc.value_number",
      "label": "预测 Tc 单点",
      "path": "predicted_tc.value_number",
      "group": "超导性质",
      "mode": "fact",
      "read": "本文对应压力、方法、核处理、表行及表注中的预测结果。",
      "checks": [
        "每个Tc按本记录方法和μ*配对核对。",
        "共享组内λ/ωlog/条件可共用稳定身份；Tc与μ*按点身份独立核对。"
      ],
      "dependencies": [
        "当前状态的材料、压力、温度、物相等真实输入。",
        "Tc和μ*配对；λ/ωlog引用本记录EPC软件与适用条件，不依赖无关优化元数据。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "按记录稳定身份和当前方法找到原文表行，逐点比较Tc–μ*配对及该组λ/ωlog。",
        "检查value_kind与实际值槽位、tc_group/point_key及property_field_review的实际路径；不要只因数组前移把结果移给另一点。",
        "只修改当前错误点或真正共用条件，再保存说明并核对所影响字段，其他通过结果保留。"
      ],
      "example": "例：同一方法下两组Tc–μ*是两个结果点，不允许只保留高Tc或把端点与μ*配反。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 85,
          "symbol": "expand_property_fields"
        },
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 34,
          "symbol": "review_context"
        },
        {
          "path": "backend/ingest/tc_parameters.py",
          "line": 6,
          "symbol": "parameter_issues"
        },
        {
          "path": "backend/ingest/review_dependencies.py",
          "line": 32,
          "symbol": "record_inputs"
        }
      ]
    },
    {
      "id": "predicted_tc.value_min",
      "label": "预测 Tc 范围第一端",
      "path": "predicted_tc.value_min",
      "group": "超导性质",
      "mode": "fact",
      "read": "本文对应压力、方法、核处理、表行及表注中的预测结果。",
      "checks": [
        "需要结合原文Tc–μ*反向配对，不能按名字max/min猜测μ*端点。",
        "共享组内λ/ωlog/条件可共用稳定身份；Tc与μ*按点身份独立核对。"
      ],
      "dependencies": [
        "当前状态的材料、压力、温度、物相等真实输入。",
        "Tc和μ*配对；λ/ωlog引用本记录EPC软件与适用条件，不依赖无关优化元数据。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "按记录稳定身份和当前方法找到原文表行，逐点比较Tc–μ*配对及该组λ/ωlog。",
        "检查value_kind与实际值槽位、tc_group/point_key及property_field_review的实际路径；不要只因数组前移把结果移给另一点。",
        "只修改当前错误点或真正共用条件，再保存说明并核对所影响字段，其他通过结果保留。"
      ],
      "example": "例：同一方法下两组Tc–μ*是两个结果点，不允许只保留高Tc或把端点与μ*配反。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 85,
          "symbol": "expand_property_fields"
        },
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 34,
          "symbol": "review_context"
        },
        {
          "path": "backend/ingest/tc_parameters.py",
          "line": 6,
          "symbol": "parameter_issues"
        },
        {
          "path": "backend/ingest/review_dependencies.py",
          "line": 32,
          "symbol": "record_inputs"
        }
      ]
    },
    {
      "id": "predicted_tc.value_max",
      "label": "预测 Tc 范围第二端",
      "path": "predicted_tc.value_max",
      "group": "超导性质",
      "mode": "fact",
      "read": "本文对应压力、方法、核处理、表行及表注中的预测结果。",
      "checks": [
        "与同一条记录的另一Tc端点共同核对，不能跨压力或方法拼接。",
        "共享组内λ/ωlog/条件可共用稳定身份；Tc与μ*按点身份独立核对。"
      ],
      "dependencies": [
        "当前状态的材料、压力、温度、物相等真实输入。",
        "Tc和μ*配对；λ/ωlog引用本记录EPC软件与适用条件，不依赖无关优化元数据。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "按记录稳定身份和当前方法找到原文表行，逐点比较Tc–μ*配对及该组λ/ωlog。",
        "检查value_kind与实际值槽位、tc_group/point_key及property_field_review的实际路径；不要只因数组前移把结果移给另一点。",
        "只修改当前错误点或真正共用条件，再保存说明并核对所影响字段，其他通过结果保留。"
      ],
      "example": "例：同一方法下两组Tc–μ*是两个结果点，不允许只保留高Tc或把端点与μ*配反。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 85,
          "symbol": "expand_property_fields"
        },
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 34,
          "symbol": "review_context"
        },
        {
          "path": "backend/ingest/tc_parameters.py",
          "line": 6,
          "symbol": "parameter_issues"
        },
        {
          "path": "backend/ingest/review_dependencies.py",
          "line": 32,
          "symbol": "record_inputs"
        }
      ]
    },
    {
      "id": "predicted_tc.method_code",
      "label": "预测 Tc 方法",
      "path": "predicted_tc.method_code",
      "group": "超导性质",
      "mode": "fact",
      "read": "本文对应压力、方法、核处理、表行及表注中的预测结果。",
      "checks": [
        "区分Allen–Dynes、McMillan、各向同性/各向异性Eliashberg、SCDFT等合法方法。",
        "共享组内λ/ωlog/条件可共用稳定身份；Tc与μ*按点身份独立核对。"
      ],
      "dependencies": [
        "当前状态的材料、压力、温度、物相等真实输入。",
        "Tc和μ*配对；λ/ωlog引用本记录EPC软件与适用条件，不依赖无关优化元数据。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "按记录稳定身份和当前方法找到原文表行，逐点比较Tc–μ*配对及该组λ/ωlog。",
        "检查value_kind与实际值槽位、tc_group/point_key及property_field_review的实际路径；不要只因数组前移把结果移给另一点。",
        "只修改当前错误点或真正共用条件，再保存说明并核对所影响字段，其他通过结果保留。"
      ],
      "example": "例：同一方法下两组Tc–μ*是两个结果点，不允许只保留高Tc或把端点与μ*配反。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 85,
          "symbol": "expand_property_fields"
        },
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 34,
          "symbol": "review_context"
        },
        {
          "path": "backend/ingest/tc_parameters.py",
          "line": 6,
          "symbol": "parameter_issues"
        },
        {
          "path": "backend/ingest/review_dependencies.py",
          "line": 32,
          "symbol": "record_inputs"
        }
      ]
    },
    {
      "id": "predicted_tc.payload.approximation",
      "label": "历史近似标签（原义待核对）",
      "path": "predicted_tc.payload.approximation",
      "group": "超导性质",
      "mode": "fact",
      "read": "只读取历史混装标签、原始响应和对应原句；新生成不使用此字段。",
      "checks": [
        "不把旧DFT改名成振动层次，也不把旧harmonic迁移成电子理论。",
        "电子数值与方法标签分别核对；不由错误标签否定正确数值，不升级为人工通过。"
      ],
      "dependencies": [
        "当前状态的材料、压力、温度、物相等真实输入。",
        "Tc和μ*配对；λ/ωlog引用本记录EPC软件与适用条件，不依赖无关优化元数据。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "新输入按电子理论、声子技术与振动处理分别填写；旧值及来源保留。",
        "只处理实际错误标签及必要依赖，不清空整条记录或整张材料卡。"
      ],
      "example": "例：同一方法下两组Tc–μ*是两个结果点，不允许只保留高Tc或把端点与μ*配反。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 85,
          "symbol": "expand_property_fields"
        },
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 34,
          "symbol": "review_context"
        },
        {
          "path": "backend/ingest/tc_parameters.py",
          "line": 6,
          "symbol": "parameter_issues"
        },
        {
          "path": "backend/ingest/review_dependencies.py",
          "line": 32,
          "symbol": "record_inputs"
        }
      ]
    },
    {
      "id": "predicted_tc.payload.parameters.lambda_ep",
      "label": "电声耦合强度 λ",
      "path": "predicted_tc.payload.parameters.lambda_ep",
      "group": "超导性质",
      "mode": "fact",
      "read": "本文对应压力、方法、核处理、表行及表注中的预测结果。",
      "checks": [
        "输入须为完整非负有限数值；以同一EPC工作流来源与范围核对。",
        "共享组内λ/ωlog/条件可共用稳定身份；Tc与μ*按点身份独立核对。"
      ],
      "dependencies": [
        "当前状态的材料、压力、温度、物相等真实输入。",
        "Tc和μ*配对；λ/ωlog引用本记录EPC软件与适用条件，不依赖无关优化元数据。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "按记录稳定身份和当前方法找到原文表行，逐点比较Tc–μ*配对及该组λ/ωlog。",
        "检查value_kind与实际值槽位、tc_group/point_key及property_field_review的实际路径；不要只因数组前移把结果移给另一点。",
        "只修改当前错误点或真正共用条件，再保存说明并核对所影响字段，其他通过结果保留。"
      ],
      "example": "例：同一方法下两组Tc–μ*是两个结果点，不允许只保留高Tc或把端点与μ*配反。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 85,
          "symbol": "expand_property_fields"
        },
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 34,
          "symbol": "review_context"
        },
        {
          "path": "backend/ingest/tc_parameters.py",
          "line": 6,
          "symbol": "parameter_issues"
        },
        {
          "path": "backend/ingest/review_dependencies.py",
          "line": 32,
          "symbol": "record_inputs"
        }
      ]
    },
    {
      "id": "predicted_tc.payload.parameters.omega_log",
      "label": "对数平均声子频率 ωlog",
      "path": "predicted_tc.payload.parameters.omega_log",
      "group": "超导性质",
      "mode": "fact",
      "read": "本文对应压力、方法、核处理、表行及表注中的预测结果。",
      "checks": [
        "完整非负有限值，保留实际单位并按当前口径转换；旧omega_log_k兼容但不并造两个参数。",
        "共享组内λ/ωlog/条件可共用稳定身份；Tc与μ*按点身份独立核对。"
      ],
      "dependencies": [
        "当前状态的材料、压力、温度、物相等真实输入。",
        "Tc和μ*配对；λ/ωlog引用本记录EPC软件与适用条件，不依赖无关优化元数据。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "按记录稳定身份和当前方法找到原文表行，逐点比较Tc–μ*配对及该组λ/ωlog。",
        "检查value_kind与实际值槽位、tc_group/point_key及property_field_review的实际路径；不要只因数组前移把结果移给另一点。",
        "只修改当前错误点或真正共用条件，再保存说明并核对所影响字段，其他通过结果保留。"
      ],
      "example": "例：同一方法下两组Tc–μ*是两个结果点，不允许只保留高Tc或把端点与μ*配反。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 85,
          "symbol": "expand_property_fields"
        },
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 34,
          "symbol": "review_context"
        },
        {
          "path": "backend/ingest/tc_parameters.py",
          "line": 6,
          "symbol": "parameter_issues"
        },
        {
          "path": "backend/ingest/review_dependencies.py",
          "line": 32,
          "symbol": "record_inputs"
        }
      ]
    },
    {
      "id": "predicted_tc.payload.parameters.mu_star",
      "label": "库仑赝势 μ*",
      "path": "predicted_tc.payload.parameters.mu_star",
      "group": "超导性质",
      "mode": "fact",
      "read": "本文对应压力、方法、核处理、表行及表注中的预测结果。",
      "checks": [
        "必须与当前Tc组合或区间端点正确配对，不把方法组共用参数误套到所有独立点。",
        "共享组内λ/ωlog/条件可共用稳定身份；Tc与μ*按点身份独立核对。"
      ],
      "dependencies": [
        "当前状态的材料、压力、温度、物相等真实输入。",
        "Tc和μ*配对；λ/ωlog引用本记录EPC软件与适用条件，不依赖无关优化元数据。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "按记录稳定身份和当前方法找到原文表行，逐点比较Tc–μ*配对及该组λ/ωlog。",
        "检查value_kind与实际值槽位、tc_group/point_key及property_field_review的实际路径；不要只因数组前移把结果移给另一点。",
        "只修改当前错误点或真正共用条件，再保存说明并核对所影响字段，其他通过结果保留。"
      ],
      "example": "例：同一方法下两组Tc–μ*是两个结果点，不允许只保留高Tc或把端点与μ*配反。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 85,
          "symbol": "expand_property_fields"
        },
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 34,
          "symbol": "review_context"
        },
        {
          "path": "backend/ingest/tc_parameters.py",
          "line": 6,
          "symbol": "parameter_issues"
        },
        {
          "path": "backend/ingest/review_dependencies.py",
          "line": 32,
          "symbol": "record_inputs"
        }
      ]
    },
    {
      "id": "measured_tc.value_number",
      "label": "测量 Tc",
      "path": "measured_tc.value_number",
      "group": "超导性质",
      "mode": "fact",
      "read": "对应实验样品、测量压力、磁场、方法与原文判据。",
      "checks": [
        "measured_tc使用experimental_conditions，不接受预测用calculation_conditions。",
        "Tc规范单位K；电阻、磁化率、比热等方法和onset/zero等判据分别保留。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：电阻开始下降温度与零电阻温度是不同判据，不能只取更高者。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        }
      ]
    },
    {
      "id": "measured_tc.method_code",
      "label": "测量方法",
      "path": "measured_tc.method_code",
      "group": "超导性质",
      "mode": "fact",
      "read": "对应实验样品、测量压力、磁场、方法与原文判据。",
      "checks": [
        "measured_tc使用experimental_conditions，不接受预测用calculation_conditions。",
        "Tc规范单位K；电阻、磁化率、比热等方法和onset/zero等判据分别保留。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：电阻开始下降温度与零电阻温度是不同判据，不能只取更高者。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        }
      ]
    },
    {
      "id": "measured_tc.criterion_code",
      "label": "测量 Tc 判据",
      "path": "measured_tc.criterion_code",
      "group": "超导性质",
      "mode": "fact",
      "read": "对应实验样品、测量压力、磁场、方法与原文判据。",
      "checks": [
        "measured_tc使用experimental_conditions，不接受预测用calculation_conditions。",
        "Tc规范单位K；电阻、磁化率、比热等方法和onset/zero等判据分别保留。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：电阻开始下降温度与零电阻温度是不同判据，不能只取更高者。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        }
      ]
    },
    {
      "id": "measured_tc.payload.experimental_conditions.description",
      "label": "实验 Conditions 描述",
      "path": "measured_tc.payload.experimental_conditions.description",
      "group": "超导性质",
      "mode": "fact",
      "read": "对应实验样品、测量压力、磁场、方法与原文判据。",
      "checks": [
        "measured_tc使用experimental_conditions，不接受预测用calculation_conditions。",
        "Tc规范单位K；电阻、磁化率、比热等方法和onset/zero等判据分别保留。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：电阻开始下降温度与零电阻温度是不同判据，不能只取更高者。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        }
      ]
    },
    {
      "id": "predicted_tc.payload.parameters.extensions[key=mu_star].value_min",
      "label": "μ* 范围下界",
      "path": "predicted_tc.payload.parameters.extensions[key=mu_star].value_min",
      "group": "超导性质",
      "mode": "fact",
      "read": "原文对μ*范围及其与Tc端点对应关系的明确陈述。",
      "checks": [
        "专用mu_star范围只在明确反向Tc–μ*对应时使用；其他报告范围不得强行解成配对。",
        "不能同时启用标量μ*和冲突的范围表示。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "按记录稳定身份和当前方法找到原文表行，逐点比较Tc–μ*配对及该组λ/ωlog。",
        "检查value_kind与实际值槽位、tc_group/point_key及property_field_review的实际路径；不要只因数组前移把结果移给另一点。",
        "只修改当前错误点或真正共用条件，再保存说明并核对所影响字段，其他通过结果保留。"
      ],
      "example": "例：μ* 范围下界改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/tc_parameters.py",
          "line": 6,
          "symbol": "parameter_issues"
        },
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 85,
          "symbol": "expand_property_fields"
        }
      ]
    },
    {
      "id": "predicted_tc.payload.parameters.extensions[key=mu_star].value_max",
      "label": "μ* 范围上界",
      "path": "predicted_tc.payload.parameters.extensions[key=mu_star].value_max",
      "group": "超导性质",
      "mode": "fact",
      "read": "原文对μ*范围及其与Tc端点对应关系的明确陈述。",
      "checks": [
        "专用mu_star范围只在明确反向Tc–μ*对应时使用；其他报告范围不得强行解成配对。",
        "不能同时启用标量μ*和冲突的范围表示。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "按记录稳定身份和当前方法找到原文表行，逐点比较Tc–μ*配对及该组λ/ωlog。",
        "检查value_kind与实际值槽位、tc_group/point_key及property_field_review的实际路径；不要只因数组前移把结果移给另一点。",
        "只修改当前错误点或真正共用条件，再保存说明并核对所影响字段，其他通过结果保留。"
      ],
      "example": "例：μ* 范围上界改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/tc_parameters.py",
          "line": 6,
          "symbol": "parameter_issues"
        },
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 85,
          "symbol": "expand_property_fields"
        }
      ]
    },
    {
      "id": "predicted_tc.payload.parameters.extensions[key=mu_star_reported_range].value_min / value_max",
      "label": "报告的 μ* 范围（非逐点配对）",
      "path": "predicted_tc.payload.parameters.extensions[key=mu_star_reported_range].value_min / value_max",
      "group": "超导性质",
      "mode": "fact",
      "read": "原文对μ*范围及其与Tc端点对应关系的明确陈述。",
      "checks": [
        "专用mu_star范围只在明确反向Tc–μ*对应时使用；其他报告范围不得强行解成配对。",
        "不能同时启用标量μ*和冲突的范围表示。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "按记录稳定身份和当前方法找到原文表行，逐点比较Tc–μ*配对及该组λ/ωlog。",
        "检查value_kind与实际值槽位、tc_group/point_key及property_field_review的实际路径；不要只因数组前移把结果移给另一点。",
        "只修改当前错误点或真正共用条件，再保存说明并核对所影响字段，其他通过结果保留。"
      ],
      "example": "例：报告的 μ* 范围（非逐点配对）改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "共用机制，非独立字段算法",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/tc_parameters.py",
          "line": 6,
          "symbol": "parameter_issues"
        },
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 85,
          "symbol": "expand_property_fields"
        }
      ]
    },
    {
      "id": "records[*].payload.calculation_conditions.calculation_code",
      "label": "计算软件",
      "path": "records[*].payload.calculation_conditions.calculation_code",
      "group": "计算条件",
      "mode": "condition",
      "read": "对应本文或SI的Methods、计算参数表、表注及其适用范围。",
      "checks": [
        "必须对应实际计算阶段与版本语境；VASP、QE、SSCHA不互相代替。",
        "白名单条件需完整来源、材料/物相/软件/阶段都成立，且不存在例外与冲突。",
        "普通直接字段、阶段扩展和SSCHA条件按真实键保留，不按页面位置继承。"
      ],
      "dependencies": [
        "该字段读取的软件、电子理论、泛函和明确阶段；不是整个计算条件对象。",
        "来源中明确限定的材料/物相/压强/结构优化范围。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先检查此参数所属材料、物相、软件和计算阶段，回看同一表行/表注或Methods原句。",
        "查看scientific_context.json中的关联、fact_evidences、scope_evidences与gaps，以及condition_window/rule_review是否完整且当前有效。",
        "原文未报告则留空；泛函尤其不得从另一软件推算。若阶段或软件错误，修正关联范围，不把所有条件一起重置。"
      ],
      "example": "例：同名计算软件出现在两个阶段时，需分别找到各自软件和范围依据。",
      "scope": "条件化程序规则",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/condition_rules.py",
          "line": 8,
          "symbol": "PARAMETERS"
        },
        {
          "path": "backend/ingest/condition_rules.py",
          "line": 419,
          "symbol": "current_review"
        },
        {
          "path": "backend/ingest/scientific_context.py",
          "line": 558,
          "symbol": "apply_associations"
        },
        {
          "path": "backend/ingest/calculation_methods.py",
          "line": 57,
          "symbol": "method_field_issue"
        }
      ]
    },
    {
      "id": "records[*].payload.calculation_conditions.electronic_method",
      "label": "电子结构理论 / 方法",
      "path": "records[*].payload.calculation_conditions.electronic_method",
      "group": "计算条件",
      "mode": "condition",
      "read": "对应本文或SI的Methods、计算参数表、表注及其适用范围。",
      "checks": [
        "电子理论如DFT、HF、DFT+U；DFPT、harmonic、SSCHA、软件和泛函不能混填。",
        "原文与材料、物相、计算阶段和具体结果的关系成立；不从软件或harmonic猜电子理论。",
        "交换关联泛函、U等参数仅按报告填写，DFPT定义推断保留推断身份。"
      ],
      "dependencies": [
        "该字段读取的软件、电子理论、泛函和明确阶段；不是整个计算条件对象。",
        "来源中明确限定的材料/物相/压强/结构优化范围。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先检查此参数所属材料、物相、软件和计算阶段，回看同一表行/表注或Methods原句。",
        "查看scientific_context.json中的关联、fact_evidences、scope_evidences与gaps，以及condition_window/rule_review是否完整且当前有效。",
        "原文未报告则留空；泛函尤其不得从另一软件推算。若阶段或软件错误，修正关联范围，不把所有条件一起重置。"
      ],
      "example": "例：同名电子结构理论 / 方法出现在两个阶段时，需分别找到各自软件和范围依据。",
      "scope": "条件化程序规则",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/condition_rules.py",
          "line": 8,
          "symbol": "PARAMETERS"
        },
        {
          "path": "backend/ingest/condition_rules.py",
          "line": 419,
          "symbol": "current_review"
        },
        {
          "path": "backend/ingest/scientific_context.py",
          "line": 558,
          "symbol": "apply_associations"
        },
        {
          "path": "backend/ingest/calculation_methods.py",
          "line": 57,
          "symbol": "method_field_issue"
        }
      ]
    },
    {
      "id": "records[*].payload.calculation_conditions.exchange_correlation_functional",
      "label": "交换关联泛函",
      "path": "records[*].payload.calculation_conditions.exchange_correlation_functional",
      "group": "计算条件",
      "mode": "condition",
      "read": "对应本文或SI的Methods、计算参数表、表注及其适用范围。",
      "checks": [
        "必须按当前软件和阶段原文记录。QE未报告留空，不能从VASP的PBE推成QE-PBE。",
        "白名单条件需完整来源、材料/物相/软件/阶段都成立，且不存在例外与冲突。",
        "普通直接字段、阶段扩展和SSCHA条件按真实键保留，不按页面位置继承。"
      ],
      "dependencies": [
        "该字段读取的软件、电子理论、泛函和明确阶段；不是整个计算条件对象。",
        "来源中明确限定的材料/物相/压强/结构优化范围。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先检查此参数所属材料、物相、软件和计算阶段，回看同一表行/表注或Methods原句。",
        "查看scientific_context.json中的关联、fact_evidences、scope_evidences与gaps，以及condition_window/rule_review是否完整且当前有效。",
        "原文未报告则留空；泛函尤其不得从另一软件推算。若阶段或软件错误，修正关联范围，不把所有条件一起重置。"
      ],
      "example": "例：VASP负责几何优化、QE负责EPC时，VASP参数不能当作QE参数；QE泛函未报告就留空。",
      "scope": "条件化程序规则",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/condition_rules.py",
          "line": 8,
          "symbol": "PARAMETERS"
        },
        {
          "path": "backend/ingest/condition_rules.py",
          "line": 419,
          "symbol": "current_review"
        },
        {
          "path": "backend/ingest/scientific_context.py",
          "line": 558,
          "symbol": "apply_associations"
        },
        {
          "path": "backend/ingest/calculation_methods.py",
          "line": 57,
          "symbol": "method_field_issue"
        }
      ]
    },
    {
      "id": "records[*].payload.calculation_conditions.extensions[key={stage}.phonon_method].value_*",
      "label": "声子方法",
      "path": "records[*].payload.calculation_conditions.extensions[key={stage}.phonon_method].value_*",
      "group": "计算条件",
      "mode": "condition",
      "read": "对应本文或SI的Methods、计算参数表、表注及其适用范围。",
      "checks": [
        "DFPT、有限位移等按声子方法保存；历史分组仅有限转换，不能把错误对象形状静默丢弃。",
        "白名单条件需完整来源、材料/物相/软件/阶段都成立，且不存在例外与冲突。",
        "普通直接字段、阶段扩展和SSCHA条件按真实键保留，不按页面位置继承。"
      ],
      "dependencies": [
        "该字段读取的软件、电子理论、泛函和明确阶段；不是整个计算条件对象。",
        "来源中明确限定的材料/物相/压强/结构优化范围。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先检查此参数所属材料、物相、软件和计算阶段，回看同一表行/表注或Methods原句。",
        "查看scientific_context.json中的关联、fact_evidences、scope_evidences与gaps，以及condition_window/rule_review是否完整且当前有效。",
        "原文未报告则留空；泛函尤其不得从另一软件推算。若阶段或软件错误，修正关联范围，不把所有条件一起重置。"
      ],
      "example": "例：同名声子方法出现在两个阶段时，需分别找到各自软件和范围依据。",
      "scope": "条件化程序规则",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/condition_rules.py",
          "line": 8,
          "symbol": "PARAMETERS"
        },
        {
          "path": "backend/ingest/condition_rules.py",
          "line": 419,
          "symbol": "current_review"
        },
        {
          "path": "backend/ingest/scientific_context.py",
          "line": 558,
          "symbol": "apply_associations"
        },
        {
          "path": "backend/ingest/calculation_methods.py",
          "line": 57,
          "symbol": "method_field_issue"
        }
      ]
    },
    {
      "id": "records[*].payload.calculation_conditions.k_grid",
      "label": "k 网格",
      "path": "records[*].payload.calculation_conditions.k_grid",
      "group": "计算条件",
      "mode": "condition",
      "read": "对应本文或SI的Methods、计算参数表、表注及其适用范围。",
      "checks": [
        "区分采样网格与倒空间分辨率，核查对应软件及SCF/NSCF/EPC阶段。",
        "白名单条件需完整来源、材料/物相/软件/阶段都成立，且不存在例外与冲突。",
        "普通直接字段、阶段扩展和SSCHA条件按真实键保留，不按页面位置继承。"
      ],
      "dependencies": [
        "该字段读取的软件、电子理论、泛函和明确阶段；不是整个计算条件对象。",
        "来源中明确限定的材料/物相/压强/结构优化范围。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先检查此参数所属材料、物相、软件和计算阶段，回看同一表行/表注或Methods原句。",
        "查看scientific_context.json中的关联、fact_evidences、scope_evidences与gaps，以及condition_window/rule_review是否完整且当前有效。",
        "原文未报告则留空；泛函尤其不得从另一软件推算。若阶段或软件错误，修正关联范围，不把所有条件一起重置。"
      ],
      "example": "例：同名k 网格出现在两个阶段时，需分别找到各自软件和范围依据。",
      "scope": "条件化程序规则",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/condition_rules.py",
          "line": 8,
          "symbol": "PARAMETERS"
        },
        {
          "path": "backend/ingest/condition_rules.py",
          "line": 419,
          "symbol": "current_review"
        },
        {
          "path": "backend/ingest/scientific_context.py",
          "line": 558,
          "symbol": "apply_associations"
        },
        {
          "path": "backend/ingest/calculation_methods.py",
          "line": 57,
          "symbol": "method_field_issue"
        }
      ]
    },
    {
      "id": "records[*].payload.calculation_conditions.q_grid",
      "label": "q 网格",
      "path": "records[*].payload.calculation_conditions.q_grid",
      "group": "计算条件",
      "mode": "condition",
      "read": "对应本文或SI的Methods、计算参数表、表注及其适用范围。",
      "checks": [
        "区分粗网格与插值细网格，不能拿超胞大小代替q网格。",
        "白名单条件需完整来源、材料/物相/软件/阶段都成立，且不存在例外与冲突。",
        "普通直接字段、阶段扩展和SSCHA条件按真实键保留，不按页面位置继承。"
      ],
      "dependencies": [
        "该字段读取的软件、电子理论、泛函和明确阶段；不是整个计算条件对象。",
        "来源中明确限定的材料/物相/压强/结构优化范围。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先检查此参数所属材料、物相、软件和计算阶段，回看同一表行/表注或Methods原句。",
        "查看scientific_context.json中的关联、fact_evidences、scope_evidences与gaps，以及condition_window/rule_review是否完整且当前有效。",
        "原文未报告则留空；泛函尤其不得从另一软件推算。若阶段或软件错误，修正关联范围，不把所有条件一起重置。"
      ],
      "example": "例：同名q 网格出现在两个阶段时，需分别找到各自软件和范围依据。",
      "scope": "条件化程序规则",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/condition_rules.py",
          "line": 8,
          "symbol": "PARAMETERS"
        },
        {
          "path": "backend/ingest/condition_rules.py",
          "line": 419,
          "symbol": "current_review"
        },
        {
          "path": "backend/ingest/scientific_context.py",
          "line": 558,
          "symbol": "apply_associations"
        },
        {
          "path": "backend/ingest/calculation_methods.py",
          "line": 57,
          "symbol": "method_field_issue"
        }
      ]
    },
    {
      "id": "records[*].payload.calculation_conditions.extensions[key={stage}.q_grid_interpolated].value_*",
      "label": "插值 q 网格",
      "path": "records[*].payload.calculation_conditions.extensions[key={stage}.q_grid_interpolated].value_*",
      "group": "计算条件",
      "mode": "condition",
      "read": "对应本文或SI的Methods、计算参数表、表注及其适用范围。",
      "checks": [
        "明确这是插值细网格，不覆盖原DFPT粗网格。",
        "白名单条件需完整来源、材料/物相/软件/阶段都成立，且不存在例外与冲突。",
        "普通直接字段、阶段扩展和SSCHA条件按真实键保留，不按页面位置继承。"
      ],
      "dependencies": [
        "该字段读取的软件、电子理论、泛函和明确阶段；不是整个计算条件对象。",
        "来源中明确限定的材料/物相/压强/结构优化范围。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先检查此参数所属材料、物相、软件和计算阶段，回看同一表行/表注或Methods原句。",
        "查看scientific_context.json中的关联、fact_evidences、scope_evidences与gaps，以及condition_window/rule_review是否完整且当前有效。",
        "原文未报告则留空；泛函尤其不得从另一软件推算。若阶段或软件错误，修正关联范围，不把所有条件一起重置。"
      ],
      "example": "例：同名插值 q 网格出现在两个阶段时，需分别找到各自软件和范围依据。",
      "scope": "条件化程序规则",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/condition_rules.py",
          "line": 8,
          "symbol": "PARAMETERS"
        },
        {
          "path": "backend/ingest/condition_rules.py",
          "line": 419,
          "symbol": "current_review"
        },
        {
          "path": "backend/ingest/scientific_context.py",
          "line": 558,
          "symbol": "apply_associations"
        },
        {
          "path": "backend/ingest/calculation_methods.py",
          "line": 57,
          "symbol": "method_field_issue"
        }
      ]
    },
    {
      "id": "records[*].payload.calculation_conditions.k_broadening",
      "label": "k 展宽",
      "path": "records[*].payload.calculation_conditions.k_broadening",
      "group": "计算条件",
      "mode": "condition",
      "read": "对应本文或SI的Methods、计算参数表、表注及其适用范围。",
      "checks": [
        "原始数值、单位及含义与k采样绑定，不能与q展宽合并。",
        "白名单条件需完整来源、材料/物相/软件/阶段都成立，且不存在例外与冲突。",
        "普通直接字段、阶段扩展和SSCHA条件按真实键保留，不按页面位置继承。"
      ],
      "dependencies": [
        "该字段读取的软件、电子理论、泛函和明确阶段；不是整个计算条件对象。",
        "来源中明确限定的材料/物相/压强/结构优化范围。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先检查此参数所属材料、物相、软件和计算阶段，回看同一表行/表注或Methods原句。",
        "查看scientific_context.json中的关联、fact_evidences、scope_evidences与gaps，以及condition_window/rule_review是否完整且当前有效。",
        "原文未报告则留空；泛函尤其不得从另一软件推算。若阶段或软件错误，修正关联范围，不把所有条件一起重置。"
      ],
      "example": "例：同名k 展宽出现在两个阶段时，需分别找到各自软件和范围依据。",
      "scope": "条件化程序规则",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/condition_rules.py",
          "line": 8,
          "symbol": "PARAMETERS"
        },
        {
          "path": "backend/ingest/condition_rules.py",
          "line": 419,
          "symbol": "current_review"
        },
        {
          "path": "backend/ingest/scientific_context.py",
          "line": 558,
          "symbol": "apply_associations"
        },
        {
          "path": "backend/ingest/calculation_methods.py",
          "line": 57,
          "symbol": "method_field_issue"
        }
      ]
    },
    {
      "id": "records[*].payload.calculation_conditions.q_broadening",
      "label": "q 展宽",
      "path": "records[*].payload.calculation_conditions.q_broadening",
      "group": "计算条件",
      "mode": "condition",
      "read": "对应本文或SI的Methods、计算参数表、表注及其适用范围。",
      "checks": [
        "对应q过程的展宽，与电子k展宽分开。",
        "白名单条件需完整来源、材料/物相/软件/阶段都成立，且不存在例外与冲突。",
        "普通直接字段、阶段扩展和SSCHA条件按真实键保留，不按页面位置继承。"
      ],
      "dependencies": [
        "该字段读取的软件、电子理论、泛函和明确阶段；不是整个计算条件对象。",
        "来源中明确限定的材料/物相/压强/结构优化范围。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先检查此参数所属材料、物相、软件和计算阶段，回看同一表行/表注或Methods原句。",
        "查看scientific_context.json中的关联、fact_evidences、scope_evidences与gaps，以及condition_window/rule_review是否完整且当前有效。",
        "原文未报告则留空；泛函尤其不得从另一软件推算。若阶段或软件错误，修正关联范围，不把所有条件一起重置。"
      ],
      "example": "例：同名q 展宽出现在两个阶段时，需分别找到各自软件和范围依据。",
      "scope": "条件化程序规则",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/condition_rules.py",
          "line": 8,
          "symbol": "PARAMETERS"
        },
        {
          "path": "backend/ingest/condition_rules.py",
          "line": 419,
          "symbol": "current_review"
        },
        {
          "path": "backend/ingest/scientific_context.py",
          "line": 558,
          "symbol": "apply_associations"
        },
        {
          "path": "backend/ingest/calculation_methods.py",
          "line": 57,
          "symbol": "method_field_issue"
        }
      ]
    },
    {
      "id": "records[*].payload.calculation_conditions.extensions[key={stage}.energy_cutoff].value_*",
      "label": "波函数截断能",
      "path": "records[*].payload.calculation_conditions.extensions[key={stage}.energy_cutoff].value_*",
      "group": "计算条件",
      "mode": "condition",
      "read": "对应本文或SI的Methods、计算参数表、表注及其适用范围。",
      "checks": [
        "区分波函数与电荷密度截断，保留Ry/eV等原单位与软件归属。",
        "白名单条件需完整来源、材料/物相/软件/阶段都成立，且不存在例外与冲突。",
        "普通直接字段、阶段扩展和SSCHA条件按真实键保留，不按页面位置继承。"
      ],
      "dependencies": [
        "该字段读取的软件、电子理论、泛函和明确阶段；不是整个计算条件对象。",
        "来源中明确限定的材料/物相/压强/结构优化范围。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先检查此参数所属材料、物相、软件和计算阶段，回看同一表行/表注或Methods原句。",
        "查看scientific_context.json中的关联、fact_evidences、scope_evidences与gaps，以及condition_window/rule_review是否完整且当前有效。",
        "原文未报告则留空；泛函尤其不得从另一软件推算。若阶段或软件错误，修正关联范围，不把所有条件一起重置。"
      ],
      "example": "例：同名波函数截断能出现在两个阶段时，需分别找到各自软件和范围依据。",
      "scope": "条件化程序规则",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/condition_rules.py",
          "line": 8,
          "symbol": "PARAMETERS"
        },
        {
          "path": "backend/ingest/condition_rules.py",
          "line": 419,
          "symbol": "current_review"
        },
        {
          "path": "backend/ingest/scientific_context.py",
          "line": 558,
          "symbol": "apply_associations"
        },
        {
          "path": "backend/ingest/calculation_methods.py",
          "line": 57,
          "symbol": "method_field_issue"
        }
      ]
    },
    {
      "id": "records[*].payload.calculation_conditions.extensions[key={stage}.charge_density_cutoff].value_*",
      "label": "电荷密度截断能",
      "path": "records[*].payload.calculation_conditions.extensions[key={stage}.charge_density_cutoff].value_*",
      "group": "计算条件",
      "mode": "condition",
      "read": "对应本文或SI的Methods、计算参数表、表注及其适用范围。",
      "checks": [
        "不由波函数截断能乘默认比例推算，原文未报告留空。",
        "白名单条件需完整来源、材料/物相/软件/阶段都成立，且不存在例外与冲突。",
        "普通直接字段、阶段扩展和SSCHA条件按真实键保留，不按页面位置继承。"
      ],
      "dependencies": [
        "该字段读取的软件、电子理论、泛函和明确阶段；不是整个计算条件对象。",
        "来源中明确限定的材料/物相/压强/结构优化范围。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先检查此参数所属材料、物相、软件和计算阶段，回看同一表行/表注或Methods原句。",
        "查看scientific_context.json中的关联、fact_evidences、scope_evidences与gaps，以及condition_window/rule_review是否完整且当前有效。",
        "原文未报告则留空；泛函尤其不得从另一软件推算。若阶段或软件错误，修正关联范围，不把所有条件一起重置。"
      ],
      "example": "例：同名电荷密度截断能出现在两个阶段时，需分别找到各自软件和范围依据。",
      "scope": "条件化程序规则",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/condition_rules.py",
          "line": 8,
          "symbol": "PARAMETERS"
        },
        {
          "path": "backend/ingest/condition_rules.py",
          "line": 419,
          "symbol": "current_review"
        },
        {
          "path": "backend/ingest/scientific_context.py",
          "line": 558,
          "symbol": "apply_associations"
        },
        {
          "path": "backend/ingest/calculation_methods.py",
          "line": 57,
          "symbol": "method_field_issue"
        }
      ]
    },
    {
      "id": "records[*].payload.calculation_conditions.extensions[key={stage}.convergence_energy].value_*",
      "label": "能量收敛阈值",
      "path": "records[*].payload.calculation_conditions.extensions[key={stage}.convergence_energy].value_*",
      "group": "计算条件",
      "mode": "condition",
      "read": "对应本文或SI的Methods、计算参数表、表注及其适用范围。",
      "checks": [
        "与力收敛分开，明确每步/总能量、单位及所属优化软件。",
        "白名单条件需完整来源、材料/物相/软件/阶段都成立，且不存在例外与冲突。",
        "普通直接字段、阶段扩展和SSCHA条件按真实键保留，不按页面位置继承。"
      ],
      "dependencies": [
        "该字段读取的软件、电子理论、泛函和明确阶段；不是整个计算条件对象。",
        "来源中明确限定的材料/物相/压强/结构优化范围。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先检查此参数所属材料、物相、软件和计算阶段，回看同一表行/表注或Methods原句。",
        "查看scientific_context.json中的关联、fact_evidences、scope_evidences与gaps，以及condition_window/rule_review是否完整且当前有效。",
        "原文未报告则留空；泛函尤其不得从另一软件推算。若阶段或软件错误，修正关联范围，不把所有条件一起重置。"
      ],
      "example": "例：同名能量收敛阈值出现在两个阶段时，需分别找到各自软件和范围依据。",
      "scope": "条件化程序规则",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/condition_rules.py",
          "line": 8,
          "symbol": "PARAMETERS"
        },
        {
          "path": "backend/ingest/condition_rules.py",
          "line": 419,
          "symbol": "current_review"
        },
        {
          "path": "backend/ingest/scientific_context.py",
          "line": 558,
          "symbol": "apply_associations"
        },
        {
          "path": "backend/ingest/calculation_methods.py",
          "line": 57,
          "symbol": "method_field_issue"
        }
      ]
    },
    {
      "id": "records[*].payload.calculation_conditions.extensions[key={stage}.convergence_force].value_*",
      "label": "力收敛阈值",
      "path": "records[*].payload.calculation_conditions.extensions[key={stage}.convergence_force].value_*",
      "group": "计算条件",
      "mode": "condition",
      "read": "对应本文或SI的Methods、计算参数表、表注及其适用范围。",
      "checks": [
        "与能量阈值分开，保留力单位和结构优化阶段。",
        "白名单条件需完整来源、材料/物相/软件/阶段都成立，且不存在例外与冲突。",
        "普通直接字段、阶段扩展和SSCHA条件按真实键保留，不按页面位置继承。"
      ],
      "dependencies": [
        "该字段读取的软件、电子理论、泛函和明确阶段；不是整个计算条件对象。",
        "来源中明确限定的材料/物相/压强/结构优化范围。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先检查此参数所属材料、物相、软件和计算阶段，回看同一表行/表注或Methods原句。",
        "查看scientific_context.json中的关联、fact_evidences、scope_evidences与gaps，以及condition_window/rule_review是否完整且当前有效。",
        "原文未报告则留空；泛函尤其不得从另一软件推算。若阶段或软件错误，修正关联范围，不把所有条件一起重置。"
      ],
      "example": "例：同名力收敛阈值出现在两个阶段时，需分别找到各自软件和范围依据。",
      "scope": "条件化程序规则",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/condition_rules.py",
          "line": 8,
          "symbol": "PARAMETERS"
        },
        {
          "path": "backend/ingest/condition_rules.py",
          "line": 419,
          "symbol": "current_review"
        },
        {
          "path": "backend/ingest/scientific_context.py",
          "line": 558,
          "symbol": "apply_associations"
        },
        {
          "path": "backend/ingest/calculation_methods.py",
          "line": 57,
          "symbol": "method_field_issue"
        }
      ]
    },
    {
      "id": "records[*].payload.calculation_conditions.extensions[key={stage}.supercell].value_*",
      "label": "超胞",
      "path": "records[*].payload.calculation_conditions.extensions[key={stage}.supercell].value_*",
      "group": "计算条件",
      "mode": "condition",
      "read": "对应本文或SI的Methods、计算参数表、表注及其适用范围。",
      "checks": [
        "指明声子、SSCHA或其他阶段所用超胞，不按常见配置猜。",
        "白名单条件需完整来源、材料/物相/软件/阶段都成立，且不存在例外与冲突。",
        "普通直接字段、阶段扩展和SSCHA条件按真实键保留，不按页面位置继承。"
      ],
      "dependencies": [
        "该字段读取的软件、电子理论、泛函和明确阶段；不是整个计算条件对象。",
        "来源中明确限定的材料/物相/压强/结构优化范围。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先检查此参数所属材料、物相、软件和计算阶段，回看同一表行/表注或Methods原句。",
        "查看scientific_context.json中的关联、fact_evidences、scope_evidences与gaps，以及condition_window/rule_review是否完整且当前有效。",
        "原文未报告则留空；泛函尤其不得从另一软件推算。若阶段或软件错误，修正关联范围，不把所有条件一起重置。"
      ],
      "example": "例：同名超胞出现在两个阶段时，需分别找到各自软件和范围依据。",
      "scope": "条件化程序规则",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/condition_rules.py",
          "line": 8,
          "symbol": "PARAMETERS"
        },
        {
          "path": "backend/ingest/condition_rules.py",
          "line": 419,
          "symbol": "current_review"
        },
        {
          "path": "backend/ingest/scientific_context.py",
          "line": 558,
          "symbol": "apply_associations"
        },
        {
          "path": "backend/ingest/calculation_methods.py",
          "line": 57,
          "symbol": "method_field_issue"
        }
      ]
    },
    {
      "id": "records[*].payload.calculation_conditions.extensions[key={stage}.atoms].value_*",
      "label": "计算超胞原子数",
      "path": "records[*].payload.calculation_conditions.extensions[key={stage}.atoms].value_*",
      "group": "计算条件",
      "mode": "condition",
      "read": "对应本文或SI的Methods、计算参数表、表注及其适用范围。",
      "checks": [
        "不把化学式计数或另一阶段超胞原子数搬来代替。",
        "白名单条件需完整来源、材料/物相/软件/阶段都成立，且不存在例外与冲突。",
        "普通直接字段、阶段扩展和SSCHA条件按真实键保留，不按页面位置继承。"
      ],
      "dependencies": [
        "该字段读取的软件、电子理论、泛函和明确阶段；不是整个计算条件对象。",
        "来源中明确限定的材料/物相/压强/结构优化范围。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先检查此参数所属材料、物相、软件和计算阶段，回看同一表行/表注或Methods原句。",
        "查看scientific_context.json中的关联、fact_evidences、scope_evidences与gaps，以及condition_window/rule_review是否完整且当前有效。",
        "原文未报告则留空；泛函尤其不得从另一软件推算。若阶段或软件错误，修正关联范围，不把所有条件一起重置。"
      ],
      "example": "例：同名计算超胞原子数出现在两个阶段时，需分别找到各自软件和范围依据。",
      "scope": "条件化程序规则",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/condition_rules.py",
          "line": 8,
          "symbol": "PARAMETERS"
        },
        {
          "path": "backend/ingest/condition_rules.py",
          "line": 419,
          "symbol": "current_review"
        },
        {
          "path": "backend/ingest/scientific_context.py",
          "line": 558,
          "symbol": "apply_associations"
        },
        {
          "path": "backend/ingest/calculation_methods.py",
          "line": 57,
          "symbol": "method_field_issue"
        }
      ]
    },
    {
      "id": "records[*].payload.calculation_conditions.extensions[key={stage}.temperature_k].value_*",
      "label": "计算条件温度",
      "path": "records[*].payload.calculation_conditions.extensions[key={stage}.temperature_k].value_*",
      "group": "计算条件",
      "mode": "condition",
      "read": "对应本文或SI的Methods、计算参数表、表注及其适用范围。",
      "checks": [
        "与材料状态温度、退火温度及SSCHA/AIMD温度分别归属，不默认0K。",
        "白名单条件需完整来源、材料/物相/软件/阶段都成立，且不存在例外与冲突。",
        "普通直接字段、阶段扩展和SSCHA条件按真实键保留，不按页面位置继承。"
      ],
      "dependencies": [
        "该字段读取的软件、电子理论、泛函和明确阶段；不是整个计算条件对象。",
        "来源中明确限定的材料/物相/压强/结构优化范围。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先检查此参数所属材料、物相、软件和计算阶段，回看同一表行/表注或Methods原句。",
        "查看scientific_context.json中的关联、fact_evidences、scope_evidences与gaps，以及condition_window/rule_review是否完整且当前有效。",
        "原文未报告则留空；泛函尤其不得从另一软件推算。若阶段或软件错误，修正关联范围，不把所有条件一起重置。"
      ],
      "example": "例：同名计算条件温度出现在两个阶段时，需分别找到各自软件和范围依据。",
      "scope": "条件化程序规则",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/condition_rules.py",
          "line": 8,
          "symbol": "PARAMETERS"
        },
        {
          "path": "backend/ingest/condition_rules.py",
          "line": 419,
          "symbol": "current_review"
        },
        {
          "path": "backend/ingest/scientific_context.py",
          "line": 558,
          "symbol": "apply_associations"
        },
        {
          "path": "backend/ingest/calculation_methods.py",
          "line": 57,
          "symbol": "method_field_issue"
        }
      ]
    },
    {
      "id": "thermodynamical_properties.records[*].payload.thermodynamic_stability.basis",
      "label": "稳定性判据",
      "path": "thermodynamical_properties.records[*].payload.thermodynamic_stability.basis",
      "group": "热力学性质",
      "mode": "fact",
      "read": "原文热力学稳定性论证、凸包、形成量、ZPE口径和对应条件。",
      "checks": [
        "formation_energy / formation_enthalpy / formation_gibbs / unspecified分别存储。",
        "当前稳定性合同为version=1，模块必须是thermodynamical_properties下的property/custom。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：稳定性判据改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "稳定性专用结构合同 + 共享语义核对",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/thermodynamic_stability.py",
          "line": 11,
          "symbol": "stability_issues"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        }
      ]
    },
    {
      "id": "thermodynamical_properties.records[*].payload.thermodynamic_stability.cases.{basis}.stability",
      "label": "稳定 / 不稳定 / 未判定",
      "path": "thermodynamical_properties.records[*].payload.thermodynamic_stability.cases.{basis}.stability",
      "group": "热力学性质",
      "mode": "fact",
      "read": "原文热力学稳定性论证、凸包、形成量、ZPE口径和对应条件。",
      "checks": [
        "只接受stable、unstable、unknown；记录摘要须与当前判据一致。",
        "当前稳定性合同为version=1，模块必须是thermodynamical_properties下的property/custom。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：稳定 / 不稳定 / 未判定改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "稳定性专用结构合同 + 共享语义核对",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/thermodynamic_stability.py",
          "line": 11,
          "symbol": "stability_issues"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        }
      ]
    },
    {
      "id": "thermodynamical_properties.records[*].payload.thermodynamic_stability.cases.{basis}.zpe",
      "label": "零点振动能口径",
      "path": "thermodynamical_properties.records[*].payload.thermodynamic_stability.cases.{basis}.zpe",
      "group": "热力学性质",
      "mode": "fact",
      "read": "原文热力学稳定性论证、凸包、形成量、ZPE口径和对应条件。",
      "checks": [
        "included / excluded / unspecified明确记录，不替论文猜测。",
        "当前稳定性合同为version=1，模块必须是thermodynamical_properties下的property/custom。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：零点振动能口径改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "稳定性专用结构合同 + 共享语义核对",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/thermodynamic_stability.py",
          "line": 11,
          "symbol": "stability_issues"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        }
      ]
    },
    {
      "id": "thermodynamical_properties.records[*].payload.thermodynamic_stability.cases.{basis}.unit",
      "label": "稳定性数值单位",
      "path": "thermodynamical_properties.records[*].payload.thermodynamic_stability.cases.{basis}.unit",
      "group": "热力学性质",
      "mode": "fact",
      "read": "原文热力学稳定性论证、凸包、形成量、ZPE口径和对应条件。",
      "checks": [
        "当前合同只接受eV/atom或meV/atom，不能省去归一化口径。",
        "当前稳定性合同为version=1，模块必须是thermodynamical_properties下的property/custom。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：稳定性数值单位改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "稳定性专用结构合同 + 共享语义核对",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/thermodynamic_stability.py",
          "line": 11,
          "symbol": "stability_issues"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        }
      ]
    },
    {
      "id": "thermodynamical_properties.records[*].payload.thermodynamic_stability.cases.{basis}.above_hull",
      "label": "凸包上方能量",
      "path": "thermodynamical_properties.records[*].payload.thermodynamic_stability.cases.{basis}.above_hull",
      "group": "热力学性质",
      "mode": "fact",
      "read": "原文热力学稳定性论证、凸包、形成量、ZPE口径和对应条件。",
      "checks": [
        "只为unstable结论记录above-hull；须非负有限值。",
        "当前稳定性合同为version=1，模块必须是thermodynamical_properties下的property/custom。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：凸包上方能量改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "稳定性专用结构合同 + 共享语义核对",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/thermodynamic_stability.py",
          "line": 11,
          "symbol": "stability_issues"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        }
      ]
    },
    {
      "id": "thermodynamical_properties.records[*].payload.thermodynamic_stability.cases.{basis}.temperature_k",
      "label": "稳定性判据温度",
      "path": "thermodynamical_properties.records[*].payload.thermodynamic_stability.cases.{basis}.temperature_k",
      "group": "热力学性质",
      "mode": "fact",
      "read": "原文热力学稳定性论证、凸包、形成量、ZPE口径和对应条件。",
      "checks": [
        "形成能/形成焓合同温度为0K；Gibbs温度依据原文独立核对。",
        "当前稳定性合同为version=1，模块必须是thermodynamical_properties下的property/custom。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：稳定性判据温度改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "稳定性专用结构合同 + 共享语义核对",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/thermodynamic_stability.py",
          "line": 11,
          "symbol": "stability_issues"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        }
      ]
    },
    {
      "id": "thermodynamical_properties.records[*].payload.thermodynamic_stability.cases.{basis}.decomposition_path",
      "label": "分解路径",
      "path": "thermodynamical_properties.records[*].payload.thermodynamic_stability.cases.{basis}.decomposition_path",
      "group": "热力学性质",
      "mode": "fact",
      "read": "原文热力学稳定性论证、凸包、形成量、ZPE口径和对应条件。",
      "checks": [
        "文本字段，核对实际分解产物与当前化学组成和压强。",
        "当前稳定性合同为version=1，模块必须是thermodynamical_properties下的property/custom。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：分解路径改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "稳定性专用结构合同 + 共享语义核对",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/thermodynamic_stability.py",
          "line": 11,
          "symbol": "stability_issues"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        }
      ]
    },
    {
      "id": "thermodynamical_properties.records[*].payload.thermodynamic_stability.cases.{basis}.source_description",
      "label": "稳定性来源说明",
      "path": "thermodynamical_properties.records[*].payload.thermodynamic_stability.cases.{basis}.source_description",
      "group": "热力学性质",
      "mode": "fact",
      "read": "原文热力学稳定性论证、凸包、形成量、ZPE口径和对应条件。",
      "checks": [
        "必须为文本，保留具体图、表或论证来源，不能用“稳定”二字代替依据。",
        "当前稳定性合同为version=1，模块必须是thermodynamical_properties下的property/custom。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：稳定性来源说明改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "稳定性专用结构合同 + 共享语义核对",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/thermodynamic_stability.py",
          "line": 11,
          "symbol": "stability_issues"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        }
      ]
    },
    {
      "id": "dynamical_properties.records[custom].payload.{实际字段}",
      "label": "动力学稳定 / 虚频等自定义性质",
      "path": "dynamical_properties.records[custom].payload.{实际字段}",
      "group": "动力学性质",
      "mode": "fact",
      "read": "声子或动力学结果原文与实际发布的自定义定义。",
      "checks": [
        "当前没有统一硬编码的全部动力学参数清单；按实际自定义记录及叶子核对。",
        "PDF自动物性注册范围不因存在手工自定义入口就扩大；未注册自动候选保留审计，不自动入自定义项。",
        "不能把热力学稳定等同于动力学稳定，也不只凭图形质量检查就批准科学结论。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：无虚频的声子结论与位于凸包上的热力学结论是两种不同证据。",
      "scope": "开放字段模板；不是专用动力学求解器",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/upload_jobs.py",
          "line": 1409,
          "symbol": "_prune_generated_properties"
        }
      ]
    },
    {
      "id": "records[*].payload.parameters.extensions[*].name_raw",
      "label": "扩展名称（参数）",
      "path": "records[*].payload.parameters.extensions[*].name_raw",
      "group": "超导性质",
      "mode": "fact",
      "read": "当前扩展项的原文、所属记录及稳定field_key/key。",
      "checks": [
        "名称与实际科学含义一致，改名称只影响该键及真实依赖。",
        "扩展对象先通过property_extensions合同，再按现有独立键展开核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：扩展名称（参数）改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "实际扩展叶子模板",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_extensions.py",
          "line": 39,
          "symbol": "extension_issues"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 85,
          "symbol": "expand_property_fields"
        }
      ]
    },
    {
      "id": "records[*].payload.parameters.extensions[*].key",
      "label": "扩展稳定键 / 阶段（参数）",
      "path": "records[*].payload.parameters.extensions[*].key",
      "group": "超导性质",
      "mode": "fact",
      "read": "当前扩展项的原文、所属记录及稳定field_key/key。",
      "checks": [
        "已知条件扩展必须明确阶段；field_key及真实key维持身份，不按数组下标串位。",
        "扩展对象先通过property_extensions合同，再按现有独立键展开核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：扩展稳定键 / 阶段（参数）改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "实际扩展叶子模板",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_extensions.py",
          "line": 39,
          "symbol": "extension_issues"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 85,
          "symbol": "expand_property_fields"
        }
      ]
    },
    {
      "id": "records[*].payload.parameters.extensions[*].value_kind",
      "label": "扩展值类型（参数）",
      "path": "records[*].payload.parameters.extensions[*].value_kind",
      "group": "超导性质",
      "mode": "fact",
      "read": "当前扩展项的原文、所属记录及稳定field_key/key。",
      "checks": [
        "number、range、text、boolean对应实际值形状；不能类型与值槽位矛盾。",
        "扩展对象先通过property_extensions合同，再按现有独立键展开核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：扩展值类型（参数）改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "实际扩展叶子模板",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_extensions.py",
          "line": 39,
          "symbol": "extension_issues"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 85,
          "symbol": "expand_property_fields"
        }
      ]
    },
    {
      "id": "records[*].payload.parameters.extensions[*].value_raw",
      "label": "扩展原始值（参数）",
      "path": "records[*].payload.parameters.extensions[*].value_raw",
      "group": "超导性质",
      "mode": "fact",
      "read": "当前扩展项的原文、所属记录及稳定field_key/key。",
      "checks": [
        "保留原始文字；非空数值文本却无规范数值时明确报错。",
        "扩展对象先通过property_extensions合同，再按现有独立键展开核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：扩展原始值（参数）改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "实际扩展叶子模板",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_extensions.py",
          "line": 39,
          "symbol": "extension_issues"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 85,
          "symbol": "expand_property_fields"
        }
      ]
    },
    {
      "id": "records[*].payload.parameters.extensions[*].value_number",
      "label": "扩展单值（参数）",
      "path": "records[*].payload.parameters.extensions[*].value_number",
      "group": "超导性质",
      "mode": "fact",
      "read": "当前扩展项的原文、所属记录及稳定field_key/key。",
      "checks": [
        "需符合当前数值型合同及科学量纲，不能把null变零。",
        "扩展对象先通过property_extensions合同，再按现有独立键展开核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：扩展单值（参数）改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "实际扩展叶子模板",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_extensions.py",
          "line": 39,
          "symbol": "extension_issues"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 85,
          "symbol": "expand_property_fields"
        }
      ]
    },
    {
      "id": "records[*].payload.parameters.extensions[*].value_min",
      "label": "扩展范围下界（参数）",
      "path": "records[*].payload.parameters.extensions[*].value_min",
      "group": "超导性质",
      "mode": "fact",
      "read": "当前扩展项的原文、所属记录及稳定field_key/key。",
      "checks": [
        "范围完整且顺序合法，保持原来的物理含义。",
        "扩展对象先通过property_extensions合同，再按现有独立键展开核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：扩展范围下界（参数）改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "实际扩展叶子模板",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_extensions.py",
          "line": 39,
          "symbol": "extension_issues"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 85,
          "symbol": "expand_property_fields"
        }
      ]
    },
    {
      "id": "records[*].payload.parameters.extensions[*].value_max",
      "label": "扩展范围上界（参数）",
      "path": "records[*].payload.parameters.extensions[*].value_max",
      "group": "超导性质",
      "mode": "fact",
      "read": "当前扩展项的原文、所属记录及稳定field_key/key。",
      "checks": [
        "与下界同一字段和来源；不得拿端点替代真正标量。",
        "扩展对象先通过property_extensions合同，再按现有独立键展开核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：扩展范围上界（参数）改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "实际扩展叶子模板",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_extensions.py",
          "line": 39,
          "symbol": "extension_issues"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 85,
          "symbol": "expand_property_fields"
        }
      ]
    },
    {
      "id": "records[*].payload.parameters.extensions[*].unit_raw",
      "label": "扩展单位（参数）",
      "path": "records[*].payload.parameters.extensions[*].unit_raw",
      "group": "超导性质",
      "mode": "fact",
      "read": "当前扩展项的原文、所属记录及稳定field_key/key。",
      "checks": [
        "单位与具体值和阶段绑定，不凭名称套默认单位。",
        "扩展对象先通过property_extensions合同，再按现有独立键展开核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：扩展单位（参数）改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "实际扩展叶子模板",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_extensions.py",
          "line": 39,
          "symbol": "extension_issues"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 85,
          "symbol": "expand_property_fields"
        }
      ]
    },
    {
      "id": "records[*].payload.calculation_conditions.extensions[*].name_raw",
      "label": "扩展名称（计算条件）",
      "path": "records[*].payload.calculation_conditions.extensions[*].name_raw",
      "group": "计算条件",
      "mode": "condition",
      "read": "当前扩展项的原文、所属记录及稳定field_key/key。",
      "checks": [
        "名称与实际科学含义一致，改名称只影响该键及真实依赖。",
        "扩展对象先通过property_extensions合同，再按现有独立键展开核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先检查此参数所属材料、物相、软件和计算阶段，回看同一表行/表注或Methods原句。",
        "查看scientific_context.json中的关联、fact_evidences、scope_evidences与gaps，以及condition_window/rule_review是否完整且当前有效。",
        "原文未报告则留空；泛函尤其不得从另一软件推算。若阶段或软件错误，修正关联范围，不把所有条件一起重置。"
      ],
      "example": "例：扩展名称（计算条件）改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "实际扩展叶子模板",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_extensions.py",
          "line": 39,
          "symbol": "extension_issues"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 85,
          "symbol": "expand_property_fields"
        }
      ]
    },
    {
      "id": "records[*].payload.calculation_conditions.extensions[*].key",
      "label": "扩展稳定键 / 阶段（计算条件）",
      "path": "records[*].payload.calculation_conditions.extensions[*].key",
      "group": "计算条件",
      "mode": "condition",
      "read": "当前扩展项的原文、所属记录及稳定field_key/key。",
      "checks": [
        "已知条件扩展必须明确阶段；field_key及真实key维持身份，不按数组下标串位。",
        "扩展对象先通过property_extensions合同，再按现有独立键展开核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先检查此参数所属材料、物相、软件和计算阶段，回看同一表行/表注或Methods原句。",
        "查看scientific_context.json中的关联、fact_evidences、scope_evidences与gaps，以及condition_window/rule_review是否完整且当前有效。",
        "原文未报告则留空；泛函尤其不得从另一软件推算。若阶段或软件错误，修正关联范围，不把所有条件一起重置。"
      ],
      "example": "例：扩展稳定键 / 阶段（计算条件）改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "实际扩展叶子模板",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_extensions.py",
          "line": 39,
          "symbol": "extension_issues"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 85,
          "symbol": "expand_property_fields"
        }
      ]
    },
    {
      "id": "records[*].payload.calculation_conditions.extensions[*].value_kind",
      "label": "扩展值类型（计算条件）",
      "path": "records[*].payload.calculation_conditions.extensions[*].value_kind",
      "group": "计算条件",
      "mode": "condition",
      "read": "当前扩展项的原文、所属记录及稳定field_key/key。",
      "checks": [
        "number、range、text、boolean对应实际值形状；不能类型与值槽位矛盾。",
        "扩展对象先通过property_extensions合同，再按现有独立键展开核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先检查此参数所属材料、物相、软件和计算阶段，回看同一表行/表注或Methods原句。",
        "查看scientific_context.json中的关联、fact_evidences、scope_evidences与gaps，以及condition_window/rule_review是否完整且当前有效。",
        "原文未报告则留空；泛函尤其不得从另一软件推算。若阶段或软件错误，修正关联范围，不把所有条件一起重置。"
      ],
      "example": "例：扩展值类型（计算条件）改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "实际扩展叶子模板",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_extensions.py",
          "line": 39,
          "symbol": "extension_issues"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 85,
          "symbol": "expand_property_fields"
        }
      ]
    },
    {
      "id": "records[*].payload.calculation_conditions.extensions[*].value_raw",
      "label": "扩展原始值（计算条件）",
      "path": "records[*].payload.calculation_conditions.extensions[*].value_raw",
      "group": "计算条件",
      "mode": "condition",
      "read": "当前扩展项的原文、所属记录及稳定field_key/key。",
      "checks": [
        "保留原始文字；非空数值文本却无规范数值时明确报错。",
        "扩展对象先通过property_extensions合同，再按现有独立键展开核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先检查此参数所属材料、物相、软件和计算阶段，回看同一表行/表注或Methods原句。",
        "查看scientific_context.json中的关联、fact_evidences、scope_evidences与gaps，以及condition_window/rule_review是否完整且当前有效。",
        "原文未报告则留空；泛函尤其不得从另一软件推算。若阶段或软件错误，修正关联范围，不把所有条件一起重置。"
      ],
      "example": "例：扩展原始值（计算条件）改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "实际扩展叶子模板",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_extensions.py",
          "line": 39,
          "symbol": "extension_issues"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 85,
          "symbol": "expand_property_fields"
        }
      ]
    },
    {
      "id": "records[*].payload.calculation_conditions.extensions[*].value_number",
      "label": "扩展单值（计算条件）",
      "path": "records[*].payload.calculation_conditions.extensions[*].value_number",
      "group": "计算条件",
      "mode": "condition",
      "read": "当前扩展项的原文、所属记录及稳定field_key/key。",
      "checks": [
        "需符合当前数值型合同及科学量纲，不能把null变零。",
        "扩展对象先通过property_extensions合同，再按现有独立键展开核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先检查此参数所属材料、物相、软件和计算阶段，回看同一表行/表注或Methods原句。",
        "查看scientific_context.json中的关联、fact_evidences、scope_evidences与gaps，以及condition_window/rule_review是否完整且当前有效。",
        "原文未报告则留空；泛函尤其不得从另一软件推算。若阶段或软件错误，修正关联范围，不把所有条件一起重置。"
      ],
      "example": "例：扩展单值（计算条件）改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "实际扩展叶子模板",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_extensions.py",
          "line": 39,
          "symbol": "extension_issues"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 85,
          "symbol": "expand_property_fields"
        }
      ]
    },
    {
      "id": "records[*].payload.calculation_conditions.extensions[*].value_min",
      "label": "扩展范围下界（计算条件）",
      "path": "records[*].payload.calculation_conditions.extensions[*].value_min",
      "group": "计算条件",
      "mode": "condition",
      "read": "当前扩展项的原文、所属记录及稳定field_key/key。",
      "checks": [
        "范围完整且顺序合法，保持原来的物理含义。",
        "扩展对象先通过property_extensions合同，再按现有独立键展开核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先检查此参数所属材料、物相、软件和计算阶段，回看同一表行/表注或Methods原句。",
        "查看scientific_context.json中的关联、fact_evidences、scope_evidences与gaps，以及condition_window/rule_review是否完整且当前有效。",
        "原文未报告则留空；泛函尤其不得从另一软件推算。若阶段或软件错误，修正关联范围，不把所有条件一起重置。"
      ],
      "example": "例：扩展范围下界（计算条件）改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "实际扩展叶子模板",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_extensions.py",
          "line": 39,
          "symbol": "extension_issues"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 85,
          "symbol": "expand_property_fields"
        }
      ]
    },
    {
      "id": "records[*].payload.calculation_conditions.extensions[*].value_max",
      "label": "扩展范围上界（计算条件）",
      "path": "records[*].payload.calculation_conditions.extensions[*].value_max",
      "group": "计算条件",
      "mode": "condition",
      "read": "当前扩展项的原文、所属记录及稳定field_key/key。",
      "checks": [
        "与下界同一字段和来源；不得拿端点替代真正标量。",
        "扩展对象先通过property_extensions合同，再按现有独立键展开核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先检查此参数所属材料、物相、软件和计算阶段，回看同一表行/表注或Methods原句。",
        "查看scientific_context.json中的关联、fact_evidences、scope_evidences与gaps，以及condition_window/rule_review是否完整且当前有效。",
        "原文未报告则留空；泛函尤其不得从另一软件推算。若阶段或软件错误，修正关联范围，不把所有条件一起重置。"
      ],
      "example": "例：扩展范围上界（计算条件）改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "实际扩展叶子模板",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_extensions.py",
          "line": 39,
          "symbol": "extension_issues"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 85,
          "symbol": "expand_property_fields"
        }
      ]
    },
    {
      "id": "records[*].payload.calculation_conditions.extensions[*].unit_raw",
      "label": "扩展单位（计算条件）",
      "path": "records[*].payload.calculation_conditions.extensions[*].unit_raw",
      "group": "计算条件",
      "mode": "condition",
      "read": "当前扩展项的原文、所属记录及稳定field_key/key。",
      "checks": [
        "单位与具体值和阶段绑定，不凭名称套默认单位。",
        "扩展对象先通过property_extensions合同，再按现有独立键展开核对。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先检查此参数所属材料、物相、软件和计算阶段，回看同一表行/表注或Methods原句。",
        "查看scientific_context.json中的关联、fact_evidences、scope_evidences与gaps，以及condition_window/rule_review是否完整且当前有效。",
        "原文未报告则留空；泛函尤其不得从另一软件推算。若阶段或软件错误，修正关联范围，不把所有条件一起重置。"
      ],
      "example": "例：扩展单位（计算条件）改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "实际扩展叶子模板",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/property_extensions.py",
          "line": 39,
          "symbol": "extension_issues"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        },
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 85,
          "symbol": "expand_property_fields"
        }
      ]
    },
    {
      "id": "records[*].record_key",
      "label": "记录稳定身份",
      "path": "records[*].record_key",
      "group": "记录身份与开放字段",
      "mode": "metadata",
      "read": "服务端记录身份、已发布定义及当前科学内容的引用。",
      "checks": [
        "按PropertyRecordInput、validate_record与实际发布定义检查。",
        "该键的身份/引用/容器职责与科学数值叶子的审核职责分开。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "例：记录稳定身份改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "身份/定义/来源或开放叶子模板",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/upload_contracts.py",
          "line": 155,
          "symbol": "PropertyRecordInput"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        }
      ]
    },
    {
      "id": "records[*].module_code",
      "label": "模块代码",
      "path": "records[*].module_code",
      "group": "记录身份与开放字段",
      "mode": "metadata",
      "read": "服务端记录身份、已发布定义及当前科学内容的引用。",
      "checks": [
        "按PropertyRecordInput、validate_record与实际发布定义检查。",
        "该键的身份/引用/容器职责与科学数值叶子的审核职责分开。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "例：模块代码改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "身份/定义/来源或开放叶子模板",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/upload_contracts.py",
          "line": 155,
          "symbol": "PropertyRecordInput"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        }
      ]
    },
    {
      "id": "records[*].record_type",
      "label": "记录类型",
      "path": "records[*].record_type",
      "group": "记录身份与开放字段",
      "mode": "metadata",
      "read": "服务端记录身份、已发布定义及当前科学内容的引用。",
      "checks": [
        "按PropertyRecordInput、validate_record与实际发布定义检查。",
        "该键的身份/引用/容器职责与科学数值叶子的审核职责分开。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "例：记录类型改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "身份/定义/来源或开放叶子模板",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/upload_contracts.py",
          "line": 155,
          "symbol": "PropertyRecordInput"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        }
      ]
    },
    {
      "id": "records[*].property_code",
      "label": "性质代码",
      "path": "records[*].property_code",
      "group": "记录身份与开放字段",
      "mode": "metadata",
      "read": "服务端记录身份、已发布定义及当前科学内容的引用。",
      "checks": [
        "按PropertyRecordInput、validate_record与实际发布定义检查。",
        "该键的身份/引用/容器职责与科学数值叶子的审核职责分开。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "例：性质代码改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "身份/定义/来源或开放叶子模板",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/upload_contracts.py",
          "line": 155,
          "symbol": "PropertyRecordInput"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        }
      ]
    },
    {
      "id": "records[*].custom_property_key",
      "label": "自定义性质键",
      "path": "records[*].custom_property_key",
      "group": "记录身份与开放字段",
      "mode": "metadata",
      "read": "服务端记录身份、已发布定义及当前科学内容的引用。",
      "checks": [
        "按PropertyRecordInput、validate_record与实际发布定义检查。",
        "该键的身份/引用/容器职责与科学数值叶子的审核职责分开。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "例：自定义性质键改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "身份/定义/来源或开放叶子模板",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/upload_contracts.py",
          "line": 155,
          "symbol": "PropertyRecordInput"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        }
      ]
    },
    {
      "id": "records[*].definition_key",
      "label": "表单定义键",
      "path": "records[*].definition_key",
      "group": "记录身份与开放字段",
      "mode": "metadata",
      "read": "服务端记录身份、已发布定义及当前科学内容的引用。",
      "checks": [
        "按PropertyRecordInput、validate_record与实际发布定义检查。",
        "该键的身份/引用/容器职责与科学数值叶子的审核职责分开。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "例：表单定义键改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "身份/定义/来源或开放叶子模板",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/upload_contracts.py",
          "line": 155,
          "symbol": "PropertyRecordInput"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        }
      ]
    },
    {
      "id": "records[*].definition_version",
      "label": "表单定义版本",
      "path": "records[*].definition_version",
      "group": "记录身份与开放字段",
      "mode": "metadata",
      "read": "服务端记录身份、已发布定义及当前科学内容的引用。",
      "checks": [
        "按PropertyRecordInput、validate_record与实际发布定义检查。",
        "该键的身份/引用/容器职责与科学数值叶子的审核职责分开。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "例：表单定义版本改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "身份/定义/来源或开放叶子模板",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/upload_contracts.py",
          "line": 155,
          "symbol": "PropertyRecordInput"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        }
      ]
    },
    {
      "id": "records[*].structure_key",
      "label": "关联结构身份",
      "path": "records[*].structure_key",
      "group": "记录身份与开放字段",
      "mode": "metadata",
      "read": "服务端记录身份、已发布定义及当前科学内容的引用。",
      "checks": [
        "按PropertyRecordInput、validate_record与实际发布定义检查。",
        "该键的身份/引用/容器职责与科学数值叶子的审核职责分开。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "例：关联结构身份改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "身份/定义/来源或开放叶子模板",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/upload_contracts.py",
          "line": 155,
          "symbol": "PropertyRecordInput"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        }
      ]
    },
    {
      "id": "records[*].payload",
      "label": "开放科学payload",
      "path": "records[*].payload",
      "group": "记录身份与开放字段",
      "mode": "fact",
      "read": "服务端记录身份、已发布定义及当前科学内容的引用。",
      "checks": [
        "按PropertyRecordInput、validate_record与实际发布定义检查。",
        "该键的身份/引用/容器职责与科学数值叶子的审核职责分开。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：开放科学payload改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "身份/定义/来源或开放叶子模板",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/upload_contracts.py",
          "line": 155,
          "symbol": "PropertyRecordInput"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        }
      ]
    },
    {
      "id": "records[*].evidence",
      "label": "旧单条来源入口",
      "path": "records[*].evidence",
      "group": "记录身份与开放字段",
      "mode": "metadata",
      "read": "服务端记录身份、已发布定义及当前科学内容的引用。",
      "checks": [
        "按PropertyRecordInput、validate_record与实际发布定义检查。",
        "该键的身份/引用/容器职责与科学数值叶子的审核职责分开。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "例：旧单条来源入口改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "身份/定义/来源或开放叶子模板",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/upload_contracts.py",
          "line": 155,
          "symbol": "PropertyRecordInput"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        }
      ]
    },
    {
      "id": "records[*].evidences",
      "label": "多条来源关联",
      "path": "records[*].evidences",
      "group": "记录身份与开放字段",
      "mode": "metadata",
      "read": "服务端记录身份、已发布定义及当前科学内容的引用。",
      "checks": [
        "按PropertyRecordInput、validate_record与实际发布定义检查。",
        "该键的身份/引用/容器职责与科学数值叶子的审核职责分开。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "例：多条来源关联改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "身份/定义/来源或开放叶子模板",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/upload_contracts.py",
          "line": 155,
          "symbol": "PropertyRecordInput"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        }
      ]
    },
    {
      "id": "records[*].is_representative",
      "label": "代表 Tc 组合",
      "path": "records[*].is_representative",
      "group": "记录身份与开放字段",
      "mode": "metadata",
      "read": "服务端记录身份、已发布定义及当前科学内容的引用。",
      "checks": [
        "不依数组位置确认归属；记录、模块、结构须属于当前论文或状态。",
        "实际payload叶子走independent_fields；evidence/evidences通过独立来源处理，不伪造为数值。",
        "代表Tc仅允许当前状态一个有效组合，需明确到Tc和μ*，不能勾一整条范围。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "例：代表 Tc 组合改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "身份/定义/来源或开放叶子模板",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/upload_contracts.py",
          "line": 155,
          "symbol": "PropertyRecordInput"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        },
        {
          "path": "backend/ingest/field_review.py",
          "line": 68,
          "symbol": "independent_fields"
        }
      ]
    },
    {
      "id": "spectra.phdos.curves",
      "label": "声子 DOS 曲线",
      "path": "spectra.phdos.curves",
      "group": "独立谱处理",
      "mode": "spectrum",
      "read": "对应原谱图、曲线点、坐标轴、单位、结构N及幅值标定依据。",
      "checks": [
        "曲线、原图、单位、通道及质量独立保存，缺少采样不补零。",
        "谱数据的保存和送审边界独立，不因谱质量待核对自动阻断论文送审。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：声子 DOS 曲线改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "独立谱合同；不属于普通字段生成批",
      "errorCodes": [
        "质量待核对",
        "标定条件不足"
      ],
      "failureRoute": "保留曲线与质量，缺条件不算该派生项",
      "sources": [
        {
          "path": "backend/spectra/contracts.py",
          "line": 9,
          "symbol": "ALGORITHM_VERSION"
        },
        {
          "path": "backend/spectra/scientific_review.py",
          "line": 43,
          "symbol": "audit_dataset"
        }
      ]
    },
    {
      "id": "spectra.alpha2f.curves",
      "label": "α²F 谱曲线",
      "path": "spectra.alpha2f.curves",
      "group": "独立谱处理",
      "mode": "spectrum",
      "read": "对应原谱图、曲线点、坐标轴、单位、结构N及幅值标定依据。",
      "checks": [
        "原始相对幅值与论文λ标定分开；未知幅值不可捏造。",
        "谱数据的保存和送审边界独立，不因谱质量待核对自动阻断论文送审。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：α²F 谱曲线改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "独立谱合同；不属于普通字段生成批",
      "errorCodes": [
        "质量待核对",
        "标定条件不足"
      ],
      "failureRoute": "保留曲线与质量，缺条件不算该派生项",
      "sources": [
        {
          "path": "backend/spectra/contracts.py",
          "line": 9,
          "symbol": "ALGORITHM_VERSION"
        },
        {
          "path": "backend/spectra/scientific_review.py",
          "line": 43,
          "symbol": "audit_dataset"
        }
      ]
    },
    {
      "id": "spectra.frequency",
      "label": "谱频率与采样范围",
      "path": "spectra.frequency",
      "group": "独立谱处理",
      "mode": "spectrum",
      "read": "对应原谱图、曲线点、坐标轴、单位、结构N及幅值标定依据。",
      "checks": [
        "频率单位按合同转换，不要求退休的零频人工确认；仅用实际有效采样范围。",
        "谱数据的保存和送审边界独立，不因谱质量待核对自动阻断论文送审。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：谱频率与采样范围改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "独立谱合同；不属于普通字段生成批",
      "errorCodes": [
        "质量待核对",
        "标定条件不足"
      ],
      "failureRoute": "保留曲线与质量，缺条件不算该派生项",
      "sources": [
        {
          "path": "backend/spectra/contracts.py",
          "line": 9,
          "symbol": "ALGORITHM_VERSION"
        },
        {
          "path": "backend/spectra/scientific_review.py",
          "line": 43,
          "symbol": "audit_dataset"
        }
      ]
    },
    {
      "id": "spectra.lambda_ep",
      "label": "谱积分 λ",
      "path": "spectra.lambda_ep",
      "group": "独立谱处理",
      "mode": "spectrum",
      "read": "对应原谱图、曲线点、坐标轴、单位、结构N及幅值标定依据。",
      "checks": [
        "实际幅值和有效频率范围足够时计算；相对图不能直接充当绝对λ。",
        "谱数据的保存和送审边界独立，不因谱质量待核对自动阻断论文送审。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：谱积分 λ改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "独立谱合同；不属于普通字段生成批",
      "errorCodes": [
        "质量待核对",
        "标定条件不足"
      ],
      "failureRoute": "保留曲线与质量，缺条件不算该派生项",
      "sources": [
        {
          "path": "backend/spectra/contracts.py",
          "line": 9,
          "symbol": "ALGORITHM_VERSION"
        },
        {
          "path": "backend/spectra/scientific_review.py",
          "line": 43,
          "symbol": "audit_dataset"
        }
      ]
    },
    {
      "id": "spectra.omega_log",
      "label": "谱计算 ωlog",
      "path": "spectra.omega_log",
      "group": "独立谱处理",
      "mode": "spectrum",
      "read": "对应原谱图、曲线点、坐标轴、单位、结构N及幅值标定依据。",
      "checks": [
        "按有效正频率及积分条件计算，与原文参数保留各自来源。",
        "谱数据的保存和送审边界独立，不因谱质量待核对自动阻断论文送审。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：谱计算 ωlog改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "独立谱合同；不属于普通字段生成批",
      "errorCodes": [
        "质量待核对",
        "标定条件不足"
      ],
      "failureRoute": "保留曲线与质量，缺条件不算该派生项",
      "sources": [
        {
          "path": "backend/spectra/contracts.py",
          "line": 9,
          "symbol": "ALGORITHM_VERSION"
        },
        {
          "path": "backend/spectra/scientific_review.py",
          "line": 43,
          "symbol": "audit_dataset"
        }
      ]
    },
    {
      "id": "spectra.dos_relative_area",
      "label": "DOS 相对面积与元素比例",
      "path": "spectra.dos_relative_area",
      "group": "独立谱处理",
      "mode": "spectrum",
      "read": "对应原谱图、曲线点、坐标轴、单位、结构N及幅值标定依据。",
      "checks": [
        "像素面积、共同尺度面积比、按3N归一化与绝对积分分开；没有N时不假装可算3N。",
        "谱数据的保存和送审边界独立，不因谱质量待核对自动阻断论文送审。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：DOS 相对面积与元素比例改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "独立谱合同；不属于普通字段生成批",
      "errorCodes": [
        "质量待核对",
        "标定条件不足"
      ],
      "failureRoute": "保留曲线与质量，缺条件不算该派生项",
      "sources": [
        {
          "path": "backend/spectra/contracts.py",
          "line": 9,
          "symbol": "ALGORITHM_VERSION"
        },
        {
          "path": "backend/spectra/scientific_review.py",
          "line": 43,
          "symbol": "audit_dataset"
        }
      ]
    },
    {
      "id": "spectra.quality",
      "label": "谱提取质量与人工历史",
      "path": "spectra.quality",
      "group": "独立谱处理",
      "mode": "spectrum",
      "read": "对应原谱图、曲线点、坐标轴、单位、结构N及幅值标定依据。",
      "checks": [
        "质量检查不等于科学公开审核；原始运行与人工修改历史分开保留。",
        "谱数据的保存和送审边界独立，不因谱质量待核对自动阻断论文送审。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "从字段名或待处理入口打开侧栏，对照当前值、原文和所属材料状态。",
        "改值时保存实际变化及要求的人工说明，再主动核对本字段或在明确提交时做必要核对。",
        "若属于程序错误，沿下方源码入口核对提取、类型与版本，不通过删除证据或重置整份草稿绕过。"
      ],
      "example": "例：谱提取质量与人工历史改值后，应核对这个字段的新值和真实依赖，不能清空其他材料的已通过结果。",
      "scope": "独立谱合同；不属于普通字段生成批",
      "errorCodes": [
        "质量待核对",
        "标定条件不足"
      ],
      "failureRoute": "保留曲线与质量，缺条件不算该派生项",
      "sources": [
        {
          "path": "backend/spectra/contracts.py",
          "line": 9,
          "symbol": "ALGORITHM_VERSION"
        },
        {
          "path": "backend/spectra/scientific_review.py",
          "line": 43,
          "symbol": "audit_dataset"
        }
      ]
    },
    {
      "id": "module.superconductive_properties@1",
      "label": "表单定义：module.superconductive_properties",
      "path": "module.superconductive_properties@1",
      "group": "表单定义",
      "mode": "metadata",
      "read": "本机只读查询的published定义元数据；其他运行目标以其实际定义为准。",
      "checks": [
        "模块、记录类型、性质代码与方法代码须匹配定义。",
        "core_schema与payload的json_schema分别校验，定义内容与校验和须一致。",
        "additionalProperties开放不等于存在该物理量的专用核对算法。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "定义版本1；payload已声明键：无固定叶子，按开放合同处理。",
      "scope": "本机发布定义快照",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/form_definitions.py",
          "line": 76,
          "symbol": "validate_definition_payload"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        }
      ]
    },
    {
      "id": "module.dynamical_properties@1",
      "label": "表单定义：module.dynamical_properties",
      "path": "module.dynamical_properties@1",
      "group": "表单定义",
      "mode": "metadata",
      "read": "本机只读查询的published定义元数据；其他运行目标以其实际定义为准。",
      "checks": [
        "模块、记录类型、性质代码与方法代码须匹配定义。",
        "core_schema与payload的json_schema分别校验，定义内容与校验和须一致。",
        "additionalProperties开放不等于存在该物理量的专用核对算法。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "定义版本1；payload已声明键：无固定叶子，按开放合同处理。",
      "scope": "本机发布定义快照",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/form_definitions.py",
          "line": 76,
          "symbol": "validate_definition_payload"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        }
      ]
    },
    {
      "id": "module.thermodynamical_properties@1",
      "label": "表单定义：module.thermodynamical_properties",
      "path": "module.thermodynamical_properties@1",
      "group": "表单定义",
      "mode": "metadata",
      "read": "本机只读查询的published定义元数据；其他运行目标以其实际定义为准。",
      "checks": [
        "模块、记录类型、性质代码与方法代码须匹配定义。",
        "core_schema与payload的json_schema分别校验，定义内容与校验和须一致。",
        "additionalProperties开放不等于存在该物理量的专用核对算法。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "定义版本1；payload已声明键：无固定叶子，按开放合同处理。",
      "scope": "本机发布定义快照",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/form_definitions.py",
          "line": 76,
          "symbol": "validate_definition_payload"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        }
      ]
    },
    {
      "id": "module.electronic_properties@1",
      "label": "表单定义：module.electronic_properties",
      "path": "module.electronic_properties@1",
      "group": "表单定义",
      "mode": "metadata",
      "read": "本机只读查询的published定义元数据；其他运行目标以其实际定义为准。",
      "checks": [
        "模块、记录类型、性质代码与方法代码须匹配定义。",
        "core_schema与payload的json_schema分别校验，定义内容与校验和须一致。",
        "additionalProperties开放不等于存在该物理量的专用核对算法。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "定义版本1；payload已声明键：无固定叶子，按开放合同处理。",
      "scope": "本机发布定义快照",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/form_definitions.py",
          "line": 76,
          "symbol": "validate_definition_payload"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        }
      ]
    },
    {
      "id": "record.superconductive_properties.predicted_tc.allen_dynes@1",
      "label": "表单定义：record.superconductive_properties.predicted_tc.allen_dynes",
      "path": "record.superconductive_properties.predicted_tc.allen_dynes@1",
      "group": "表单定义",
      "mode": "metadata",
      "read": "本机只读查询的published定义元数据；其他运行目标以其实际定义为准。",
      "checks": [
        "模块、记录类型、性质代码与方法代码须匹配定义。",
        "core_schema与payload的json_schema分别校验，定义内容与校验和须一致。",
        "additionalProperties开放不等于存在该物理量的专用核对算法。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "定义版本1；payload已声明键：parameters、calculation_conditions",
      "scope": "本机发布定义快照",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/form_definitions.py",
          "line": 76,
          "symbol": "validate_definition_payload"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        }
      ]
    },
    {
      "id": "record.superconductive_properties.predicted_tc.unknown@1",
      "label": "表单定义：record.superconductive_properties.predicted_tc.unknown",
      "path": "record.superconductive_properties.predicted_tc.unknown@1",
      "group": "表单定义",
      "mode": "metadata",
      "read": "本机只读查询的published定义元数据；其他运行目标以其实际定义为准。",
      "checks": [
        "模块、记录类型、性质代码与方法代码须匹配定义。",
        "core_schema与payload的json_schema分别校验，定义内容与校验和须一致。",
        "additionalProperties开放不等于存在该物理量的专用核对算法。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "定义版本1；payload已声明键：parameters、calculation_conditions",
      "scope": "本机发布定义快照",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/form_definitions.py",
          "line": 76,
          "symbol": "validate_definition_payload"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        }
      ]
    },
    {
      "id": "record.superconductive_properties.measured_tc.resistivity@1",
      "label": "表单定义：record.superconductive_properties.measured_tc.resistivity",
      "path": "record.superconductive_properties.measured_tc.resistivity@1",
      "group": "表单定义",
      "mode": "metadata",
      "read": "本机只读查询的published定义元数据；其他运行目标以其实际定义为准。",
      "checks": [
        "模块、记录类型、性质代码与方法代码须匹配定义。",
        "core_schema与payload的json_schema分别校验，定义内容与校验和须一致。",
        "additionalProperties开放不等于存在该物理量的专用核对算法。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "定义版本1；payload已声明键：experimental_conditions",
      "scope": "本机发布定义快照",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/form_definitions.py",
          "line": 76,
          "symbol": "validate_definition_payload"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        }
      ]
    },
    {
      "id": "record.superconductive_properties.custom@1",
      "label": "表单定义：record.superconductive_properties.custom",
      "path": "record.superconductive_properties.custom@1",
      "group": "表单定义",
      "mode": "metadata",
      "read": "本机只读查询的published定义元数据；其他运行目标以其实际定义为准。",
      "checks": [
        "模块、记录类型、性质代码与方法代码须匹配定义。",
        "core_schema与payload的json_schema分别校验，定义内容与校验和须一致。",
        "additionalProperties开放不等于存在该物理量的专用核对算法。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "定义版本1；payload已声明键：无固定叶子，按开放合同处理。",
      "scope": "本机发布定义快照",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/form_definitions.py",
          "line": 76,
          "symbol": "validate_definition_payload"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        }
      ]
    },
    {
      "id": "record.dynamical_properties.custom@1",
      "label": "表单定义：record.dynamical_properties.custom",
      "path": "record.dynamical_properties.custom@1",
      "group": "表单定义",
      "mode": "metadata",
      "read": "本机只读查询的published定义元数据；其他运行目标以其实际定义为准。",
      "checks": [
        "模块、记录类型、性质代码与方法代码须匹配定义。",
        "core_schema与payload的json_schema分别校验，定义内容与校验和须一致。",
        "additionalProperties开放不等于存在该物理量的专用核对算法。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "定义版本1；payload已声明键：无固定叶子，按开放合同处理。",
      "scope": "本机发布定义快照",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/form_definitions.py",
          "line": 76,
          "symbol": "validate_definition_payload"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        }
      ]
    },
    {
      "id": "record.thermodynamical_properties.custom@1",
      "label": "表单定义：record.thermodynamical_properties.custom",
      "path": "record.thermodynamical_properties.custom@1",
      "group": "表单定义",
      "mode": "metadata",
      "read": "本机只读查询的published定义元数据；其他运行目标以其实际定义为准。",
      "checks": [
        "模块、记录类型、性质代码与方法代码须匹配定义。",
        "core_schema与payload的json_schema分别校验，定义内容与校验和须一致。",
        "additionalProperties开放不等于存在该物理量的专用核对算法。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "定义版本1；payload已声明键：无固定叶子，按开放合同处理。",
      "scope": "本机发布定义快照",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/form_definitions.py",
          "line": 76,
          "symbol": "validate_definition_payload"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        }
      ]
    },
    {
      "id": "record.electronic_properties.custom@1",
      "label": "表单定义：record.electronic_properties.custom",
      "path": "record.electronic_properties.custom@1",
      "group": "表单定义",
      "mode": "metadata",
      "read": "本机只读查询的published定义元数据；其他运行目标以其实际定义为准。",
      "checks": [
        "模块、记录类型、性质代码与方法代码须匹配定义。",
        "core_schema与payload的json_schema分别校验，定义内容与校验和须一致。",
        "additionalProperties开放不等于存在该物理量的专用核对算法。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "定义版本1；payload已声明键：无固定叶子，按开放合同处理。",
      "scope": "本机发布定义快照",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/form_definitions.py",
          "line": 76,
          "symbol": "validate_definition_payload"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        }
      ]
    },
    {
      "id": "record.superconductive_properties.predicted_tc.mcmillan@1",
      "label": "表单定义：record.superconductive_properties.predicted_tc.mcmillan",
      "path": "record.superconductive_properties.predicted_tc.mcmillan@1",
      "group": "表单定义",
      "mode": "metadata",
      "read": "本机只读查询的published定义元数据；其他运行目标以其实际定义为准。",
      "checks": [
        "模块、记录类型、性质代码与方法代码须匹配定义。",
        "core_schema与payload的json_schema分别校验，定义内容与校验和须一致。",
        "additionalProperties开放不等于存在该物理量的专用核对算法。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "定义版本1；payload已声明键：parameters、calculation_conditions",
      "scope": "本机发布定义快照",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/form_definitions.py",
          "line": 76,
          "symbol": "validate_definition_payload"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        }
      ]
    },
    {
      "id": "record.superconductive_properties.predicted_tc.isotropic_eliashberg@1",
      "label": "表单定义：record.superconductive_properties.predicted_tc.isotropic_eliashberg",
      "path": "record.superconductive_properties.predicted_tc.isotropic_eliashberg@1",
      "group": "表单定义",
      "mode": "metadata",
      "read": "本机只读查询的published定义元数据；其他运行目标以其实际定义为准。",
      "checks": [
        "模块、记录类型、性质代码与方法代码须匹配定义。",
        "core_schema与payload的json_schema分别校验，定义内容与校验和须一致。",
        "additionalProperties开放不等于存在该物理量的专用核对算法。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "定义版本1；payload已声明键：parameters、calculation_conditions",
      "scope": "本机发布定义快照",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/form_definitions.py",
          "line": 76,
          "symbol": "validate_definition_payload"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        }
      ]
    },
    {
      "id": "record.superconductive_properties.predicted_tc.anisotropic_eliashberg@1",
      "label": "表单定义：record.superconductive_properties.predicted_tc.anisotropic_eliashberg",
      "path": "record.superconductive_properties.predicted_tc.anisotropic_eliashberg@1",
      "group": "表单定义",
      "mode": "metadata",
      "read": "本机只读查询的published定义元数据；其他运行目标以其实际定义为准。",
      "checks": [
        "模块、记录类型、性质代码与方法代码须匹配定义。",
        "core_schema与payload的json_schema分别校验，定义内容与校验和须一致。",
        "additionalProperties开放不等于存在该物理量的专用核对算法。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "定义版本1；payload已声明键：parameters、calculation_conditions",
      "scope": "本机发布定义快照",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/form_definitions.py",
          "line": 76,
          "symbol": "validate_definition_payload"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        }
      ]
    },
    {
      "id": "record.superconductive_properties.predicted_tc.scdft@1",
      "label": "表单定义：record.superconductive_properties.predicted_tc.scdft",
      "path": "record.superconductive_properties.predicted_tc.scdft@1",
      "group": "表单定义",
      "mode": "metadata",
      "read": "本机只读查询的published定义元数据；其他运行目标以其实际定义为准。",
      "checks": [
        "模块、记录类型、性质代码与方法代码须匹配定义。",
        "core_schema与payload的json_schema分别校验，定义内容与校验和须一致。",
        "additionalProperties开放不等于存在该物理量的专用核对算法。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "定义版本1；payload已声明键：parameters、calculation_conditions",
      "scope": "本机发布定义快照",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/form_definitions.py",
          "line": 76,
          "symbol": "validate_definition_payload"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        }
      ]
    },
    {
      "id": "record.superconductive_properties.predicted_tc.other@1",
      "label": "表单定义：record.superconductive_properties.predicted_tc.other",
      "path": "record.superconductive_properties.predicted_tc.other@1",
      "group": "表单定义",
      "mode": "metadata",
      "read": "本机只读查询的published定义元数据；其他运行目标以其实际定义为准。",
      "checks": [
        "模块、记录类型、性质代码与方法代码须匹配定义。",
        "core_schema与payload的json_schema分别校验，定义内容与校验和须一致。",
        "additionalProperties开放不等于存在该物理量的专用核对算法。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "定义版本1；payload已声明键：parameters、calculation_conditions",
      "scope": "本机发布定义快照",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/form_definitions.py",
          "line": 76,
          "symbol": "validate_definition_payload"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        }
      ]
    },
    {
      "id": "record.superconductive_properties.measured_tc.magnetic_susceptibility@1",
      "label": "表单定义：record.superconductive_properties.measured_tc.magnetic_susceptibility",
      "path": "record.superconductive_properties.measured_tc.magnetic_susceptibility@1",
      "group": "表单定义",
      "mode": "metadata",
      "read": "本机只读查询的published定义元数据；其他运行目标以其实际定义为准。",
      "checks": [
        "模块、记录类型、性质代码与方法代码须匹配定义。",
        "core_schema与payload的json_schema分别校验，定义内容与校验和须一致。",
        "additionalProperties开放不等于存在该物理量的专用核对算法。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "定义版本1；payload已声明键：experimental_conditions",
      "scope": "本机发布定义快照",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/form_definitions.py",
          "line": 76,
          "symbol": "validate_definition_payload"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        }
      ]
    },
    {
      "id": "record.superconductive_properties.measured_tc.specific_heat@1",
      "label": "表单定义：record.superconductive_properties.measured_tc.specific_heat",
      "path": "record.superconductive_properties.measured_tc.specific_heat@1",
      "group": "表单定义",
      "mode": "metadata",
      "read": "本机只读查询的published定义元数据；其他运行目标以其实际定义为准。",
      "checks": [
        "模块、记录类型、性质代码与方法代码须匹配定义。",
        "core_schema与payload的json_schema分别校验，定义内容与校验和须一致。",
        "additionalProperties开放不等于存在该物理量的专用核对算法。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "定义版本1；payload已声明键：experimental_conditions",
      "scope": "本机发布定义快照",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/form_definitions.py",
          "line": 76,
          "symbol": "validate_definition_payload"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        }
      ]
    },
    {
      "id": "record.superconductive_properties.measured_tc.other@1",
      "label": "表单定义：record.superconductive_properties.measured_tc.other",
      "path": "record.superconductive_properties.measured_tc.other@1",
      "group": "表单定义",
      "mode": "metadata",
      "read": "本机只读查询的published定义元数据；其他运行目标以其实际定义为准。",
      "checks": [
        "模块、记录类型、性质代码与方法代码须匹配定义。",
        "core_schema与payload的json_schema分别校验，定义内容与校验和须一致。",
        "additionalProperties开放不等于存在该物理量的专用核对算法。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "定义版本1；payload已声明键：experimental_conditions",
      "scope": "本机发布定义快照",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/form_definitions.py",
          "line": 76,
          "symbol": "validate_definition_payload"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        }
      ]
    },
    {
      "id": "record.superconductive_properties.measured_tc.unknown@1",
      "label": "表单定义：record.superconductive_properties.measured_tc.unknown",
      "path": "record.superconductive_properties.measured_tc.unknown@1",
      "group": "表单定义",
      "mode": "metadata",
      "read": "本机只读查询的published定义元数据；其他运行目标以其实际定义为准。",
      "checks": [
        "模块、记录类型、性质代码与方法代码须匹配定义。",
        "core_schema与payload的json_schema分别校验，定义内容与校验和须一致。",
        "additionalProperties开放不等于存在该物理量的专用核对算法。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "定义版本1；payload已声明键：experimental_conditions",
      "scope": "本机发布定义快照",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/form_definitions.py",
          "line": 76,
          "symbol": "validate_definition_payload"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        }
      ]
    },
    {
      "id": "record.electronic_properties.band_gap@1",
      "label": "表单定义：record.electronic_properties.band_gap",
      "path": "record.electronic_properties.band_gap@1",
      "group": "表单定义",
      "mode": "metadata",
      "read": "本机只读查询的published定义元数据；其他运行目标以其实际定义为准。",
      "checks": [
        "模块、记录类型、性质代码与方法代码须匹配定义。",
        "core_schema与payload的json_schema分别校验，定义内容与校验和须一致。",
        "additionalProperties开放不等于存在该物理量的专用核对算法。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "定义版本1；payload已声明键：无固定叶子，按开放合同处理。",
      "scope": "本机发布定义快照",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/form_definitions.py",
          "line": 76,
          "symbol": "validate_definition_payload"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        }
      ]
    },
    {
      "id": "record.electronic_properties.dos_fermi@1",
      "label": "表单定义：record.electronic_properties.dos_fermi",
      "path": "record.electronic_properties.dos_fermi@1",
      "group": "表单定义",
      "mode": "metadata",
      "read": "本机只读查询的published定义元数据；其他运行目标以其实际定义为准。",
      "checks": [
        "模块、记录类型、性质代码与方法代码须匹配定义。",
        "core_schema与payload的json_schema分别校验，定义内容与校验和须一致。",
        "additionalProperties开放不等于存在该物理量的专用核对算法。"
      ],
      "dependencies": [
        "本字段的实际值、来源及适用范围；稳定对象身份不随数组位置变化。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "检查当前记录的稳定身份、所属论文/材料状态与关联结构是否仍存在。",
        "核对definition_key、definition_version、published状态和checksum；定义不匹配应修复绑定，不靠修改科学数值绕过。"
      ],
      "example": "定义版本1；payload已声明键：无固定叶子，按开放合同处理。",
      "scope": "本机发布定义快照",
      "errorCodes": [
        "draft_version_conflict",
        "definition_not_available",
        "schema_checksum_mismatch"
      ],
      "failureRoute": "修正身份、定义或引用，不让模型编造",
      "sources": [
        {
          "path": "backend/ingest/form_definitions.py",
          "line": 76,
          "symbol": "validate_definition_payload"
        },
        {
          "path": "backend/ingest/property_modules.py",
          "line": 242,
          "symbol": "validate_record"
        }
      ]
    },
    {
      "id": "records[*].payload.calculation_conditions.phonon_method",
      "label": "声子计算技术",
      "path": "records[*].payload.calculation_conditions.phonon_method",
      "group": "计算条件",
      "mode": "condition",
      "read": "对应工作流的DFPT、有限位移、SSCHA及复合技术原句。",
      "checks": [
        "与电子理论和振动层次分别记录，可表达不同阶段的复合流程。",
        "普通电子带隙/DOS不接收无关声子/EPC条件，明确修正关系时才允许。"
      ],
      "dependencies": [
        "该字段读取的软件、电子理论、泛函和明确阶段；不是整个计算条件对象。",
        "来源中明确限定的材料/物相/压强/结构优化范围。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先检查此参数所属材料、物相、软件和计算阶段，回看同一表行/表注或Methods原句。",
        "查看scientific_context.json中的关联、fact_evidences、scope_evidences与gaps，以及condition_window/rule_review是否完整且当前有效。",
        "原文未报告则留空；泛函尤其不得从另一软件推算。若阶段或软件错误，修正关联范围，不把所有条件一起重置。"
      ],
      "example": "只归入当前结果和对应工作流，不按同卡或同压强复制。",
      "scope": "条件化程序规则",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/calculation_methods.py",
          "line": 95,
          "symbol": "record_method_issue"
        },
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 85,
          "symbol": "expand_property_fields"
        }
      ]
    },
    {
      "id": "records[*].payload.calculation_conditions.vibrational_treatment",
      "label": "振动处理层次",
      "path": "records[*].payload.calculation_conditions.vibrational_treatment",
      "group": "计算条件",
      "mode": "condition",
      "read": "对应结果的harmonic、quasi_harmonic或量子/经典非谐处理。",
      "checks": [
        "不从结构优化目标广播；不把DFT、HF或DFPT填在振动层次。",
        "原文未区分量子/经典时保留未知，不由0 K补猜。"
      ],
      "dependencies": [
        "该字段读取的软件、电子理论、泛函和明确阶段；不是整个计算条件对象。",
        "来源中明确限定的材料/物相/压强/结构优化范围。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先检查此参数所属材料、物相、软件和计算阶段，回看同一表行/表注或Methods原句。",
        "查看scientific_context.json中的关联、fact_evidences、scope_evidences与gaps，以及condition_window/rule_review是否完整且当前有效。",
        "原文未报告则留空；泛函尤其不得从另一软件推算。若阶段或软件错误，修正关联范围，不把所有条件一起重置。"
      ],
      "example": "只归入当前结果和对应工作流，不按同卡或同压强复制。",
      "scope": "条件化程序规则",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/calculation_methods.py",
          "line": 95,
          "symbol": "record_method_issue"
        },
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 85,
          "symbol": "expand_property_fields"
        }
      ]
    },
    {
      "id": "records[*].payload.calculation_conditions.method_scope",
      "label": "计算适用关系",
      "path": "records[*].payload.calculation_conditions.method_scope",
      "group": "计算条件",
      "mode": "fact",
      "read": "当前结果的物理对象、阶段、工作流及明确的电子—声子修正关系。",
      "checks": [
        "修正关系须有逐字原文及实际引用，不能用推断理由代替引句。",
        "选择关系本身不等于通过；材料、物相、压力、阶段、软件不相符时拒绝复用。"
      ],
      "dependencies": [
        "该字段读取的软件、电子理论、泛函和明确阶段；不是整个计算条件对象。",
        "来源中明确限定的材料/物相/压强/结构优化范围。"
      ],
      "failures": [
        "原文不支持当前值，或来源、所属状态与当前字段不一致。",
        "未完成定位、过期或技术故障不能当作科学通过。"
      ],
      "fixes": [
        "先检查此参数所属材料、物相、软件和计算阶段，回看同一表行/表注或Methods原句。",
        "查看scientific_context.json中的关联、fact_evidences、scope_evidences与gaps，以及condition_window/rule_review是否完整且当前有效。",
        "原文未报告则留空；泛函尤其不得从另一软件推算。若阶段或软件错误，修正关联范围，不把所有条件一起重置。"
      ],
      "example": "只归入当前结果和对应工作流，不按同卡或同压强复制。",
      "scope": "字段语义与来源核对，不是条件白名单自动通过",
      "errorCodes": [
        "schema_validation_failed",
        "evidence_stale",
        "evidence_review_required",
        "unchecked",
        "missing"
      ],
      "failureRoute": "保留本字段问题，检查值、来源及真实依赖",
      "sources": [
        {
          "path": "backend/ingest/calculation_methods.py",
          "line": 95,
          "symbol": "record_method_issue"
        },
        {
          "path": "backend/ingest/property_field_review.py",
          "line": 85,
          "symbol": "expand_property_fields"
        }
      ]
    }
  ],
  "coverage": {
    "paper_fields": [
      "title",
      "authors",
      "co_first_authors",
      "corresponding_authors",
      "journal",
      "year",
      "issue_number",
      "volume",
      "pages",
      "doi",
      "abstract",
      "summary",
      "methodology",
      "key_finding",
      "research_motivation",
      "keywords_tags",
      "paper_type",
      "theoretical_subtype",
      "superconductor_kind",
      "material_families",
      "research_materials",
      "knowledge_graph_title"
    ],
    "state_fields": [
      "material_name",
      "material",
      "material_dimensionality",
      "pressure_value_gpa",
      "pressure_min_gpa",
      "pressure_max_gpa",
      "temperature_value_k",
      "magnetic_field_t",
      "reported_space_group_symbol",
      "reported_space_group_number",
      "crystal_system",
      "state_kind",
      "structure_optimization",
      "structure_families",
      "condition_note",
      "note",
      "pressure_raw",
      "pressure_unit_raw",
      "temperature_raw",
      "temperature_unit_raw",
      "calculation_context",
      "experimental_context",
      "element_count"
    ],
    "record_input_fields": [
      "record_key",
      "module_code",
      "record_type",
      "property_code",
      "custom_property_key",
      "definition_key",
      "definition_version",
      "name_raw",
      "value_kind",
      "value_raw",
      "value_number",
      "value_min",
      "value_max",
      "value_text",
      "value_boolean",
      "uncertainty",
      "unit_raw",
      "canonical_unit",
      "method_code",
      "method_raw",
      "criterion_code",
      "criterion_raw",
      "structure_key",
      "payload",
      "evidence",
      "evidences",
      "is_representative"
    ],
    "condition_parameters": [
      "atoms",
      "calculation_code",
      "charge_density_cutoff",
      "convergence_energy",
      "convergence_force",
      "electronic_method",
      "energy_cutoff",
      "exchange_correlation_functional",
      "k_grid",
      "phonon_method",
      "q_grid",
      "q_grid_interpolated",
      "supercell",
      "temperature_k",
      "vibrational_treatment"
    ],
    "dynamic_fields": "按extensions与开放payload模板，不枚举未来所有用户定义叶子"
  },
  "definitions": [
    {
      "definition_key": "module.superconductive_properties",
      "version": 1,
      "target_kind": "property_module",
      "module_code": "superconductive_properties",
      "record_type": null,
      "method_code": null,
      "property_code": null,
      "core_schema": {},
      "json_schema": {
        "type": "object",
        "additionalProperties": true
      },
      "ui_schema": {},
      "status": "published"
    },
    {
      "definition_key": "module.dynamical_properties",
      "version": 1,
      "target_kind": "property_module",
      "module_code": "dynamical_properties",
      "record_type": null,
      "method_code": null,
      "property_code": null,
      "core_schema": {},
      "json_schema": {
        "type": "object",
        "additionalProperties": true
      },
      "ui_schema": {},
      "status": "published"
    },
    {
      "definition_key": "module.thermodynamical_properties",
      "version": 1,
      "target_kind": "property_module",
      "module_code": "thermodynamical_properties",
      "record_type": null,
      "method_code": null,
      "property_code": null,
      "core_schema": {},
      "json_schema": {
        "type": "object",
        "additionalProperties": true
      },
      "ui_schema": {},
      "status": "published"
    },
    {
      "definition_key": "module.electronic_properties",
      "version": 1,
      "target_kind": "property_module",
      "module_code": "electronic_properties",
      "record_type": null,
      "method_code": null,
      "property_code": null,
      "core_schema": {},
      "json_schema": {
        "type": "object",
        "additionalProperties": true
      },
      "ui_schema": {},
      "status": "published"
    },
    {
      "definition_key": "record.superconductive_properties.predicted_tc.allen_dynes",
      "version": 1,
      "target_kind": "property_record",
      "module_code": "superconductive_properties",
      "record_type": "predicted_tc",
      "method_code": "allen_dynes",
      "property_code": "tc",
      "core_schema": {
        "type": "object"
      },
      "json_schema": {
        "type": "object",
        "required": [
          "calculation_conditions"
        ],
        "properties": {
          "parameters": {
            "type": "object"
          },
          "calculation_conditions": {
            "type": "object"
          }
        },
        "additionalProperties": true
      },
      "ui_schema": {
        "groups": [
          "calculation_conditions",
          "parameters"
        ]
      },
      "status": "published"
    },
    {
      "definition_key": "record.superconductive_properties.predicted_tc.unknown",
      "version": 1,
      "target_kind": "property_record",
      "module_code": "superconductive_properties",
      "record_type": "predicted_tc",
      "method_code": "unknown",
      "property_code": "tc",
      "core_schema": {
        "type": "object"
      },
      "json_schema": {
        "type": "object",
        "required": [
          "calculation_conditions"
        ],
        "properties": {
          "parameters": {
            "type": "object"
          },
          "calculation_conditions": {
            "type": "object"
          }
        },
        "additionalProperties": true
      },
      "ui_schema": {},
      "status": "published"
    },
    {
      "definition_key": "record.superconductive_properties.measured_tc.resistivity",
      "version": 1,
      "target_kind": "property_record",
      "module_code": "superconductive_properties",
      "record_type": "measured_tc",
      "method_code": "resistivity",
      "property_code": "tc",
      "core_schema": {
        "type": "object"
      },
      "json_schema": {
        "type": "object",
        "required": [
          "experimental_conditions"
        ],
        "properties": {
          "experimental_conditions": {
            "type": "object"
          }
        },
        "additionalProperties": true
      },
      "ui_schema": {},
      "status": "published"
    },
    {
      "definition_key": "record.superconductive_properties.custom",
      "version": 1,
      "target_kind": "property_record",
      "module_code": "superconductive_properties",
      "record_type": "property",
      "method_code": null,
      "property_code": "custom",
      "core_schema": {
        "type": "object"
      },
      "json_schema": {
        "type": "object",
        "additionalProperties": true
      },
      "ui_schema": {},
      "status": "published"
    },
    {
      "definition_key": "record.dynamical_properties.custom",
      "version": 1,
      "target_kind": "property_record",
      "module_code": "dynamical_properties",
      "record_type": "property",
      "method_code": null,
      "property_code": "custom",
      "core_schema": {
        "type": "object"
      },
      "json_schema": {
        "type": "object",
        "additionalProperties": true
      },
      "ui_schema": {},
      "status": "published"
    },
    {
      "definition_key": "record.thermodynamical_properties.custom",
      "version": 1,
      "target_kind": "property_record",
      "module_code": "thermodynamical_properties",
      "record_type": "property",
      "method_code": null,
      "property_code": "custom",
      "core_schema": {
        "type": "object"
      },
      "json_schema": {
        "type": "object",
        "additionalProperties": true
      },
      "ui_schema": {},
      "status": "published"
    },
    {
      "definition_key": "record.electronic_properties.custom",
      "version": 1,
      "target_kind": "property_record",
      "module_code": "electronic_properties",
      "record_type": "property",
      "method_code": null,
      "property_code": "custom",
      "core_schema": {
        "type": "object"
      },
      "json_schema": {
        "type": "object",
        "additionalProperties": true
      },
      "ui_schema": {},
      "status": "published"
    },
    {
      "definition_key": "record.superconductive_properties.predicted_tc.mcmillan",
      "version": 1,
      "target_kind": "property_record",
      "module_code": "superconductive_properties",
      "record_type": "predicted_tc",
      "method_code": "mcmillan",
      "property_code": "tc",
      "core_schema": {
        "type": "object"
      },
      "json_schema": {
        "type": "object",
        "required": [
          "calculation_conditions"
        ],
        "properties": {
          "parameters": {
            "type": "object"
          },
          "calculation_conditions": {
            "type": "object"
          }
        },
        "additionalProperties": true
      },
      "ui_schema": {},
      "status": "published"
    },
    {
      "definition_key": "record.superconductive_properties.predicted_tc.isotropic_eliashberg",
      "version": 1,
      "target_kind": "property_record",
      "module_code": "superconductive_properties",
      "record_type": "predicted_tc",
      "method_code": "isotropic_eliashberg",
      "property_code": "tc",
      "core_schema": {
        "type": "object"
      },
      "json_schema": {
        "type": "object",
        "required": [
          "calculation_conditions"
        ],
        "properties": {
          "parameters": {
            "type": "object"
          },
          "calculation_conditions": {
            "type": "object"
          }
        },
        "additionalProperties": true
      },
      "ui_schema": {},
      "status": "published"
    },
    {
      "definition_key": "record.superconductive_properties.predicted_tc.anisotropic_eliashberg",
      "version": 1,
      "target_kind": "property_record",
      "module_code": "superconductive_properties",
      "record_type": "predicted_tc",
      "method_code": "anisotropic_eliashberg",
      "property_code": "tc",
      "core_schema": {
        "type": "object"
      },
      "json_schema": {
        "type": "object",
        "required": [
          "calculation_conditions"
        ],
        "properties": {
          "parameters": {
            "type": "object"
          },
          "calculation_conditions": {
            "type": "object"
          }
        },
        "additionalProperties": true
      },
      "ui_schema": {},
      "status": "published"
    },
    {
      "definition_key": "record.superconductive_properties.predicted_tc.scdft",
      "version": 1,
      "target_kind": "property_record",
      "module_code": "superconductive_properties",
      "record_type": "predicted_tc",
      "method_code": "scdft",
      "property_code": "tc",
      "core_schema": {
        "type": "object"
      },
      "json_schema": {
        "type": "object",
        "required": [
          "calculation_conditions"
        ],
        "properties": {
          "parameters": {
            "type": "object"
          },
          "calculation_conditions": {
            "type": "object"
          }
        },
        "additionalProperties": true
      },
      "ui_schema": {},
      "status": "published"
    },
    {
      "definition_key": "record.superconductive_properties.predicted_tc.other",
      "version": 1,
      "target_kind": "property_record",
      "module_code": "superconductive_properties",
      "record_type": "predicted_tc",
      "method_code": "other",
      "property_code": "tc",
      "core_schema": {
        "type": "object"
      },
      "json_schema": {
        "type": "object",
        "required": [
          "calculation_conditions"
        ],
        "properties": {
          "parameters": {
            "type": "object"
          },
          "calculation_conditions": {
            "type": "object"
          }
        },
        "additionalProperties": true
      },
      "ui_schema": {},
      "status": "published"
    },
    {
      "definition_key": "record.superconductive_properties.measured_tc.magnetic_susceptibility",
      "version": 1,
      "target_kind": "property_record",
      "module_code": "superconductive_properties",
      "record_type": "measured_tc",
      "method_code": "magnetic_susceptibility",
      "property_code": "tc",
      "core_schema": {
        "type": "object"
      },
      "json_schema": {
        "type": "object",
        "required": [
          "experimental_conditions"
        ],
        "properties": {
          "experimental_conditions": {
            "type": "object"
          }
        },
        "additionalProperties": true
      },
      "ui_schema": {},
      "status": "published"
    },
    {
      "definition_key": "record.superconductive_properties.measured_tc.specific_heat",
      "version": 1,
      "target_kind": "property_record",
      "module_code": "superconductive_properties",
      "record_type": "measured_tc",
      "method_code": "specific_heat",
      "property_code": "tc",
      "core_schema": {
        "type": "object"
      },
      "json_schema": {
        "type": "object",
        "required": [
          "experimental_conditions"
        ],
        "properties": {
          "experimental_conditions": {
            "type": "object"
          }
        },
        "additionalProperties": true
      },
      "ui_schema": {},
      "status": "published"
    },
    {
      "definition_key": "record.superconductive_properties.measured_tc.other",
      "version": 1,
      "target_kind": "property_record",
      "module_code": "superconductive_properties",
      "record_type": "measured_tc",
      "method_code": "other",
      "property_code": "tc",
      "core_schema": {
        "type": "object"
      },
      "json_schema": {
        "type": "object",
        "required": [
          "experimental_conditions"
        ],
        "properties": {
          "experimental_conditions": {
            "type": "object"
          }
        },
        "additionalProperties": true
      },
      "ui_schema": {},
      "status": "published"
    },
    {
      "definition_key": "record.superconductive_properties.measured_tc.unknown",
      "version": 1,
      "target_kind": "property_record",
      "module_code": "superconductive_properties",
      "record_type": "measured_tc",
      "method_code": "unknown",
      "property_code": "tc",
      "core_schema": {
        "type": "object"
      },
      "json_schema": {
        "type": "object",
        "required": [
          "experimental_conditions"
        ],
        "properties": {
          "experimental_conditions": {
            "type": "object"
          }
        },
        "additionalProperties": true
      },
      "ui_schema": {},
      "status": "published"
    },
    {
      "definition_key": "record.electronic_properties.band_gap",
      "version": 1,
      "target_kind": "property_record",
      "module_code": "electronic_properties",
      "record_type": "property",
      "method_code": null,
      "property_code": "band_gap",
      "core_schema": {
        "type": "object"
      },
      "json_schema": {
        "type": "object",
        "additionalProperties": true
      },
      "ui_schema": {},
      "status": "published"
    },
    {
      "definition_key": "record.electronic_properties.dos_fermi",
      "version": 1,
      "target_kind": "property_record",
      "module_code": "electronic_properties",
      "record_type": "property",
      "method_code": null,
      "property_code": "dos_fermi",
      "core_schema": {
        "type": "object"
      },
      "json_schema": {
        "type": "object",
        "additionalProperties": true
      },
      "ui_schema": {},
      "status": "published"
    }
  ],
  "source_index": {
    "backend/ingest/scientific_evidence.py": {
      "sha256": "7a2d674cd9266c06ea44ddf89ec7711e4d9fdf4a3b0030d2ec586edbbc0514ee"
    },
    "backend/ingest/grobid_document.py": {
      "sha256": "d6654a0f37a3a7b95d41396bd47c06364286928b171fe11c304712bfce6a126a"
    },
    "backend/services/citation_graph.py": {
      "sha256": "87c498307fbcc7c26817d56ab6ffec2c75a92e0a77fd2462b577817cb3d81ff7"
    },
    "backend/ingest/field_review.py": {
      "sha256": "92a5c2c821c864ffda14c840a482097b71ead9b0cace3f187391b2674bca4320"
    },
    "backend/ingest/upload_jobs.py": {
      "sha256": "d071a336113963ecd2b4b32e1d0d155920691f35297c2cb2e76196000889b6e4"
    },
    "backend/ingest/publication_year.py": {
      "sha256": "6d215d629a4e4fe5aac7ded8a9867162b34bf8cf959b98df554b7721730ccec6"
    },
    "backend/ingest/property_evidence.py": {
      "sha256": "239aaa49e0687ca612868a3d2fc5888ffffdf79a98926c28808889d810d9fa50"
    },
    "backend/ingest/paper_summary.py": {
      "sha256": "5ab706dd7fc82ae598e7f13b7528b7bc48a118ff6e9fc7fb83aab937d1ae13f0"
    },
    "backend/ingest/language_contract.py": {
      "sha256": "d94503b2140668d40fd9a743138faae1df91824fe9f32e4e2a97a35a261ef88c"
    },
    "backend/ingest/research_motivation.py": {
      "sha256": "4360ddae9ad1ac60f0e82cc9ec09e6caac5f33c5ccfcfad6c41f32ad21c6e59d"
    },
    "backend/ingest/keyword_extraction.py": {
      "sha256": "6157b3ba20948ec7ce057379d4223c97b0d4b8ee8a4f9b76667ad1c6d521171d"
    },
    "backend/api/rag.py": {
      "sha256": "d947b61b4384313777e524148b43e275567dcca297d403257921ad647b461a9e"
    },
    "backend/ingest/theoretical_subtype.py": {
      "sha256": "e3914c06b2a50e3a7487fe6542d7ad6f1d7f07b0df02ba98492cccf591d5706e"
    },
    "backend/services/classification_catalog.py": {
      "sha256": "562698eec31b74e4c4ac8610aa6f98f816e8eda5842df474023e7f5c51ed2f8b"
    },
    "backend/ingest/state_optimization.py": {
      "sha256": "e0651e5faa005e793328ab4307094e90c689f9219697470672eead73faf044ae"
    },
    "backend/ingest/scientific_drafts.py": {
      "sha256": "040c26e90ae8c309441f73791524f07488ef295be937091c5f869b2f0e22bf57"
    },
    "backend/services/structure_candidates.py": {
      "sha256": "31099233fbb7c2bdb458a94da019a997f1a86ae9b9dab851eeb8325f389f71f4"
    },
    "backend/ingest/property_modules.py": {
      "sha256": "4c76584ee53604aaf97a24bb1540e88f39c9b5108445be48b3ed1e8b9e7dd46b"
    },
    "backend/ingest/domain_extraction.py": {
      "sha256": "2d5fd003ce75a51bded178acdc0fa347e59b73cf5d8a5734e43f092ef6be2514"
    },
    "backend/ingest/fermi_dos.py": {
      "sha256": "916d0bf4f79541c51e86c06fd75cf0bfc6e0f70ac8581df5fec308c029919c68"
    },
    "backend/ingest/property_field_review.py": {
      "sha256": "1ad554c4a2af92c686311b9e75f1aa0be954c9c98bb1ed16b6154e4386839e48"
    },
    "backend/ingest/tc_parameters.py": {
      "sha256": "e4c994cbef6563a61f79c9e8c8761451aeffe37b71215a75253a48d78efa0278"
    },
    "backend/ingest/review_dependencies.py": {
      "sha256": "cfc011a7638e794897c82a1af2a61bb001d14dedf44017ebf8c2d3548a97744f"
    },
    "backend/ingest/condition_rules.py": {
      "sha256": "e43f32ed7bb1db4dac20cf1392edd5040e2852ff160f0d1fd58066a3302ba9f2"
    },
    "backend/ingest/scientific_context.py": {
      "sha256": "ac4ced7065f1dbe731e68848ed06b49f5b615d0b5383d604941adc2bb803583f"
    },
    "backend/ingest/calculation_methods.py": {
      "sha256": "c71c17027776f62257bf77c217c193e979796349bd61903add9471ead519d151"
    },
    "backend/ingest/thermodynamic_stability.py": {
      "sha256": "5fbb6bfff1e53c2120ee6c88ebf5667bf812e33c3773e6027b62910225555485"
    },
    "backend/ingest/property_extensions.py": {
      "sha256": "07e1fc57fea0c5ef91f943272670967d21ed27649d942dc613cf1f64c8ec0e93"
    },
    "backend/ingest/upload_contracts.py": {
      "sha256": "231724e6c6a62524c9b1d48358dc43f9c7071c74fe04d56c43941d1d59f84286"
    },
    "backend/spectra/contracts.py": {
      "sha256": "d9e465aa714029d72b667e85ac0c2726edb24e4727e9520c4c79d2c0de339213"
    },
    "backend/spectra/scientific_review.py": {
      "sha256": "304fec3ac153b942bd83536c9efdf8f80d0bb837c469e76f00d1612b3c01fa88"
    },
    "backend/ingest/form_definitions.py": {
      "sha256": "e8836c6dcfda4ad958958d7374634079849d5622ec792c8c7a837a9e260b7bf5"
    },
    "backend/ingest/material_state_contract.py": {
      "sha256": "529b451708e4e956c2dc170d3cad81d68dd4cd00036f5c18c8c823266a266072"
    },
    "backend/ingest/bibliography_lookup.py": {
      "sha256": "04dd3a7b99974a6644b7bedcf25d65963a27ec2b26615333da06d8facd6d6838"
    },
    "backend/ingest/model_review.py": {
      "sha256": "f8eedfe074e8a76becef3c0c9eeb9d82900fbf27be0703f504e4d568eea24b85"
    }
  }
};

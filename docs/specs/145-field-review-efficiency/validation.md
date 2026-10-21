# 本轮建档与审计验证

日期：2026-10-21。本轮未实施业务性能优化。

## 来源与口径

代码基线：1b34600。当前La–Sc–H草稿：447个核对单元、518个服务端editable_fields入口，包含22个论文信息、184个状态基础项、56个超导子项、176个计算条件项（含空项/规则外项）、8条电子物性和1个结构对象。与此前145项已填计算条件是不同分母。

计数工具直接调用现有API处理函数preflight，读取当前快照/历史/PDF，阻止complete_json；未发新模型请求、未执行保存、未修改真实草稿或服务。未插桩计时与包裹函数计数分两次执行，确认两次snapshot_version一致。

最新一次未插桩preflight为11.661秒；此前11.134秒及12.285秒为其他单次测量，不构成性能改善或稳定p95。返回27.79 MiB，1699条历史result约51.42 MiB。没有计算网络传输、浏览器渲染或整个“完成”按钮的总时长。

三次快照、两次load_results、两次PDF遍历、标题/作者首页核验各两次、544次恢复入口、651次条件依据验证、4618次片段定位、423次状态解释入口、290次关联核验、新LLM请求0。逐字段分布见assets/field-audit.json。计数包含提前返回及嵌套；不可相加当“独立科学审核次数”。无法归属字段的调用单列unattributed_counts，不均摊。

## 清单与图

- field-catalog.md覆盖447核对单元；assets/editable-fields.csv覆盖518服务端可编辑入口，按共享审核单元关联计数。
- 值类型/方法身份等主表单结构键、当前不存在的动态模块、结构文件内部原子与追溯元数据不冒充独立可编辑科学核对单元。原请求“每一个键值对”在本轮先按实际核对/编辑接口清单逐项展开，进一步的主表单DOM覆盖和改值链计数属于逐字段审查的后续范围，未伪称全站所有输入已实测。
- assets/field-review-map.fragment.html最初是图形片段，用户报告直接打开不可读后，现已在原路径补为完整独立HTML：UTF-8、中文语言、移动端视口和内嵌主题/控件样式齐全，不依赖对话宿主或网络。保留原文件名避免用户旧路径失效；对话中先前的片段副本仍独立保存。
- 浏览器验证736px与360px无横向溢出或SVG文本裁切；遍历447项、SSCHA250 GPa规则5/片段36计数一致，建议分支切换有效，N(EF)子入口与人工说明路径可切换，pageerror=0。不是SC-Wiki产品页面性能验收。
- 第一次视觉测试错误等待原生option可见而超时，改为等待attached后通过；这是测试条件修正，不是产品Bug。

## 复现

使用项目Python执行tools/audit_fields.py，显式提供--task、--owner、--output。工具加载当前仓库.env，只打印计数、标签和耗时，不打印密钥；输出不含完整原文或历史JSON。

tools/refresh_assets.py接收已测JSON，同步清单、CSV、图。只修改本Spec资产，不连接后端。

tools/verify_map.mjs接受原路径的完整HTML或早期带iframe预览，分别验证直接页面或iframe。通过PLAYWRIGHT_MODULE/CHROMIUM_PATH选择本地浏览器依赖。现有独立文件可直接用浏览器打开，无需render.py包裹。

完整原始测量与截图在本地.data/issue145-field-audit/，远程不上传业务历史。docs内保留可审查的字段摘要和方法计数。Spec原话、字段去重/覆盖、原图解码/哈希、相对链接与git diff检查已完成。

## 待完成

逐字段讨论、具体延迟阈值、修改后的动态次数、完整“完成/保存人工记录”按钮链及未来性能改动验收尚未完成。历史LLM请求总数和首次PDF解析全部阶段未追溯，不填固定次数。未推送、未部署、不关闭Issue。

## 原路径直接阅读修复

用户原话：

> /Users/mayuan/Codes/SC-Wiki/docs/specs/145-field-review-efficiency/assets/field-review-map.fragment.html 里面都是乱码？！！！！无法阅读

只读检查原字节为UTF-8，本机Chrome自动识别后标题中文正确，但原文件没有编码声明且主题变量为空，缺少独立运行样式。因此未声称已复现同一个查看器的乱码；修复交付为完整UTF-8离线网页，并在用户原路径验证中文和交互。本次不改网站业务代码或字段数据。

## 标红条件调查补充

直接在隔离浏览器上下文导入当前前端EvidenceFieldMarkers.tsx的evidenceProblem，查看15个代表状态：supported/未过期不红；modified属性本身不红；unchecked/missing/uncertain/unsupported无处理标记时红；stale即使过去人工确认/接受也红；required=false不触发来源红；当前人工确认/已接受候选/非空resolution抑制来源红；只填写reason或resolution为空格不消红。此检查是现有谓词行为核查，不是产品修复测试。

red-marking.md同时覆盖本地error属性、动态schema、后台状态降级、派生依赖、普通物性共享标记等入口；不宣称所有ValidationIssue都会画到输入框，部分仅Alert或模块提示。原图新增原因折叠区，原字段数据与计数不变，直接HTML仍保留UTF-8和内嵌样式。

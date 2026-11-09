# 真实场景人工黑盒测试

由 AI 操作现有浏览器，用户审查问题及改变既有逻辑的方案。使用真实网页、登录、PDF 解析和业务存储，不拦截或模拟接口，不通过数据库或直接调用业务 API 代替网页操作。测试辅助代码、用例、交互脚本和本轮材料记录均放在本目录。

## 当前用例

`h3s.json` 保存用户指定的两份 PDF 路径、正文／补充材料角色、账号、浏览器和逐阶段操作。原 PDF 保持在用户给定位置，每轮记录大小与 SHA-256，确保修复后重传相同来源。测试前通过网页核对实际登录邮箱及角色；工具不从 Cookie、localStorage 或其他存储提取账号或令牌。

- 用户：`myth620137018@163.com`，Safari，`http://127.0.0.1:5173/upload`。
- 超级管理员：`mayuan_mark@163.com`，Chrome，`http://localhost:5173/upload`。这是当前已打开的实际地址，两个浏览器保留各自会话。
- 论文正文：`2014 H3S-段德芳.pdf`；补充材料：`2014 H3S supplymentary.pdf`。
- 检索体系：H3S。化学式搜索按元素匹配，最终必须打开本轮论文并核对身份和材料状态，同体系的旧结果不能作为通过证据。

## 操作顺序

1. 用户上传并解析，生成可校对草稿，暂不送审。
2. 每次发现问题先使用全局 `big-project-investigator`；调查与流程图输出到对话。对照现行 Issue、Spec、Overview 和代码，旧逻辑／旧需求没有落实则直接修复，合理验证后提交，并更新原 Issue 与 Spec；需要颠覆既有逻辑时，先展示方案征求用户意见。修复之后取消并清理本轮未送审任务，再上传原文件重新解析，不以旧草稿或旧提取结果代替重跑。记录每轮任务、源码、实际模型、复用与重跑范围以及结果。重复至无阻塞问题，再正式提交审核。
3. 超级管理员找到一处有依据的真实待修改项，填写具体拒绝意见并退回。记录字段、原文依据和交接身份，不故意写坏科学事实制造问题；若无真实待修改项，向用户说明后讨论该步骤。
4. 用户修改退回稿，保存、重读核对后重新提交，保留修改前后内容及依据。
5. 超级管理员复核，填写通过日志并批准；重读审核结果和正式交接记录，核对上传者与审核者。
6. 在探索中搜索，打开本轮论文，核对论文 ID、标题、DOI、批准版本和材料状态。界面结果是公开读取证据；需要进一步证明底层数据库记录时，只读核验另行明确记录，不将同名命中说成数据库核验。

问题记录及每轮观察是测试证据，未完成行动的协作状态仍以 GitHub Issue 为准。现有规则入口为 #179 文件角色、#174 表单约束、#147 字段审核、#176 科学字段、#192 交接快照、#178 搜索及 #35 清理生命周期；具体问题应继续查阅最新约束。

## 浏览器入口

使用 macOS 自带 `osascript` 和 Python 3.9+，不安装浏览器或第三方依赖，不新建浏览器会话。两个浏览器必须已运行并完成真实登录。操作需要浏览器允许 Apple 事件 JavaScript；关闭时工具记录错误，不自动更改设置：

- Safari：设置 → 开发者 → 允许来自 Apple 事件的 JavaScript。
- Chrome：查看 → 开发者 → 允许 Apple 事件中的 JavaScript。

在仓库根目录执行：

```sh
python3 "tests/TestForRealScenario/scenario.py" check
python3 "tests/TestForRealScenario/scenario.py" start
python3 "tests/TestForRealScenario/scenario.py" tabs --actor user
python3 "tests/TestForRealScenario/scenario.py" tabs --actor superadmin
```

`start` 输出本轮绝对路径，下面用 `<本轮路径>` 表示。`tabs` 只列出对应网站的窗口、标签标识和 URL；Safari 标签使用序号，Chrome 使用标签 ID。每次操作前重新核对这些标识，不能直接操作当前活动标签。查看网页：

```sh
python3 "tests/TestForRealScenario/scenario.py" inspect --run "<本轮路径>" --actor user --window 81 --tab 1
```

窗口及标签数字只是用法示例，必须以当前 `tabs` 输出为准。`inspect` 返回可见文字和控件信息，不读取密码值或令牌；它是 DOM 观察，不等于截图或科学来源的目视验收。

需要点击或填表时，将同步 DOM 交互脚本存入本轮目录，再执行：

```sh
python3 "tests/TestForRealScenario/scenario.py" exec --run "<本轮路径>" --actor user --window 81 --tab 1 --script "<本轮路径>/操作.js"
```

脚本使用 `return` 返回观察结果，按实际页面查找唯一控件，不以全表单赋值替代交互，不调用业务 API、不修改登录状态。异步页面变化应在后续独立读取中核验；每个阶段核对真实身份和结果后再继续。

用户明确要求直接使用给定 PDF 路径进行后续测试。以下命令重新核对来源哈希，将原文件的真实字节作为浏览器 File 对象交给正文／补充材料输入，并触发上传组件的正常变更事件；后续仍点击网页“开始上传并解析”。这一步不覆盖原生文件选择器的能力验收。

```sh
python3 "tests/TestForRealScenario/scenario.py" attach --run "<本轮路径>" --actor user --window 81 --tab 1
```

记录观察，例如任务 ID、论文 ID、具体退回意见、修改内容、通过日志及结果链接：

```sh
python3 "tests/TestForRealScenario/scenario.py" note --run "<本轮路径>" --actor user --phase parse --text "记录实际观察，不填示例成功结果"
```

阶段 ID 见 `h3s.json`。`note` 只保存操作者记录，不自动判定阶段通过，也不代写业务审核日志。业务通过日志必须在超级管理员网页填写并重新打开核验。

## 材料与验证边界

`runs/` 保存本轮来源清单、源码 SHA、工作区状态、网页观察、交互脚本与失败记录，默认不提交 Git；源码 SHA 与工作区状态必须一起解释，不把未提交工作区当成纯提交版本。账号登录信息、密码和令牌不写入用例或交互脚本。已有业务草稿与正式论文不批量清理，只处理当前测试轮次明确记录的任务。

辅助工具自检：

```sh
python3 -m unittest discover -s "tests/TestForRealScenario" -p "test_*.py"
```

工具自检通过、文件哈希通过、网站可访问，都不代表真实业务流程已通过。上传解析、退回返修、批准及搜索必须分别保留本轮实际结果；中断或无法操作时明确记录未完成。后续修改科学表单、PDF 字段或标准键时，继续执行仓库要求的专项回归与真实来源重跑。

固定失败重放使用项目 Python 环境执行（包含真实 Redis 的隔离实例和隔离对象存储，不操作业务库）：

```sh
/Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python -m pytest "tests/TestForRealScenario" -o "python_files=test_*.py verify_*.py"
```

`fixtures/h3s-filling-failed.json` 保留真实失败响应；`test_candidate_coverage.py`验证通用候选去向、正式最终关口、既有模型上下文和保存重读；真实模型重跑另存各轮证据，不以构造响应代替科学验收。`verify_review_failure.py` 验证技术错误不被依赖变化提示覆盖；成功字段和真实未核对状态分别保留。

`verify_worker_capacity.py` 执行真实本地启动函数验证并发配置透传，并用独立TCP Redis及正式RQ启动入口验证“10项同时执行、第11项排队”。`worker_capacity_probe.py` 只占用隔离任务槽，不解析PDF、不调用模型；它验证容量，不能作为十篇论文科学解析通过的证据。本机当前 `.env` 的 `UPLOAD_LLM_CONCURRENCY=10` 已通过实际进程注册核对，恢复容量后再继续正文／补充材料的单任务黑盒流程。

CaH6的第三轮真实后处理失败中，fixtures/cah6-dos-archive-failed.json保留CaH4 50GPa DOS的完整独立状态、必要原文及实际模型响应；仅按状态隔离，没有改写科学值或来源。test_cah6_dos_archive_replay.py固定重放宿主来源档案误入模型字段检查的故障，验证当前值、单位、档案及候选去向。它不调用模型或业务库，不替代CaH6新上传黑盒；完整失败/成功后处理制品仍在对应runs目录。

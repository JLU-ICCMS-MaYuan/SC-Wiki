# 本机验证记录

环境为本机原生实时开发、mayuan分支；未推送或部署。

## 回归与静态检查

四宿主新增用例在旧代码均因没有拆分入口失败。实现后上传、返修、管理员和超级管理员4项交互通过，覆盖预览、取消零写入、确认、稳定身份与来源保存；变更仅重绘原卡与新增卡，不创建模型任务。另5项覆盖原物性对象/来源引用保持、陈旧编辑、原卡删除、只读权限收回与邻卡最新值保护。首次测试夹具缺validation.structure_hash导致DOM断言失败，已补正确夹具且原失败保留；没有放宽生产检查。

完整表单237通过、12变异全部检出、字段契约通过、TypeScript及前端构建通过。第一次TypeScript未知结构字段作为ReactNode报错已修正Boolean条件。网页预览发现计数多余花括号，按现有i18n占位符修正，4宿主再验计数通过。构建仅有既有体积提示，未放宽阈值。依赖清单/锁文件未改；本轮npm审计及Bandit/pip_audit不可用边界沿本轮报告，不重复计通过。

## GPT原草稿真实网页验收

原Task d789acceee124022b3257f84780d1156；上传者Safari核验myth620137018@163.com/用户，先将账号模型切回原gpt-6.1-sol，未改原Flash任务模型身份。原LaH9@50 GPa状态state-d3a7ec5c19fad5b56094在网页预览P6₃/mmc物性卡与Cc结构卡，明确确认、保存并重开。

原52状态变53；原物性键、两个物性模块及3条记录、方法/共同参数和来源全文保持；新结构卡structure-state-4125a619-d9d3-416c-860a-4733bbe336b3只有原Cc晶胞，无物性记录。晶胞哈希31192e2f9c28533275df7e50237f5b39f58ba0ab82ad3c12fc03c4d3132c976c、规范内容及来源对象与原稿全等；原物性卡群号194、晶系hexagonal。其他51状态和paper全文全等。网页重开显示同一结果，未用业务API/SQL改值。

证据：tests/TestForRealScenario/runs/20261111-peng2017-flash-blackbox-01/gpt-split-reread.json、gpt-split-reopened-ui.json及gpt-before/after-split.json.gz；网页事件单独保留。一次innerText读取超时后改用不强制布局的textContent重读，没有重复拆分。普通输入、保存未运行模型核对。

## 边界

本次实现和GPT网页拆分已验证；后续受影响科学字段核对和两模型五阶段黑盒仍未完成。没有新增API、数据表、科学字段或审核流程。GitHub远程Spec链接待验证，未为链接自行push。Issue保持本地交付状态说明，不以此宣称整篇通过。

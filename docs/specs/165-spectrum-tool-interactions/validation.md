# 实现与验证记录

日期：2026-10-27（Asia/Shanghai）。Issue：[#165](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/165)。

## 已实现行为

- 两个并列拖动按钮直接进入对应工具；删除重复联动开关，联动权重算法和参数不改。
- 初始/退出为idle，只选点查看，不移动谱点；持续工具同钮退出、异钮切换，标定槽单独识别。
- 增加点可先选工具后选已有起点；首次点击不写Document，8屏幕像素内吸附，未命中不创建点。起点有效后复用连续加点、原直连插入和未连接点补接。
- 退出清理临时手势、pointer capture和吸附会话，保留已完成的编辑。全屏MUI Dialog中的Esc在捕获阶段处理；输入框聚焦时也可退出工具。
- 主题主色由useTheme读取，持续工具专用CSS变量区分浅色未选中与深色选中，不覆盖其他.active标签。
- 撤销标定时回到idle，防止旧取点身份与高亮槽失配；保存、删除、撤销等立即动作沿用。

## 自动验证

从仓库根执行：

    DEBUG_PRINT_LIMIT=1000 npm --prefix frontend run test:upload-ui -- tests/01_decentralized_uploading/spectrum-*.test.tsx tests/01_decentralized_uploading/property-spectra-navigation.test.tsx tests/01_decentralized_uploading/upload-spectrum-save-navigation.test.tsx

13个文件、95项测试全部通过，其中新增工具交互测试11项，直接渲染正式Editor/Canvas，包含完整Dialog。单元测试中的SVG矩阵仅作浏览器坐标接口替身，实际缩放和指针映射由下述浏览器补验。

frontend下npm run build通过；现有大包与3Dmol eval提示仍存在，未修改依赖。git diff --check通过。

## 正式页面浏览器

复用backend/tests/manual_editor_server.py，在临时SQLite与文件存储中运行实际FastAPI谱路由；所有浏览器API被重定向到127.0.0.1:8195，前端为专用5175端口。真实用户业务库未参与。
α²F夹具将原图及标定同步旋转为纵轴，DOS使用横轴；浏览器真实选择、拖动、插点、补接、保存和刷新。

| 标准 | 证据 |
|---|---|
| SC-001 | 默认idle不能拖动；单点只改目标点；联动改变相邻点，撤销/重做恢复 |
| SC-002 | 增加点先激活；缩放后9px外不吸附、7px内吸附；首次仅选起点，点/线不变 |
| SC-003 | 组件测试逐项同钮退出/异钮切换/标定槽/Esc；全屏Dialog回归；浏览器确认退出后不会继续新增 |
| SC-004 | 纵轴α²F原直连插点替换正确、未连接补接保留，正式保存刷新回读；横轴DOS不改其他分波；既有导航/编辑回归通过 |
| SC-005 | 纵轴α²F、横轴DOS、高倍缩放、1440px桌面与390px窄屏通过；不冒称全部材料和所有组合人工验收 |
| SC-006 | 浏览器读取实际计算样式：选中rgb(79,70,229)/白字，未选中rgba(79,70,229,0.08)；两张截图已目视核对，控件aria-pressed一致 |

6组浏览器场景通过，无pageerror。第一次验证暴露外层Dialog吞掉Esc的问题，修复捕获阶段处理并新增真实Dialog组件回归后重新跑通全部场景；保留这一限制的来源说明，不将单元测试替代浏览器。

- [浏览器报告](validation/tool-interactions-browser.json)
- [桌面两按钮与主题深浅状态](validation/linked-dark-single-light.png)
- [390px窄屏两按钮](validation/mobile-two-buttons.png)

## 范围保护与限制

正式dragInfluence.ts和独立Demo共27个源文件在实施前后逐字哈希一致，记录见[保留文件哈希](validation/preserved-sources.json)。用户已有的两处参数修改不纳入提交。

本轮没有后端算法改动或数据库迁移；浏览器测试使用实际HTTP/SQLite，但身份由测试夹具注入，不代表生产JWT/业务库/网关验收。现有旧浏览器手工编辑脚本的起点与按钮名称断言同步更新，未将其整套重跑算入本轮结果。

未推送、未部署；源码已实现不等于生产环境已发布。远程Spec链接待推送授权后验证，Issue保持开放。

## 2026-11-05 六工具界面调整验证

本轮按新增原话及图4/5核对后的实际答复实现。下方记录本轮结果；上文2026-10-27记录是历史证据。

### 实际行为与覆盖

- 六工具按选点、移动、批量拖动、单点拖动、增加新点、批量框选竖排，滑条在下；Alt+1～6 选择对应工具，重复快捷键保持选中，按钮再次点击仍退出。物理数字键兼容 macOS Option 特殊字符。
- 选点拖动不改变数据；移动只改变视口；批量和单点保持原算法。组合输入、额外修饰键、保存中及离开确认期间不切换工具；工具高亮与画布一致。
- 显示其他分波、原图开关紧邻适应窗口左侧，隐藏原图禁用滑条。桌面1440×1000与窄屏390×844实际测量竖排、控件顺序、画布空间和横向溢出，截图已目视检查；窄屏滑条完整显示。
- 确认坐标修改真实所选点，可撤销重做；正式HTTP保存后重新读取manual文档坐标一致。图3像素卡和状态换算说明不展示。
- 方向切换保留，α²F纵频率轴及DOS横频率轴均验证“只改幅值”不改变频率方向；联动范围说明隐藏。单曲线隐藏编辑曲线；正式组件交互回归保留同文档多曲线切换及清理旧锚点。
- 原直连插点、断口补接、8屏幕像素吸附、先选工具再选起点、保存刷新及分波隔离通过。原有版本和权限边界沿用谱线回归；本轮浏览器身份由隔离夹具注入，不冒称生产鉴权验收。

### 自动验证结果

| 检查 | 本轮结果 | 证据 |
| --- | --- | --- |
| 谱线、详情导航及保存入口回归 | 15文件124项通过；工作区和隔离归档均通过 | [谱线日志](validation/2026-11-05-six-tools/spectrum-tests.log) |
| form-contract | 13文件188项通过，含上传、返修、管理员、超级管理员 | [表单日志](validation/2026-11-05-six-tools/form-contract.log) |
| form-contract:mutation | 8项渲染回退、4项漏红回退全部检出 | [变异日志](validation/2026-11-05-six-tools/mutation.log) |
| TypeScript + Vite生产构建 | 通过；保留原大包及3Dmol eval提示 | [构建日志](validation/2026-11-05-six-tools/build.log) |
| 正式React/HTTP/SQLite浏览器 | 8组检查通过，pageerror为0，写请求仅隔离manual接口 | [浏览器报告](validation/2026-11-05-six-tools/tool-interactions-browser.json) |

命令沿用本目录quickstart；谱线测试为
`npm run test:upload-ui --prefix frontend -- tests/01_decentralized_uploading/spectrum-*.test.tsx tests/01_decentralized_uploading/property-spectra-navigation.test.tsx tests/01_decentralized_uploading/upload-spectrum-save-navigation.test.tsx`。
另执行 `npm run test:form-contract --prefix frontend`、`npm run test:form-contract:mutation --prefix frontend`、`npm run build --prefix frontend`。
浏览器使用本轮更新的 `tests/01_decentralized_uploading/spectrum-tool-interactions-production.cjs`，前端5175、后端8195均为本轮临时隔离进程。

首次新增坐标测试使用1.1换算后做浮点严格相等，得到89.99999999999999而非90；改用可精确表示的幅值1作为测试数据后，完整124项通过，没有改生产计算或降低有效精度。窄屏滑条检查后缩短其轨道并以全新SQLite重新运行全部浏览器场景，通过后保留最终截图。

- [桌面六工具与精简侧栏](validation/2026-11-05-six-tools/six-tools-desktop.png)
- [390px六工具与完整滑条](validation/2026-11-05-six-tools/six-tools-mobile.png)
- [验证源码及保持不变的联动/Demo文件摘要](validation/2026-11-05-six-tools/source-snapshot.json)

### 需求映射与边界

FR-001/010/011、SC-007由六工具快捷键、选点/移动及布局实测覆盖；FR-012/013、SC-008由开关交互、坐标确认、撤销重做及保存重读覆盖；FR-014、SC-009由双轴方向限制、单曲线隐藏与多曲线组件交互覆盖；原SC-001～006由本轮谱线和浏览器回归覆盖。无需恢复已由#167移除的零频工具。

五张用户原图已保留原字节并重新解码校验，索引见spec.md；图片仅作材料。独立Demo、联动参数、后端算法和接口未修改；其他任务的工作树改动未纳入本次提交。旧浏览器脚本仅同步新按钮名称，未将其所有套件冒称重新运行。无业务数据迁移、推送或部署；远程Spec链接继续待验证，Issue保持开放。

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

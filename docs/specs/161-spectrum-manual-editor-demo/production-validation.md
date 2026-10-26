# 正式接入验收

## 已验证

- 74项后端测试通过：其中20项人工修订测试经正式FastAPI路由、正式context权限、SQLAlchemy模型与实际SQLite文件验证持久保存、409版本冲突、403无权、422非法、旧运行不变、单位换算、其他曲线保留、公开过滤、CSV来源、零频状态及返修身份重绑定。登录身份由测试依赖提供，不将其冒充真实JWT端到端验收。
- 42项前端测试通过：正式数据适配/编辑核心、现有谱入口、三模式、历史导航、主表单未保存输入及几何回归。
- TypeScript/Vite正式前端构建通过；存在项目已有的3Dmol eval及大分包警告。
- [浏览器结果](assets/production-browser-validation.json)：正式React路由连接隔离后端HTTP，后端使用正式谱接口、SQLite文件和本地FileStorage。实际执行α²F编辑、写入新版本、回跳、刷新、历史回读、竞争保存后的409保留输入、PhDOS只保存H且La不变、390px布局；所有写入只到隔离manual端点，不请求真实业务API。
- Demo调参原文件SHA-256保持 `b3c8c9e32bfe0698f80def9171844e26b819e0c50e5e3feaebb62a049311f4e0`，原文件未编辑或暂存。正式配置复制用户认可的2/.3/1/.1，正式业务路径不导入docs样例、固定图片或Demo本机草稿。
- 将本次43个暂存文件连同已提交基线导出到独立候选目录，复验74项后端、42项前端和正式构建均通过。候选不包含同时进行的预测模块改动，也不包含用户Demo调参原文件的未提交修改；正式调参副本已包含在候选中。

## 可复查图片

- [正式编辑器](assets/production-editor.png)
- [保存后详情](assets/production-saved-detail.png)
- [冲突保留输入](assets/production-conflict.png)
- [窄屏详情](assets/production-mobile-detail.png)、[窄屏编辑器](assets/production-mobile-editor.png)

## 未完成的外部环境验证

尝试在本机MySQL 3307创建独立测试库失败（当前账号无法完成建库），没有修改业务库、表或数据。本轮SQLite验证不能替代MySQL行锁与JSON持久化的实际环境复验；隔离MySQL测试支持 `SCWIKI_MANUAL_TEST_DATABASE_URL`，明确拒绝不含 `issue161_test_` 的数据库。未执行生产部署、迁移、推送或业务数据回填。

本轮软件实现与隔离存储链路通过，不代表整谱科学正确、训练就绪或已获科学采纳。人工修订后积分明确失效，需要另行核对；旧自动结果和历史保留。

## 运行隔离浏览器测试

使用 `backend/tests/manual_editor_server.py` 在 `/tmp/scwiki-manual-test-*` 目录创建独立SQLite/文件存储，服务仅监听127.0.0.1:8191。指定该隔离目录的DATABASE_URL与FILE_STORAGE_LOCAL_ROOT，以及测试专用JWT_SECRET_KEY。脚本拒绝非测试目录或非SQLite地址。

运行 `node tests/01_decentralized_uploading/spectrum-manual-production.cjs`；它将浏览器的全部 `/api/` 请求转发到隔离接口，使用正式页面组件。不得把测试服务器作为正式部署使用。测试完成后关闭该进程，保留证据文件供复查。

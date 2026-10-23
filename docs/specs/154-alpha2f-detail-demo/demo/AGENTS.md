# 原型工作约定

本目录是 #154 与 #155 共用的独立交互 Demo，正式前后端保持隔离。运行本地服务并打开预览，不把启动步骤交给用户代劳。

有用户截图作为样式与问题参考，按其明确要求重排分区；视觉方案待用户查看后认可。新的反馈仅改变对应范围，不能把原型认可自动解释为生产接入授权。

应用界面在 src/ 中。保留 .openai/hosting.json、worker/index.js、scripts/prepare-sites-build.mjs、tests/sites-worker.test.mjs 的运行约定。部署前应构建并执行托管测试，但本次未要求部署。

用户请求优先。仓库根 AGENTS.md 的 mayuan 分支检查、只提交本任务、简体中文及禁止自动推送规则继续适用。

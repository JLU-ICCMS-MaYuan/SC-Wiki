# 验证路径

1. 确认 mayuan 分支，用户已准备 Conda，已有 .env 仅指向本机独占实例。
2. make deploy CHECK_ONLY=1：检查不写入配置或数据；历史 dist 包不兼容应明确拒绝。
3. make deploy：在新实例或匹配归属的实例完成安装恢复，检查 make status。
4. 访问 http://127.0.0.1:5173/、/health、/api/form-definitions；检查 worker 注册。
5. 修改工作区源码，验证 Python 重载、前端热更新及 Go 重新编译。
6. make stop 后检查端口释放，make start 后再次检查接口。
7. 干净源码下 make frozen，核验包并在隔离目录恢复比对；未提交改动时必须明确拒绝。
8. 旧实例迁移报告全部通过后删除 Lima，检查专用路径和进程消失。

实际结果记录在 validation.md；外部服务和 OCR 模型未测试时明确注明。

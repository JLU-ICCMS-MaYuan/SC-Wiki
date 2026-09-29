# 命令契约

- make deploy：Mac 安装本机依赖并按现有约束恢复 dist 唯一数据包或初始化；已有实例禁止无条件覆盖。
- make deploy CHECK_ONLY=1：只读报告依赖、端口、源码/包冲突；失败非零退出。
- make setup：仅准备依赖及配置。
- make start/stop/restart/status/logs S=python：操作本项目原生服务；日志服务名作为数据传入，不执行 shell 片段。
- make frozen OUTPUT=/绝对路径/包.tar.gz：逻辑冻结业务数据；拒绝未提交源码、归属不明、在途任务和已存在输出；失败恢复原有服务。
- make test/test-go：使用本项目运行环境执行已有测试入口。

Mac 的默认 make 自动选用 Makefile.mac；Linux 继续现有入口。运行目录 .local、业务数据 .data 不进入 Git。启动成功不等于外部 LLM、SMTP 或可选 OCR 模型已验收。

Java21 合并完成后，Mac 的 make setup/deploy/start 不再创建或引用独立 .local/grobid-java；安装器必须验证 sc-wiki 中实际 Java 版本。Linux 行为保持原样，旧包的服务清单不一致仍明确拒绝。

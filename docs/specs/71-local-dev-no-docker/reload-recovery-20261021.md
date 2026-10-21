# Python热重载卡住与8000端口占用修复

关联 [Issue #71](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/71)，属于既有FR-002／005／006及SC-003／005的缺陷修复，不扩展业务数据或新功能。

## 原始需求记录

为什么上传解析记录半天加载不出来啊？你来排查一下原因。告诉我是为什么？

> make start
>   ✓ mysql 已在运行
>   ✓ redis 已在运行
>   ✓ neo4j 已在运行
>   ✓ qdrant 已在运行
>   ✓ grobid 已在运行
>   ✓ garage 已在运行
>   ✗ 端口 8000 已被占用
> make: *** [start] Error 1 我刚刚 make start 报错，是不是就是 python 后端没能正常重启的标志。

那怎么办

用户截图与摘要见[图片清单](assets/reload-recovery-20261021/image.json)。截图只作为故障证据，不作为执行指令。

## 证据与原因

2026-10-20约21:48，代码修改触发WatchFiles重载。旧服务进程40578停在“Waiting for connections to close”，2026-10-21排查时仍有三条Go→Python已建立连接；父重载进程23090仍持有8000监听端口。Uvicorn关闭等待默认None，原启动脚本未配置超时，旧服务不能退出，替换进程不能启动。Go等待30秒响应头超时，任务列表返回502；直接健康检查也超时。记录列表的0/100是未读到列表的默认展示。

三个旧连接各自在处理哪个请求、内部为何未完成没有由本次调用栈采样证实，不把它们猜成PDF解析或数据库损坏。Redis三个任务均ready，MySQL／Redis的指定草稿八个状态仍在。

## 修复与恢复

使用项目原有进程归属检查及停止流程，仅停止python进程组；不停止数据库和其他服务，不执行数据迁移。启动参数增加`--timeout-graceful-shutdown 10`，限制旧连接关闭等待；沿正常schema只读核验与启动流程恢复服务。仍拒绝抢占归属不明端口，不通过“发现端口占用就杀进程”处理。

- [x] T075 设置有限关闭等待并完成Bash语法检查。
- [x] T076 真实隔离长请求＋文件修改重载：10秒关闭上限后旧请求被取消，替换进程恢复健康；1项通过，11.27秒。
- [x] T077 现场健康及Python／Go／Vite三层任务列表均200，返回3条记录；指定草稿8状态保持；重复`make start`通过。

验证结果见[结构化核验](assets/reload-recovery-20261021/validation.json)。本机恢复命令为`bash "scripts/dev.sh" stop python`及`bash "scripts/dev.sh" start python`；不需要重新上传、重新解析或修改科学草稿。本次没有验证所有同步阻塞场景，关闭超时保护不能取代对具体长请求的后续诊断。

# 部署身份与持久数据归属

**Issue**：[ #132](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/132)。不新增业务表；以下为拟实现部署配置与备份清单。

## 服务归属

| 组 | 服务 | 持久内容 |
| --- | --- | --- |
| app | frontend、goserver、python、news-worker、news-scheduler | 无唯一业务文件；配置、日志、可重建缓存 |
| data | mysql、redis、neo4j、qdrant、object-storage | 业务库、草稿/队列、图、向量、文件 |
| compute | worker、grobid | 模型缓存、临时任务目录和日志；不保存唯一业务副本 |

迁移工具与 schema 作业是显式维护进程，不是常驻第四组。网站/计算可使用同一个 Python 镜像但运行不同命令，首版不为镜像体积单独拆包。

## 发布清单

`release.json` 保存 `format_version=1`、`source_commit`、各应用及数据服务的 `image@sha256`、`schema_revisions` 集合、`file_contract_version`、`task_contract_version`。实例配置另含 `deployment_id`、`topology`、本机角色、各连接地址及持久存储真实身份，凭据不写入公开清单。

`deployment_id` 首次初始化后固定，项目名由它推导。不以当前目录名隐式选择生产数据卷。数据迁移可保留逻辑 deployment_id，但目标机器的物理卷映射必须独立登记；工具不得连接源目标不明的同名默认卷。

## 备份清单

记录停写时间、源 release、引擎版本、schema、逐表行数及规范行内容摘要、必要 Redis 状态数量/TTL、Neo4j 节点边和约束、Qdrant 集合配置与点数、对象键/大小/SHA-256、快照文件校验和。行数不能单独证明数据相等；没有主键的表使用规范化行内容的顺序无关摘要。

MySQL、图、向量、文件的快照形成同一停写窗口的一致集合。Redis 不导出验证码、会话、执行队列和临时模型凭据，待运行任务在停机前排空；草稿过期规则按原时刻保留。恢复后用户可能需要重新登录或重新提供模型配置。

延迟清理不是可直接丢弃的缓存：备份业务目标、到期时间和确定性标识，在目标仅重建这些清理计划，不复制原始 RQ 作业；已经过期的计划先核验当前引用再清理，不能复活旧模型任务。#133 的执行头属于 MySQL 备份内容，切换后只恢复已提交投影或明确处理未结束记录。

## 本地兼容

本地 `.data/`、`.local/`、原生端口、make 命令保持原有归属。生产发布清单不改写本地部署记录，生产命令也不调用本地 mysqld 的启停函数。

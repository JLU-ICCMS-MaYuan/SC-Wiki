# MySQL补验收与七项旧失败收尾

## 用户指令与范围

用户对上一轮“MySQL专用验证跳过、旧失败只作基线区分”的说明标注后要求：

> 请完成

本轮完成该标注范围：补跑原六项MySQL验证，修正七项过期测试/夹具，并扩大实际存储、并发与来源权限回归。不包含Flash科学读数收敛、官方OpenAI账号实调、整篇解析/批准、部署或Git推送；这些既有门仍单独保留。

## 最终结果

| 验证层 | 结果 | 实际含义 |
| --- | --- | --- |
| 原六项MySQL专用验证 | 6 passed，零跳过 | 事务绑定/外键/版本、权限/修订可见性、HTTP归属版本，以及人工谱保存、重算、状态确认三组行锁竞争 |
| MySQL扩展组合 | 79 passed，零跳过 | MySQL 8.4.2的正式路由/谱保存/历史/重算/确认，加7项图片来源与快照测试；同组合还包含数学单元检查 |
| 旧失败与准入反例 | 16 passed | 原七个失败已消除；两文件共11项通过，新增5项非测试目标/未授权拒绝反例 |
| 任务专属隔离源码的综合回归 | 525 passed；SQLite轮6项MySQL专用跳过 | 此轮的六个跳过与上面的实际MySQL六项逐项对应，已全部执行，不再作为未验证项 |

最新79项在“提交71b02686＋本任务8个测试/脚本文件”的独立源码副本再跑通过。隔离副本没有共享工作区正在进行的image_catalog等其他改动。具体测试路径、日志和SHA见[evidence/20261110-mysql-followup](evidence/20261110-mysql-followup/verified-source.json)。没有新增或放宽生产数值容差，没有增加等待超时来掩盖竞争。

上一轮四宿主233项、8＋4变异门与字段契约摘要保留为原执行记录；本轮没有重跑它们，也没有修改生产表单或科学字段契约。

## 独立MySQL与数据保护

使用已有Conda环境的MySQL 8.4.2二进制，自建临时实例。绑定127.0.0.1随机端口，端口不是业务3307；数据库名为严格issue137_test_加12位十六进制。测试入口同时校验显式开关、地址、数据库名、实际@@port及@@datadir。同步/异步连接必须指向同一隔离库；URL或数据目录不匹配时禁止写入。

首次尝试用ORM直接建完整表被MySQL的JSON默认值语法拒绝；随后改用仓库实际initialize迁移链建立全新隔离Schema，没有修改产品模型、迁移文件或关闭外键来通过。完整Schema会启用正式工作稿；旧谱夹具却始终返回未规范化的原草稿，导致状态签名409。夹具已改为读取实际context生成的权威工作稿，仍保留状态真实变化时的409断言。

可重复入口是scripts/verify_visual_mysql_isolated.py，指定不存在的证据目录。脚本创建自己的进程、数据目录和库，验证完成后仅停止自己持有的Popen进程并清除临时数据，保留日志和结果。最终运行的server_stopped和data_directory_removed均为true。没有对业务MySQL、真实论文或用户草稿执行DDL、写入或清理。

## 原六项逐项对照

1. test_mysql_commit_binding_foreign_keys_and_versions：正式绑定、提交重读、异常事务回滚、修订复制和原运行不变。
2. test_mysql_paper_permission_and_revision_visibility：私稿/正式论文权限及批准版本可见性。
3. test_mysql_navigation_assignment_http_versions_permissions_and_pending_calibration：真实HTTP归属、202队列/409旧版本、422未知状态、403越权和历史保留。
4. test_mysql_concurrent_manual_saves_only_one_version_commits：两个并发人工谱保存分别200和409，仅增加一个版本。
5. test_mysql_concurrent_recalculations_only_one_commits：两个并发重算分别200和409，仅增加一个运行，旧结果不变。
6. test_mysql_revalidation_row_lock_only_one_confirmation：两个并发状态确认分别200和409，不重复确认。

## 七项旧失败如何修正

以下调整是恢复测试与现行#203/#226/#189契约的一致性，不改变产品科学含义。

| 原失败 | 已证实的原因 | 当前断言 |
| --- | --- | --- |
| 固定14个字段 | #203软件分组和#226名称/单位独立键已使旧数量过期 | 核对契约全部条件路径、Tc/λ/ωlog/μ*和独立名称/单位，继续验证真实依赖及非父级授信 |
| 扩展重排找不到原路径 | 旧sscha.energy_cutoff已是标准软件参数，不是人工扩展；扩展现在逐子字段核对 | 用合法field_key人工扩展，重排后逐名称/值类型/原始值核对稳定身份和哈希；共同参数/不同方法/结果仍分开 |
| 标注变化应改数值哈希 | 现行名称/单位拥有各自键，不能当作原数值变化 | 只改名称时名称哈希改变，数值、单位和相邻ωlog哈希不变 |
| 范围拆分要求所有版本不变 | 测试同时建立了原先不存在的显式共同方法归属 | Tc–μ*值和旧稳定身份保留；新增4个空名称/单位键逐项检查；真实方法绑定改变的字段必须失效重核，未变共同量仍复用 |
| 字段设置保存只有一个设置对象事件 | 名称与单位现为独立字段 | 固定已有单位后只改名称，恰好一个名称字段事件；只改μ*仍不伪造Tc编辑事件 |
| 上传保存应追加旧审计数组 | 现行只更新每字段当前_field_baselines，不追加不可变旧历史 | 验证实际编辑者、首次原值、当前值、同值零追加、后台不冒充人工、Redis事务及保留期限一致，拒绝伪造历史 |
| 结构请求须重复block_id和blocks | #224当前模型视图只发source_id/页/原文；原block_id/框保留在宿主归档 | 全部90行原文与身份对照宿主原始请求；回执只引用已发source_ids，call_id配对不变，当前索引无已读重复 |

保留改前7 failed/4 passed和MySQL初次3 passed/3 errors的真实日志，未覆盖删除。最终旧失败文件11项全部通过；新增隔离准入5项全部通过。

## 复核命令

使用项目Python执行：

```bash
PYTHONDONTWRITEBYTECODE=1 "/Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python"   "scripts/verify_visual_mysql_isolated.py"   --evidence-dir "/tmp/scwiki-visual-mysql-new-run"
```

证据目录必须不存在；mysqld默认使用同Python环境中的二进制，也可明确传--mysqld。脚本仅对自己的新库执行完整初始化，不能传业务数据库URL。MySQL零跳过和SQLite分层跳过分别见mysql-final.log与final-regressions.log。

## 协作与剩余边界

本轮只提交任务8个测试/脚本文件和对应文档证据，保留共享工作区其他图像流程及运行记录的修改。四个关联Issue更新本次补验收，继续保持OPEN；Flash科学读数、远程Spec/代码尚未push及整篇业务门不被这次测试替代。

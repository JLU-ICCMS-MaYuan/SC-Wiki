# 研究者社区论坛

## 功能边界

该功能负责研究者身份、贡献排行和科研交流：邮箱注册、JWT 会话、公开研究身份页，以及问答、体系与论文评论、站内通知和举报管理。侧栏“社区”展开排行榜、Tc~X 演变、讨论三个入口。图表组合的编辑入口在管理页；图表本身的行为记录在 [Tc 历史与压力图表](../03_Superconductivity_Data_Search_and_Database_Discovery/tc-history-and-pressure-charts.md)。

## 小功能目录

| 小功能 | 职责 | 依赖 |
| --- | --- | --- |
| [注册、登录与 JWT](registration-login-and-jwt.md) | 账号创建、凭据校验、会话撤销和前端本地会话 | Go API、JWT、bcrypt |
| [研究者贡献排行](researcher-contribution-ranking.md) | 展示贡献参与人数、上传与审核 Top 20 及登录用户个人排名 | 论文、审核事件、用户、Redis |
| [社区问答与评论](community-discussion.md) | 问答与点赞、体系和论文交流、站内通知与举报管理 | Go API、MySQL、Redis、账号与论文权限 |

## 功能组成

```text
研究者社区论坛
├── 注册、登录与 JWT（社区身份）
├── 研究者贡献排行（社区贡献展示）
└── 社区问答与评论（科研交流）
```

## 关联关系

注册只创建普通用户，完成邮箱验证码验证后自动登录，不需要人工审批。上传与审核行为汇聚为贡献榜单：展示贡献参与人数、双 Top 20 与登录用户个人排名；榜单用户名可进入匿名公开研究身份页，封禁账号保留标识，注销账号匿名化。排行快照缓存一小时并支持手动即时刷新。管理员资格审批与账号治理属 02 目录。

交流内容不改变论文科学数据或贡献排名。体系讨论跨论文共享，论文评论跟随论文 ID 并继承论文可见性。社区迁移和运行边界见[数据库初始化与迁移](../02_Decentralized_Maintenance_and_Verification/database-initialization-and-migrations.md)。

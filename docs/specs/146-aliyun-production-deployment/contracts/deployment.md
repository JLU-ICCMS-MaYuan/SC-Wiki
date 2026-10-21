# 部署契约

- 目标：/opt/scwiki；项目 scwiki-app、scwiki-data、scwiki-compute；网络显式创建，三项目引用 external 网络。
- 命令：init、config、pull、up、stop、status、logs、check、migrate；作用组必须明确，组合 up 顺序 data → compute → app。
- init 是唯一创建新存储身份的入口；普通 up 检查既有目录/卷和 release。没有隐式 down -v 或 prune。
- migrate 是显式命令；普通启动只读检查 schema 和认证。多 Alembic heads 按制品核对，未知 schema 不 stamp。
- endpoint/账号由私有配置注入；本地原生 .env 不直接用于生产。
- /health 表示进程存活，/readyz 表示角色依赖可用；不在检查中创建集合、桶或业务表。
- 单机数据端口不映射到宿主机。跨机仅在独立私网覆写中映射并限制来源；本次不发布该覆写。

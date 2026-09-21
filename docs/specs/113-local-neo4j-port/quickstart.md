# 验证说明：本地 Neo4j 17687

关联 [Spec](spec.md)、[Tasks](tasks.md) 与 [Issue #113](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/113)。

## 前置条件

在项目根目录执行，已有可用的 Neo4j 安装和本机 `.env`；17687 未被其他程序占用。
使用已安装 Neo4j 驱动和 python-dotenv 的 `sc-wiki` Python 环境。
凭据仅从本机配置读取，不放入命令行参数或文档。

## 配置核对

| 位置 | 预期 |
| --- | --- |
| `scripts/lib-local.sh` | `NEO4J_BOLT_PORT=17687` |
| `.env` | `NEO4J_URI=bolt://127.0.0.1:17687` |
| `.local/neo4j/conf/neo4j.conf` | `server.bolt.listen_address=127.0.0.1:17687` |
| 同上 | `server.bolt.advertised_address=127.0.0.1:17687` |
| 同上 | `server.http.listen_address=127.0.0.1:7474` |

已有安装必须同步上述本机配置；修复提交 `7a614bb3` 中的安装脚本会跳过已安装的 Neo4j。
若客户端已运行，需按现有流程重启对应客户端，使其加载新地址。

## 单服务启动

```bash
bash "scripts/dev.sh" start neo4j
```

预期显示 Neo4j 已就绪，连接地址为 `bolt://127.0.0.1:17687`。
若已运行，可直接执行下面的只读验证；不为此重复启动全部服务或执行数据库迁移。

## 认证与公布地址验证

以下命令在已激活 `sc-wiki` 环境的终端执行：

```bash
python - <<'PY'
import json
import urllib.request
from dotenv import dotenv_values
from neo4j import GraphDatabase

cfg = dotenv_values(".env")
assert cfg["NEO4J_URI"] == "bolt://127.0.0.1:17687"
with GraphDatabase.driver(
    cfg["NEO4J_URI"],
    auth=(cfg["NEO4J_USER"], cfg["NEO4J_PASSWORD"]),
    connection_timeout=5,
) as driver:
    driver.verify_connectivity()
    with driver.session(default_access_mode="READ") as session:
        assert session.run("RETURN 1 AS ok").single()["ok"] == 1
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
with opener.open("http://127.0.0.1:7474/", timeout=5) as response:
    assert json.load(response)["bolt_direct"] == "bolt://127.0.0.1:17687"
print("认证、只读查询与公布地址检查通过")
PY
```

## 已执行结果：2026-09-21

| 验证 | 结果与证据边界 |
| --- | --- |
| 修改前实际绑定 17687 | 成功；7687 绑定返回 `Errno 98` |
| 单服务启动 | `scripts/dev.sh start neo4j` 成功，使用 17687 |
| 真实驱动认证及只读查询 | 通过，文档补录时再次核验通过 |
| HTTP 根入口 | 7474 可访问，`bolt_direct` 为新地址 |
| 配置生成 | 旧地址改写和缺失项默认值均为 17687 |
| #112 工作区同步 | 两个未提交模块使用 17687；仅验证配置约定 |
| Bash 语法和修改格式 | `bash -n` 与 `git diff --check` 通过 |

## 提交与运行边界

核心修复提交 `7a614bb3` 包含 6 个文件，新增 8 行、删除 7 行。
私有 `.env` 与 Neo4j 本机配置已同步但不入库；#112 未提交代码由原 Issue 跟踪。
文档补录期间 #112 正在改写安装入口及启动脚本，新增部署运行模块也使用相同端口；本记录不对这些未提交修改的运行行为作完成声明。

本次没有执行完整 `make start`、生产部署或另一台机器验收，也没有核验 AI 外部服务。
本地提交不包含推送授权；GitHub 上的 Spec 文件链接须在分支推送后才能浏览。

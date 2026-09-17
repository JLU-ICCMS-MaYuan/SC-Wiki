# RAG 读取收敛验证

关联 [Issue #107](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/107)，补齐 #90 的统一记录读取契约。

## 修复与证据

- 修复前 `tools/mysql.py` 查询临界温度、压力和电声耦合均在执行 SQL 前触发
  `SuperconductorProperty has no attribute pressure_gpa`。使用 Git 中原实现、当前模型和禁止数据库访问的会话替身复现。
- `search_property_records` 替代含义不明的 `query`；别名转换集中于数据库服务，AI 工具只解析条件和输出结果。
- AI 工具、材料接口、四种结构化检索、材料详情、统计与旧问答引擎共用当前批准版本连接及记录输出。
- 普通 `/chat` 与 `/chat/stream` 共用 Mentor，最终事件返回最终答案；探索仍由显式参数控制。
- 删除没有调用方的旧物性删除工具及失效的注释查询代码；不执行业务数据删除。

## 本地自动验证

```bash
JWT_SECRET_KEY=rag-local-test-only DEBUG=false python -m pytest \
  "tests/05_rag_question_answering" \
  "tests/test_rag_service.py" \
  "tests/test_rag_internal_imports.py" \
  "tests/test_rag_internal_api.py" \
  -q -o asyncio_default_fixture_loop_scope=function
```

运行环境需安装 `requirements.txt` 中测试依赖。上述 JWT 值仅用于测试导入，不是运行配置。
本次在 `sc-wiki` Python 环境执行；缺少的 `pytest-asyncio` 安装于临时测试目录，并通过进程级
`PYTHONPATH` 加载，没有修改全局环境。

结果：工作区与仅包含本次暂存内容的独立源码快照均为 49 项通过。共享文件中其他任务的既有修改逐行保留在工作区，没有混入提交。测试覆盖：

1. SQLite 中仅创建当前读取所需表，不创建 `key_properties`、`superconductor_properties` 或旧 Tc 表，执行真实 SQLAlchemy 查询。
2. Tc 数值及范围、压力、独立 λ、自定义文本和布尔值、零值、只有材料名的状态、记录内条件参数。
3. 同名材料跨论文独立；未批准论文、旧 revision 记录不可见；论文升版后原记录立即退出查询结果。
4. 四种检索、列表、详情、统计、同步/异步工具、知识图谱材料接口使用相同记录来源。
5. 真实 Mentor 图执行真实工具并读取隔离数据库后回答；仅替换外部模型响应，不替换物性查询。
6. 旧 `ask` 和 `ask_stream` 完整生成路径均不引用旧表，保留同名材料不同条件的记录和来源。
7. 错误条件与数据库异常不伪装成空结果；API 路由、导入、工具隔离与既有评测单元测试通过。

## 验证边界

- 未执行生产数据库变更、部署、Git 推送或真实外部模型请求。
- 没有以 SQLite 测试代替目标 MySQL 部署验收；没有以工具测试代替 Qdrant 发布更新或 Neo4j 关系工具真实验收。
- `RAG_DATABASE_URL` 仍可独立配置，部署时需要确保与业务数据库指向同一权威实例。
- 材料物性工具已切换权威数据源，历史包含该工具的评测结果不能直接作为本版本的对照结果；历史报告保留原样。

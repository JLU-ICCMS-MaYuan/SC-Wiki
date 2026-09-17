# 混合检索

## 功能说明

根据查询意图选择 SQL 精确检索、Qdrant 语义检索或二者融合，并返回排序后的论文与超导体结果。

## 当前行为

- 搜索引擎定义多种搜索模式，并可自动识别查询模式。
- SQL 路径处理结构化论文、材料和属性条件。
- AI 工具 `query_properties` 调用数据库服务 `search_property_records`；化学式/元素检索、材料详情、`material_info`、知识图谱材料接口与统计统一读取 `property_records`，不再读取已退役的旧物性表或 Neo4j 物性副本。
- 结构化读取仅返回当前已批准论文版本，记录、状态、材料的论文和版本必须一致。同名材料在不同论文、状态、方法下的记录分别保留；只有材料名、没有化学式的状态也可按名称查询。
- 输出保留数值、完整范围、文本、布尔值、规范单位、原始单位、压力及记录内 Conditions/参数。范围筛选按上界比较，不将中点当成论文报告的单值；压力从材料状态读取。
- 数值条件支持 `>`、`<`、`>=`、`<=`、`=`；留空时不加数值筛选，可读取文本/布尔记录。非法条件明确报错；数据库失败与没有匹配记录分别返回。独立 λ 记录与 Tc 内嵌 λ 参数不自动合并。
- 语义路径查询 Qdrant 向量集合，正式科学来源保留来源类型与归因限定；新来源的论文 revision 必须匹配当前已批准版本。
- 混合路径合并、去重和排序结果，服务层提供统一门面。

## 工作流程

问题进入模式检测；引擎执行 SQL、语义或混合查询；结果经过规范化、融合和 top-k 截断；API 返回数据或供问答引擎构造上下文。

## 约束

- SQL 检索依赖 RAG 异步数据库，语义检索依赖 Qdrant。
- 自动模式识别是规则和实现驱动的路由，不保证覆盖所有自然语言表达。
- 真实数据集条件测试可能因本地数据缺失而跳过。

## 代码与测试

- `backend/rag/search/sql_search.py`
- `backend/rag/search/property_records.py`
- `backend/rag/tools/mysql.py`
- `backend/rag/search/vector_search.py`
- `backend/rag/vectordb.py`
- `backend/rag/service.py`
- `backend/rag/database.py`
- `tests/05_rag_question_answering/`

## 相关变更记录

- [Issue #107：修复 RAG 物性查询迁移遗漏](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/107)，验证见 [#90 RAG 读取收敛](../../specs/90-unified-superconductor-properties/rag-read-validation.md)。

## 已知问题

- RAG 配置仍允许通过 `RAG_DATABASE_URL` 指向独立数据库。统一模型不代表两个实例自动同步；部署时须确认与主业务使用同一权威数据实例。
- Qdrant 索引发布与外部 Neo4j 关系工具独立于结构化读取；本地数据库/工具回归不代替外部索引更新和真实模型验收。

语义检索的正式科学来源支持 human_review：保存管理员身份、理由与版本，引用和上下文明确标注人工判断及论文未直接支持，不表述为论文报告或 AI 已验证；融合提示逐个保留来源片段及各自归因。

# 知识图谱数据同步

## 功能说明

引用图不依赖 Neo4j 同步。论文 PDF 上传后由独立 GROBID 服务解析参考文献，Python 保存可追溯的解析及程序/LLM2匹配结果；Go 在公开查询时从 MySQL 实时投影引用边。

## 当前流程

1. 上传 Worker 找到正文 PDF，调用 `processFulltextDocument`，从 TEI 的 `biblStruct` 中提取 DOI、题名、作者、年份和原始引文。
2. 解析状态与参考文献先放入 Redis 草稿，校对页默认显示前 5 条，其余由用户展开；GROBID 不可用时保留 `unavailable` 状态，不阻断人工校对。
3. 第4步汇总后、第5步等待核对前，程序先按DOI或规范题名与兼容书目身份匹配；疑难引文有库内候选时固定使用LLM2，每批最多16条，限定逐条候选ID或null。相似度仅用于候选召回，非法结构、漏答或额外键均失败。双向结果、理由、版本及失败回执持久保存，原文保留。
4. 解析详情的“参考文献匹配”链接打开新标签页：左侧仅列命中的引用者，中间当前论文，右侧全部已解析引文且命中填色。接口仅限任务所有者及现有管理员权限；刷新、读取和无变化保存不调用模型。
5. 提交时保存当前版本的原解析结果及服务器快照到 `paper_reference_extractions` 和 `paper_references`；仅复用身份、原文和服务器缓存核验有效的模型依据，普通客户端不能伪造或删除快照。
6. 论文审核通过后，重试出边并复用有效匹配依据，更新相关历史未匹配关系。源引文绑定当前源版本，目标绑定书目身份；无关科学内容升版不使目标身份失效。匹配结果页不提前公开尚未审核的引用边；任务归档后按正式论文归属读取已有快照。
7. 论文升版时，系统先读取旧版本主 PDF，重新调用 GROBID，再把新解析结果写入新版本；旧版本引用不会通过版本级联继续作为新版本事实。若主 PDF 不可用或 GROBID 失败，新版本只记录 `unavailable/failed` 状态，不保留旧引用。论文删除时先清理引用源记录和图谱标记。

历史已审核论文可通过 `backend/scripts/backfill_citation_references.py` 显式回填。命令必须指定
`--paper-id` 或 `--all-approved`，按论文独立调用 GROBID 并独立提交事务；重复执行只替换同一论文当前
revision 的提取结果，不创建新 revision 或重复引用。缺少主 PDF、GROBID 不可用或解析失败时记录可观察
状态并以非零退出码报告，不人工创建引用边。

## 事实边界

- MySQL 的 `paper_references` 是公开引用事实唯一来源。LLM2只核对已解析原引文与给定库内书目候选是否为同一篇；不能从主题、正文叙述或 `builds_on` 生成引用边。每项决定按原文、候选书目、模型和算法签名复用；相关输入变化才定向失效。
- GROBID 解析结果不是“100% 成功”保证；结构化结果、失败信息和未匹配原文都必须保留，便于人工复核或以后重试。
- Neo4j 的其他论文关系和 `graph.json` 仍可被旧功能使用；材料 `STUDIES` 路径已退役。它们都不会影响本引用图的边、节点或被引次数。

## 运行配置

- Compose 服务：`grobid` 使用 `lfoppiano/grobid:0.8.1`，健康检查 `/api/isalive`。
- Python 与 Worker 使用 `GROBID_URL=http://grobid:8070`，并等待 `grobid` 健康后启动。
- 本地宿主机开发由 `scripts/dev.sh` 管理同版本 GROBID，固定绑定 `127.0.0.1:8070`，等待
  `/api/isalive` 成功后再报告服务可用；本地 Python/Worker 使用 `GROBID_URL=http://127.0.0.1:8070`。
  WSL cgroup 环境启动容器时附带 `JAVA_TOOL_OPTIONS=-XX:-UseContainerSupport`，避免 Java 容器资源探测
  导致启动失败。
- 匹配快照、依据及缓存迁移：`alembic/versions/20261106_0225_citation_matching.py`；业务库尚未执行本轮升级，须在确定目标后显式升级至 `20261106_0225`。隔离验证见[#225](../../specs/225-citation-matching-and-static-graph/validation.md)。
- 原图谱迁移：`alembic/versions/20260902_0004_paper_citation_graph.py`。迁移前会检查 `papers.year`，发现空值时明确失败，必须先补全。

## 代码与测试

- 解析、匹配和重试：`backend/services/citation_graph.py`
- Worker：`backend/ingest/upload_jobs.py`
- 提交与审核触点：`backend/api/rag.py`、`goserver/handlers/admin.go`
- Schema 测试：`tests/02_maintenance_and_verification/test_issue81_citation_graph_schema.py`

## 相关变更记录

- [Issue #82](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/82)：修复引用图谱运行链路、受控迁移开发库并提供历史引用回填。

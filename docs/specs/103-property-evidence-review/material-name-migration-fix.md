# 材料名缺列导致科学数据保存失败

关联 [Issue #103](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/103) 与 [功能 Spec](spec.md)。本补充只处理 2026-09-16 的数据库版本不一致故障，不代表材料名完整功能验收。

## 故障与依据

管理员保存 #29 时，Go 论文基本信息保存成功，Python `PUT /api/rag/papers/29/scientific-draft` 返回 500。日志为 MySQL 1054：`Unknown column 'material_states.material_name' in 'field list'`。

提交 `df4e61de` 引入 ORM 字段及迁移 `20260916_0105`，运行数据库仍停留在 `20260915_0104`，另有并行版本 `20260914_0052`。ORM 在科学保存的同值比较阶段查询缺失列，尚未删除重建科学数据就失败。界面保留分阶段保存提示符合现有契约；重试本身不能补出数据库列。

`scripts/dev.sh` 的 `start_python` 在服务健康时直接返回；开发热重载只更新程序，不执行迁移。`create_all` 也不会给已有表添加新列。不能将服务健康或存在迁移文件当作数据库已升级的证明。

## 需求与成功标准

- FR-029：补齐材料名缺列迁移，使现有含化学式材料状态能够重新保存、修改压强和重新读取；不回填材料名，不修改已有科学值或核对历史。
- SC-018：当前 MySQL 的实际列与版本验证通过；迁移前后已有材料状态除新增空列外完全一致；通过真实科学保存入口执行隔离夹具的保存、修改、重读，并确认外层事务回滚后夹具不存在。

## 方案、数据与接口

故障分类为部署版本不一致。沿用已经提交的迁移，仅执行 `20260915_0104 → 20260916_0105`，增加 `material_states.material_name VARCHAR(255) NULL`。既有三条材料状态的旧列内容摘要在迁移前后比对；不写真实论文 #29。MySQL 结构变更不能依赖事务回滚，因此只执行经过检查的单列增量迁移，不运行无关迁移或降级。

科学写入继续复用 `rewrite_paper_scientific_draft` 的会话和事务；测试只替换连接工厂为外层回滚事务，不替换持久化、校验或同值比较逻辑。接口不新增参数、不调用模型、不批准论文。不在正常查询中增加“缺列就忽略”的兜底，以免掩盖部署不一致。

需求映射：FR-029 / SC-018 → T044（迁移与数据核验）、T045（真实保存回归）、T046（文档与 Issue 回写）。

## 操作与回归

在已确认的本地 `127.0.0.1:3307/scwiki` 环境执行；其他部署先核对实际连接和当前版本。不要打印连接凭据。

```bash
. "scripts/lib-local.sh"
load_env
"$PY_BIN/python" -m alembic current
"$PY_BIN/python" -m alembic upgrade 20260916_0105
DEBUG=false SCWIKI_CURRENT_MYSQL=1 "$PY_BIN/python" -m pytest "tests/01_decentralized_uploading/test_material_name_migration.py" "tests/01_decentralized_uploading/test_pressure_review_mysql.py" -q
```

显式 revision 用于避开并行迁移分支；不能盲用 `head`，也不能用 stamp 假装完成结构更新。修改中的表单内容由用户在修复后重新保存，本次不代替用户提交真实论文数据。

## 技术任务与验证记录

- [x] T044 核验真实数据库版本、应用指定迁移、比对旧材料状态内容。
- [x] T045 增加并执行 `tests/01_decentralized_uploading/test_material_name_migration.py`，验证增量兼容与真实保存回滚；复跑压强保存回归。
- [x] T046 同步 Issue #103、本补充 Spec 与迁移说明，按可安全分离的范围提交。

2026-09-16 验证：新增回归在迁移前为 1 通过、1 失败，失败原因与用户日志一致，均为 MySQL 1054 缺列；迁移后新增回归和原压强回归共 3 项通过。真实科学保存入口完成夹具创建、修改压强、重读材料名/稳定键/压强，测试结束确认夹具论文不存在。当前仍运行的 Go → Python `/api/rag/evidence/preflight` 对 #29 返回 HTTP 200、31 个核对项，没有发起模型或保存/批准请求。

全部三条既有材料状态的新列均为 null，旧列内容摘要在迁移前后保持 `e79b0f118896222cb35741e7b09fd59149ebf4d86ecf7da521213e27911c5495`。本次只执行已提交的单列迁移，运行代码仍包含前序未提交工作；不把工作区验证等同于整个 Feature 已在 Git 完整交付。测试命令显式设 `DEBUG=false`，避免终端已有 `DEBUG=release` 干扰布尔配置解析；不修改持久环境配置。

## 保留边界

只填材料名、化学式为空的完整能力尚未验收：现有保存仍要求有效化学式关联；材料名单独修改的同值比较、核对依赖、显示等完整链路不能以此次缺列修复作为通过依据。Issue #103 保持开放，保留前序未完成项。

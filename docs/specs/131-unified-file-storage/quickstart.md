# 使用与验收：统一业务文件存储

**Issue**：[ #131](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/131)。本机实例业务文件已经迁移至 Garage S3；以下矩阵的实际覆盖与尚缺场景见[验证记录](validation.md)。

## 前置条件

隔离开发/验收环境，已实现本 Feature 的同一提交，真实 MySQL、Redis、私有 S3 bucket；不得使用当前业务库。通过私有环境文件配置两个后端，密钥不进入测试日志。已有上传、审核、人工证据、返修、头像、结构附件样本及两名不同所有者。

## 自动验证入口

```bash
python -m pytest "tests/02_maintenance_and_verification/test_file_storage_contract.py" "tests/02_maintenance_and_verification/test_file_storage_migration.py" "tests/02_maintenance_and_verification/test_local_storage_compat.py" "tests/01_decentralized_uploading/test_file_storage_workflows.py"
python -m pytest "tests/02_maintenance_and_verification/test_file_reference_inventory.py" "tests/02_maintenance_and_verification/test_file_storage_reconcile.py"
```

在 `goserver/` 工作目录执行：

```bash
go test ./storage ./handlers
```

真实服务测试缺少配置时须标明跳过，不能把跳过统计为 SC 通过。测试生成文件存放临时目录，结束只删除本次测试命名空间。

## 行为矩阵

| 场景 | 操作与预期 | 来源 |
| --- | --- | --- |
| 文件类型 | 分别上传 PDF、CIF/POSCAR 附件、人工证据和头像；读取/替换/删除符合原权限 | US1、SC-001 |
| 解析产物 | 保存 Markdown、IR 文件和审核产物；确认内容摘要，API 可读取 | US1、SC-001 |
| 隔离 | API/Worker 使用不同临时目录，不挂载共同业务目录；读取不依赖源路径 | US1、SC-004 |
| 故障 | 错误凭据、断开 S3、上传中断；不得发布完成引用，响应脱敏 | FR-004、FR-010 |
| 引用清理 | 提交论文或建立返修后清理原任务；现有引用可读，重复删除幂等 | FR-006 |
| 历史迁移 | 按迁移契约执行 scan/copy/verify/switch；各阶段注入中断并重跑，文件和引用零遗漏 | US2、SC-002、SC-003 |
| 回退 | 目标尚未开放新写入时恢复旧值与旧配置；旧业务可读、源文件仍在 | US2、SC-003 |
| 本地开发 | local 模式运行现有 make deploy/start/frozen 流程的隔离夹具；无 S3 也可用 | US3、SC-005 |
| 安全清理 | 不传 `--apply` 运行 `python -m backend.scripts.reconcile_file_storage` 只列数量；维护窗口内对隔离库运行 `--apply`，仍引用的头像和人工证据可读 | FR-006 |

## 证据要求

记录提交、依赖版本、测试结果、数据清单数量与摘要、失败样例和未执行项。不要写实际用户文件正文、云凭据、模型密钥。完成后新增 `validation.md`；本轮不预先创建“已通过”的运行证据。

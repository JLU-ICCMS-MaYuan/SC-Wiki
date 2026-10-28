# 验证步骤

1. 使用 `python3 -m scripts.local_deploy.environment` 配合仓库路径定位应用 Python。
2. 跑本目录关联的新后台格式测试、#139 方法与条件规则回归；先记录修改前失败，再验证修复。
3. 用原任务已归档 raw.json 和 input.json 执行真实 normalize_extraction；原任务与原始响应只读。
4. 定向读取 CaH6 正文/SI 的方法来源，新调用所选模型，仅关注声子方法、软件、泛函及其必要记录上下文；结果经过生产链，写隔离副本重读，不重新解析所有 PDF 页面及所有字段。
5. 跑前端实际条件表单编辑与重开测试、生产构建，核对“声子方法”名称与阶段/来源保留。
6. 报告源码、输入哈希、模型名称、重跑/复用步骤及输出位置；不把字段通过称为整篇通过。

实际命令与结果完成后写入 [验证记录](validation.md)。

## 本次可复现命令

```bash
DATABASE_URL="sqlite:///:memory:" "/Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python" "scripts/verify-phonon-field-parsing.py" --task-id 29b2dd4604b64ee58c669c0efddb8cab --live --source "5d2884b8fc0b4331881cb78a347f489c:1,4" --source "c463643719b3420eb4e1936d95780c6b:2,3" --output ".data/issue172-live-new"
```

该验证入口是本 Issue 的 CaH6 专用案例，要求来源身份/页码正确；不是任意论文的通用字段评测器。输出目录必须尚不存在；重新调用会使用当前配置的模型。它不会排队或改写原任务。

固定失败重放使用 `--response` 指向原任务归档的 raw.json（旁边须有 input.json），不加 `--live`；最终实际路径见验证记录。

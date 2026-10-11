# 研究驱动力全文归纳增量验收记录

关联 [Issue #66](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/66)、[Spec](spec.md)。

## H3S 实测

- 来源：`2014 H3S-段德芳.pdf` 与同任务补充材料；任务 ID
  `947214683efc415abd9b1d64c457d86c`。更新前核对上传任务为 `ready`，两份来源文件
  的 SHA-256 与任务清单一致，草稿研究驱动力等于原 AI 快照，`user_values` 为空，旧字段
  核对无人工裁决。
- 模型：本机配置的 `deepseek-v4-pro`。对已解析的主文及补充材料共 40 个来源片段通读后，
  返回两条有原文依据的英文动因。服务端形成独立行：

  ```text
  1. To resolve the uncertain high-pressure crystal structure of (H2S)2H2 left by earlier experimental and theoretical work, where the most stable ordered phase could not be reliably identified by structural relaxation.
  2. To investigate the metallization and potential high-temperature superconductivity of the recently synthesized hydrogen-rich compound (H2S)2H2.
  ```

- 两条内容分别对应引言对既有结构判断局限的说明、作者对金属化和潜在高温超导的明确动机。
  字段核对状态为 `supported`，有 2 条定位到本文的引句。没有为凑成第三条而拆分或编造动因。
- 更新前先保存私有快照：
  `.data/issue66-backups/947214683efc415abd9b1d64c457d86c-20261011T093658Z-before.json`。
  持任务锁复核原值后，仅更新草稿中的 `paper.research_motivation` 与同名兼容值，以及
  `result.json` 的对应 AI 基线；字段核对按新内容版本定向重算。重读 Redis 与 MySQL 草稿，
  其他论文字段及材料状态保持一致；旧核对记录保留为历史版本。

## 回归结果

- `backend/tests/test_research_motivation.py`：5 项通过，覆盖全文输入、逐行编号、原文引句
  定位、无效输出重试与非论文来源排除。
- TypeScript 编译通过；新增上传校对页测试通过，确认多行值进入文本框、失败提示出现。
  论文详情相关既有测试 10 项通过。
- 扩展后端回归 77 项通过、2 项失败：旧化学式归一化测试把 `Fd-3m-Li2MgH16` 与
  `Li2MgH16` 预期合为一态；提交失败模拟的 `load_results` mock 不接受当前
  `include_stale` 参数。两项均未调用本增量代码，留给对应任务处理。
- 上传校对页与论文详情相关前端测试共 34 项通过。回归中发现并行开发的理论子类型文案
  `AI 建议` 与既有全局文案断言冲突，改为同义的“全文模型判断”后复验通过。

## 当前边界

本次验证包含真实 H3S 来源、模型输出、持久草稿和字段核对。未重新上传全部论文，也未把
原文引句定位等同于语义绝对正确；人工校对仍是发布前门槛。

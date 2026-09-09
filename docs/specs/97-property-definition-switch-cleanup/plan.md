# 实施计划

## 技术上下文

React 19 / TypeScript 5.6 的 `PropertyModuleEditor` 负责定义选择和记录载荷；`paperProcessing.normalizeUploadDraft` 负责浏览器草稿边界归一化；Python `upload_contracts.convert_legacy_state` 和 `upload_jobs._normalize_draft` 负责 Redis 草稿输入；`property_modules.normalize_module` 负责记录级权威校验；`api/rag.py` 负责上传提交前校验和 HTTP 错误转换。

## 设计决策

1. 在共享的记录身份归一化函数中处理标准键清理和自定义键补足，供添加、切换、复制和历史草稿加载复用。
2. 后端兼容层仅对已有 `property_modules` 的 v2 草稿做深拷贝清理；缺失自定义键以 `record_key` 派生确定性键，避免重复加载产生随机身份。
3. `normalize_module` 接受可选路径前缀；上传提交校验传入完整材料状态路径，其他持久化调用保持原有默认路径。
4. 前端把后端方括号路径规范化为自身使用的方括号形式，错误横幅使用 `issues[]` 全量消息；定位优先使用完整字段，记录级问题回退到记录容器。

## 组件职责

| 组件 | 职责 |
| --- | --- |
| `propertyModules.ts` | 定义记录身份归一化，保证标准键为空、自定义键稳定 |
| `PropertyModuleEditor.tsx` | 定义切换时调用归一化，保留已有自定义键 |
| `paperProcessing.ts` | 加载草稿时应用前端身份归一化 |
| `upload_contracts.py` | Redis v2 草稿输入兼容清理 |
| `property_modules.py` | 使用调用方路径执行权威记录校验 |
| `rag.py` | 传入完整路径并返回结构化问题 |
| `UploadTaskEditor.tsx` | 汇总问题、展开状态、标记和聚焦字段 |

## 验证策略

先新增会在旧实现失败的 Python 和 Vitest 回归测试，再实施代码。后端覆盖纯归一化、完整路径和真实 `_validate_draft` 错误契约；前端覆盖定义切换、历史载荷和提交错误展示。最后运行相关 Python 测试、Vitest、TypeScript 构建和差异检查。

## 风险与回滚

风险限于草稿载荷归一化和错误路径显示。所有变更均为可逆代码修改，无数据库迁移；若验证失败，保留未提交修改并修正对应实现，不回滚其他任务文件。

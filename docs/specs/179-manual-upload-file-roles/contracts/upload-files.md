# 上传文件接口与交互契约

**Spec**：[spec.md](../spec.md)。

## 新建任务

沿用 POST /api/upload-tasks，files 每项包含 client_id、role、filename、size、media_type。角色仍为 main/supplementary/attachment。恰好一个 main，main/supplementary 接收 .pdf/.txt/.md，attachment 接收 .cif/.poscar/.vasp/POSCAR/CONTCAR，不允许错区自动搬运。保留 50 MiB 限制、权限和既有错误封装；数量/格式错误在创建持久状态前拒绝。

file_role_policy 不是客户端可控请求字段；create_task 总是为新任务写入 user-specified-v1。上传 PUT、锁定、版本和幂等仍为原契约。

## 用户界面

三处命名明确的区域支持文件选择和拖拽，按钮可键盘操作；正文输入不允许多份且额外文件明确拒绝，不静默替换；补充材料和源数据允许多份。每区域显示允许格式、数量说明和自己的文件列表；全局显示大小/并发规则、错误及上传按钮。

本地选择/移除无网络请求。缺正文时开始操作给出恰好一个正文的错误，不创建任务。上传中禁用更改。新任务没有角色下拉或二次角色确认。

## 历史兼容与来源

无策略标记的既有任务保留旧读取和 resolve-roles 恢复，不批量写入。新任务 Worker 不调用角色评估，也不因角色信息弱暂停。解析错误报告原错误，不能改变角色规避。引文只用指定主文，文本提取用 main/supplementary；结构原件走现有结构处理。纠正文件独立定位，冲突仍按现有规则待审。

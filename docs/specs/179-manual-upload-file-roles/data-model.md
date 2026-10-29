# 数据与状态：用户指定上传文件身份

**Spec**：[spec.md](spec.md)。

## 上传任务

新增内部字段 file_role_policy，唯一新任务值 user-specified-v1，由 create_task 设置。原有任务无该字段即为有界历史流程，读取/恢复不自动补值。ScientificUploadDraft.state 保存完整 JSON，因此无需结构迁移。

新任务状态仍为 uploading → queued → extracting → reading → summarizing → ready。真实失败、取消、重复和提交沿原生命周期；没有 extracting → needs_role_review 的新任务边。历史任务原有 needs_role_review 和版本化人工恢复保持。

## 文件

保留 file_id/client_id、role、declared_role、original_filename、kind、sha256、sort_order 和上传/解析状态。新任务 role 与 declared_role 相同且不由文本重写；锁定后清单不可变。main 恰好一个，main/supplementary 仅 pdf/txt/md，attachment 仅 cif/poscar（含 vasp/POSCAR/CONTCAR 命名）。

结构候选和 Evidence 的来源外键、文件身份、页码及哈希不变，不新建数据权威副本。产品改名不改存储值。历史普通文本附件可读，不因新建清单校验被批量拒绝或重写。

## 所有权

上传前选择由浏览器拥有；清单创建后由服务端任务拥有；正式提交由既有事务认领文件。用户指定角色不能由 parser、关键词、元数据或模型推断覆盖。文件一致性记录只检查所属论文，不拥有改分类的权限。

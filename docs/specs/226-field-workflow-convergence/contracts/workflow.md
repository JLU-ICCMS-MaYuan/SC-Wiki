# 接口及行为契约

现有field-decision新增approve_without_evidence动作，持久为approve+mode=without_evidence；target/item/review_token和原权限/周期校验保持。返回当前record和新令牌，不调用模型。服务端检查字段格式与必填/派生规则，不接受客户端自报通过。

人工资料接口增加单个长text与多url项；image/pdf沿现有上传接口，各10项。完整人工资料后普通field-input/jobs/submit-check核对；无证决定有效时普通提交不发起该字段模型。显式“大模型核对”对当前值的资料要求与错误反馈保持。

snapshot_for允许传入调用方SQL会话，内部实现不在持锁保存中另开连接。写入拥有统一锁顺序，纯查看权限不申请写锁。数据库错误返回真实技术分类，不伪造科学不通过。

四宿主字段设置读取同一契约/当前值，原专用控件优先，否则共享类型编辑器。应用只更新当前字段及真实依赖，取消不修改；冻结只读。标准键/类型保持。

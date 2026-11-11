# 官方Flash受限JSON动作传输

## 原因及本轮选择

正常结束的官方Flash Chat原生函数回执多次出现非法JSON/混入XML；本机拒绝后，去掉冗余JSON模式仍未恢复。完整失败在本轮native-json-failure-generation6及native-mode-generation7-failure。不是SI太长，未提高上下文或科学动作预算。

按用户本轮“后续按推荐执行、不再弹框”的授权实施此协议选择，并不冒称用户逐字审定了新接口。与旧设计的差异是：这些图像请求不再依赖上游原生function_call参数，而由同一个带图Flash经官方Responses text.format.json_schema声明一个action，本机按原注册表真实执行只读工具。它不是纯文本模型路线，不换模型，不允许模型伪造工具结果；也不生成或声称存在provider原生调用ID。第三方GPT保持既有传输。

## 边界

- action的name只能为当前已注册工具，arguments逐项复用原闭合Schema；局部技术身份依原规则恢复，其他未知字段、错误类型、越权来源及科学错误仍拒绝。
- JSON Schema根只允许一个action，避免API原生并行工具带来的不确定性；原13次动作循环、请求并发和科学字段契约不改。
- 该分支强制reasoning.effort=none及原温度；真实探针reasoning token为0。API只提供动作内容，本机读取原PDF/像素、计算并产生回执，后续对话明确标为实际本机工具结果。
- 原始模型动作、绑定后的动作和传输版本分别留证；不伪造native回执，不通过接口或SQL替代网页业务。
- 实际发送的动作Schema计入原预算，函数的引用定义独立命名避免串字段，不提高96000门。
- 代码选择位于image_feedback，对官方Flash及其官方兼容别名启用；移除此请求选项即可关闭，不改.env或增加用户设置页。

## 实测

同一真实失败输入、同模型/原图/参数Schema：官方Responses返回completed、合法动作及本地Schema通过，76018输入/1112输出token、reasoning token0；仅协议探针，没有工具或业务执行。原SI正式工具链新读3次得到lambda约4.3（图读分辨率0.3）和2.4（0.2），经过原标定及IR保存重读；原图人工核对在该约数精度内。不把这一个图的局部通过当整篇/五阶段通过。记录在responses-action-probe及最新horizontal-lambda-live时间目录。

SDK序列化/本地拒绝/引用/预算/旧路径及原图相邻回归、三项契约另见本轮registered-actions-*.log。当前真实Task仍需从网页续跑后验收，不能宣布黑盒完成。


## 完整动作交付

真实第8代收到的流式文本在JSON内部缺少分隔符，完整坏响应和堆栈保留host-action-generation8-failure；不作内容修补。该分支现在使用完整Responses交付：请求stream=false，收到completed标记后才解析，期间如实显示等待，取消仍由原可中断请求控制。并非增加模型重试或调用层次，其他模型/原生Responses流保持原方式。原单图新模型3次返回合法JSON、按原图标定保留未解决结果（0条合格读数），不把协议完成冒充科学成功。完整/未完成标记、请求/取消/记忆相关回归见atomic-actions-after.log；真实任务继续验收。


## 固定外框由本机管理

第9代完整API响应的action值已经完全闭合、可按原工具Schema校验，缺少的仅是本协议最外层闭合符。真实失败先证明内部完整后，解析器允许在API明确completed且唯一action对象完整、无重复键/非有限值/额外成员时，由本机构造固定外框；不拼接动作参数、不补任何科学内容。内部数组、字段、字符串或动作对象缺失、XML混入参数或多值歧义仍拒绝，未完成API回执即便文本看似完整也拒绝。原始响应和归一化审计完整保留，原Schema/来源/类型及科学门保持。该边界仅用于本机JSON动作协议，不扩展原生或普通JSON的接受条件。实际原失败及正/反例在complete-action-missing-envelope.json和test_registered_actions.py，后续仍通过同Task网页验收。

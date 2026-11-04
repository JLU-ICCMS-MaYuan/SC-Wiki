# La-H真实人工黑盒测试记录

本轮尚未完成。环境：本机原生实时开发；分支mayuan。

论文：Potential high-Tc superconducting lanthanum and yttrium hydrides at high pressure；DOI：10.1073/pnas.1704505114。

运行目录：/Users/mayuan/Codes/SC-Wiki/tests/TestForRealScenario/runs/20261104T043104Z-lah-324f7fe6

## 已核验

用户Safari为myth620137018@163.com，超级管理员Chrome为mayuan_mark@163.com。旧任务fb798a2f754847a782b557bd676962ea失败、未提交、未生成正式论文；两份PDF由原任务文件引用从本机S3取回，角色、大小和SHA256一致，副本保存在本轮sources/。只读数据库当前无该DOI论文。

源文件正文SHA256：bf06c039e4a673454f1240a7febb8f14b5a9cb1762f89bbfd517bb09d0a117e8。补充材料SHA256：5b1b8e740c08cf69d973a712c6058e9fa2b9306098fcab39dc632bf998a33624。

## 修复与验证

#176：先实测保存草稿重建请求369189字符，逐条证据完全去重仍360489；用户确认集中重复片段后，实际紧凑字符串238103字符，未扩大250000上限或按状态分批。

#194：真实Worker堆栈在候选回填向空父级写值时TypeError；4反例先失败，修复后通过。输入去重2反例先失败。定向49项通过；字段契约、144项四宿主表单、8项变异检出通过。6项旧字段回归在独立HEAD c3681470逐项复现，不计通过。

## 五阶段

1. 新上传解析、校对与送审：待执行。
2. 超管真实拒绝退回：待执行。
3. 用户返修重提：待执行。
4. 超管填写通过日志并批准：待执行。
5. 探索La/H精确体系及LaH10、正式数据核验：待执行。

## 共享工作区

保留原有upload_jobs.py空行修改、full-reparse-20261102.md已有修改、docs/discussions及docs/investigations删除和.workbuddy/。本次仅修改科学整理输入投影、共享候选空父级写入及其回归和对应文档，不推送。

## 第一轮网页新上传的追加发现

修复提交b9e09a46后，已从用户网页清理旧失败任务并上传相同文件为4d639f2fc0384cba9550db7cb31f9fea，实际模型gpt-6.1-sol。正文和SI均完成文字提取；正文AI提取完成，SI首次AI响应因合法空条件与内部表单不一致被拦截，触发原有一次重试。完整原响应已留存，隔离正式后处理复现invalid_condition_type。

按#205原有协议补齐合法缺省为空固定容器，1故障回归先失败、2保护项通过；修复后71项定向通过。后续将在检查完成后取消、清理本轮未送审稿，并再次从网页新上传原PDF，不复用本轮AI答案。

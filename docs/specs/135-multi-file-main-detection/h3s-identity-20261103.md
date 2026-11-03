# H3S 文件身份误提示补齐

依据既有FR-006/007/008/009及[身份修复规格](identity-consistency-fix.md)，不新增身份审核流程或模型调用。

## 实际问题

H3S任务d287126aadb040b9982856feba798450首次送审时，正文的SUBJECT AREAS栏目被误认为题名，系统提示与SI题名不同。本轮已对照原PDF正常确认同篇，送审没有绕过确认版本。后续从两份原PDF首页重读，又复现无Markdown标题标记的正文题名只取后半行、SI题名只取前半行的问题。

## 修复与边界

沿用原栏目过滤与“题名后紧随署名”的判据：排除明确的Subject Areas冒号栏目；对首页前部/SI标题头适用既有两行题名连接，并先连接再接受单行候选，避免截断。无法可靠识别仍为unknown；真实题名或DOI差异仍产生具体警告及确认。规则标记document-identity-v3，不回写已批准论文或旧确认历史。

## 验证

新回归先分别检出栏目误识别和未加标题标记的换行截断；新旧身份定向15项通过。两个原PDF均重新核验哈希、直接读取首页后执行正式extract_identity/compare_identities，得到一致题名、status=ok；另用gpt-6.1-sol从原首页独立重新提取题名/DOI，未向模型提供预期答案，主文题名及10.1038/srep06968通过，隔离结果保存重读一致。产品规则路径新增模型调用为0。

证据位于tests/TestForRealScenario/runs/20261103T084543Z-fc5c53c7/identity-source-verification.json、identity-model-input.json及identity-model-output.json。本轮黑盒后续退回、返修、批准和H3S检索已实测完成，论文1204及旧历史均保留。

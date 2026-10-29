# 验证入口

使用 python3 -m scripts.local_deploy.environment 确认项目运行时；Python 回归使用项目 sc-wiki 环境，固定重放无需模型。测试科学表单：

```sh
npm run test:upload-ui --prefix frontend -- ../tests/01_decentralized_uploading/predicted-tc-groups.test.tsx
npm run test:form-contract --prefix frontend
npm run test:form-contract:mutation --prefix frontend
npm run build --prefix frontend
```

真实验证使用隔离目录和任务副本。复用已核对的正文／SI 文字，重新调用模型提取受影响字段，再经过正式整理、来源验证及保存重读。原用户任务不写入。原始四记录应收敛为一个方法行两个配对点；S19 只保留来源，不产生文本温度。真实调用报告与固定重放报告分别保存。

测试结果及实际命令追加 validation.md；本文件不预先宣称通过。

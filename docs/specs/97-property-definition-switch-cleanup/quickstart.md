# 快速验收

1. 打开上传草稿，添加一条自定义性质并填写名称和值。
2. 将定义切换为测量 Tc，确认记录提交载荷的 `custom_property_key` 为 `null`，再切回自定义性质，确认原键仍存在。
3. 使用包含标准记录残留自定义键的 v2 草稿加载编辑器，确认键被清理且值、条件、Evidence 未变化。
4. 提交一条带残留键的草稿，确认 400 响应的 `issues[0].field` 包含完整 `material_states[0].property_modules[0].records[0]` 路径，页面显示“规范性质不能携带自定义键”并展开对应记录。
5. 运行：

```bash
pytest -q backend/tests/test_property_modules.py backend/tests/test_issue90_properties.py backend/tests/test_submit_error_contract.py
cd frontend && npm run test:upload-ui -- --run ../tests/01_decentralized_uploading/property-record-editor.test.tsx ../tests/01_decentralized_uploading/submit-validation-feedback.test.tsx
npm run build
```

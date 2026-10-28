# 图片证据索引

```yaml
images:
  - id: IMG-001
    upload_order: 1
    original_name: codex-clipboard-79284859-9c5f-48ca-9021-f8be4baa9af0.png
    locator: docs/specs/174-form-processing-contract/assets/IMG-001-input-delay.png
    status: local_verified
    user_context: "为什么我在填写这个内容的时候，反应这么慢？是不是后台又多了什么检测？？？？？"
    related: ["Issue #174", US1, SC-004]
    sha256: 4e685b269f224746f2b7a885e115f09515cc1d04aa18bc0f9f75f413d66d6a65
    media_type: image/png
    dimensions_px: [2256, 1016]
    verification: "2026-10-28：原文件可解码，归档文件逐字节哈希一致，尺寸 2256×1016；只验证本地文件。"
```

AI 观察：用户圈出了图谱科学标题输入框。静态图片本身不能证明输入耗时；延迟证据来自另行执行的当前草稿隔离浏览器测量。无 OCR 或裁剪副本。此前标题缺失截图复用 #173 的 IMG-001，不重复存储。

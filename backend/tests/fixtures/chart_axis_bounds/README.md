# Peng2017真实反序边界回归来源

- 对应Issue：[#227](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/227)，FR-013、SC-007。
- 来源：Peng2017正文第4页图4，DOI `10.1103/PhysRevLett.119.107001`。
- 原PDF SHA256：`bf0725bea058339b814489fe213ec8285a0fca01eb5143da95254330eea06846`。
- `gpt-tc-response.json`和`gpt-tc-repeat1-response.json`逐字节复制自`tests/TestForRealScenario/runs/20261110-yh-fig4-comparison/`的两轮`server:LLM2/gpt-6.1-sol`真实响应，未排序、修补或换值；均返回`bounds=[795,0]`。
- `panel-tc.png`为该实验从原PDF内嵌图原像素裁出的Tc面板；原图879×632像素，裁剪框`[0,393,879,632]`。没有把插值放大当作更多图像信息。
- 固定重放验证18条可见柱、PrH9两条未读、ScH6系列/压力/约数与标定事实的保存重读。99/85 K只作为该固定图及两轮定位的回归结果，不是作者精确报告值。
- 本夹具不包含密钥、模型地址、业务草稿或数据库记录。固定响应测试不调用模型；真实原PDF新提取另见Spec的validation.md。

# 原始柱边追踪失败

来自本机Y-H黑盒任务d789acceee124022b3257f84780d1156的正文图4，实际模型server:LLM2/gpt-6.1-sol，PDF摘要及600 DPI裁剪/原图定位见source.json。failed-response.json和failed-crop.png为真实失败原响应/原像素，不修饰AI坐标或数字。运行请求目录227ed12b767b19d96f4f10f5291f4dc3f32f268cb61b7bc7d998455c4f3fdf1a-0。

YH10、mu*=0.13模型定位y=269；程序在蓝色128到133的像素波动处断开，错误停在约200 K网格线，算为~199 K。修复只按同色相追踪实际柱边，不使用正文287 K反推像素。原图/PDF不修改。source.json仅保留科学/定位元数据，不含凭据。

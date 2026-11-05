# 部署验证记录

日期：2026-11-05（Asia/Shanghai）。状态：服务器内部署与验收完成；外部入口尚未交付。

## 已核实的准备条件

Ubuntu 24.04.5、Python 3.12.3、4090 24564MiB、驱动 595.99.02、32 逻辑核心，/home 数据盘可用约 956GB。systemd 用户管理器运行；初始 linger=no。

## 权重与部署材料

- 当前部署源码为 `4d00dfbc4fe529695d1c9b1742078774b2a05e0e`，初版为 `9cd8548954ca3f057ea61633ea6c16132c37da35`；没有推送 Git。
- 当前启动器 SHA256：`a7a50895d3f634ae8ae6f4bea6f4812b78c5256dc937920d92c5dd39c88d8573`；验收脚本 SHA256：`e6f12a63778ebf7ceac5422e6517fe4c41afd6f526580eaba1b12c3d51cd5de0`，与当前部署源码及本地文件一致。
- 模型清单 SHA256：`fe39bea0babcfc0f8cf441a897aa2b3a2c069dcf2980a861622c8d2bd1385a27`。
- 固定 HF revision：`5cf2132abc99cad020ac570b19d031efec650f2b`。
- 2026-11-05 16:13 左右，权重下载、拼装及全量文件验证完成，日志为服务器 `download-fast.log`，结果 `ALL_FIXED_REVISION_FILES_VERIFIED`，共 14 个文件、8,059,521,975 字节。
- 两块权重 SHA256 分别为 `e70bfe3c970523fb7ef4eddffed2254ce3f1e7150c3de2af4342de129dd756f8`、`ed1b87c8e9eb7e535a1a155e4fd00d9f4dba80e58a6db48a4c9f82cede7079c1`。
- systemd 用户单元已安装、enable，linger=yes；密钥和环境文件均为 0600。主机开机启动仅验证配置，未重启主机。

## 真实推理与生命周期验收

| 验收 | 实际结果 | 原始证据 |
| --- | --- | --- |
| 依赖一致性与设备 | pip check 通过；vLLM 0.11.2、PyTorch 2.9.0+cu128、CUDA 运行时 12.8、4090 支持 BF16 | [运行记录](evidence/finalize.log)、[171 项依赖冻结](evidence/dependencies.freeze.txt) |
| 首轮完整接口回归 | 18 项检查通过，包括模型身份、中英文单条/批量、索引、有限数值、L2 范数、32/1536/2560 维、鉴权与错误输入 | [首轮结果](evidence/smoke-initial.json) |
| 重启后的完整回归 | 同样 18 项检查通过，真实重新加载模型后完成 | [重启后结果](evidence/smoke-after-restart.json) |
| 跨语言相关性冒烟 | 2560 维：相关英文片段 0.755168，无关片段 0.024268；1536 维亦通过 | [固定输入结果](evidence/smoke-initial.json) |
| OpenAI SDK | 实际调用返回 1536 维，固定短输入样本约 0.0367 秒 | [运行记录](evidence/finalize.log) |
| 异常自动恢复 | 主动 SIGKILL 本单元主进程后自动恢复，PID 59550→59738，NRestarts 0→1，42.289 秒后向量调用成功 | [恢复结果](evidence/recovery.json) |
| SSH 全部退出后常驻 | 断开所有交互 SSH，再连接时 PID 59738 与重启计数保持，1536 维请求成功 | [退出后验证](evidence/logout-verification.json) |
| 资源与私有配置 | 显存使用 15577MiB、空闲 8506MiB；服务 active/running，私有文件 0600 | [运行事实](evidence/runtime-facts.json) |

固定三条短文本批次在机器内约 0.067 秒。以上延迟不包含公网链路，也不等于长论文或高并发基准；相关性只覆盖固定冒烟样本，不宣称全库检索质量通过。

## 首次失败、修复与重跑

初版只设置 is_matryoshka=true，vLLM 0.11.2 对请求 2561 维返回 HTTP 200 与 2560 维，未按既有接口约束拒绝；请求 31 维也被接受。原始失败保留于 [失败日志](evidence/finalize-first-failure.log) 和 [固定边界响应](evidence/dimension-failure.json)。

这属于恢复本 Feature 已写明的维度边界，不改变模型或产品设计。使用引擎原生 matryoshka_dimensions 明确允许官方 32–2560 维范围，拒绝越界值；没有自行填充向量、修改权重、放宽断言或另外实现推理 API。修复源码为 4d00dfbc，随后重新加载并完成两轮完整回归。

## 网络检查与未启用草案

- 算力平台拒绝普通 SSH TCP 转发，报 `administratively prohibited: port forwarding is disabled`。
- GPU 到用户指定阿里云 22 端口 TCP 可达，读到 OpenSSH banner；真正的出站 SSH 命令触发平台工单复核，未获放行，本次等待已取消，测试命令未执行。
- 阿里云 Caddy 2.10.2 与受限账号配置草案均通过语法/有效配置校验；root 的 GatewayPorts 仍为 no，网站健康为 HTTP 200。没有加载草案或重启网站。
- 用户继续询问直连与中转区别，尚未授权阿里云入口变更；两条访问方案仍在讨论中。

## 清理与验证边界

已清理本次模型下载分片、拼装临时文件、独立安装缓存、重复 wheel 和引导脚本；保留运行环境、正式权重、私有配置和验收证据。缓存清理后又完成退出 SSH 后的真实向量调用。

本次没有修改科学表单、PDF 解析字段、网站模型配置或业务索引；不将这些测试写成整站或生产业务验收。跨机 HTTP、真实本地 SC-Wiki 接入、阿里云模型配置切换及旧向量索引重建均未完成。

## 待完成的外部入口

直接访问需要平台提供固定 HTTPS 映射或 VPN。阿里云中转只是备选，需要平台允许出站通道及用户另行授权入口配置变更；当前没有可供本地应用直接填写的外部 Base URL。

## 文档远程链接

Issue #222 已创建，类型 type:feature。2026-11-05 以 JLU-ICCMS-MaYuan 身份检查 mayuan 分支 Spec URL，实际为 HTTP 404，见[原始访问记录](evidence/remote-spec-link.json)。Spec 已保存在本地，双向远程可达尚未完成；本次没有 Git 推送授权。

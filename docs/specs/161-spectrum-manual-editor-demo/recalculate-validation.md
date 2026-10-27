# 正式主动重算与详情精简验收

日期：2026-10-27。用户确认本轮Issue与Spec增补稿后实施，FR-050至054/SC-028至030。

## 验证结果

- 正式前端7个测试文件54项通过，覆盖重算按钮/忙碌状态、λ与ωlog独立展示、DOS积分与比较分离、历史禁止、零频摘要去重、详情04移除及编辑/导航回归。
- 后端108项通过、2项行锁竞争仅SQLite跳过。使用α²F=0.01ν、0至6 THz核对λ=0.12、ωlog=(6/e)×47.99243073366221 K；相对谱乘37倍后ωlog不变且λ不发布。测试拒绝断片/分叉/闭环/重复/回折/缺端/缺依据/非零零频幅值，检查不改点。
- 当前MySQL56项通过，包含人工保存与重算的行锁竞争：两个同版本请求只有一个成功、另一个409。原有16集合/50运行数量和逐行哈希不变，无临时记录遗留；[报告](assets/recalculate-current-mysql-validation.json)。身份/临时草稿由测试依赖提供，SQLAlchemy和事务运行在用户授权的当前库；无DDL。
- [浏览器8场景](assets/recalculate-browser-validation.json)：正式React页面及真实HTTP/SQLite持久化，所有API流量重定向本次8191测试服务；验证两个按钮、忙碌重复点击、人工保存失效/重新积分、刷新、相对谱独立ωlog、缺口阻塞、并发409、390px布局。未向真实业务API写谱。
- TypeScript/Vite正式构建通过；保留既有3Dmol eval和大包提示，非本轮引入。
- 人工查看[α²F详情](assets/recalculate-alpha-result.png)与[窄屏DOS](assets/recalculate-mobile-detail.png)：按钮位于03标题区域，完成提示只一处，04及蓝色解释区均已移除。编辑器逐点表仍可用。
- [Demo保护](assets/recalculate-demo-protection.json)前后文件内容哈希一致；用户联动配置及Demo产物未修改、未提交。
- [用户原图](assets/recalculate-user-request.png)按原字节归档；Spec记录来源与哈希。

## 数值与权限边界

重算遍历稳定ID连线图，复杂度O(n)，无需图片重新识别。只有连续单值路径进入分段线性积分；不补点、不跨缺口、不将累计λ刻度冒充α²F。仅在计算副本消除线性标定的机器浮点舍入误差，不回写源像素，也不把真实非零幅值改零。

相对谱ωlog依据来自用户保留的零基线和统一倍率说明，且要求已确认普通频率物理定义；文本存在和数值积分通过不代表论文证据经科学审查。DOS各分波可用不同采样网格，但覆盖范围必须一致；积分与3N比较独立，不通过强制归一化自证。

计算记录写不可变新运行，保留旧运行；清除旧采纳，不自动科学采纳。只读/历史/失效记录不能触发重算；受限公开频段不暴露整谱积分。科学条件不足返回可回读的具体原因，网络或版本失败不覆盖曲线。

## 对应实现

- FR-050/053 → backend/api/spectra.py、backend/spectra/recalculate.py、SpectrumDetailPage.tsx；HTTP/MySQL/浏览器版本证据。
- FR-051/052 → connected_samples、alpha_integrals、dos_integrals；test_spectra_recalculate.py数值与负例。
- FR-054 → SpectrumDetailView.tsx、ZeroFrequencyCheck.tsx；前端断言与桌面/窄屏截图。

本次没有推送、部署或数据库结构变更。远程Spec链接仍待获得推送授权后验证，Issue保持开放。

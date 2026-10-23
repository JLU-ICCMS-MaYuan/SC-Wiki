# 11人名单修订验证

日期：2026-10-23。用户最终确认：只移除江崎，保留11人。

## 人数与获奖事实

- 原展陈1+3+3+2+3=12人；移除江崎后1+3+2+2+3=11人。
- 用户提供的参考名单2003年列出Abrikosov、Ginzburg、Leggett三人，却标为2人，导致累计10人与姓名列表不一致。
- 2003年官方新闻稿明确为三人获奖，并区分超导与超流贡献；Leggett因超流氦-3理论获奖，按用户最终选择继续展出。来源：https://www.nobelprize.org/prizes/physics/2003/press-release/ 。
- 当前展陈`data.ts`及英文传记去掉江崎，移除其网站原照资产；Spec历史照片和原始需求保留。正式`/nobel/esaki`不再显示详情。
- `awards.ts`保留完整同届历史记录；1973年仍为江崎1/4、Giaever 1/4、Josephson 1/2。共享说明提及江崎不意味着存在其展位。

## 验证结果

- 23项Vitest通过：11人范围、被排除的详情、保留Josephson/Leggett、完整奖项份额及共享文案、英文巡检和布局不变量。
- TypeScript与正式Vite构建通过；既有大包与3Dmol eval提示未改变。
- [正式页面浏览器验证](assets/roster-validation/production/browser.json)：11人详情、原照、共同获奖及份额、语言切换、手机、已删除人物路由提示通过。
- [展陈交互验证](assets/roster-validation/demo/browser.json)：三种视口363旋转相位无重叠，拖动、暂停恢复、触屏、取消、键盘和详情链接通过。
- [紧凑布局验证](assets/roster-validation/compact/browser.json)：中英文三种宽度726相位通过，索引间隔约12–13.5px；引言为十一位，联系人保持不变。

仅本地源码修改和验证，未推送或部署云端。最终漫画、原照外部许可和全面科研史审校仍在后续阶段。

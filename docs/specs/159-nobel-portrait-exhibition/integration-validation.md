# 诺奖展陈正式接入与授奖关系验证

日期：2026-10-23。范围：当前源码 `/news` 和 `/nobel/:personId`，未部署云端。

## 授奖事实

已实际读取12人诺贝尔奖官方事实页并提取授奖理由与份额，见 [award-facts.json](assets/award-facts.json)。共同获奖者按同年名单生成，并与个人贡献分开呈现。

1973年：江崎玲于奈的贡献为半导体隧穿，Giaever为超导体中的电子隧穿，二人各获全奖1/4；Josephson因超电流穿过隧道势垒的理论预言获1/2。单独获奖者Onnes不列共享者；1972、2003年各三人各1/3，1987年两人各1/2。页面未将共享奖项写成合作完成同一项研究。

## 运行验证

- 正式前端 TypeScript/Vite 构建通过；照片通过Vite URL import打包到`/assets`。当前Python后端仅挂载`/assets`/`/static`，因此没有沿用仅在Vite有效的`/img`路径。
- 本地真实页面检查见 [browser.json](assets/production-validation/browser.json)：从`/news`点击到新标签页、空opener、详情刷新、12人英文详情及引用、官方份额比对、中英文切换、未知人物、手机12人文字不裁切、全局样式隔离通过。新闻接口采样响应均为200；不据此宣称所有资讯功能全面验收。
- 编译产物预览服务器验证见 [build-smoke.json](assets/production-validation/build-smoke.json)：正式首页、12个详情、刷新和12张`/assets`图片解码通过。
- 共用展陈回归见 [demo/browser.json](assets/production-validation/demo/browser.json)：三种视口363个旋转位置无重叠；鼠标/触屏拖动、反向、取消、防误点击、键盘和减少动态仍通过。
- 首轮25项Vitest通过。随后图片改用构建导入后的复查，24项通过、1项资讯抽屉原有断言失配：并行任务未提交的`NewsFeed.tsx`将来源链接改为`Phys.org`，原有`news-page-layout.test.tsx`仍查找`source`。本任务未修改这两个文件，未将其改动混入提交。诺奖9项专项测试、13项英文巡检及另2项资讯测试通过。
- Node 26直接运行旧测试时，Node自身localStorage未配置导致失败；使用`NODE_OPTIONS=--no-experimental-webstorage`后由jsdom提供存储，验证恢复。此参数仅用于本次测试命令，未改系统设置。

## 边界

- 用户已认可第三轮视觉并要求接入，当前正式页面仍使用用户指定的历史原照；最终漫画后置。
- 图片最初外部作者与许可、全部科研生平与国家身份的全面审校仍未完成；授奖事实定向核验不等于全部内容通过。
- 当前工作区有并行任务；构建读取当前工作树。本任务提交只包含诺奖范围，不能将构建成功等同于并行改动已提交。
- Issue #159保持开放，远程Spec链接等待用户明确授权推送后核验。

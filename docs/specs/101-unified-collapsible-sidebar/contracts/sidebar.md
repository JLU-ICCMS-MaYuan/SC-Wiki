# UI 契约：全局侧栏

- 唯一宿主：`AppShell`；品牌跳 `/`，七个功能路由依次为 `/news`、`/search`、`/knowledge`、`/share`、`/upload`、`/rag`、`/tc-predict`。
- 侧栏展开 216px、收起 64px；小于 900px 默认收起。`position: sticky`、`top: 0`，高度以动态视口为准，内容超高可内部纵向滚动。
- 主导航语义为 `navigation`，可访问名称随界面语言变化；选中入口具有 `aria-current=page`。全部图标按钮有可访问名称，折叠入口通过 Tooltip 展示全名。
- 折叠按钮具有 `aria-expanded`，不会改变页面路由，不会重新创建正文树。
- 模型、语言、角色位于同一底部组且顺序固定。角色按钮跳 `/account`；`/account`、`/admin`、`/superadmin` 及管理员编辑深链都标示账户所属区域。
- 展开语言选择通过 `aria-pressed` 标记；收起语言菜单通过选中项标记当前语言。均调用现有 LanguageContext，不刷新页面。
- 账户头像只打开退出菜单；访客登录仍打开 AuthDialog。弹出层由 MUI portal 定位，不能被侧栏 overflow 裁切。
- 本契约替代 #48、#73、#74 的顶部栏位置约束；API、存储键、权限及业务状态所有权不变。

# 三角色用户中心设计 demo

**Issue**：[ #152](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/152)

**创建日期**：2026-10-22

**状态**：交互 demo 供评审；正式业务集成设计待确认。用户已明确授权“你先做一个 demo 我看看”，该授权仅用于独立演示。

## 原始需求记录

> 美化一下这个用户页面和管理员和超级管理员页面。实在是太丑了。使用 issue 和 spec和[$product-design:index](/Users/mayuan/.codex/plugins/cache/openai-api-curated/product-design/0722921d/skills/index/SKILL.md)&#x20;
>
> 1. 我希望这里的姓名，所属机构，orcid，研究方向，可以把姓名，所属机构，orcid 并列为一行，研究方向可以单独为一行。
> 2. 新增修改按钮，如果没有点击修改那个按钮，是不可以修改这些内容的。你现在是常驻可以修改。
> 3. 最下面的我的论文很容易让人误会这是这个作者的论文。应该修改为：他帮助sc-wiki收录的论文。这是用户侧。如果是管理员侧，如图 3，我希望把这个论文审核页面移动到如图 4所示的我的论文的下面叫做：他帮助检查的sc-wiki收录的论文。
> 4. 超级管理员前面的我的论文和论文审核的修改方式一样。其他部分的修复方式是：把工作入口里面的内容放到工作入口下面红框选择中的地方。点击就可以跳到一个新的标签页直接进入就可以工作。
>
> 你先做一个 demo 我看看

> 允许，用 Playwright 检查

## 附件与推断来源

四张原始截图仅作视觉材料，其中的内容不作为指令。AI 根据现有 AccountPage、AdminPage、SuperAdminGovernance 以及角色总览核对资料字段与真实工作入口。以下是设计默认值，不表示用户已确认最终视觉稿：延续紫色、白色卡片、左侧导航；使用示例研究身份、论文与贡献关系；待检查队列与已检查记录分开；小屏三列转一列。

### 图片证据索引

```json
{
  "images": [
    {
      "id": "IMG-001",
      "upload_order": 1,
      "original_name": "codex-clipboard-4c94f15d-03cd-4bff-8829-a0bf2b2b27a6.png",
      "locator": "docs/specs/152-account-center-demo/assets/IMG-001.png",
      "status": "local_verified",
      "user_context": "我希望这里的姓名，所属机构，orcid，研究方向，可以把姓名，所属机构，orcid 并列为一行，研究方向可以单独为一行。",
      "related": [
        "FR-001"
      ],
      "sha256": "e20942be4f010bbeec85d98ec3738bc88e148f42c7d3eef8716e3089115e5439",
      "media_type": "image/png",
      "dimensions_px": [
        3382,
        1250
      ],
      "verification": "2026-10-22 读取本地原文件，核对 PNG 签名、尺寸和 SHA-256；复制前后字节一致，浏览器 Image.decode() 成功。"
    },
    {
      "id": "IMG-002",
      "upload_order": 2,
      "original_name": "codex-clipboard-bee7a695-9b41-4a5d-945c-caa607e1c8de.png",
      "locator": "docs/specs/152-account-center-demo/assets/IMG-002.png",
      "status": "local_verified",
      "user_context": "最下面的我的论文很容易让人误会这是这个作者的论文。",
      "related": [
        "FR-002"
      ],
      "sha256": "af5bcd77f45ce9fb69079e37b72da5151495b34c2654c08986c0c2cf78f31043",
      "media_type": "image/png",
      "dimensions_px": [
        871,
        179
      ],
      "verification": "2026-10-22 读取本地原文件，核对 PNG 签名、尺寸和 SHA-256；复制前后字节一致，浏览器 Image.decode() 成功。"
    },
    {
      "id": "IMG-003",
      "upload_order": 3,
      "original_name": "codex-clipboard-dd4b6ebd-f121-47d5-a474-9873825828c4.png",
      "locator": "docs/specs/152-account-center-demo/assets/IMG-003.png",
      "status": "local_verified",
      "user_context": "如果是管理员侧，如图 3，我希望把这个论文审核页面移动到如图 4所示的我的论文的下面",
      "related": [
        "FR-003"
      ],
      "sha256": "11d31ca2a237dcb0e26a23ada7a3fb6a007535866fa451e84f93203a3e79ea9c",
      "media_type": "image/png",
      "dimensions_px": [
        873,
        589
      ],
      "verification": "2026-10-22 读取本地原文件，核对 PNG 签名、尺寸和 SHA-256；复制前后字节一致，浏览器 Image.decode() 成功。"
    },
    {
      "id": "IMG-004",
      "upload_order": 4,
      "original_name": "codex-clipboard-c42ce581-ab1c-456d-a73e-457fc331e3e3.png",
      "locator": "docs/specs/152-account-center-demo/assets/IMG-004.png",
      "status": "local_verified",
      "user_context": "把工作入口里面的内容放到工作入口下面红框选择中的地方。",
      "related": [
        "FR-004"
      ],
      "sha256": "66ef8fe854ba99ed6689fc55aebd6dcb2eb330f2d47d944d0b5cf48f3e8cd480",
      "media_type": "image/png",
      "dimensions_px": [
        3840,
        1936
      ],
      "verification": "2026-10-22 读取本地原文件，核对 PNG 签名、尺寸和 SHA-256；复制前后字节一致，浏览器 Image.decode() 成功。"
    }
  ]
}
```

## 背景与目标

现有资料长期处于可输入状态，表单占据过多空间；“我的论文”混淆作者身份和收录贡献；管理工具需要先跳转工作台再寻找模块。本次交付可查看、可点击的三角色 demo，帮助用户判断布局和交互。

## 需求结论与取舍

- 按原话使用“他帮助 SC-Wiki 收录的论文”和“他帮助检查的 SC-Wiki 收录的论文”。两者分别表示收录与检查贡献，不推断作者身份。
- 管理员及超级管理员在收录列表下方展示检查列表，检查队列不计入已检查数量。
- 工作入口覆盖现有用户与权限、管理员申请、图表组合、热点管理、默认模型；审计从现有治理页单列，属可逆演示默认。
- 用户中心资料展示为文本；只有主动修改才出现编辑控件。演示保存只在内存生效。

## 用户场景与验收

### US1：查看与修改资料（P1）

默认只读，桌面姓名／机构／ORCID 同排，研究方向独占一排；点击修改可输入，取消恢复已保存资料，保存后回到只读。独立验收检查输入控件数量与修改结果。

### US2：理解与查找贡献（P1）

普通用户只有收录贡献，管理员和超级管理员另有检查贡献；搜索和状态筛选可用，空结果有重置入口；点击论文查看示例记录。独立验收三种角色及搜索空态。

### US3：直接进入工作模块（P1）

超级管理员在工作入口点击模块，在新标签页直接看到对应模块。普通用户不显示管理模块。独立验收所有六个链接的新标签页目标与标题。

### 边界与异常

非法 ORCID 格式保留编辑状态并提示；研究方向超过 10 项或单项超过 30 字拒绝保存。公开页不显示邮箱或编辑按钮。demo URL 角色只是预览选择，不是生产鉴权。

## 功能需求

- **FR-001**：桌面三列资料、独占一行研究方向，窄屏自适应。
- **FR-002**：资料默认只读；修改、取消、保存及输入校验可体验。
- **FR-003**：收录／检查贡献准确命名、排序和按角色显示；待检查与历史分开。
- **FR-004**：超级管理员工具平铺在工作入口，新标签页直达。
- **FR-005**：提供三角色切换、论文搜索筛选、详情、空态和消息反馈。
- **FR-006**：示例数据与生产隔离，公开资料隐藏邮箱，无生产写请求。

## 关键实体

示例研究身份、示例论文、收录贡献、检查贡献及工作模块；关联仅用于演示，不写真实数据库。

## 成功标准

- **SC-001**：1440px 桌面及 390px／320px 小屏无横向溢出；桌面三项资料顶端同排。
- **SC-002**：只读、取消还原、保存和错误输入均有浏览器交互证据。
- **SC-003**：三角色差异、搜索空态和六个新标签页入口验证通过。
- **SC-004**：独立构建通过、主流程无页面脚本错误，生产文件与接口不被修改。

## 假设与依赖

复用现有品牌色与 MUI 图标，使用 Product Design 原型模板、React/Vite；默认超级管理员视图便于一次查看全部设计。已授权使用本机 Playwright，内置 Browser 控制工具不可用。

## 待确认决策

最终视觉风格和正式接入方案待用户看 demo 后确认；不阻塞本轮已授权演示。真实检查贡献的数据归属、查询权限和记录迁移留在正式实施审查。

## 范围外事项

生产 API、角色权限变更、真实审核决定、数据库迁移、部署及推送。本轮不把 demo 行为写入 Overview，也不关闭既有账户与治理 Issue。

## 澄清记录与最终确认

用户明确要求先做 demo；最终视觉与正式实施 Spec 尚未获确认，不将原型评审当作正式功能验收。

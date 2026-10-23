import React, { useEffect, useRef, useState } from "react";
import {
  LocalFireDepartmentOutlined as Hot,
  ExploreOutlined as Explore,
  AccountTreeOutlined as Graph,
  PeopleOutline as People,
  CloudUploadOutlined as Upload,
  ChatBubbleOutline as Chat,
  AutoAwesomeOutlined as Spark,
  ShieldOutlined as Shield,
  ArrowOutward as External,
  EditOutlined as Edit,
  Check,
  Close,
  Search,
  DescriptionOutlined as Paper,
  FactCheckOutlined as Review,
  LockOutlined as Lock,
  ChevronRight as Right,
  ExpandMore as Down,
  SettingsOutlined as Settings,
  Tune,
  BarChartOutlined as Chart,
  NewspaperOutlined as News,
  PersonAddAltOutlined as PersonAdd,
  HistoryOutlined as History,
  InfoOutlined as Info,
  ArrowBack as Back,
  Menu,
} from "@mui/icons-material";

const roles = { user: "普通用户", admin: "管理员", superadmin: "超级管理员" };
const initialProfile = {
  name: "马原",
  affiliation: "吉林大学 · 物理学院",
  orcid: "",
  interests: "高压超导, 第一性原理计算, 电子-声子耦合",
};
const papers = [
  {
    id: 1,
    title:
      "Superconductivity at 250 K in lanthanum hydride under high pressures",
    journal: "Nature",
    year: "2019",
    material: "LaH₁₀",
    status: "已收录",
    date: "2026.10.20",
    doi: "10.1038/s41586-019-1201-8",
  },
  {
    id: 2,
    title:
      "Conventional superconductivity at 203 kelvin at high pressures in the sulfur hydride system",
    journal: "Nature",
    year: "2015",
    material: "H₃S",
    status: "检查中",
    date: "2026.10.18",
    doi: "10.1038/nature14964",
  },
  {
    id: 3,
    title: "Superconductivity at 39 K in magnesium diboride",
    journal: "Nature",
    year: "2001",
    material: "MgB₂",
    status: "已收录",
    date: "2026.10.15",
    doi: "10.1038/35065039",
  },
];
const workItems = [
  {
    id: "users",
    icon: People,
    title: "用户与权限",
    text: "管理账号状态与角色权限",
    tag: "账号治理",
  },
  {
    id: "applications",
    icon: PersonAdd,
    title: "管理员申请",
    text: "处理研究者提交的资格申请",
    tag: "2 项待处理",
  },
  {
    id: "charts",
    icon: Chart,
    title: "图表组合",
    text: "维护可公开探索的数据图表",
    tag: "内容管理",
  },
  {
    id: "news",
    icon: News,
    title: "热点管理",
    text: "编辑与发布超导研究快讯",
    tag: "内容管理",
  },
  {
    id: "models",
    icon: Tune,
    title: "默认模型配置",
    text: "管理站点默认 AI 模型",
    tag: "站点设置",
  },
  {
    id: "audit",
    icon: History,
    title: "操作审计",
    text: "查看账号变更与处理记录",
    tag: "治理记录",
  },
];
const href = (role, view) => `?role=${role}&view=${view}`;
function Badge({ children, tone = "" }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
function SectionHead({ icon: Icon, title, description, children }) {
  return (
    <div className="section-heading">
      <div className="section-label">
        <span className="section-icon">
          <Icon />
        </span>
        <div>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
      </div>
      {children}
    </div>
  );
}
function Sidebar({ role, collapsed, toggle }) {
  return (
    <aside className={`sidebar ${collapsed ? "collapsed" : ""}`}>
      <a className="brand" href={href(role, "account")}>
        <span className="brand-mark">SC</span>
        <strong>SC-Wiki</strong>
        <span className="brand-caption">超导文献数据库</span>
      </a>
      <div className="nav-title">探索与发现</div>
      <nav aria-label="主要导航">
        {[
          [Hot, "热点", "/news"],
          [Explore, "探索", "/explore"],
          [Graph, "脉络", "/graph"],
          [People, "社区", "/community"],
          [Upload, "上传", "/upload"],
          [Chat, "对话", "/rag"],
          [Spark, "预测", "/predict"],
        ].map(([Icon, label, path]) => (
          <a
            key={label}
            href={`http://127.0.0.1:5173${path}`}
            target="_blank"
            rel="noopener noreferrer"
            title={`${label}（现有站点）`}
          >
            <Icon />
            <span>{label}</span>
          </a>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <div className="nav-title">个人空间</div>
        <a className="nav-active" href={href(role, "account")}>
          <Shield />
          <span>用户中心</span>
        </a>
        <div className="side-note">
          <Lock />
          <span>共同建设，可信科研</span>
        </div>
        <button
          className="collapse-button"
          onClick={toggle}
          aria-label={collapsed ? "展开侧栏" : "收起侧栏"}
        >
          <Menu />
          <span>收起导航</span>
        </button>
        <div className="sidebar-person">
          <span className="tiny-avatar">M</span>
          <div>
            <b>mayuan</b>
            <small>{roles[role]}</small>
          </div>
          <span className="online-dot" />
        </div>
      </div>
    </aside>
  );
}
function Profile({ role, isPublic, onNotice }) {
  const [profile, setProfile] = useState(initialProfile),
    [draft, setDraft] = useState(initialProfile),
    [editing, setEditing] = useState(false),
    [error, setError] = useState("");
  const nameRef = useRef(null);
  useEffect(() => {
    if (editing) nameRef.current?.focus();
  }, [editing]);
  const save = (event) => {
    event.preventDefault();
    const interests = draft.interests
      .split(/[,，]/)
      .map((v) => v.trim())
      .filter(Boolean);
    if (draft.orcid && !/^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$/.test(draft.orcid))
      return setError("ORCID 请使用 0000-0000-0000-0000 格式。");
    if (interests.length > 10 || interests.some((v) => v.length > 30))
      return setError("研究方向最多 10 项，每项最多 30 字。");
    setProfile({ ...draft, interests: interests.join(", ") });
    setEditing(false);
    setError("");
    onNotice("资料已保存到本次演示，刷新后恢复示例。");
  };
  return (
    <section className="card profile-card" aria-label="个人资料">
      <div className="profile-top">
        <div className="identity">
          <span className="avatar">M</span>
          <div>
            <div className="identity-name">
              <h2>{profile.name || "mayuan"}</h2>
              <Badge tone="purple">{roles[role]}</Badge>
            </div>
            <p className="username">
              @mayuan <span>·</span> SC-Wiki 贡献者
            </p>
            {!isPublic && (
              <p className="email">
                mayuan@example.com{" "}
                <span>
                  <Check />
                  邮箱已验证
                </span>
              </p>
            )}
          </div>
        </div>
        {!isPublic && (
          <div className="profile-actions">
            <a
              className="button quiet"
              href={href(role, "public")}
              target="_blank"
              rel="noopener noreferrer"
            >
              查看公开主页
              <External />
            </a>
            {!editing && (
              <button
                className="button primary"
                onClick={() => {
                  setDraft(profile);
                  setEditing(true);
                }}
              >
                <Edit />
                修改资料
              </button>
            )}
          </div>
        )}
      </div>
      <form onSubmit={save}>
        <div className="profile-fields">
          {[
            ["name", "姓名"],
            ["affiliation", "所属机构"],
            ["orcid", "ORCID"],
          ].map(([key, label]) => (
            <div className="field" key={key}>
              <label htmlFor={`profile-${key}`}>{label}</label>
              {editing ? (
                <input
                  ref={key === "name" ? nameRef : null}
                  id={`profile-${key}`}
                  value={draft[key]}
                  maxLength={key === "orcid" ? 19 : 100}
                  placeholder={
                    key === "orcid" ? "0000-0000-0000-0000" : "可留空"
                  }
                  onChange={(e) =>
                    setDraft({ ...draft, [key]: e.target.value })
                  }
                />
              ) : (
                <div className={`field-value ${!profile[key] ? "unset" : ""}`}>
                  {profile[key] || "暂未填写"}
                </div>
              )}
            </div>
          ))}
          <div className="field research">
            <label htmlFor="profile-interests">研究方向</label>
            {editing ? (
              <>
                <input
                  id="profile-interests"
                  value={draft.interests}
                  onChange={(e) =>
                    setDraft({ ...draft, interests: e.target.value })
                  }
                />
                <small>用逗号分隔，最多 10 项，每项最多 30 字。</small>
              </>
            ) : (
              <div className="research-tags">
                {profile.interests ? (
                  profile.interests
                    .split(", ")
                    .map((item, index) => <span key={index}>{item}</span>)
                ) : (
                  <span>暂未填写</span>
                )}
              </div>
            )}
          </div>
        </div>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <div className="profile-footer">
          <p>
            <Info />
            公开资料对所有访客可见，邮箱仅自己可见。
          </p>
          {editing && (
            <div className="button-row">
              <button
                type="button"
                className="button secondary"
                onClick={() => {
                  setEditing(false);
                  setError("");
                }}
              >
                取消
              </button>
              <button className="button primary" type="submit">
                <Check />
                保存资料
              </button>
            </div>
          )}
        </div>
      </form>
    </section>
  );
}
function PaperList({ role, reviewed = false, onSelect, isPublic = false }) {
  const [query, setQuery] = useState(""),
    [status, setStatus] = useState("全部状态"),
    [tab, setTab] = useState("history");
  const entries = reviewed
    ? tab === "history"
      ? papers
          .filter((p) => p.status === "已收录")
          .map((p) => ({ ...p, status: "检查通过" }))
      : papers
          .filter((p) => p.status === "检查中")
          .map((p) => ({ ...p, status: "待检查" }))
    : papers;
  const filtered = entries.filter(
    (p) =>
      `${p.title} ${p.doi} ${p.material}`
        .toLowerCase()
        .includes(query.toLowerCase()) &&
      (status === "全部状态" || p.status === status),
  );
  return (
    <section
      className="card papers-card"
      aria-label={reviewed ? "检查贡献" : "收录贡献"}
    >
      <SectionHead
        icon={reviewed ? Review : Paper}
        title={
          reviewed
            ? "他帮助检查的 SC-Wiki 收录的论文"
            : "他帮助 SC-Wiki 收录的论文"
        }
        description={
          reviewed
            ? "记录为文献质量做出的检查贡献。"
            : "每一次整理与提交，都让超导知识更完整。这里记录收录贡献。"
        }
      >
        <span className="section-count">
          {reviewed ? "02" : "03"}
          <small>{reviewed ? "篇已检查" : "篇已提交"}</small>
        </span>
      </SectionHead>
      {reviewed && !isPublic && (
        <div className="review-tabs" role="tablist" aria-label="论文检查记录">
          <button
            role="tab"
            aria-selected={tab === "history"}
            className={tab === "history" ? "active" : ""}
            onClick={() => {
              setTab("history");
              setStatus("全部状态");
            }}
          >
            已检查记录 <span>2</span>
          </button>
          <button
            role="tab"
            aria-selected={tab === "queue"}
            className={tab === "queue" ? "active" : ""}
            onClick={() => {
              setTab("queue");
              setStatus("全部状态");
            }}
          >
            待检查 <span className="pending-count">1</span>
          </button>
          <a
            href={href(role, "review")}
            target="_blank"
            rel="noopener noreferrer"
          >
            打开检查工作区
            <External />
          </a>
        </div>
      )}
      <div className="list-toolbar">
        <label className="search-box">
          <Search />
          <input
            aria-label={reviewed ? "搜索检查论文" : "搜索收录论文"}
            placeholder="搜索论文标题、DOI 或材料…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          {query && (
            <button aria-label="清空搜索" onClick={() => setQuery("")}>
              <Close />
            </button>
          )}
        </label>
        <select
          aria-label={reviewed ? "检查状态" : "收录状态"}
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option>全部状态</option>
          {[...new Set(entries.map((p) => p.status))].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
      </div>
      <div className="paper-list">
        {filtered.map((p, index) => (
          <button
            className="paper-row"
            key={p.id}
            onClick={() => onSelect(p, reviewed && tab === "queue")}
          >
            <span className="paper-index">
              {String(index + 1).padStart(2, "0")}
            </span>
            <span className="paper-text">
              <strong>{p.title}</strong>
              <span className="paper-meta">
                <b>{p.material}</b>
                <i />
                {p.journal} · {p.year}
                <i />
                <span>
                  {reviewed ? "检查" : "提交"}于 {p.date}
                </span>
              </span>
            </span>
            <Badge
              tone={
                p.status === "检查中" || p.status === "待检查"
                  ? "amber"
                  : "green"
              }
            >
              {p.status}
            </Badge>
            <Right className="row-arrow" />
          </button>
        ))}
        {!filtered.length && (
          <div className="empty">
            <Search />
            <b>没有匹配的论文</b>
            <p>试试其他关键词，或切换到全部状态。</p>
            <button
              className="button secondary"
              onClick={() => {
                setQuery("");
                setStatus("全部状态");
              }}
            >
              重置筛选
            </button>
          </div>
        )}
      </div>
      <div className="list-footer">
        <span>
          共 {filtered.length} 条{reviewed ? "检查记录" : "收录记录"}
        </span>
        <span>示例数据 · 不代表论文作者身份</span>
      </div>
    </section>
  );
}
function Security({ onNotice }) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState("identity");
  const [oldPassword, setOldPassword] = useState("");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [sentAt, setSentAt] = useState(0);
  const [now, setNow] = useState(Date.now());
  // 固定凭证仅供独立原型演示，正式接入必须由后端校验和发送验证码。
  const [demoPassword, setDemoPassword] = useState("DemoOld123!");
  const cooldown = Math.max(0, Math.ceil((sentAt + 60000 - now) / 1000));
  const expired = sentAt > 0 && now - sentAt >= 300000;
  useEffect(() => {
    if (!sentAt) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [sentAt]);
  const clearForm = () => {
    setStep("identity");
    setOldPassword("");
    setEmail("");
    setCode("");
    setNewPassword("");
    setConfirmPassword("");
    setSentAt(0);
    setError("");
  };
  const sendCode = () => {
    if (
      oldPassword !== demoPassword ||
      email.trim().toLowerCase() !== "mayuan@example.com"
    ) {
      setError("旧密码或账户绑定邮箱不正确，请核对后重试。");
      return;
    }
    if (cooldown > 0) return;
    const timestamp = Date.now();
    setSentAt(timestamp);
    setNow(timestamp);
    setCode("");
    setError("");
    setStep("password");
    onNotice("验证码已模拟发送。演示验证码为 246810，不会发送真实邮件。");
  };
  const submit = (event) => {
    event.preventDefault();
    if (step === "identity") return sendCode();
    if (!sentAt || Date.now() - sentAt >= 300000) {
      setError("验证码已过期，请重新发送。");
      return;
    }
    if (code !== "246810") return setError("验证码不正确，请重新输入。");
    if (newPassword.length < 10) return setError("新密码至少需要 10 位。");
    if (newPassword === demoPassword)
      return setError("新密码不能与旧密码相同。");
    if (newPassword !== confirmPassword)
      return setError("两次输入的新密码不一致。");
    setDemoPassword(newPassword);
    clearForm();
    setOpen(false);
    onNotice("邮箱验证通过，密码已在本次演示中修改。刷新后恢复示例。");
  };
  return (
    <section className="card security-card">
      <button
        className="security-toggle"
        aria-expanded={open}
        onClick={() => {
          clearForm();
          setOpen(!open);
        }}
      >
        <span className="section-icon">
          <Lock />
        </span>
        <span>
          <b>账户安全</b>
          <small>管理登录密码，保护你的研究身份</small>
        </span>
        <span className="security-action">
          修改密码
          <Down className={open ? "rotated" : ""} />
        </span>
      </button>
      {open && (
        <form className="security-form security-verification" onSubmit={submit}>
          <ol className="security-steps" aria-label="修改密码步骤">
            <li
              aria-current={step === "identity" ? "step" : undefined}
              className={step === "identity" ? "current" : "complete"}
            >
              <span>{step === "identity" ? "1" : <Check />}</span>验证身份
            </li>
            <li
              aria-current={step === "password" ? "step" : undefined}
              className={step === "password" ? "current" : ""}
            >
              <span>2</span>设置新密码
            </li>
          </ol>
          {step === "identity" ? (
            <>
              <p className="security-description">
                先验证旧密码和账户绑定邮箱，再向该邮箱发送验证码。
              </p>
              <div className="security-fields">
                <label>
                  旧密码
                  <input
                    type="password"
                    required
                    autoComplete="current-password"
                    value={oldPassword}
                    onChange={(event) => {
                      setOldPassword(event.target.value);
                      setError("");
                    }}
                    placeholder="请输入当前登录密码"
                  />
                </label>
                <label>
                  账户邮箱
                  <input
                    type="email"
                    required
                    autoComplete="email"
                    value={email}
                    onChange={(event) => {
                      setEmail(event.target.value);
                      setError("");
                    }}
                    placeholder="请输入账户绑定的邮箱"
                  />
                </label>
              </div>
              <p className="security-demo">
                仅供体验：
                {demoPassword === "DemoOld123!" ? (
                  <>
                    旧密码 <code>DemoOld123!</code>，
                  </>
                ) : (
                  "请使用刚刚设置的密码，"
                )}
                邮箱 <code>mayuan@example.com</code>
                。不发送真实邮件，请勿输入真实密码。
              </p>
            </>
          ) : (
            <>
              <div className="security-sent">
                <Check />
                <div>
                  <b>身份已验证</b>
                  <p>
                    验证码已模拟发送至账户邮箱{" "}
                    <strong>{email.trim().toLowerCase()}</strong>
                  </p>
                </div>
                <button
                  type="button"
                  className="button quiet"
                  onClick={clearForm}
                >
                  重新验证身份
                </button>
              </div>
              <div className="security-fields">
                <div className="security-code">
                  <label htmlFor="security-email-code">邮箱验证码</label>
                  <div className="code-input">
                    <input
                      id="security-email-code"
                      type="text"
                      required
                      inputMode="numeric"
                      autoComplete="one-time-code"
                      pattern="[0-9]{6}"
                      maxLength={6}
                      value={code}
                      onChange={(event) => setCode(event.target.value)}
                      placeholder="输入 6 位验证码"
                    />
                    <button
                      type="button"
                      className="button secondary"
                      disabled={cooldown > 0}
                      onClick={sendCode}
                    >
                      {cooldown > 0 ? `${cooldown} 秒后重发` : "重新发送"}
                    </button>
                  </div>
                </div>
                <label>
                  新密码
                  <input
                    type="password"
                    required
                    minLength={10}
                    autoComplete="new-password"
                    value={newPassword}
                    onChange={(event) => setNewPassword(event.target.value)}
                    placeholder="至少 10 位，不能与旧密码相同"
                  />
                </label>
                <label>
                  确认新密码
                  <input
                    type="password"
                    required
                    minLength={10}
                    autoComplete="new-password"
                    value={confirmPassword}
                    onChange={(event) => setConfirmPassword(event.target.value)}
                    placeholder="再次输入新密码"
                  />
                </label>
              </div>
              <p className="security-demo">
                演示验证码 <code>246810</code> ·{" "}
                {expired ? "已过期，请重新发送" : "5 分钟内有效"}
                。正式接入后，修改成功将使旧登录状态失效。
              </p>
            </>
          )}
          {error && (
            <p className="security-error" role="alert">
              {error}
            </p>
          )}
          <div className="security-buttons">
            <button
              type="button"
              className="button secondary"
              onClick={() => {
                clearForm();
                setOpen(false);
              }}
            >
              取消
            </button>
            <button
              className="button primary"
              disabled={
                step === "identity"
                  ? !oldPassword || !email.trim()
                  : !code || !newPassword || !confirmPassword
              }
            >
              {step === "identity" ? "验证并发送验证码" : "验证并修改密码"}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
function WorkEntries({ role, onNotice }) {
  return (
    <section className="card work-card">
      <SectionHead
        icon={Settings}
        title="工作入口"
        description={
          role === "superadmin"
            ? "选择一项工作，在新标签页直接开始。"
            : "一起让超导文献更完整、更可信。"
        }
      />
      {role === "superadmin" ? (
        <div className="work-grid">
          {workItems.map(({ id, icon: Icon, title, text, tag }) => (
            <a
              key={id}
              href={href(role, id)}
              target="_blank"
              rel="noopener noreferrer"
              className="work-item"
            >
              <div className="work-item-top">
                <span className="work-icon">
                  <Icon />
                </span>
                <External />
              </div>
              <h3>{title}</h3>
              <p>{text}</p>
              <span
                className={
                  id === "applications" ? "work-tag pending" : "work-tag"
                }
              >
                {tag}
              </span>
            </a>
          ))}
        </div>
      ) : role === "admin" ? (
        <a
          className="admin-entry"
          href={href(role, "review")}
          target="_blank"
          rel="noopener noreferrer"
        >
          <Review />
          <div>
            <b>论文检查工作区</b>
            <p>打开待检查队列，核对论文内容与证据。</p>
          </div>
          <External />
        </a>
      ) : (
        <div className="apply-entry">
          <div>
            <h3>参与文献检查，让专业知识发挥更多价值</h3>
            <p>完善科研资料后，可以申请成为 SC-Wiki 管理员。</p>
          </div>
          <button
            className="button secondary"
            onClick={() =>
              onNotice("演示：管理员申请已提交，本次预览不会创建真实申请。")
            }
          >
            申请成为管理员
            <Right />
          </button>
        </div>
      )}
    </section>
  );
}
function Workspace({ view, onNotice, onSelect }) {
  const item = workItems.find((item) => item.id === view),
    [filter, setFilter] = useState(""),
    [resolved, setResolved] = useState([]),
    [model, setModel] = useState("DeepSeek V3");
  const names = {
    users: ["researcher_lin", "materials_wang", "demo_researcher"],
    applications: ["researcher_lin", "materials_wang"],
    charts: ["超导临界温度与压力", "氢化物研究时间线"],
    news: ["本周超导研究进展", "高压氢化物研究专题"],
    audit: [
      "管理员申请已批准 · researcher_chen",
      "科研资料已更新 · demo_researcher",
    ],
  };
  if (view === "review")
    return (
      <>
        <div className="page-intro">
          <div>
            <span className="eyebrow">REVIEW WORKSPACE</span>
            <h1>论文检查工作区</h1>
            <p>已直接进入待检查队列，无需再次寻找工作入口。</p>
          </div>
        </div>
        <section className="card">
          <SectionHead
            icon={Review}
            title="待检查论文"
            description="示例队列 · 1 篇待检查"
          />
          <button
            className="paper-row"
            onClick={() => onSelect(papers[1], true)}
          >
            <Paper />
            <span className="paper-text">
              <strong>{papers[1].title}</strong>
              <span className="paper-meta">H₃S · Nature · 2015</span>
            </span>
            <span className="text-link">开始检查</span>
            <Right />
          </button>
        </section>
      </>
    );
  if (!item) return <section className="card empty">没有此演示模块</section>;
  return (
    <>
      <div className="page-intro">
        <div>
          <span className="eyebrow">WORKSPACE</span>
          <h1>{item.title}</h1>
          <p>{item.text}。当前为独立演示工作区。</p>
        </div>
      </div>
      <section className="card">
        <SectionHead
          icon={item.icon}
          title={view === "models" ? "站点默认模型" : item.title}
          description="已直达此模块，所有操作仅影响当前演示。"
        />
        {view === "models" ? (
          <form
            className="model-form"
            onSubmit={(e) => {
              e.preventDefault();
              onNotice("默认模型设置已在演示中保存。");
            }}
          >
            <label>
              默认文本模型
              <select value={model} onChange={(e) => setModel(e.target.value)}>
                <option>DeepSeek V3</option>
                <option>Qwen Plus</option>
              </select>
            </label>
            <p className="muted">预览配置交互，不调用真实模型。</p>
            <button className="button primary">保存配置</button>
          </form>
        ) : (
          <>
            <label className="search-box workspace-search">
              <Search />
              <input
                aria-label="搜索工作记录"
                placeholder="搜索记录…"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
              />
            </label>
            <div className="workspace-list">
              {(names[view] || [])
                .filter((name) => name.includes(filter))
                .map((name) => (
                  <div className="workspace-row" key={name}>
                    <span className="section-icon">
                      <item.icon />
                    </span>
                    <div>
                      <b>{name}</b>
                      <small>演示记录 · 2026.10.22</small>
                    </div>
                    {view === "applications" ? (
                      resolved.includes(name) ? (
                        <Badge tone="green">已批准</Badge>
                      ) : (
                        <button
                          className="button secondary"
                          onClick={() => {
                            setResolved([...resolved, name]);
                            onNotice("申请已批准（仅演示）。");
                          }}
                        >
                          批准申请
                        </button>
                      )
                    ) : (
                      view !== "audit" && (
                        <button
                          className="button quiet"
                          onClick={() =>
                            onNotice(
                              `已选择 ${name}。本轮仅演示入口与浏览，不修改生产记录。`,
                            )
                          }
                        >
                          查看
                          <Right />
                        </button>
                      )
                    )}
                  </div>
                ))}
              {!(names[view] || []).some((name) => name.includes(filter)) && (
                <div className="empty">没有匹配的记录</div>
              )}
            </div>
          </>
        )}
      </section>
    </>
  );
}
export function App() {
  const params = new URLSearchParams(window.location.search),
    [role, setRole] = useState(
      roles[params.get("role")] ? params.get("role") : "superadmin",
    );
  const view = params.get("view") || "account",
    [collapsed, setCollapsed] = useState(false),
    [notice, setNotice] = useState(""),
    [selected, setSelected] = useState(null),
    [reviewAction, setReviewAction] = useState(false),
    dialog = useRef(null);
  const isPublic = view === "public",
    isAccount = view === "account" || isPublic,
    canAccess =
      isAccount ||
      (view === "review" ? role !== "user" : role === "superadmin");
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 5000);
    return () => clearTimeout(timer);
  }, [notice]);
  useEffect(() => {
    if (selected) dialog.current?.showModal();
  }, [selected]);
  const select = (paper, review) => {
    setSelected(paper);
    setReviewAction(Boolean(review));
  };
  const changeRole = (next) => {
    setRole(next);
    const url = new URL(window.location.href);
    url.searchParams.set("role", next);
    window.history.replaceState(null, "", url);
  };
  return (
    <div className={`app ${collapsed ? "nav-collapsed" : ""}`}>
      <Sidebar
        role={role}
        collapsed={collapsed}
        toggle={() => setCollapsed(!collapsed)}
      />
      <div className="main-shell">
        <header className="topbar">
          <span className="breadcrumb">
            个人空间
            <Right />
            <b>{isPublic ? "公开主页" : isAccount ? "用户中心" : "工作区"}</b>
          </span>
          <span className="topbar-note">
            <span className="online-dot" />
            SC-Wiki · 共建超导知识
          </span>
        </header>
        <main>
          <div className="demo-bar">
            <span>
              <Badge tone="purple">设计预览</Badge>
              <span>示例资料与论文 · 仅本地演示</span>
            </span>
            <div className="role-switch" aria-label="预览角色">
              {Object.entries(roles).map(([key, label]) => (
                <button
                  key={key}
                  aria-pressed={role === key}
                  onClick={() => changeRole(key)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          {isAccount ? (
            <>
              <div className="page-intro">
                <div>
                  <span className="eyebrow">YOUR RESEARCH IDENTITY</span>
                  <h1>{isPublic ? "研究者主页" : "用户中心"}</h1>
                  <p>
                    {isPublic
                      ? "连接研究者与超导知识，记录每一份贡献。"
                      : "管理研究身份，记录每一份对超导知识的贡献。"}
                  </p>
                </div>
                <span className="page-date">
                  SC-Wiki 社区成员
                  <People />
                </span>
              </div>
              <Profile
                key={`${role}-${view}`}
                role={role}
                isPublic={isPublic}
                onNotice={setNotice}
              />
              <div className="contribution-label">
                <span>知识共建</span>
                <span>贡献让知识持续生长</span>
              </div>
              <PaperList role={role} onSelect={select} isPublic={isPublic} />
              {role !== "user" && (
                <PaperList
                  key={role}
                  role={role}
                  reviewed
                  onSelect={select}
                  isPublic={isPublic}
                />
              )}
              {!isPublic && (
                <>
                  <Security key={role} onNotice={setNotice} />
                  <WorkEntries role={role} onNotice={setNotice} />
                </>
              )}
            </>
          ) : canAccess ? (
            <>
              <a className="back-link" href={href(role, "account")}>
                <Back />
                返回用户中心
              </a>
              <Workspace view={view} onNotice={setNotice} onSelect={select} />
            </>
          ) : (
            <section className="card empty">
              <Lock />
              <h1>当前角色无法访问此工作区</h1>
              <a className="button primary" href={href(role, "account")}>
                返回用户中心
              </a>
            </section>
          )}
          <footer className="page-footer">
            <span>
              <span className="footer-brand">SC-Wiki</span>{" "}
              超导知识，因共建而完整。
            </span>
            <span>用户中心 · 交互设计 demo</span>
          </footer>
        </main>
      </div>
      {notice && (
        <div className="toast" role="status">
          <Check />
          <span>{notice}</span>
          <button aria-label="关闭提示" onClick={() => setNotice("")}>
            <Close />
          </button>
        </div>
      )}
      <dialog
        ref={dialog}
        onClose={() => setSelected(null)}
        className="paper-dialog"
      >
        {selected && (
          <>
            <div className="dialog-heading">
              <Badge tone="purple">
                {reviewAction
                  ? "论文检查 · 演示"
                  : selected.status === "检查通过"
                    ? "检查贡献 · 示例"
                    : "收录贡献 · 示例"}
              </Badge>
              <button
                aria-label="关闭详情"
                onClick={() => dialog.current.close()}
              >
                <Close />
              </button>
            </div>
            <h2>{selected.title}</h2>
            <p>
              {selected.journal} · {selected.year} · {selected.material}
            </p>
            <div className="detail-note">
              <Info />
              <span>
                这里展示由该用户帮助收录或检查的论文，不代表该用户是论文作者。
              </span>
            </div>
            <dl>
              <dt>DOI</dt>
              <dd>{selected.doi}</dd>
              <dt>记录状态</dt>
              <dd>{selected.status}</dd>
              <dt>贡献类型</dt>
              <dd>
                {reviewAction || selected.status === "检查通过"
                  ? "论文内容与来源检查"
                  : "文献整理与提交"}
              </dd>
            </dl>
            {reviewAction && (
              <div className="review-checks">
                <h3>内容核对</h3>
                <label>
                  <input type="checkbox" />
                  标题、期刊与 DOI 一致
                </label>
                <label>
                  <input type="checkbox" />
                  材料信息与原文一致
                </label>
                <label>
                  <input type="checkbox" />
                  物性数据已核对来源
                </label>
                <p>此处仅预览检查布局，完整证据审核沿用现有工作区。</p>
              </div>
            )}
            <div className="dialog-footer">
              <a
                className="button secondary"
                href={`https://doi.org/${selected.doi}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                查看原文
                <External />
              </a>
              <button
                className="button primary"
                onClick={() => dialog.current.close()}
              >
                关闭
              </button>
            </div>
          </>
        )}
      </dialog>
    </div>
  );
}

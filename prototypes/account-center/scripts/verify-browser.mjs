import assert from "node:assert/strict";
import fs from "node:fs/promises";
import { chromium } from "playwright";

const base = process.env.DEMO_URL || "http://127.0.0.1:5186";
const browser = await chromium.launch(
  process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
    ? {
        executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE,
        headless: true,
      }
    : { channel: "chrome", headless: true },
);
const context = await browser.newContext({
  viewport: { width: 1440, height: 1100 },
  deviceScaleFactor: 1,
});
const errors = [],
  writes = [],
  checks = [];
context.on("page", (page) =>
  page.on("pageerror", (error) => errors.push(error.message)),
);
context.on("request", (request) => {
  if (!["GET", "HEAD"].includes(request.method())) writes.push(request.url());
});
await fs.mkdir("qa", { recursive: true });
const page = await context.newPage();
async function visit(role, view = "account") {
  await page.goto(`${base}/?role=${role}&view=${view}`);
  await page.getByRole("heading", { level: 1 }).waitFor();
  await page.evaluate(() => document.fonts.ready);
}
async function noOverflow(width) {
  const dimensions = await page.evaluate(() => ({
    viewport: innerWidth,
    scroll: document.documentElement.scrollWidth,
  }));
  assert.ok(dimensions.scroll <= width, JSON.stringify(dimensions));
}
try {
  for (const role of ["user", "admin", "superadmin"]) {
    await visit(role);
    const profile = page.getByRole("region", { name: "个人资料", exact: true });
    assert.equal(await profile.locator("input").count(), 0);
    assert.equal(
      await page.getByRole("region", { name: "检查贡献", exact: true }).count(),
      role === "user" ? 0 : 1,
    );
    assert.equal(
      await page.locator(".work-item").count(),
      role === "superadmin" ? 6 : 0,
    );
    const fields = await page
      .locator(".profile-fields .field")
      .evaluateAll((elements) =>
        elements.map((el) => el.getBoundingClientRect().top),
      );
    assert.equal(fields[0], fields[1]);
    assert.equal(fields[1], fields[2]);
    assert.ok(fields[3] > fields[0]);
    await page.getByRole("button", { name: "修改资料", exact: true }).click();
    await page
      .getByRole("textbox", { name: "姓名", exact: true })
      .fill("取消后的名字");
    await page.getByRole("button", { name: "取消", exact: true }).click();
    assert.equal(await profile.locator(".identity h2").innerText(), "马原");
    await page.getByRole("button", { name: "修改资料", exact: true }).click();
    await page
      .getByRole("textbox", { name: "姓名", exact: true })
      .fill("演示研究者");
    await page
      .getByRole("textbox", { name: "ORCID", exact: true })
      .fill("invalid");
    await page.getByRole("button", { name: "保存资料", exact: true }).click();
    assert.ok(await page.getByRole("alert").isVisible());
    await page
      .getByRole("textbox", { name: "ORCID", exact: true })
      .fill("0000-0002-1825-0097");
    await page.getByRole("button", { name: "保存资料", exact: true }).click();
    assert.equal(
      await profile.locator(".identity h2").innerText(),
      "演示研究者",
    );
    assert.equal(await profile.locator("input").count(), 0);
    checks.push(`${role}: 默认只读、三列、角色差异、取消、错误提示、保存通过`);
    await visit(role);
    await page.screenshot({ path: `qa/${role}-desktop.png`, fullPage: true });
  }
  await page
    .getByRole("textbox", { name: "搜索收录论文" })
    .fill("nothing-matches-123");
  assert.equal(
    await page
      .getByRole("region", { name: "收录贡献", exact: true })
      .locator(".paper-row")
      .count(),
    0,
  );
  await page.getByRole("button", { name: "重置筛选", exact: true }).click();
  await page.getByRole("combobox", { name: "收录状态" }).selectOption("已收录");
  assert.equal(
    await page
      .getByRole("region", { name: "收录贡献", exact: true })
      .locator(".paper-row")
      .count(),
    2,
  );
  await page.getByRole("tab", { name: /待检查/ }).click();
  const review = page.getByRole("region", { name: "检查贡献", exact: true });
  assert.equal(await review.locator(".paper-row").count(), 1);
  await review.locator(".paper-row").click();
  assert.ok(await page.getByRole("dialog").isVisible());
  assert.equal(await page.getByRole("dialog").getByRole("checkbox").count(), 3);
  await page.keyboard.press("Escape");
  assert.ok(!(await page.getByRole("dialog").isVisible()));
  checks.push("搜索空态、重置、状态筛选、待检查队列、详情及 Escape 关闭通过");
  for (const [view, title] of Object.entries({
    users: "用户与权限",
    applications: "管理员申请",
    charts: "图表组合",
    news: "热点管理",
    models: "默认模型配置",
    audit: "操作审计",
    review: "论文检查工作区",
  })) {
    const link = page
      .locator(`a[href="?role=superadmin&view=${view}"]`)
      .first();
    assert.equal(await link.getAttribute("target"), "_blank");
    assert.ok((await link.getAttribute("rel")).includes("noopener"));
    const popupPromise = context.waitForEvent("page");
    await link.click();
    const popup = await popupPromise;
    await popup.waitForLoadState();
    await popup.getByRole("heading", { level: 1, name: title }).waitFor();
    assert.equal(new URL(popup.url()).searchParams.get("view"), view);
    if (view === "applications") {
      await popup
        .getByRole("button", { name: "批准申请", exact: true })
        .first()
        .click();
      assert.ok(await popup.getByText("已批准", { exact: true }).isVisible());
    }
    if (view === "models") {
      await popup.getByRole("combobox").selectOption("Qwen Plus");
      await popup.getByRole("button", { name: "保存配置" }).click();
      assert.ok(await popup.getByRole("status").isVisible());
    }
    await popup.close();
  }
  checks.push("六个工作入口及检查入口均新标签页直达，申请与模型示例操作通过");
  await visit("user", "public");
  assert.equal(
    await page.getByText("mayuan@example.com", { exact: true }).count(),
    0,
  );
  assert.equal(
    await page.getByRole("button", { name: "修改资料", exact: true }).count(),
    0,
  );
  await visit("user", "users");
  await page
    .getByRole("heading", { name: "当前角色无法访问此工作区" })
    .waitFor();
  checks.push("公开页隐藏邮箱、编辑和管理入口；普通角色管理深链受限（仅演示）");
  for (const width of [390, 320, 768]) {
    await page.setViewportSize({ width, height: 844 });
    await visit("superadmin");
    await noOverflow(width);
    await page.getByRole("button", { name: "修改资料", exact: true }).click();
    await noOverflow(width);
    await page
      .getByRole("textbox", { name: "姓名", exact: true })
      .fill("手机修改");
    await page.getByRole("button", { name: "保存资料", exact: true }).click();
    assert.equal(await page.locator(".identity h2").innerText(), "手机修改");
    await visit("superadmin");
    await page.screenshot({
      path: `qa/superadmin-${width}.png`,
      fullPage: true,
    });
  }
  checks.push("390/320/768px 查看及编辑无横向溢出，保存可用");
  await page.setViewportSize({ width: 2048, height: 1033 });
  await visit("superadmin");
  await page.screenshot({ path: "qa/superadmin-wide.png", fullPage: true });
  await page
    .locator(".profile-card")
    .screenshot({ path: "qa/profile-final.png" });
  await page.getByRole("button", { name: "修改资料", exact: true }).click();
  await page
    .locator(".profile-card")
    .screenshot({ path: "qa/profile-edit-final.png" });
  assert.deepEqual(errors, []);
  assert.deepEqual(writes, []);
  const report = {
    checkedAt: new Date().toISOString(),
    checks,
    errors,
    writeRequests: writes,
  };
  await fs.writeFile(
    "qa/browser-results.json",
    JSON.stringify(report, null, 2),
  );
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}

import assert from "node:assert/strict";
import fs from "node:fs/promises";
import { chromium } from "playwright";

const browser = await chromium.launch(
  process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
    ? {
        executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE,
        headless: true,
      }
    : { channel: "chrome", headless: true },
);
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
const errors = [],
  writes = [];
page.on("pageerror", (error) => errors.push(error.message));
page.on("request", (request) => {
  if (!["GET", "HEAD"].includes(request.method())) writes.push(request.url());
});
const security = page.locator(".security-card");
const send = () =>
  security.getByRole("button", { name: "验证并发送验证码", exact: true });
const submit = () =>
  security.getByRole("button", { name: "验证并修改密码", exact: true });
const fillIdentity = async (
  password = "DemoOld123!",
  email = "mayuan@example.com",
) => {
  await security.getByLabel("旧密码", { exact: true }).fill(password);
  await security.getByLabel("账户邮箱", { exact: true }).fill(email);
};
const fillPassword = async (
  code = "246810",
  password = "NewDemoPassword123!",
  confirm = password,
) => {
  await security.getByLabel("邮箱验证码", { exact: true }).fill(code);
  await security.getByLabel("新密码", { exact: true }).fill(password);
  await security.getByLabel("确认新密码", { exact: true }).fill(confirm);
};
try {
  await fs.mkdir("qa", { recursive: true });
  await page.clock.install();
  await page.goto(
    `${process.env.DEMO_URL || "http://127.0.0.1:5186"}/?role=superadmin`,
  );
  await security.locator(".security-toggle").click();
  assert.ok(await send().isDisabled());
  assert.equal(await security.getByLabel("新密码", { exact: true }).count(), 0);
  await security.getByLabel("旧密码", { exact: true }).fill("DemoOld123!");
  assert.ok(await send().isDisabled());
  await fillIdentity("wrong-password");
  await send().click();
  assert.match(
    await security.getByRole("alert").innerText(),
    /旧密码或账户绑定邮箱不正确/,
  );
  assert.equal(
    await security.getByLabel("邮箱验证码", { exact: true }).count(),
    0,
  );
  await fillIdentity("DemoOld123!", "someone@example.com");
  await send().click();
  assert.equal(
    await security.getByLabel("邮箱验证码", { exact: true }).count(),
    0,
  );
  await fillIdentity();
  await security.screenshot({ path: "qa/password-identity-desktop.png" });
  await send().click();
  assert.ok(
    await security.getByRole("button", { name: /秒后重发/ }).isDisabled(),
  );
  assert.equal(await security.getByLabel("旧密码", { exact: true }).count(), 0);
  await security.screenshot({ path: "qa/password-code-desktop.png" });
  await fillPassword("000000");
  await submit().click();
  assert.match(await security.getByRole("alert").innerText(), /验证码不正确/);
  await fillPassword("246810", "NewDemoPassword123!", "DifferentPassword!");
  await submit().click();
  assert.match(await security.getByRole("alert").innerText(), /不一致/);
  await fillPassword("246810", "DemoOld123!");
  await submit().click();
  assert.match(
    await security.getByRole("alert").innerText(),
    /不能与旧密码相同/,
  );
  await page.clock.fastForward(301000);
  await fillPassword();
  await submit().click();
  assert.match(await security.getByRole("alert").innerText(), /验证码已过期/);
  await security.getByRole("button", { name: "重新发送", exact: true }).click();
  assert.equal(
    await security.getByLabel("邮箱验证码", { exact: true }).inputValue(),
    "",
  );
  await fillPassword();
  await submit().click();
  assert.equal(await security.locator("form").count(), 0);
  assert.match(await page.getByRole("status").innerText(), /邮箱验证通过/);
  await security.locator(".security-toggle").click();
  await fillIdentity();
  await send().click();
  assert.ok(await security.getByRole("alert").isVisible());
  await fillIdentity("NewDemoPassword123!");
  await send().click();
  await security
    .getByRole("button", { name: "重新验证身份", exact: true })
    .click();
  assert.equal(
    await security.getByLabel("旧密码", { exact: true }).inputValue(),
    "",
  );
  await fillIdentity("NewDemoPassword123!");
  await send().click();
  await security.getByRole("button", { name: "取消", exact: true }).click();
  await security.locator(".security-toggle").click();
  assert.equal(
    await security.getByLabel("邮箱验证码", { exact: true }).count(),
    0,
  );
  assert.equal(
    await security.getByLabel("账户邮箱", { exact: true }).inputValue(),
    "",
  );
  for (const role of ["管理员", "普通用户"]) {
    await page.getByRole("button", { name: role, exact: true }).click();
    assert.equal(await security.locator("form").count(), 0);
    await security.locator(".security-toggle").click();
    await fillIdentity();
    await send().click();
    await fillPassword();
    await submit().click();
    assert.equal(await security.locator("form").count(), 0);
  }
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 844 });
    await page.reload();
    await security.locator(".security-toggle").click();
    await fillIdentity();
    assert.ok(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    );
    await security.screenshot({ path: `qa/password-identity-${width}.png` });
    await send().click();
    assert.ok(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    );
    await security.screenshot({ path: `qa/password-code-${width}.png` });
  }
  assert.deepEqual(errors, []);
  assert.deepEqual(writes, []);
  const result = {
    checks:
      "三角色完整改密、前置身份、错误验证码、过期与重发、密码一致性、旧密码失效、取消与角色重置、小屏通过",
    pageErrors: errors,
    writeRequests: writes,
  };
  await fs.writeFile(
    "qa/password-results.json",
    JSON.stringify(result, null, 2),
  );
  console.log(result);
} finally {
  await browser.close();
}

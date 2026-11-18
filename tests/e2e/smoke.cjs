// Browser smoke test (local only): signup -> verify -> login -> upload -> verify extraction -> analyze.
// Needs: API on :8000, web on :3000, Postgres, and E2E_OUT_DIR/audit.pdf from
// `uv run python -m compback_extract.synthetic_cli` (see docs/runbooks/local-e2e.md).
const { chromium } = require("playwright");
const { execSync } = require("child_process");

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const OUT = process.env.E2E_OUT_DIR ?? "./.data/e2e";
const DRAIN = process.env.E2E_DRAIN_CMD ?? "uv run python -c \"from compback_worker.runner import run_once\nwhile run_once(): pass\"";
const DB = process.env.E2E_PSQL ?? "psql -h localhost -U postgres -d compback";
const email = `owner-${Date.now()}@example.com`;
const password = "correct horse battery staple 42";
const sh = (cmd) => execSync(cmd, { encoding: "utf8", shell: "/bin/bash" }).trim();

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  page.on("pageerror", (e) => console.log("PAGEERROR", e.message));

  await page.goto(BASE);
  await page.screenshot({ path: `${OUT}/01-landing.png`, fullPage: true });

  await page.goto(`${BASE}/signup`);
  await page.fill("#org_name", "Ridgeline Roofing LLC (Fictional)");
  await page.fill("#email", email);
  await page.fill("#password", password);
  await page.check('input[name="terms"]');
  await page.click('button[type="submit"]');
  await page.getByText("Check your email").waitFor();

  const token = sh(
    `${DB} -tAc "SELECT payload->>'token' FROM email_outbox o JOIN users u ON u.id = o.to_user_id WHERE u.email = '${email}' ORDER BY o.created_at DESC LIMIT 1"`,
  );
  await page.goto(`${BASE}/verify-email?token=${token}`);
  await page.getByText("Your email is verified").waitFor();

  await page.goto(`${BASE}/login`);
  await page.fill("#email", email);
  await page.fill("#password", password);
  await page.click('button[type="submit"]');
  await page.waitForURL(`${BASE}/app`);
  await page.click("text=Ridgeline Roofing LLC (Fictional)");
  await page.waitForURL(/\/app\/[0-9a-f-]+$/);
  const orgUrl = page.url();

  await page.setInputFiles('input[type="file"]', `${OUT}/audit.pdf`);
  await page.getByText("audit.pdf").waitFor();
  console.log(sh(DRAIN));
  await page.reload();
  await page.getByText("ready").first().waitFor();

  await page.fill("#carrier_name", "Demo Workers Insurance Exchange (Fictional)");
  await page.fill("#policy_number", "WC-9399006-SYN");
  await page.selectOption("#state", "NC");
  await page.fill("#period_start", "2024-06-15");
  await page.fill("#period_end", "2025-06-15");
  await page.click("text=Add policy");
  await page.getByText("WC-9399006-SYN").first().waitFor();
  await page.screenshot({ path: `${OUT}/02-workspace.png`, fullPage: true });

  await page.click("text=audit.pdf");
  await page.getByText("Extracted values").waitFor();
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${OUT}/03-verify.png`, fullPage: true });
  await page.click("text=Values match the document");
  await page.getByText("Marked as verified").waitFor();

  await page.goto(orgUrl);
  await page.click("text=WC-9399006-SYN");
  await page.click("text=Attach");
  await page.getByText("attached").waitFor();
  await page.click("text=Run free scan");
  await page.getByText("Free scan result").waitFor();
  await page.click("text=Show steps");
  await page.screenshot({ path: `${OUT}/04-analysis.png`, fullPage: true });
  console.log("OK", page.url());
  await browser.close();
})().catch((e) => {
  console.error("FAILED", e.message);
  process.exit(1);
});

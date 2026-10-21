import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";

const here = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE_CHAT = path.resolve(
  here,
  "../../fixtures/whatsapp/ios/chat.txt",
);

test.describe("SlothDigest smoke (mocked backend via MSW)", () => {
  test("upload fixture, run digest, see the digest card", async ({ page }) => {
    await page.goto("#/sources");

    const input = page.getByLabel("Chat export file");
    await input.setInputFiles(FIXTURE_CHAT);

    await expect(page.getByRole("status")).toContainText(
      /404 new messages, 8 duplicates skipped/i,
      { timeout: 15000 },
    );

    await page.getByRole("button", { name: "Digest" }).click();
    await page.getByRole("button", { name: /run digest now/i }).click();

    await expect(
      page.getByRole("article", { name: /weekend trip planning/i }),
    ).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole("heading", { level: 3, name: /needs you/i }));
  });
});

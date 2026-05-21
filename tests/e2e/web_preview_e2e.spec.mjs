import { test, expect } from "@playwright/test";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..", "..");

function dnsmosSinglePayload() {
  return {
    domain: "speech",
    model: {
      model_key: "dnsmos",
      result: {
        model_name: "DNSMOS",
        grade: "Good",
        duration: 12.3,
        original_sr: 16000,
        original_channels: 1,
        file_path: "demo.wav",
        dimensions: {
          OVRL: { score: 4.2, grade: "Good", description: "整体听感稳定" },
          SIG: { score: 4.4, grade: "Good", description: "语音清晰" },
          BAK: { score: 3.7, grade: "Fair", description: "背景仍有残留" },
        },
      },
    },
    signal: {
      metrics: {
        LUFS: { value: -13.4, unit: "LUFS", grade: "Warning", description: "响度偏高" },
        LRA: { value: 7.2, unit: "LU", grade: "Good", description: "动态范围合理" },
        TruePeak: { value: -0.2, unit: "dBTP", grade: "Warning", description: "峰值接近上限" },
        Clipping: { value: 0, unit: "次", grade: "Good", description: "无削波" },
        SNR: { value: 18.6, unit: "dB", grade: "Good", description: "信噪比可接受" },
      },
    },
  };
}

function dnsmosComparePayload() {
  return {
    domain: "speech",
    model_key: "dnsmos",
    base_key: "B",
    items: [
      {
        key: "A", file_path: "a.wav", rank: 2, delta_from_base: -0.7,
        task: {
          domain: "speech",
          model: {
            model_key: "dnsmos",
            result: {
              model_name: "DNSMOS", grade: "Good", duration: 12.0,
              original_sr: 16000, original_channels: 1, file_path: "a.wav",
              dimensions: {
                OVRL: { score: 3.5, grade: "Fair", description: "整体听感一般" },
                SIG: { score: 3.8, grade: "Fair", description: "语音略模糊" },
                BAK: { score: 3.0, grade: "Fair", description: "背景噪声明显" },
              },
            },
          },
          signal: {
            metrics: {
              LUFS: { value: -14.8, unit: "LUFS", grade: "Good", description: "综合响度稳定" },
              TruePeak: { value: -1.4, unit: "dBTP", grade: "Good", description: "峰值安全" },
              SNR: { value: 23.5, unit: "dB", grade: "Good", description: "信噪比稳定" },
            },
          },
        },
      },
      {
        key: "B", file_path: "b.wav", rank: 1, delta_from_base: 0.7,
        task: {
          domain: "speech",
          model: {
            model_key: "dnsmos",
            result: {
              model_name: "DNSMOS", grade: "Good", duration: 12.1,
              original_sr: 16000, original_channels: 1, file_path: "b.wav",
              dimensions: {
                OVRL: { score: 4.2, grade: "Good", description: "整体听感稳定" },
                SIG: { score: 4.4, grade: "Good", description: "语音清晰" },
                BAK: { score: 3.7, grade: "Fair", description: "背景仍有残留" },
              },
            },
          },
          signal: {
            metrics: {
              LUFS: { value: -14.8, unit: "LUFS", grade: "Good", description: "综合响度稳定" },
              TruePeak: { value: -1.4, unit: "dBTP", grade: "Good", description: "峰值安全" },
              SNR: { value: 23.5, unit: "dB", grade: "Good", description: "信噪比稳定" },
            },
          },
        },
      },
    ],
    summary: {
      winner_key: "B",
      winner_file: "b.wav",
      reason: "B 在 DNSMOS OVRL 维度上比 A 提升 0.7 分",
      metrics: { OVRL: { delta: 0.7 } },
    },
  };
}

async function setupPage(page, apiOverrides = {}) {
  await page.route("**/api/settings", async (route) => {
    await route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({
        default_eval_model: "dnsmos",
        default_analysis_model: "audiobox",
        trace: true,
        compare_default: "free",
      }),
    });
  });

  await page.route("**/api/history", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
  });

  for (const [urlPattern, payload] of Object.entries(apiOverrides)) {
    await page.route(`**${urlPattern}`, async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(payload) });
    });
  }

  await page.goto("/design/web-preview.html");
  await page.waitForLoadState("networkidle");
}

test.describe("web-preview E2E", () => {

  test("empty state: model note and signal note both have content on load", async ({ page }) => {
    await setupPage(page);

    const modelNote = page.locator('[data-model-note="eval-single"]');
    await expect(modelNote).toBeVisible();
    await expect(modelNote).toContainText("DNSMOS");

    const signalNote = page.locator('[data-signal-note="eval-single"]');
    await expect(signalNote).toBeVisible();
    await expect(signalNote).toContainText("信号分析");
  });

  test("empty state: 添加文件 triggers upload and transitions to done", async ({ page }) => {
    await setupPage(page, { "/api/evaluate/upload": dnsmosSinglePayload() });

    const emptyScene = page.locator('[data-page="eval"] [data-scene="empty"].active');
    await expect(emptyScene).toBeVisible();

    const wavFile = path.resolve(repoRoot, "tests/files/test1.wav");

    const uploadCard = page.locator('[data-single-upload-card="eval"]');
    await uploadCard.click();

    const fileInput = await page.locator("input[type='file']").first();
    await fileInput.setInputFiles(wavFile);

    const singleScene = page.locator('[data-page="eval"] [data-scene="single"]');
    await expect(singleScene).toBeVisible({ timeout: 5000 });

    const resultArea = page.locator('[data-page="eval"] [data-result-area="eval-single"]');
    await expect(resultArea).toBeVisible({ timeout: 5000 });

    const cardTitle = page.locator('[data-page="eval"] .card-title');
    await expect(cardTitle).toContainText("test1.wav");

    const progressLabel = page.locator('[data-page="eval"] [data-scene="single"] .progress-label');
    await expect(progressLabel).toContainText("评测完成");

    const hasDone = await page.locator('[data-page="eval"] [data-scene="single"] .progress-panel')
      .evaluate((el) => el.classList.contains("done"));
    expect(hasDone).toBe(true);
  });

  test("compare: + 新增组 adds group cards up to F then hides button", async ({ page }) => {
    await setupPage(page);

    await page.locator('[data-scene-trigger="eval:compare"]').first().click();

    const compareScene = page.locator('[data-page="eval"] [data-scene="compare"].active');
    await expect(compareScene).toBeVisible();

    const emptyPanel = page.locator('[data-compare-state="eval-empty"]');
    await expect(emptyPanel).toBeVisible();

    const groupA = page.locator('[data-compare-upload-group="eval-A"]');
    const groupB = page.locator('[data-compare-upload-group="eval-B"]');
    await expect(groupA).toBeVisible();
    await expect(groupB).toBeVisible();

    const addBtn = page.locator('[data-compare-add-group="eval"]');
    await expect(addBtn).toBeVisible();

    await addBtn.click();
    await expect(page.locator('[data-compare-upload-group="eval-C"]')).toBeVisible();

    await addBtn.click();
    await expect(page.locator('[data-compare-upload-group="eval-D"]')).toBeVisible();

    await addBtn.click();
    await expect(page.locator('[data-compare-upload-group="eval-E"]')).toBeVisible();

    await addBtn.click();
    await expect(page.locator('[data-compare-upload-group="eval-F"]')).toBeVisible();

    await expect(addBtn).not.toBeVisible();
  });

  test("compare: upload card shows filename after file upload", async ({ page }) => {
    await setupPage(page);

    await page.locator('[data-scene-trigger="eval:compare"]').first().click();

    const wavA = path.resolve(repoRoot, "tests/files/test1.wav");

    await page.locator('[data-compare-upload-group="eval-A"]').click();
    await page.locator("input[type='file']").last().setInputFiles(wavA);

    const cardA = page.locator('[data-compare-upload-group="eval-A"]');
    await expect(cardA).toHaveClass(/uploaded/);
    await expect(cardA.locator("[data-group-status='eval-A']")).toContainText("已选择");
    await expect(cardA.locator(".upload-hint")).toContainText("test1.wav");

    const hintEl = page.locator('[data-compare-start="eval"] .hint');
    await expect(hintEl).toContainText("至少添加 2 组文件后开始对比评测");
  });

  test("compare: start button hint shows group names after 2 uploads", async ({ page }) => {
    await setupPage(page);

    await page.locator('[data-scene-trigger="eval:compare"]').first().click();

    const wavA = path.resolve(repoRoot, "tests/files/test1.wav");
    const wavB = path.resolve(repoRoot, "tests/files/test2.wav");

    await page.locator('[data-compare-upload-group="eval-A"]').click();
    await page.locator("input[type='file']").last().setInputFiles(wavA);

    await page.locator('[data-compare-upload-group="eval-B"]').click();
    await page.locator("input[type='file']").last().setInputFiles(wavB);

    const startBtn = page.locator('[data-compare-start="eval"]');
    await expect(startBtn).not.toHaveClass(/disabled/);
    const hintEl = startBtn.locator(".hint");
    await expect(hintEl).toContainText("已添加");
  });

  test("compare: upload 2 groups and start compare transitions to done", async ({ page }) => {
    await setupPage(page, { "/api/evaluate/compare-upload": dnsmosComparePayload() });

    await page.locator('[data-scene-trigger="eval:compare"]').first().click();

    const wavA = path.resolve(repoRoot, "tests/files/test1.wav");
    const wavB = path.resolve(repoRoot, "tests/files/test2.wav");

    await page.locator('[data-compare-upload-group="eval-A"]').click();
    await page.locator("input[type='file']").last().setInputFiles(wavA);

    await page.locator('[data-compare-upload-group="eval-B"]').click();
    await page.locator("input[type='file']").last().setInputFiles(wavB);

    // After 2 files uploaded, status is "ready" — use the enabled start button in ready panel
    const startBtn = page.locator('[data-compare-start-ready="eval"]');
    await expect(startBtn).toBeVisible();
    await startBtn.click();

    const donePanel = page.locator('[data-compare-state="eval-done"]');
    await expect(donePanel).toBeVisible({ timeout: 5000 });

    const ranking = page.locator('[data-compare-ranking="eval"] .ranking-list');
    await expect(ranking).toContainText("a.wav");
    await expect(ranking).toContainText("b.wav");
  });

  test("compare: done state base pills are clickable after switching to base mode", async ({ page }) => {
    await setupPage(page, { "/api/evaluate/compare-upload": dnsmosComparePayload() });

    await page.locator('[data-scene-trigger="eval:compare"]').first().click();

    const wavA = path.resolve(repoRoot, "tests/files/test1.wav");
    const wavB = path.resolve(repoRoot, "tests/files/test2.wav");

    await page.locator('[data-compare-upload-group="eval-A"]').click();
    await page.locator("input[type='file']").last().setInputFiles(wavA);

    await page.locator('[data-compare-upload-group="eval-B"]').click();
    await page.locator("input[type='file']").last().setInputFiles(wavB);

    await page.locator('[data-compare-start-ready="eval"]').click();

    const donePanel = page.locator('[data-compare-state="eval-done"]');
    await expect(donePanel).toBeVisible({ timeout: 5000 });

    // Switch to base mode to make base-picker visible
    // Switch to base mode using the chip inside the done panel
    const baseChip = page.locator('[data-compare-state="eval-done"] [data-compare-mode="base"]');
    await baseChip.click();

    const basePickerDone = page.locator('[data-base-picker-done="eval"]');
    await expect(basePickerDone).toBeVisible();

    const baseRowDone = page.locator('[data-base-root-done="eval"]');
    const pillCount = await baseRowDone.locator(".base-pill").count();
    expect(pillCount).toBe(2);

    await baseRowDone.locator(".base-pill:nth-child(2)").click();

    const mode = await page.evaluate(() => state.compare.eval.mode);
    expect(mode).toBe("base");

    const baseKey = await page.evaluate(() => state.compare.eval.base);
    expect(baseKey).toBe("B");
  });

  test("reset clears result and returns to empty state", async ({ page }) => {
    await setupPage(page, { "/api/evaluate/upload": dnsmosSinglePayload() });

    const wavFile = path.resolve(repoRoot, "tests/files/test1.wav");

    const uploadCard = page.locator('[data-single-upload-card="eval"]');
    await uploadCard.click();
    await page.locator("input[type='file']").first().setInputFiles(wavFile);

    await expect(page.locator('[data-page="eval"] [data-result-area="eval-single"]')).toBeVisible({ timeout: 5000 });

    await page.locator('[data-reset-trigger="eval"]').first().click();

    await expect(page.locator('[data-page="eval"] [data-scene="empty"].active')).toBeVisible();
    await expect(page.locator('[data-page="eval"] [data-scene="single"]')).not.toBeVisible();

    const notesRow = page.locator('[data-notes-row="eval"]');
    await expect(notesRow).toBeVisible();
  });
});
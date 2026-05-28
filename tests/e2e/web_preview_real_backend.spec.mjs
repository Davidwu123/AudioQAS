import { test, expect } from "@playwright/test";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..", "..");
const fixtureRoot = path.resolve(repoRoot, "tests", "fixtures");
const formatFixtureRoot = path.resolve(fixtureRoot, "format_matrix");
const errorFixtureRoot = path.resolve(fixtureRoot, "error_cases");

const defaultSettings = {
  default_eval_model: "dnsmos",
  default_analysis_model: "audiobox",
  trace: true,
  compare_default: "free",
  preprocess_resample: true,
  preprocess_to_mono: true,
  preprocess_extract_audio: true,
  export_format: "json",
  history_retention_days: 180,
};

function fixture(name) {
  return path.join(fixtureRoot, name);
}

function formatFixture(name) {
  return path.join(formatFixtureRoot, name);
}

function errorFixture(name) {
  return path.join(errorFixtureRoot, name);
}

function singleFileInput(page, pageKey) {
  return page.locator("input[type='file']").nth(pageKey === "eval" ? 0 : 1);
}

async function resetSettings(page, patch = {}) {
  const response = await page.request.post("/api/settings", {
    data: { ...defaultSettings, ...patch },
  });
  expect(response.ok()).toBeTruthy();
}

async function openApp(page, settingsPatch = {}) {
  await resetSettings(page, settingsPatch);
  await page.goto("/");
  await page.waitForLoadState("networkidle");
}

async function selectTopPage(page, pageKey) {
  await page.locator(`.nav-btn[data-page="${pageKey}"]`).click();
  await expect(page.locator(`section[data-page="${pageKey}"]`)).toHaveClass(/active/);
}

async function selectModel(page, scope, modelKey) {
  const button = page.locator(`[data-model-scope="${scope}"][data-model-key="${modelKey}"]`);
  if (await button.evaluate((node) => node.classList.contains("active"))) return;
  await button.click();
  await expect(button).toHaveClass(/active/);
}

async function uploadSingle(page, pageKey, filePath) {
  const responsePromise = page.waitForResponse(
    (response) => response.url().includes("/api/evaluate/upload") && response.request().method() === "POST",
    { timeout: 120000 },
  );
  await page.locator(`[data-single-upload-card="${pageKey}"]`).click();
  await singleFileInput(page, pageKey).setInputFiles(filePath);
  const response = await responsePromise;
  expect(response.status()).toBe(200);
}

async function expectSingleResult(page, pageKey, expectedFileName, options) {
  const resultArea = page.locator(`[data-page="${pageKey}"] [data-result-area="${pageKey}-single"]`);
  await expect(resultArea).toBeVisible({ timeout: 120000 });
  await expect(page.locator(`[data-page="${pageKey}"] .card-title`).first()).toContainText(expectedFileName);
  await expect(page.locator(`[data-page="${pageKey}"] .progress-label`).first()).toContainText(/完成/);
  await expect(page.locator(`[data-page="${pageKey}"] .pill-grade`).first()).toBeVisible();
  await expect(page.locator(`[data-${pageKey}-file-summary]`)).toContainText("Hz");

  for (const text of options.traceContains || []) {
    await expect(page.locator(`[data-${pageKey}-trace]`)).toContainText(text);
  }
  for (const text of options.modelLabels) {
    await expect(page.locator(`[data-page="${pageKey}"] .score-card .label`, { hasText: text })).toBeVisible();
  }
}

async function expectSingleDetailTabs(page, pageKey, expectedFileName, modelHeader) {
  const table = page.locator(`[data-single-detail-table="${pageKey}"]`);
  await expect(table.locator("thead tr")).toContainText(modelHeader);
  await expect(table.locator("tbody tr")).toContainText(expectedFileName);

  await table.locator(`[data-single-detail-view="signal"]`).click();
  await expect(table.locator("thead tr")).toContainText("综合响度");
  await expect(table.locator("tbody tr")).toContainText(/-?\d+(\.\d+)?/);

  await table.locator(`[data-single-detail-view="full"]`).click();
  await expect(table.locator("thead tr")).toContainText("预处理追溯");
  await expect(table.locator("tbody tr")).toContainText(expectedFileName);
}

async function expectExportDownload(page, pageKey, scene) {
  const downloadPromise = page.waitForEvent("download");
  await page.locator(`[data-export-trigger="${pageKey}"]`).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(new RegExp(`^audioqas_${pageKey}_${scene}_req_${pageKey}_${scene}_\\d{4}\\.json$`));
  const downloadPath = await download.path();
  expect(downloadPath).toBeTruthy();
  const content = fs.readFileSync(downloadPath, "utf8");
  expect(content).toContain(`"page": "${pageKey}"`);
  expect(content).toContain(`"scene": "${scene}"`);
  expect(content).toContain(`"payload"`);
}

async function expectReset(page, pageKey) {
  await page.locator(`[data-reset-trigger="${pageKey}"]`).click();
  await expect(page.locator(`[data-scene-root="${pageKey}"] [data-scene="empty"]`)).toHaveClass(/active/);
  await expect(page.locator(`[data-single-upload-card="${pageKey}"]`)).toBeVisible();
}

async function openCompare(page, pageKey) {
  await page.locator(`[data-scene-trigger="${pageKey}:compare"]`).click();
  await expect(page.locator(`[data-scene-root="${pageKey}"] [data-scene="compare"]`)).toHaveClass(/active/);
}

async function addCompareGroup(page, pageKey, groupKey) {
  await page.locator(`[data-compare-add-group="${pageKey}"]`).click();
  await expect(page.locator(`[data-compare-upload-group="${pageKey}-${groupKey}"]`)).toBeVisible();
}

async function uploadCompareGroup(page, pageKey, groupKey, filePath) {
  const uploadCard = page.locator(`[data-compare-upload-group="${pageKey}-${groupKey}"]:visible`);
  if (await uploadCard.count()) {
    await uploadCard.click();
    await page.locator("input[type='file']").last().setInputFiles(filePath);
    await expect(page.locator(`[data-scene-root="${pageKey}"] [data-scene="compare"]`)).toContainText(path.basename(filePath));
    return;
  }

  const builderCard = page
    .locator(`[data-group-builder="${pageKey}"] .group-card`)
    .filter({ has: page.locator("strong", { hasText: groupKey }) });
  await builderCard.click();
  await page.locator("input[type='file']").last().setInputFiles(filePath);
  await expect(page.locator(`[data-scene-root="${pageKey}"] [data-scene="compare"]`)).toContainText(path.basename(filePath));
}

async function startCompare(page, pageKey) {
  const responsePromise = page.waitForResponse(
    (response) => response.url().includes("/api/evaluate/compare-upload") && response.request().method() === "POST",
    { timeout: 180000 },
  );
  await page.locator(`[data-compare-start-ready="${pageKey}"]`).click();
  const response = await responsePromise;
  expect(response.status()).toBe(200);
  await expect(page.locator(`[data-compare-state="${pageKey}-done"]`)).toBeVisible({ timeout: 180000 });
}

async function expectCompareResult(page, pageKey, expected) {
  await expect(page.locator(`[data-compare-summary="${pageKey}"] strong`).first()).toContainText("推荐版本");

  const rankingCards = page.locator(`[data-compare-ranking="${pageKey}"] .ranking-card`);
  await expect(rankingCards).toHaveCount(expected.files.length);
  for (const fileName of expected.files) {
    await expect(page.locator(`[data-compare-ranking="${pageKey}"] .ranking-list`)).toContainText(fileName);
  }

  const table = page.locator(`[data-compare-table="${pageKey}"]`);
  await expect(table.locator("thead tr")).toContainText(expected.modelHeader);
  await expect(table.locator(`[data-compare-model-tag="${pageKey}"]`)).toContainText(expected.modelTag);

  await table.locator(`[data-detail-view="signal"]`).click();
  await expect(table.locator("thead tr")).toContainText("综合响度");

  await table.locator(`[data-detail-view="full"]`).click();
  await expect(table.locator("thead tr")).toContainText("预处理追溯");
  for (const fileName of expected.files) {
    await expect(table.locator("tbody")).toContainText(fileName);
  }
  for (const text of expected.fullContains || []) {
    await expect(table.locator("tbody")).toContainText(text);
  }
}

async function expectCompareBaseMode(page, pageKey, groupKeys) {
  await page.locator(`[data-compare-state="${pageKey}-done"] [data-compare-kind="${pageKey}"][data-compare-mode="base"]`).click();
  await expect(page.locator(`[data-compare-table="${pageKey}"] [data-base-tag="${pageKey}"]`)).toContainText(`基准组 ${groupKeys[0]}`);
  await expect(page.locator(`[data-compare-ranking="${pageKey}"] .ranking-list`)).toContainText(`vs ${groupKeys[0]}`);

  const secondBase = groupKeys[1];
  await page.locator(`[data-base-root-done="${pageKey}"] .base-pill`, { hasText: secondBase }).click();
  await expect(page.locator(`[data-compare-table="${pageKey}"] [data-base-tag="${pageKey}"]`)).toContainText(`基准组 ${secondBase}`);
  await expect(page.locator(`[data-compare-ranking="${pageKey}"] .ranking-list`)).toContainText(`vs ${secondBase}`);
}

async function openHistory(page) {
  await selectTopPage(page, "history");
  await expect(page.locator("[data-history-stack] .timeline-card").first()).toBeVisible({ timeout: 30000 });
}

async function expectHistoryDetailAlert(page, card, expectedTexts) {
  const dialogPromise = page.waitForEvent("dialog");
  await card.locator("[data-history-detail]").click();
  const dialog = await dialogPromise;
  for (const text of expectedTexts) {
    expect(dialog.message()).toContain(text);
  }
  await dialog.dismiss();
}

async function expectSingleUploadError(page, pageKey, filePath, expectedText) {
  const responsePromise = page.waitForResponse(
    (response) => response.url().includes("/api/evaluate/upload") && response.request().method() === "POST",
    { timeout: 120000 },
  );
  await page.locator(`[data-single-upload-card="${pageKey}"]`).click();
  await singleFileInput(page, pageKey).setInputFiles(filePath);
  const response = await responsePromise;
  expect(response.status()).toBe(400);
  const errorPanel = page.locator(`[data-state-panel="${pageKey}-single-error"]`);
  await expect(errorPanel).toBeVisible();
  await expect(errorPanel.locator("[data-error-reason]")).toContainText(expectedText);
}

test.describe("真实后端 E2E：纯人声评测页", () => {
  test.beforeEach(async ({ page }) => {
    await openApp(page);
  });

  test("纯人声 DNSMOS 单文件 wav 全链路", async ({ page }) => {
    await uploadSingle(page, "eval", formatFixture("format_matrix.wav"));

    await expectSingleResult(page, "eval", "format_matrix.wav", {
      modelLabels: ["整体听感 · OVRL", "语音清晰度 · SIG", "背景干净度 · BAK"],
      traceContains: ["DNSMOS"],
    });
    await expectSingleDetailTabs(page, "eval", "format_matrix.wav", "整体听感");
    await expectExportDownload(page, "eval", "single");
    await expectReset(page, "eval");
  });

  test("纯人声 NISQA 单文件 mp3 全链路", async ({ page }) => {
    await selectModel(page, "eval", "nisqa");
    await uploadSingle(page, "eval", formatFixture("format_matrix.mp3"));

    await expectSingleResult(page, "eval", "format_matrix.mp3", {
      modelLabels: ["整体质量 · OVRL", "噪声感知 · NOI", "连续性 · DIS", "染色感 · COL", "响度 · LOUD"],
      traceContains: ["解码音频", "NISQA"],
    });
    await expectSingleDetailTabs(page, "eval", "format_matrix.mp3", "整体质量");
    await expectExportDownload(page, "eval", "single");
    await expectReset(page, "eval");
  });

  test("纯人声 DNSMOS 单文件视频 mp4 全链路", async ({ page }) => {
    await uploadSingle(page, "eval", formatFixture("format_matrix.mp4"));

    await expectSingleResult(page, "eval", "format_matrix.mp4", {
      modelLabels: ["整体听感 · OVRL", "语音清晰度 · SIG", "背景干净度 · BAK"],
      traceContains: ["原始视频", "抽取音轨", "DNSMOS"],
    });
    await expectSingleDetailTabs(page, "eval", "format_matrix.mp4", "整体听感");
    await expectExportDownload(page, "eval", "single");
    await expectReset(page, "eval");
  });

  test("纯人声 DNSMOS 双组对比全链路", async ({ page }) => {
    await openCompare(page, "eval");
    await uploadCompareGroup(page, "eval", "A", fixture("test1.wav"));
    await uploadCompareGroup(page, "eval", "B", fixture("test2.wav"));
    await startCompare(page, "eval");

    await expectCompareResult(page, "eval", {
      files: ["test1.wav", "test2.wav"],
      modelHeader: "整体听感",
      modelTag: "DNSMOS",
      fullContains: ["DNSMOS"],
    });
    await expectCompareBaseMode(page, "eval", ["A", "B"]);
    await expectExportDownload(page, "eval", "compare");
    await expectReset(page, "eval");
  });

  test("纯人声 NISQA 三组对比包含视频输入全链路", async ({ page }) => {
    await selectModel(page, "eval", "nisqa");
    await openCompare(page, "eval");
    await addCompareGroup(page, "eval", "C");
    await uploadCompareGroup(page, "eval", "C", formatFixture("format_matrix.mp4"));
    await uploadCompareGroup(page, "eval", "A", formatFixture("format_matrix.wav"));
    await uploadCompareGroup(page, "eval", "B", formatFixture("format_matrix.mp3"));
    await startCompare(page, "eval");

    await expectCompareResult(page, "eval", {
      files: ["format_matrix.wav", "format_matrix.mp3", "format_matrix.mp4"],
      modelHeader: "整体质量",
      modelTag: "NISQA",
      fullContains: ["解码音频", "原始视频", "抽取音轨", "NISQA"],
    });
    await expectCompareBaseMode(page, "eval", ["A", "B"]);
    await page.locator(`[data-base-root-done="eval"] .base-pill`, { hasText: "C" }).click();
    await expect(page.locator(`[data-compare-table="eval"] [data-base-tag="eval"]`)).toContainText("基准组 C");
    await expectExportDownload(page, "eval", "compare");
    await expectReset(page, "eval");
  });
});

test.describe("真实后端 E2E：综合音频分析页", () => {
  test.beforeEach(async ({ page }) => {
    await openApp(page);
    await selectTopPage(page, "analysis");
  });

  test("综合音频分析 AudioBox 单文件混合音频全链路", async ({ page }) => {
    await uploadSingle(page, "analysis", formatFixture("format_matrix.mp3"));

    await expectSingleResult(page, "analysis", "format_matrix.mp3", {
      modelLabels: ["制作质量 · PQ", "内容享受 · CE", "内容有用 · CU", "制作复杂度 · PC"],
      traceContains: ["解码音频", "AudioBox Aesthetics"],
    });
    await expectSingleDetailTabs(page, "analysis", "format_matrix.mp3", "制作质量");
    await expectExportDownload(page, "analysis", "single");
    await expectReset(page, "analysis");
  });

  test("综合音频分析 AudioBox 单文件视频全链路", async ({ page }) => {
    await uploadSingle(page, "analysis", formatFixture("format_matrix.mp4"));

    await expectSingleResult(page, "analysis", "format_matrix.mp4", {
      modelLabels: ["制作质量 · PQ", "内容享受 · CE", "内容有用 · CU", "制作复杂度 · PC"],
      traceContains: ["原始视频", "抽取音轨", "AudioBox Aesthetics"],
    });
    await expectSingleDetailTabs(page, "analysis", "format_matrix.mp4", "制作质量");
    await expectExportDownload(page, "analysis", "single");
    await expectReset(page, "analysis");
  });

  test("综合音频分析 AudioBox 双组混合音频对比全链路", async ({ page }) => {
    await openCompare(page, "analysis");
    await uploadCompareGroup(page, "analysis", "A", fixture("test1.wav"));
    await uploadCompareGroup(page, "analysis", "B", fixture("test2.wav"));
    await startCompare(page, "analysis");

    await expectCompareResult(page, "analysis", {
      files: ["test1.wav", "test2.wav"],
      modelHeader: "制作质量",
      modelTag: "AudioBox Aesthetics",
      fullContains: ["AudioBox Aesthetics"],
    });
    await expectCompareBaseMode(page, "analysis", ["A", "B"]);
    await expectExportDownload(page, "analysis", "compare");
    await expectReset(page, "analysis");
  });

  test("综合音频分析 AudioBox 三组混合视频对比全链路", async ({ page }) => {
    await openCompare(page, "analysis");
    await addCompareGroup(page, "analysis", "C");
    await uploadCompareGroup(page, "analysis", "C", formatFixture("format_matrix.mkv"));
    await uploadCompareGroup(page, "analysis", "A", formatFixture("format_matrix.mp4"));
    await uploadCompareGroup(page, "analysis", "B", formatFixture("format_matrix.mov"));
    await startCompare(page, "analysis");

    await expectCompareResult(page, "analysis", {
      files: ["format_matrix.mp4", "format_matrix.mov", "format_matrix.mkv"],
      modelHeader: "制作质量",
      modelTag: "AudioBox Aesthetics",
      fullContains: ["原始视频", "抽取音轨", "AudioBox Aesthetics"],
    });
    await expectCompareBaseMode(page, "analysis", ["A", "B"]);
    await page.locator(`[data-base-root-done="analysis"] .base-pill`, { hasText: "C" }).click();
    await expect(page.locator(`[data-compare-table="analysis"] [data-base-tag="analysis"]`)).toContainText("基准组 C");
    await expectExportDownload(page, "analysis", "compare");
    await expectReset(page, "analysis");
  });
});

test.describe("真实后端 E2E：历史页", () => {
  test.beforeEach(async ({ page }) => {
    await openApp(page);
  });

  test("历史页记录真实单文件任务并可查看详情", async ({ page }) => {
    await uploadSingle(page, "eval", formatFixture("format_matrix.wav"));
    await openHistory(page);

    const firstCard = page.locator("[data-history-stack] .timeline-card").first();
    await expect(firstCard).toContainText("纯人声评测");
    await expect(firstCard).toContainText("format_matrix.wav");
    await expect(firstCard).toContainText("DNSMOS");
    await expect(firstCard).toContainText("单文件");

    await expectHistoryDetailAlert(page, firstCard, ["纯人声评测", "DNSMOS", "single", "format_matrix.wav"]);
  });

  test("历史页记录真实对比任务并可查看详情", async ({ page }) => {
    await openCompare(page, "eval");
    await uploadCompareGroup(page, "eval", "A", fixture("test1.wav"));
    await uploadCompareGroup(page, "eval", "B", fixture("test2.wav"));
    await startCompare(page, "eval");
    await openHistory(page);

    const firstCard = page.locator("[data-history-stack] .timeline-card").first();
    await expect(firstCard).toContainText("纯人声评测");
    await expect(firstCard).toContainText("2 groups");
    await expect(firstCard).toContainText("对比");
    await expect(firstCard.locator("[data-history-trace]")).toContainText("A:");
    await expect(firstCard.locator("[data-history-trace]")).toContainText("B:");

    await expectHistoryDetailAlert(page, firstCard, ["纯人声评测", "compare", "2 groups", "A:", "B:"]);
  });

  test("历史页筛选覆盖全部、纯人声评测、综合音频分析", async ({ page }) => {
    await uploadSingle(page, "eval", formatFixture("format_matrix.wav"));
    await selectTopPage(page, "analysis");
    await uploadSingle(page, "analysis", formatFixture("format_matrix.mp3"));
    await openHistory(page);

    await page.locator("[data-history-filter='all']").click();
    await expect(page.locator("[data-history-stack] .timeline-card").first()).toBeVisible();

    await page.locator("[data-history-filter='eval']").click();
    await expect(page.locator("[data-history-stack] .timeline-card").first()).toBeVisible();
    await expect(page.locator("[data-history-stack]")).toContainText("纯人声评测");
    await expect(page.locator("[data-history-stack]")).not.toContainText("综合音频分析");

    await page.locator("[data-history-filter='analysis']").click();
    await expect(page.locator("[data-history-stack] .timeline-card").first()).toBeVisible();
    await expect(page.locator("[data-history-stack]")).toContainText("综合音频分析");
    await expect(page.locator("[data-history-stack]")).not.toContainText("纯人声评测");
  });
});

test.describe("真实后端 E2E：设置页", () => {
  test.beforeEach(async ({ page }) => {
    await openApp(page);
  });

  test("设置页默认纯人声模型持久化并影响新上传", async ({ page }) => {
    await selectTopPage(page, "settings");
    await page.locator('[data-setting-value="default-eval-model"]').click();
    await expect(page.locator('[data-setting-value="default-eval-model"]')).toContainText("NISQA");

    await page.reload();
    await page.waitForLoadState("networkidle");
    await expect(page.locator('[data-model-scope="eval"][data-model-key="nisqa"]')).toHaveClass(/active/);

    await uploadSingle(page, "eval", formatFixture("format_matrix.mp3"));
    await expectSingleResult(page, "eval", "format_matrix.mp3", {
      modelLabels: ["整体质量 · OVRL", "噪声感知 · NOI"],
      traceContains: ["NISQA"],
    });
  });

  test("设置页 trace 开关影响结果展示并持久化", async ({ page }) => {
    await selectTopPage(page, "settings");
    await page.locator('[data-setting-toggle="trace"]').click();
    await expect(page.locator('[data-setting-toggle="trace"]')).not.toHaveClass(/on/);

    await page.reload();
    await page.waitForLoadState("networkidle");
    await expect(page.locator('[data-setting-toggle="trace"]')).not.toHaveClass(/on/);

    await uploadSingle(page, "eval", formatFixture("format_matrix.wav"));
    await expect(page.locator('[data-trace-block="eval"]')).toBeHidden();
  });

  test("设置页预处理开关影响真实上传错误态", async ({ page }) => {
    await selectTopPage(page, "settings");
    await page.locator('[data-setting-toggle="preprocess-extract-audio"]').click();
    await expect(page.locator('[data-setting-toggle="preprocess-extract-audio"]')).not.toHaveClass(/on/);
    await selectTopPage(page, "eval");
    await expectSingleUploadError(page, "eval", formatFixture("format_matrix.mp4"), "视频自动提取音轨已关闭");

    await resetSettings(page, { preprocess_to_mono: false });
    await page.reload();
    await page.waitForLoadState("networkidle");
    await expectSingleUploadError(page, "eval", fixture("test1.wav"), "自动转单声道已关闭");

    await resetSettings(page, { preprocess_resample: false });
    await page.reload();
    await page.waitForLoadState("networkidle");
    await expectSingleUploadError(page, "eval", fixture("test1.wav"), "自动重采样已关闭");
  });

  test("设置页默认对比模式持久化", async ({ page }) => {
    await selectTopPage(page, "settings");
    await page.locator('[data-setting-value="compare-default"]').click();
    await expect(page.locator('[data-setting-value="compare-default"]')).toContainText("基准对比");

    await page.reload();
    await page.waitForLoadState("networkidle");
    await selectTopPage(page, "eval");
    await openCompare(page, "eval");
    const activeLabels = await page.locator('[data-scene-root="eval"] [data-mode-root="eval"] .mode-chip.active').allTextContents();
    expect(activeLabels).toContain("基准对比");
    expect(activeLabels).not.toContain("自由对比");
  });

  test("设置页导出格式持久化并影响后续导出", async ({ page }) => {
    await selectTopPage(page, "settings");
    await expect(page.locator('[data-setting-value="export-format"]')).toContainText("JSON");
    await page.locator('[data-setting-value="export-format"]').click();
    await expect(page.locator('[data-setting-value="export-format"]')).toContainText("CSV");

    await page.reload();
    await page.waitForLoadState("networkidle");
    await expect(page.locator('[data-setting-value="export-format"]')).toContainText("CSV");

    await uploadSingle(page, "eval", formatFixture("format_matrix.wav"));
    const downloadPromise = page.waitForEvent("download");
    await page.locator('[data-export-trigger="eval"]').click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/\.csv$/);
    const downloadPath = await download.path();
    expect(fs.readFileSync(downloadPath, "utf8")).toContain('"scene","single"');
  });
});

test.describe("真实后端 E2E：错误态", () => {
  test.beforeEach(async ({ page }) => {
    await openApp(page);
  });

  test("错误态空文件上传展示用户可见错误", async ({ page }) => {
    await expectSingleUploadError(page, "eval", errorFixture("empty_upload.wav"), "The uploaded file is empty.");
  });

  test("错误态无效音频上传展示用户可见错误", async ({ page }) => {
    await expectSingleUploadError(page, "eval", errorFixture("invalid_audio.wav"), "could not be decoded");
  });

  test("错误态仅 header WAV 展示 empty_audio", async ({ page }) => {
    await expectSingleUploadError(page, "eval", errorFixture("header_only.wav"), "The uploaded file contains no audio samples.");
  });

  test.skip("损坏 WAV 头包含 PCM payload 时恢复成功并展示结果", async ({ page }) => {
    await uploadSingle(page, "eval", errorFixture("damaged_header.wav"));

    await expectSingleResult(page, "eval", "damaged_header.wav", {
      modelLabels: ["整体听感 · OVRL", "语音清晰度 · SIG", "背景干净度 · BAK"],
      traceContains: ["DNSMOS"],
    });
    await expectSingleDetailTabs(page, "eval", "damaged_header.wav", "整体听感");
  });
});

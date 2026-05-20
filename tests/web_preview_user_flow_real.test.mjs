import test from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";
import { JSDOM } from "jsdom";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..");
const htmlPath = path.join(repoRoot, "design", "web-preview.html");
const dataScriptPath = path.join(repoRoot, "design", "web-preview-data.js");
const appScriptPath = path.join(repoRoot, "design", "web-preview-app.js");
const realPayloadHelper = path.join(repoRoot, "tests", "helpers", "web_real_backend_payload.py");

function fetchRealPayload(mode, ...args) {
  const output = execFileSync(
    path.join(repoRoot, ".venv", "bin", "python"),
    [realPayloadHelper, mode, ...args],
    {
      cwd: repoRoot,
      encoding: "utf8",
      maxBuffer: 10 * 1024 * 1024,
      env: {
        ...process.env,
        PYTHONPATH: repoRoot,
      },
    },
  );
  const lines = output.trim().split(/\r?\n/).filter(Boolean);
  return JSON.parse(lines.at(-1));
}

function createFetch(fetchMap) {
  const calls = [];
  const fetch = async function fetch(url, options = {}) {
    const key = typeof url === "string" ? url : String(url);
    calls.push({ url: key, options });
    if (!(key in fetchMap)) {
      throw new Error(`Unexpected fetch: ${url}`);
    }
    const value = fetchMap[key];
    if (typeof value === "function") {
      return value({ url: key, options, calls });
    }
    return {
      ok: true,
      status: 200,
      async json() {
        return value;
      },
    };
  };
  fetch.calls = calls;
  return fetch;
}

async function bootPreview({ fetchMap }) {
  const effectiveFetchMap = {
    "/api/settings": {
      default_eval_model: "dnsmos",
      default_analysis_model: "audiobox",
      trace: true,
      compare_default: "free",
    },
    ...fetchMap,
  };
  const html = fs.readFileSync(htmlPath, "utf8");
  const dom = new JSDOM(html, {
    url: "http://localhost/design/web-preview.html",
    runScripts: "outside-only",
    pretendToBeVisual: true,
  });
  const { window } = dom;
  const alerts = [];
  let rafTime = 0;
  const context = dom.getInternalVMContext();
  const trackedFetch = createFetch(effectiveFetchMap);

  window.fetch = trackedFetch;
  window.alert = (message) => {
    alerts.push(message);
  };
  window.performance.now = () => rafTime;
  window.requestAnimationFrame = (callback) => {
    rafTime += 1000;
    callback(rafTime);
    return rafTime;
  };
  window.cancelAnimationFrame = () => {};

  vm.runInContext(fs.readFileSync(dataScriptPath, "utf8"), context, { filename: dataScriptPath });
  vm.runInContext(fs.readFileSync(appScriptPath, "utf8"), context, { filename: appScriptPath });
  tagOwnedSingleInputs(window.document);
  await flush(window);

  function query(selector) {
    const node = window.document.querySelector(selector);
    assert.ok(node, `Missing selector: ${selector}`);
    return node;
  }

  function setFiles(input, files) {
    Object.defineProperty(input, "files", {
      configurable: true,
      value: files,
    });
  }

  return {
    window,
    async close() {
      dom.window.close();
    },
    alerts,
    text(selector) {
      return window.document.querySelector(selector)?.textContent?.replace(/\s+/g, " ").trim() ?? "";
    },
    texts(selector) {
      return [...window.document.querySelectorAll(selector)].map((node) => node.textContent?.replace(/\s+/g, " ").trim() ?? "");
    },
    async click(selector) {
      query(selector).dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
      await flush(window);
    },
    async uploadSingle(page, fileName) {
      let waitForCompletion = true;
      if (typeof arguments[2] === "object" && arguments[2] !== null) {
        waitForCompletion = arguments[2].waitForCompletion !== false;
      }
      query(`[data-upload-trigger="${page}:single"]`).dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
      const input = query(`input[type="file"][data-test-owner="${page}:single"]`);
      const file = new window.File(["audio"], fileName, { type: "audio/wav" });
      setFiles(input, [file]);
      input.dispatchEvent(new window.Event("change", { bubbles: true }));
      await waitFor(window, () => trackedFetch.calls.some((call) => call.url === "/api/evaluate/upload"), `single upload ${page}`);
      if (!waitForCompletion) return;
      await waitFor(window, () => query(`[data-page="${page}"] .card-title`).textContent?.includes(fileName), `single render ${page}`);
    },
    async openCompare(kind) {
      await this.click(`[data-scene-trigger="${kind}:compare"]`);
      await waitFor(window, () => query(`[data-scene-root="${kind}"] [data-scene="compare"]`).classList.contains("active"), `open compare ${kind}`);
    },
    async uploadCompare(kind, filesByGroup) {
      for (const [groupKey, fileName] of Object.entries(filesByGroup)) {
        const card = [...window.document.querySelectorAll(`[data-group-builder="${kind}"] .group-card`)]
          .find((node) => node.querySelector("strong")?.textContent?.trim() === groupKey);
        assert.ok(card, `Missing compare group card: ${kind} ${groupKey}`);
        const input = resolveClickedInput(card, [...window.document.querySelectorAll('input[type="file"]')]);
        assert.ok(input, `Missing compare input for ${kind} ${groupKey}`);
        const file = new window.File(["audio"], fileName, { type: "audio/wav" });
        setFiles(input, [file]);
        input.dispatchEvent(new window.Event("change", { bubbles: true }));
        await flush(window);
      }
      await waitFor(window, () => trackedFetch.calls.some((call) => call.url === "/api/evaluate/compare-upload"), `compare upload ${kind}`);
      await waitFor(window, () => query(`[data-compare-ranking="${kind}"] .ranking-list`).textContent?.length > 0, `compare render ${kind}`);
    },
  };
}

async function flush(window) {
  await Promise.resolve();
  await new Promise((resolve) => window.setTimeout(resolve, 0));
  await Promise.resolve();
}

async function waitFor(window, predicate, label, timeoutMs = 1000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    await flush(window);
    if (predicate()) return;
  }
  assert.fail(`Timed out waiting for ${label}`);
}

function tagOwnedSingleInputs(document) {
  for (const page of ["eval", "analysis"]) {
    const triggers = [...document.querySelectorAll(`[data-upload-trigger="${page}:single"]`)];
    const hiddenInputs = [...document.querySelectorAll('input[type="file"]')];
    for (const trigger of triggers) {
      const input = resolveOwnedInput(trigger, hiddenInputs);
      if (input) input.dataset.testOwner = `${page}:single`;
    }
  }
}

function resolveOwnedInput(trigger, inputs) {
  let ownedInput = null;
  const cleanup = [];
  for (const input of inputs) {
    const originalClick = input.click;
    input.click = function click() {
      ownedInput = input;
    };
    cleanup.push(() => {
      input.click = originalClick;
    });
  }
  trigger.dispatchEvent(new trigger.ownerDocument.defaultView.MouseEvent("click", { bubbles: true }));
  for (const restore of cleanup) restore();
  return ownedInput;
}

function resolveClickedInput(trigger, inputs) {
  let clickedInput = null;
  const beforeInputs = new Set(inputs);
  const cleanup = [];
  for (const input of inputs) {
    const originalClick = input.click;
    input.click = function click() {
      clickedInput = input;
    };
    cleanup.push(() => {
      input.click = originalClick;
    });
  }
  trigger.dispatchEvent(new trigger.ownerDocument.defaultView.MouseEvent("click", { bubbles: true }));
  for (const restore of cleanup) restore();
  if (clickedInput) return clickedInput;
  const afterInputs = [...trigger.ownerDocument.querySelectorAll('input[type="file"]')];
  return afterInputs.find((input) => !beforeInputs.has(input)) || null;
}

test("real speech dnsmos single-file render stays aligned with preview", async () => {
  const payload = fetchRealPayload("single", "speech", "dnsmos", "test1.wav");
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
      "/api/evaluate/upload": payload,
    },
  });
  try {
    await app.uploadSingle("eval", "test1.wav");
    assert.equal(app.text("[data-eval-file-summary]").includes("48000Hz"), true);
    assert.equal(app.text("[data-eval-file-summary]").includes("Stereo"), true);
    assert.equal(app.text("[data-eval-advice]").length > 0, true);
    assert.equal(app.text('[data-page="eval"] .pill-grade').length > 0, true);
    assert.equal(app.window.document.querySelector('[data-page="eval"] .pill-grade')?.getAttribute("style")?.includes("background:"), true);
    assert.equal(app.text('[data-page="eval"] .overview-summary p').length > 0, true);
    assert.deepEqual(app.texts("[data-eval-model-grid] .score-card .label"), ["整体听感 · OVRL", "语音清晰度 · SIG", "背景干净度 · BAK", "处理建议"]);
    assert.match(app.window.document.querySelector('[data-eval-model-grid] .score-card .bar span')?.getAttribute("style") || "", /var\(--(?:good|fair|excellent|poor|bad|warn)\)/);
    assert.equal(app.text('[data-single-detail-table="eval"] thead tr').includes("整体听感"), true);
    assert.equal(app.text("[data-eval-trace]").includes("DNSMOS"), true);
    await app.click('[data-single-detail-kind="eval"][data-single-detail-view="signal"]');
    assert.equal(app.text('[data-single-detail-table="eval"] thead tr').includes("综合响度"), true);
    assert.match(app.text('[data-single-detail-table="eval"] tbody tr'), /-?\d+\.\d/);
  } finally {
    await app.close();
  }
});

test("real speech nisqa single-file render stays aligned with preview", async () => {
  const payload = fetchRealPayload("single", "speech", "nisqa", "test1.wav");
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
      "/api/evaluate/upload": payload,
    },
  });
  try {
    await app.click('[data-model-scope="eval"][data-model-key="nisqa"]');
    await app.uploadSingle("eval", "test1.wav");
    assert.equal(app.text("[data-eval-advice]").length > 0, true);
    assert.equal(app.text('[data-page="eval"] .pill-grade').includes("·"), true);
    assert.deepEqual(app.texts("[data-eval-model-grid] .score-card .label"), ["整体质量 · OVRL", "噪声感知 · NOI", "连续性 · DIS", "染色感 · COL", "响度 · LOUD"]);
    assert.equal(app.text('[data-single-detail-table="eval"] thead tr').includes("整体质量"), true);
    await app.click('[data-single-detail-kind="eval"][data-single-detail-view="signal"]');
    assert.equal(app.text('[data-single-detail-table="eval"] thead tr').includes("综合响度"), true);
    assert.match(app.text('[data-single-detail-table="eval"] tbody tr'), /-?\d+\.\d/);
    await app.click('[data-single-detail-kind="eval"][data-single-detail-view="full"]');
    assert.equal(app.text('[data-single-detail-table="eval"] tbody tr').includes("NISQA"), true);
  } finally {
    await app.close();
  }
});

test("real analysis audiobox single-file render stays aligned with preview", async () => {
  const payload = fetchRealPayload("single", "mixed", "audiobox", "test1.wav");
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
      "/api/evaluate/upload": payload,
    },
  });
  try {
    await app.click('[data-page="analysis"]');
    await app.uploadSingle("analysis", "test1.wav");
    assert.equal(app.text("[data-analysis-advice]").length > 0, true);
    assert.equal(app.text('[data-page="analysis"] .pill-grade').includes("·"), true);
    assert.equal(app.text('[data-page="analysis"] .overview-summary p').length > 0, true);
    assert.deepEqual(app.texts('[data-page="analysis"] .score-card .label'), ["制作质量 · PQ", "内容享受 · CE", "内容有用 · CU", "制作复杂度 · PC"]);
    assert.equal(app.text("[data-analysis-file-summary]").includes("48000Hz"), true);
    assert.equal(app.text('[data-single-detail-table="analysis"] thead tr').includes("制作质量"), true);
    await app.click('[data-single-detail-kind="analysis"][data-single-detail-view="signal"]');
    assert.equal(app.text('[data-single-detail-table="analysis"] thead tr').includes("综合响度"), true);
    assert.match(app.text('[data-single-detail-table="analysis"] tbody tr'), /-?\d+\.\d/);
  } finally {
    await app.close();
  }
});

test("real speech compare render stays aligned with preview", async () => {
  const payload = fetchRealPayload("compare", "speech", "dnsmos", "test1.wav", "test2.wav");
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
      "/api/evaluate/compare-upload": payload,
    },
  });
  try {
    await app.openCompare("eval");
    await app.uploadCompare("eval", { A: "test1.wav", B: "test2.wav" });
    assert.equal(app.text('[data-compare-summary="eval"] strong').includes("推荐版本"), true);
    assert.notEqual(app.window.document.querySelectorAll('[data-compare-summary="eval"] .compare-summary-default .compare-kpi span')[0]?.className, "", true);
    assert.equal(app.text('[data-compare-ranking="eval"] .ranking-list').includes("test1.wav") || app.text('[data-compare-ranking="eval"] .ranking-list').includes("test2.wav"), true);
    assert.notEqual(app.window.document.querySelector('[data-compare-ranking="eval"] .ranking-card.top .ranking-score strong')?.className, "", true);
    assert.equal(app.text('[data-compare-table="eval"] thead tr').includes("整体听感"), true);
    await app.click('[data-compare-table="eval"] [data-detail-view="signal"]');
    assert.equal(app.text('[data-compare-table="eval"] thead tr').includes("综合响度"), true);
    assert.match(app.text('[data-compare-table="eval"] tbody'), /-?\d+\.\d/);
    await app.click('[data-compare-table="eval"] [data-detail-view="full"]');
    assert.equal(app.text('[data-compare-table="eval"] tbody').includes("DNSMOS"), true);
  } finally {
    await app.close();
  }
});

test("real speech compare nisqa render keeps full dimensions and base mode recomputes runtime copy", async () => {
  const payload = fetchRealPayload("compare", "speech", "nisqa", "test1.wav", "test2.wav");
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
      "/api/evaluate/compare-upload": payload,
    },
  });
  try {
    await app.click('[data-model-scope="eval"][data-model-key="nisqa"]');
    await app.openCompare("eval");
    await app.uploadCompare("eval", { A: "test1.wav", B: "test2.wav" });
    assert.equal(app.text('[data-compare-table="eval"] [data-compare-model-tag="eval"]').includes("NISQA"), true);
    assert.equal(app.text('[data-compare-table="eval"] thead tr').includes("整体质量"), true);
    assert.equal(app.text('[data-compare-table="eval"] thead tr').includes("噪声感知"), true);
    assert.equal(app.text('[data-compare-table="eval"] thead tr').includes("连续性"), true);
    await app.click('[data-compare-kind="eval"][data-compare-mode="base"]');
    await waitFor(app.window, () => app.text('[data-compare-summary="eval"] .compare-summary-alt').includes("比基准 A"), "real nisqa base summary A");
    assert.notEqual(app.window.document.querySelectorAll('[data-compare-summary="eval"] .compare-summary-alt .compare-kpi span')[0]?.className, "", true);
    assert.equal(app.text('[data-compare-ranking="eval"] .ranking-list').includes("vs A"), true);
    await app.click('[data-base-root="eval"] .base-pill:nth-child(2)');
    await waitFor(app.window, () => app.text('[data-compare-summary="eval"] .compare-summary-alt').includes("基准 B"), "real nisqa base summary B");
    assert.equal(app.text('[data-compare-ranking="eval"] .ranking-list').includes("vs B"), true);
  } finally {
    await app.close();
  }
});

test("real analysis compare render stays aligned with preview", async () => {
  const payload = fetchRealPayload("compare", "mixed", "audiobox", "test1.wav", "test2.wav");
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
      "/api/evaluate/compare-upload": payload,
    },
  });
  try {
    await app.click('[data-page="analysis"]');
    await app.openCompare("analysis");
    await app.uploadCompare("analysis", { A: "test1.wav", B: "test2.wav" });
    assert.equal(app.text('[data-compare-summary="analysis"] strong').includes("推荐版本"), true);
    assert.equal(app.text('[data-compare-ranking="analysis"] .ranking-list').includes("test1.wav") || app.text('[data-compare-ranking="analysis"] .ranking-list').includes("test2.wav"), true);
    assert.equal(app.text('[data-compare-table="analysis"] thead tr').includes("制作质量"), true);
    await app.click('[data-compare-kind="analysis"][data-compare-mode="base"]');
    await waitFor(app.window, () => app.text('[data-compare-summary="analysis"] .compare-summary-alt').includes("基准 A"), "real analysis base summary A");
    assert.equal(app.text('[data-compare-ranking="analysis"] .ranking-list').includes("vs A"), true);
    await app.click('[data-base-root="analysis"] .base-pill:nth-child(2)');
    await waitFor(app.window, () => app.text('[data-compare-summary="analysis"] .compare-summary-alt').includes("基准 B"), "real analysis base summary B");
    assert.equal(app.text('[data-compare-ranking="analysis"] .ranking-list').includes("vs B"), true);
    await app.click('[data-compare-table="analysis"] [data-detail-view="signal"]');
    assert.equal(app.text('[data-compare-table="analysis"] thead tr').includes("综合响度"), true);
    await app.click('[data-compare-table="analysis"] [data-detail-view="full"]');
    assert.equal(app.text('[data-compare-table="analysis"] tbody').includes("AudioBox"), true);
  } finally {
    await app.close();
  }
});

test("real single upload failure still surfaces user-facing error copy", async () => {
  const realError = fetchRealPayload("single-error", "speech", "missing-model", "test1.wav");
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
      "/api/evaluate/upload": {
        ok: false,
        status: realError.status,
        async json() {
          return {};
        },
      },
    },
  });
  try {
    await app.uploadSingle("eval", "test1.wav", { waitForCompletion: false });
    await waitFor(app.window, () => app.alerts.length > 0, "real failure alert");
    assert.match(app.alerts[0], /本机评测失败/);
    assert.match(app.alerts[0], /页面渲染失败：/);
  } finally {
    await app.close();
  }
});

test("real history render shows uploaded single-file result summary", async () => {
  const historyItems = fetchRealPayload("history-single", "speech", "dnsmos", "test1.wav");
  const app = await bootPreview({
    fetchMap: {
      "/api/history": historyItems,
    },
  });
  try {
    await app.click('[data-page="history"]');
    assert.equal(app.texts("[data-history-stack] .timeline-card").length >= 1, true);
    assert.equal(app.text("[data-history-stack] .timeline-card:first-child p").includes("test1.wav"), true);
    assert.equal(app.text("[data-history-stack] .timeline-card:first-child p").includes("DNSMOS"), true);
    assert.equal(app.text("[data-history-stack] .timeline-card:first-child p").includes("单文件"), true);
    assert.equal(app.texts("[data-history-stack] .timeline-card:first-child .meta-pill").length >= 2, true);
    assert.equal(app.text("[data-history-stack] .timeline-card:first-child .meta-pill:last-child").includes("预处理:"), true);
  } finally {
    await app.close();
  }
});

test("real settings flow persists compare default and trace state across reload", async () => {
  const settingsState = {
    default_eval_model: "dnsmos",
    default_analysis_model: "audiobox",
    trace: true,
    compare_default: "free",
    preprocess_resample: true,
    preprocess_to_mono: true,
    preprocess_extract_audio: true,
    export_format: "json_csv",
    history_retention_days: 180,
  };
  const fetchMap = {
    "/api/history": [],
    "/api/settings": ({ options }) => {
      if ((options?.method || "GET") === "POST") {
        const patch = JSON.parse(options.body);
        Object.assign(settingsState, patch);
      }
      return {
        ok: true,
        status: 200,
        async json() {
          return { ...settingsState };
        },
      };
    },
  };

  let app = await bootPreview({ fetchMap });
  try {
    await app.click('[data-page="settings"]');
    assert.equal(app.text('[data-setting-value="compare-default"]'), "自由对比");
    await app.click('[data-setting-value="compare-default"]');
    await app.click('[data-setting-toggle="trace"]');
  } finally {
    await app.close();
  }

  app = await bootPreview({ fetchMap });
  try {
    await app.click('[data-page="settings"]');
    assert.equal(app.text('[data-setting-value="compare-default"]'), "基准对比");
    assert.equal(app.window.document.querySelector('[data-setting-toggle="trace"]').classList.contains("on"), false);
    await app.click('[data-page="eval"]');
    await app.openCompare("eval");
    assert.equal(app.text('[data-mode-root="eval"] .mode-chip.active'), "基准对比");
  } finally {
    await app.close();
  }
});

test("settings page persists full advanced options across reload", async () => {
  const settingsState = {
    default_eval_model: "dnsmos",
    default_analysis_model: "audiobox",
    trace: true,
    compare_default: "free",
    preprocess_resample: true,
    preprocess_to_mono: true,
    preprocess_extract_audio: true,
    export_format: "json_csv",
    history_retention_days: 180,
  };
  const fetchMap = {
    "/api/history": [],
    "/api/settings": ({ options }) => {
      if ((options?.method || "GET") === "POST") {
        Object.assign(settingsState, JSON.parse(options.body));
      }
      return {
        ok: true,
        status: 200,
        async json() {
          return { ...settingsState };
        },
      };
    },
  };

  let app = await bootPreview({ fetchMap });
  try {
    await app.click('[data-page="settings"]');
    await app.click('[data-setting-value="default-eval-model"]');
    await app.click('[data-setting-toggle="preprocess-resample"]');
    await app.click('[data-setting-toggle="preprocess-to-mono"]');
    await app.click('[data-setting-toggle="preprocess-extract-audio"]');
    await app.click('[data-setting-value="export-format"]');
    await app.click('[data-setting-value="export-format"]');
    await app.click('[data-setting-value="history-retention-days"]');
    await app.click('[data-setting-value="history-retention-days"]');
  } finally {
    await app.close();
  }

  app = await bootPreview({ fetchMap });
  try {
    await app.click('[data-page="settings"]');
    assert.equal(app.text('[data-setting-value="default-eval-model"]'), "NISQA");
    assert.equal(app.window.document.querySelector('[data-setting-toggle="preprocess-resample"]').classList.contains("on"), false);
    assert.equal(app.window.document.querySelector('[data-setting-toggle="preprocess-to-mono"]').classList.contains("on"), false);
    assert.equal(app.window.document.querySelector('[data-setting-toggle="preprocess-extract-audio"]').classList.contains("on"), false);
    assert.equal(app.text('[data-setting-value="export-format"]'), "CSV");
    assert.equal(app.text('[data-setting-value="history-retention-days"]'), "30 天");
  } finally {
    await app.close();
  }
});

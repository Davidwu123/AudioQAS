import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";
import { JSDOM } from "jsdom";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..");
const htmlPath = path.join(repoRoot, "audioqas", "web", "static", "web-preview.html");
const dataScriptPath = path.join(repoRoot, "audioqas", "web", "static", "web-preview-data.js");
const appScriptPath = path.join(repoRoot, "audioqas", "web", "static", "web-preview-app.js");

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
    if (value && typeof value === "object" && typeof value.json === "function") {
      if (!value.text) value.text = async () => JSON.stringify(await value.json());
      return value;
    }
    return {
      ok: true,
      status: 200,
      async json() {
        return value;
      },
      async text() {
        return JSON.stringify(value);
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
    url: "http://localhost/static-preview/web-preview.html",
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
  vm.runInContext(`
    Object.defineProperty(XMLHttpRequest.prototype, 'upload', {
      get: function() { return undefined; },
      configurable: true,
    });
  `, context, { filename: "xhr-mock" });
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
    document: window.document,
    alerts,
    fetchCalls: trackedFetch.calls,
    async close() {
      dom.window.close();
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
      const card = query(`[data-single-upload-card="${page}"]`);
      card.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
      await flush(window);
      const input = query(`input[type="file"][data-test-owner="${page}:single"]`);
      const file = new window.File(["audio"], fileName, { type: fileName.endsWith(".mov") ? "video/quicktime" : "audio/wav" });
      setFiles(input, [file]);
      input.dispatchEvent(new window.Event("change", { bubbles: true }));
      await waitFor(window, () => trackedFetch.calls.some((call) => call.url === "/api/evaluate/upload"), "single-file upload fetch");
      await waitFor(window, () => {
        const method = trackedFetch.calls.filter((call) => call.url === "/api/evaluate/upload").at(-1)?.options?.method;
        return method === "POST";
      }, "single-file upload POST");
      if (!waitForCompletion) return;
      await waitFor(window, () => {
        const resultArea = window.document.querySelector(`[data-page="${page}"] [data-result-area]`);
        const titleEl = window.document.querySelector(`[data-page="${page}"] .card-title`);
        if (resultArea && resultArea.style.display !== "none" && titleEl && titleEl.textContent?.includes(fileName)) return true;
        const errorPanel = window.document.querySelector(`[data-page="${page}"] [data-state-panel]`);
        if (errorPanel && errorPanel.style.display !== "none") return true;
        return false;
      }, `rendered single-file result for ${page}`);
    },
    async openCompare(kind) {
      await this.click(`[data-scene-trigger="${kind}:compare"]`);
      await waitFor(window, () => {
        return query(`[data-scene-root="${kind}"] [data-scene="compare"]`).classList.contains("active");
      }, `open compare scene for ${kind}`);
    },
    async addCompareGroup(kind) {
      await this.click(`[data-add-group="${kind}"]`);
      await waitFor(window, () => window.document.querySelectorAll(`[data-group-builder="${kind}"] .group-card`).length >= 3, `add compare group for ${kind}`);
    },
    async uploadCompare(kind, filesByGroup, options = {}) {
      const startBtn = window.document.querySelector(`[data-compare-start="${kind}"]`) || window.document.querySelector(`[data-compare-start-ready="${kind}"]`);
      for (const [groupKey, fileName] of Object.entries(filesByGroup)) {
        const groupCard = window.document.querySelector(`[data-compare-upload-group="${kind}-${groupKey}"]`);
        const input = resolveClickedInput(groupCard, [...window.document.querySelectorAll('input[type="file"]')]) || compareFileInputs[kind]?.[groupKey];
        if (!groupCard) {
          const card = [...window.document.querySelectorAll(`[data-group-builder="${kind}"] .group-card`)]
            .find((node) => node.querySelector("strong")?.textContent?.trim() === groupKey);
          assert.ok(card, `Missing compare group card: ${kind} ${groupKey}`);
          const input2 = resolveClickedInput(card, [...window.document.querySelectorAll('input[type="file"]')]);
          assert.ok(input2, `Missing compare input for ${kind} ${groupKey}`);
          const file = new window.File(["audio"], fileName, { type: fileName.endsWith(".mov") ? "video/quicktime" : "audio/wav" });
          setFiles(input2, [file]);
          input2.dispatchEvent(new window.Event("change", { bubbles: true }));
        } else {
          groupCard.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
          await flush(window);
          const lastInput = [...window.document.querySelectorAll('input[type="file"]')].filter(i => !i.dataset.testOwner || i.dataset.testOwner.startsWith(kind + ":compare")).at(-1);
          const file = new window.File(["audio"], fileName, { type: fileName.endsWith(".mov") ? "video/quicktime" : "audio/wav" });
          setFiles(lastInput, [file]);
          lastInput.dispatchEvent(new window.Event("change", { bubbles: true }));
        }
        await flush(window);
      }
      if (options.start === false) return;
      if (startBtn) startBtn.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
      await waitFor(window, () => trackedFetch.calls.some((call) => call.url === "/api/evaluate/compare-upload"), `${kind} compare upload fetch`);
      await waitFor(window, () => {
        const method = trackedFetch.calls.filter((call) => call.url === "/api/evaluate/compare-upload").at(-1)?.options?.method;
        return method === "POST";
      }, `${kind} compare upload POST`);
      const firstFile = Object.values(filesByGroup)[0];
      await waitFor(window, () => {
        return query(`[data-compare-ranking="${kind}"] .ranking-list`).textContent?.includes(firstFile);
      }, `rendered compare ranking for ${kind}`);
    },
    text(selector) {
      return window.document.querySelector(selector)?.textContent?.replace(/\s+/g, " ").trim() ?? "";
    },
    texts(selector) {
      return [...window.document.querySelectorAll(selector)].map((node) => node.textContent?.replace(/\s+/g, " ").trim() ?? "");
    },
    isVisible(selector) {
      const node = window.document.querySelector(selector);
      if (!node) return false;
      return node.style.display !== "none";
    },
    async waitForTextSequence(selector, expectedTexts) {
      for (const expectedText of expectedTexts) {
        await waitFor(window, () => this.text(selector) === expectedText, `text ${expectedText} for ${selector}`);
      }
    },
    observeTexts(selector) {
      const node = query(selector);
      const values = [this.text(selector)];
      const observer = new window.MutationObserver(() => {
        values.push(this.text(selector));
      });
      observer.observe(node, { childList: true, characterData: true, subtree: true });
      return {
        values,
        disconnect() {
          observer.disconnect();
        },
      };
    },
    captureTextAssignments(selector) {
      const node = query(selector);
      const values = [this.text(selector)];
      const descriptor = findPropertyDescriptor(node, "textContent");
      assert.ok(descriptor?.get && descriptor?.set, `Missing textContent descriptor for ${selector}`);
      Object.defineProperty(node, "textContent", {
        configurable: true,
        get() {
          return descriptor.get.call(this);
        },
        set(value) {
          values.push(String(value).replace(/\s+/g, " ").trim());
          descriptor.set.call(this, value);
        },
      });
      return {
        values,
        disconnect() {
          delete node.textContent;
        },
      };
    },
  };
}

async function flush(window) {
  await Promise.resolve();
  await new Promise((resolve) => window.setTimeout(resolve, 0));
  await Promise.resolve();
}

async function waitFor(window, predicate, label, timeoutMs = 500) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    await flush(window);
    if (predicate()) return;
  }
  assert.fail(`Timed out waiting for ${label}`);
}

function tagOwnedSingleInputs(document) {
  const evalCard = document.querySelector('[data-single-upload-card="eval"]');
  const analysisCard = document.querySelector('[data-single-upload-card="analysis"]');
  const hiddenInputs = [...document.querySelectorAll('input[type="file"]')];
  if (evalCard) {
    const input = resolveOwnedInput(evalCard, hiddenInputs);
    if (input) input.dataset.testOwner = "eval:single";
  }
  if (analysisCard) {
    const input = resolveOwnedInput(analysisCard, hiddenInputs);
    if (input) input.dataset.testOwner = "analysis:single";
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
  for (const restore of cleanup) {
    restore();
  }
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
  for (const restore of cleanup) {
    restore();
  }
  if (clickedInput) return clickedInput;
  const afterInputs = [...trigger.ownerDocument.querySelectorAll('input[type="file"]')];
  return afterInputs.find((input) => !beforeInputs.has(input)) || null;
}

function findPropertyDescriptor(target, key) {
  let current = target;
  while (current) {
    const descriptor = Object.getOwnPropertyDescriptor(current, key);
    if (descriptor) return descriptor;
    current = Object.getPrototypeOf(current);
  }
  return null;
}

function buildJsonResponse(payload) {
  return {
    ok: true,
    status: 200,
    async json() {
      return payload;
    },
  };
}

function createDeferredJsonResponse(payload) {
  let resolveJson;
  const response = {
    ok: true,
    status: 200,
    async json() {
      await new Promise((resolve) => {
        resolveJson = resolve;
      });
      return payload;
    },
  };
  return {
    response,
    resolve() {
      resolveJson?.();
    },
  };
}

function baseSignalMetrics(metrics) {
  return {
    LUFS: { value: -15.0, unit: "LUFS", grade: "Good", description: "综合响度稳定" },
    LRA: { value: 7.2, unit: "LU", grade: "Good", description: "动态范围合理" },
    TruePeak: { value: -1.2, unit: "dBTP", grade: "Good", description: "峰值安全" },
    Clipping: { value: 0, unit: "次", grade: "Good", description: "无削波" },
    THD: { value: 0.4, unit: "%", grade: "Good", description: "失真较低" },
    SNR: { value: 22.1, unit: "dB", grade: "Good", description: "信噪比良好" },
    Stereo: { value: "中", unit: "", grade: "Good", description: "声像稳定" },
    ...metrics,
  };
}

function buildDnsmosSinglePayload() {
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
      metrics: baseSignalMetrics({
        LUFS: { value: -13.4, unit: "LUFS", grade: "Warning", description: "响度偏高" },
        TruePeak: { value: -0.2, unit: "dBTP", grade: "Warning", description: "峰值接近上限" },
        SNR: { value: 18.6, unit: "dB", grade: "Good", description: "信噪比可接受" },
      }),
    },
  };
}

function buildNisqaSinglePayload() {
  return {
    domain: "speech",
    model: {
      model_key: "nisqa",
      result: {
        model_name: "NISQA",
        grade: "Good",
        duration: 18.4,
        original_sr: 48000,
        original_channels: 2,
        file_path: "nisqa_sample.wav",
        dimensions: {
          OVRL: { score: 4.3, grade: "Good", description: "整体质量良好" },
          NOI: { score: 4.1, grade: "Good", description: "噪声控制较稳" },
          DIS: { score: 4.0, grade: "Good", description: "连续性稳定" },
          COL: { score: 3.8, grade: "Fair", description: "存在轻微染色" },
          LOUD: { score: 4.2, grade: "Good", description: "响度控制合理" },
        },
      },
    },
    signal: {
      metrics: baseSignalMetrics({
        LUFS: { value: -16.2, unit: "LUFS", grade: "Good", description: "综合响度合理" },
        LRA: { value: 6.8, unit: "LU", grade: "Good", description: "动态稳定" },
        TruePeak: { value: -1.1, unit: "dBTP", grade: "Good", description: "峰值安全" },
        SNR: { value: 21.4, unit: "dB", grade: "Good", description: "信噪比稳定" },
      }),
    },
  };
}

function buildAudioboxSinglePayload() {
  return {
    domain: "mixed",
    model: {
      model_key: "audiobox",
      result: {
        model_name: "AudioBox Aesthetics",
        grade: "Good",
        duration: 31.2,
        original_sr: 48000,
        original_channels: 1,
        file_path: "mix.mov",
        dimensions: {
          PQ: { score: 7.8, grade: "Excellent", description: "制作完成度高" },
          CE: { score: 7.1, grade: "Good", description: "内容享受度稳定" },
          CU: { score: 8.5, grade: "Excellent", description: "内容信息有效" },
          PC: { score: 5.9, grade: "Fair", description: "制作复杂度仍可优化" },
        },
      },
    },
    signal: {
      metrics: baseSignalMetrics({
        LUFS: { value: -13.8, unit: "LUFS", grade: "Warning", description: "响度偏高" },
        LRA: { value: 9.4, unit: "LU", grade: "Good", description: "动态稳定" },
        TruePeak: { value: -0.3, unit: "dBTP", grade: "Warning", description: "峰值接近上限" },
        Stereo: { value: "中", unit: "", grade: "Good", description: "声像稳定" },
      }),
    },
  };
}

function buildCompareSignalMetrics(metrics) {
  return baseSignalMetrics({
    LUFS: { value: -14.8, unit: "LUFS", grade: "Good", description: "综合响度稳定" },
    LRA: { value: 6.2, unit: "LU", grade: "Good", description: "动态范围合理" },
    TruePeak: { value: -1.4, unit: "dBTP", grade: "Good", description: "峰值安全" },
    Clipping: { value: 0, unit: "次", grade: "Good", description: "无削波" },
    THD: { value: 0.3, unit: "%", grade: "Good", description: "失真较低" },
    SNR: { value: 23.5, unit: "dB", grade: "Good", description: "信噪比稳定" },
    Stereo: { value: "中", unit: "", grade: "Good", description: "声像稳定" },
    ...metrics,
  });
}

function buildCompareItem({ key, filePath, rank, delta, modelName, dimensions, signalMetrics }) {
  return {
    key,
    file_path: filePath,
    rank,
    delta_from_base: delta,
    task: {
      domain: modelName === "AudioBox Aesthetics" ? "mixed" : "speech",
      model: {
        model_key: modelName === "NISQA" ? "nisqa" : modelName === "AudioBox Aesthetics" ? "audiobox" : "dnsmos",
        result: {
          model_name: modelName,
          grade: "Good",
          duration: 12.0 + rank,
          original_sr: modelName === "DNSMOS" ? 16000 : 48000,
          original_channels: modelName === "AudioBox Aesthetics" ? 2 : 1,
          file_path: filePath,
          dimensions,
        },
      },
      signal: {
        metrics: buildCompareSignalMetrics(signalMetrics),
      },
    },
  };
}

function buildDnsmosComparePayload() {
  return {
    base_key: "A",
    items: [
      buildCompareItem({
        key: "A",
        filePath: "a.wav",
        rank: 2,
        delta: 0,
        modelName: "DNSMOS",
        dimensions: {
          OVRL: { score: 3.9, grade: "Fair", description: "整体听感一般" },
          SIG: { score: 4.0, grade: "Good", description: "清晰度尚可" },
          BAK: { score: 3.5, grade: "Fair", description: "背景还有残留" },
        },
        signalMetrics: {
          LUFS: { value: -14.9, unit: "LUFS", grade: "Good", description: "响度稳定" },
          TruePeak: { value: -1.0, unit: "dBTP", grade: "Good", description: "峰值安全" },
          Clipping: { value: 1, unit: "次", grade: "Fair", description: "存在轻微削波" },
        },
      }),
      buildCompareItem({
        key: "B",
        filePath: "b.wav",
        rank: 1,
        delta: 0.7,
        modelName: "DNSMOS",
        dimensions: {
          OVRL: { score: 4.6, grade: "Excellent", description: "整体听感最稳" },
          SIG: { score: 4.5, grade: "Excellent", description: "语音清晰" },
          BAK: { score: 4.2, grade: "Good", description: "背景更干净" },
        },
        signalMetrics: {
          LUFS: { value: -15.2, unit: "LUFS", grade: "Good", description: "响度合理" },
          TruePeak: { value: -1.5, unit: "dBTP", grade: "Good", description: "峰值更稳" },
          Clipping: { value: 0, unit: "次", grade: "Good", description: "无削波" },
        },
      }),
    ],
  };
}

function buildNisqaComparePayload() {
  return {
    base_key: "A",
    items: [
      buildCompareItem({
        key: "A",
        filePath: "nisqa_a.wav",
        rank: 2,
        delta: 0,
        modelName: "NISQA",
        dimensions: {
          OVRL: { score: 4.0, grade: "Good", description: "整体质量稳定" },
          NOI: { score: 3.8, grade: "Fair", description: "噪声仍可优化" },
          DIS: { score: 3.9, grade: "Fair", description: "连续性一般" },
          COL: { score: 3.7, grade: "Fair", description: "有轻微染色" },
          LOUD: { score: 4.1, grade: "Good", description: "响度合理" },
        },
        signalMetrics: {
          LUFS: { value: -16.4, unit: "LUFS", grade: "Good", description: "响度稳定" },
          TruePeak: { value: -1.3, unit: "dBTP", grade: "Good", description: "峰值安全" },
        },
      }),
      buildCompareItem({
        key: "B",
        filePath: "nisqa_b.wav",
        rank: 1,
        delta: 0.5,
        modelName: "NISQA",
        dimensions: {
          OVRL: { score: 4.5, grade: "Excellent", description: "整体质量更稳" },
          NOI: { score: 4.4, grade: "Good", description: "噪声控制更强" },
          DIS: { score: 4.2, grade: "Good", description: "连续性更稳" },
          COL: { score: 4.0, grade: "Good", description: "染色更少" },
          LOUD: { score: 4.3, grade: "Good", description: "响度控制更稳" },
        },
        signalMetrics: {
          LUFS: { value: -16.0, unit: "LUFS", grade: "Good", description: "响度合理" },
          TruePeak: { value: -1.6, unit: "dBTP", grade: "Good", description: "峰值安全" },
        },
      }),
    ],
  };
}

function buildAudioboxComparePayload() {
  return {
    base_key: "A",
    items: [
      buildCompareItem({
        key: "A",
        filePath: "rough_mix.mov",
        rank: 2,
        delta: 0,
        modelName: "AudioBox Aesthetics",
        dimensions: {
          PQ: { score: 6.8, grade: "Good", description: "制作质量稳定" },
          CE: { score: 6.6, grade: "Good", description: "内容享受度较稳" },
          CU: { score: 7.2, grade: "Good", description: "内容有效" },
          PC: { score: 5.8, grade: "Fair", description: "制作复杂度一般" },
        },
        signalMetrics: {
          LUFS: { value: -13.9, unit: "LUFS", grade: "Warning", description: "响度偏高" },
          TruePeak: { value: -0.5, unit: "dBTP", grade: "Fair", description: "峰值偏高" },
          Stereo: { value: "宽", unit: "", grade: "Good", description: "声像较宽" },
        },
      }),
      buildCompareItem({
        key: "B",
        filePath: "master_v2.mov",
        rank: 1,
        delta: 0.9,
        modelName: "AudioBox Aesthetics",
        dimensions: {
          PQ: { score: 7.7, grade: "Excellent", description: "制作质量更完整" },
          CE: { score: 7.4, grade: "Good", description: "内容享受度更高" },
          CU: { score: 8.1, grade: "Excellent", description: "内容信息更明确" },
          PC: { score: 6.3, grade: "Good", description: "制作复杂度更优" },
        },
        signalMetrics: {
          LUFS: { value: -14.5, unit: "LUFS", grade: "Good", description: "响度更稳" },
          TruePeak: { value: -1.2, unit: "dBTP", grade: "Good", description: "峰值安全" },
          Stereo: { value: "宽", unit: "", grade: "Good", description: "声像宽阔" },
        },
      }),
    ],
  };
}

test("web preview boots in jsdom and defaults to eval empty scene", async () => {
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
    },
  });
  try {
    assert.equal(app.document.querySelector('[data-page="eval"]').classList.contains("active"), true);
    assert.equal(app.document.querySelector('[data-scene-root="eval"] [data-scene="empty"]').classList.contains("active"), true);
    assert.equal(app.document.querySelector('[data-scene-root="eval"] [data-scene="single"]').classList.contains("active"), false);
  } finally {
    await app.close();
  }
});

test("speech single-file dnsmos flow renders preview-aligned result blocks", async () => {
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
      "/api/evaluate/upload": buildJsonResponse(buildDnsmosSinglePayload()),
    },
  });
  try {
    await app.uploadSingle("eval", "demo.wav");

    assert.equal(app.fetchCalls.some((call) => call.url === "/api/evaluate/upload"), true);
    const uploadCall = app.fetchCalls.filter((call) => call.url === "/api/evaluate/upload").at(-1);
    assert.equal(typeof uploadCall?.options?.headers?.["X-Request-Id"], "string");
    assert.equal(uploadCall?.options?.headers?.["X-Request-Id"].startsWith("req_eval_single_"), true);
    assert.equal(app.text("[data-eval-file-summary]"), "12.3s · 16000Hz · Mono · 当前模型 DNSMOS");
    assert.equal(app.text("[data-eval-advice]"), "建议先整理峰值和响度，再复评。");
    assert.equal(app.text("[data-eval-trace]"), "原始文件 → 重采样到 16kHz → 送入 DNSMOS");
    assert.equal(app.document.querySelector('[data-page="eval"] .pill-grade')?.classList.contains("status-good"), true);
    assert.match(app.document.querySelector('[data-page="eval"] .score-card .bar span')?.getAttribute("style") || "", /var\(--good\)/);
    assert.deepEqual(app.texts("[data-eval-model-grid] .score-card .label"), ["整体听感 · OVRL", "语音清晰度 · SIG", "背景干净度 · BAK", "处理建议"]);
    assert.equal(app.texts('[data-page="eval"] .metric .state')[0], "需关注");
    assert.equal(app.text('[data-single-detail-table="eval"] thead tr').includes("整体听感"), true);
    assert.equal(app.text('[data-single-detail-table="eval"] tbody tr').includes("4.2"), true);
  } finally {
    await app.close();
  }
});

test("speech single-file nisqa flow renders OVRL NOI DIS COL LOUD and supports detail switching", async () => {
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
      "/api/evaluate/upload": buildJsonResponse(buildNisqaSinglePayload()),
    },
  });
  try {
    await app.click('[data-model-scope="eval"][data-model-key="nisqa"]');
    await app.uploadSingle("eval", "nisqa_sample.wav");

    assert.equal(app.fetchCalls.some((call) => call.url === "/api/evaluate/upload"), true);
    assert.equal(app.text("[data-eval-file-summary]"), "18.4s · 48000Hz · Stereo · 当前模型 NISQA");
    assert.equal(app.text("[data-eval-trace]"), "原始文件 → 转单声道 → 保持 48kHz → 送入 NISQA");
    assert.deepEqual(app.texts("[data-eval-model-grid] .score-card .label"), ["整体质量 · OVRL", "噪声感知 · NOI", "连续性 · DIS", "染色感 · COL", "响度 · LOUD"]);
    assert.equal(app.text('[data-single-detail-table="eval"] thead tr').includes("整体质量"), true);
    assert.equal(app.text('[data-single-detail-table="eval"] tbody tr').includes("4.3"), true);

    await app.click('[data-single-detail-kind="eval"][data-single-detail-view="signal"]');
    assert.equal(app.text('[data-single-detail-table="eval"] thead tr').includes("综合响度"), true);
    assert.equal(app.text('[data-single-detail-table="eval"] tbody tr').includes("-16.2"), true);

    await app.click('[data-single-detail-kind="eval"][data-single-detail-view="full"]');
    assert.equal(app.text('[data-single-detail-table="eval"] thead tr').includes("预处理追溯"), true);
    assert.equal(app.text('[data-single-detail-table="eval"] tbody tr').includes("原始文件 → 转单声道 → 保持 48kHz → 送入 NISQA"), true);
  } finally {
    await app.close();
  }
});

test("analysis single-file audiobox flow renders PQ CE CU PC and supports detail switching", async () => {
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
      "/api/evaluate/upload": buildJsonResponse(buildAudioboxSinglePayload()),
    },
  });
  try {
    await app.click('[data-page="analysis"]');
    await app.uploadSingle("analysis", "mix.mov");

    assert.equal(app.fetchCalls.some((call) => call.url === "/api/evaluate/upload"), true);
    assert.equal(app.text("[data-analysis-file-summary]"), "31.2s · 48000Hz · Mono · 当前模型 AudioBox Aesthetics");
    assert.equal(app.text("[data-analysis-advice]"), "建议先整理峰值和响度，再复核内容完成度。");
    assert.equal(app.text("[data-analysis-trace]"), "原始视频 → 抽取音轨 → 保持 48kHz → 送入 AudioBox Aesthetics");
    assert.deepEqual(app.texts('[data-page="analysis"] .score-card .label'), ["制作质量 · PQ", "内容享受 · CE", "内容有用 · CU", "制作复杂度 · PC"]);
    assert.equal(app.texts('[data-page="analysis"] .metric .desc')[2], "峰值接近上限，建议再留 0.7 dBTP 余量。");
    assert.equal(app.text('[data-single-detail-table="analysis"] thead tr').includes("制作质量"), true);
    assert.equal(app.text('[data-single-detail-table="analysis"] tbody tr').includes("7.8"), true);

    await app.click('[data-single-detail-kind="analysis"][data-single-detail-view="signal"]');
    assert.equal(app.text('[data-single-detail-table="analysis"] thead tr').includes("声像宽度"), true);
    assert.equal(app.text('[data-single-detail-table="analysis"] tbody tr').includes("中"), true);

    await app.click('[data-single-detail-kind="analysis"][data-single-detail-view="full"]');
    assert.equal(app.text('[data-single-detail-table="analysis"] thead tr').includes("预处理追溯"), true);
    assert.equal(app.text('[data-single-detail-table="analysis"] tbody tr').includes("AudioBox Aesthetics"), true);
  } finally {
    await app.close();
  }
});

test("speech compare free mode renders recommended version and ranking", async () => {
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
      "/api/evaluate/compare-upload": buildJsonResponse(buildDnsmosComparePayload()),
    },
  });
  try {
    await app.openCompare("eval");
    await app.uploadCompare("eval", {
      A: "a.wav",
      B: "b.wav",
    });

    assert.equal(app.fetchCalls.some((call) => call.url === "/api/evaluate/compare-upload"), true);
    const compareCall = app.fetchCalls.filter((call) => call.url === "/api/evaluate/compare-upload").at(-1);
    assert.equal(typeof compareCall?.options?.headers?.["X-Request-Id"], "string");
    assert.equal(compareCall?.options?.headers?.["X-Request-Id"].startsWith("req_eval_compare_"), true);
    assert.equal(app.text('[data-mode-root="eval"] .mode-chip.active'), "自由对比");
    assert.match(app.text('[data-compare-summary="eval"] strong'), /推荐版本 B/);
    assert.equal(app.text('[data-compare-summary="eval"] .compare-reason').includes("综合表现更稳"), true);
    assert.equal(app.document.querySelectorAll('[data-compare-summary="eval"] .compare-summary-default .compare-kpi span')[0]?.classList.contains("status-excellent"), true);
    assert.equal(app.document.querySelectorAll('[data-compare-summary="eval"] .compare-summary-default .compare-kpi span')[1]?.classList.contains("status-good"), true);
    assert.equal(app.document.querySelectorAll('[data-compare-summary="eval"] .compare-summary-default .compare-kpi span')[2]?.classList.contains("status-good"), true);
    assert.equal(app.text('[data-compare-ranking="eval"] .ranking-list').includes("B · b.wav"), true);
    assert.equal(app.text('[data-compare-ranking="eval"] .ranking-list').includes("综合排序第1"), true);
    assert.equal(app.document.querySelector('[data-compare-ranking="eval"] .ranking-card.top .ranking-score strong')?.classList.contains("status-excellent"), true);
    assert.equal(app.text('[data-compare-table="eval"] [data-base-tag="eval"]'), "自由对比");
    assert.equal(app.text('[data-compare-table="eval"] thead tr').includes("整体听感"), true);
    assert.equal(app.text('[data-compare-table="eval"] tbody').includes("4.6"), true);

    await app.click('[data-compare-table="eval"] [data-detail-view="full"]');
    assert.equal(app.text('[data-compare-table="eval"] thead tr').includes("预处理追溯"), true);
    assert.equal(app.text('[data-compare-table="eval"] tbody tr').includes("原始文件 → 重采样到 16kHz → 送入 DNSMOS"), true);
  } finally {
    await app.close();
  }
});

test("speech compare base mode recomputes summary relative to selected base group", async () => {
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
      "/api/evaluate/compare-upload": buildJsonResponse(buildDnsmosComparePayload()),
    },
  });
  try {
    await app.openCompare("eval");
    await app.uploadCompare("eval", {
      A: "a.wav",
      B: "b.wav",
    });
    await app.click('[data-compare-kind="eval"][data-compare-mode="base"]');
    await waitFor(app.window, () => app.text('[data-compare-ranking="eval"] .ranking-list').includes("vs A +0.7"), "eval base mode ranking A");

    assert.equal(app.text('[data-mode-root="eval"] .mode-chip.active'), "基准对比");
    assert.match(app.text('[data-compare-summary="eval"] .compare-summary-alt strong'), /B 比基准 A 更好/);
    assert.equal(app.text('[data-compare-summary="eval"] .compare-summary-alt').includes("B 比基准 A 更好"), true);
    assert.equal(app.document.querySelectorAll('[data-compare-summary="eval"] .compare-summary-alt .compare-kpi span')[0]?.classList.contains("status-good"), true);
    assert.equal(app.text('[data-compare-ranking="eval"] .ranking-list').includes("vs A +0.7"), true);
    await app.click('[data-compare-table="eval"] [data-detail-view="full"]');
    assert.equal(app.text('[data-compare-table="eval"] thead tr').includes("相对基准差值"), true);

    await app.click('[data-base-root-done="eval"] .base-pill:nth-child(2)');
    await waitFor(app.window, () => app.text('[data-compare-summary="eval"] .compare-summary-alt').includes("当前基准 B 仍然更好"), "eval base mode summary B");
    assert.equal(app.text('[data-mode-root="eval"] .mode-chip.active'), "基准对比");
    assert.equal(app.text('[data-compare-summary="eval"] .compare-summary-alt').includes("当前基准 B 仍然更好"), true);
    assert.equal(app.document.querySelectorAll('[data-compare-summary="eval"] .compare-summary-alt .compare-kpi span')[0]?.classList.contains("status-warn"), true);
    assert.equal(app.text('[data-compare-ranking="eval"] .ranking-list').includes("vs B -0.70"), true);
    assert.equal(app.text('[data-compare-ranking="eval"] .ranking-list').includes("比基准更差"), true);
    assert.equal(app.text('[data-compare-table="eval"] tbody tr').includes("原始文件 → 重采样到 16kHz → 送入 DNSMOS"), true);
  } finally {
    await app.close();
  }
});

test("speech compare nisqa flow keeps OVRL NOI DIS COL LOUD in rendered output", async () => {
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
      "/api/evaluate/compare-upload": buildJsonResponse(buildNisqaComparePayload()),
    },
  });
  try {
    await app.click('[data-model-scope="eval"][data-model-key="nisqa"]');
    await app.openCompare("eval");
    await app.uploadCompare("eval", {
      A: "nisqa_a.wav",
      B: "nisqa_b.wav",
    });

    assert.equal(app.fetchCalls.some((call) => call.url === "/api/evaluate/compare-upload"), true);
    assert.equal(app.text('[data-mode-root="eval"] .mode-chip.active'), "自由对比");
    assert.match(app.text('[data-compare-summary="eval"] strong'), /推荐版本 B/);
    assert.equal(app.text('[data-compare-table="eval"] [data-compare-model-tag="eval"]'), "模型: NISQA");
    assert.deepEqual(
      app.texts('[data-compare-table="eval"] thead .th-label').slice(0, 8),
      ["组别", "文件", "整体质量", "噪声感知", "连续性", "染色感", "响度", "排序"],
    );
    assert.equal(app.text('[data-compare-ranking="eval"] .ranking-list').includes("综合排序第1"), true);
    assert.equal(app.text('[data-compare-table="eval"] tbody').includes("4.5"), true);

    await app.click('[data-compare-table="eval"] [data-detail-view="full"]');
    assert.equal(app.text('[data-compare-table="eval"] thead tr').includes("预处理追溯"), true);
    assert.equal(app.text('[data-compare-table="eval"] tbody').includes("原始文件 → 保持 48kHz → 送入 NISQA"), true);
  } finally {
    await app.close();
  }
});

test("analysis compare flow renders AudioBox summary ranking and detailed pipeline", async () => {
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
      "/api/evaluate/compare-upload": buildJsonResponse(buildAudioboxComparePayload()),
    },
  });
  try {
    await app.click('[data-page="analysis"]');
    await app.openCompare("analysis");
    await app.uploadCompare("analysis", {
      A: "rough_mix.mov",
      B: "master_v2.mov",
    });

    assert.equal(app.fetchCalls.some((call) => call.url === "/api/evaluate/compare-upload"), true);
    assert.equal(app.text('[data-mode-root="analysis"] .mode-chip.active'), "自由对比");
    assert.match(app.text('[data-compare-summary="analysis"] strong'), /推荐版本 B/);
    assert.equal(app.text('[data-compare-summary="analysis"] .compare-reason').includes("综合表现更稳"), true);
    assert.equal(app.text('[data-compare-ranking="analysis"] .ranking-list').includes("B · master_v2.mov"), true);
    assert.equal(app.text('[data-compare-table="analysis"] [data-compare-model-tag="analysis"]'), "模型: AudioBox Aesthetics");
    assert.equal(app.text('[data-compare-table="analysis"] thead tr').includes("制作质量"), true);
    assert.equal(app.text('[data-compare-table="analysis"] tbody').includes("7.7"), true);

    await app.click('[data-compare-table="analysis"] [data-detail-view="full"]');
    assert.equal(app.text('[data-compare-table="analysis"] thead tr').includes("预处理追溯"), true);
    assert.equal(app.text('[data-compare-table="analysis"] tbody').includes("原始视频 → 抽取音轨 → 转单声道 → 保持 48kHz → 送入 AudioBox Aesthetics"), true);
  } finally {
    await app.close();
  }
});

test("history success renders fetched timeline cards and summary pills", async () => {
  const app = await bootPreview({
    fetchMap: {
      "/api/history": buildJsonResponse([
        {
          timestamp: "2026-05-19 10:30",
          page_title: "纯人声评测",
          file_summary: "meeting_take.wav",
          model_label: "DNSMOS",
          scene: "single",
          summary_metrics: ["OVRL 4.12", "True Peak -1.3"],
          trace_summary: "Mono → 16kHz",
        },
        {
          timestamp: "2026-05-19 11:05",
          page_title: "综合音频分析",
          file_summary: "mix_v2.mov",
          model_label: "AudioBox Aesthetics",
          scene: "compare",
          summary_metrics: ["4 组对比", "最佳 B"],
          trace_summary: "抽取音轨 → Mono",
        },
      ]),
    },
  });
  try {
    await app.click('[data-page="history"]');

    assert.equal(app.texts("[data-history-stack] .timeline-card").length, 2);
    assert.equal(app.text("[data-history-stack] .timeline-card:first-child h3"), "2026-05-19 10:30 · 纯人声评测");
    assert.equal(app.text("[data-history-stack] .timeline-card:first-child p"), "meeting_take.wav · DNSMOS · 单文件");
    assert.deepEqual(app.texts("[data-history-stack] .timeline-card:first-child .meta-pill"), [
      "OVRL 4.12",
      "True Peak -1.3",
      "预处理: Mono → 16kHz",
    ]);
    assert.equal(app.text("[data-history-stack] .timeline-card:last-child p"), "mix_v2.mov · AudioBox Aesthetics · 对比");
  } finally {
    await app.close();
  }
});

test("history empty shows empty copy and no timeline cards", async () => {
  const app = await bootPreview({
    fetchMap: {
      "/api/history": buildJsonResponse([]),
    },
  });
  try {
    await app.click('[data-page="history"]');

    assert.equal(app.isVisible("[data-history-empty]"), true);
    assert.equal(app.text("[data-history-empty]"), "暂无历史任务");
    assert.equal(app.texts("[data-history-stack] .timeline-card").length, 0);
  } finally {
    await app.close();
  }
});

test("history error shows user-facing failure copy", async () => {
  const app = await bootPreview({
    fetchMap: {
      "/api/history": {
        ok: false,
        status: 503,
        async json() {
          return {};
        },
      },
    },
  });
  try {
    await app.click('[data-page="history"]');

    assert.equal(app.isVisible("[data-history-empty]"), true);
    assert.equal(app.text("[data-history-empty]"), "历史加载失败：History load failed: 503");
    assert.equal(app.texts("[data-history-stack] .timeline-card").length, 0);
  } finally {
    await app.close();
  }
});

test("history page refreshes automatically when revisiting the page", async () => {
  let historyCallCount = 0;
  const app = await bootPreview({
    fetchMap: {
      "/api/history": () => {
        historyCallCount += 1;
        return {
          ok: true,
          status: 200,
          async json() {
            if (historyCallCount === 1) return [];
            return [{
              timestamp: "2026-05-19 12:00",
              page_title: "纯人声评测",
              file_summary: "yangqi.wav",
              model_label: "DNSMOS",
              scene: "single",
              summary_metrics: ["OVRL 3.91", "LUFS -18.4"],
              trace_summary: "Mono → 16kHz",
            }];
          },
        };
      },
      "/api/settings": {
        default_eval_model: "dnsmos",
        default_analysis_model: "audiobox",
        trace: true,
        compare_default: "free",
      },
    },
  });
  try {
    await app.click('[data-page="eval"]');
    await app.click('[data-page="history"]');

    assert.equal(historyCallCount >= 2, true);
    assert.equal(app.texts("[data-history-stack] .timeline-card").length, 1);
    assert.equal(app.text("[data-history-stack] .timeline-card:first-child p"), "yangqi.wav · DNSMOS · 单文件");
  } finally {
    await app.close();
  }
});

test("settings trace toggle hides result trace blocks but preserves history summary pills", async () => {
  const settingsState = {
    default_eval_model: "dnsmos",
    default_analysis_model: "audiobox",
    trace: true,
    compare_default: "free",
  };
  const app = await bootPreview({
    fetchMap: {
      "/api/history": buildJsonResponse([
        {
          timestamp: "2026-05-19 10:30",
          page_title: "纯人声评测",
          file_summary: "meeting_take.wav",
          model_label: "DNSMOS",
          scene: "single",
          summary_metrics: ["OVRL 4.12", "True Peak -1.3"],
          trace_summary: "Mono → 16kHz",
        },
      ]),
      "/api/evaluate/upload": buildJsonResponse(buildDnsmosSinglePayload()),
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
    },
  });
  try {
    await app.uploadSingle("eval", "demo.wav");
    await app.click('[data-page="history"]');
    assert.equal(app.isVisible("[data-history-stack] [data-history-trace]"), true);
    assert.equal(app.text("[data-history-stack] .timeline-card .meta-pill:first-child"), "OVRL 4.12");

    await app.click('[data-page="settings"]');
    await app.click('[data-setting-toggle="trace"]');

    await app.click('[data-page="eval"]');
    assert.equal(app.isVisible('[data-page="eval"] [data-trace-block]'), false);
    assert.equal(app.text("[data-history-stack] .timeline-card .meta-pill:first-child"), "OVRL 4.12");

    await app.click('[data-page="history"]');
    assert.deepEqual(app.texts("[data-history-stack] .timeline-card .meta-pill").slice(0, 2), ["OVRL 4.12", "True Peak -1.3"]);
    assert.equal(app.isVisible("[data-history-stack] [data-history-trace]"), false);
  } finally {
    await app.close();
  }
});

test("settings compare default toggle changes newly opened compare scene mode", async () => {
  const settingsState = {
    default_eval_model: "dnsmos",
    default_analysis_model: "audiobox",
    trace: true,
    compare_default: "free",
  };
  const app = await bootPreview({
    fetchMap: {
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
    },
  });
  try {
    await app.click('[data-page="settings"]');
    assert.equal(app.text('[data-setting-value="compare-default"]'), "自由对比");
    await app.click('[data-setting-value="compare-default"]');
    assert.equal(app.text('[data-setting-value="compare-default"]'), "基准对比");

    await app.click('[data-page="eval"]');
    await app.openCompare("eval");
    assert.equal(app.text('[data-mode-root="eval"] .mode-chip.active'), "基准对比");

    await app.click('[data-page="analysis"]');
    await app.openCompare("analysis");
    assert.equal(app.text('[data-mode-root="analysis"] .mode-chip.active'), "基准对比");
  } finally {
    await app.close();
  }
});

test("failed single upload shows error state panel", async () => {
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
      "/api/evaluate/upload": {
        ok: false,
        status: 500,
        async json() {
          return {};
        },
      },
    },
  });
  try {
    await app.uploadSingle("eval", "broken.wav");

    const errorPanel = app.document.querySelector('[data-state-panel="eval-single-error"]');
    assert.ok(errorPanel, "error state panel exists");
    assert.equal(errorPanel.style.display !== "none", true, "error state panel visible");
    const reasonEl = errorPanel.querySelector('[data-error-reason]');
    assert.ok(reasonEl, "error reason element exists");
    assert.match(reasonEl.textContent, /Upload evaluate failed: 500/);
  } finally {
    await app.close();
  }
});

test("single upload shows readable preprocess-disabled error when backend rejects auto processing", async () => {
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
      "/api/evaluate/upload": {
        ok: false,
        status: 400,
        async json() {
          return {
            code: "mono_convert_disabled",
            stage: "preprocess",
            message: "Automatic mono conversion is disabled for the current settings.",
          };
        },
      },
    },
  });
  try {
    await app.uploadSingle("eval", "broken.wav");

    const errorPanel = app.document.querySelector('[data-state-panel="eval-single-error"]');
    assert.ok(errorPanel, "error state panel exists for preprocess error");
    assert.equal(errorPanel.style.display !== "none", true, "error state panel visible");
    const reasonEl = errorPanel.querySelector('[data-error-reason]');
    assert.match(reasonEl.textContent, /自动转单声道已关闭/);
  } finally {
    await app.close();
  }
});

test("single upload shows readable backend detail errors for empty audio", async () => {
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
      "/api/evaluate/upload": {
        ok: false,
        status: 400,
        async json() {
          return {
            detail: {
              code: "empty_audio",
              stage: "preprocess",
              message: "The uploaded file contains no audio samples.",
            },
          };
        },
        async text() {
          return JSON.stringify({
            detail: {
              code: "empty_audio",
              stage: "preprocess",
              message: "The uploaded file contains no audio samples.",
            },
          });
        },
      },
    },
  });
  try {
    await app.uploadSingle("eval", "header_only.wav");

    const errorPanel = app.document.querySelector('[data-state-panel="eval-single-error"]');
    assert.ok(errorPanel, "error state panel exists for empty audio");
    assert.equal(errorPanel.style.display !== "none", true, "error state panel visible");
    const reasonEl = errorPanel.querySelector('[data-error-reason]');
    assert.match(reasonEl.textContent, /contains no audio samples/);
  } finally {
    await app.close();
  }
});

test("single upload shows readable file-too-large error when backend rejects oversized upload", async () => {
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
      "/api/evaluate/upload": {
        ok: false,
        status: 413,
        async json() {
          return {
            detail: "File too large (max 500MB)",
          };
        },
      },
    },
  });
  try {
    await app.uploadSingle("eval", "huge.mp4");

    const errorPanel = app.document.querySelector('[data-state-panel="eval-single-error"]');
    assert.ok(errorPanel, "error state panel exists for upload size limit");
    assert.equal(errorPanel.style.display !== "none", true, "error state panel visible");
    const reasonEl = errorPanel.querySelector('[data-error-reason]');
    assert.match(reasonEl.textContent, /500MB|文件超过当前上传上限/);
  } finally {
    await app.close();
  }
});

test("single upload flow reaches done state and shows progress stages", async () => {
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
      "/api/evaluate/upload": buildJsonResponse(buildDnsmosSinglePayload()),
    },
  });
  try {
    const progressLog = app.captureTextAssignments('[data-page="eval"] [data-scene="single"] .progress-label');
    await app.uploadSingle("eval", "demo.wav");
    progressLog.disconnect();

    assertOrderedIncludes(progressLog.values, [
      "上传中",
      "评测完成",
    ]);

    const progressPanel = app.document.querySelector('[data-page="eval"] [data-scene="single"] .progress-panel');
    assert.ok(progressPanel, "progress panel exists");
    assert.equal(progressPanel.classList.contains("done"), true, "progress panel has done class");
  } finally {
    await app.close();
  }
});

test("single export button downloads current result as json", async () => {
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
      "/api/evaluate/upload": buildJsonResponse(buildDnsmosSinglePayload()),
    },
  });
  try {
    const downloadUrls = [];
    const originalCreateObjectURL = app.window.URL.createObjectURL;
    const originalRevokeObjectURL = app.window.URL.revokeObjectURL;
    app.window.URL.createObjectURL = () => {
      const url = "blob:test-export";
      downloadUrls.push(url);
      return url;
    };
    app.window.URL.revokeObjectURL = (url) => {
      downloadUrls.push(`revoked:${url}`);
    };
    const clickedDownloads = [];
    const originalAnchorClick = app.window.HTMLAnchorElement.prototype.click;
    app.window.HTMLAnchorElement.prototype.click = function click() {
      clickedDownloads.push({ href: this.href, download: this.download });
    };

    await app.uploadSingle("eval", "demo.wav");
    await app.click('[data-export-trigger="eval"]');

    assert.equal(downloadUrls.includes("blob:test-export"), true);
    assert.equal(downloadUrls.includes("revoked:blob:test-export"), true);
    assert.equal(clickedDownloads.length, 2);
    assert.equal(clickedDownloads[0].href, "blob:test-export");
    assert.equal(clickedDownloads[0].download.startsWith("audioqas_eval_single_"), true);
    assert.equal(clickedDownloads[0].download.endsWith(".json"), true);
    assert.equal(clickedDownloads[1].download.startsWith("audioqas_eval_single_"), true);
    assert.equal(clickedDownloads[1].download.endsWith(".csv"), true);

    app.window.URL.createObjectURL = originalCreateObjectURL;
    app.window.URL.revokeObjectURL = originalRevokeObjectURL;
    app.window.HTMLAnchorElement.prototype.click = originalAnchorClick;
  } finally {
    await app.close();
  }
});

test("reset button clears current page runtime result and returns to empty", async () => {
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
      "/api/evaluate/upload": buildJsonResponse(buildDnsmosSinglePayload()),
    },
  });
  try {
    await app.uploadSingle("eval", "demo.wav");

    await app.click('[data-reset-trigger="eval"]');

    assert.equal(app.document.querySelector('[data-scene-root="eval"] [data-scene="empty"]').classList.contains("active"), true);
    assert.equal(app.document.querySelector('[data-scene-root="eval"] [data-scene="single"]').classList.contains("active"), false);
  } finally {
    await app.close();
  }
});

test("history filter buttons actually filter runtime cards", async () => {
  const app = await bootPreview({
    fetchMap: {
      "/api/history": buildJsonResponse([
        {
          id: "task-1",
          timestamp: "2026-05-19 10:30",
          page_key: "eval",
          page_title: "纯人声评测",
          scene: "single",
          model_label: "DNSMOS",
          file_summary: "meeting_take.wav",
          summary_metrics: ["OVRL 4.12"],
          trace_summary: "Mono → 16kHz",
        },
        {
          id: "task-2",
          timestamp: "2026-05-19 11:05",
          page_key: "analysis",
          page_title: "综合音频分析",
          scene: "compare",
          compare_mode: "base",
          model_label: "AudioBox Aesthetics",
          file_summary: "mix_v2.mov",
          summary_metrics: ["4 组对比", "最佳 B"],
          trace_summary: "抽取音轨 → Mono",
        },
      ]),
    },
  });
  try {
    await app.click('[data-page="history"]');
    assert.equal(app.texts("[data-history-stack] .timeline-card").length, 2);

    await app.click('[data-history-filter="eval"]');
    assert.equal(app.texts("[data-history-stack] .timeline-card").length, 1);
    assert.equal(app.text("[data-history-stack] .timeline-card:first-child p"), "meeting_take.wav · DNSMOS · 单文件");

    await app.click('[data-history-filter="compare-base"]');
    assert.equal(app.texts("[data-history-stack] .timeline-card").length, 1);
    assert.equal(app.text("[data-history-stack] .timeline-card:first-child p"), "mix_v2.mov · AudioBox Aesthetics · 对比");
  } finally {
    await app.close();
  }
});

test("history detail button loads backend detail and shows alert summary", async () => {
  const app = await bootPreview({
    fetchMap: {
      "/api/history": buildJsonResponse([
        {
          id: "task-1",
          timestamp: "2026-05-19 10:30",
          page_key: "eval",
          page_title: "纯人声评测",
          scene: "single",
          model_label: "DNSMOS",
          file_summary: "meeting_take.wav",
          summary_metrics: ["OVRL 4.12"],
          trace_summary: "Mono → 16kHz",
        },
      ]),
      "/api/history/task-1": buildJsonResponse({
        id: "task-1",
        timestamp: "2026-05-19 10:30",
        page_title: "纯人声评测",
        file_summary: "meeting_take.wav",
        model_label: "DNSMOS",
        scene: "single",
        trace_summary: "Mono → 16kHz",
        detail: {
          domain: "speech",
          file_path: "meeting_take.wav",
        },
      }),
    },
  });
  try {
    await app.click('[data-page="history"]');
    await app.click('[data-history-detail="task-1"]');

    assert.equal(app.fetchCalls.some((call) => call.url === "/api/history/task-1"), true);
    assert.equal(app.alerts.length > 0, true);
    assert.match(app.alerts.at(-1), /meeting_take\.wav/);
    assert.match(app.alerts.at(-1), /DNSMOS/);
  } finally {
    await app.close();
  }
});

test("single upload can reset while request is still running", async () => {
  const deferred = createDeferredJsonResponse(buildDnsmosSinglePayload());
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
      "/api/evaluate/upload": deferred.response,
    },
  });
  try {
    await app.uploadSingle("eval", "slow.wav", { waitForCompletion: false });
    await app.click('[data-reset-trigger="eval"]');

    assert.equal(app.document.querySelector('[data-scene-root="eval"] [data-scene="empty"]').classList.contains("active"), true);
    assert.equal(app.text('[data-single-upload-card="eval"] [data-single-upload-status="eval"]'), "未上传");
  } finally {
    deferred.resolve();
    await app.close();
  }
});

test("single upload error can retry through visible retry control", async () => {
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
      "/api/evaluate/upload": {
        ok: false,
        status: 400,
        async json() {
          return {
            detail: {
              code: "invalid_audio_file",
              stage: "preprocess",
              message: "The uploaded file could not be decoded as a supported audio/video file.",
            },
          };
        },
        async text() {
          return JSON.stringify({
            detail: {
              code: "invalid_audio_file",
              stage: "preprocess",
              message: "The uploaded file could not be decoded as a supported audio/video file.",
            },
          });
        },
      },
    },
  });
  try {
    await app.uploadSingle("eval", "broken.wav");

    assert.equal(app.isVisible('[data-state-panel="eval-single-error"]'), true);
    const inputsBefore = app.document.querySelectorAll('input[type="file"]').length;
    await app.click('[data-retry-trigger="eval:single"]');
    assert.equal(app.document.querySelectorAll('input[type="file"]').length, inputsBefore);
  } finally {
    await app.close();
  }
});

test("compare partial upload reaches ready state before starting", async () => {
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
      "/api/evaluate/compare-upload": buildJsonResponse(buildDnsmosComparePayload()),
    },
  });
  try {
    await app.openCompare("eval");
    await app.uploadCompare("eval", { A: "a.wav", B: "b.wav" }, { start: false });

    assert.equal(app.isVisible('[data-compare-state="eval-ready"]'), true);
    assert.equal(app.text('[data-group-builder="eval"]').includes("a.wav"), true);
    assert.equal(app.text('[data-group-builder="eval"]').includes("b.wav"), true);
  } finally {
    await app.close();
  }
});

test("page switching keeps single results isolated by page", async () => {
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
      "/api/evaluate/upload": ({ options }) => {
        const body = options.body;
        const domain = body.get("domain");
        return buildJsonResponse(domain === "mixed" ? buildAudioboxSinglePayload() : buildDnsmosSinglePayload());
      },
    },
  });
  try {
    await app.uploadSingle("eval", "speech.wav");
    await app.click('[data-page="analysis"]');
    await app.uploadSingle("analysis", "mix.wav");

    assert.equal(app.text('[data-page="analysis"] .card-title'), "mix.wav");
    await app.click('[data-page="eval"]');
    assert.equal(app.text('[data-page="eval"] .card-title'), "speech.wav");
  } finally {
    await app.close();
  }
});

test("model switch after result caches previous model output", async () => {
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
      "/api/evaluate/upload": buildJsonResponse(buildDnsmosSinglePayload()),
    },
  });
  try {
    await app.uploadSingle("eval", "demo.wav");
    assert.equal(app.text("[data-eval-model-grid]").includes("整体听感"), true);

    await app.click('[data-model-scope="eval"][data-model-key="nisqa"]');
    assert.equal(app.isVisible('[data-page="eval"] [data-result-area]'), false);

    await app.click('[data-model-scope="eval"][data-model-key="dnsmos"]');
    assert.equal(app.isVisible('[data-page="eval"] [data-result-area]'), true);
    assert.equal(app.text("[data-eval-model-grid]").includes("整体听感"), true);
  } finally {
    await app.close();
  }
});

test("compare model switch before start clears selected groups for the new model", async () => {
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
      "/api/evaluate/compare-upload": buildJsonResponse(buildDnsmosComparePayload()),
    },
  });
  try {
    await app.openCompare("eval");
    await app.uploadCompare("eval", { A: "a.wav", B: "b.wav" }, { start: false });
    assert.equal(app.isVisible('[data-compare-state="eval-ready"]'), true);

    await app.click('[data-model-scope="eval"][data-model-key="nisqa"]');
    assert.equal(app.isVisible('[data-compare-state="eval-empty"]'), true);
    assert.equal(app.text('[data-compare-upload-group="eval-A"]').includes("未上传"), true);
  } finally {
    await app.close();
  }
});

function assertOrderedIncludes(values, expectedSequence) {
  let index = 0;
  for (const value of values) {
    if (value.startsWith(expectedSequence[index])) index += 1;
    if (index === expectedSequence.length) return;
  }
  assert.fail(`Expected ordered sequence ${expectedSequence.join(" -> ")}, got ${values.join(" | ")}`);
}

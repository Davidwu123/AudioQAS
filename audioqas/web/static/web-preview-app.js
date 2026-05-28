const state = {
  page: "eval",
  evalScene: "empty",
  analysisScene: "empty",
  models: {
    eval: "dnsmos",
    analysis: "audiobox",
  },
  detailViews: {
    eval: "metrics",
    analysis: "metrics",
  },
  compare: {
    eval: { mode: "free", base: "A" },
    analysis: { mode: "free", base: "A" },
  },
};

const runtimeState = {
  single: {
    eval: { file: null, status: "empty", result: null, error: null },
    analysis: { file: null, status: "empty", result: null, error: null },
  },
  compare: {
    groups: {
      eval: {},
      analysis: {},
    },
    results: {
      eval: null,
      analysis: null,
    },
    status: {
      eval: "empty",
      analysis: "empty",
    },
    error: {
      eval: null,
      analysis: null,
    },
  },
  requests: {
    eval: { single: null, compare: null },
    analysis: { single: null, compare: null },
  },
  settings: {
    trace: true,
    compareDefault: "free",
    preprocessResample: true,
    preprocessToMono: true,
    preprocessExtractAudio: true,
    exportFormat: "json_csv",
    historyRetentionDays: 180,
  },
  history: {
    status: "idle",
    items: [],
    error: null,
    filter: "all",
  },
};

const resultCache = {};

function getCacheKey(page, scene, modelKey) {
  return `${page}_${scene}_${modelKey}`;
}

let requestCounter = 0;

function nextRequestId(page, scene) {
  requestCounter += 1;
  return `req_${page}_${scene}_${String(requestCounter).padStart(4, "0")}`;
}

const {
  pageMeta,
  viewClassMap,
  compareGroupDefs,
  modelContent,
  buildSingleFileViewModel,
  formatSignalMetricValue,
  buildSingleDetailHeaders,
  buildSingleDetailCells,
  buildRuntimeCompareGroups,
  buildRuntimeCompareSummary,
  buildCompareSummaryViewModel,
  buildCompareRankingViewModel,
  buildCompareTableViewModel,
  formatExportSetting,
  formatHistoryRetentionDays,
  formatCompareModeLabel,
  formatSceneLabel,
  formatModelTag,
  getCompareDataset,
  formatSigned,
  formatScore,
  getStatusClass,
  getDetailColumns,
  buildDetailHeaders,
  buildDetailCell,
} = AudioQASWebPreview;

function applyCompareSummary(summaryNode, viewModel, mode) {
  if (!summaryNode) return;
  summaryNode.classList.toggle("alt", mode === "base");
  const current = mode === "base" ? viewModel.base : viewModel.free;
  const targetClass = mode === "base" ? ".compare-summary-alt" : ".compare-summary-default";
  const scope = summaryNode.querySelector(targetClass);
  if (!scope) return;
  scope.querySelector(".winner-mark").textContent = current.winnerKey;
  scope.querySelector("strong").textContent = current.title;
  scope.querySelector(".winner-copy span").textContent = current.subline;
  scope.querySelector(".compare-reason").textContent = current.reason;
  const kpiLabels = scope.querySelectorAll(".compare-kpi strong");
  const kpiSpans = scope.querySelectorAll(".compare-kpi span");
  current.kpis.forEach((kpi, index) => {
    if (kpiLabels[index]) kpiLabels[index].textContent = kpi.label;
    if (kpiSpans[index]) {
      kpiSpans[index].textContent = kpi.value;
      kpiSpans[index].className = kpi.className;
    }
  });
}

function applySingleOverview(page, view, options = {}) {
  const {
    titleSelector,
    summarySelector,
    adviceSelector,
    traceSelector,
    summaryTextSelector,
    gridSelector,
    compactFive = false,
  } = options;
  const title = document.querySelector(titleSelector);
  const fileSummary = document.querySelector(summarySelector);
  const advice = document.querySelector(adviceSelector);
  const trace = document.querySelector(traceSelector);
  const heroValue = document.querySelector(`[data-page="${page}"] .score-hero .value`);
  const heroGrade = document.querySelector(`[data-page="${page}"] .score-hero .pill-grade`);
  const summaryText = document.querySelector(summaryTextSelector);
  const grid = document.querySelector(gridSelector);

  if (title) title.textContent = view.fileName;
  if (fileSummary) fileSummary.textContent = view.summary;
  if (advice) advice.textContent = view.adviceText;
  if (trace) trace.textContent = view.traceText;
  if (heroValue && view.hero) {
    heroValue.textContent = view.hero.valueText;
    heroValue.className = `value ${view.hero.valueClass}`;
  }
  if (heroGrade && view.hero) {
    heroGrade.textContent = view.hero.gradeText;
    heroGrade.className = `pill-grade ${view.hero.gradeClass}`;
    heroGrade.setAttribute("style", view.hero.gradeStyle);
  }
  if (summaryText && view.primaryMetric) summaryText.textContent = view.primaryMetric.description;
  if (grid) {
    if (compactFive) {
      grid.classList.toggle("compact-five", view.layoutMode === "compact-five");
    }
    grid.innerHTML = view.modelCards.map((card) => `
      <div class="score-card">
        <div class="label">${card.label || card.key}</div>
        <div class="number ${card.gradeClass}">${card.scoreText}</div>
        <div class="bar"><span style="${card.barStyle}"></span></div>
        <div class="grade ${card.gradeClass}">${card.grade}</div>
        <div class="desc">${card.description}</div>
      </div>
    `).join("");
  }
}

function applySingleMetricCards(page, view) {
  const grid = document.querySelector(`[data-page="${page}"] [data-${page === "eval" ? "eval" : "analysis"}-signal-grid]`);
  if (!grid) return;
  grid.innerHTML = view.signalCards.map((metric) => `
    <div class="metric">
      <div class="label">${metric.label || `${metric.key} · ${metric.unit}`}</div>
      <div class="value ${metric.valueClass}">${metric.valueText}</div>
      <div class="state ${metric.stateClass}">${metric.stateText}</div>
      <div class="desc">${metric.description}</div>
    </div>
  `).join("");
}

function applySingleDetailTable(page, view, modelKey) {
  const tableRoot = document.querySelector(`[data-single-detail-table="${page}"]`);
  if (!tableRoot) return;
  const currentView = state.detailViews[page];
  tableRoot.classList.remove("metrics", "signal", "full");
  tableRoot.classList.add(viewClassMap[currentView] || "metrics");
  const modelTag = tableRoot.querySelector(`[data-single-model-tag="${page}"]`);
  if (modelTag) modelTag.textContent = formatModelTag(view.modelName);
  const theadRow = tableRoot.querySelector("thead tr");
  if (theadRow) {
    theadRow.innerHTML = buildSingleDetailHeaders(page, currentView, modelKey);
  }
  const tbody = tableRoot.querySelector("tbody");
  if (tbody) {
    tbody.innerHTML = `<tr>${buildSingleDetailCells(page, view.detailRow, currentView, modelKey)}</tr>`;
  }
  tableRoot.querySelectorAll("[data-single-detail-view]").forEach((button) => {
    button.classList.toggle("active", button.dataset.singleDetailView === currentView);
  });
}

function createHiddenFileInput(page) {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".wav,.flac,.mp3,.aac,.m4a,.ogg,.mp4,.mov,.mkv,.avi";
  input.style.display = "none";
  input.addEventListener("change", async () => {
    const file = input.files?.[0];
    if (!file) return;
    await evaluateUploadedFile(page, file);
    input.value = "";
  });
  document.body.appendChild(input);
  return input;
}

const fileInputs = {
  eval: createHiddenFileInput("eval"),
  analysis: createHiddenFileInput("analysis"),
};

function createHiddenCompareInput(kind, groupKey) {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".wav,.flac,.mp3,.aac,.m4a,.ogg,.mp4,.mov,.mkv,.avi";
  input.style.display = "none";
  input.addEventListener("change", async () => {
    const file = input.files?.[0];
    if (!file) return;
    runtimeState.compare.groups[kind][groupKey] = file;
    input.value = "";
    const groupCount = Object.keys(runtimeState.compare.groups[kind]).length;
    if (groupCount >= 2 && runtimeState.compare.status[kind] === "empty") {
      runtimeState.compare.status[kind] = "ready";
    }
    render();
  });
  document.body.appendChild(input);
  return input;
}

const compareFileInputs = {
  eval: {},
  analysis: {},
};

function uploadWithProgress(url, body, requestId, onProgress) {
  let hasXHRProgress = false;
  try {
    hasXHRProgress = typeof XMLHttpRequest !== "undefined"
      && new XMLHttpRequest().upload !== undefined
      && XMLHttpRequest.prototype.upload !== undefined;
  } catch { /* not a real browser XHR */ }
  if (!hasXHRProgress) {
    if (onProgress) { onProgress(10); onProgress(50); }
    return fetch(url, { method: "POST", body, headers: { "X-Request-Id": requestId } })
      .then(async (res) => {
        if (!res.ok) {
          const t = typeof res.text === "function" ? await res.text() : String(res.statusText);
          throw new Error(explainUploadError(res.status, t));
        }
        if (onProgress) onProgress(100);
        return res.json();
      });
  }
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.setRequestHeader("X-Request-Id", requestId);
    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable) {
        const pct = Math.round((e.loaded / e.total) * 100);
        onProgress(pct);
      }
    });
    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch (err) {
          reject(new Error(`Invalid JSON response: ${xhr.responseText.substring(0, 200)}`));
        }
      } else {
        let errorPayload = xhr.responseText;
        try {
          errorPayload = JSON.parse(xhr.responseText);
          errorPayload = errorPayload?.detail ?? errorPayload;
        } catch { /* use raw text */ }
        reject(new Error(explainUploadError(xhr.status, errorPayload)));
      }
    });
    xhr.addEventListener("error", () => reject(new Error("Network error")));
    xhr.addEventListener("abort", () => reject(new Error("Upload aborted")));
    xhr.send(body);
  });
}

function setSingleProgress(page, label, width) {
  const single = document.querySelector(`[data-scene-root="${page}"] [data-scene="single"]`);
  const progressLabel = single?.querySelector(".progress-label");
  const progressFill = single?.querySelector(".progress-fill");
  if (progressLabel) progressLabel.textContent = label;
  if (progressFill) progressFill.style.width = width;
}

function explainUploadError(status, bodyText) {
  if (typeof bodyText === "string") {
    try {
      const parsed = JSON.parse(bodyText);
      bodyText = parsed?.detail ?? parsed;
    } catch { /* use raw string below */ }
  }
  if (typeof bodyText === "object" && bodyText !== null) {
    const code = typeof bodyText.code === "string" ? bodyText.code : "";
    const message = typeof bodyText.message === "string" ? bodyText.message : "";
    if (message) {
      if (code === "empty_upload" || code === "empty_audio" || code === "invalid_audio_file") {
        return message;
      }
      if (code === "mono_convert_disabled") {
        return "自动转单声道已关闭，当前文件需要先转单声道后才能评测。";
      }
      if (code === "resample_disabled") {
        return "自动重采样已关闭，当前文件采样率不符合模型要求。";
      }
      if (code === "video_extract_disabled") {
        return "视频自动提取音轨已关闭，当前视频文件无法直接评测。";
      }
      return message;
    }
    bodyText = code || JSON.stringify(bodyText);
  }
  if (bodyText.includes("mono_convert_disabled")) {
    return "自动转单声道已关闭，当前文件需要先转单声道后才能评测。";
  }
  if (bodyText.includes("resample_disabled")) {
    return "自动重采样已关闭，当前文件采样率不符合模型要求。";
  }
  if (bodyText.includes("video_extract_disabled")) {
    return "视频自动提取音轨已关闭，当前视频文件无法直接评测。";
  }
  if (status === 413 || bodyText.includes("File too large")) {
    const match = bodyText.match(/max\s+(\d+MB)/i);
    const sizeHint = match ? match[1] : "当前上传上限";
    return `文件超过当前上传上限（${sizeHint}）。`;
  }
  return `Upload evaluate failed: ${status}`;
}

function markSingleLoading(page, file) {
  runtimeState.single[page] = { file, status: "running", result: null, error: null };
  const requestId = runtimeState.requests[page]?.single;
  setSingleProgress(page, requestId ? `上传中 10% · ${requestId}` : "上传中 10%", "10%");
  renderStatePanels(page);
}

async function evaluateUploadedFile(page, file) {
  const domain = page === "eval" ? "speech" : "mixed";
  const modelKey = state.models[page];
  const requestId = nextRequestId(page, "single");
  runtimeState.requests[page].single = requestId;
  const form = new FormData();
  form.append("domain", domain);
  form.append("model_key", modelKey);
  form.append("include_signal", "true");
  form.append("file", file);

  const sceneRoot = document.querySelector(`[data-scene-root="${page}"]`);
  if (!sceneRoot) return;
  const single = sceneRoot.querySelector('[data-scene="single"]');
  sceneRoot.querySelectorAll(".scenario").forEach((node) => node.classList.toggle("active", node === single));
  state[`${page}Scene`] = "single";
  markSingleLoading(page, file);
  setSingleProgress(page, `上传中 · ${requestId}`, "0%");

  try {
    const payload = await uploadWithProgress("/api/evaluate/upload", form, requestId, (pct) => {
      const label = pct < 100 ? `上传中 ${pct}% · ${requestId}` : `上传完成 · ${requestId}`;
      setSingleProgress(page, label, `${Math.min(pct, 50)}%`);
    });
    if (runtimeState.requests[page].single !== requestId) return;
    setSingleProgress(page, `模型评测中 · ${requestId}`, "55%");
    runtimeState.single[page] = { file, status: "done", result: payload, error: null };
    applySingleEvaluation(page, payload, file.name);
    setSingleProgress(page, page === "eval" ? "评测完成 100%" : "分析完成 100%", "100%");
    const progressPanel = document.querySelector(`[data-scene-root="${page}"] [data-scene="single"] .progress-panel`);
    if (progressPanel) progressPanel.classList.add("done");
    renderStatePanels(page);
  } catch (error) {
    if (runtimeState.requests[page].single !== requestId) return;
    console.error(error);
    runtimeState.single[page] = { file, status: "error", result: null, error: String(error) };
    render();
  }
}

async function evaluateCompareUpload(kind) {
  const domain = kind === "eval" ? "speech" : "mixed";
  const modelKey = state.models[kind];
  const requestId = nextRequestId(kind, "compare");
  runtimeState.requests[kind].compare = requestId;
  const selectedGroups = Object.entries(runtimeState.compare.groups[kind])
    .sort(([a], [b]) => a.localeCompare(b));
  if (selectedGroups.length < 2) return;

  runtimeState.compare.status[kind] = "running";
  render();

  const sceneRoot = document.querySelector(`[data-scene-root="${kind}"]`);
  const compare = sceneRoot?.querySelector('[data-scene="compare"]');
  const progressLabel = compare?.querySelector(".progress-label");
  const progressFill = compare?.querySelector(".progress-fill");
  if (progressLabel) progressLabel.textContent = `上传中 · ${requestId}`;
  if (progressFill) progressFill.style.width = "0%";

  const multipart = new FormData();
  multipart.append("domain", domain);
  multipart.append("model_key", modelKey);
  multipart.append("base_key", state.compare[kind].base || selectedGroups[0][0]);
  multipart.append("include_signal", "true");
  for (const [key, file] of selectedGroups) {
    multipart.append("keys", key);
    multipart.append("files", file);
  }

  try {
    const payload = await uploadWithProgress("/api/evaluate/compare-upload", multipart, requestId, (pct) => {
      const label = pct < 100 ? `上传中 ${pct}% · ${requestId}` : `上传完成 · ${requestId}`;
      if (progressLabel) progressLabel.textContent = label;
      if (progressFill) progressFill.style.width = `${Math.min(pct, 50)}%`;
    });
    if (progressLabel) progressLabel.textContent = `对比处理中 · ${requestId}`;
    if (progressFill) progressFill.style.width = "55%";
    runtimeState.compare.results[kind] = payload;
    runtimeState.compare.status[kind] = "done";
    render();
    renderCompareFromRuntime(kind, payload);
    if (progressLabel) progressLabel.textContent = kind === "eval" ? "对比评测完成 100%" : "对比分析完成 100%";
    if (progressFill) progressFill.style.width = "100%";
    const progressPanel = compare?.querySelector(".progress-panel");
    if (progressPanel) progressPanel.classList.add("done");
  } catch (error) {
    console.error(error);
    runtimeState.compare.status[kind] = "error";
    runtimeState.compare.error[kind] = error instanceof Error ? error.message : String(error);
    render();
  }
}

function setPage(page) {
  state.page = page;
  if (page === "history") {
    loadHistoryItems();
    return;
  }
  render();
}

function setScene(page, scene) {
  state[`${page}Scene`] = scene;
  if (scene === "compare") {
    state.compare[page].mode = runtimeState.settings.compareDefault;
  }
  render();
}

function resetPageState(page) {
  runtimeState.single[page] = { file: null, status: "empty", result: null, error: null };
  runtimeState.compare.results[page] = null;
  runtimeState.compare.groups[page] = {};
  runtimeState.compare.status[page] = "empty";
  runtimeState.compare.error[page] = null;
  runtimeState.requests[page].single = null;
  runtimeState.requests[page].compare = null;
  state.detailViews[page] = "metrics";
  state.compare[page] = { mode: runtimeState.settings.compareDefault, base: "A" };
  compareGroupState[page] = 0;
  state[`${page}Scene`] = "empty";
  render();
}

function nextExportFormat(value) {
  if (value === "json_csv") return "json";
  if (value === "json") return "csv";
  return "json_csv";
}

function nextHistoryRetentionDays(value) {
  if (value === 30) return 90;
  if (value === 90) return 180;
  if (value === 180) return 99999;
  return 30;
}

function applySettingsPayload(payload) {
  state.models.eval = payload.default_eval_model || state.models.eval;
  state.models.analysis = payload.default_analysis_model || state.models.analysis;
  runtimeState.settings.trace = payload.trace ?? runtimeState.settings.trace;
  runtimeState.settings.compareDefault = payload.compare_default || runtimeState.settings.compareDefault;
  runtimeState.settings.preprocessResample = payload.preprocess_resample ?? runtimeState.settings.preprocessResample;
  runtimeState.settings.preprocessToMono = payload.preprocess_to_mono ?? runtimeState.settings.preprocessToMono;
  runtimeState.settings.preprocessExtractAudio = payload.preprocess_extract_audio ?? runtimeState.settings.preprocessExtractAudio;
  runtimeState.settings.exportFormat = payload.export_format || runtimeState.settings.exportFormat;
  runtimeState.settings.historyRetentionDays = payload.history_retention_days ?? runtimeState.settings.historyRetentionDays;
}

function openSingleUploadAction(page) {
  state[`${page}Scene`] = "single";
  render();
  fileInputs[page]?.click();
}

function changeSceneAction(page, scene) {
  setScene(page, scene);
}

function changeCompareModeAction(kind, mode) {
  state.compare[kind].mode = mode;
  render();
}

async function toggleSettingAction(key, isOn) {
  if (key === "trace") runtimeState.settings.trace = isOn;
  if (key === "preprocess-resample") runtimeState.settings.preprocessResample = isOn;
  if (key === "preprocess-to-mono") runtimeState.settings.preprocessToMono = isOn;
  if (key === "preprocess-extract-audio") runtimeState.settings.preprocessExtractAudio = isOn;
  await persistSettings({
    trace: runtimeState.settings.trace,
    preprocess_resample: runtimeState.settings.preprocessResample,
    preprocess_to_mono: runtimeState.settings.preprocessToMono,
    preprocess_extract_audio: runtimeState.settings.preprocessExtractAudio,
  });
}

async function updateCompareDefaultAction() {
  runtimeState.settings.compareDefault = runtimeState.settings.compareDefault === "free" ? "base" : "free";
  ["eval", "analysis"].forEach((kind) => {
    if (state[`${kind}Scene`] === "compare") state.compare[kind].mode = runtimeState.settings.compareDefault;
  });
  await persistSettings({ compare_default: runtimeState.settings.compareDefault });
}

async function updateExportFormatAction() {
  runtimeState.settings.exportFormat = nextExportFormat(runtimeState.settings.exportFormat);
  await persistSettings({ export_format: runtimeState.settings.exportFormat });
}

async function updateHistoryRetentionAction() {
  runtimeState.settings.historyRetentionDays = nextHistoryRetentionDays(runtimeState.settings.historyRetentionDays);
  await persistSettings({ history_retention_days: runtimeState.settings.historyRetentionDays });
}

function applyHistoryFilterAction(filter) {
  runtimeState.history.filter = filter || "all";
  renderHistory();
}

async function showHistoryDetailAction(itemId) {
  await showHistoryDetail(itemId);
}

function exportPageAction(page) {
  downloadExport(page);
}

function resetPageAction(page) {
  resetPageState(page);
}

function switchModelAction(scope, modelKey) {
  const currentModel = state.models[scope];
  if (runtimeState.single[scope].status === "done") {
    resultCache[getCacheKey(scope, "single", currentModel)] = runtimeState.single[scope];
  }
  if (runtimeState.compare.status[scope] === "done") {
    resultCache[getCacheKey(scope, "compare", currentModel)] = {
      results: runtimeState.compare.results[scope],
      groups: runtimeState.compare.groups[scope],
      base: state.compare[scope].base,
      requestId: runtimeState.requests[scope].compare,
    };
  }
  state.models[scope] = modelKey;
  const cachedSingle = resultCache[getCacheKey(scope, "single", modelKey)];
  if (cachedSingle) {
    runtimeState.single[scope] = { ...cachedSingle };
  } else {
    runtimeState.single[scope] = { file: null, status: "empty", result: null, error: null };
  }
  const cachedCompare = resultCache[getCacheKey(scope, "compare", modelKey)];
  if (cachedCompare) {
    runtimeState.compare.results[scope] = cachedCompare.results;
    runtimeState.compare.groups[scope] = cachedCompare.groups;
    state.compare[scope].base = cachedCompare.base;
    runtimeState.requests[scope].compare = cachedCompare.requestId;
    runtimeState.compare.status[scope] = "done";
    runtimeState.compare.error[scope] = null;
  } else {
    runtimeState.compare.results[scope] = null;
    runtimeState.compare.groups[scope] = {};
    runtimeState.compare.status[scope] = "empty";
    runtimeState.compare.error[scope] = null;
    runtimeState.requests[scope].compare = null;
  }
  render();
}

async function toggleDefaultEvalModelAction() {
  state.models.eval = state.models.eval === "dnsmos" ? "nisqa" : "dnsmos";
  await persistSettings({ default_eval_model: state.models.eval });
}

function changeCompareDetailViewAction(kind, view) {
  state.detailViews[kind] = view;
  render();
}

function changeSingleDetailViewAction(kind, view) {
  state.detailViews[kind] = view;
  const single = runtimeState.single[kind];
  if (single?.status === "done" && single.result && single.file) {
    applySingleEvaluation(kind, single.result, single.file.name);
  } else {
    render();
  }
}

function addCompareGroupAction(kind) {
  addCompareGroup(kind);
}

function buildExportPayload(page) {
  const single = runtimeState.single[page];
  if (single?.status === "done" && single.result) {
    return {
      page,
      scene: "single",
      request_id: runtimeState.requests[page].single,
      exported_at: new Date().toISOString(),
      file_name: single.file?.name || null,
      payload: single.result,
    };
  }
  const compare = runtimeState.compare.results[page];
  if (compare) {
    return {
      page,
      scene: "compare",
      request_id: runtimeState.requests[page].compare,
      exported_at: new Date().toISOString(),
      compare_mode: state.compare[page].mode,
      payload: compare,
    };
  }
  return null;
}

function downloadExport(page) {
  const exportPayload = buildExportPayload(page);
  if (!exportPayload) {
    window.alert("当前页面还没有可导出的结果。");
    return;
  }
  const scene = exportPayload.scene;
  const reqId = exportPayload.request_id || "unknown";
  const download = (content, type, ext) => {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `audioqas_${page}_${scene}_${reqId}.${ext}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };
  if (runtimeState.settings.exportFormat === "json" || runtimeState.settings.exportFormat === "json_csv") {
    download(JSON.stringify(exportPayload, null, 2), "application/json", "json");
  }
  if (runtimeState.settings.exportFormat === "csv" || runtimeState.settings.exportFormat === "json_csv") {
    const rows = [
      ["page", page],
      ["scene", scene],
      ["request_id", exportPayload.request_id || ""],
      ["exported_at", exportPayload.exported_at],
    ];
    const csv = rows.map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(",")).join("\n");
    download(csv, "text/csv", "csv");
  }
}

function buildFactRows(lines) {
  return lines.map(([label, text]) => `<div class="fact-row"><strong>${label}</strong><span>${text}</span></div>`).join("");
}

function renderModelContent(scope) {
  const modelKey = state.models[scope];
  const config = modelContent[scope][modelKey];
  const single = document.querySelector(`[data-model-note="${scope}-single"]`);
  const compare = document.querySelector(`[data-model-note="${scope}-compare"]`);
  [single, compare].forEach((card) => {
    if (!card) return;
    card.classList.add("active-model");
    card.innerHTML = `<h4>${config.title}</h4><div class="fact-list">${buildFactRows(config.lines)}</div>`;
  });
  const toolbar = document.querySelector(`[data-toolbar-model="${scope}"]`);
  if (toolbar) toolbar.textContent = config.toolbar;

  const progressModel = document.querySelector(`[data-${scope}-progress-model]`);
  if (progressModel) {
    progressModel.textContent = modelKey === "nisqa" ? "送入 NISQA" : scope === "analysis" ? "送入 AudioBox" : "送入 DNSMOS";
  }

  const signalSingle = document.querySelector(`[data-signal-note="${scope}-single"]`);
  const signalCompare = document.querySelector(`[data-signal-note="${scope}-compare"]`);
  const signalTitle = "信号分析";
  const signalLines = scope === "eval"
    ? [["适用", "通话噪声、回声、响度异常"], ["维度", "频谱、波形、SNR、响度包络"], ["用途", "定位语音退化根因"], ["局限", "需配合 MOS 模型做综合判断"]]
    : [["适用", "音乐频段、混音平衡、响度分布"], ["维度", "频谱、波形、SNR、响度包络"], ["用途", "拆解制作问题、辅助美学评分"], ["局限", "不能替代主观听感"]];
  [signalSingle, signalCompare].forEach((card) => {
    if (!card) return;
    card.classList.add("active-signal");
    card.innerHTML = `<h4>${signalTitle}</h4><div class="fact-list">${buildFactRows(signalLines)}</div>`;
  });
}

function applySingleEvaluation(page, payload, fileName) {
  const view = buildSingleFileViewModel(page, payload, fileName);

  if (page === "eval") {
    applySingleOverview(page, view, {
      titleSelector: '[data-page="eval"] .card-title',
      summarySelector: "[data-eval-file-summary]",
      adviceSelector: "[data-eval-advice]",
      traceSelector: "[data-eval-trace]",
      summaryTextSelector: '[data-page="eval"] .overview-summary p',
      gridSelector: "[data-eval-model-grid]",
      compactFive: true,
    });
  }

  if (page === "analysis") {
    applySingleOverview(page, view, {
      titleSelector: '[data-page="analysis"] .card-title',
      summarySelector: "[data-analysis-file-summary]",
      adviceSelector: "[data-analysis-advice]",
      traceSelector: "[data-analysis-trace]",
      summaryTextSelector: '[data-page="analysis"] .overview-summary p',
      gridSelector: '[data-page="analysis"] .four-col',
    });
  }

  applySingleMetricCards(page, view);
  applySingleDetailTable(page, view, payload.model.model_key);
}

async function loadHistoryItems() {
  runtimeState.history.status = "loading";
  runtimeState.history.error = null;
  try {
    const response = await fetch("/api/history");
    if (!response.ok) {
      throw new Error(`History load failed: ${response.status}`);
    }
    runtimeState.history.items = await response.json();
    runtimeState.history.status = "success";
  } catch (error) {
    console.error(error);
    runtimeState.history.status = "error";
    runtimeState.history.error = error instanceof Error ? error.message : String(error);
  }
  render();
}

async function loadSettings() {
  try {
    const response = await fetch("/api/settings");
    if (!response.ok) {
      throw new Error(`Settings load failed: ${response.status}`);
    }
    const payload = await response.json();
    applySettingsPayload(payload);
    ["eval", "analysis"].forEach((kind) => {
      if (state[`${kind}Scene`] === "compare") {
        state.compare[kind].mode = runtimeState.settings.compareDefault;
      }
    });
  } catch (error) {
    console.error(error);
  }
  render();
}

async function persistSettings(patch) {
  try {
    const response = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    if (!response.ok) {
      throw new Error(`Settings save failed: ${response.status}`);
    }
    const payload = await response.json();
    applySettingsPayload(payload);
  } catch (error) {
    console.error(error);
  }
  render();
}

function getVisibleGroups(kind) {
  const dataset = getCompareDataset(kind, state.models);
  const defs = dataset.groups;
  const builder = document.querySelector(`[data-group-builder="${kind}"]`);
  const count = builder ? builder.querySelectorAll(".group-card").length : 0;
  return defs.slice(0, count);
}

function getVisibleCompareGroupCount(kind) {
  const dataset = getCompareDataset(kind, state.models);
  const readyBuilderCount = document.querySelector(`[data-group-builder="${kind}"]`)?.querySelectorAll(".group-card").length || 0;
  const uploadCardCount = document.querySelectorAll(`[data-compare-upload-group^="${kind}-"]`).length;
  const uploadedKeys = Object.keys(runtimeState.compare.groups[kind] || {});
  const uploadedMaxIndex = uploadedKeys.reduce((maxIndex, key) => {
    const index = dataset.groups.findIndex((group) => group.key === key);
    return Math.max(maxIndex, index);
  }, -1);
  return Math.min(dataset.groups.length, Math.max(readyBuilderCount, uploadCardCount, uploadedMaxIndex + 1));
}

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function renderCompareUploadCards(kind) {
  const groups = runtimeState.compare.groups[kind] || {};
  const groupKeys = Object.keys(groups);

  document.querySelectorAll(`[data-compare-upload-group*="${kind}-"]`).forEach((card) => {
    const key = card.dataset.compareUploadGroup;
    const groupKey = key.replace(kind + "-", "");
    const file = groups[groupKey];
    const statusEl = card.querySelector(`[data-group-status="${key}"]`);
    const hintEl = card.querySelector(".upload-hint");
    const formatEl = card.querySelector(".format-hint");

    if (file) {
      card.classList.add("uploaded");
      if (statusEl) statusEl.textContent = "已选择";
      if (hintEl) {
        const ext = file.name.split(".").pop().toUpperCase();
        hintEl.innerHTML = `<span class="file-summary">${file.name}<span class="file-type-tag">${ext}</span><span class="file-size">${formatFileSize(file.size)}</span></span>`;
      }
      if (formatEl) formatEl.style.display = "none";
    } else {
      card.classList.remove("uploaded");
      if (statusEl) statusEl.textContent = "未上传";
      if (hintEl) hintEl.textContent = "点击上传文件";
      if (formatEl) formatEl.style.display = "";
    }
  });

  const startBtn = document.querySelector(`[data-compare-start="${kind}"]`);
  if (startBtn) {
    const count = groupKeys.length;
    const ready = count >= 2;
    startBtn.classList.toggle("disabled", !ready);
    const hintEl = startBtn.querySelector(".hint");
    if (hintEl) {
      if (ready) {
        hintEl.textContent = `已添加 ${count} 组: ${groupKeys.join("、")}`;
      } else {
        hintEl.textContent = `至少添加 2 组文件后开始对比${kind === "eval" ? "评测" : "分析"}`;
      }
    }
  }
}

function renderSingleUploadCards() {
  ["eval", "analysis"].forEach((page) => {
    const card = document.querySelector(`[data-single-upload-card="${page}"]`);
    if (!card) return;
    const file = runtimeState.single[page]?.file;
    const statusEl = card.querySelector(`[data-single-upload-status="${page}"]`);
    const hintEl = card.querySelector(".upload-hint");
    const formatEl = card.querySelector(".format-hint");
    if (file) {
      card.classList.add("uploaded");
      if (statusEl) statusEl.textContent = "已选择";
      if (hintEl) {
        const ext = file.name.split(".").pop().toUpperCase();
        hintEl.innerHTML = `<span class="file-summary">${file.name}<span class="file-type-tag">${ext}</span><span class="file-size">${formatFileSize(file.size)}</span></span>`;
      }
      if (formatEl) formatEl.style.display = "none";
    } else {
      card.classList.remove("uploaded");
      if (statusEl) statusEl.textContent = "未上传";
      if (hintEl) hintEl.textContent = "点击上传文件";
      if (formatEl) formatEl.style.display = "";
    }
  });
}

function renderCompareBuilder(kind) {
  const builder = document.querySelector(`[data-group-builder="${kind}"]`);
  const baseRow = document.querySelector(`[data-base-root="${kind}"]`);
  const baseRowDone = document.querySelector(`[data-base-root-done="${kind}"]`);
  if (!builder || !baseRow) return;

  const selectedGroups = runtimeState.compare.groups[kind] || {};
  const uploadedKeys = Object.keys(selectedGroups).sort();
  const addButton = builder.querySelector(`[data-add-group="${kind}"]`);
  const visibleCount = getVisibleCompareGroupCount(kind);

  while (builder.querySelectorAll(".group-card").length < visibleCount) {
    const card = document.createElement("div");
    card.className = "group-card";
    builder.insertBefore(card, addButton || null);
  }

  const visibleGroups = getVisibleGroups(kind);
  builder.querySelectorAll(".group-card").forEach((card, index) => {
    const group = visibleGroups[index];
    if (!group) return;
    const selected = selectedGroups[group.key];
    const text = selected ? `${selected.name}<br>本机已选择` : "未上传<br>点击上传文件";
    card.innerHTML = `<strong>${group.key}</strong><span>${text}</span>`;
    card.classList.remove("active", "empty");
    card.classList.toggle("empty", !selected);
    card.onclick = () => {
      compareFileInputs[kind][group.key] ||= createHiddenCompareInput(kind, group.key);
      compareFileInputs[kind][group.key].click();
    };
  });

  function renderBasePills(row) {
    row.innerHTML = "";
    if (uploadedKeys.length === 0) return;
    uploadedKeys.forEach((key) => {
      const pill = document.createElement("button");
      pill.className = "base-pill";
      pill.type = "button";
      pill.textContent = key;
      pill.classList.toggle("active", state.compare[kind].base === key);
      pill.addEventListener("click", () => {
        state.compare[kind].base = key;
        state.compare[kind].mode = "base";
        render();
      });
      row.appendChild(pill);
    });
  }

  renderBasePills(baseRow);
  if (baseRowDone) renderBasePills(baseRowDone);
}

function renderCompareSection(kind) {
  const domain = kind === "analysis" ? "analysis" : "speech";
  const runtimeCompare = runtimeState.compare.results[kind];
  if (runtimeCompare) {
    renderCompareFromRuntime(kind, runtimeCompare);
    return;
  }
  const dataset = getCompareDataset(kind, state.models);
  const visibleGroups = getVisibleGroups(kind);
  const compareState = state.compare[kind];
  if (!visibleGroups.length) return;

  if (!visibleGroups.some((group) => group.key === compareState.base)) {
    compareState.base = visibleGroups[0].key;
  }

  const baseGroup = visibleGroups.find((group) => group.key === compareState.base) || visibleGroups[0];
  const byScore = [...visibleGroups].sort((a, b) => b.score - a.score);
  const bestOverall = byScore[0];
  const byDelta = [...visibleGroups]
    .filter((group) => group.key !== baseGroup.key)
    .map((group) => ({ ...group, delta: group.score - baseGroup.score }))
    .sort((a, b) => b.delta - a.delta);
  const bestDelta = byDelta[0] || { ...baseGroup, delta: 0 };

  const summary = document.querySelector(`[data-compare-summary="${kind}"]`);
  if (summary) {
    const mode = compareState.mode;
    const winner = mode === "base" ? bestDelta : bestOverall;
    const scoreLabel = mode === "base" ? "相对提升" : "总分";
    const scoreValue = mode === "base" ? formatSigned(winner.delta) : formatScore(winner.score);
    const helperLabel = mode === "base" ? "当前基准" : "峰值";
    const helperValue = mode === "base" ? baseGroup.key : winner.peak.toFixed(1);
    const helperClass = mode === "base" ? "status-good" : getStatusClass("peak", winner.peak);
    const domain = kind === "analysis" ? "analysis" : "speech";
    const thirdLabel = kind === "analysis" ? (mode === "base" ? "总分" : "状态") : (mode === "base" ? "总分" : "削波");
    const thirdValue = kind === "analysis"
      ? (mode === "base" ? formatScore(winner.score) : "可优化后交付")
      : (mode === "base" ? formatScore(winner.score) : String(winner.clipping));
    const thirdClass = mode === "base"
      ? getStatusClass("score", winner.score, domain)
      : kind === "analysis"
        ? "status-good"
        : getStatusClass("clipping", winner.clipping);
    const reason = mode === "base"
      ? `相对 ${baseGroup.key}，${winner.file} 的 ${dataset.metricLabel} 提升最明显，且峰值和失真控制更稳。`
      : winner.rationale;
    const subline = mode === "base"
      ? `\`${winner.file}\` 相对基准组 ${baseGroup.key} 提升最明显。`
      : `\`${winner.file}\` 综合表现最稳，适合作为当前首选版本。`;
    const summaryView = buildCompareSummaryViewModel(kind, mode, baseGroup, bestOverall, {
      ...winner,
      delta: winner.delta ?? 0,
      title: `推荐版本 ${winner.key}`,
      subline,
      reason,
      scoreLabel,
      scoreValue,
      helperLabel,
      helperValue,
      helperClass,
      thirdLabel,
      thirdValue,
      thirdClass,
    });
    applyCompareSummary(summary, summaryView, mode);
  }

  const ranking = document.querySelector(`[data-compare-ranking="${kind}"] .ranking-list`);
  if (ranking) {
    const rankingView = buildCompareRankingViewModel(kind, compareState.mode === "base" ? byDelta : byScore, compareState.mode, baseGroup.key);
    ranking.innerHTML = rankingView.map((item, index) => `
      <div class="ranking-card${item.top ? " top" : ""}">
        <div class="ranking-index">#${index + 1}</div>
        <div class="ranking-main">
          <strong>${item.headline}</strong>
          <span>${item.copy}</span>
        </div>
        <div class="ranking-score">
          <strong class="${item.scoreClass}">${item.scoreText}</strong>
          <span>${item.subline}</span>
        </div>
      </div>
    `).join("");
  }

  const tableRoot = document.querySelector(`[data-compare-table="${kind}"]`);
  if (tableRoot) {
    const view = state.detailViews[kind];
    tableRoot.classList.toggle("base", compareState.mode === "base");
    tableRoot.classList.remove("metrics", "signal", "full");
    tableRoot.classList.add(viewClassMap[view] || "metrics");
    const tableView = buildCompareTableViewModel(kind, visibleGroups, view, compareState.mode, state.models, baseGroup.key);
    const tag = tableRoot.querySelector(`[data-base-tag="${kind}"]`);
    if (tag) tag.textContent = tableView.tag;
    const modelTag = tableRoot.querySelector(`[data-compare-model-tag="${kind}"]`);
    if (modelTag) {
      const label = kind === "eval"
        ? (state.models.eval === "nisqa" ? "NISQA" : "DNSMOS")
        : "AudioBox Aesthetics";
      modelTag.textContent = formatModelTag(label);
    }
    const theadRow = tableRoot.querySelector("thead tr");
    if (theadRow) {
      theadRow.innerHTML = tableView.headers;
    }
    const tbody = tableRoot.querySelector("tbody");
    if (tbody) {
      tbody.innerHTML = tableView.tbodyHtml;
    }
  }
}

function renderCompareFromRuntime(kind, payload) {
  const compareState = state.compare[kind];
  const items = buildRuntimeCompareGroups(kind, payload, state.models);
  const sorted = [...items].sort((a, b) => a.rank - b.rank);
  const activeBaseKey = compareState.base || payload.base_key || "A";
  const activeBaseGroup = items.find((item) => item.key === activeBaseKey) || items[0] || null;
  const compareSummary = buildRuntimeCompareSummary(kind, items, compareState.mode, activeBaseKey);
  const best = compareSummary.best;
  const displayItems = items.map((item) => ({
    ...item,
    delta: Number((item.score - (activeBaseGroup?.score ?? 0)).toFixed(2)),
  }));
  const displaySorted = [...displayItems].sort((a, b) => a.rank - b.rank);
  const summary = document.querySelector(`[data-compare-summary="${kind}"]`);
  if (summary && best) {
    const summaryView = buildCompareSummaryViewModel(kind, compareState.mode, activeBaseGroup, sorted[0], best, compareSummary);
    applyCompareSummary(summary, summaryView, compareState.mode);
  }

  const ranking = document.querySelector(`[data-compare-ranking="${kind}"] .ranking-list`);
  if (ranking) {
    const rankingView = buildCompareRankingViewModel(kind, displaySorted, compareState.mode, activeBaseKey);
    ranking.innerHTML = rankingView.map((item, index) => `
      <div class="ranking-card${item.top ? " top" : ""}">
        <div class="ranking-index">#${index + 1}</div>
        <div class="ranking-main">
          <strong>${item.headline}</strong>
          <span>${item.copy}</span>
        </div>
        <div class="ranking-score">
          <strong class="${item.scoreClass}">${item.scoreText}</strong>
          <span>${item.subline}</span>
        </div>
      </div>
    `).join("");
  }

  const tableRoot = document.querySelector(`[data-compare-table="${kind}"]`);
  if (tableRoot) {
    const view = state.detailViews[kind];
    const tableView = buildCompareTableViewModel(kind, displayItems, view, compareState.mode, state.models, activeBaseKey);
    const modelTag = tableRoot.querySelector(`[data-compare-model-tag="${kind}"]`);
    if (modelTag) {
      const label = kind === "eval"
        ? (state.models.eval === "nisqa" ? "NISQA" : "DNSMOS")
        : "AudioBox Aesthetics";
      modelTag.textContent = formatModelTag(label);
    }
    const tag = tableRoot.querySelector(`[data-base-tag="${kind}"]`);
    if (tag) tag.textContent = tableView.tag;
    const theadRow = tableRoot.querySelector("thead tr");
    if (theadRow) {
      theadRow.innerHTML = tableView.headers;
    }
    const tbody = tableRoot.querySelector("tbody");
    if (tbody) {
      tbody.innerHTML = tableView.tbodyHtml;
    }
  }
}

function renderTraceVisibility() {
  document.querySelectorAll("[data-trace-block]").forEach((el) => {
    el.style.display = runtimeState.settings.trace ? "" : "none";
  });
  document.querySelectorAll("[data-history-trace]").forEach((el) => {
    el.style.display = runtimeState.settings.trace ? "" : "none";
  });
}

function renderHistory() {
  const stack = document.querySelector("[data-history-stack]");
  const empty = document.querySelector("[data-history-empty]");
  if (!stack || !empty) return;
  const items = runtimeState.history.items;
  const filteredItems = items.filter((item) => {
    switch (runtimeState.history.filter) {
      case "eval":
        return item.page_key === "eval";
      case "analysis":
        return item.page_key === "analysis";
      case "compare-free":
        return item.scene === "compare" && item.compare_mode === "free";
      case "compare-base":
        return item.scene === "compare" && item.compare_mode === "base";
      default:
        return true;
    }
  });
  const showEmpty = runtimeState.history.status === "success" && items.length === 0;
  empty.style.display = showEmpty ? "" : "none";
  if (showEmpty) {
    stack.innerHTML = "";
    return;
  }
  if (runtimeState.history.status === "error") {
    empty.style.display = "";
    empty.textContent = `历史加载失败：${runtimeState.history.error}`;
    stack.innerHTML = "";
    return;
  }
  if (runtimeState.history.status !== "success") return;
  if (!filteredItems.length) {
    empty.style.display = "";
    empty.textContent = "当前筛选条件下暂无历史任务";
    stack.innerHTML = "";
    return;
  }
  empty.textContent = "暂无历史任务";
  stack.innerHTML = filteredItems.map((item) => `
    <div class="timeline-card">
      <div class="timeline-top">
        <div>
          <h3>${item.timestamp} · ${item.page_title}</h3>
          <p>${item.file_summary} · ${item.model_label} · ${formatSceneLabel(item.scene)}</p>
        </div>
        <button class="small-btn" data-history-detail="${item.id}">查看详情</button>
      </div>
      <div class="timeline-tags">
        ${item.summary_metrics.map((metric) => `<span class="meta-pill">${metric}</span>`).join("")}
        <span class="meta-pill" data-history-trace>预处理: ${item.trace_summary}</span>
      </div>
    </div>
  `).join("");
}

function renderSettings() {
  const evalModel = document.querySelector('[data-setting-value="default-eval-model"]');
  const analysisModel = document.querySelector('[data-setting-value="default-analysis-model"]');
  const traceToggle = document.querySelector('[data-setting-toggle="trace"]');
  const compareDefault = document.querySelector('[data-setting-value="compare-default"]');
  const preprocessResample = document.querySelector('[data-setting-toggle="preprocess-resample"]');
  const preprocessToMono = document.querySelector('[data-setting-toggle="preprocess-to-mono"]');
  const preprocessExtractAudio = document.querySelector('[data-setting-toggle="preprocess-extract-audio"]');
  const exportFormat = document.querySelector('[data-setting-value="export-format"]');
  const historyRetentionDays = document.querySelector('[data-setting-value="history-retention-days"]');
  if (evalModel) evalModel.textContent = state.models.eval === "nisqa" ? "NISQA" : "DNSMOS";
  if (analysisModel) analysisModel.textContent = "AudioBox Aesthetics";
  if (traceToggle) traceToggle.classList.toggle("on", runtimeState.settings.trace);
  if (compareDefault) compareDefault.textContent = formatCompareModeLabel(runtimeState.settings.compareDefault);
  if (preprocessResample) preprocessResample.classList.toggle("on", runtimeState.settings.preprocessResample);
  if (preprocessToMono) preprocessToMono.classList.toggle("on", runtimeState.settings.preprocessToMono);
  if (preprocessExtractAudio) preprocessExtractAudio.classList.toggle("on", runtimeState.settings.preprocessExtractAudio);
  if (exportFormat) exportFormat.textContent = formatExportSetting(runtimeState.settings.exportFormat);
  if (historyRetentionDays) historyRetentionDays.textContent = formatHistoryRetentionDays(runtimeState.settings.historyRetentionDays);
}

async function showHistoryDetail(itemId) {
  try {
    const response = await fetch(`/api/history/${itemId}`);
    if (!response.ok) {
      throw new Error(`History detail failed: ${response.status}`);
    }
    const payload = await response.json();
    const lines = [
      `时间: ${payload.timestamp}`,
      `页面: ${payload.page_title}`,
      formatModelTag(payload.model_label),
      `场景: ${payload.scene}`,
      `文件: ${payload.file_summary}`,
      `追溯: ${payload.trace_summary}`,
    ];
    window.alert(lines.join("\n"));
  } catch (error) {
    console.error(error);
    window.alert(`历史详情加载失败：${error instanceof Error ? error.message : String(error)}`);
  }
}

function renderDetailViews() {
  ["eval", "analysis"].forEach((kind) => {
    const table = document.querySelector(`[data-compare-table="${kind}"]`);
    if (!table) return;
    table.classList.remove("metrics", "signal", "full");
    table.classList.add(viewClassMap[state.detailViews[kind]] || "metrics");
    table.querySelectorAll("[data-detail-view]").forEach((button) => {
      button.classList.toggle("active", button.dataset.detailView === state.detailViews[kind]);
    });
  });
}

function getSceneStatus(page, scene) {
  if (scene === "single") return runtimeState.single[page].status;
  if (scene === "compare") return runtimeState.compare.status[page];
  return "empty";
}

function getActiveSceneName(page) {
  const currentScene = state[`${page}Scene`];
  if (currentScene === "single") {
    const status = getSceneStatus(page, "single");
    return status === "empty" ? "empty" : "single";
  }
  return currentScene;
}

function renderStatePanels(page) {
  const sceneRoot = document.querySelector(`[data-scene-root="${page}"]`);
  if (!sceneRoot) return;

  const singleStatus = getSceneStatus(page, "single");
  const compareStatus = getSceneStatus(page, "compare");
  const activeScene = getActiveSceneName(page);

  const notesRow = sceneRoot.querySelector('[data-notes-row]');
  if (notesRow) notesRow.style.display = activeScene === "compare" ? "none" : "";

  const singleScene = sceneRoot.querySelector('[data-scene="single"]');
  if (singleScene) {
    const progressPanel = singleScene.querySelector(".progress-panel");
    if (progressPanel) {
      progressPanel.style.display = (singleStatus === "running" || singleStatus === "done") ? "" : "none";
      progressPanel.classList.toggle("done", singleStatus === "done");
    }
    const resultArea = singleScene.querySelector('[data-result-area]');
    if (resultArea) resultArea.style.display = singleStatus === "done" ? "" : "none";
    const modelGrid = singleScene.querySelector("[data-eval-model-grid]") || singleScene.querySelector("[data-analysis-model-grid]");
    if (modelGrid) modelGrid.style.display = singleStatus === "done" ? "" : "none";
    const signalGrid = singleScene.querySelector("[data-eval-signal-grid]") || singleScene.querySelector("[data-analysis-signal-grid]");
    if (signalGrid) signalGrid.style.display = singleStatus === "done" ? "" : "none";
    const detailTable = singleScene.querySelector(`[data-single-detail-table="${page}"]`);
    if (detailTable) detailTable.style.display = singleStatus === "done" ? "" : "none";
    const sections = singleScene.querySelectorAll(".section-title");
    sections.forEach((s) => s.style.display = singleStatus === "done" ? "" : "none");
    const errorPanel = singleScene.querySelector('[data-state-panel]');
    if (errorPanel) {
      errorPanel.style.display = singleStatus === "error" ? "" : "none";
      if (singleStatus === "error") {
        const reasonSpan = errorPanel.querySelector('[data-error-reason]');
        if (reasonSpan) reasonSpan.textContent = runtimeState.single[page].error || "未知错误";
      }
    }
  }

  const compareScene = sceneRoot.querySelector('[data-scene="compare"]');
  if (compareScene) {
    const hasPriorResult = compareStatus === "error" && runtimeState.compare.results[page];
    compareScene.querySelectorAll("[data-compare-state]").forEach((panel) => {
      const panelState = panel.dataset.compareState;
      const suffix = panelState.replace(page + "-", "");
      let visible = suffix === compareStatus;
      if (hasPriorResult && suffix === "done") visible = true;
      panel.style.display = visible ? "" : "none";
    });
    const progressPanel = compareScene.querySelector(".progress-panel");
    if (progressPanel) {
      progressPanel.style.display = (compareStatus === "running" || compareStatus === "done") ? "" : "none";
      progressPanel.classList.toggle("done", compareStatus === "done");
    }
    if (compareStatus === "error") {
      const errorReason = compareScene.querySelector('[data-error-reason]');
      if (errorReason) errorReason.textContent = runtimeState.compare.error[page] || "未知错误";
      if (hasPriorResult) {
        const donePanel = compareScene.querySelector(`[data-compare-state="${page}-done"]`);
        const banner = donePanel?.querySelector(`[data-error-banner="${page}-compare"]`);
        if (banner) {
          banner.textContent = `本次对比失败，当前展示仍为上一次完成结果：${runtimeState.compare.error[page] || "未知错误"}`;
          banner.style.display = "";
        }
      }
    } else {
      const donePanel = compareScene.querySelector(`[data-compare-state="${page}-done"]`);
      const banner = donePanel?.querySelector(`[data-error-banner="${page}-compare"]`);
      if (banner) banner.style.display = "none";
    }
  }
}
  function renderModelControls() {
  document.querySelectorAll("[data-model-scope]").forEach((button) => {
    button.classList.toggle("active", state.models[button.dataset.modelScope] === button.dataset.modelKey);
  });
}

function renderPageScaffolding() {
  document.querySelectorAll(".page").forEach((el) => {
    el.classList.toggle("active", el.dataset.page === state.page);
  });

  document.querySelectorAll(".nav-btn").forEach((el) => {
    const target = el.dataset.page;
    el.classList.toggle("active", target === state.page);
  });

  document.querySelectorAll("[data-model-group]").forEach((group) => {
    const kind = group.dataset.modelGroup;
    if (state.page === "eval") group.style.display = kind === "voice" ? "block" : "none";
    else if (state.page === "analysis") group.style.display = kind === "analysis" ? "block" : "none";
    else group.style.display = "none";
  });

  ["eval", "analysis"].forEach((page) => {
    const activeScene = getActiveSceneName(page);
    document.querySelectorAll(`[data-scene-root="${page}"] .scenario`).forEach((el) => {
      el.classList.toggle("active", el.dataset.scene === activeScene);
    });
    const compareBtn = document.querySelector(`[data-compare-btn="${page}"]`);
    if (compareBtn) {
      compareBtn.classList.toggle("active", state[`${page}Scene`] === "compare");
    }
    const singleBtn = document.querySelector(`[data-single-btn="${page}"]`);
    if (singleBtn) {
      singleBtn.classList.toggle("active", state[`${page}Scene`] !== "compare");
    }
    const basePicker = document.querySelector(`[data-base-picker="${page}"]`);
    if (basePicker) {
      basePicker.classList.toggle("active", state.compare[page].mode === "base");
    }
    const basePickerDone = document.querySelector(`[data-base-picker-done="${page}"]`);
    if (basePickerDone) {
      basePickerDone.classList.toggle("active", state.compare[page].mode === "base");
    }
    const modeRoot = document.querySelector(`[data-mode-root="${page}"]`);
    document.querySelectorAll(`[data-mode-root="${page}"]`).forEach((root) => {
      root.querySelectorAll(".mode-chip").forEach((chip) => {
        chip.classList.toggle("active", chip.dataset.compareMode === state.compare[page].mode);
      });
    });
  });

  document.getElementById("page-title").textContent = pageMeta[state.page].title;
  document.getElementById("page-subtitle").textContent = pageMeta[state.page].subtitle;
}

function render() {
  renderPageScaffolding();
  ["eval", "analysis"].forEach((page) => renderStatePanels(page));
  renderModelControls();
  renderModelContent("eval");
  renderModelContent("analysis");
  renderSingleUploadCards();
  renderCompareUploadCards("eval");
  renderCompareUploadCards("analysis");
  renderCompareBuilder("eval");
  renderCompareBuilder("analysis");
  renderCompareSection("eval");
  renderCompareSection("analysis");
  renderDetailViews();
  renderHistory();
  renderSettings();
  renderTraceVisibility();
  animateVisibleProgress();
}

function animateVisibleProgress() {
  document.querySelectorAll(".page.active .scenario.active .progress-fill").forEach((fill) => {
    const panel = fill.closest(".progress-panel");
    if (panel && panel.classList.contains("done")) return;
    const label = panel?.querySelector(".progress-label");
    const styleWidth = fill.style.width || "0%";
    const target = Number.parseInt(styleWidth, 10) || 0;
    fill.style.width = "0%";
    if (label) label.textContent = "0%";
    const duration = 900;
    const start = performance.now();
    function tick(now) {
      const progress = Math.min((now - start) / duration, 1);
      const current = Math.round(target * progress);
      fill.style.width = `${current}%`;
      if (label) label.textContent = `${current}%`;
      if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  });
}

document.querySelectorAll(".nav-btn").forEach((el) => {
  el.addEventListener("click", () => setPage(el.dataset.page));
});

document.querySelectorAll("[data-single-upload-card]").forEach((card) => {
  card.addEventListener("click", () => {
    const kind = card.dataset.singleUploadCard;
    openSingleUploadAction(kind);
  });
});

document.querySelectorAll("[data-scene-trigger]").forEach((button) => {
  button.addEventListener("click", () => {
    const [page, scene] = button.dataset.sceneTrigger.split(":");
    changeSceneAction(page, scene);
  });
});

document.querySelectorAll('[data-compare-btn]').forEach((button) => {
  button.addEventListener("click", () => {
    const page = button.dataset.compareBtn;
    changeSceneAction(page, "compare");
  });
});

document.querySelectorAll("[data-compare-mode]").forEach((button) => {
  button.addEventListener("click", () => {
    changeCompareModeAction(button.dataset.compareKind, button.dataset.compareMode);
  });
});

document.querySelectorAll("[data-setting-toggle]").forEach((toggle) => {
  toggle.addEventListener("click", async () => {
    toggle.classList.toggle("on");
    const key = toggle.dataset.settingToggle;
    await toggleSettingAction(key, toggle.classList.contains("on"));
  });
});

document.querySelector('[data-setting-value="default-eval-model"]')?.addEventListener("click", async () => {
  await toggleDefaultEvalModelAction();
});

document.querySelector('[data-setting-value="compare-default"]')?.addEventListener("click", async (event) => {
  const target = event.currentTarget;
  await updateCompareDefaultAction();
  target.textContent = formatCompareModeLabel(runtimeState.settings.compareDefault);
});

document.querySelector('[data-setting-value="export-format"]')?.addEventListener("click", async (event) => {
  const target = event.currentTarget;
  await updateExportFormatAction();
  target.textContent = formatExportSetting(runtimeState.settings.exportFormat);
});

document.querySelector('[data-setting-value="history-retention-days"]')?.addEventListener("click", async (event) => {
  const target = event.currentTarget;
  await updateHistoryRetentionAction();
  target.textContent = formatHistoryRetentionDays(runtimeState.settings.historyRetentionDays);
});

document.querySelectorAll(".detail-switch").forEach((group) => {
  const table = group.closest("[data-compare-table]");
  const kind = table?.dataset.compareTable;
  group.querySelectorAll("[data-detail-view]").forEach((button) => {
    button.addEventListener("click", () => {
      if (!kind) return;
      changeCompareDetailViewAction(kind, button.dataset.detailView);
    });
  });
});

document.querySelectorAll(".detail-switch").forEach((group) => {
  const table = group.closest("[data-single-detail-table]");
  const kind = table?.dataset.singleDetailTable;
  group.querySelectorAll("[data-single-detail-view]").forEach((button) => {
    button.addEventListener("click", () => {
      if (!kind) return;
      changeSingleDetailViewAction(kind, button.dataset.singleDetailView);
    });
  });
});

document.querySelectorAll(".history-filters").forEach((group) => {
  group.querySelectorAll(".small-btn").forEach((button) => {
    button.addEventListener("click", () => {
      group.querySelectorAll(".small-btn").forEach((node) => node.classList.remove("active"));
      button.classList.add("active");
      applyHistoryFilterAction(button.dataset.historyFilter || "all");
    });
  });
});

document.querySelectorAll("[data-export-trigger]").forEach((button) => {
  button.addEventListener("click", () => {
    exportPageAction(button.dataset.exportTrigger);
  });
});

document.querySelectorAll("[data-reset-trigger]").forEach((button) => {
  button.addEventListener("click", () => {
    resetPageAction(button.dataset.resetTrigger);
  });
});

document.querySelectorAll("[data-model-scope]").forEach((button) => {
  button.addEventListener("click", () => {
    const scope = button.dataset.modelScope;
    switchModelAction(scope, button.dataset.modelKey);
  });
});

document.querySelectorAll("[data-scroll-model-note]").forEach((button) => {
  button.addEventListener("click", () => {
    const targetId = button.dataset.scrollModelNote;
    const note = document.querySelector(`[data-model-note="${targetId}"]`);
    if (!note) return;
    note.scrollIntoView({ behavior: "smooth", block: "center" });
    note.classList.add("pulse-highlight");
    setTimeout(() => note.classList.remove("pulse-highlight"), 2000);
  });
});

document.querySelectorAll("[data-compare-start]").forEach((button) => {
  button.addEventListener("click", () => {
    const kind = button.dataset.compareStart;
    const groupCount = Object.keys(runtimeState.compare.groups[kind]).length;
    if (groupCount >= 2) {
      startCompareAction(kind);
    }
  });
});

document.querySelectorAll("[data-compare-start-ready]").forEach((button) => {
  button.addEventListener("click", () => {
    startCompareAction(button.dataset.compareStartReady);
  });
});

document.querySelectorAll("[data-retry-trigger]").forEach((button) => {
  button.addEventListener("click", () => {
    const [page, scene] = button.dataset.retryTrigger.split(":");
    if (scene === "single") {
      fileInputs[page]?.click();
    } else if (scene === "compare") {
      startCompareAction(page);
    }
  });
});

document.querySelectorAll("[data-compare-upload-group]").forEach((card) => {
  card.addEventListener("click", () => {
    const key = card.dataset.compareUploadGroup;
    const kind = key.startsWith("eval") ? "eval" : "analysis";
    const groupKey = key.replace(kind + "-", "");
    compareFileInputs[kind][groupKey] ||= createHiddenCompareInput(kind, groupKey);
    compareFileInputs[kind][groupKey].click();
  });
});

document.querySelectorAll("[data-compare-add-group]").forEach((button) => {
  button.addEventListener("click", () => {
    const kind = button.dataset.compareAddGroup;
    const defs = compareGroupDefs[kind];
    const nextIndex = compareGroupState[kind];
    if (nextIndex >= defs.length) return;
    const groupKey = defs[nextIndex];
    compareGroupState[kind] += 1;
    const row = document.querySelector(`[data-compare-groups-row="${kind}"]`);
    if (!row) return;
    const card = document.createElement("div");
    card.className = "group-card-upload";
    card.dataset.compareUploadGroup = `${kind}-${groupKey}`;
    card.innerHTML = `
      <div class="group-key">${groupKey}组</div>
      <div class="upload-hint">点击上传文件</div>
      <div class="format-hint">音频 wav/flac/mp3/aac/m4a/ogg · 视频 mp4/mov/mkv/avi（需 ffmpeg）</div>
      <div class="file-status" data-group-status="${kind}-${groupKey}">未上传</div>
    `;
    card.addEventListener("click", () => {
      compareFileInputs[kind][groupKey] ||= createHiddenCompareInput(kind, groupKey);
      compareFileInputs[kind][groupKey].click();
    });
    row.insertBefore(card, button);
    if (compareGroupState[kind] >= defs.length) button.style.display = "none";
  });
});

function startCompareAction(kind) {
  const groupCount = Object.keys(runtimeState.compare.groups[kind]).length;
  if (groupCount < 2) return;
  runtimeState.compare.status[kind] = "running";
  render();
  evaluateCompareUpload(kind);
}

const compareGroupState = {
  eval: 0,
  analysis: 0,
};

function addCompareGroup(kind) {
  const defs = compareGroupDefs[kind];
  const index = compareGroupState[kind];
  if (index >= defs.length) return;
  compareGroupState[kind] += 1;
  const builder = document.querySelector(`[data-group-builder="${kind}"]`);
  const addButton = builder?.querySelector(`[data-add-group="${kind}"]`);
  const dataset = getCompareDataset(kind, state.models);
  if (compareGroupState[kind] >= defs.length && addButton) {
    addButton.style.display = "none";
  }
  const totalCards = builder?.querySelectorAll(".group-card").length || 0;
  if (totalCards < dataset.groups.length) {
    const nextGroup = dataset.groups[totalCards];
    if (nextGroup && addButton) {
      const card = document.createElement("div");
      card.className = "group-card";
      card.innerHTML = `<strong>${nextGroup.key}</strong><span>${nextGroup.inputText}</span>`;
      builder.insertBefore(card, addButton);
    }
  }
  render();
}

document.querySelectorAll("[data-add-group]").forEach((button) => {
  button.addEventListener("click", () => addCompareGroupAction(button.dataset.addGroup));
});

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-history-detail]");
  if (!button) return;
  await showHistoryDetailAction(button.dataset.historyDetail);
});

loadHistoryItems();
loadSettings();
render();

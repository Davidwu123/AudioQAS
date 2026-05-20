const state = {
  page: "eval",
  evalScene: "single",
  analysisScene: "single",
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

const settingsState = {
  trace: true,
  compareDefault: "free",
  preprocessResample: true,
  preprocessToMono: true,
  preprocessExtractAudio: true,
  exportFormat: "json_csv",
  historyRetentionDays: 180,
};

const runtimeState = {
  single: {
    eval: { file: null, status: "idle", result: null, error: null },
    analysis: { file: null, status: "idle", result: null, error: null },
  },
  requests: {
    eval: { single: null, compare: null },
    analysis: { single: null, compare: null },
  },
  history: {
    status: "idle",
    items: [],
    error: null,
    filter: "all",
  },
  compareGroups: {
    eval: {},
    analysis: {},
  },
  compareResults: {
    eval: null,
    analysis: null,
  },
};

let requestCounter = 0;
const initialMarkup = {};

function nextRequestId(page, scene) {
  requestCounter += 1;
  return `req_${page}_${scene}_${String(requestCounter).padStart(4, "0")}`;
}

function rememberInitialMarkup() {
  [
    '[data-page="eval"] [data-scene="single"]',
    '[data-page="eval"] [data-scene="compare"]',
    '[data-page="analysis"] [data-scene="single"]',
    '[data-page="analysis"] [data-scene="compare"]',
  ].forEach((selector) => {
    const node = document.querySelector(selector);
    if (node) initialMarkup[selector] = node.innerHTML;
  });
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
  getCompareDataset,
  formatSigned,
  formatScore,
  getStatusClass,
  getDetailColumns,
  buildDetailHeaders,
  buildDetailCell,
} = AudioQASWebPreview;

function createHiddenFileInput(page) {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".wav,.flac,.mp3,.aac,.ogg,.m4a,.mp4,.mkv,.avi,.mov";
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
  input.accept = ".wav,.flac,.mp3,.aac,.ogg,.m4a,.mp4,.mkv,.avi,.mov";
  input.style.display = "none";
  input.addEventListener("change", async () => {
    const file = input.files?.[0];
    if (!file) return;
    runtimeState.compareGroups[kind][groupKey] = file;
    input.value = "";
    renderCompareBuilder(kind);
    const selected = Object.keys(runtimeState.compareGroups[kind]).length;
    if (selected >= 2) {
      await evaluateCompareUpload(kind);
    }
  });
  document.body.appendChild(input);
  return input;
}

const compareFileInputs = {
  eval: {},
  analysis: {},
};

function setSingleProgress(page, label, width) {
  const single = document.querySelector(`[data-scene-root="${page}"] [data-scene="single"]`);
  const progressLabel = single?.querySelector(".progress-label");
  const progressFill = single?.querySelector(".progress-fill");
  if (progressLabel) progressLabel.textContent = label;
  if (progressFill) progressFill.style.width = width;
}

function explainUploadError(status, bodyText) {
  if (typeof bodyText === "object" && bodyText !== null) {
    const code = typeof bodyText.code === "string" ? bodyText.code : "";
    const message = typeof bodyText.message === "string" ? bodyText.message : "";
    if (message) {
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
  return `Upload evaluate failed: ${status}`;
}

function markSingleLoading(page, file) {
  runtimeState.single[page] = { file, status: "loading", result: null, error: null };
  const requestId = runtimeState.requests[page]?.single;
  setSingleProgress(page, requestId ? `上传中 10% · ${requestId}` : "上传中 10%", "10%");
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
  setSingleProgress(page, `预处理中 25% · ${requestId}`, "25%");

  try {
    const response = await fetch("/api/evaluate/upload", {
      method: "POST",
      body: form,
      headers: {
        "X-Request-Id": requestId,
      },
    });
    setSingleProgress(page, `模型评测中 60% · ${requestId}`, "60%");
    if (!response.ok) {
      let errorPayload = "";
      if (typeof response.json === "function") {
        const json = await response.json();
        errorPayload = json?.detail ?? json;
      } else if (typeof response.text === "function") {
        errorPayload = await response.text();
      }
      throw new Error(explainUploadError(response.status, errorPayload));
    }
    const payload = await response.json();
    setSingleProgress(page, `信号分析中 85% · ${requestId}`, "85%");
    runtimeState.single[page] = { file, status: "success", result: payload, error: null };
    applySingleEvaluation(page, payload, file.name);
    setSingleProgress(page, `100% · ${requestId}`, "100%");
  } catch (error) {
    console.error(error);
    runtimeState.single[page] = { file, status: "error", result: null, error: String(error) };
    setSingleProgress(page, `失败 · ${requestId}`, "0%");
    const detail = error instanceof Error ? error.message : String(error);
    window.alert(`本机评测失败，请确认本地 Python 服务已启动且模型依赖可用。\n\n请求 ID：${requestId}\n页面渲染失败：${detail}`);
  }
}

async function evaluateCompareUpload(kind) {
  const domain = kind === "eval" ? "speech" : "mixed";
  const modelKey = state.models[kind];
  const requestId = nextRequestId(kind, "compare");
  runtimeState.requests[kind].compare = requestId;
  const selectedGroups = Object.entries(runtimeState.compareGroups[kind])
    .sort(([a], [b]) => a.localeCompare(b));
  if (selectedGroups.length < 2) return;

  const sceneRoot = document.querySelector(`[data-scene-root="${kind}"]`);
  const compare = sceneRoot?.querySelector('[data-scene="compare"]');
  sceneRoot?.querySelectorAll(".scenario").forEach((node) => node.classList.toggle("active", node === compare));
  state[`${kind}Scene`] = "compare";

  const progressLabel = compare?.querySelector(".progress-label");
  const progressFill = compare?.querySelector(".progress-fill");
  if (progressLabel) progressLabel.textContent = `对比处理中 · ${requestId}`;
  if (progressFill) progressFill.style.width = "35%";

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
    const response = await fetch("/api/evaluate/compare-upload", {
      method: "POST",
      body: multipart,
      headers: {
        "X-Request-Id": requestId,
      },
    });
    if (!response.ok) {
      throw new Error(`Compare upload failed: ${response.status}`);
    }
    const payload = await response.json();
    runtimeState.compareResults[kind] = payload;
    renderCompareFromRuntime(kind, payload);
    if (progressLabel) progressLabel.textContent = `100% · ${requestId}`;
    if (progressFill) progressFill.style.width = "100%";
  } catch (error) {
    console.error(error);
    if (progressLabel) progressLabel.textContent = `失败 · ${requestId}`;
    if (progressFill) progressFill.style.width = "0%";
    window.alert(`本机对比评测失败，请确认本地 Python 服务已启动且模型依赖可用。\n\n请求 ID：${requestId}`);
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
    state.compare[page].mode = settingsState.compareDefault;
  }
  render();
}

function resetPageState(page) {
  runtimeState.single[page] = { file: null, status: "idle", result: null, error: null };
  runtimeState.compareResults[page] = null;
  runtimeState.compareGroups[page] = {};
  runtimeState.requests[page].single = null;
  runtimeState.requests[page].compare = null;
  state.detailViews[page] = "metrics";
  state.compare[page] = { mode: settingsState.compareDefault, base: "A" };
  compareGroupState[page] = 0;

  const selectors = [
    `[data-page="${page}"] [data-scene="single"]`,
    `[data-page="${page}"] [data-scene="compare"]`,
  ];
  selectors.forEach((selector) => {
    const node = document.querySelector(selector);
    if (node && initialMarkup[selector]) {
      node.innerHTML = initialMarkup[selector];
    }
  });

  state[`${page}Scene`] = "single";
  render();
}

function formatExportSetting(value) {
  if (value === "json") return "JSON";
  if (value === "csv") return "CSV";
  return "CSV + JSON";
}

function nextExportFormat(value) {
  if (value === "json_csv") return "json";
  if (value === "json") return "csv";
  return "json_csv";
}

function formatHistoryRetentionDays(value) {
  return value >= 99999 ? "永久" : `${value} 天`;
}

function nextHistoryRetentionDays(value) {
  if (value === 30) return 90;
  if (value === 90) return 180;
  if (value === 180) return 99999;
  return 30;
}

function buildExportPayload(page) {
  const single = runtimeState.single[page];
  if (single?.status === "success" && single.result) {
    return {
      page,
      scene: "single",
      request_id: runtimeState.requests[page].single,
      exported_at: new Date().toISOString(),
      file_name: single.file?.name || null,
      payload: single.result,
    };
  }
  const compare = runtimeState.compareResults[page];
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
  const download = (content, type, ext) => {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `audioqas_${page}_${scene}.${ext}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };
  if (settingsState.exportFormat === "json" || settingsState.exportFormat === "json_csv") {
    download(JSON.stringify(exportPayload, null, 2), "application/json", "json");
  }
  if (settingsState.exportFormat === "csv" || settingsState.exportFormat === "json_csv") {
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
  const docButton = document.querySelector(`[data-model-doc="${scope}"]`);
  if (docButton) docButton.textContent = config.docLabel;

  if (scope === "eval") {
    if (runtimeState.single.eval.status === "success") {
      return;
    }
    const summary = document.querySelector("[data-eval-file-summary]");
    if (summary) {
      summary.textContent = modelKey === "nisqa"
        ? "45.3s · 48kHz · Stereo · 当前模型 NISQA"
        : "45.3s · 48kHz · Stereo · 当前模型 DNSMOS";
    }
    const trace = document.querySelector("[data-eval-trace]");
    if (trace) {
      trace.textContent = modelKey === "nisqa"
        ? "原始文件 → 转单声道 → 保持 48kHz → 送入 NISQA"
        : "原始文件 → 转单声道 → 重采样到 16kHz → 送入 DNSMOS";
    }
    const progress = document.querySelector("[data-eval-progress-model]");
    if (progress) {
      progress.textContent = modelKey === "nisqa" ? "送入 NISQA" : "送入 DNSMOS";
    }
    const compareTag = document.querySelector('[data-compare-model-tag="eval"]');
    if (compareTag) {
      compareTag.textContent = `模型: ${modelKey === "nisqa" ? "NISQA" : "DNSMOS"}`;
    }
    const compareLabel = document.querySelector('[data-compare-primary-label="eval"]');
    const compareSub = document.querySelector('[data-compare-primary-sub="eval"]');
    if (compareLabel && compareSub) {
      compareLabel.textContent = modelKey === "nisqa" ? "整体质量" : "整体听感";
      compareSub.textContent = "OVRL";
    }
  }
}

function scoreClassFromGrade(grade) {
  const map = {
    Excellent: "status-excellent",
    Good: "status-good",
    Fair: "status-fair",
    Poor: "status-poor",
    Bad: "status-bad",
  };
  return map[grade] || "status-fair";
}

function applySingleEvaluation(page, payload, fileName) {
  const view = buildSingleFileViewModel(page, payload, fileName);

  if (page === "eval") {
    const title = document.querySelector('[data-page="eval"] .card-title');
    const fileSummary = document.querySelector("[data-eval-file-summary]");
    const advice = document.querySelector("[data-eval-advice]");
    const trace = document.querySelector("[data-eval-trace]");
    const heroValue = document.querySelector('[data-page="eval"] .score-hero .value');
    const heroGrade = document.querySelector('[data-page="eval"] .score-hero .pill-grade');
    const summaryText = document.querySelector('[data-page="eval"] .overview-summary p');
    const grid = document.querySelector("[data-eval-model-grid]");

    if (title) title.textContent = view.fileName;
    if (fileSummary) fileSummary.textContent = view.summary;
    if (advice) advice.textContent = view.adviceText;
    if (trace) trace.textContent = view.traceText;

    if (heroValue && view.primaryMetric) {
      heroValue.textContent = Number(view.primaryMetric.score).toFixed(2);
      heroValue.className = `value ${scoreClassFromGrade(view.primaryMetric.grade)}`;
    }
    if (heroGrade && view.primaryMetric) {
      heroGrade.textContent = `${view.primaryMetric.grade} · ${view.primaryMetric.description}`;
      heroGrade.className = `pill-grade ${scoreClassFromGrade(view.primaryMetric.grade)}`;
    }
    if (summaryText && view.primaryMetric) summaryText.textContent = view.primaryMetric.description;
    if (grid) {
      grid.classList.toggle("compact-five", view.layoutMode === "compact-five");
      grid.innerHTML = view.modelCards.map((card) => `
        <div class="score-card">
          <div class="label">${card.key}</div>
          <div class="number ${scoreClassFromGrade(card.grade)}">${Number(card.score).toFixed(2)}</div>
          <div class="bar"><span style="width:${Math.min(Number(card.score) / 5 * 100, 100)}%;background:var(--accent)"></span></div>
          <div class="grade ${scoreClassFromGrade(card.grade)}">${card.grade}</div>
          <div class="desc">${card.description}</div>
        </div>
      `).join("");
    }
  }

  if (page === "analysis") {
    const title = document.querySelector('[data-page="analysis"] .card-title');
    const advice = document.querySelector("[data-analysis-advice]");
    const fileSummary = document.querySelector("[data-analysis-file-summary]");
    const trace = document.querySelector("[data-analysis-trace]");
    const heroValue = document.querySelector('[data-page="analysis"] .score-hero .value');
    const heroGrade = document.querySelector('[data-page="analysis"] .score-hero .pill-grade');
    const summaryText = document.querySelector('[data-page="analysis"] .overview-summary p');
    const grid = document.querySelector('[data-page="analysis"] .four-col');

    if (title) title.textContent = view.fileName;
    if (advice) advice.textContent = view.adviceText;
    if (fileSummary) fileSummary.textContent = view.summary;
    if (trace) trace.textContent = view.traceText;
    if (heroValue && view.primaryMetric) {
      heroValue.textContent = Number(view.primaryMetric.score).toFixed(1);
      heroValue.className = `value ${scoreClassFromGrade(view.primaryMetric.grade)}`;
    }
    if (heroGrade && view.primaryMetric) {
      heroGrade.textContent = `${view.primaryMetric.grade} · ${view.primaryMetric.description}`;
      heroGrade.className = `pill-grade ${scoreClassFromGrade(view.primaryMetric.grade)}`;
    }
    if (summaryText && view.primaryMetric) summaryText.textContent = view.primaryMetric.description;
    if (grid) {
      grid.innerHTML = view.modelCards.map((card) => `
        <div class="score-card">
          <div class="label">${card.key}</div>
          <div class="number ${scoreClassFromGrade(card.grade)}">${Number(card.score).toFixed(1)}</div>
          <div class="bar"><span style="width:${Math.min(Number(card.score) / 10 * 100, 100)}%;background:var(--accent)"></span></div>
          <div class="grade ${scoreClassFromGrade(card.grade)}">${card.grade}</div>
          <div class="desc">${card.description}</div>
        </div>
      `).join("");
    }
  }

  const metricCards = document.querySelectorAll(`[data-page="${page}"] .metric`);
  metricCards.forEach((card, index) => {
    const metric = view.signalCards[index];
    if (!metric) return;
    const label = card.querySelector(".label");
    const value = card.querySelector(".value");
    const stateNode = card.querySelector(".state");
    const desc = card.querySelector(".desc");
    if (label) label.textContent = `${metric.key} · ${metric.unit}`;
    if (value) {
      value.textContent = formatSignalMetricValue(metric);
      value.className = `value ${metric.grade === "Good" ? "status-good" : metric.grade === "Warning" ? "status-warn" : "status-poor"}`;
    }
    if (stateNode) {
      stateNode.textContent = metric.grade;
      stateNode.className = `state ${metric.grade === "Good" ? "status-good" : metric.grade === "Warning" ? "status-warn" : "status-poor"}`;
    }
    if (desc) desc.textContent = metric.description;
  });

  const tableRoot = document.querySelector(`[data-single-detail-table="${page}"]`);
  if (tableRoot) {
    const currentView = state.detailViews[page];
    tableRoot.classList.remove("metrics", "signal", "full");
    tableRoot.classList.add(viewClassMap[currentView] || "metrics");
    const modelTag = tableRoot.querySelector(`[data-single-model-tag="${page}"]`);
    if (modelTag) modelTag.textContent = `模型: ${view.modelName}`;
    const theadRow = tableRoot.querySelector("thead tr");
    if (theadRow) {
      theadRow.innerHTML = buildSingleDetailHeaders(page, currentView, payload.model.model_key);
    }
    const tbody = tableRoot.querySelector("tbody");
    if (tbody) {
      tbody.innerHTML = `<tr>${buildSingleDetailCells(page, view.detailRow, currentView, payload.model.model_key)}</tr>`;
    }
    tableRoot.querySelectorAll("[data-single-detail-view]").forEach((button) => {
      button.classList.toggle("active", button.dataset.singleDetailView === currentView);
    });
  }
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
    state.models.eval = payload.default_eval_model || state.models.eval;
    state.models.analysis = payload.default_analysis_model || state.models.analysis;
    settingsState.trace = payload.trace ?? settingsState.trace;
    settingsState.compareDefault = payload.compare_default || settingsState.compareDefault;
    settingsState.preprocessResample = payload.preprocess_resample ?? settingsState.preprocessResample;
    settingsState.preprocessToMono = payload.preprocess_to_mono ?? settingsState.preprocessToMono;
    settingsState.preprocessExtractAudio = payload.preprocess_extract_audio ?? settingsState.preprocessExtractAudio;
    settingsState.exportFormat = payload.export_format || settingsState.exportFormat;
    settingsState.historyRetentionDays = payload.history_retention_days ?? settingsState.historyRetentionDays;
    ["eval", "analysis"].forEach((kind) => {
      if (state[`${kind}Scene`] === "compare") {
        state.compare[kind].mode = settingsState.compareDefault;
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
    state.models.eval = payload.default_eval_model || state.models.eval;
    state.models.analysis = payload.default_analysis_model || state.models.analysis;
    settingsState.trace = payload.trace ?? settingsState.trace;
    settingsState.compareDefault = payload.compare_default || settingsState.compareDefault;
    settingsState.preprocessResample = payload.preprocess_resample ?? settingsState.preprocessResample;
    settingsState.preprocessToMono = payload.preprocess_to_mono ?? settingsState.preprocessToMono;
    settingsState.preprocessExtractAudio = payload.preprocess_extract_audio ?? settingsState.preprocessExtractAudio;
    settingsState.exportFormat = payload.export_format || settingsState.exportFormat;
    settingsState.historyRetentionDays = payload.history_retention_days ?? settingsState.historyRetentionDays;
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

function renderCompareBuilder(kind) {
  const builder = document.querySelector(`[data-group-builder="${kind}"]`);
  const baseRow = document.querySelector(`[data-base-root="${kind}"]`);
  if (!builder || !baseRow) return;

  const visibleGroups = getVisibleGroups(kind);
  const selectedGroups = runtimeState.compareGroups[kind] || {};
  builder.querySelectorAll(".group-card").forEach((card, index) => {
    const group = visibleGroups[index];
    if (!group) return;
    const selected = selectedGroups[group.key];
    const text = selected ? `${selected.name}<br>本机已选择` : group.inputText;
    card.innerHTML = `<strong>${group.key}</strong><span>${text}</span>`;
    card.classList.remove("active", "empty");
    card.onclick = () => {
      compareFileInputs[kind][group.key] ||= createHiddenCompareInput(kind, group.key);
      compareFileInputs[kind][group.key].click();
    };
  });

  baseRow.innerHTML = "";
  visibleGroups.forEach((group) => {
    const pill = document.createElement("button");
    pill.className = "base-pill";
    pill.type = "button";
    pill.textContent = group.key;
    pill.classList.toggle("active", state.compare[kind].base === group.key);
    pill.addEventListener("click", () => {
      state.compare[kind].base = group.key;
      state.compare[kind].mode = "base";
      render();
    });
    baseRow.appendChild(pill);
  });
}

function renderCompareSection(kind) {
  const domain = kind === "analysis" ? "analysis" : "speech";
  const runtimeCompare = runtimeState.compareResults[kind];
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
    const title = `推荐版本 ${winner.key}`;
    summary.classList.toggle("alt", mode === "base");
    summary.querySelector(".compare-summary-default .winner-mark").textContent = bestOverall.key;
    summary.querySelector(".compare-summary-default strong").textContent = `推荐版本 ${bestOverall.key}`;
    summary.querySelector(".compare-summary-default .winner-copy span").textContent = `\`${bestOverall.file}\` 综合表现最稳，适合作为当前首选版本。`;
    summary.querySelector(".compare-summary-default .compare-reason").textContent = bestOverall.rationale;
    const defaultKpis = summary.querySelectorAll(".compare-summary-default .compare-kpi span");
    defaultKpis[0].textContent = formatScore(bestOverall.score);
    defaultKpis[0].className = getStatusClass("score", bestOverall.score, domain);
    defaultKpis[1].textContent = bestOverall.peak.toFixed(1);
    defaultKpis[1].className = getStatusClass("peak", bestOverall.peak);
    defaultKpis[2].textContent = kind === "analysis" ? "可优化后交付" : String(bestOverall.clipping);
    defaultKpis[2].className = kind === "analysis" ? "status-good" : getStatusClass("clipping", bestOverall.clipping);

    summary.querySelector(".compare-summary-alt .winner-mark").textContent = winner.key;
    summary.querySelector(".compare-summary-alt strong").textContent = title;
    summary.querySelector(".compare-summary-alt .winner-copy span").textContent = subline;
    summary.querySelector(".compare-summary-alt .compare-reason").textContent = reason;
    const altSpans = summary.querySelectorAll(".compare-summary-alt .compare-kpi span");
    const altLabels = summary.querySelectorAll(".compare-summary-alt .compare-kpi strong");
    altLabels[0].textContent = scoreLabel;
    altLabels[1].textContent = helperLabel;
    altLabels[2].textContent = thirdLabel;
    altSpans[0].textContent = scoreValue;
    altSpans[0].className = winner.delta >= 0 ? "status-good" : "status-warn";
    altSpans[1].textContent = helperValue;
    altSpans[1].className = helperClass;
    altSpans[2].textContent = thirdValue;
    altSpans[2].className = thirdClass;
  }

  const ranking = document.querySelector(`[data-compare-ranking="${kind}"] .ranking-list`);
  if (ranking) {
    const mode = compareState.mode;
    const list = mode === "base" ? byDelta : byScore;
    ranking.innerHTML = list.map((group, index) => {
      const top = index === 0 ? " top" : "";
      const main = mode === "base"
        ? `相对基准 ${baseGroup.key} 的综合提升${index === 0 ? "最大" : index === 1 ? "明显" : "仍有收益"}。`
        : group.rationale;
      const sub = mode === "base"
        ? `vs ${baseGroup.key} ${formatSigned(group.delta)}`
        : `综合排序第${index + 1}`;
      const score = formatScore(group.score);
      return `<div class="ranking-card${top}">
        <div class="ranking-index">#${index + 1}</div>
        <div class="ranking-main">
          <strong>${group.key} · ${group.file}</strong>
          <span>${main}</span>
        </div>
        <div class="ranking-score">
          <strong class="${getStatusClass("score", group.score, domain)}">${score}</strong>
          <span>${sub}</span>
        </div>
      </div>`;
    }).join("");
  }

  const tableRoot = document.querySelector(`[data-compare-table="${kind}"]`);
  if (tableRoot) {
    const view = state.detailViews[kind];
    tableRoot.classList.toggle("base", compareState.mode === "base");
    tableRoot.classList.remove("metrics", "signal", "full");
    tableRoot.classList.add(viewClassMap[view] || "metrics");
    const tag = tableRoot.querySelector(`[data-base-tag="${kind}"]`);
    if (tag) tag.textContent = compareState.mode === "base" ? `基准组 ${baseGroup.key}` : "自由对比";
    const modelTag = tableRoot.querySelector(`[data-compare-model-tag="${kind}"]`);
    if (modelTag) {
      const label = kind === "eval"
        ? (state.models.eval === "nisqa" ? "NISQA" : "DNSMOS")
        : "AudioBox Aesthetics";
      modelTag.textContent = `模型: ${label}`;
    }
    const theadRow = tableRoot.querySelector("thead tr");
    if (theadRow) {
      theadRow.innerHTML = buildDetailHeaders(kind, view, compareState.mode, state.models);
    }
    const tbody = tableRoot.querySelector("tbody");
    if (tbody) {
      const columns = getDetailColumns(kind, view, state.models).filter((column) => !column.mode || column.mode === compareState.mode);
      tbody.innerHTML = visibleGroups.map((group) => {
        const delta = group.score - baseGroup.score;
        const rank = byScore.findIndex((item) => item.key === group.key) + 1;
        const ctx = { delta, rank };
        return `<tr>${columns.map((column) => buildDetailCell(column.key, group, ctx)).join("")}</tr>`;
      }).join("");
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
    summary.classList.toggle("alt", compareState.mode === "base");
    summary.querySelector(".compare-summary-default .winner-mark").textContent = best.key;
    summary.querySelector(".compare-summary-default strong").textContent = `推荐版本 ${best.key}`;
    summary.querySelector(".compare-summary-default .winner-copy span").textContent = compareSummary.defaultSubline;
    summary.querySelector(".compare-summary-default .compare-reason").textContent = compareSummary.defaultReason;
    const spans = summary.querySelectorAll(".compare-summary-default .compare-kpi span");
    spans[0].textContent = compareSummary.defaultKpis.score;
    spans[1].textContent = compareSummary.defaultKpis.peak;
    spans[2].textContent = kind === "analysis" ? "可优化后交付" : compareSummary.defaultKpis.clipping;
    summary.querySelector(".compare-summary-alt .winner-mark").textContent = best.key;
    summary.querySelector(".compare-summary-alt strong").textContent = compareSummary.altHeadline;
    summary.querySelector(".compare-summary-alt .winner-copy span").textContent = `\`${best.file}\` vs ${activeBaseKey} ${formatSigned(best.delta)}`;
    summary.querySelector(".compare-summary-alt .compare-reason").textContent = compareSummary.altReason;
    const altSpans = summary.querySelectorAll(".compare-summary-alt .compare-kpi span");
    altSpans[0].textContent = formatSigned(best.delta);
    altSpans[1].textContent = activeBaseKey;
    altSpans[2].textContent = formatScore(best.score);
  }

  const ranking = document.querySelector(`[data-compare-ranking="${kind}"] .ranking-list`);
  if (ranking) {
    ranking.innerHTML = displaySorted.map((item, index) => `
      <div class="ranking-card${index === 0 ? " top" : ""}">
        <div class="ranking-index">#${index + 1}</div>
        <div class="ranking-main">
          <strong>${item.key} · ${item.file}</strong>
          <span>${compareState.mode === "base"
            ? item.delta > 0
              ? "比基准更好"
              : item.delta === 0
                ? "与基准持平"
                : "比基准更差"
            : item.rationale}</span>
        </div>
        <div class="ranking-score">
          <strong class="${getStatusClass("score", item.score, kind === "analysis" ? "analysis" : "speech")}">${formatScore(item.score)}</strong>
          <span>${compareState.mode === "base"
            ? `vs ${activeBaseKey} ${formatSigned(item.score - (activeBaseGroup?.score ?? 0))}`
            : `综合排序第${index + 1}`}</span>
        </div>
      </div>
    `).join("");
  }

  const tableRoot = document.querySelector(`[data-compare-table="${kind}"]`);
  if (tableRoot) {
    const view = state.detailViews[kind];
    const modelTag = tableRoot.querySelector(`[data-compare-model-tag="${kind}"]`);
    if (modelTag) {
      const label = kind === "eval"
        ? (state.models.eval === "nisqa" ? "NISQA" : "DNSMOS")
        : "AudioBox Aesthetics";
      modelTag.textContent = `模型: ${label}`;
    }
    const theadRow = tableRoot.querySelector("thead tr");
    if (theadRow) {
      theadRow.innerHTML = buildDetailHeaders(kind, view, compareState.mode, state.models);
    }
    const tbody = tableRoot.querySelector("tbody");
    if (tbody) {
      tbody.innerHTML = displayItems.map((group) => {
        const columns = getDetailColumns(kind, view, state.models).filter((column) => !column.mode || column.mode === compareState.mode);
        return `<tr>${columns.map((column) => buildDetailCell(column.key, group, { delta: group.delta, rank: group.rank })).join("")}</tr>`;
      }).join("");
    }
  }
}

function renderTraceVisibility() {
  document.querySelectorAll("[data-trace-block]").forEach((el) => {
    el.style.display = settingsState.trace ? "" : "none";
  });
  document.querySelectorAll("[data-history-trace]").forEach((el) => {
    el.style.display = settingsState.trace ? "" : "none";
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
          <p>${item.file_summary} · ${item.model_label} · ${item.scene === "compare" ? "对比" : "单文件"}</p>
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
  if (traceToggle) traceToggle.classList.toggle("on", settingsState.trace);
  if (compareDefault) compareDefault.textContent = settingsState.compareDefault === "free" ? "自由对比" : "基准对比";
  if (preprocessResample) preprocessResample.classList.toggle("on", settingsState.preprocessResample);
  if (preprocessToMono) preprocessToMono.classList.toggle("on", settingsState.preprocessToMono);
  if (preprocessExtractAudio) preprocessExtractAudio.classList.toggle("on", settingsState.preprocessExtractAudio);
  if (exportFormat) exportFormat.textContent = formatExportSetting(settingsState.exportFormat);
  if (historyRetentionDays) historyRetentionDays.textContent = formatHistoryRetentionDays(settingsState.historyRetentionDays);
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
      `模型: ${payload.model_label}`,
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
    const activeScene = state[`${page}Scene`];
    document.querySelectorAll(`[data-scene-root="${page}"] .scenario`).forEach((el) => {
      el.classList.toggle("active", el.dataset.scene === activeScene);
    });
    const compareBtn = document.querySelector(`[data-compare-btn="${page}"]`);
    if (compareBtn) {
      compareBtn.classList.toggle("active", activeScene === "compare");
    }
    const basePicker = document.querySelector(`[data-base-picker="${page}"]`);
    if (basePicker) {
      basePicker.classList.toggle("active", state.compare[page].mode === "base");
    }
    const modeRoot = document.querySelector(`[data-mode-root="${page}"]`);
    if (modeRoot) {
      modeRoot.querySelectorAll(".mode-chip").forEach((chip) => {
        chip.classList.toggle("active", chip.dataset.compareMode === state.compare[page].mode);
      });
    }
  });

  document.getElementById("page-title").textContent = pageMeta[state.page].title;
  document.getElementById("page-subtitle").textContent = pageMeta[state.page].subtitle;
}

function render() {
  renderPageScaffolding();
  renderModelControls();
  renderModelContent("eval");
  renderModelContent("analysis");
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
    const label = fill.closest(".progress-panel").querySelector(".progress-label");
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

document.querySelectorAll('[data-upload-trigger="eval:single"]').forEach((button) => {
  button.addEventListener("click", (event) => {
    event.preventDefault();
    fileInputs.eval.click();
  });
});

document.querySelectorAll('[data-upload-trigger="analysis:single"]').forEach((button) => {
  button.addEventListener("click", (event) => {
    event.preventDefault();
    fileInputs.analysis.click();
  });
});

document.querySelectorAll("[data-scene-trigger]").forEach((button) => {
  button.addEventListener("click", () => {
    const [page, scene] = button.dataset.sceneTrigger.split(":");
    setScene(page, scene);
  });
});

document.querySelectorAll('[data-compare-btn]').forEach((button) => {
  button.addEventListener("click", () => {
    const page = button.dataset.compareBtn;
    setScene(page, "compare");
  });
});

document.querySelectorAll("[data-compare-mode]").forEach((button) => {
  button.addEventListener("click", () => {
    state.compare[button.dataset.compareKind].mode = button.dataset.compareMode;
    render();
  });
});

document.querySelectorAll("[data-setting-toggle]").forEach((toggle) => {
  toggle.addEventListener("click", async () => {
    toggle.classList.toggle("on");
    const key = toggle.dataset.settingToggle;
    if (key === "trace") settingsState.trace = toggle.classList.contains("on");
    if (key === "preprocess-resample") settingsState.preprocessResample = toggle.classList.contains("on");
    if (key === "preprocess-to-mono") settingsState.preprocessToMono = toggle.classList.contains("on");
    if (key === "preprocess-extract-audio") settingsState.preprocessExtractAudio = toggle.classList.contains("on");
    await persistSettings({
      trace: settingsState.trace,
      preprocess_resample: settingsState.preprocessResample,
      preprocess_to_mono: settingsState.preprocessToMono,
      preprocess_extract_audio: settingsState.preprocessExtractAudio,
    });
  });
});

document.querySelector('[data-setting-value="default-eval-model"]')?.addEventListener("click", async () => {
  state.models.eval = state.models.eval === "dnsmos" ? "nisqa" : "dnsmos";
  await persistSettings({ default_eval_model: state.models.eval });
});

document.querySelector('[data-setting-value="compare-default"]')?.addEventListener("click", async (event) => {
  const target = event.currentTarget;
  settingsState.compareDefault = settingsState.compareDefault === "free" ? "base" : "free";
  target.textContent = settingsState.compareDefault === "free" ? "自由对比" : "基准对比";
  ["eval", "analysis"].forEach((kind) => {
    if (state[`${kind}Scene`] === "compare") state.compare[kind].mode = settingsState.compareDefault;
  });
  await persistSettings({ compare_default: settingsState.compareDefault });
});

document.querySelector('[data-setting-value="export-format"]')?.addEventListener("click", async (event) => {
  const target = event.currentTarget;
  settingsState.exportFormat = nextExportFormat(settingsState.exportFormat);
  target.textContent = formatExportSetting(settingsState.exportFormat);
  await persistSettings({ export_format: settingsState.exportFormat });
});

document.querySelector('[data-setting-value="history-retention-days"]')?.addEventListener("click", async (event) => {
  const target = event.currentTarget;
  settingsState.historyRetentionDays = nextHistoryRetentionDays(settingsState.historyRetentionDays);
  target.textContent = formatHistoryRetentionDays(settingsState.historyRetentionDays);
  await persistSettings({ history_retention_days: settingsState.historyRetentionDays });
});

document.querySelectorAll(".detail-switch").forEach((group) => {
  const table = group.closest("[data-compare-table]");
  const kind = table?.dataset.compareTable;
  group.querySelectorAll("[data-detail-view]").forEach((button) => {
    button.addEventListener("click", () => {
      if (!kind) return;
      state.detailViews[kind] = button.dataset.detailView;
      render();
    });
  });
});

document.querySelectorAll(".detail-switch").forEach((group) => {
  const table = group.closest("[data-single-detail-table]");
  const kind = table?.dataset.singleDetailTable;
  group.querySelectorAll("[data-single-detail-view]").forEach((button) => {
    button.addEventListener("click", () => {
      if (!kind) return;
      state.detailViews[kind] = button.dataset.singleDetailView;
      const single = runtimeState.single[kind];
      if (single?.status === "success" && single.result && single.file) {
        applySingleEvaluation(kind, single.result, single.file.name);
      } else {
        render();
      }
    });
  });
});

document.querySelectorAll(".history-filters").forEach((group) => {
  group.querySelectorAll(".small-btn").forEach((button) => {
    button.addEventListener("click", () => {
      group.querySelectorAll(".small-btn").forEach((node) => node.classList.remove("active"));
      button.classList.add("active");
      runtimeState.history.filter = button.dataset.historyFilter || "all";
      renderHistory();
    });
  });
});

document.querySelectorAll("[data-export-trigger]").forEach((button) => {
  button.addEventListener("click", () => {
    downloadExport(button.dataset.exportTrigger);
  });
});

document.querySelectorAll("[data-reset-trigger]").forEach((button) => {
  button.addEventListener("click", () => {
    resetPageState(button.dataset.resetTrigger);
  });
});

document.querySelectorAll("[data-model-scope]").forEach((button) => {
  button.addEventListener("click", () => {
    const scope = button.dataset.modelScope;
    state.models[scope] = button.dataset.modelKey;
    runtimeState.compareGroups[scope === "eval" ? "eval" : "analysis"] = {};
    runtimeState.compareResults[scope === "eval" ? "eval" : "analysis"] = null;
    render();
  });
});

document.querySelectorAll("[data-model-doc]").forEach((button) => {
  button.addEventListener("click", () => {
    const scope = button.dataset.modelDoc;
    const config = modelContent[scope][state.models[scope]];
    const lines = config.lines.map(([label, text]) => `${label}: ${text}`).join("\n");
    window.alert(`${config.title}\n\n${lines}`);
  });
});

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
  button.addEventListener("click", () => addCompareGroup(button.dataset.addGroup));
});

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-history-detail]");
  if (!button) return;
  await showHistoryDetail(button.dataset.historyDetail);
});

rememberInitialMarkup();
loadHistoryItems();
loadSettings();
render();

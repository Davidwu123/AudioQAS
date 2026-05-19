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
};

const runtimeState = {
  single: {
    eval: { file: null, status: "idle", result: null, error: null },
    analysis: { file: null, status: "idle", result: null, error: null },
  },
  history: {
    status: "idle",
    items: [],
    error: null,
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

function markSingleLoading(page, file) {
  runtimeState.single[page] = { file, status: "loading", result: null, error: null };
  setSingleProgress(page, "上传中 10%", "10%");
}

async function evaluateUploadedFile(page, file) {
  const domain = page === "eval" ? "speech" : "mixed";
  const modelKey = state.models[page];
  const form = new FormData();
  form.append("domain", domain);
  form.append("model_key", modelKey);
  form.append("include_signal", "true");
  form.append("file", file);

  const sceneRoot = document.querySelector(`[data-scene-root="${page}"]`);
  if (!sceneRoot) return;
  const single = sceneRoot.querySelector('[data-scene="single"]');
  sceneRoot.querySelectorAll(".scenario").forEach((node) => node.classList.toggle("active", node === single));
  markSingleLoading(page, file);
  setSingleProgress(page, "预处理中 25%", "25%");

  try {
    const response = await fetch("/api/evaluate/upload", {
      method: "POST",
      body: form,
    });
    setSingleProgress(page, "模型评测中 60%", "60%");
    if (!response.ok) {
      throw new Error(`Upload evaluate failed: ${response.status}`);
    }
    const payload = await response.json();
    setSingleProgress(page, "信号分析中 85%", "85%");
    runtimeState.single[page] = { file, status: "success", result: payload, error: null };
    applySingleEvaluation(page, payload, file.name);
    setSingleProgress(page, "100%", "100%");
  } catch (error) {
    console.error(error);
    runtimeState.single[page] = { file, status: "error", result: null, error: String(error) };
    setSingleProgress(page, "失败", "0%");
    const detail = error instanceof Error ? error.message : String(error);
    window.alert(`本机评测失败，请确认本地 Python 服务已启动且模型依赖可用。\n\n页面渲染失败：${detail}`);
  }
}

async function evaluateCompareUpload(kind) {
  const domain = kind === "eval" ? "speech" : "mixed";
  const modelKey = state.models[kind];
  const selectedGroups = Object.entries(runtimeState.compareGroups[kind])
    .sort(([a], [b]) => a.localeCompare(b));
  if (selectedGroups.length < 2) return;

  const sceneRoot = document.querySelector(`[data-scene-root="${kind}"]`);
  const compare = sceneRoot?.querySelector('[data-scene="compare"]');
  sceneRoot?.querySelectorAll(".scenario").forEach((node) => node.classList.toggle("active", node === compare));

  const progressLabel = compare?.querySelector(".progress-label");
  const progressFill = compare?.querySelector(".progress-fill");
  if (progressLabel) progressLabel.textContent = "对比处理中";
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
    });
    if (!response.ok) {
      throw new Error(`Compare upload failed: ${response.status}`);
    }
    const payload = await response.json();
    runtimeState.compareResults[kind] = payload;
    renderCompareFromRuntime(kind, payload);
    if (progressLabel) progressLabel.textContent = "100%";
    if (progressFill) progressFill.style.width = "100%";
  } catch (error) {
    console.error(error);
    if (progressLabel) progressLabel.textContent = "失败";
    if (progressFill) progressFill.style.width = "0%";
    window.alert("本机对比评测失败，请确认本地 Python 服务已启动且模型依赖可用。");
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
      compareSub.textContent = modelKey === "nisqa" ? "MOS" : "OVRL";
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
  builder.querySelectorAll(".group-card").forEach((card, index) => {
    const group = visibleGroups[index];
    if (!group) return;
    const selected = runtimeState.compareGroups[kind][group.key];
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
    const thirdLabel = kind === "analysis" ? (mode === "base" ? "总分" : "状态") : (mode === "base" ? "总分" : "削波");
    const thirdValue = kind === "analysis"
      ? (mode === "base" ? formatScore(winner.score) : "可优化后交付")
      : (mode === "base" ? formatScore(winner.score) : String(winner.clipping));
    const thirdClass = mode === "base"
      ? getStatusClass("score", winner.score)
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
    defaultKpis[0].className = getStatusClass("score", bestOverall.score);
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
          <strong class="${getStatusClass("score", group.score)}">${score}</strong>
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
  const summary = document.querySelector(`[data-compare-summary="${kind}"]`);
  if (summary && best) {
    summary.querySelector(".compare-summary-default .winner-mark").textContent = best.key;
    summary.querySelector(".compare-summary-default strong").textContent = `推荐版本 ${best.key}`;
    summary.querySelector(".compare-summary-default .winner-copy span").textContent = compareSummary.defaultSubline;
    summary.querySelector(".compare-summary-default .compare-reason").textContent = compareSummary.defaultReason;
    const spans = summary.querySelectorAll(".compare-summary-default .compare-kpi span");
    spans[0].textContent = compareSummary.defaultKpis.score;
    spans[1].textContent = compareSummary.defaultKpis.peak;
    spans[2].textContent = kind === "analysis" ? "可优化后交付" : compareSummary.defaultKpis.clipping;
    summary.querySelector(".compare-summary-alt .winner-mark").textContent = best.key;
    summary.querySelector(".compare-summary-alt strong").textContent = `推荐版本 ${best.key}`;
    summary.querySelector(".compare-summary-alt .winner-copy span").textContent = `\`${best.file}\` 相对基准 ${activeBaseKey} 提升最明显。`;
    summary.querySelector(".compare-summary-alt .compare-reason").textContent = compareSummary.altReason;
    const altSpans = summary.querySelectorAll(".compare-summary-alt .compare-kpi span");
    altSpans[0].textContent = formatSigned(best.delta);
    altSpans[1].textContent = activeBaseKey;
    altSpans[2].textContent = formatScore(best.score);
  }

  const ranking = document.querySelector(`[data-compare-ranking="${kind}"] .ranking-list`);
  if (ranking) {
    ranking.innerHTML = sorted.map((item, index) => `
      <div class="ranking-card${index === 0 ? " top" : ""}">
        <div class="ranking-index">#${index + 1}</div>
        <div class="ranking-main">
          <strong>${item.key} · ${item.file}</strong>
          <span>${item.rationale}</span>
        </div>
        <div class="ranking-score">
          <strong class="${getStatusClass("score", item.score)}">${formatScore(item.score)}</strong>
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
      tbody.innerHTML = items.map((group) => {
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
  stack.innerHTML = items.map((item) => `
    <div class="timeline-card">
      <div class="timeline-top">
        <div>
          <h3>${item.timestamp} · ${item.page_title}</h3>
          <p>${item.file_summary} · ${item.model_label} · ${item.scene === "compare" ? "对比" : "单文件"}</p>
        </div>
        <button class="small-btn">查看详情</button>
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
  if (evalModel) evalModel.textContent = state.models.eval === "nisqa" ? "NISQA" : "DNSMOS";
  if (analysisModel) analysisModel.textContent = "AudioBox Aesthetics";
  if (traceToggle) traceToggle.classList.toggle("on", settingsState.trace);
  if (compareDefault) compareDefault.textContent = settingsState.compareDefault === "free" ? "自由对比" : "基准对比";
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
    const target = Number(fill.dataset.target || "100");
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
    if (scene === "single") return;
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
    await persistSettings({ trace: settingsState.trace });
  });
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
    });
  });
});

document.querySelectorAll("[data-model-scope]").forEach((button) => {
  button.addEventListener("click", () => {
    state.models[button.dataset.modelScope] = button.dataset.modelKey;
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

loadHistoryItems();
loadSettings();
render();

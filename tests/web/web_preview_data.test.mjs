import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import preview from "../../audioqas/web/static/web-preview-data.js";

test("shared compare datasets cover all expected models", () => {
  assert.ok(preview.compareData.eval.dnsmos);
  assert.ok(preview.compareData.eval.nisqa);
  assert.ok(preview.compareData.analysis);
});

test("all compare groups expose required business fields", () => {
  const required = ["key", "file", "inputText", "score", "lufs", "lra", "peak", "clipping", "thd", "pipeline", "decision", "rationale"];
  const datasets = [
    preview.compareData.eval.dnsmos.groups,
    preview.compareData.eval.nisqa.groups,
    preview.compareData.analysis.groups,
  ];
  for (const groups of datasets) {
    assert.equal(groups.length, 6);
    for (const group of groups) {
      for (const field of required) {
        assert.notEqual(group[field], undefined, `${group.key} missing ${field}`);
      }
    }
  }
});

test("dnsmos and nisqa produce different compare results", () => {
  const dnsmos = preview.getCompareDataset("eval", { eval: "dnsmos", analysis: "audiobox" });
  const nisqa = preview.getCompareDataset("eval", { eval: "nisqa", analysis: "audiobox" });
  assert.notEqual(dnsmos.modelName, nisqa.modelName);
  assert.notEqual(dnsmos.groups[0].pipeline, nisqa.groups[0].pipeline);
  assert.notEqual(dnsmos.groups[2].score, nisqa.groups[2].score);
});

test("metrics columns switch to nisqa-specific labels", () => {
  const columns = preview.getDetailColumns("eval", "metrics", { eval: "nisqa", analysis: "audiobox" });
  assert.deepEqual(
    columns.map((item) => item.sub),
    ["Group", "File", "OVRL", "NOI", "DIS", "COL", "LOUD", "Rank"],
  );
});

test("signal/detail/full views show different business columns", () => {
  const metrics = preview.getDetailColumns("analysis", "metrics", { eval: "dnsmos", analysis: "audiobox" }).map((item) => item.key);
  const signal = preview.getDetailColumns("analysis", "signal", { eval: "dnsmos", analysis: "audiobox" }).map((item) => item.key);
  const full = preview.getDetailColumns("analysis", "full", { eval: "dnsmos", analysis: "audiobox" }).map((item) => item.key);

  assert.ok(metrics.includes("ce"));
  assert.ok(metrics.includes("pc"));
  assert.ok(!metrics.includes("pipeline"));

  assert.ok(signal.includes("stereo"));
  assert.ok(signal.includes("lra"));
  assert.ok(!signal.includes("decision"));

  assert.ok(full.includes("pipeline"));
  assert.ok(full.includes("decision"));
});

test("detail header rendering respects compare mode", () => {
  const freeHeaders = preview.buildDetailHeaders("eval", "full", "free", { eval: "dnsmos", analysis: "audiobox" });
  const baseHeaders = preview.buildDetailHeaders("eval", "full", "base", { eval: "dnsmos", analysis: "audiobox" });
  assert.match(freeHeaders, /Decision/);
  assert.doesNotMatch(freeHeaders, /Delta/);
  assert.match(baseHeaders, /Delta/);
  assert.doesNotMatch(baseHeaders, /Decision/);
});

test("detail cells format numeric business values as expected", () => {
  const group = preview.compareData.analysis.groups[2];
  const rankCell = preview.buildDetailCell("rank", group, { delta: 2.6, rank: 1 });
  const deltaCell = preview.buildDetailCell("delta", group, { delta: 2.6, rank: 1 });
  const thdCell = preview.buildDetailCell("thd", group, { delta: 2.6, rank: 1 });

  assert.match(rankCell, /#1/);
  assert.match(deltaCell, /\+2\.60/);
  assert.match(thdCell, /0\.4%/);
});

test("html references external data/app scripts", () => {
  const html = fs.readFileSync(new URL("../../audioqas/web/static/web-preview.html", import.meta.url), "utf8");
  assert.match(html, /location\.protocol === "file:" \? "\." : "\/static-preview"/);
  assert.match(html, /web-preview-data\.js\?v=/);
  assert.match(html, /web-preview-app\.js\?v=/);
});

test("html exposes explicit single-file entry without batch upload triggers", () => {
  const html = fs.readFileSync(new URL("../../audioqas/web/static/web-preview.html", import.meta.url), "utf8");
  assert.match(html, /data-scene-trigger="eval:single"[^>]*>单文件测评</);
  assert.match(html, /data-scene-trigger="analysis:single"[^>]*>单文件分析</);
  assert.match(html, /data-scene-trigger="eval:compare"[^>]*>对比评测</);
  assert.match(html, /data-scene-trigger="analysis:compare"[^>]*>对比分析</);
  assert.doesNotMatch(html, /data-upload-trigger="eval:batch"/);
  assert.doesNotMatch(html, /data-upload-trigger="analysis:batch"/);
  assert.doesNotMatch(html, /\+ 添加文件/);
});

test("speech single-file mapping keeps dnsmos primary dimensions", () => {
  const payload = {
    domain: "speech",
    model: {
      model_key: "dnsmos",
      result: {
        model_name: "DNSMOS",
        grade: "Good",
        duration: 12.3,
        original_sr: 16000,
        original_channels: 1,
        preprocessed: true,
        preprocessed_path: "/tmp/a.wav",
        dimensions: {
          OVRL: { score: 3.8, grade: "Good", description: "ok" },
          SIG: { score: 4.1, grade: "Good", description: "clear" },
          BAK: { score: 3.2, grade: "Fair", description: "noise" },
        },
      },
    },
    signal: {
      metrics: {
        LUFS: { value: -15.6, unit: "LUFS", grade: "Warning", description: "响度偏轻或偏响" },
        LRA: { value: 6.4, unit: "LU", grade: "Good", description: "动态范围合理" },
        TruePeak: { value: -0.2, unit: "dBTP", grade: "Warning", description: "峰值接近上限" },
      },
    },
  };

  const view = preview.buildSingleFileViewModel("eval", payload, "demo.wav");
  assert.equal(view.fileName, "demo.wav");
  assert.equal(view.primaryMetric.key, "OVRL");
  assert.deepEqual(view.modelCards.map((card) => card.key), ["OVRL", "SIG", "BAK", "advice"]);
  assert.equal(view.layoutMode, "default");
  assert.equal(view.adviceText, "建议先整理峰值和响度，再复评。");
  assert.equal(view.detailRow.file, "demo.wav");
  assert.equal(view.traceText, "原始文件 → 重采样到 16kHz → 送入 DNSMOS");
  assert.equal(view.hero.valueText, "3.80");
  assert.equal(view.hero.gradeClass, "status-good");
  assert.match(view.modelCards[0].barStyle, /var\(--good\)/);
  assert.deepEqual(
    view.modelCards.map((card) => card.label),
    ["整体听感 · OVRL", "语音清晰度 · SIG", "背景干净度 · BAK", "处理建议"],
  );
  assert.deepEqual(
    view.signalCards.map((card) => card.label),
    ["综合响度 · LUFS", "响度范围 · LRA", "真实峰值 · True Peak"],
  );
  assert.equal(view.signalCards[0].stateText, "需关注");
});

test("speech single-file mapping keeps full nisqa dimensions", () => {
  const payload = {
    domain: "speech",
    model: {
      model_key: "nisqa",
      result: {
        model_name: "NISQA",
        grade: "Good",
        duration: 10.1,
        original_sr: 48000,
        original_channels: 1,
        preprocessed: false,
        preprocessed_path: "",
        dimensions: {
          OVRL: { score: 4.0, grade: "Good", description: "overall" },
          NOI: { score: 3.9, grade: "Good", description: "noise" },
          DIS: { score: 4.1, grade: "Good", description: "continuity" },
          COL: { score: 3.8, grade: "Fair", description: "coloration" },
          LOUD: { score: 4.2, grade: "Good", description: "loudness" },
        },
      },
    },
    signal: null,
  };

  const view = preview.buildSingleFileViewModel("eval", payload, "nisqa.wav");
  assert.deepEqual(view.modelCards.map((card) => card.key), ["OVRL", "NOI", "DIS", "COL", "LOUD"]);
  assert.equal(view.layoutMode, "compact-five");
  assert.ok(view.adviceText);
});

test("analysis single-file mapping includes summary trace and detail row", () => {
  const payload = {
    domain: "mixed",
    model: {
      model_key: "audiobox",
      result: {
        model_name: "AudioBox Aesthetics",
        grade: "Good",
        duration: 31.2,
        original_sr: 48000,
        original_channels: 1,
        preprocessed: false,
        preprocessed_path: "",
        dimensions: {
          PQ: { score: 7.8, grade: "Good", description: "制作完成度高" },
          CE: { score: 7.1, grade: "Good", description: "内容节奏完整" },
          CU: { score: 8.5, grade: "Excellent", description: "信息有效" },
          PC: { score: 5.9, grade: "Fair", description: "仍有精修空间" },
        },
      },
    },
    signal: {
      metrics: {
        LUFS: { value: -14.2, unit: "LUFS", grade: "Warning", description: "响度偏高" },
        LRA: { value: 9.4, unit: "LU", grade: "Good", description: "动态稳定" },
        TruePeak: { value: -0.3, unit: "dBTP", grade: "Warning", description: "峰值接近上限" },
        Clipping: { value: 0, unit: "次", grade: "Good", description: "无削波" },
        THD: { value: 0.4, unit: "%", grade: "Good", description: "失真较低" },
      },
    },
  };

  const view = preview.buildSingleFileViewModel("analysis", payload, "mix.mov");
  assert.equal(view.summary, "31.2s · 48000Hz · Mono · 当前模型 AudioBox Aesthetics");
  assert.equal(view.traceText, "原始文件 → 保持 48kHz → 送入 AudioBox Aesthetics");
  assert.equal(view.detailRow.file, "mix.mov");
  assert.equal(view.detailRow.score, 7.8);
  assert.equal(view.hero.valueText, "7.8");
  assert.equal(view.modelCards[2].gradeClass, "status-excellent");
  assert.equal(view.signalCards[0].stateClass, "status-warn");
  assert.deepEqual(
    view.modelCards.map((card) => card.label),
    ["制作质量 · PQ", "内容享受 · CE", "内容有用 · CU", "制作复杂度 · PC"],
  );
  assert.equal(view.signalCards[2].description, "峰值接近上限，建议再留 0.7 dBTP 余量。");
});

test("trace text expands speech model preprocessing steps", () => {
  const dnsmosTrace = preview.buildTraceText({
    file_path: "clip.wav",
    model_name: "DNSMOS",
    original_sr: 48000,
    original_channels: 2,
  });
  const nisqaTrace = preview.buildTraceText({
    file_path: "room.mov",
    model_name: "NISQA",
    original_sr: 48000,
    original_channels: 1,
  });

  assert.equal(dnsmosTrace, "原始文件 → 转单声道 → 重采样到 16kHz → 送入 DNSMOS");
  assert.equal(nisqaTrace, "原始视频 → 抽取音轨 → 保持 48kHz → 送入 NISQA");
});

test("trace text prefers backend pipeline steps over inferred defaults", () => {
  const trace = preview.buildTraceText({
    file_path: "clip.wav",
    model_name: "DNSMOS",
    original_sr: 48000,
    original_channels: 2,
    pipeline_steps: ["source_audio"],
  });

  assert.equal(trace, "原始文件 → 送入 DNSMOS");
});

test("trace text shows disabled preprocess hints when backend skipped auto steps", () => {
  const trace = preview.buildTraceText({
    file_path: "clip.wav",
    model_name: "DNSMOS",
    pipeline_steps: ["source_audio"],
    preprocess_settings: {
      resample: false,
      to_mono: false,
      extract_audio: true,
    },
  });

  assert.match(trace, /已关闭自动转单声道/);
  assert.match(trace, /已关闭自动重采样/);
});

test("signal metric formatting trims raw floating point noise", () => {
  assert.equal(preview.formatSignalMetricValue({ key: "LUFS", value: -18.945531254, unit: "LUFS" }), "-18.9");
  assert.equal(preview.formatSignalMetricValue({ key: "TruePeak", value: -0.345531254, unit: "dBTP" }), "-0.3");
  assert.equal(preview.formatSignalMetricValue({ key: "THD", value: 0.4235531254, unit: "%" }), "0.4%");
  assert.equal(preview.formatSignalMetricValue({ key: "Clipping", value: 3, unit: "次" }), "3");
});

test("runtime compare groups keep detailed pipeline and formatted metrics", () => {
  const payload = {
    base_key: "A",
    items: [
      {
        key: "A",
        rank: 2,
        delta_from_base: 0,
        file_path: "/tmp/a.wav",
        task: {
          model: {
            model_key: "dnsmos",
            result: {
              model_name: "DNSMOS",
              file_path: "a.wav",
              original_sr: 48000,
              original_channels: 2,
              dimensions: {
                OVRL: { score: 3.2, grade: "Fair", description: "ok" },
                SIG: { score: 3.8, grade: "Good", description: "clear" },
                BAK: { score: 2.8, grade: "Fair", description: "noise" },
              },
            },
          },
          signal: {
            metrics: {
              LUFS: { value: -14.8, unit: "LUFS", grade: "Warning", description: "偏高" },
              LRA: { value: 8.2, unit: "LU", grade: "Good", description: "稳定" },
              TruePeak: { value: -0.3, unit: "dBTP", grade: "Warning", description: "接近上限" },
              Clipping: { value: 0, unit: "次", grade: "Good", description: "无削波" },
              THD: { value: 0.5, unit: "%", grade: "Good", description: "失真低" },
            },
          },
        },
      },
      {
        key: "B",
        rank: 1,
        delta_from_base: 0.6,
        file_path: "/tmp/b.wav",
        task: {
          model: {
            model_key: "dnsmos",
            result: {
              model_name: "DNSMOS",
              file_path: "b.wav",
              original_sr: 48000,
              original_channels: 1,
              dimensions: {
                OVRL: { score: 3.8, grade: "Good", description: "better" },
                SIG: { score: 4.1, grade: "Good", description: "clear" },
                BAK: { score: 3.6, grade: "Good", description: "clean" },
              },
            },
          },
          signal: {
            metrics: {
              LUFS: { value: -15.2, unit: "LUFS", grade: "Good", description: "适中" },
              LRA: { value: 7.8, unit: "LU", grade: "Good", description: "稳定" },
              TruePeak: { value: -1.1, unit: "dBTP", grade: "Good", description: "安全" },
              Clipping: { value: 0, unit: "次", grade: "Good", description: "无削波" },
              THD: { value: 0.4, unit: "%", grade: "Good", description: "失真低" },
            },
          },
        },
      },
    ],
  };

  const groups = preview.buildRuntimeCompareGroups("eval", payload, { eval: "dnsmos", analysis: "audiobox" });
  assert.equal(groups[0].pipeline, "原始文件 → 转单声道 → 重采样到 16kHz → 送入 DNSMOS");
  assert.equal(groups[1].pipeline, "原始文件 → 重采样到 16kHz → 送入 DNSMOS");
  assert.equal(groups[1].lufs, -15.2);
  assert.equal(groups[1].peak, -1.1);
});

test("runtime compare groups keep nisqa loudness dimension", () => {
  const payload = {
    base_key: "A",
    items: [
      {
        key: "A",
        rank: 1,
        delta_from_base: 0,
        file_path: "/tmp/a.wav",
        task: {
          model: {
            model_key: "nisqa",
            result: {
              model_name: "NISQA",
              file_path: "a.wav",
              original_sr: 48000,
              original_channels: 1,
              dimensions: {
                OVRL: { score: 3.9, grade: "Good", description: "overall" },
                NOI: { score: 3.5, grade: "Fair", description: "noise" },
                DIS: { score: 4.0, grade: "Good", description: "continuity" },
                COL: { score: 3.7, grade: "Fair", description: "coloration" },
                LOUD: { score: 4.2, grade: "Good", description: "loudness" },
              },
            },
          },
          signal: null,
        },
      },
    ],
  };

  const groups = preview.buildRuntimeCompareGroups("eval", payload, { eval: "nisqa", analysis: "audiobox" });
  assert.equal(groups[0].loud, 4.2);
});

test("runtime compare summary uses product copy instead of technical placeholder", () => {
  const groups = [
    {
      key: "A",
      file: "a.wav",
      score: 3.2,
      peak: -0.3,
      clipping: 0,
      delta: 0,
      rationale: "作为原始样本保留对照价值。",
      rank: 2,
    },
    {
      key: "B",
      file: "b.wav",
      score: 3.8,
      peak: -1.1,
      clipping: 0,
      delta: 0.6,
      rationale: "综合表现更稳，适合作为当前首选版本。",
      rank: 1,
    },
  ];

  const summary = preview.buildRuntimeCompareSummary("eval", groups, "free", "A");
  assert.equal(summary.best.key, "B");
  assert.match(summary.defaultReason, /综合表现更稳/);
  assert.match(summary.defaultSubline, /当前首选版本/);
  assert.equal(summary.defaultKpis.score, "3.8");
});

test("runtime compare summary recomputes delta when base group changes", () => {
  const groups = [
    {
      key: "A",
      file: "a.wav",
      score: 3.2,
      peak: -0.3,
      clipping: 0,
      delta: 0,
      rationale: "A",
      rank: 3,
    },
    {
      key: "B",
      file: "b.wav",
      score: 3.8,
      peak: -1.1,
      clipping: 0,
      delta: 0.6,
      rationale: "B",
      rank: 1,
    },
    {
      key: "C",
      file: "c.wav",
      score: 3.5,
      peak: -0.8,
      clipping: 0,
      delta: 0.3,
      rationale: "C",
      rank: 2,
    },
  ];

  const summary = preview.buildRuntimeCompareSummary("eval", groups, "base", "B");
  assert.equal(summary.baseGroup.key, "B");
  assert.equal(summary.best.key, "C");
  assert.equal(summary.best.delta, -0.3);
  assert.equal(summary.byDelta[0].key, "C");
  assert.equal(summary.byDelta[1].key, "A");
  assert.equal(summary.altHeadline, "当前基准 B 仍然更好");
  assert.match(summary.altReason, /比基准 B 更差/);
});

test("runtime compare summary keeps preview-style copy across free and base modes", () => {
  const groups = [
    {
      key: "A",
      file: "a.wav",
      score: 3.9,
      peak: -0.9,
      clipping: 0,
      delta: 0,
      rationale: "作为当前对照组保留复核价值。",
      rank: 2,
    },
    {
      key: "B",
      file: "b.wav",
      score: 4.6,
      peak: -1.4,
      clipping: 0,
      delta: 0.7,
      rationale: "综合表现更稳，适合作为当前首选版本。",
      rank: 1,
    },
  ];

  const freeSummary = preview.buildRuntimeCompareSummary("eval", groups, "free", "A");
  const baseSummary = preview.buildRuntimeCompareSummary("eval", groups, "base", "A");

  assert.equal(freeSummary.defaultSubline, "`b.wav` 综合表现更稳，适合作为当前首选版本。");
  assert.equal(baseSummary.altHeadline, "B 比基准 A 更好");
  assert.equal(baseSummary.altReason, "b.wav 比基准 A 更好，分差 +0.70。");
});

test("compare ranking and table view models can be shared by preview and runtime renderers", () => {
  const groups = [
    {
      key: "A",
      file: "a.wav",
      score: 3.9,
      peak: -0.9,
      clipping: 0,
      delta: 0,
      rationale: "作为当前对照组保留复核价值。",
      rank: 2,
      pipeline: "原始文件 → 重采样到 16kHz → 送入 DNSMOS",
    },
    {
      key: "B",
      file: "b.wav",
      score: 4.6,
      peak: -1.4,
      clipping: 0,
      delta: 0.7,
      rationale: "综合表现更稳，适合作为当前首选版本。",
      rank: 1,
      pipeline: "原始文件 → 重采样到 16kHz → 送入 DNSMOS",
    },
  ];

  const ranking = preview.buildCompareRankingViewModel("eval", groups, "free", "A");
  const table = preview.buildCompareTableViewModel("eval", groups, "full", "base", { eval: "dnsmos", analysis: "audiobox" }, "A");

  assert.equal(ranking[0].headline, "B · b.wav");
  assert.equal(ranking[0].subline, "综合排序第1");
  assert.equal(table.tag, "基准组 A");
  assert.match(table.tbodyHtml, /相对基准差值|原始文件 → 重采样到 16kHz → 送入 DNSMOS/);
});

test("getStatusClass uses separate thresholds for speech and analysis scales", () => {
  // speech scale (1-5): 4.5 is excellent
  assert.equal(preview.getStatusClass("score", 4.5, "speech"), "status-excellent");
  assert.equal(preview.getStatusClass("score", 3.0, "speech"), "status-fair");
  // analysis scale (1-10): 4.5 is fair, 8.0 is excellent
  assert.equal(preview.getStatusClass("score", 4.5, "analysis"), "status-fair");
  assert.equal(preview.getStatusClass("score", 8.0, "analysis"), "status-excellent");
  assert.equal(preview.getStatusClass("score", 6.0, "analysis"), "status-good");
});

test("buildRuntimeCompareGroups extracts snr field when present", () => {
  const payload = {
    base_key: "A",
    items: [
      {
        key: "A",
        rank: 1,
        delta_from_base: 0,
        file_path: "/tmp/a.wav",
        task: {
          model: {
            model_key: "dnsmos",
            result: {
              model_name: "DNSMOS",
              file_path: "a.wav",
              original_sr: 48000,
              original_channels: 2,
              dimensions: {
                OVRL: { score: 3.8, grade: "Good", description: "ok" },
                SIG: { score: 4.1, grade: "Good", description: "clear" },
                BAK: { score: 3.2, grade: "Fair", description: "noise" },
              },
            },
          },
          signal: {
            metrics: {
              LUFS: { value: -14.8, unit: "LUFS", grade: "Warning" },
              LRA: { value: 8.2, unit: "LU", grade: "Good" },
              TruePeak: { value: -0.3, unit: "dBTP", grade: "Warning" },
              Clipping: { value: 0, unit: "次", grade: "Good" },
              THD: { value: 0.5, unit: "%", grade: "Good" },
              SNR: { value: 14.2, unit: "dB", grade: "Good" },
            },
          },
        },
      },
    ],
  };
  const groups = preview.buildRuntimeCompareGroups("eval", payload, { eval: "dnsmos", analysis: "audiobox" });
  assert.equal(groups[0].snr, 14.2);
});

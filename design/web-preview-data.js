(function(root, factory) {
  const lib = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = lib;
  }
  root.AudioQASWebPreview = lib;
})(typeof globalThis !== "undefined" ? globalThis : this, function() {
  const pageMeta = {
    eval: {
      title: "纯人声评测",
      subtitle: "适用于通话、口播、会议、纯人声录音。评测结果同时包含当前模型结果、信号分析和预处理追溯。",
    },
    analysis: {
      title: "综合音频分析",
      subtitle: "适用于人声+音乐、视频音轨、节目成品与混合内容。结果同时包含当前模型结果、信号分析和预处理追溯。",
    },
    history: {
      title: "历史",
      subtitle: "查看历史任务、结果摘要、预处理追溯和导出记录。",
    },
    settings: {
      title: "设置",
      subtitle: "管理默认模型、结果显示、预处理、导出和历史设置。",
    },
  };

  const viewClassMap = {
    metrics: "metrics",
    signal: "signal",
    full: "full",
  };

  const compareGroupDefs = {
    eval: ["C", "D", "E", "F"],
    analysis: ["C", "D", "E", "F"],
  };

  const gradeClassMap = {
    Excellent: "status-excellent",
    Good: "status-good",
    Fair: "status-fair",
    Poor: "status-poor",
    Bad: "status-bad",
  };

  const statusColorVarMap = {
    "status-excellent": "var(--excellent)",
    "status-good": "var(--good)",
    "status-fair": "var(--fair)",
    "status-poor": "var(--poor)",
    "status-bad": "var(--bad)",
    "status-warn": "var(--warn)",
    "status-accent": "var(--accent)",
  };

  const gradeBackgroundStyleMap = {
    "status-excellent": "background:rgba(86,211,100,0.12)",
    "status-good": "background:rgba(63,185,80,0.12)",
    "status-fair": "background:rgba(227,179,65,0.12)",
    "status-poor": "background:rgba(255,158,66,0.14)",
    "status-bad": "background:rgba(248,81,73,0.14)",
    "status-warn": "background:rgba(255,158,66,0.14)",
    "status-accent": "background:rgba(88,166,255,0.14)",
  };

  const detailColumns = {
    eval: {
      metrics: [
        { key: "group", label: "组别", sub: "Group" },
        { key: "file", label: "文件", sub: "File" },
        { key: "score", label: "整体听感", sub: "OVRL" },
        { key: "sig", label: "语音清晰度", sub: "SIG" },
        { key: "bak", label: "背景干净度", sub: "BAK" },
        { key: "noise", label: "噪声感知", sub: "Noise" },
        { key: "rank", label: "排序", sub: "Rank" },
      ],
      signal: [
        { key: "group", label: "组别", sub: "Group" },
        { key: "file", label: "文件", sub: "File" },
        { key: "lufs", label: "综合响度", sub: "LUFS" },
        { key: "lra", label: "响度范围", sub: "LRA" },
        { key: "peak", label: "真实峰值", sub: "True Peak" },
        { key: "clipping", label: "削波次数", sub: "Clipping" },
        { key: "thd", label: "谐波失真", sub: "THD" },
        { key: "snr", label: "信噪比", sub: "SNR" },
      ],
      full: [
        { key: "group", label: "组别", sub: "Group" },
        { key: "file", label: "文件", sub: "File" },
        { key: "score", label: "整体听感", sub: "OVRL" },
        { key: "lufs", label: "综合响度", sub: "LUFS" },
        { key: "peak", label: "真实峰值", sub: "True Peak" },
        { key: "clipping", label: "削波次数", sub: "Clipping" },
        { key: "thd", label: "谐波失真", sub: "THD" },
        { key: "pipeline", label: "预处理追溯", sub: "Pipeline" },
        { key: "decision", label: "综合判断", sub: "Decision", mode: "free" },
        { key: "delta", label: "相对基准差值", sub: "Delta", mode: "base" },
        { key: "rank", label: "排序", sub: "Rank" },
      ],
    },
    analysis: {
      metrics: [
        { key: "group", label: "组别", sub: "Group" },
        { key: "file", label: "文件", sub: "File" },
        { key: "score", label: "制作质量", sub: "PQ" },
        { key: "ce", label: "内容享受", sub: "CE" },
        { key: "cu", label: "内容有用", sub: "CU" },
        { key: "pc", label: "制作复杂度", sub: "PC" },
        { key: "rank", label: "排序", sub: "Rank" },
      ],
      signal: [
        { key: "group", label: "组别", sub: "Group" },
        { key: "file", label: "文件", sub: "File" },
        { key: "lufs", label: "综合响度", sub: "LUFS" },
        { key: "lra", label: "响度范围", sub: "LRA" },
        { key: "peak", label: "真实峰值", sub: "True Peak" },
        { key: "clipping", label: "削波次数", sub: "Clipping" },
        { key: "thd", label: "谐波失真", sub: "THD" },
        { key: "stereo", label: "声像宽度", sub: "Stereo" },
      ],
      full: [
        { key: "group", label: "组别", sub: "Group" },
        { key: "file", label: "文件", sub: "File" },
        { key: "score", label: "制作质量", sub: "PQ" },
        { key: "lufs", label: "综合响度", sub: "LUFS" },
        { key: "peak", label: "真实峰值", sub: "True Peak" },
        { key: "clipping", label: "削波次数", sub: "Clipping" },
        { key: "thd", label: "谐波失真", sub: "THD" },
        { key: "pipeline", label: "预处理追溯", sub: "Pipeline" },
        { key: "decision", label: "综合判断", sub: "Decision", mode: "free" },
        { key: "delta", label: "相对基准差值", sub: "Delta", mode: "base" },
        { key: "rank", label: "排序", sub: "Rank" },
      ],
    },
  };

  const compareData = {
    eval: {
      dnsmos: {
        metricLabel: "整体听感",
        metricKey: "OVRL",
        modelName: "DNSMOS",
        groups: [
          { key: "A", file: "call_raw.wav", inputText: "call_raw.wav<br>原始人声样本", score: 2.98, sig: 3.24, bak: 2.61, noise: 2.8, lufs: -13.2, lra: 10.8, peak: -0.1, clipping: 3, thd: 1.2, snr: 14.2, pipeline: "原始文件 → 转单声道 → 16kHz → DNSMOS", decision: "原始参考版本", rationale: "作为原始样本保留对照价值，但背景噪声和峰值风险都偏高。" },
          { key: "B", file: "denoise_v1.wav", inputText: "denoise_v1.wav<br>一轮降噪", score: 3.41, sig: 3.76, bak: 3.22, noise: 3.4, lufs: -14.6, lra: 9.7, peak: -0.8, clipping: 0, thd: 0.8, snr: 18.6, pipeline: "原始文件 → 降噪 → 转单声道 → 16kHz → DNSMOS", decision: "基础改善", rationale: "有改善，但还没进入可直接交付区间。" },
          { key: "C", file: "denoise_v2.wav", inputText: "denoise_v2.wav<br>二轮降噪", score: 3.86, sig: 4.02, bak: 3.81, noise: 4.0, lufs: -15.5, lra: 8.8, peak: -1.0, clipping: 0, thd: 0.6, snr: 21.1, pipeline: "原始文件 → 强降噪 → 转单声道 → 16kHz → DNSMOS", decision: "强处理候选", rationale: "降噪力度更强，整体表现接近最优。" },
          { key: "D", file: "eq_mix.wav", inputText: "eq_mix.wav<br>降噪 + EQ", score: 4.02, sig: 4.18, bak: 3.94, noise: 4.2, lufs: -15.9, lra: 8.5, peak: -1.2, clipping: 0, thd: 0.5, snr: 22.4, pipeline: "原始文件 → 降噪 → EQ → 转单声道 → 16kHz → DNSMOS", decision: "当前最优", rationale: "综合最稳，感知结果和信号结果都领先。" },
          { key: "E", file: "compress_v1.wav", inputText: "compress_v1.wav<br>压缩版", score: 3.72, sig: 3.91, bak: 3.58, noise: 3.7, lufs: -14.9, lra: 7.9, peak: -0.6, clipping: 0, thd: 0.9, snr: 19.7, pipeline: "原始文件 → 降噪 → 压缩 → 转单声道 → 16kHz → DNSMOS", decision: "平衡候选", rationale: "响度更统一，但处理痕迹比 D 更明显。" },
          { key: "F", file: "publish_ref.wav", inputText: "publish_ref.wav<br>交付参考版", score: 3.95, sig: 4.09, bak: 3.78, noise: 3.9, lufs: -15.3, lra: 8.3, peak: -1.1, clipping: 0, thd: 0.4, snr: 21.8, pipeline: "原始文件 → 降噪 → EQ → 轻限幅 → 16kHz → DNSMOS", decision: "交付参考", rationale: "整体完成度高，但背景干净度略弱于 D。" },
        ],
      },
      nisqa: {
        metricLabel: "整体质量",
        metricKey: "OVRL",
        modelName: "NISQA",
        groups: [
          { key: "A", file: "call_raw.wav", inputText: "call_raw.wav<br>原始人声样本", score: 2.84, sig: 2.93, bak: 2.68, noise: 2.52, lufs: -13.2, lra: 10.8, peak: -0.1, clipping: 3, thd: 1.2, snr: 14.2, pipeline: "原始文件 → 转单声道 → 保持 48kHz → NISQA", decision: "原始参考版本", rationale: "整体质量和噪声维度都偏低，适合作为清晰的原始基线。" },
          { key: "B", file: "denoise_v1.wav", inputText: "denoise_v1.wav<br>一轮降噪", score: 3.52, sig: 3.88, bak: 3.35, noise: 3.41, lufs: -14.6, lra: 9.7, peak: -0.8, clipping: 0, thd: 0.8, snr: 18.6, pipeline: "原始文件 → 降噪 → 转单声道 → 保持 48kHz → NISQA", decision: "基础改善", rationale: "噪声感知改善明显，但连续性与染色仍有优化空间。" },
          { key: "C", file: "denoise_v2.wav", inputText: "denoise_v2.wav<br>二轮降噪", score: 4.12, sig: 4.21, bak: 3.62, noise: 4.08, lufs: -15.5, lra: 8.8, peak: -1.0, clipping: 0, thd: 0.6, snr: 21.1, pipeline: "原始文件 → 强降噪 → 转单声道 → 保持 48kHz → NISQA", decision: "降噪优先候选", rationale: "整体质量和噪声控制最突出，但染色感略高于 D。" },
          { key: "D", file: "eq_mix.wav", inputText: "eq_mix.wav<br>降噪 + EQ", score: 4.06, sig: 4.09, bak: 3.91, noise: 3.96, lufs: -15.9, lra: 8.5, peak: -1.2, clipping: 0, thd: 0.5, snr: 22.4, pipeline: "原始文件 → 降噪 → EQ → 转单声道 → 保持 48kHz → NISQA", decision: "平衡候选", rationale: "染色更稳，连续性更自然，整体更适合长期听感。" },
          { key: "E", file: "compress_v1.wav", inputText: "compress_v1.wav<br>压缩版", score: 3.68, sig: 3.79, bak: 3.31, noise: 3.48, lufs: -14.9, lra: 7.9, peak: -0.6, clipping: 0, thd: 0.9, snr: 19.7, pipeline: "原始文件 → 降噪 → 压缩 → 转单声道 → 保持 48kHz → NISQA", decision: "响度平衡候选", rationale: "响度和连续性更统一，但整体质量收益有限。" },
          { key: "F", file: "publish_ref.wav", inputText: "publish_ref.wav<br>交付参考版", score: 3.98, sig: 4.02, bak: 3.75, noise: 3.89, lufs: -15.3, lra: 8.3, peak: -1.1, clipping: 0, thd: 0.4, snr: 21.8, pipeline: "原始文件 → 降噪 → EQ → 轻限幅 → 保持 48kHz → NISQA", decision: "交付参考", rationale: "综合稳定，但整体质量与噪声控制仍略低于 C。" },
        ],
      },
    },
    analysis: {
      metricLabel: "制作质量",
      metricKey: "PQ",
      modelName: "AudioBox Aesthetics",
      groups: [
        { key: "A", file: "rough_mix.wav", inputText: "rough_mix.wav<br>初版混音", score: 5.2, ce: 5.0, cu: 6.1, pc: 4.8, lufs: -12.6, lra: 11.8, peak: -0.1, clipping: 2, thd: 1.8, stereo: "宽", pipeline: "原始文件 → 转单声道 → 保持 48kHz → AudioBox", decision: "原始混音参考", rationale: "信息完整，但响度和峰值都还未到交付状态。" },
        { key: "B", file: "master_v1.wav", inputText: "master_v1.wav<br>第一版母带", score: 7.1, ce: 6.8, cu: 7.6, pc: 6.3, lufs: -14.4, lra: 9.2, peak: -0.4, clipping: 0, thd: 0.9, stereo: "中", pipeline: "原始文件 → 限幅 → 转单声道 → 48kHz → AudioBox", decision: "基础母带版", rationale: "已经完成基础修正，但峰值余量还不够宽。" },
        { key: "C", file: "master_v2.wav", inputText: "master_v2.wav<br>响度调整版", score: 7.8, ce: 7.1, cu: 8.5, pc: 5.9, lufs: -15.8, lra: 9.4, peak: -1.0, clipping: 0, thd: 0.4, stereo: "中", pipeline: "原始文件 → 限幅 → 响度回调 → 48kHz → AudioBox", decision: "当前最优", rationale: "内容层与工程层都最均衡，最接近最终交付。" },
        { key: "D", file: "stream_cut.mov", inputText: "stream_cut.mov<br>节目成片", score: 6.6, ce: 6.2, cu: 7.1, pc: 5.4, lufs: -15.0, lra: 8.7, peak: -0.7, clipping: 0, thd: 0.7, stereo: "窄", pipeline: "原始视频 → 抽取音轨 → 转单声道 → 48kHz → AudioBox", decision: "抽轨对照版", rationale: "抽轨对照价值更高，不适合作为最终主版本。" },
        { key: "E", file: "platform_norm.wav", inputText: "platform_norm.wav<br>平台归一化版", score: 7.4, ce: 6.9, cu: 8.0, pc: 5.6, lufs: -16.1, lra: 8.9, peak: -1.4, clipping: 0, thd: 0.5, stereo: "中", pipeline: "原始文件 → 平台响度归一化 → 48kHz → AudioBox", decision: "平台适配版", rationale: "平台适配更稳，但内容冲击力略弱于 C。" },
        { key: "F", file: "final_publish.wav", inputText: "final_publish.wav<br>最终交付版", score: 7.6, ce: 7.0, cu: 8.2, pc: 5.8, lufs: -15.4, lra: 9.1, peak: -1.1, clipping: 0, thd: 0.4, stereo: "中", pipeline: "原始文件 → 母带微调 → 48kHz → AudioBox", decision: "交付候选", rationale: "整体已经接近交付，但制作完成度仍略低于 C。" },
      ],
    },
  };

  const modelContent = {
    eval: {
      dnsmos: {
        title: "DNSMOS",
        lines: [
          ["适用", "纯人声、通话、会议、口播"],
          ["优点", "结果直观，适合快速筛查人声问题"],
          ["局限", "不适合强配乐或节目成品"],
          ["原理", "无参考语音质量预测"],
          ["指标", "OVRL=整体听感，SIG=语音清晰度，BAK=背景干净度"],
        ],
        toolbar: "DNSMOS / NISQA + 信号分析",
        docLabel: "当前模型：DNSMOS",
      },
      nisqa: {
        title: "NISQA",
        lines: [
          ["适用", "纯人声、高质量语音样本、需要更细分维度时"],
          ["优点", "维度更多，便于拆解噪声、连续性、染色和响度问题"],
          ["局限", "推理更重，仍不适合强混合内容"],
          ["原理", "无参考语音质量预测"],
          ["指标", "OVRL=整体质量，NOI=噪声度，DIS=连续性，COL=染色度，LOUD=响度"],
        ],
        toolbar: "NISQA / DNSMOS + 信号分析",
        docLabel: "当前模型：NISQA",
      },
    },
    analysis: {
      audiobox: {
        title: "AudioBox Aesthetics",
        lines: [
          ["适用", "人声+音乐、节目成品、混合内容"],
          ["优点", "更接近内容级判断，适合成品审视"],
          ["局限", "不能与语音 MOS 数值直接横向等价比较"],
          ["原理", "内容美学 / 内容感知评分"],
          ["指标", "PQ=制作质量，CE=内容享受，CU=内容有用，PC=制作复杂度"],
        ],
        toolbar: "AudioBox Aesthetics + 信号分析",
        docLabel: "当前模型：AudioBox Aesthetics",
      },
    },
  };

  function normalizeModels(models) {
    return {
      eval: (models && models.eval) || "dnsmos",
      analysis: (models && models.analysis) || "audiobox",
    };
  }

  function getCompareDataset(kind, models) {
    const normalized = normalizeModels(models);
    if (kind === "eval") return compareData.eval[normalized.eval];
    return compareData[kind];
  }

  function formatSigned(value, digits) {
    const safeDigits = digits == null ? 2 : digits;
    return `${value >= 0 ? "+" : ""}${value.toFixed(safeDigits)}`;
  }

  function roundDelta(value) {
    return Number(value.toFixed(2));
  }

  function formatScore(value) {
    return Number.isInteger(value) ? String(value) : value.toFixed(1).replace(/\.0$/, "");
  }

  function formatChannels(channelCount) {
    return channelCount === 1 ? "Mono" : channelCount === 2 ? "Stereo" : `${channelCount}ch`;
  }

  function buildTraceText(result) {
    if (Array.isArray(result.pipeline_steps) && result.pipeline_steps.length > 0) {
      const mapping = {
        source_video: "原始视频",
        source_audio: "原始文件",
        extract_audio: "抽取音轨",
        to_mono: "转单声道",
        resample_16k: "重采样到 16kHz",
        keep_48k: "保持 48kHz",
        passthrough: "直接使用原始音频",
      };
      const modelLabel = result.model_name === "AudioBox-Aesthetics" ? "AudioBox Aesthetics" : result.model_name;
      const labels = result.pipeline_steps.map((step) => mapping[step] || step);
      const settings = result.preprocess_settings || {};
      const disabledHints = [];
      if (settings.extract_audio === false) disabledHints.push("已关闭自动提取音轨");
      if (settings.to_mono === false) disabledHints.push("已关闭自动转单声道");
      if (settings.resample === false) disabledHints.push("已关闭自动重采样");
      const trace = [...labels, `送入 ${modelLabel}`].join(" → ");
      if (result.pipeline_steps.length <= 2 && disabledHints.length > 0) {
        return `${trace}（${disabledHints.join("，")}）`;
      }
      return trace;
    }
    const source = String(result.file_path || "").match(/\.(mp4|mkv|avi|mov|wmv|flv)$/i) ? "原始视频" : "原始文件";
    const steps = [source];
    if (source === "原始视频") steps.push("抽取音轨");
    if (result.original_channels && result.original_channels > 1) {
      steps.push("转单声道");
    }
    if (result.model_name === "DNSMOS") {
      steps.push("重采样到 16kHz");
    } else if (result.model_name === "NISQA") {
      steps.push("保持 48kHz");
    } else if (result.model_name === "AudioBox-Aesthetics" || result.model_name === "AudioBox Aesthetics") {
      steps.push("保持 48kHz");
    }
    const modelLabel = result.model_name === "AudioBox-Aesthetics" ? "AudioBox Aesthetics" : result.model_name;
    steps.push(`送入 ${modelLabel}`);
    return steps.join(" → ");
  }

  function buildAdviceText(page, payload) {
    const metrics = payload.signal?.metrics || {};
    const peakGrade = metrics.TruePeak?.grade;
    const lufsGrade = metrics.LUFS?.grade;
    const clippingGrade = metrics.Clipping?.grade;
    if (peakGrade === "Warning" || peakGrade === "Poor" || lufsGrade === "Warning" || lufsGrade === "Poor") {
      return page === "analysis"
        ? "建议先整理峰值和响度，再复核内容完成度。"
        : "建议先整理峰值和响度，再复评。";
    }
    if (clippingGrade === "Warning" || clippingGrade === "Poor") {
      return page === "analysis"
        ? "建议先消除削波和失真风险，再继续复核。"
        : "建议先消除削波和失真风险，再复评。";
    }
    const primaryGrade = payload.model.result.grade;
    if (primaryGrade === "Poor" || primaryGrade === "Bad" || primaryGrade === "Fair") {
      return page === "analysis"
        ? "建议继续优化内容完成度和工程细节后再复核。"
        : "建议继续优化人声质量和工程细节后再复评。";
    }
    return page === "analysis"
      ? "结果已具备继续复核价值，可进入下一步检查。"
      : "结果已具备继续复评价值，可进入下一步检查。";
  }

  function scoreClassFromGrade(grade) {
    return gradeClassMap[grade] || "status-fair";
  }

  function colorVarFromStatusClass(statusClass) {
    return statusColorVarMap[statusClass] || "var(--accent)";
  }

  function gradeBackgroundStyle(grade) {
    const statusClass = scoreClassFromGrade(grade);
    return gradeBackgroundStyleMap[statusClass] || gradeBackgroundStyleMap["status-accent"];
  }

  function signalStateClass(grade) {
    return grade === "Good" ? "status-good" : grade === "Warning" ? "status-warn" : "status-poor";
  }

  function signalStateText(grade) {
    return grade === "Good" ? "稳定" : grade === "Warning" ? "需关注" : "存在风险";
  }

  function signalLabel(key) {
    const labels = {
      LUFS: "综合响度 · LUFS",
      LRA: "响度范围 · LRA",
      TruePeak: "真实峰值 · True Peak",
      Clipping: "削波次数 · Clipping",
      THD: "谐波失真 · THD",
      SNR: "信噪比 · SNR",
      Stereo: "声像宽度 · Stereo",
    };
    return labels[key] || key;
  }

  function signalDescription(page, key, metric) {
    if (page === "eval") {
      const speechDescriptions = {
        LUFS: "响度略高，长时间听会偏顶。",
        LRA: "动态范围比较稳定，适合口播内容。",
        TruePeak: "峰值接近上限，建议保留更多余量。",
        Clipping: "没有发现明显削波事件。",
        THD: "谐波失真较低，没有明显破音风险。",
      };
      return speechDescriptions[key] || metric.description;
    }
    const analysisDescriptions = {
      LUFS: "响度略高，平台归一化后可能被压回去。",
      LRA: "动态范围比较稳定，适合节目成品。",
      TruePeak: "峰值接近上限，建议再留 0.7 dBTP 余量。",
      Clipping: "没有发现可见削波事件。",
      THD: "谐波失真较低，没有明显破音风险。",
    };
    return analysisDescriptions[key] || metric.description;
  }

  function buildSingleFileViewModel(page, payload, fileName) {
    const result = payload.model.result;
    const dimensions = result.dimensions || {};
    const signalMetrics = payload.signal?.metrics || {};
    const isAnalysis = page === "analysis";
    const orderedModelKeys = page === "eval" && payload.model.model_key === "nisqa"
      ? ["OVRL", "NOI", "DIS", "COL", "LOUD"]
      : Object.keys(dimensions);
    const primaryKey = orderedModelKeys.find((key) => dimensions[key]) || Object.keys(dimensions)[0];
    const primaryMetric = primaryKey ? { key: primaryKey, ...dimensions[primaryKey] } : null;
    const detailRow = {
      file: fileName,
      score: primaryKey ? dimensions[primaryKey]?.score : null,
      sig: dimensions.SIG?.score ?? dimensions.DIS?.score ?? null,
      bak: dimensions.BAK?.score ?? dimensions.COL?.score ?? null,
      noise: dimensions.NOI?.score ?? null,
      loud: dimensions.LOUD?.score ?? null,
      ce: dimensions.CE?.score ?? null,
      cu: dimensions.CU?.score ?? null,
      pc: dimensions.PC?.score ?? null,
      lufs: signalMetrics.LUFS?.value ?? null,
      lra: signalMetrics.LRA?.value ?? null,
      peak: signalMetrics.TruePeak?.value ?? null,
      clipping: signalMetrics.Clipping?.value ?? null,
      thd: signalMetrics.THD?.value ?? null,
      snr: signalMetrics.SNR?.value ?? null,
      stereo: signalMetrics.Stereo?.value ?? null,
      pipeline: buildTraceText(result),
    };
    const labelMap = page === "analysis"
      ? {
        PQ: "制作质量 · PQ",
        CE: "内容享受 · CE",
        CU: "内容有用 · CU",
        PC: "制作复杂度 · PC",
      }
      : payload.model.model_key === "nisqa"
        ? {
          OVRL: "整体质量 · OVRL",
          NOI: "噪声感知 · NOI",
          DIS: "连续性 · DIS",
          COL: "染色感 · COL",
          LOUD: "响度 · LOUD",
        }
        : {
          OVRL: "整体听感 · OVRL",
          SIG: "语音清晰度 · SIG",
          BAK: "背景干净度 · BAK",
        };

    const modelCards = orderedModelKeys
      .filter((key) => dimensions[key])
      .map((key) => {
        const metric = dimensions[key];
        const gradeClass = scoreClassFromGrade(metric.grade);
        const maxScore = isAnalysis ? 10 : 5;
        return {
          key,
          label: labelMap[key] || key,
          ...metric,
          scoreText: Number(metric.score).toFixed(isAnalysis ? 1 : 2),
          gradeClass,
          barStyle: `width:${Math.min(Number(metric.score) / maxScore * 100, 100)}%;background:${colorVarFromStatusClass(gradeClass)}`,
        };
      });

    if (page === "eval" && payload.model.model_key === "dnsmos") {
      modelCards.push({
        key: "advice",
        label: "处理建议",
        score: null,
        scoreText: "A-",
        grade: "需继续优化",
        description: buildAdviceText(page, payload),
        gradeClass: "status-accent",
        barStyle: "width:78%;background:var(--accent)",
      });
    }

    return {
      fileName,
      modelName: result.model_name,
      summary: `${result.duration.toFixed(1)}s · ${result.original_sr}Hz · ${formatChannels(result.original_channels)} · 当前模型 ${result.model_name}`,
      traceText: buildTraceText(result),
      adviceText: buildAdviceText(page, payload),
      layoutMode: page === "eval" && payload.model.model_key === "nisqa" ? "compact-five" : "default",
      primaryMetric,
      hero: primaryMetric ? {
        valueText: Number(primaryMetric.score).toFixed(isAnalysis ? 1 : 2),
        valueClass: scoreClassFromGrade(primaryMetric.grade),
        gradeText: `${primaryMetric.grade} · ${primaryMetric.description}`,
        gradeClass: scoreClassFromGrade(primaryMetric.grade),
        gradeStyle: gradeBackgroundStyle(primaryMetric.grade),
      } : null,
      modelCards,
      signalCards: Object.entries(signalMetrics).map(([key, metric]) => ({
        key,
        ...metric,
        label: signalLabel(key),
        valueText: formatSignalMetricValue(metric),
        valueClass: signalStateClass(metric.grade),
        stateText: signalStateText(metric.grade),
        stateClass: signalStateClass(metric.grade),
        description: signalDescription(page, key, metric),
      })),
      detailRow,
    };
  }

  function getSingleDetailColumns(page, view, modelKey) {
    if (page === "eval" && modelKey === "nisqa" && view === "metrics") {
      return [
        { key: "file", label: "文件", sub: "File" },
        { key: "score", label: "整体质量", sub: "OVRL" },
        { key: "noise", label: "噪声感知", sub: "NOI" },
        { key: "sig", label: "连续性", sub: "DIS" },
        { key: "bak", label: "染色感", sub: "COL" },
        { key: "loud", label: "响度", sub: "LOUD" },
      ];
    }
    return detailColumns[page][view].filter((column) => !["group", "decision", "delta", "rank"].includes(column.key));
  }

  function buildSingleDetailHeaders(page, view, modelKey) {
    return getSingleDetailColumns(page, view, modelKey)
      .map((column) => `<th><span class="th-label">${column.label}</span><span class="th-sub">${column.sub}</span></th>`)
      .join("");
  }

  function buildSingleDetailCells(page, row, view, modelKey) {
    const domain = page === "eval" ? "speech" : "analysis";
    return getSingleDetailColumns(page, view, modelKey)
      .map((column) => {
        const rawValue = row[column.key];
        const cls = getColumnClass(column.key, rawValue, domain);
        return `<td${cls ? ` class="${cls}"` : ""}>${formatCellValue(column.key, rawValue)}</td>`;
      })
      .join("");
  }

  function buildRuntimeCompareGroups(kind, payload, models) {
    return payload.items.map((item) => {
      const result = item.task.model.result;
      const dims = result.dimensions || {};
      const firstDimension = Object.values(dims)[0];
      return {
        key: item.key,
        file: item.file_path.split("/").pop(),
        score: firstDimension?.score ?? 0,
        sig: dims.SIG?.score ?? dims.DIS?.score ?? 0,
        bak: dims.BAK?.score ?? dims.COL?.score ?? 0,
        noise: dims.NOI?.score ?? 0,
        loud: dims.LOUD?.score ?? 0,
        ce: dims.CE?.score ?? 0,
        cu: dims.CU?.score ?? 0,
        pc: dims.PC?.score ?? 0,
        peak: item.task.signal?.metrics?.TruePeak?.value ?? 0,
        clipping: item.task.signal?.metrics?.Clipping?.value ?? 0,
        lufs: item.task.signal?.metrics?.LUFS?.value ?? null,
        lra: item.task.signal?.metrics?.LRA?.value ?? null,
        thd: item.task.signal?.metrics?.THD?.value ?? null,
        snr: item.task.signal?.metrics?.SNR?.value ?? null,
        stereo: item.task.signal?.metrics?.Stereo?.value ?? null,
        delta: item.delta_from_base ?? 0,
        rationale: item.rank === 1 ? "综合表现更稳，适合作为当前首选版本。" : "作为当前对照组保留复核价值。",
        rank: item.rank,
        pipeline: buildTraceText(result),
        decision: item.rank === 1 ? "当前推荐版本" : "对照候选",
      };
    });
  }

  function buildRuntimeCompareSummary(kind, groups, mode, baseKey) {
    const sorted = [...groups].sort((a, b) => a.rank - b.rank);
    const base = groups.find((group) => group.key === baseKey) || groups[0];
    const byDelta = groups
      .filter((group) => group.key !== base?.key)
      .map((group) => ({ ...group, delta: roundDelta(group.score - (base?.score ?? 0)) }))
      .sort((a, b) => b.delta - a.delta);
    const best = mode === "base" ? (byDelta[0] || sorted[0]) : sorted[0];
    const altHeadline = !best
      ? ""
      : best.delta > 0
        ? `${best.key} 比基准 ${base?.key || baseKey} 更好`
        : best.delta === 0
          ? `${best.key} 与基准 ${base?.key || baseKey} 基本持平`
          : `当前基准 ${base?.key || baseKey} 仍然更好`;
    const altReason = !best
      ? ""
      : best.delta > 0
        ? `${best.file} 比基准 ${base?.key || baseKey} 更好，分差 ${formatSigned(best.delta)}。`
        : best.delta === 0
          ? `${best.file} 与基准 ${base?.key || baseKey} 基本持平，分差 ${formatSigned(best.delta)}。`
          : `${best.file} 比基准 ${base?.key || baseKey} 更差，分差 ${formatSigned(best.delta)}。`;
    return {
      best,
      baseGroup: base,
      byDelta,
      defaultReason: best?.rationale || "",
      defaultSubline: best ? `\`${best.file}\` 综合表现更稳，适合作为当前首选版本。` : "",
      defaultKpis: {
        score: best ? formatScore(best.score) : "-",
        peak: best ? best.peak.toFixed(1) : "-",
        clipping: best ? String(best.clipping) : "-",
      },
      altHeadline,
      altReason,
    };
  }

  function buildCompareSummaryViewModel(kind, mode, baseGroup, bestOverall, bestDelta, runtimeSummary = null) {
    const isAnalysis = kind === "analysis";
    const domain = isAnalysis ? "analysis" : "speech";
    const freeWinner = runtimeSummary?.best || bestOverall;
    const baseWinner = runtimeSummary?.best || bestDelta || baseGroup;

    const free = {
      winnerKey: freeWinner?.key || "-",
      title: freeWinner ? `推荐版本 ${freeWinner.key}` : "推荐版本",
      subline: runtimeSummary?.defaultSubline || (freeWinner ? `\`${freeWinner.file}\` 综合表现更稳，适合作为当前首选版本。` : "等待脚本填充当前最佳结果。"),
      reason: runtimeSummary?.defaultReason || freeWinner?.rationale || "等待脚本填充结论。",
      kpis: [
        {
          label: "总分",
          value: freeWinner ? formatScore(freeWinner.score) : "-",
          className: freeWinner ? getStatusClass("score", freeWinner.score, domain) : "muted",
        },
        {
          label: "峰值",
          value: freeWinner ? freeWinner.peak.toFixed(1) : "-",
          className: freeWinner ? getStatusClass("peak", freeWinner.peak) : "muted",
        },
        {
          label: isAnalysis ? "状态" : "削波",
          value: freeWinner ? (isAnalysis ? "可优化后交付" : String(freeWinner.clipping)) : "-",
          className: freeWinner ? (isAnalysis ? "status-good" : getStatusClass("clipping", freeWinner.clipping)) : "muted",
        },
      ],
    };

    const base = {
      winnerKey: baseWinner?.key || "-",
      title: runtimeSummary?.altHeadline || (baseWinner ? `推荐版本 ${baseWinner.key}` : "推荐版本"),
      subline: runtimeSummary
        ? `\`${baseWinner.file}\` vs ${baseGroup.key} ${formatSigned(baseWinner.delta)}`
        : baseWinner?.subline
          ? baseWinner.subline
        : baseWinner
          ? `\`${baseWinner.file}\` 相对基准组 ${baseGroup.key} 提升最明显。`
          : "等待脚本填充基准对比结果。",
      reason: runtimeSummary?.altReason || baseWinner?.reason || (baseWinner ? `相对 ${baseGroup.key}，${baseWinner.file} 的表现变化最明显。` : "等待脚本填充结论。"),
      kpis: [
        {
          label: "相对提升",
          value: baseWinner ? formatSigned(baseWinner.delta) : "-",
          className: baseWinner ? (baseWinner.delta >= 0 ? "status-good" : "status-warn") : "muted",
        },
        {
          label: "当前基准",
          value: baseGroup?.key || "-",
          className: baseGroup ? "status-good" : "muted",
        },
        {
          label: "总分",
          value: baseWinner ? formatScore(baseWinner.score) : "-",
          className: baseWinner ? getStatusClass("score", baseWinner.score, domain) : "muted",
        },
      ],
    };

    return { free, base };
  }

  function buildCompareRankingViewModel(kind, groups, mode, baseKey) {
    const isAnalysis = kind === "analysis";
    const domain = isAnalysis ? "analysis" : "speech";
    const baseGroup = groups.find((group) => group.key === baseKey) || groups[0] || null;
    const list = mode === "base"
      ? groups
        .filter((group) => group.key !== baseGroup?.key)
        .map((group) => ({ ...group, delta: Number((group.score - (baseGroup?.score ?? 0)).toFixed(2)) }))
        .sort((a, b) => b.delta - a.delta)
      : [...groups].sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99));

    return list.map((group, index) => ({
      key: group.key,
      headline: `${group.key} · ${group.file}`,
      copy: mode === "base"
        ? group.delta > 0
          ? "比基准更好"
          : group.delta === 0
            ? "与基准持平"
            : "比基准更差"
        : group.rationale,
      scoreText: formatScore(group.score),
      scoreClass: getStatusClass("score", group.score, domain),
      subline: mode === "base"
        ? `vs ${baseGroup?.key || baseKey} ${formatSigned(group.delta)}`
        : `综合排序第${index + 1}`,
      top: index === 0,
    }));
  }

  function buildCompareTableViewModel(kind, groups, view, mode, models, baseKey) {
    const orderedGroups = mode === "base"
      ? groups.map((group) => ({
        ...group,
        delta: Number((group.score - ((groups.find((item) => item.key === baseKey) || groups[0] || { score: 0 }).score)).toFixed(2)),
      }))
      : [...groups];
    const headers = buildDetailHeaders(kind, view, mode, models);
    const columns = getDetailColumns(kind, view, models).filter((column) => !column.mode || column.mode === mode);
    const tbodyHtml = orderedGroups.map((group, index) => {
      const rank = group.rank ?? index + 1;
      const delta = group.delta ?? 0;
      return `<tr>${columns.map((column) => buildDetailCell(column.key, group, { delta, rank })).join("")}</tr>`;
    }).join("");

    return {
      tag: mode === "base" ? `基准组 ${baseKey}` : "自由对比",
      headers,
      tbodyHtml,
    };
  }

  function formatExportSetting(value) {
    if (value === "json") return "JSON";
    if (value === "csv") return "CSV";
    return "CSV + JSON";
  }

  function formatHistoryRetentionDays(value) {
    return value >= 99999 ? "永久" : `${value} 天`;
  }

  function formatCompareModeLabel(value) {
    return value === "free" ? "自由对比" : "基准对比";
  }

  function formatSceneLabel(scene) {
    return scene === "compare" ? "对比" : "单文件";
  }

  function formatModelTag(label) {
    return `模型: ${label}`;
  }

  function formatSignalMetricValue(metric) {
    const value = metric.value;
    if (value == null) return "--";
    if (metric.key === "Clipping" || metric.unit === "次" || Number.isInteger(value)) {
      return String(value);
    }
    if (metric.unit === "%") {
      return `${Number(value).toFixed(1)}%`;
    }
    return Number(value).toFixed(1);
  }

  function getStatusClass(kind, value, domain) {
    if (kind === "score") {
      const thresholds = domain === "analysis"
        ? { excellent: 8.0, good: 6.0, fair: 4.0, poor: 2.0 }
        : { excellent: 4.5, good: 4.0, fair: 3.0, poor: 2.0 };
      if (value >= thresholds.excellent) return "status-excellent";
      if (value >= thresholds.good) return "status-good";
      if (value >= thresholds.fair) return "status-fair";
      if (value >= thresholds.poor) return "status-poor";
      return "status-bad";
    }
    if (kind === "lufs") return value <= -15 ? "status-good" : value <= -14 ? "status-fair" : "status-warn";
    if (kind === "peak") return value <= -1 ? "status-good" : value <= -0.5 ? "status-fair" : "status-warn";
    if (kind === "clipping") return value === 0 ? "status-good" : value <= 1 ? "status-fair" : "status-poor";
    if (kind === "thd") return value <= 0.5 ? "status-good" : value <= 1 ? "status-fair" : "status-warn";
    return "status-good";
  }

  function getDetailColumns(kind, view, models) {
    const normalized = normalizeModels(models);
    if (kind === "eval" && normalized.eval === "nisqa" && view === "metrics") {
      return [
        { key: "group", label: "组别", sub: "Group" },
        { key: "file", label: "文件", sub: "File" },
        { key: "score", label: "整体质量", sub: "OVRL" },
        { key: "noise", label: "噪声感知", sub: "NOI" },
        { key: "sig", label: "连续性", sub: "DIS" },
        { key: "bak", label: "染色感", sub: "COL" },
        { key: "loud", label: "响度", sub: "LOUD" },
        { key: "rank", label: "排序", sub: "Rank" },
      ];
    }
    return detailColumns[kind][view];
  }

  function buildDetailHeaders(kind, view, mode, models) {
    return getDetailColumns(kind, view, models)
      .filter((column) => !column.mode || column.mode === mode)
      .map((column) => `<th><span class="th-label">${column.label}</span><span class="th-sub">${column.sub}</span></th>`)
      .join("");
  }

  function formatCellValue(columnKey, value) {
    if (value == null) return "";
    if (["score", "sig", "bak", "noise", "loud", "ce", "cu", "pc", "lra", "thd"].includes(columnKey)) {
      return columnKey === "thd" ? `${value.toFixed(1)}%` : formatScore(value);
    }
    if (["lufs", "peak", "delta"].includes(columnKey)) {
      return columnKey === "delta" ? formatSigned(value) : value.toFixed(1);
    }
    if (["clipping", "rank"].includes(columnKey)) {
      return columnKey === "rank" ? `#${value}` : String(value);
    }
    if (columnKey === "snr") return `${value.toFixed(1)} dB`;
    return String(value);
  }

  function getColumnClass(columnKey, value, domain) {
    if (["score", "sig", "bak", "noise", "loud", "ce", "cu", "pc"].includes(columnKey)) return `mono ${getStatusClass("score", value, domain)}`;
    if (columnKey === "lufs") return `mono ${getStatusClass("lufs", value)}`;
    if (columnKey === "peak") return `mono ${getStatusClass("peak", value)}`;
    if (columnKey === "clipping") return `mono ${getStatusClass("clipping", value)}`;
    if (columnKey === "thd") return `mono ${getStatusClass("thd", value)}`;
    if (columnKey === "delta") return `mono ${value > 0 ? "status-good" : value < 0 ? "status-warn" : "muted"}`;
    if (["lra", "rank"].includes(columnKey)) return "mono";
    if (columnKey === "snr") return `mono ${value >= 20 ? "status-good" : value >= 16 ? "status-fair" : "status-warn"}`;
    if (columnKey === "stereo") return value === "宽" ? "status-fair" : "status-good";
    if (columnKey === "pipeline") return "hint";
    return "";
  }

  function buildDetailCell(columnKey, group, ctx, domain) {
    const delta = ctx.delta;
    const rank = ctx.rank;
    if (columnKey === "group") return `<td><strong>${group.key}</strong></td>`;
    if (columnKey === "file") return `<td>${group.file}</td>`;
    if (columnKey === "pipeline") return `<td class="hint">${group.pipeline}</td>`;
    if (columnKey === "decision") return `<td>${group.decision}</td>`;
    const rawValue = columnKey === "delta" ? delta : columnKey === "rank" ? rank : group[columnKey];
    const cls = getColumnClass(columnKey, rawValue, domain);
    return `<td${cls ? ` class="${cls}"` : ""}>${formatCellValue(columnKey, rawValue)}</td>`;
  }

  return {
    pageMeta,
    viewClassMap,
    compareGroupDefs,
    detailColumns,
    compareData,
    modelContent,
    getCompareDataset,
    formatSigned,
    formatScore,
    formatChannels,
    buildTraceText,
    buildAdviceText,
    buildSingleFileViewModel,
    formatSignalMetricValue,
    getSingleDetailColumns,
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
    getStatusClass,
    getDetailColumns,
    buildDetailHeaders,
    formatCellValue,
    getColumnClass,
    buildDetailCell,
  };
});

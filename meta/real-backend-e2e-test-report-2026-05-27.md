# AudioQAS 真实后端 E2E 测试报告

日期：2026-05-27

## 范围

本报告覆盖 Web Preview 当前确认的可见产品流：

- 纯人声评测：添加文件、对比评测
- 综合音频分析：添加文件、对比评测
- 历史
- 设置

不覆盖未在当前产品界面确认的独立批量结果页。

## 复用测试文件

格式矩阵文件位于：

```text
tests/fixtures/format_matrix/
```

错误态文件位于：

```text
tests/fixtures/error_cases/
```

这些文件作为后续回归测试固定资产复用。

## 真实 E2E 覆盖

测试文件：

```text
tests/e2e/web_preview_real_backend.spec.mjs
```

运行命令：

```bash
npm run test:e2e:real
```

结果：`20 passed, 1 skipped`

覆盖场景：

| 页面 | 场景 | 输入 | 覆盖点 |
|---|---|---|---|
| 纯人声评测 | DNSMOS 单文件音频 | `format_matrix.wav` | 上传、真实评测、模型维度、信号分析、完整表格、导出、重置 |
| 纯人声评测 | NISQA 单文件音频 | `format_matrix.mp3` | 模型切换、NISQA 五维度、信号分析、完整表格、导出、重置 |
| 纯人声评测 | DNSMOS 单文件视频 | `format_matrix.mp4` | 视频抽取音轨、trace 展示、真实评测、导出、重置 |
| 纯人声评测 | DNSMOS 双组对比 | `test1.wav`、`test2.wav` | A/B 上传、开始对比、排名、自由/基准模式、基准切换、导出、重置 |
| 纯人声评测 | NISQA 三组对比 | `format_matrix.wav`、`format_matrix.mp3`、`format_matrix.mp4` | 3 组对比、视频输入、NISQA 维度、排名、基准切换、导出、重置 |
| 综合音频分析 | AudioBox 单文件音频 | `format_matrix.mp3` | PQ/CE/CU/PC、信号分析、完整表格、trace、导出、重置 |
| 综合音频分析 | AudioBox 单文件视频 | `format_matrix.mp4` | 视频抽取音轨、真实分析、导出、重置 |
| 综合音频分析 | AudioBox 双组对比 | `test1.wav`、`test2.wav` | 推荐摘要、排名、模型/信号/完整表格页签、基准切换、导出、重置 |
| 综合音频分析 | AudioBox 三组视频对比 | `format_matrix.mp4`、`format_matrix.mov`、`format_matrix.mkv` | 3 组视频对比、抽取音轨、排名、基准切换、导出、重置 |
| 历史 | 单文件任务 | 真实上传结果 | 历史卡片、文件名、模型名、场景文本、详情 |
| 历史 | 对比任务 | 真实对比结果 | 历史卡片、对比场景、详情 |
| 历史 | 筛选 | 历史数据 | 全部、纯人声评测、综合音频分析筛选 |
| 设置 | 默认纯人声模型 | 设置页 + 新上传 | 设置持久化并影响后续上传 |
| 设置 | trace 开关 | 设置页 + 新上传 | trace 开关持久化并影响结果展示 |
| 设置 | 预处理开关 | 设置页 + 异常上传 | 关闭自动预处理后的真实错误态 |
| 设置 | 默认对比模式 | 设置页 + 对比页 | 默认模式持久化 |
| 设置 | 导出格式 | 设置页 + 导出 | 导出格式持久化并影响下载文件名 |
| 错误态 | 空文件 | `empty_upload.wav` | 用户可见错误 |
| 错误态 | 无效音频 | `invalid_audio.wav` | 用户可见错误 |
| 错误态 | 仅 header WAV | `header_only.wav` | `empty_audio` 错误展示 |

## API/UT 覆盖

运行命令：

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests -q
```

结果：`136 passed`

重点覆盖：

- 音频格式矩阵：`wav/flac/mp3/aac/m4a/ogg`
- 视频格式矩阵：`mp4/mov/mkv/avi`
- ffmpeg 解码与视频抽取音轨 pipeline 标记
- 损坏 WAV 头但仍包含 PCM payload 的恢复路径
- header-only WAV、空文件、无效音频错误处理
- 短音频 LUFS 兜底，避免综合音频分析崩溃
- 真实上传 API 与真实对比 API 合同

## 前端 Mock/浏览器覆盖

运行命令：

```bash
npm run test:web-preview
npm run test:e2e
```

结果：

- `npm run test:web-preview`：`65 passed`
- `npm run test:e2e`：`8 passed`

重点覆盖：

- 页面初始状态
- 单文件上传、结果展示、导出、重置
- 对比上传、3+ 组添加、开始对比、基准切换
- 历史加载、空态、错误态、筛选、详情
- 设置持久化
- 上传中重置、错误后重试、切页状态隔离、切模型缓存与清理
- trace 中 `decode_audio` 展示为“解码音频”

## 明确排除

- 独立 batch result 页：当前 Web Preview 未确认该产品流。
- 500MB 大文件真实 E2E：真实浏览器回归成本高，保留在 API/mock 层覆盖。
- 损坏 WAV 头成功恢复的真实浏览器 E2E：该极短恢复样本在真实 DNSMOS 浏览器链路成本不稳定，恢复能力由 API/UT 覆盖；真实 E2E 中保留 skip 说明。
- `wmv/flv`：后端可识别扩展名，但当前产品文案未承诺支持，不纳入承诺格式矩阵。
- 无头 raw PCM：没有采样率/通道/位深参数，当前产品不支持。

## 后续缺口

- 如果后续新增独立批量结果页，需要补完整批量上传、批量结果、导出、历史链路 E2E。
- 如果产品确认 `wmv/flv` 或 raw PCM 支持，需要先更新产品文案和规范，再补 fixture 与 E2E/API 覆盖。
- 如果真实模型耗时继续上升，应把真实 E2E 拆成 nightly 全量与 PR 少量 smoke 两套。

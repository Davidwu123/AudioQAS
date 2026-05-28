# 真实后端 E2E QA 架构实施计划

> **给 agentic worker 的要求：** 实施本计划时必须使用 `superpowers:executing-plans`，并逐项按 checkbox（`- [ ]`）推进。

**目标：** 为 AudioQAS 建立第一版可发布级真实浏览器到真实后端的 E2E 测试套件，覆盖纯人声评测、综合音频分析、对比评测、历史、设置、导出/重置和关键错误态等用户可见功能，同时把全格式矩阵保留在更快、更稳定的 API/UT 层。

**架构：** 保留现有 mock Playwright 测试，用于快速覆盖浏览器状态机和 UI 分支。新增独立 real-backend Playwright 配置和脚本，启动真实 FastAPI 服务，用 Chromium 打开真实页面并上传已提交的 fixture。真实 E2E 只覆盖关键可见全链路；格式广度和底层边界继续由 API/UT 承担，避免浏览器测试变慢、变脆。

**技术栈：** Playwright、FastAPI/uvicorn、pytest、现有 AudioQAS web preview、`tests/fixtures/` 与 `tests/fixtures/format_matrix/` 下的固定测试文件。

---

## 覆盖策略

真实后端 E2E 必须覆盖：

- 真实浏览器点击、文件选择、上传
- 真实 `/api/evaluate/upload` 和 `/api/evaluate/compare-upload`
- 真实预处理和模型执行
- 用户可见结果展示
- 可见详情页签：模型维度、信号分析、完整表格
- 单文件和对比流程的导出、重置
- 关键历史与设置持久化链路
- 关键用户可见错误态

真实后端 E2E 不承担完整格式矩阵。格式广度保留在 API/UT：

- `tests/python/test_web_api.py::test_product_format_fixtures_upload_and_preprocess`
- preprocessing 相关 unit tests

不新增独立 batch result 页测试，因为它不是当前确认的产品界面。必须测试 3+ 对比组，因为对比页明确支持新增 C/D/E/F 组。

---

### Task 1：真实后端 E2E 基础设施

**文件：**
- 修改：`audioqas/web/run_local.py`
- 新增：`playwright.real.config.mjs`
- 修改：`package.json`
- 可选修改：`README.md` 或 `CONTRIBUTING.md`，仅当需要补充命令文档时修改

- [x] **Step 1：让 `run_local` 支持测试配置**

通过环境变量控制 host、port、reload：

```python
host=os.environ.get("AUDIOQAS_WEB_HOST", "127.0.0.1")
port=int(os.environ.get("AUDIOQAS_WEB_PORT", "8000"))
reload=os.environ.get("AUDIOQAS_WEB_RELOAD", "1") != "0"
```

- [x] **Step 2：新增真实后端专用 Playwright 配置**

创建 `playwright.real.config.mjs`，要求：

- 只运行真实后端 E2E spec
- 使用 `baseURL: "http://127.0.0.1:8000"`
- 通过 `.venv/bin/python -m audioqas.web.run_local` 启动真实服务
- 设置：
  - `AUDIOQAS_WEB_RELOAD=0`
  - `AUDIOQAS_PREPROCESS_DIR=.tmp/e2e-real/preprocessed`
  - `AUDIOQAS_WEB_STATE_DIR=.tmp/e2e-real/web_state`
  - `AUDIOQAS_LOG_DIR=.tmp/e2e-real/log`

- [x] **Step 3：新增 npm 脚本**

新增：

```json
"test:e2e:real": "npx playwright test --config=playwright.real.config.mjs"
```

保留现有 `test:e2e`，继续作为 mock browser 快速测试。

### Task 2：纯人声评测页真实 E2E

**文件：**
- 新增或修改：`tests/e2e/web_preview_real_backend.spec.mjs`

- [x] **Step 1：DNSMOS 单文件纯人声全链路**

使用 `tests/fixtures/format_matrix/format_matrix.wav`。

用户路径：

1. 打开 `/`
2. 停留在 `纯人声评测`
3. 点击单文件上传卡片
4. 上传文件
5. 等待真实 `/api/evaluate/upload`
6. 断言结果区可见
7. 断言文件标题/摘要正确
8. 断言 DNSMOS 维度可见
9. 切到信号分析页签并断言表头/数值
10. 切到完整表格并断言行内容
11. 断言 trace 包含 DNSMOS
12. 点击导出并断言下载文件/内容
13. 点击重置并断言页面回到空状态

- [x] **Step 2：NISQA 单文件纯人声全链路**

使用 `tests/fixtures/format_matrix/format_matrix.mp3`。

额外要求：

- 上传前切换纯人声模型为 NISQA
- 断言 ffmpeg decode trace 包含 `解码音频`
- 断言 NISQA 维度 `OVRL / NOI / DIS / COL / LOUD`
- 断言导出、重置

- [x] **Step 3：DNSMOS 单文件纯人声视频全链路**

使用 `tests/fixtures/format_matrix/format_matrix.mp4`。

用户路径：

1. 打开 `/`
2. 停留在 `纯人声评测`
3. 保持 DNSMOS 模型
4. 点击单文件上传卡片
5. 上传视频文件
6. 等待真实 `/api/evaluate/upload`
7. 断言结果区可见
8. 断言文件标题/摘要使用视频文件名
9. 断言 trace 包含 `原始视频`、`抽取音轨`、DNSMOS
10. 断言 DNSMOS 维度可见
11. 切到信号分析页签并断言表头/数值
12. 切到完整表格并断言行内容
13. 断言导出、重置

- [x] **Step 4：DNSMOS 双组纯人声对比全链路**

使用：

- `tests/fixtures/test1.wav`
- `tests/fixtures/test2.wav`

用户路径：

1. 进入纯人声对比
2. 上传 A/B
3. 开始对比
4. 等待真实 `/api/evaluate/compare-upload`
5. 断言推荐摘要
6. 断言排名包含两个文件
7. 断言模型维度表
8. 切到信号表
9. 切到完整表格
10. 切换自由/基准模式
11. 切换基准 A/B
12. 断言导出
13. 断言重置

- [x] **Step 5：NISQA 三组纯人声对比全链路（包含视频输入）**

使用：

- `tests/fixtures/format_matrix/format_matrix.wav`
- `tests/fixtures/format_matrix/format_matrix.mp3`
- `tests/fixtures/format_matrix/format_matrix.mp4`

额外要求：

- 切换纯人声模型为 NISQA
- 新增 C 组
- 上传三组文件
- 第三组使用视频文件，断言 trace/完整表格中体现 `抽取音轨`
- 断言排名有三条
- 断言 NISQA 维度
- 至少切换两个基准组
- 断言导出、重置

### Task 3：综合音频分析页真实 E2E

**文件：**
- 新增或修改：`tests/e2e/web_preview_real_backend.spec.mjs`

- [x] **Step 1：AudioBox 单文件混合音频全链路**

使用 `tests/fixtures/format_matrix/format_matrix.mp3` 或 `format_matrix.wav`。

要求：

- 切到 `综合音频分析`
- 上传文件
- 断言 AudioBox 维度 `PQ / CE / CU / PC`
- 断言信号分析页签
- 断言完整表格
- 断言 trace
- 断言导出
- 断言重置

- [x] **Step 2：AudioBox 单文件视频全链路**

使用 `tests/fixtures/format_matrix/format_matrix.mp4`。

额外要求：

- 断言 trace 包含 `抽取音轨`
- 断言可见结果使用视频文件名
- 断言导出、重置

- [x] **Step 3：AudioBox 双组混合音频对比全链路**

使用：

- `tests/fixtures/test1.wav`
- `tests/fixtures/test2.wav`

要求：

- 切到 `综合音频分析`
- 进入对比
- 上传 A/B
- 开始对比
- 断言推荐摘要
- 断言排名
- 断言模型/信号/完整表格页签
- 断言基准切换
- 断言导出
- 断言重置

- [x] **Step 4：AudioBox 三组混合视频对比全链路**

使用：

- `tests/fixtures/format_matrix/format_matrix.mp4`
- `tests/fixtures/format_matrix/format_matrix.mov`
- `tests/fixtures/format_matrix/format_matrix.mkv`

要求：

- 新增 C 组
- 上传三个视频文件
- 断言抽取音轨信息在结果数据/完整表格中体现
- 断言排名有三条
- 断言基准切换
- 断言导出
- 断言重置

### Task 4：历史页真实 E2E

**文件：**
- 新增或修改：`tests/e2e/web_preview_real_backend.spec.mjs`

- [x] **Step 1：单文件任务进入历史**

完成一次真实单文件任务后：

- 进入 `历史`
- 断言最新卡片包含文件名、模型名、单文件场景文本
- 打开详情并断言模型/结果摘要可见

- [x] **Step 2：对比任务进入历史**

完成一次真实对比任务后：

- 进入 `历史`
- 断言最新卡片包含对比场景文本
- 断言 trace summary 包含组/文件信息
- 打开详情并断言对比详情可见

- [x] **Step 3：历史筛选**

创建一个纯人声任务和一个综合分析任务后，断言以下筛选生效：

- 全部
- 纯人声评测
- 综合音频分析

### Task 5：设置页真实 E2E

**文件：**
- 新增或修改：`tests/e2e/web_preview_real_backend.spec.mjs`

- [x] **Step 1：默认纯人声模型持久化**

将默认纯人声模型从 DNSMOS 切换到 NISQA，刷新页面，断言 NISQA 仍被选中，并且新的纯人声上传使用 NISQA。

- [x] **Step 2：trace 开关影响结果展示并持久化**

关闭 trace，运行一次真实上传，断言 trace 区块隐藏；刷新后断言设置仍保持关闭。

- [x] **Step 3：预处理开关影响真实上传**

至少覆盖：

- 关闭视频抽音轨后上传视频，断言出现可读错误
- 关闭单声道转换后上传 stereo fixture，断言出现可读错误
- 关闭重采样后上传非目标采样率 fixture，断言出现可读错误

- [x] **Step 4：默认对比模式持久化**

切换默认对比模式，刷新页面，打开新的对比页，断言默认模式生效。

- [x] **Step 5：导出格式持久化**

切换导出格式，断言后续导出行为符合 JSON / CSV / JSON+CSV 设置。

### Task 6：错误态真实 E2E

**文件：**
- 新增或修改：`tests/e2e/web_preview_real_backend.spec.mjs`
- 可选新增：`tests/fixtures/error_cases/AGENTS.md`
- 可选新增：需要固定复用时提交小型错误 fixture

- [x] **Step 1：空文件上传错误**

使用一个很小的固定空文件 fixture，或在测试输出目录中创建空文件。断言用户可见错误面板展示空文件错误。

- [x] **Step 2：无效音频上传错误**

使用小型无效 `.wav` fixture 或测试输出文件。断言展示无效音频可读文案。

- [x] **Step 3：仅 header 的 WAV 错误**

使用测试内构造字节或小型固定 fixture。断言 `empty_audio` 被展示给用户。

- [x] **Step 4：损坏 WAV 头恢复成功可见**

该场景保留在 API/UT 层：真实 E2E 中保留 `test.skip` 说明，避免极短 damaged-header 样本进入真实 DNSMOS 后超出浏览器用例成本。

不要真实创建 500MB 文件测试文件大小限制，该场景保留在 API/mock browser 测试中。

### Task 7：Mock Browser 覆盖补齐

**文件：**
- 修改：`tests/web/web_preview_user_flow.test.mjs`
- 修改：`tests/web/web_preview_user_flow_real.test.mjs`

- [x] **Step 1：状态机补齐**

用 mock browser/jsdom 测试覆盖：

- uploading -> error -> retry
- uploading -> reset
- 对比部分上传 -> ready
- done -> reset
- 页面切换后的状态隔离

- [x] **Step 2：易竞态交互补齐**

用 mock 测试覆盖：

- 快速连续点击上传
- 上传后切页
- 结果完成后切模型
- 对比开始前切模型

### Task 8：验证

**文件：**
- 除非验证暴露真实问题，否则不新增源代码修改

- [x] **Step 1：真实后端 E2E 聚焦验证**

运行：

```bash
npm run test:e2e:real
```

- [x] **Step 2：现有 mock/browser 验证**

运行：

```bash
npm run test:web-preview
npm run test:e2e
```

- [x] **Step 3：Python/API 验证**

运行：

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests -q
```

- [x] **Step 4：QA 报告更新**

在 `meta/` 下更新或新增简短 QA 报告，列出：

- 已覆盖的真实 E2E 场景
- 已覆盖的 API/UT 场景
- 明确排除的场景及原因
- 实施过程中发现的后续缺口

# AudioQAS

AudioQAS 当前仓库主线是网页端产品预览，不再以旧桌面 App 文档为中心。

当前状态以 `web-preview` 为准：前端预览、最小 Web API、本机运行入口和对应测试已经接通。

核心文件：

- `design/web-preview.html`
- `design/web-preview-data.js`
- `design/web-preview-app.js`

核心文档：

- `docs/web-product-spec.md`：唯一产品/需求文档
- `docs/web-acceptance-checklist.md`：当前网页端验收清单
- `design/DESIGN.md`：唯一设计系统文档
- `AGENTS.md`：唯一 agent 工作说明

运行与验证：

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install pytest
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests -q
npm run test:web-preview
```

本机启动网页端预览与 API：

```bash
.venv/bin/python -m audioqas.web.run_local
```

启动后访问：

```text
http://127.0.0.1:8000
```

当前页面完成度：

- `纯人声评测`
  - `单文件测评` 已接入真实上传评测
  - `对比评测` 已接入真实对比上传
  - `DNSMOS / NISQA` 结果、信号分析、追溯、详细表格已联动
- `综合音频分析`
  - `单文件分析` 已接入真实上传评测
  - `对比分析` 已接入真实对比上传
  - `AudioBox Aesthetics` 结果、信号分析、追溯、详细表格已联动
- `历史`
  - 已接入 `/api/history`
  - 已支持真实写入、真实读取、空态和错误态
  - 切到历史页时会自动刷新最新列表
- `设置`
  - 已接入 `/api/settings`
  - `预处理追溯` 与 `默认对比模式` 已接入真实持久化
  - 刷新页面后设置状态会恢复

当前本机 API 入口：

- `GET /`
- `GET /api/health`
- `GET /api/bootstrap`
- `GET /api/navigation`
- `GET /api/models`
- `GET /api/signal-metrics`
- `GET /api/history`
- `GET /api/history/{item_id}`
- `GET /api/settings`
- `POST /api/evaluate/single`
- `POST /api/evaluate/batch`
- `POST /api/evaluate/compare`
- `POST /api/evaluate/upload`
- `POST /api/evaluate/upload-batch`
- `POST /api/evaluate/compare-upload`
- `POST /api/settings`

桌面端遗留实现说明：

- 当前仓库主线已经切到网页端
- `audioqas/` 下仍保留一批旧 PySide6 桌面实现，仅作为历史实现存在
- 后续如果确认不再保留桌面端，优先删除：
  - `audioqas/app.py`
  - `audioqas/ui/*`
  - `audioqas/core/history.py`
  - `tests/test_ui.py`
  - `requirements.txt` 中桌面/UI 相关依赖

# Repository Layout

更新时间：2026-05-22

本文件说明 AudioQAS 当前仓库的目录职责，避免源码、文档、设计资产、内部记录和运行产物混在一起。

## 顶层目录职责

### `audioqas/`

Python 源码主目录。

包含：

- 核心预处理与模型调用
- Web API
- 本地运行时逻辑
- 运行时前端静态资源

关键子目录：

- `audioqas/core/`
- `audioqas/models/`
- `audioqas/web/`
- `audioqas/logging/`

### `audioqas/web/static/`

当前网页端运行时前端资产。

包含：

- `web-preview.html`
- `web-preview-data.js`
- `web-preview-app.js`

这是当前页面行为和渲染的真实运行时来源。

### `docs/`

公开文档目录。

当前包含：

- `docs/web-product-spec.md`
- `docs/web-acceptance-checklist.md`
- `docs/design-system.md`
- `docs/design-system-detailed.md`
- `docs/repository-layout.md`

外部用户应优先阅读这里，而不是内部工作流记录。

### `design/`

设计资产目录。

当前只保留：

- `design/design-tokens.json`

该文件当前是设计参考资产，不是运行时直接读取的配置源。

### `tests/`

测试源码目录。

当前按职责拆分为：

- `tests/python/`
- `tests/web/`
- `tests/e2e/`
- `tests/fixtures/`
- `tests/helpers/`

### `meta/`

内部项目记录目录。

包含：

- 内部计划
- 过程 spec
- 内部 todo

这些内容不属于公开仓库主入口。

### `.tmp/`

本地运行产物目录。

当前可能包含：

- `.tmp/preprocessed/`
- `.tmp/web_uploads/`
- `.tmp/web_state/`
- `.tmp/log/`
- `.tmp/test-results/`

这些都属于可重建或本地状态文件，不是源码。

## 目录边界规则

- 运行时代码不应继续回流到 `design/`
- 公开文档不应继续回流到 `meta/`
- 测试输出不应放入 `tests/`
- 本地运行产物统一收敛到 `.tmp/`

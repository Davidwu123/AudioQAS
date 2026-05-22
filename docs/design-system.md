# AudioQAS Design System

更新时间：2026-05-22

本文件是 AudioQAS 的公开设计系统入口文档。

当前设计系统服务于 AudioQAS 网页端运行时与预览界面，重点关注：

- 页面信息层级
- 组件结构一致性
- 模型说明与结果表达方式
- 对比、历史、设置等页面的交互语义

## 设计资产位置

- 设计系统说明：`docs/design-system.md`
- 设计 token 参考资产：`design/design-tokens.json`
- 运行时前端资产：
  - `audioqas/web/static/web-preview.html`
  - `audioqas/web/static/web-preview-data.js`
  - `audioqas/web/static/web-preview-app.js`

说明：

- `design/design-tokens.json` 当前作为设计参考资产保留
- 运行时前端并不会直接读取该 JSON 文件
- 当前页面样式的实际来源仍然是 `audioqas/web/static/web-preview.html` 中的 CSS 变量与样式定义

## 设计目标

- 在 PC 浏览器中建立专业音频工具气质
- 明确区分 `纯人声评测` 与 `综合音频分析`
- 让结果、对比、追溯与历史结构保持一致
- 避免“视觉上能点、行为上不自洽”的伪交互

## 当前边界

- 仅支持 PC 浏览器
- 一级页面固定为：
  - `纯人声评测`
  - `综合音频分析`
  - `历史`
  - `设置`
- 详细数据固定拆分为：
  - `模型维度`
  - `信号分析`
  - `完整表格`

## 当前说明

`docs/design-system-detailed.md` 作为当前更完整的设计系统细节说明。

在仓库结构继续收口之前：

- `docs/design-system.md` 作为公开入口
- `docs/design-system-detailed.md` 作为当前详细设计规则来源

当前 `design/` 目录只保留设计资产文件，不再承担公开设计文档主入口职责。

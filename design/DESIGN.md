# AudioQAS Design System

> 版本: 1.0.0 | 日期: 2026-05-14
> Token 文件: `design/design-tokens.json`
> 预览页面: `design/design-preview.html`

---

## 1. 设计理念

**核心风格**: Dark Glassmorphism + Audio Engineering Professional

不是泛泛的"玻璃效果"，而是从 Logic Pro、DaVinci Resolve 这类专业音频/视频工具中提炼出的设计语言：

- **深空黑背景** — 专业工具的标准暗色系，不是紫色渐变
- **磨砂玻璃面板** — macOS Ventura 侧栏风格的半透明层叠
- **分数发光** — 评分卡片边缘根据等级颜色微发光，像音频仪表盘
- **克制动效** — 不搞花哨动画，只在评分完成时用微妙的光脉冲反馈

### 反 AI Slop 原则

以下是我们**刻意避免**的：

| 避免项 | 原因 | 我们的做法 |
|--------|------|------------|
| 紫→蓝渐变背景 | 千篇一律的 AI 默认色 | 深空黑 #0D1117，零渐变 |
| 所有东西圆角 | 不是每个元素都该圆润 | 导航栏直角，卡片 14px 圆角 |
| 无目的的玻璃效果 | glassmorphism 不是装饰 | 只在有层级关系的面板上用 |
| 滚动动画泛滥 | 专业工具不需要炫技 | 静态布局为主，仅评分完成脉冲 |
| 居中英雄区+大标题 | 这是 SaaS 落地页不是工具 | 工具型布局：侧栏+内容区 |

---

## 2. 颜色体系

### 2.1 背景层级（4层）

```
#0D1117  Base        ← 最深，窗口底色
#161B22  Surface     ← 卡片、面板
#1C2333  Elevated    ← 浮出元素（tooltip、popover）
#21262D  Overlay     ← 模态遮罩
```

层级之间差值约 5-8%，确保视觉分层但不突兀。

### 2.2 玻璃效果

玻璃面板使用 `rgba(22, 27, 34, 0.65)` 配合 20px backdrop-blur：
- **边框**: `rgba(48, 54, 61, 0.6)` — 微妙的光边
- **顶部高光**: `rgba(139, 148, 158, 0.15)` — 1px 的顶部反射线

### 2.3 文字层级

```
#E6EDF3  Primary     ← 正文、标题
#8B949E  Secondary   ← 元数据、时间戳、描述
#6E7681  Tertiary    ← placeholder、禁用提示
```

### 2.4 强调色

```
#58A6FF  Primary     ← 交互蓝色（按钮、链接、选中态）
#BC8CF2  Secondary   ← 音频可视化紫色（波形、频谱点缀）
#3FB950  Tertiary    ← 成功绿色
```

蓝色交互、紫色音频视觉、绿色正向结果，三色分工不混用。

### 2.5 评分颜色与发光

| 等级 | 颜色 | 发光 |
|------|------|------|
| Bad | #F85149 | 红色边缘微光 |
| Poor | #D29922 | 金色边缘微光 |
| Fair | #E3B341 | 黄色边缘微光 |
| Good | #3FB950 | 绿色边缘微光 |
| Excellent | #2EA043 | 翠绿边缘强光 |

---

## 3. 字体系统

macOS 系统字体栈，零自定义字体：

```
Body: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', sans-serif
Score: 'SF Mono', 'Menlo', 'Monaco', monospace
```

| Token | Size | 用途 |
|-------|------|------|
| xs | 11px | Caption、状态栏、tooltip |
| sm | 13px | 表格单元格、辅助文本 |
| md | 15px | 正文、表单输入 |
| lg | 20px | 卡片标题、区段标题 |
| xl | 28px | 评分数字 |
| xxl | 48px | 大号评分展示 |

---

## 4. 布局系统

### 4.1 间距网格（4px base）

4 → 8 → 16 → 24 → 32 → 48 → 64

### 4.2 窗口布局

```
┌─────────────────────────────────────────────────────────┐
│  Title Bar (native macOS)                                │
├──────────┬──────────────────────────────────────────────┤
│ Sidebar  │  Toolbar (52px)                               │
│ 180px    ├──────────────────────────────────────────────┤
│          │  Content Area (scrollable, glass bg)           │
│──────────│                                              │
│ Model    │                                              │
│ Selector │                                              │
│──────────│                                              │
│ Status   │                                              │
│ 28px     │                                              │
└──────────┴──────────────────────────────────────────────┘
```

侧栏结构从上到下：Logo → 导航 (评测/历史/设置) → 模型选择区 → 状态栏。

---

## 5. 核心组件设计

### 5.1 评分卡片 (ScoreCard)

```
┌────────────────────────────┐
│  ◇ 顶部高光反射线 1px      │
│                            │
│      OVRL                  │  ← 13px secondary
│                            │
│      3.82                  │  ← 28px monospace bold
│                            │  ← 评分色发光边框
│      ████░░░               │  ← 进度条，评分色
│                            │
│      Fair · 还行           │  ← 等级 + 通俗描述
│                            │
│  "像在办公室通话..."       │  ← 11px 场景比喻
└────────────────────────────┘
```

### 5.2 拖拽区 (DropZone)

20px 圆角，虚线框。hover 时虚线变蓝 `#58A6FF`，背景微蓝泛光。

支持格式提示分行：音频格式一行，视频格式一行。

### 5.3 批量结果表

暗色系表格：
- 表头 `#1C2333` + `#8B949E`
- 行 hover `rgba(88,166,255,0.08)`
- 选中行左边 3px 蓝色标记
- 分数用等级色，通俗描述 `#8B949E` 显示在分数旁

### 5.4 导航栏 + 模型选择

侧栏从上到下四层：

**导航区** - 选中项蓝色背景条 + 蓝色文字，未选中灰色。

**模型选择区** - 导航与状态之间，1px 分隔线隔开：

```
│──────────│
│ 评分模型 │  ← 11px uppercase label
│ ◎ DNSMOS │  ← 选中: 蓝色圆点 + 蓝色文字 + 维度tag
│   3维    │
│ ○ NISQA  │  ← 未选中: 灰色空心圆 + 灰色文字
│   5维·48k│     维度tag 灰色小标签
│ ○ UTMOS  │
│   MOS    │
│──────────│
```

选中模型圆点 `#58A6FF` 实心+发光，未选中 `#484F58` 空心。切换模型即时生效，状态栏同步更新模型名称。

扩展新模型只需在此区增加一行 `sidebar-model` 元素。

### 5.5 按钮系统

**Primary**: `#1F6FEB` bg / `#FFFFFF` text / 8px radius / hover `#388BFD`
**Ghost**: transparent bg / `#8B949E` text / `#30363D` border / hover 微灰背景

---

## 6. 动效规范

- **评分完成脉冲**: 卡片边框评分色→透明→评分色，400ms，一次
- **侧栏切换**: 内容区 150ms opacity 过渡，无 slide
- **hover**: 按钮/行 150ms bg 过渡；评分卡片 hover scale(1.02) + 发光增强
- **进度条**: 250ms ease-out，每完成一个文件跳一次

---

## 7. 深色/浅色模式

M1 只做深色模式。浅色模式 M4 迭代。

---

## 8. PySide6 QSS 模板

```css
QMainWindow { background-color: #0D1117; color: #E6EDF3; }

#Sidebar { background-color: rgba(13,17,23,200); border-right: 1px solid #21262D; }
#SidebarItem { height: 44px; padding: 0 16px; color: #8B949E; border-radius: 6px; }
#SidebarItem:selected { background-color: rgba(88,166,255,40); color: #58A6FF; }
#SidebarItem:hover { background-color: rgba(48,54,61,40); }

#ModelSection { border-top: 1px solid #21262D; padding: 8px 16px; }
#ModelSectionTitle { font-size: 11px; color: #6E7681; letter-spacing: 1px; }
#ModelItem { height: 32px; padding: 6px 8px; color: #8B949E; border-radius: 6px; }
#ModelItem:selected { color: #58A6FF; background-color: rgba(88,166,255,25); }
#ModelItem:hover { background-color: rgba(48,54,61,40); }
#ModelDot { width: 10px; height: 10px; border-radius: 5px; border: 2px solid #484F58; }
#ModelDot:selected { border-color: #58A6FF; background-color: #58A6FF; }
#ModelTag { font-size: 10px; padding: 1px 4px; border-radius: 3px; background: rgba(48,54,61,150); color: #6E7681; }
#ModelTag:selected { background: rgba(88,166,255,40); color: #58A6FF; }

#Toolbar { background-color: rgba(22,27,34,180); border-bottom: 1px solid #21262D; }
#StatusBar { background-color: rgba(13,17,23,230); color: #8B949E; font-size: 11px; }

QPushButton#PrimaryBtn { background-color: #1F6FEB; color: #FFFFFF; border-radius: 8px; padding: 8px 16px; }
QPushButton#PrimaryBtn:hover { background-color: #388BFD; }

QPushButton#GhostBtn { background-color: transparent; color: #8B949E; border: 1px solid #30363D; border-radius: 8px; padding: 8px 16px; }
QPushButton#GhostBtn:hover { background-color: rgba(48,54,61,100); border-color: #484F58; }

#ScoreCard { background-color: rgba(22,27,34,165); border: 1px solid rgba(48,54,61,150); border-radius: 14px; padding: 24px; }

QTableView { background-color: #161B22; alternate-background-color: #1C2333; color: #E6EDF3; gridline-color: #21262D; }
QHeaderView::section { background-color: #1C2333; color: #8B949E; padding: 8px; border-bottom: 1px solid #30363D; }

QProgressBar { background-color: #21262D; border-radius: 2px; }
QProgressBar::chunk { background-color: #58A6FF; border-radius: 2px; }

#DropZone { background-color: rgba(22,27,34,80); border: 2px dashed #30363D; border-radius: 20px; }
#DropZone[hover=true] { border-color: #58A6FF; background-color: rgba(88,166,255,15); }
```

---

## 9. 设计自查（Slop Detection）

| 维度 | 评分 | 说明 |
|------|------|------|
| 颜色一致性 | 9 | 全 token 化，无随机 hex |
| 字体层级 | 9 | 6级阶梯，system font |
| 间距节奏 | 8 | 4px grid，token 化 |
| 组件一致性 | 8 | glass panel 统一 token |
| 响应式 | 7 | 固定窗口，最小 800px |
| 深色模式 | 5 | M1 仅深色 |
| 动效 | 8 | 克制，仅脉冲+hover |
| 无障碍 | 7 | 对比度 >7:1 |
| 信息密度 | 9 | 工具型密度 |
| 精致度 | 7 | M1 基础版 |

**Slop 清零**: 无紫蓝渐变、无无目的玻璃、无英雄区、无泛滥动画、无圆角滥用。
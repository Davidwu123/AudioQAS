# AudioQAS 一键安装与启动设计

日期：2026-05-28

## 目标

在一台新电脑上，用户拉下代码后运行一个脚本，脚本自动完成必要环境检查、缺失依赖安装、模型资产准备、服务启动，并自动打开网页进入 AudioQAS 音频分析界面。

默认目标是“普通用户直接使用产品”，不安装测试相关依赖。测试依赖只有在用户显式传参时才安装。

## 入口

面向新电脑用户的推荐入口是一条命令：

```bash
curl -fsSL https://raw.githubusercontent.com/Davidwu123/AudioQAS/main/scripts/audioqas-install.sh | bash
```

带测试环境使用：

```bash
curl -fsSL https://raw.githubusercontent.com/Davidwu123/AudioQAS/main/scripts/audioqas-install.sh | bash -s -- --with-test
```

指定安装目录使用：

```bash
curl -fsSL https://raw.githubusercontent.com/Davidwu123/AudioQAS/main/scripts/audioqas-install.sh | bash -s -- --dir ~/workspace/AudioQAS
```

仓库已存在时，也可以直接使用仓库内脚本：

```bash
./scripts/audioqas-bootstrap
```

带测试环境使用：

```bash
./scripts/audioqas-bootstrap --with-test
```

只检查不安装使用：

```bash
./scripts/audioqas-bootstrap --check-only
```

## 两层脚本职责

### `scripts/audioqas-install.sh`

这是可通过 `curl | bash` 运行的 thin installer。

职责：

1. 检查 `git` 是否存在。
2. 如果 `git` 缺失，按平台自动安装 `git`。
3. clone AudioQAS 仓库到目标目录。
4. 如果目标目录已存在且是匹配 remote 的 AudioQAS git repo，则更新代码。
5. 如果目标目录已存在但不是 AudioQAS repo，停止并报错，避免覆盖用户目录。
6. 进入仓库目录后调用 `./scripts/audioqas-bootstrap`。
7. 将 `--with-test`、`--check-only`、`--dir` 之外的后续参数透传给 bootstrap。

默认目标目录规则：

1. 如果当前目录本身已经是 AudioQAS git repo，则直接在当前目录运行 `./scripts/audioqas-bootstrap`。
2. 如果当前目录下存在 `AudioQAS/` 且它是匹配 remote 的 AudioQAS git repo，则更新并使用 `./AudioQAS`。
3. 如果当前目录下不存在 `AudioQAS/`，则 clone 到 `./AudioQAS`。
4. 如果当前目录下存在 `AudioQAS/` 但不是 AudioQAS repo，则停止并报错，避免覆盖用户目录。
5. 如果用户传入 `--dir <path>`，则使用用户指定目录，并应用同样的 remote 校验和覆盖保护。

`audioqas-install.sh` 不承载 Python、ffmpeg、模型、Playwright 等安装逻辑，避免 curl 脚本过重、难 review、难维护。

### `scripts/audioqas-bootstrap`

这是仓库内主脚本。

职责：

1. 创建或复用 `.venv`。
2. 安装产品运行依赖。
3. 安装或复用 ffmpeg。
4. 准备模型资产和模型缓存。
5. 在 `--with-test` 模式下安装测试依赖。
6. 预热模型。
7. 启动服务并打开网页。

仓库内 bootstrap 不负责首次 git clone。首次获取代码由 thin installer 负责。

## 总体原则

1. 已有且版本满足的工具直接复用，不重复下载。
2. 缺失或版本不满足时自动安装，默认不反复询问。
3. 能安装到仓库本地的依赖优先安装到仓库本地。
4. 仓库本地无法解决的 OS 依赖，脚本自动走系统包管理器安装。
5. 每个安装步骤必须说明安装目的、安装位置、AudioQAS 内部使用场景。
6. 默认模式只安装运行产品所需依赖，不安装测试工具链。
7. `--with-test` 才安装 pytest、Node 测试依赖、Playwright 浏览器等测试相关内容。

## 目录布局

```text
.venv/
  bin/                         Python 虚拟环境可执行文件
  tools/
    ffmpeg/                    项目内 portable ffmpeg
    node/                      可选 portable Node
  model-cache/
    huggingface/               AudioBox / Hugging Face 缓存
    torch/                     Torch 相关缓存
  playwright-browsers/         仅 --with-test 模式安装
  bootstrap/
    downloads/                 临时下载目录，解压后清理
node_modules/                  仅 --with-test 模式安装
.tmp/
  web_uploads/                 运行时上传缓存
  preprocessed/                预处理输出
  web_state/                   历史与设置本地状态
  log/                         运行日志
```

`.venv/bootstrap/downloads/` 只作为临时目录，安装完成后删除下载压缩包，避免同一资产保留两份。

## 默认模式安装范围

默认模式面向只想打开网页做音频分析的用户。

| 依赖 | 安装目的 | 内部使用场景 | 默认安装/复用位置 |
|---|---|---|---|
| Python 3.10+ | 运行后端服务、模型推理、音频处理 | `audioqas.web.run_local`、FastAPI、DNSMOS/NISQA/AudioBox wrapper | 优先复用系统 Python；创建 `.venv` |
| Python runtime packages | 产品运行依赖 | `fastapi`、`uvicorn`、`torch`、`torchaudio`、`speechmos`、`nisqa`、`audiobox_aesthetics`、`soundfile`、`scipy`、`pyloudnorm` | `.venv/` |
| ffmpeg | 解码压缩音频、从视频提取音轨 | `mp3/aac/m4a` 解码，`mp4/mov/mkv/avi` 抽取音轨 | 系统版本满足则复用；否则 `.venv/tools/ffmpeg/` |
| DNSMOS 模型资产 | 纯人声 DNSMOS 评测 | 输出 `OVRL/SIG/BAK` | `speechmos` 包内 ONNX |
| NISQA 模型资产 | 纯人声 NISQA 评测 | 输出 `OVRL/NOI/DIS/COL/LOUD` | `audioqas/models/weights/nisqa.tar` |
| AudioBox 模型资产 | 综合音频分析 | 输出 `PQ/CE/CU/PC` | `.venv/model-cache/huggingface/` |
| OS 运行库 | 支撑 Python 包和本地服务运行 | `soundfile`、`torch`、AudioBox、浏览器打开等系统能力 | 系统包管理器自动安装必要缺口 |

默认模式不安装：

- `pytest`
- `npm` 依赖
- `node_modules/`
- Playwright test runner
- Playwright 浏览器

如果默认模式发现系统没有 Node/npm，不应报错，因为普通产品运行不依赖 Node/npm。

## `--with-test` 模式安装范围

`--with-test` 面向开发者或 CI 回归场景。

| 依赖 | 安装目的 | 内部使用场景 | 默认安装/复用位置 |
|---|---|---|---|
| pytest | Python/API/模型单元测试 | `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests -q` | `.venv/` |
| Node.js 18+ / npm | 运行前端 Node 测试和 Playwright | `npm run test:web-preview`、`npm run test:e2e` | 系统版本满足则复用；否则 `.venv/tools/node/` |
| Node packages | jsdom、Playwright test runner | DOM 级测试、浏览器 E2E | `node_modules/` |
| Playwright Chromium | 浏览器 E2E | `npm run test:e2e`、`npm run test:e2e:real` | `.venv/playwright-browsers/` |
| 浏览器 OS 依赖 | 支撑 Playwright Chromium 运行 | Linux headless browser runtime | 系统包管理器自动安装必要缺口 |

`--with-test` 模式安装完成后，可选择自动运行 smoke 验证，但不默认运行真实后端全量 E2E，因为真实模型链路耗时较长。

## 系统包管理器策略

脚本允许自动使用系统包管理器安装仓库本地无法解决的 OS 依赖，减少确认流程。

支持顺序：

1. macOS：优先使用 `brew`
2. Ubuntu / Debian：优先使用 `apt-get`
3. 其他系统：输出明确错误和手动安装建议

系统级安装只用于这些类别：

- thin installer 中缺失的 `git`
- Python/Node/ffmpeg 的基础工具缺失且无法下载 portable 版本
- Linux 下 Playwright Chromium 所需动态库
- 音频底层库缺失且 Python wheel 无法自带解决

脚本不得修改 shell profile，不得写入用户全局 PATH。运行时通过当前进程环境变量注入仓库本地工具路径。

## ffmpeg 策略

ffmpeg 可能体积较大，因此采用复用优先。

检查顺序：

1. 检查 `.venv/tools/ffmpeg/bin/ffmpeg`
2. 检查系统 `ffmpeg`
3. 如果版本满足 `>= 6.0`，直接复用
4. 如果缺失或版本不足，下载 portable ffmpeg 到 `.venv/tools/ffmpeg/`
5. portable 下载失败时，使用系统包管理器安装

运行服务时设置：

```bash
export PATH="$PWD/.venv/tools/ffmpeg/bin:$PATH"
```

检查内容：

- `ffmpeg -version`
- `ffprobe -version`
- 使用项目 fixture 或 lavfi 进行最小解码/抽取音轨 smoke

## 模型资产策略

### DNSMOS

目的：纯人声质量评测。

内部使用场景：`纯人声评测` 页面默认模型，输出 `OVRL/SIG/BAK`。

安装来源：`speechmos` Python 包自带 ONNX 权重。

检查方式：

- import `speechmos.dnsmos`
- 检查包内 `dnsmos_models/model_v8.onnx`
- 用极短 WAV 运行一次 DNSMOS smoke

### NISQA

目的：纯人声多维质量评测。

内部使用场景：`纯人声评测` 页面可选模型，输出 `OVRL/NOI/DIS/COL/LOUD`。

安装来源：项目内 `audioqas/models/weights/nisqa.tar`。

检查方式：

- 检查 `audioqas/models/weights/nisqa.tar` 存在
- import `nisqa.NISQA_model`
- 用极短 WAV 运行一次 NISQA smoke

### AudioBox

目的：综合音频分析。

内部使用场景：`综合音频分析` 页面，输出 `PQ/CE/CU/PC`。

安装来源：

- 默认使用 Hugging Face 模型 `facebook/audiobox-aesthetics`
- 缓存目录固定到 `.venv/model-cache/huggingface/`

运行时设置：

```bash
export HF_HOME="$PWD/.venv/model-cache/huggingface"
export TORCH_HOME="$PWD/.venv/model-cache/torch"
export XDG_CACHE_HOME="$PWD/.venv/cache"
```

检查方式：

- import `audiobox_aesthetics`
- 检查 Hugging Face cache 是否已有模型文件
- 缓存缺失时自动下载
- 用极短 WAV 运行一次 AudioBox smoke

如果网络不可用且缓存不存在，脚本应明确报错：

```text
AudioBox 模型资产缺失，且无法从 Hugging Face 下载。
请恢复网络后重试，或手动提供本地 checkpoint。
```

后续实现可以增加：

```bash
./scripts/audioqas-bootstrap --audiobox-ckpt /path/to/checkpoint.pt
```

## 脚本阶段

### 阶段 1：环境探测

输出当前系统、CPU 架构、Python、ffmpeg、可选 Node/npm、缓存状态。

示例：

```text
[system] macOS arm64
[python] Found Python 3.12.7, reuse for .venv creation.
[ffmpeg] Purpose: decode compressed audio and extract audio from video uploads.
[ffmpeg] Found system ffmpeg 7.1.1, reuse: /opt/homebrew/bin/ffmpeg
```

### 阶段 2：运行依赖安装

创建 `.venv`，安装产品运行依赖。

默认命令等价于：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
```

`--with-test` 时使用：

```bash
.venv/bin/python -m pip install -e ".[dev]"
```

### 阶段 3：工具安装

默认只处理 ffmpeg。

`--with-test` 时额外处理 Node/npm、`npm ci`、Playwright Chromium。

### 阶段 4：模型预热

生成或复用一个极短测试音频，依次预热：

1. DNSMOS
2. NISQA
3. AudioBox

预热目的不是评测质量，而是提前暴露 import、权重、缓存、底层库问题。

### 阶段 5：启动服务并打开网页

启动：

```bash
.venv/bin/python -m audioqas.web.run_local
```

打开：

```text
http://127.0.0.1:8000
```

打开浏览器方式：

- macOS：`open http://127.0.0.1:8000`
- Linux：`xdg-open http://127.0.0.1:8000`
- 无图形界面：只打印 URL

## 幂等性

每一步都必须可重复运行：

- `.venv` 已存在时复用
- Python 包满足时跳过或最小更新
- ffmpeg 版本满足时跳过
- AudioBox cache 已存在时跳过下载
- `node_modules` 与 lockfile 匹配时跳过 `npm ci`
- Playwright Chromium 已存在时跳过下载

脚本输出必须说明跳过原因。

## 错误处理

错误必须面向用户，不直接暴露底层堆栈作为唯一信息。

示例：

```text
[AudioBox] Failed.
Purpose: mixed-content analysis model for 综合音频分析.
Reason: Hugging Face model cache is missing and network download failed.
Next: reconnect network and rerun ./scripts/audioqas-bootstrap
```

## 文档更新

需要更新：

- `README.md`
- `CONTRIBUTING.md`
- `AGENTS.md`

README 中默认只给普通用户命令：

仓库地址：

```text
https://github.com/Davidwu123/AudioQAS
```

一键安装：

```bash
curl -fsSL https://raw.githubusercontent.com/Davidwu123/AudioQAS/main/scripts/audioqas-install.sh | bash
```

README 需要说明 `github.com/Davidwu123/AudioQAS` 是给人浏览的仓库页面，`raw.githubusercontent.com/Davidwu123/AudioQAS/...` 是给 `curl` 下载脚本原始内容使用的地址。

仓库已存在时再给：

```bash
./scripts/audioqas-bootstrap
```

开发者章节再给：

```bash
./scripts/audioqas-bootstrap --with-test
```

并列出默认模式不会安装测试相关依赖。

## 非目标

第一版不做：

- Windows 支持
- Docker 镜像
- 生产部署
- 后台 daemon/service 安装
- 修改 shell profile
- 默认运行真实后端全量 E2E

## 验收标准

1. 新电脑运行 `curl -fsSL https://raw.githubusercontent.com/Davidwu123/AudioQAS/main/scripts/audioqas-install.sh | bash` 后，能自动 clone 仓库、安装产品运行依赖、模型预热、服务启动和打开网页。
2. 默认模式不安装 Node/npm 测试链路、`node_modules`、Playwright 浏览器、pytest。
3. 运行 `./scripts/audioqas-bootstrap --with-test` 才安装测试相关依赖。
4. 已有依赖版本满足时，重复运行脚本会跳过重复下载。
5. 每个安装步骤日志都说明目的、安装位置、内部使用场景。
6. ffmpeg、DNSMOS、NISQA、AudioBox 都有明确检查和失败提示。
7. README/CONTRIBUTING/AGENTS 的安装命令一致，不再出现只安装 `pytest` 的不完整路径。
8. 目标目录已存在但不是 AudioQAS repo 时，thin installer 必须停止，不能覆盖或删除用户目录。

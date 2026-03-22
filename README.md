# AllahPan

家庭私有网盘 — 本地部署，支持 AI 语义搜索、桌面/Web 双前端、Cloudflare Tunnel 远程访问。

## 项目结构

```
AllahPan/
├── backend/              # FastAPI 后端（认证、文件、AI、系统、Tunnel）
├── frontend_desktop/     # PySide6 桌面端
├── frontend_web/         # Web 前端（静态页 + js，可由后端或独立脚本托管）
├── packaging/            # 打包辅助（如 PyInstaller runtime hook、macOS 构建脚本）
├── docs/                 # 其它说明文档
├── launcher.py           # 统一启动器（后端 + 桌面前端，与打包入口一致）
├── requirements.txt      # 根依赖（含 backend + desktop）
├── AllahPan.spec         # PyInstaller — Windows（目录型 dist/AllahPan/）
├── AllahPan-macOS.spec   # PyInstaller — macOS .app
├── AllahPan-Linux.spec   # PyInstaller — Linux
└── version.py
```

## 环境要求

- **Python 3.12**（建议与打包机一致）
- **Windows / macOS / Linux**（打包产物需在对应系统上构建）
- **Ollama**（若使用本地 AI 能力）：需单独安装并在本机运行，与是否打包无关

---

## 克隆与安装依赖

### Windows（PowerShell）

```powershell
git clone https://github.com/AfterMaxQ/AllahPan.git
cd AllahPan
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -U pip
pip install -r requirements.txt
```

（SSH：`git clone git@github.com:AfterMaxQ/AllahPan.git`）

### macOS / Linux（Bash）

```bash
git clone https://github.com/AfterMaxQ/AllahPan.git
cd AllahPan
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -r requirements.txt
```

若系统无 `python3.12`，可先安装后再执行（macOS 可用 `brew install python@3.12`）。

---

## 命令行分模块运行（不打包）

以下方式适合开发与调试：各终端均需 **先激活同一虚拟环境**（`activate` / `source .venv/bin/activate`）。

### 1. 仅启动后端（FastAPI）

在仓库根目录或 `backend` 下均可，只要 Python 能找到 `app` 包：

```powershell
# Windows / macOS / Linux 通用（在仓库根目录）
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- 默认 **API**：`http://127.0.0.1:8000/api/v1/...`
- 若后端已配置托管 `frontend_web`，浏览器访问 **`http://127.0.0.1:8000/`** 即可打开网页端（与 API 同端口）。
- 停止：对应终端 `Ctrl+C`。

### 2. 仅启动桌面前端（PySide6）

**必须先另开终端让后端已在运行**（见上一节），否则桌面端无法登录/拉列表。

```powershell
# Windows
cd frontend_desktop
python run.py
```

```bash
# macOS / Linux
cd frontend_desktop
python run.py
```

桌面端默认连接本机 API（具体以 `frontend_desktop/config.py` 及环境变量为准）。停止：`Ctrl+C`。

### 3. 仅启动「独立 Web 静态服务」（端口 3000）

适用于：希望 **页面固定从 `http://localhost:3000` 打开**，而后端仍在 **8000** 的场景。

1. **终端 1**：按上文启动后端（`uvicorn`，端口 8000）。
2. **终端 2**：

```powershell
# Windows
cd frontend_web
python run.py
```

```bash
# macOS / Linux
cd frontend_web
python run.py
```

- 脚本会在 **3000** 端口提供静态文件，并把以 **`/api/`** 开头的请求 **反向代理** 到本机后端（默认 `http://127.0.0.1:8000`）。
- 若后端不在本机 8000，可在启动前设置环境变量 **`ALLAHPAN_API_UPSTREAM`**（无尾斜杠），例如：`http://192.168.1.10:8000`。
- 也可在 `index.html` 的 meta **`allahpan-api-base`** 或页面里设置 `window.ALLAH_PAN_API_BASE` 指向你的 API 根路径（以 `/api/v1` 结尾）。详见 `frontend_web/js/api.js` 中 `getBaseUrl()`。

### 4. 三终端组合速查

| 终端 | 目录 | 命令 | 说明 |
|------|------|------|------|
| A | `backend` | `uvicorn app.main:app --host 0.0.0.0 --port 8000` | 必需 |
| B | `frontend_desktop` | `python run.py` | 桌面客户端 |
| C | `frontend_web` | `python run.py` | 可选；浏览器用 `:3000` |

若只使用浏览器且接受 **单端口**：通常 **仅终端 A** 即可，直接打开 `http://本机IP:8000/`。

---

## 一键启动：命令行从项目根目录启动后端 + 桌面前端

开发或日常在本机使用时，可在 **仓库根目录**（与 `launcher.py` 同级）用 **一条命令** 同时启动 **FastAPI 后端** 与 **PySide6 桌面客户端**（无需再开两个终端分别 `uvicorn` / `python run.py`）。

### 操作步骤

1. **进入项目根目录**（克隆后的 `AllahPan` 文件夹）。
2. **激活虚拟环境**（与上文「克隆与安装依赖」一致）。
3. **执行一键启动**：

**Windows（PowerShell，已在根目录且已 `activate`）：**

```powershell
python launcher.py
```

**macOS / Linux（Bash/zsh，已在根目录且已 `source .venv/bin/activate`）：**

```bash
python3 launcher.py
```

许多 macOS 终端里 **没有名为 `python` 的命令**（会出现 `zsh: command not found: python`），此时请始终使用 **`python3`**，或 **不依赖 activate**、直接指定虚拟环境里的解释器（最稳妥）：

```bash
./.venv/bin/python3 launcher.py
```

若刚创建/修复过 `.venv`，zsh 仍报错可尝试执行一次 `rehash`。若系统里 `python3` 不是 3.10+，请只用 `./.venv/bin/python3`，确保走本仓库要求的 Python 版本。

### 启动后会发生什么

- 启动器会先检查 `backend/app`、`frontend_desktop` 等目录是否存在；若本机 **未运行 Ollama**，会尝试执行 `ollama serve`（可用 `--no-ollama` 跳过）。
- **后端**：子进程运行 `uvicorn app.main:app`（默认 `0.0.0.0`、端口见环境变量或 `~/.allahpan/server_settings.json`）；若首选端口被占用，会自动递增端口（除非设置 `ALLAHPAN_STRICT_PORT=1`）。
- **桌面端**：子进程运行 `frontend_desktop/run.py`，并通过环境变量 `ALLAHPAN_HOST` / `ALLAHPAN_PORT` 连接刚启动的后端。
- **停止**：在运行 `launcher.py` 的终端按 **`Ctrl+C`**，会一并清理已拉起的子进程。

### 常用子命令（均在项目根目录执行）

下表中的 `python` 在 **macOS** 上请按需换成 **`python3`** 或 **`./.venv/bin/python3`**（与上一节一致）。

| 命令 | 说明 |
|------|------|
| `python launcher.py` | 启动后端 + 桌面（默认） |
| `python launcher.py --backend` | 仅启动后端（适合只要 API / 浏览器走 `:8000`） |
| `python launcher.py --gui` | 仅启动桌面（需后端已在运行） |
| `python launcher.py --status` | 查看 API / GUI / Ollama 状态 |
| `python launcher.py --stop` | 停止由启动器记录的服务 |
| `python launcher.py --no-ollama` | 不自动启动 Ollama |
| `python launcher.py -v` | 更详细的日志输出 |

日志文件：`~/.allahpan/logs/launcher.log`（Windows 为用户目录下 `.allahpan\logs\launcher.log`）。

### 与「仅浏览器」的区别

一键启动器拉起的是 **桌面客户端**。若你 **只需要浏览器** 访问网盘页，且接受 **单端口**，通常只需启动后端并打开 `http://<本机IP>:8000/`（见上文「仅启动后端」及「Web 前端 → 后端托管」）。此时可用 `python3 launcher.py --backend`（或 `./.venv/bin/python3 launcher.py --backend`）代替完整一键。

### 其它说明

- 行为与 **未打包** 场景下「后端子进程 + 桌面子进程」一致；**PyInstaller 打包后的 .app / exe** 则在单进程内起后端线程 + 主线程 GUI（与根目录脚本路径不同，此处不展开）。
- **监听地址、端口、Ollama** 可在桌面 **设置 → 本机服务与局域网 Web** 中修改，写入 `~/.allahpan/server_settings.json`（Windows 为用户目录下同名路径），**完全退出应用后重新打开**生效。
- 局域网访问时，防火墙需放行对应 **TCP 端口**。

---

## Windows：打包生成 exe（PyInstaller）

### 前置条件

- 已在 **Windows** 上使用 **本仓库相同 Python 3.12** 创建虚拟环境并执行 `pip install -r requirements.txt`。
- 安装打包工具：`pip install PyInstaller`（建议 `PyInstaller>=6`）。
- 可选：将应用图标放到 **`build/AllahPan.ico`**、`build/AllahPanVersion.txt`（版本资源）；若无，仍可按默认图标打包。

### 构建步骤

在仓库根目录、**已激活 `.venv`**：

```powershell
cd F:\path\to\AllahPan
.\.venv\Scripts\activate
pip install PyInstaller
pyinstaller AllahPan.spec
```

- **不要**在未激活虚拟环境时用「系统全局 Python」打包，否则容易缺依赖或 Qt 版本不一致。
- 构建时间较长，属正常现象。

### 产物位置与运行方式

- 输出目录：**`dist\AllahPan\`**
- 可执行文件：**`dist\AllahPan\AllahPan.exe`**
- 请 **整份拷贝 `dist\AllahPan\` 文件夹** 到目标电脑（需保持 `_internal` 等子目录相对路径不变），再双击 `AllahPan.exe`。
- 部分杀毒软件可能误报「未签名 exe」，需自行添加信任或使用代码签名证书。

### 清理后重打包（可选）

若需干净构建，可先删除旧的 `build\`、`dist\` 再执行 `pyinstaller AllahPan.spec`（注意：会删除当前未备份的构建输出）。

### 关于将 `dist/` 提交到 GitHub

`dist` 内可能含 **超过 GitHub 单文件 100MB 限制** 的依赖（如 Qt WebEngine），本仓库 **默认在 `.gitignore` 中忽略 `dist/`**。分发安装包建议使用 **网盘 / GitHub Releases 附件 / 公司制品库**，而不是直接 `git push` 整个 `dist`。

---

## macOS：打包生成 .app（PyInstaller）

### 重要说明

- **必须在 macOS 上执行** PyInstaller 的 `BUNDLE`，无法在 Windows 上交叉生成 `.app`。
- 在 **Apple Silicon（M 系列）** 上打包得到 **arm64**；在 **Intel Mac** 上打包得到 **x86_64**。给哪类机器用，尽量在对应架构上构建。

### 前置条件

```bash
cd /path/to/AllahPan
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install PyInstaller
```

可选：将 **`AllahPan.icns`** 放到 **`build/AllahPan.icns`**（也可放到 `packaging/AllahPan.icns`，构建脚本会尝试复制到 `build/`）。

### 构建方式一：一键脚本（推荐）

```bash
chmod +x packaging/build_macos_app.sh
./packaging/build_macos_app.sh
```

### 构建方式二：手动

```bash
source .venv/bin/activate
pyinstaller AllahPan-macOS.spec
```

### 产物与首次运行

- 应用包路径：**`dist/AllahPan.app`**
- 运行：`open dist/AllahPan.app`
- 若提示无法打开或来自未识别开发者，可尝试：

```bash
xattr -cr dist/AllahPan.app
```

再双击或通过「系统设置 → 隐私与安全性」放行。对外分发需 Apple 开发者账号进行 **签名与公证**，步骤见 Apple 官方文档。

### DMG（可选）

`.dmg` 用于分发：映像内应包含 **`AllahPan.app`** 以及指向系统 **`/Applications`** 的替身，用户拖入即可完成安装。

一键生成（需先成功构建 `.app`）：

```bash
chmod +x packaging/build_macos_dmg.sh
./packaging/build_macos_dmg.sh
```

或在构建应用时顺带生成 DMG：

```bash
BUILD_DMG=1 ./packaging/build_macos_app.sh
```

**注意**：应用包目录名必须是 **`AllahPan.app`**（带 `.app` 后缀）。若只有名为 `AllahPan` 的文件夹（无后缀），macOS 不会把它当应用程序，会出现空白图标、双击无反应；请使用当前仓库中的 `AllahPan-macOS.spec` 重新打包。

---

## Linux 打包（简述）

在 Linux 上激活虚拟环境后：

```bash
pip install PyInstaller
pyinstaller AllahPan-Linux.spec
```

具体产物布局以 spec 内 `COLLECT`/`EXE` 配置为准。

---

## 配置说明

- **API 根路径**：开发时常见为 `http://localhost:8000`；Web 独立 3000 端口时由 `api.js` / 环境变量决定。
- **存储目录**：默认 `~/Documents/AllahPan/files`（Windows 为「文档\AllahPan\files」），可通过环境变量 **`ALLAHPAN_STORAGE_DIR`** 或桌面端设置修改。
- **首次使用**：在 Web 或桌面端 **注册账号** 后登录。

---

## 使用教程：桌面前端（PySide6）

### 启动与连接后端

- 单独运行桌面端前，**必须先启动后端**（见上文「仅启动后端」）。
- 默认 API 为 `http://localhost:8000`；连接其它机器或端口时设置环境变量 **`ALLAHPAN_HOST`**、**`ALLAHPAN_PORT`** 后再运行 `frontend_desktop/run.py`（与 `frontend_desktop/config.py` 一致）。

### 登录与主界面

- **首次使用**：在登录页切换到注册，填写用户名、密码、邮箱后注册并登录。
- **布局**：左侧为分类导航（全部 / 图片 / 文档 / 视频 / 音频 / 等），中间为文件区，顶部为搜索栏；可在 **网格视图** 与 **列表视图** 间切换（大图标 vs 多列信息）。

### 文件：查看、添加、下载、删除与预览

- **添加（上传）**：点击工具栏「上传」，或 **将文件/文件夹拖入窗口**（支持递归扫描文件夹）；上传队列最多 **3 路并发**，底部可查看进度。
- **查看列表**：按左侧分类筛选；支持在存储目录下的 **子目录** 中浏览（与后端 `files/list?path=` 一致）。
- **下载 / 删除 / 重命名等**：选中文件后使用 **右键菜单**（下载、预览、复制链接、删除等）。
- **预览**：图片可直接预览；其它类型会尝试用 **系统默认程序** 打开。
- **搜索**：搜索栏可在 **文件名搜索** 与 **AI 语义搜索** 之间切换（自然语言描述，如「去年的旅行照片」）。

### 设置（⚙️）

- **外观**：浅色 / 深色 / 跟随系统。
- **本机服务与局域网 Web**：修改后端监听地址、端口、Ollama 等；保存后写入 **`~/.allahpan/server_settings.json`**（Windows 为用户目录下 `.allahpan`），**需完全退出应用再启动** 才生效。局域网访问时请在防火墙放行对应 **TCP 端口**。
- **存储路径**：可打开「修改存储路径」对话框选择目录；修改后需自行迁移已有文件并重启（与后端 `ALLAHPAN_STORAGE_DIR` 逻辑一致）。
- **远程访问**：见下文「Cloudflare Tunnel」。
- **系统服务**：**Ollama 引擎** 可在设置中尝试启动/停止（由后端 Ollama 管理器代理）；**开机自启** 按系统写入启动项。
- **日志**：「查看系统日志」读取 **`~/.allahpan/logs/`** 下最新 `.log` 文件。

### 运维看板（📊）

- 左侧导航进入 **「运维看板」**（`frontend_desktop/pages/ops_dashboard_page.py`）。
- **流量**：对接 `GET /api/v1/system/metrics/traffic`，展示按 API 分类聚合的每分钟请求趋势（统计自当前后端进程启动以来）。
- **数据**：对接 `GET /api/v1/system/metrics/data-volumes`，展示磁盘与 **SQLite / Chroma / 数据目录 / 存储目录** 等体积及路径说明。
- **日志监看**：对接 `GET /api/v1/system/logs/tail`，定时刷新最新日志尾部。
- 若图表空白或报错，请确认后端已更新并包含上述接口，且当前账号已登录。

### Cloudflare Tunnel（远程访问）

1. **安装 cloudflared**（宿主机上）：例如 Windows `winget install cloudflared`，macOS `brew install cloudflared`。
2. 在 [Cloudflare Zero Trust](https://one.dash.cloudflare.com/) 创建 **Cloudflare Tunnel**，公共主机名 / 路由的 **Service URL 请指向本机 AllahPan 后端**，例如 **`http://localhost:8000`**（与后端同端口，才能同时访问 **Web 页面 + `/api/v1`**；若 `frontend_web` 目录存在，访问隧道根路径即可打开网盘页）。
3. 复制 **Tunnel Token**。
4. 桌面端：**设置 → 远程访问 → 配置远程访问…**，填入 Token（可选填写绑定域名备注），保存。
5. 点击 **状态栏上的远程访问/Tunnel 区域**（或按提示），可 **启动** 隧道；成功后状态栏会显示公网地址（具体以 `cloudflared` 输出解析为准）。
6. **安全**：Token 等同于远程入口钥匙，勿泄露、勿提交到 Git；外网务必使用 **强密码**，谨慎使用「记住登录」。

---

## 使用教程：Web 前端

### 三种打开方式

| 方式 | 适用场景 | 说明 |
|------|----------|------|
| **后端托管** | 家用一台机、单端口 | 启动 `uvicorn` 后浏览器访问 **`http://<IP>:8000/`**（若存在 `frontend_web` 目录则由后端托管静态页，见 `backend/app/config.py` 中 `WEB_FRONTEND_DIR` / `ALLAHPAN_WEB_DIR`） |
| **`frontend_web/run.py`（端口 3000）** | 固定从 3000 调试静态页 | 自动把 **`/api/*`** 反向代理到 **`ALLAHPAN_API_UPSTREAM`**（默认 `http://127.0.0.1:8000`） |
| **直接打开 `index.html`** | 快速看一眼 | `file://` 下 `js/api.js` 会将 API 回退到 **`http://localhost:8000/api/v1`**；上传等能力依赖后端可达 |

### 环境变量与 API 基址

- 使用 **`frontend_web/run.py`** 时，若后端不在本机 8000，启动前设置（无尾斜杠）：
  - **PowerShell**：`$env:ALLAHPAN_API_UPSTREAM="http://192.168.1.10:8000"; python run.py`
  - **Bash**：`export ALLAHPAN_API_UPSTREAM=http://192.168.1.10:8000 && python run.py`
- 也可在页面中设置 **`window.ALLAH_PAN_API_BASE`**，或在 `index.html` 的 meta **`allahpan-api-base`** 指向 API 根（以 **`/api/v1`** 结尾）。逻辑见 **`frontend_web/js/api.js`** 的 `getBaseUrl()`。

### 登录与文件操作

- **注册 / 登录**：与桌面端共用同一套后端用户；可勾选「记住登录」（Token 存于浏览器 **localStorage**）。
- **上传**：点击上传区域选择文件，或 **拖拽** 到上传区；支持 **多文件队列** 与 **大文件分片**（小文件直传、大文件断点续传，见页面逻辑）。
- **列表与目录**：文件列表支持 **子目录** 与面包屑导航；空目录会提示上传。
- **下载 / 删除 / 重命名**：每条文件操作按钮在列表中；删除前会弹出确认框。
- **预览**：支持常见图片、音视频在线预览；不支持的类型会提示下载后查看。
- **搜索**：**按文件名** 与 **图片/语义** 两种 Tab，对应后端文件名搜索与向量/语义检索。

### 「系统状态」面板（轻量运维）

- 登录后主界面上方有 **「系统状态」** 折叠区：轮询 **`GET /api/v1/system/summary`**，展示 **存储占用条、Ollama 是否运行、图片解析队列** 等摘要。
- **桌面端** 默认约 **30s** 刷新；**窄屏移动端** 默认折叠，**展开后** 约 **90s** 刷新，以省流量。
- 摘要中还包含 **目录监听、Tunnel** 等字段，但当前网页 UI 仅展示部分字段；完整 JSON 可通过 **`/api/v1/system/summary`** 或浏览器开发者工具查看。

### Web 上配置 Tunnel（可选）

- 网页 **`js/api.js`** 已封装 **`/api/v1/tunnel/*`**（配置、启动、停止、状态等），但 **默认页面未提供 Tunnel 表单**。若仅使用浏览器、无桌面客户端，可用 **Swagger**（后端 **`http://<host>:8000/docs`**）或 **curl** 携带 **`Authorization: Bearer <token>`** 调用上述接口；**更推荐** 在桌面端「设置 → 远程访问」完成 Token 配置与启动。

### 进阶：与桌面运维看板相同的 HTTP 接口

均需 **Bearer Token**（与登录接口返回一致）：

- **`GET /api/v1/system/metrics/traffic`** — 最近约 120 分钟请求量（按分类聚合）
- **`GET /api/v1/system/metrics/data-volumes`** — 库文件与目录体积
- **`GET /api/v1/system/logs/tail?lines=300`** — 日志尾部（最多可调至 2000）

可在 **`/docs`** 中试调，便于远程排障。

---

## 文档

- `docs/`：桌面端 UI、远程访问等补充说明。
- `frontend_web/使用指南.md`：网页端使用说明。

## 许可证

见项目内版权信息。

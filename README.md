# AllahPan

家庭私有网盘 — 本地部署，支持 AI 语义搜索、桌面/Web 双前端、Cloudflare Tunnel 远程访问。

## 项目结构

```
AllahPan/
├── backend/           # FastAPI 后端（认证、文件、AI、系统、Tunnel）
├── frontend_desktop/  # PySide6 桌面端
├── frontend_web/      # Web 前端（浏览器访问）
├── docs/              # 文档
├── launcher.py        # 统一启动器（后端 + 桌面前端）
├── requirements.txt   # 根依赖（会拉取 backend + frontend_desktop 依赖）
├── AllahPan.spec      # PyInstaller 打包配置（当前平台）
├── AllahPan-macOS.spec
├── AllahPan-Linux.spec
└── version.py
```

## 环境要求

- **Python 3.12**
- Windows / macOS / Linux

---

## Windows 运行教程

### 1. 克隆仓库

```powershell
git clone https://github.com/AfterMaxQ/AllahPan.git
cd AllahPan
```

（SSH：`git clone git@github.com:AfterMaxQ/AllahPan.git`）

### 2. 创建虚拟环境并安装依赖

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 启动（二选一）

**方式 A：统一启动器（推荐）**

```powershell
python launcher.py
```

**家用主机模式（与打包 exe 一致）**

- 启动后会在本机同时跑 **后端（FastAPI）** 与 **桌面前端（PySide6）**；后端默认监听 **`0.0.0.0`**，便于局域网访问。
- **网页端**由后端托管，与 API **同一端口**：手机/其他电脑浏览器打开 `http://<本机局域网IP>:<端口>/` 即可（`frontend_web` 已随 PyInstaller 打入包内）。
- 监听地址、API 端口、Ollama 端口可在桌面 **设置 → 本机服务与局域网 Web** 中配置，保存至 `~/.allahpan/server_settings.json`，**完全退出应用后重新打开**生效。
- 若局域网无法访问，请检查系统防火墙是否放行对应 TCP 端口。

**方式 B：分别启动**

终端 1 — 后端：

```powershell
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

终端 2 — 桌面前端：

```powershell
cd frontend_desktop
python run.py
```

### 4. 打包（可选）

```powershell
.venv\Scripts\activate
pip install PyInstaller
pyinstaller AllahPan.spec
```

产物在 `dist\` 下。

---

## macOS 运行教程

### 1. 克隆仓库

```bash
git clone https://github.com/AfterMaxQ/AllahPan.git
cd AllahPan
```

（SSH：`git clone git@github.com:AfterMaxQ/AllahPan.git`）

### 2. 创建虚拟环境并安装依赖

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. 启动（二选一）

**方式 A：统一启动器**

```bash
python launcher.py
```

**方式 B：分别启动**

终端 1 — 后端：

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

终端 2 — 桌面前端：

```bash
cd frontend_desktop
python run.py
```

### 4. 打包（可选）

```bash
source .venv/bin/activate
pip install PyInstaller
pyinstaller AllahPan-macOS.spec
```

产物在 `dist/` 下。

---

## 配置说明

- **API 地址**：默认 `http://localhost:8000`，可在前端或环境变量中修改。
- **存储目录**：默认 `~/Documents/AllahPan/files`（Windows 为 `用户目录\Documents\AllahPan\files`），可通过环境变量 `ALLAHPAN_STORAGE_DIR` 或桌面端设置页修改。
- **首次使用**：在桌面端或 Web 端（`http://localhost:8000`）注册账号后登录。

## 文档

- `docs/`：桌面端显示与交互改进、MacOS 风格 UI、出门手机访问等说明。

## 许可证

见项目内版权信息。

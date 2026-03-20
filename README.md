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
- macOS / Windows / Linux

## 在 macOS 上运行（另一台电脑克隆后）

### 1. 克隆仓库

```bash
git clone https://github.com/AfterMaxQ/AllahPan.git
cd AllahPan
```

（若使用 SSH：`git clone git@github.com:AfterMaxQ/AllahPan.git`）

### 2. 创建虚拟环境并安装依赖

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. 启动方式（二选一）

**方式 A：统一启动器（推荐）**

```bash
python launcher.py
```

会同时启动后端与桌面前端，并尝试管理 Ollama。

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

浏览器访问 Web 前端：`http://localhost:8000`（需先启动后端）。

### 4. 打包（可选）

在项目根目录：

```bash
source .venv/bin/activate
pip install PyInstaller
pyinstaller AllahPan-macOS.spec
```

产物在 `dist/` 下，按 spec 中配置生成。

## 配置说明

- 默认 API：`http://localhost:8000`，可在前端或环境变量中修改。
- 存储目录：默认 `~/Documents/AllahPan/files`，可通过环境变量 `ALLAHPAN_STORAGE_DIR` 或桌面端设置页修改。
- 首次运行需在桌面端或 Web 端注册账号后登录。

## 文档

- `docs/` 下有桌面端显示与交互改进、MacOS 风格 UI、出门手机访问等说明。

## 许可证

见项目内版权信息。

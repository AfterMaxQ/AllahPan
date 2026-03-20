# AllahPan Web 前端

纯前端极简网盘界面，访问后端 API 实现文件管理、AI 搜索等功能，无需构建，浏览器直接运行。

## 功能

- **用户认证**：注册 / 登录 / 自动登录（localStorage）
- **文件管理**：列表、点击上传、拖拽上传、上传进度、下载
- **AI 搜索**：语义搜索 + 文件名搜索
- **响应式**：适配桌面和手机浏览器

## 快速开始

### 1. 启动后端

```powershell
# Windows
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

```bash
# macOS / Linux
cd backend
source ../.venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 打开前端页面（二选一）

**方式 A（推荐）：** 在 `frontend_web` 下启动 HTTP 服务器：

```powershell
# Windows
cd frontend_web
.venv\Scripts\python run.py
```

```bash
# macOS / Linux
cd frontend_web
source ../.venv/bin/activate
python run.py
```

浏览器自动打开 `http://localhost:3000`。

**方式 B：** 直接用浏览器打开 `frontend_web/index.html`（API 会回退到 `http://localhost:8000/api/v1`）。

### 3. 注册 / 登录

在页面注册账号后登录，即可使用文件上传、下载、AI 搜索等全部功能。

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/register` | 注册 |
| POST | `/api/v1/auth/login` | 登录 |
| GET | `/api/v1/auth/me` | 当前用户信息 |
| GET | `/api/v1/files/list` | 文件列表 |
| POST | `/api/v1/files/upload` | 上传文件 |
| GET | `/api/v1/files/{id}/download` | 下载文件 |
| POST | `/api/v1/ai/search` | AI 语义搜索 |
| GET | `/api/v1/system/info` | 系统信息 |

## 技术栈

纯 HTML5 + 原生 JavaScript（无框架），Fetch API 通信，localStorage 管理 Token，CSS3 响应式布局。

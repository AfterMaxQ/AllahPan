# AllahPan 桌面端

基于 PySide6 的 macOS 风格家庭私有网盘客户端，支持深色/浅色主题、文件管理、AI 语义搜索、Cloudflare Tunnel 远程访问。

## 功能

- **macOS 风格 UI**：圆角、毛玻璃感、精致的阴影与动效
- **百度网盘布局**：左侧分类导航 + 中间网格/列表视图 + 右上搜索栏
- **双视图切换**：网格视图（大图标） / 列表视图（多列信息）
- **拖拽上传**：全局拖入窗口即可上传，支持递归扫描文件夹
- **上传队列**：最多 3 并发，实时进度条
- **AI 语义搜索**：文件名搜索 + 自然语言语义搜索，模式可切换
- **深色/浅色主题**：手动切换或跟随系统
- **文件预览**：图片直接预览，其他类型调用系统默认程序打开
- **右键菜单**：下载、预览、复制链接、删除等

## 项目结构

```
frontend_desktop/
├── config.py              # 配置常量、主题配色、API 地址
├── run.py                 # 应用入口
├── requirements.txt       # Python 依赖
├── theme/
│   ├── light.py           # 浅色主题 QSS
│   └── dark.py            # 深色主题 QSS
├── api/
│   ├── client.py          # 统一 API 客户端
│   ├── auth.py            # 认证
│   ├── files.py           # 文件管理
│   ├── ai.py              # AI 语义搜索
│   ├── system.py          # 系统信息
│   └── tunnel.py          # 远程访问
├── widgets/
│   ├── file_list_model.py # 文件数据模型
│   ├── sidebar_nav.py     # 侧边栏导航
│   ├── search_bar.py      # 搜索栏
│   ├── upload_queue.py    # 上传队列
│   ├── status_bar.py      # 状态栏
│   └── file_browser.py    # 文件浏览器
└── pages/
    ├── login_page.py      # 登录/注册页面
    └── settings_page.py   # 设置页面
```

## 安装依赖

```powershell
# Windows
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

```bash
# macOS / Linux
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> 需确保后端服务（FastAPI）已在运行，桌面端通过 HTTP API 与后端通信。

## 运行应用

```powershell
# Windows
cd frontend_desktop
.venv\Scripts\activate
python run.py
```

```bash
# macOS / Linux
cd frontend_desktop
source ../.venv/bin/activate
python run.py
```

## 配置

### API 地址

默认连接 `http://localhost:8000`，可通过环境变量修改：

```powershell
# Windows
set ALLAHPAN_HOST=192.168.1.100
set ALLAHPAN_PORT=8000
python run.py
```

```bash
# macOS / Linux
export ALLAHPAN_HOST=192.168.1.100
export ALLAHPAN_PORT=8000
python run.py
```

### 主题

应用启动时默认使用浅色主题，可在设置页面中切换为深色模式或跟随系统。

## 使用说明

### 登录 / 注册

首次使用需注册账号，注册成功后登录。

### 文件管理

- **上传**：点击"上传"按钮或直接拖拽文件到窗口任意位置
- **下载**：选中文件后右键菜单选择"下载"
- **预览**：双击文件可直接预览（图片）或调用系统程序打开
- **删除**：选中文件后右键菜单选择"删除"

### 视图切换

- **网格视图**：大图标，适合图片预览
- **列表视图**：紧凑多列，显示文件大小、类型、时间、AI 状态

### 文件分类

左侧边栏提供分类筛选：全部、图片、文档、视频、音频、其他。

### 搜索

支持两种模式（点击搜索栏右侧按钮切换）：

- **文件名搜索**：关键字精确匹配
- **AI 语义搜索**：自然语言描述，如"去年的旅行照片"

## 技术栈

- **GUI 框架**：PySide6（Qt for Python）
- **HTTP 客户端**：httpx
- **后端通信**：REST API（对接 backend FastAPI）

## 设计参考

- macOS Big Sur + Sonoma 设计语言
- 百度网盘功能模式
- Qt Fusion 风格基础

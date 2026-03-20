# AllahPan PySide6 桌面端

基于 PySide6 的 macOS 风格家庭私有网盘桌面客户端。

## 功能特性

- **macOS 风格设计**：采用 SF 风格设计语言，圆角、毛玻璃效果、精致的阴影
- **百度网盘模式**：左侧文件分类导航、中间文件网格/列表视图、右上搜索栏
- **双视图切换**：支持网格视图和列表视图自由切换
- **拖拽上传**：支持全局拖拽上传文件和文件夹（递归扫描子文件夹）
- **上传队列**：最多 3 个并发上传，实时显示进度条
- **AI 语义搜索**：支持文件名搜索和 AI 自然语言语义搜索模式切换
- **深色/浅色主题**：支持手动切换和跟随系统主题
- **文件预览**：图片直接预览，其他文件调用系统默认程序打开
- **右键菜单**：下载、预览、复制链接、删除等操作

## 项目结构

```
frontend_desktop/
├── config.py              # 配置常量、主题配色、API地址
├── run.py                # 应用程序入口
├── requirements.txt      # Python 依赖
├── theme/
│   ├── __init__.py
│   ├── light.py          # 浅色主题 QSS
│   └── dark.py          # 深色主题 QSS
├── api/
│   ├── __init__.py
│   ├── client.py         # 统一 API 客户端
│   ├── auth.py           # 认证 API
│   ├── files.py         # 文件管理 API
│   ├── ai.py            # AI 语义搜索 API
│   └── system.py        # 系统 API
├── widgets/
│   ├── __init__.py
│   ├── file_list_model.py    # 文件数据模型
│   ├── sidebar_nav.py        # 侧边栏导航
│   ├── search_bar.py         # 搜索栏
│   ├── upload_queue.py       # 上传队列
│   ├── status_bar.py         # 状态栏
│   └── file_browser.py      # 文件浏览器
└── pages/
    ├── __init__.py
    ├── login_page.py     # 登录/注册页面
    └── settings_page.py # 设置页面
```

## 安装依赖

```bash
cd frontend_desktop
pip install -r requirements.txt
```

**注意**：需要确保后端服务（FastAPI）正在运行，桌面端通过 HTTP API 与后端通信。

## 运行应用

```bash
cd frontend_desktop
python run.py
```

## 配置

### API 地址

默认连接 `http://localhost:8000`，可通过环境变量修改：

```bash
set ALLAHPAN_HOST=192.168.1.100
set ALLAHPAN_PORT=8000
python run.py
```

### 主题

应用启动时默认使用浅色主题，可在设置页面中切换：
- 浅色模式
- 深色模式
- 跟随系统

## 使用说明

### 登录/注册

首次使用需要注册账号，注册成功后使用账号密码登录。

### 文件管理

- **上传文件**：点击「上传」按钮选择文件，或直接拖拽文件到窗口任意位置
- **下载文件**：选中文件后点击「下载」按钮，或右键菜单选择「下载」
- **预览文件**：双击文件可直接预览（图片）或调用系统程序打开
- **删除文件**：选中文件后右键菜单选择「删除」

### 视图切换

- **网格视图**：大图标显示，适合图片预览
- **列表视图**：紧凑布局，显示更多文件信息（大小、类型、时间、AI状态）

### 文件分类

左侧边栏提供文件分类筛选：
- 全部文件
- 图片
- 文档
- 视频
- 音频
- 其他

### 搜索

搜索栏支持两种模式：
- **文件名搜索**：输入文件名关键字精确匹配
- **AI 语义搜索**：输入自然语言描述，如"去年的旅行照片"

点击搜索栏右侧按钮切换模式。

## 技术栈

- **GUI 框架**：PySide6（Qt for Python）
- **HTTP 客户端**：httpx
- **后端通信**：REST API（与 backend FastAPI 对接）

## 设计参考

- macOS Big Sur + Sonoma 设计语言
- 百度网盘功能模式
- Qt Fusion 风格基础

## 许可证

MIT License

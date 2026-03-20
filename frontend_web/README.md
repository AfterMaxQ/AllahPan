# AllahPan 极简 Web 前端

这是一个极简的 Web 前端，用于快速验证后端 API 功能。

## 功能特性

✅ **用户认证**
- 用户注册
- 用户登录
- 自动登录（基于 localStorage）

✅ **文件管理**
- 文件列表展示
- 点击上传文件
- 拖拽上传文件
- 上传进度条
- 文件下载

✅ **AI 功能**
- AI 语义搜索
- 文件名搜索
- 搜索结果展示

## 快速开始

### 1. 启动后端服务

```bash
cd backend
f:\Python\AllahPan\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端服务将在 `http://localhost:8000` 启动。

### 2. 打开前端页面

直接在浏览器中打开：
```
file:///f:/Python/AllahPan/frontend_web/index.html
```

或者使用简单的 HTTP 服务器：

```bash
cd frontend_web
f:\Python\AllahPan\.venv\Scripts\python.exe -m http.server 3000
```

然后访问：`http://localhost:3000`

## 使用流程

1. **注册账号**
   - 点击"立即注册"
   - 输入用户名、密码、邮箱
   - 点击"注册"

2. **登录**
   - 输入用户名和密码
   - 点击"登录"

3. **上传文件**
   - 点击上传区域选择文件
   - 或直接拖拽文件到上传区域
   - 查看上传进度

4. **下载文件**
   - 在文件列表中找到目标文件
   - 点击"下载"按钮

5. **搜索文件**
   - 在搜索框输入关键词
   - 自动执行 AI 语义搜索
   - 查看搜索结果

## API 端点

后端 API 基础地址：`http://localhost:8000/api/v1`

- `POST /auth/register` - 用户注册
- `POST /auth/login` - 用户登录
- `GET /auth/me` - 获取当前用户信息
- `GET /files/list` - 获取文件列表
- `POST /files/upload` - 上传文件
- `GET /files/{file_id}/download` - 下载文件
- `POST /ai/search` - AI 语义搜索
- `GET /system/info` - 系统信息

## 技术栈

- **纯 HTML5** - 单文件实现
- **原生 JavaScript** - 无需框架
- **Fetch API** - HTTP 请求
- **localStorage** - Token 存储
- **CSS3** - 响应式设计

## 注意事项

1. **CORS 配置**：后端已配置允许 `localhost:3000` 和 `localhost:5173` 的跨域请求

2. **Token 管理**：登录成功后，Token 会自动存储到 localStorage，并在后续请求中自动携带

3. **文件上传**：支持拖拽上传和点击上传，显示实时进度条

4. **AI 搜索**：需要确保 Ollama 服务正在运行，并加载了相应的模型

## 下一步

完成 Web 前端验证后，可以开始开发 PySide6 桌面客户端，实现更完整的功能和更好的用户体验。

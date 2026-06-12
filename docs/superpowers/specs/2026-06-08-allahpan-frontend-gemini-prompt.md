你是一位前端开发专家。请为 AllahPan（家庭共享云盘）实现 Vue 3 前端应用。

## 项目背景

AllahPan 是部署在家庭 Mac 上的共享云盘，用户是家庭成员。后端已全部完成（Spring Boot + JWT + MinIO + ES + RabbitMQ），前端需要从零搭建。

## 技术栈

- Vue 3 (Composition API + `<script setup>`)
- Vite 8 + sass-embedded
- Element Plus 2.14（UI 框架）
- Vue Router 4、Pinia 3、Axios、Spark-MD5
- `@element-plus/icons-vue`（图标库）
- 后端端口 :8088，前端 :5173，vite proxy 已配好

## 设计语言

请阅读项目中的设计语言文档：
`docs/superpowers/specs/2026-06-08-allahpan-frontend-design.md`

核心氛围：**暖白底色 + 木色点缀，温馨简洁，家庭感**。文档是引导性的，细节可自由发挥，保持整体氛围一致即可。

## API 文档

`docs/api/` 目录下包含全部后端 API 文档（7 个模块，约 27 个端点），含 curl 示例和 JSON 响应。

模块：01-auth（认证）、02-user（用户）、03-file（文件）、04-favorite（收藏）、05-search-core（搜索代理）、06-search-service（搜索服务）、07-share（分享）

## 目录结构

请按以下结构组织代码：

```
allahpan-web/src/
├── main.js                   # 入口：注册 Element Plus、Router、Pinia
├── App.vue                   # 根组件
├── router/index.js           # 路由配置
├── api/
│   ├── index.js              # Axios 实例 + 拦截器
│   ├── auth.js               # 认证 API
│   ├── file.js               # 文件 API
│   ├── search.js             # 搜索 API
│   └── favorite.js           # 收藏 API
├── stores/
│   ├── user.js               # 用户状态（Pinia）
│   └── file.js               # 文件浏览状态（Pinia）
├── utils/
│   ├── md5.js                # 浏览器端 MD5 计算（Spark-MD5）
│   └── format.js             # 文件大小/日期格式化
├── views/
│   ├── Login.vue             # 登录页（手机验证码 + 密码双通道）
│   ├── SetPassword.vue       # 首次登录设密码
│   ├── FileBrowser.vue       # 文件浏览器（主页）
│   ├── Favorites.vue         # 收藏夹
│   └── Search.vue            # 搜索结果页
├── components/
│   ├── layout/
│   │   ├── AppLayout.vue     # 主布局容器
│   │   ├── AppHeader.vue     # 顶部栏
│   │   └── AppSidebar.vue    # 侧边导航
│   ├── file/
│   │   ├── FileToolbar.vue   # 工具栏
│   │   ├── FileGridView.vue  # 网格视图
│   │   ├── FileListView.vue  # 列表视图
│   │   ├── FileCard.vue      # 网格卡片
│   │   ├── FileRow.vue       # 列表行
│   │   ├── FileUploadDialog.vue     # 上传弹窗
│   │   ├── FolderCreateDialog.vue   # 新建文件夹弹窗
│   │   ├── BreadcrumbNav.vue        # 面包屑导航
│   │   ├── FileContextMenu.vue      # 右键菜单
│   │   └── FilePreviewDialog.vue    # 文件预览弹窗
│   ├── search/
│   │   ├── SearchBar.vue     # 全局搜索输入框
│   │   └── SearchResultItem.vue     # 搜索结果条目
│   └── common/
│       ├── FileIcon.vue      # 文件类型图标
│       ├── ProcessBadge.vue  # 处理状态标签
│       └── EmptyState.vue    # 空状态占位
├── styles/
│   └── global.css            # 全局样式 + Element Plus 主题变量
└── assets/                   # 静态资源
```

## 关键业务逻辑

1. **认证：** 手机验证码登录 + 密码登录双通道。首次登录（`firstLogin=1`）强制跳转设密码页。JWT 存在 localStorage，Axios 拦截器自动带 `Authorization: Bearer <token>`
2. **文件上传：** 调用 `/api/file/preUpload` → 拿到预签名 URL → 浏览器直传 MinIO（PUT）→ 调 `/api/file/confirmUpload` 确认。大文件用 Spark-MD5 计算 MD5 做秒传
3. **文件浏览：** 进入文件夹调 `GET /api/file/list?parentId=`（0=根目录），支持网格/列表切换，面包屑导航，右键菜单（重命名、移动、删除、下载、分享）
4. **文件下载：** `GET /api/file/{id}/download` 返回预签名下载 URL，`window.open(url)` 触发浏览器下载
5. **分享：** 创建分享 → 生成分享码和链接，访问分享 → 公开接口无需认证，可下载
6. **搜索：** 输入关键词 → 调 `/api/search?keyword=` → 高亮展示结果
7. **收藏：** 收藏/取消收藏 → 收藏夹页面查看

## 注意事项

- 所有图标用 `@element-plus/icons-vue` 或内联 SVG，**禁止使用 Emoji**
- Element Plus 中文语言包已在 main.js 注册
- 错误提示用 `ElMessage`，确认操作用 `ElMessageBox.confirm`
- 路由守卫：未登录跳登录页，首次登录跳设密码页
- 文件大小格式化：<1024 显示 B，<1MB 显示 KB，否则 MB/GB
- 设计语言文档是引导而非严格规范，遇到未覆盖的细节以"温馨简洁"为准绳自行发挥

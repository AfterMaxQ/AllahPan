# 04 — 文件管理操作架构图

## 单表树形结构 (parent_id 自引用)

```mermaid
graph TD
    Root["📁 / (root)<br/>parentId = 0"]
    F1["📁 我的图片<br/>id=2, parentId=0<br/>isFolder=1"]
    F2["📁 工作文档<br/>id=5, parentId=0<br/>isFolder=1"]
    F1A["🖼️ test.png<br/>id=1, parentId=2<br/>isFolder=0"]
    F1B["📁 截图<br/>id=3, parentId=2<br/>isFolder=1"]
    F1B1["🖼️ shot1.png<br/>id=4, parentId=3<br/>isFolder=0"]

    Root --> F1
    Root --> F2
    F1 --> F1A
    F1 --> F1B
    F1B --> F1B1
```

## 文件生命周期状态机

```mermaid
stateDiagram-v2
    [*] --> Active: 上传/创建文件夹
    Active --> Trash: deleteFile()<br/>设置 deleteTime
    Trash --> Active: restoreFile()<br/>清除 deleteTime
    Trash --> Deleted: permanentDelete()<br/>删 MinIO 对象 + DB 记录
    Deleted --> [*]

    note right of Active: deleteTime IS NULL
    note right of Trash: deleteTime IS NOT NULL
    note left of Deleted: 物理删除,不可恢复
```

## 软删除流程（deleteFile）

```mermaid
flowchart TD
    A["deleteFile(fileId)"] --> B["selectByPrimaryKey(fileId)"]
    B --> C{"文件存在?"}
    C -->|"否"| Err["Asserts.fail('文件不存在')"]
    C -->|"是"| D["file.deleteTime = new Date()"]
    D --> E["updateByPrimaryKeySelective(file)"]
    E --> F{"isFolder == 1?"}
    F -->|"是"| G["deleteChildren(fileId)"]
    F -->|"否"| Done["完成"]
    G --> H["SELECT children WHERE<br/>parentId=folderId AND deleteTime IS NULL"]
    H --> I["对每个子节点:"]
    I --> J["设置 deleteTime = new Date()"]
    J --> K{"子节点是文件夹?"}
    K -->|"是"| G
    K -->|"否"| L["下一个子节点"]
    L --> I
```

## 垃圾站恢复流程（restoreFile）

```mermaid
flowchart TD
    A["restoreFile(fileId)"] --> B{"文件存在?"}
    B -->|"否"| Err1["Asserts.fail"]
    B -->|"是"| C{"deleteTime != null?"}
    C -->|"否"| Err2["Asserts.fail('不在垃圾站')"]
    C -->|"是"| D{"parentId > 0?"}
    D -->|"是"| E["查父文件夹"]
    E --> F{"父文件夹在垃圾站?"}
    F -->|"是"| Err3["Asserts.fail('请先恢复父文件夹')"]
    F -->|"否"| G["file.deleteTime = null"]
    D -->|"否"| G
    G --> H["updateByPrimaryKeySelective(file)"]
    H --> I{"isFolder == 1?"}
    I -->|"是"| J["restoreChildren(fileId)"]
    I -->|"否"| Done["完成"]
    J --> K["递归: 清除所有子孙 deleteTime"]
    K --> Done
```

## 永久删除流程（permanentDelete）

```mermaid
flowchart TD
    A["permanentDelete(fileId)"] --> B["selectByPrimaryKey(fileId)"]
    B --> C{"文件存在?"}
    C -->|"否"| Err["Asserts.fail"]
    C -->|"是"| D{"storageKey != null?"}
    D -->|"是"| E["minioUtil.removeFromTrash(storageKey)"]
    D -->|"否"| F
    E --> F{"thumbnailKey != null?"}
    F -->|"是"| G["minioUtil.removeThumbnail(thumbnailKey)"]
    F -->|"否"| H{"isFolder == 1?"}
    G --> H
    H -->|"是"| I["permanentDeleteChildren(fileId)<br/>递归物理删除所有子孙"]
    H -->|"否"| J["fileMapper.deleteByPrimaryKey(fileId)"]
    I --> J
    J --> Done["完成 — 数据不可恢复"]
```

## 目录树构建（面包屑导航）

```mermaid
flowchart LR
    A["GET /api/file/tree/{folderId}"] --> B["getDirectoryTree(folderId)"]
    B --> C["从 folderId 开始<br/>循环查 selectByPrimaryKey"]
    C --> D{"current > 0?"}
    D -->|"是"| E["list.add(0, file)<br/>插入列表头部"]
    E --> F["current = file.parentId"]
    F --> D
    D -->|"否"| G["返回 List<File><br/>顺序: 根 → ... → 当前"]
```

示例结果：`[/, 我的图片, 截图]`

## 文件列表排序规则

```sql
SELECT * FROM files
WHERE parent_id = ? AND delete_time IS NULL
ORDER BY is_folder DESC, create_time DESC
```

文件夹优先显示，同类型按创建时间倒序。

## API 端点汇总

| 方法 | 路径 | 功能 | 存储层 |
|------|------|------|--------|
| POST | `/api/file/upload` | 上传（multipart） | MinioUtil.putObject() |
| POST | `/api/file/create-folder` | 创建文件夹 | — |
| GET | `/api/file/list?parentId=` | 文件列表 | — |
| GET | `/api/file/tree/{folderId}` | 目录树 | — |
| GET | `/api/file/{fileId}` | 文件详情 | — |
| GET | `/api/file/{fileId}/download` | 下载 | MinioUtil.getObject() |
| GET | `/api/file/{fileId}/stream` | 内联预览 | MinioUtil.getObject() |
| GET | `/api/file/{fileId}/thumbnail` | 缩略图 | MinioUtil.getThumbnail() |
| GET | `/api/file/watch?token=` | SSE 实时推送 | — |
| DELETE | `/api/file/{fileId}` | 软删除 | MinioUtil.copyToTrash() |
| DELETE | `/api/file/batch` | 批量软删除 | MinioUtil.copyToTrash() |
| GET | `/api/file/trash` | 垃圾站列表 | — |
| PUT | `/api/file/trash/{fileId}/restore` | 恢复 | MinioUtil.restoreFromTrash() |
| DELETE | `/api/file/trash/{fileId}` | 永久删除 | MinioUtil.removeFromTrash() |
| PUT | `/api/file/{fileId}/rename` | 重命名 | — |
| PUT | `/api/file/{fileId}/move` | 移动 | — |

## 下载/预览/缩略图 — MinIO 流式访问

```mermaid
flowchart TD
    A["请求 download / stream / thumbnail"] --> B{"MinIO 对象存在?"}
    B -->|"是"| C["InputStream 流式返回"]
    C --> D["download: Content-Disposition: attachment"]
    C --> E["stream: Content-Disposition: inline"]
    C --> F["thumbnail: Content-Type: image/jpeg<br/>来源: allahpan-thumbnails bucket"]
    B -->|"否"| G["返回 404 Not Found"]
```

所有文件/缩略图通过 MinIO SDK 读取，无需本地磁盘访问。

## TrashCleanupTask — 定时清理

```
@Scheduled(cron = "0 0 3 * * ?")  // 每天凌晨 3:00
```

自动永久删除垃圾站中超过 60 天的文件：

```mermaid
flowchart TD
    A["TrashCleanupTask.cleanExpiredTrash()"] --> B["SELECT files WHERE<br/>deleteTime <= NOW() - 60 days"]
    B --> C["遍历过期文件"]
    C --> D["permanentDelete(fileId)"]
    D --> E["从 MinIO trash bucket 删除对象"]
    D --> F["从 MinIO thumbnails bucket 删除缩略图"]
    D --> G["删除 ES 索引"]
    D --> H["删除 DB 记录"]
    C --> I["日志: 成功 N 条, 失败 M 条"]
```

## 新增操作流程

### 重命名（renameFile）

```mermaid
flowchart TD
    A["PUT /api/file/{fileId}/rename<br/>{newName}"] --> B["selectByPrimaryKey(fileId)"]
    B --> C{"文件存在且未删除?"}
    C -->|"否"| Err["Asserts.fail"]
    C -->|"是"| D["newName 非空?"]
    D -->|"否"| Err2["Asserts.fail"]
    D -->|"是"| E["file.fileName = newName"]
    E --> F["file.filePath = buildPath(newName, parentId)"]
    F --> G["updateByPrimaryKeySelective(file)"]
    G --> H{"isFolder == 1?"}
    H -->|"是"| I["rebuildDescendantPaths(fileId)<br/>递归重建所有子孙 filePath"]
    H -->|"否"| Done["完成"]
    I --> Done
```

### 移动（moveFile）

```mermaid
flowchart TD
    A["PUT /api/file/{fileId}/move<br/>{targetParentId}"] --> B["selectByPrimaryKey(fileId)"]
    B --> C{"文件存在且未删除?"}
    C -->|"否"| Err["Asserts.fail"]
    C -->|"是"| D["校验目标父目录: 存在/是文件夹/未删除"]
    D --> E{"targetParentId == fileId?"}
    E -->|"是"| Err2["不能移动到自身"]
    E -->|"否"| F{"isDescendant(fileId, targetParentId)?"}
    F -->|"是"| Err3["不能移动到子文件夹"]
    F -->|"否"| G{"parentId 已相同?"}
    G -->|"是"| Done["无操作返回"]
    G -->|"否"| H["file.parentId = targetParentId"]
    H --> I["file.filePath = buildPath(...)"]
    I --> J["updateByPrimaryKeySelective(file)"]
    J --> K{"isFolder == 1?"}
    K -->|"是"| L["rebuildDescendantPaths(fileId)"]
    K -->|"否"| Done2["完成"]
    L --> Done2
```

## 关键文件索引

| 功能 | 文件 | 方法 |
|------|------|------|
| 软删除 | `FileServiceImpl.java` | `deleteFile()` |
| 递归软删子节点 | `FileServiceImpl.java` | `deleteChildren()` |
| 垃圾站列表 | `FileServiceImpl.java` | `listTrash()` |
| 恢复 | `FileServiceImpl.java` | `restoreFile()` |
| 递归恢复 | `FileServiceImpl.java` | `restoreChildren()` |
| 永久删除 | `FileServiceImpl.java` | `permanentDelete()` |
| 递归物理删除 | `FileServiceImpl.java` | `permanentDeleteChildren()` |
| 目录树 | `FileServiceImpl.java` | `getDirectoryTree()` |
| 文件列表 | `FileServiceImpl.java` | `listFiles()` |
| 路径构建 | `FileServiceImpl.java` | `buildPath()` |
| 递归重建子孙路径 | `FileServiceImpl.java` | `rebuildDescendantPaths()` |
| 循环检测 | `FileServiceImpl.java` | `isDescendant()` |
| 重命名 | `FileServiceImpl.java` | `renameFile()` |
| 移动 | `FileServiceImpl.java` | `moveFile()` |
| 批量删除 | `FileServiceImpl.java` | `batchDelete()` |
| MinIO 对象 I/O | `MinioUtil.java` | `putObject()`, `getObject()`, `removeObject()`, `copyToTrash()`, `restoreFromTrash()`, `removeFromTrash()`, `putThumbnail()`, `getThumbnail()`, `removeThumbnail()` |
| SSE 广播 | `SseBroadcaster.java` | `broadcast()` |
| 定时清理 | `TrashCleanupTask.java` | `cleanExpiredTrash()` |

# 020 — 垃圾站显示不存在的文件（孤儿垃圾记录）

## 现象

垃圾站页面 (`/api/file/trash`) 显示已删除的文件和文件夹，但对应物理文件在 `C:\Users\ray\AllahPan\.trash` 目录中不存在。用户无法恢复或永久删除这些文件（操作时报错或静默失败）。

## 根因

项目从 Minio 迁移到本地文件系统后，存在 4 个独立代码路径会创建 DB 垃圾记录（`delete_time IS NOT NULL`）但未将物理文件移至 `.trash/`：

| 路径 | 文件 | 问题 |
|------|------|------|
| StorageKeyMigration | `StorageKeyMigration.java:35` | 迁移时 `andDeleteTimeIsNull()` 跳过已删除记录，旧 Minio 格式 storageKey 在本地磁盘无对应文件 |
| FileSystemWatcher.fullSync | `FileSystemWatcher.java:403-413` | DB 有但磁盘无时，设置 `deleteTime` 但文件已消失，无文件可移至 `.trash/` |
| FileSystemWatcher.removeFromDb | `FileSystemWatcher.java:329-339` | WatchService 检测到外部删除时，软删除但不移动文件 |
| FileServiceImpl.moveToTrash | `FileServiceImpl.java:216` | 明确跳过文件夹（`isFolder == 1`），文件夹无物理文件但出现在垃圾列表中 |
| FileServiceImpl.deleteFile | `FileServiceImpl.java:179` | 先写 DB（`setDeleteTime`）再移动文件，若移动失败则 DB 已提交，产生孤儿 |

## 修复

### 1. 清理现有孤儿（启动时一次性）

`FileServiceImpl.cleanupOrphanedTrash()` — `@PostConstruct` 方法，遍历所有 `delete_time IS NOT NULL` 的记录：
- 跳过文件夹（无物理文件）
- 对非文件夹记录检查 `.trash/<storageKey>` 是否存在
- 不存在则调用 `fileMapper.deleteByPrimaryKey()` 硬删除 DB 记录
- 日志输出：`清理孤儿垃圾记录完成: 检查 X 条, 删除 Y 条`

### 2. 修复 deleteFile/deleteChildren 的执行顺序

将 `moveToTrash()` 调用移到 `setDeleteTime()` + `updateByPrimaryKeySelective()` 之前。
如果物理移动失败，deleteTime 不会被写入 DB，避免产生孤儿记录。
`deleteChildren()` 中每个子文件独立 try-catch，一个失败不影响其他兄弟文件。

### 3. LocalStorageServiceImpl.moveToTrash() 不再静默失败

源文件不存在时抛出 `NoSuchFileException` 而不是静默 `return`。
配合执行顺序修复，确保物理文件不存在时不会创建垃圾 DB 记录。

### 4. FileSystemWatcher 改用硬删除

`removeFromDb()` 和 `fullSync()` 中对外部删除的文件改用 `deleteByPrimaryKey()` 硬删除，
不再设置 `deleteTime` 软删除。文件已从磁盘消失，创建垃圾记录无实际意义且产生孤儿。

### 5. StorageKeyMigration 包含已删除记录

移除 `andDeleteTimeIsNull()` 过滤条件，让已删除记录的 storageKey 也从 Minio 格式迁移到本地路径格式，
确保启动清理能正确识别这些记录。

### 6. 启动时创建 .trash 目录

`LocalStorageServiceImpl.init()` 新增 `Files.createDirectories(trashDir)`，确保首次启动时 `.trash/` 目录存在。

### 7. listTrash 弹性过滤

- 添加 `andUploaderIdEqualTo(getCurrentUserId())` 用户隔离
- 对非文件夹记录，确认 `.trash/<storageKey>` 物理文件存在才返回

## 涉及文件

| 文件 | 改动 |
|------|------|
| `.../service/impl/FileServiceImpl.java` | 新增 cleanupOrphanedTrash + 修复 deleteFile/deleteChildren 顺序 + listTrash 弹性过滤 |
| `.../service/impl/LocalStorageServiceImpl.java` | moveToTrash 抛出 NoSuchFileException + init 创建 .trash/ |
| `.../component/FileSystemWatcher.java` | removeFromDb 和 fullSync 改为硬删除 |
| `.../component/StorageKeyMigration.java` | 移除 andDeleteTimeIsNull 过滤 |

## 验证

1. 重启服务，检查日志出现 `清理孤儿垃圾记录完成: 检查 X 条, 删除 Y 条`
2. 第二次重启，同日志显示 `删除 0 条`（所有孤儿已清理）
3. 访问 `GET /api/file/trash`，确认仅显示有物理 `.trash/` 文件的记录
4. 通过 UI 删除文件 → 确认 `.trash/` 中有对应文件且垃圾站可显示
5. 通过 UI 恢复文件 → 确认文件回到原位置，垃圾站不再显示
6. 手动从 `.trash/` 删除一个文件 → 刷新垃圾站，确认该记录不再出现
7. 从磁盘手动删除一个文件 → FileSystemWatcher 日志显示"硬删除"而非"软删除"

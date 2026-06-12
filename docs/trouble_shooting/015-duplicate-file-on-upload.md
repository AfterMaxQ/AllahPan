# 015 — 拖拽上传图片产生重复文件

**日期:** 2026-06-09

## 症状

拖拽图片上传到网盘时，文件列表中同时出现两个同名文件：
- 一个状态为 **"已缩略"** (processStatus=1)
- 一个状态为 **"可用"** (processStatus=3)

两个记录指向同一个 MinIO 对象，但 DB 中有两条独立记录。

## 根因

**`FileSystemWatcher.ensureFileInDb` 的去重逻辑仅按 `storageKey` 查询，但 web 上传和本地文件监听使用不同格式的 storageKey，导致去重失败。**

### 完整链路

```
用户拖拽图片上传
  ↓
① pre-upload: 生成 MinIO pre-signed URL
  ↓
② fetch() PUT 到 MinIO（浏览器直传）
  ↓
③ confirm-upload:
    - FileServiceImpl.confirmUpload() 创建 DB 记录 #1
      storageKey = "1/2026/06/uuid.png"  ← MinIO key（UUID 格式）
      processStatus = 0 (UPLOADED)
    - LocalSyncService.mirrorMinioToLocal()
      从 MinIO 下载 → 写入本地 C:/Users/ray/AllahPan/图片名.png
  ↓
④ FileSystemWatcher 检测到本地新文件
    - reconcilePath: storageKey = "图片名.png"  ← 本地相对路径
    - ensureFileInDb:
      ✗ 按 storageKey 查: WHERE storage_key='图片名.png' → 无匹配
         （DB 中是 "1/2026/06/uuid.png"）
      ✗ 计算 MD5 → 匹配到记录 #1
      ✗ 走"秒传"路径: 创建 DB 记录 #2
         storageKey = "1/2026/06/uuid.png"（复用 MinIO key）
         processStatus = 3 (COMPLETED，秒传直接完成)
  ↓
⑤ RabbitMQ 管线处理记录 #1
    UPLOADED(0) → THUMBNAILED(1) → TEXT_EXTRACTED(2) → COMPLETED(3)
  ↓
⑥ 前端看到两个文件:
    - 记录 #1: processStatus=1 ("已缩略")
    - 记录 #2: processStatus=3 ("可用")
```

### StorageKey 格式不匹配

| 来源 | storageKey 格式 | 示例 |
|------|----------------|------|
| `confirmUpload` (web 上传) | MinIO UUID key | `1/2026/06/abc123.png` |
| `FileSystemWatcher.reconcilePath` | 本地相对路径 | `截图.png` |

`ensureFileInDb` 的唯一去重依据是 `storageKey`，两种格式永远不匹配 → 每次 web 上传都会产生一条重复记录。

### 为什么 MD5 "秒传" 帮了倒忙

`ensureFileInDb` 的 MD5 秒传逻辑（line 269-293）本意是：本地出现的新文件，如果内容与已有文件相同，不重新上传 MinIO，直接复用已有 MinIO key 创建一条新记录。

但当文件来自 `mirrorMinioToLocal`（web 上传已创建了 DB 记录），MD5 秒传变成了重复记录的来源——它找到了刚才 confirm-upload 创建的记录，又创建了一条。

## 修复

### `FileSystemWatcher.ensureFileInDb` — 增加 parentId + fileName 二次去重

**文件:** `allahpan-core/src/main/java/com/allahpan/component/FileSystemWatcher.java`

在 storageKey 检查之后、try 块之前，增加 `parentId + fileName` 的唯一性检查：

```java
// 二次去重：web 上传 → mirrorMinioToLocal → watcher 检测到时，
// DB 已有记录但 storageKey 格式不同（MinIO key vs 本地相对路径），
// 因此用 parentId + fileName 兜底检查，避免创建重复记录
String fileName = absolutePath.getFileName().toString();
Long parentId = findParentId(absolutePath);
FileExample nameEx = new FileExample();
nameEx.createCriteria()
        .andParentIdEqualTo(parentId)
        .andFileNameEqualTo(fileName)
        .andDeleteTimeIsNull();
if (!fileMapper.selectByExample(nameEx).isEmpty()) {
    log.debug("文件已在 DB 中（web 上传已镜像到本地），跳过: {}", storageKey);
    return;
}
```

**为什么放在 storageKey 检查之后而非之前：**
- storageKey 格式在 watcher 自发现文件时是一致的（本地路径 = 本地路径）
- 放在之后避免对 watcher 正常流程增加不必要的 DB 查询
- 只在 web 上传触发的 watcher 事件中才需要这个兜底检查

**与 `FileServiceImpl.assertNameUnique` 逻辑一致：**
```java
// FileServiceImpl.java:404
private void assertNameUnique(Long parentId, String fileName) {
    FileExample example = new FileExample();
    example.createCriteria()
            .andParentIdEqualTo(parentId)
            .andFileNameEqualTo(fileName)
            .andDeleteTimeIsNull();
    Asserts.isTrue(fileMapper.selectByExample(example).isEmpty(),
            "同名文件或文件夹已存在");
}
```

两者使用相同的 `parentId + fileName + deleteTimeIsNull` 组合判断，确保整个系统中同名去重逻辑一致。

### 修复范围

仅修改 `FileSystemWatcher.java` 一处，约 14 行新增代码。不涉及前端、API、数据库 schema 变更。

## 这个 bug 为什么难发现

1. **两条记录看起来都是合法的：** 都有正确的 storageKey、filePath、MD5，都指向同一个 MinIO 对象
2. **时序依赖：** 需要 watcher 在 `mirrorMinioToLocal` 写盘后、管线完成前触发——通常 1000ms debounce 内就会触发
3. **storageKey 不一致是设计上的：** MinIO key 用 UUID 格式避免冲突，本地路径用原始文件名——各自合理，但在 watcher 去重时产生了碰撞

## 关联文档

- [03 — 文件上传流程](../architecture/03-file-upload-flow.md)
- [04 — 文件操作](../architecture/04-file-operations.md)
- [08 — RabbitMQ 管线](../architecture/08-rabbitmq-pipeline.md)

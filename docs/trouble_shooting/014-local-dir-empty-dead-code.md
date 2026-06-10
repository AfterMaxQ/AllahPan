# 014 — C:\Users\<用户名>\AllahPan 目录为空（死代码误导）

**日期:** 2026-06-09

## 症状

用户发现 `C:\Users\<用户名>\AllahPan` 目录存在但是空的，尽管已经上传了很多文件。怀疑上传功能有问题。

## 原因

**不是文件上传失败，而是文件根本不存储在本地磁盘。**

AllahPan 使用 **MinIO 对象存储**（Docker 容器，`localhost:9000`，bucket: `allahpan-files`）作为文件存储后端。上传流程为：

```
浏览器 → fetch() PUT → MinIO 预签名 URL (直传)
                         ↓
后端 → MySQL files 表（仅元数据：storageKey, fileName, fileSize 等）
```

`FileStorageConfig.java` 是一个**死代码类**（零引用）——它在 `@PostConstruct` 中自动创建了 `%USERPROFILE%/AllahPan` 目录，但 `getRootDir()` 和 `getUserDir()` 方法在整个项目中没有任何调用方。Spring 仅因 `@Configuration` 注解而实例化它，目录被创建但永远不被写入。

## 修复

1. 删除 `allahpan-core/src/main/java/com/allahpan/config/FileStorageConfig.java`
2. 更新 `application-dev.yml` 中 `allahpan.file.root-dir` 配置为说明文件存储架构

## 如何查看已上传的文件

文件存储在 MinIO 中。可以通过以下方式查看：

- **Web UI**: http://localhost:9001 (MinIO Console，登录 minioadmin/minioadmin)
- **前端应用**: http://localhost:5173 (文件浏览器)
- **API**: `GET /api/file/list?parentId=0`

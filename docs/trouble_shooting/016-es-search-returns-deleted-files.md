# 016 — 搜索返回已删除文件（ES 索引与软删除不同步）

## 现象

搜索能命中已移入垃圾站的文件。前端文件列表不显示这些文件（`deleteTime IS NULL` 过滤），但 Elasticsearch 索引中仍有它们的文档，搜索结果中包含不可访问的文件。

## 根因

ES 索引的全生命周期缺少同步：

| 操作 | 之前的 ES 行为 | 问题 |
|------|---------------|------|
| 软删除 | 不处理 | ES 中旧文档保留，搜索仍能命中 |
| 恢复 | 不处理 | 若 ES 曾被清空，恢复后搜不到 |
| 永久删除 | 不处理 | ES 文档永远残留 |

根本原因：`FileServiceImpl.deleteFile()` 和 `permanentDelete()` 从未调 `EsIndexService.delete()`。

## 修复

**3 月 9 日** — `FileServiceImpl` 注入 `EsIndexService`，所有生命周期操作同步 ES：

```java
// 软删除 → 从 ES 移除
deleteFile() → esIndexService.delete(fileId)
deleteChildren() → esIndexService.delete(child.getId())

// 恢复 → 重新索引
restoreFile() → esIndexService.index(file)
restoreChildren() → esIndexService.index(child)

// 永久删除 → 确保从 ES 移除（兜底）
permanentDelete() → esIndexService.delete(fileId)
```

同时新增：

- **搜索服务** `DELETE /es-admin/files/_all` — 清空全量索引
- **Core 服务** `EsIndexServiceImpl.rebuildAll()` — 清空后根据 DB 未删除文件重建索引
- **Core 服务** `POST /api/search/rebuild-index` — API 触发重建
- **启动自清理** — `@PostConstruct` 延迟 30s 调用 `rebuildAll()`，自动清理历史孤儿文档

## 验证

1. 上传图片 → 等 OCR 完成 → 搜索能命中
2. 删除文件（软删除）→ 搜索不再命中
3. 恢复文件 → 搜索重新命中
4. 永久删除 → 搜索不再命中
5. `POST /api/search/rebuild-index` → 返回 `indexedCount` 与前端文件数一致
6. 服务重启 → 日志显示 `ES 孤儿文档已清理，当前索引 N 个文件`

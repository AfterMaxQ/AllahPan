# 018 — ES 索引漂移导致搜索返回过期/重复数据

## 现象

搜索"二条城"返回 28 条结果，但实际全是已删除的文件。同一个 PNG 文件出现十几次，内容描述各不相同。

前端文件列表只有 2 个文件，搜索却返回几十个。

## 根因

**ES 索引与 DB 状态漂移**。文件删除时 `esIndexService.delete()` 调用搜索服务 (:8081)，如果搜索服务当时未运行，删除静默失败（空 catch 块），ES 文档永久残留。

启动时的 `rebuildAll()` 只有一次 30s 延迟触发，搜索服务未就绪则永久跳过。

结果：ES 63 个文档 vs DB 3 个文件（差 60 个）。

## 修复

### 1. ES 操作加重试（`EsIndexServiceImpl.java`）

`delete()` 和 `index()` 各重试 3 次（2s/4s/6s 递增延迟），避免搜索服务短暂不可达导致操作丢失。

### 2. 启动清理改为轮询

不再单次 30s 延迟，改为每 5s 探测搜索服务健康状态，最多等 5 分钟。就绪后立即执行 `rebuildAll()`。

### 3. 定时对账（`@Scheduled`）

每 30 分钟全量 `rebuildAll()`，作为兜底安全网。首次延迟 10 分钟。

### 4. 手动重建端点

`POST /api/search/rebuild-index` 已存在，可在不重启的情况下手动触发。

## 涉及文件

| 文件 | 改动 |
|------|------|
| `allahpan-core/.../EsIndexServiceImpl.java` | 重试逻辑 + 轮询启动 + 定时对账 |

## 验证

```bash
# ES 文档数
curl -s http://localhost:9200/allahpan_files/_count
# 应与 DB 未删除文件数一致

# DB 未删除文件数
mysql> SELECT COUNT(*) FROM files WHERE delete_time IS NULL AND is_folder = 0;
```

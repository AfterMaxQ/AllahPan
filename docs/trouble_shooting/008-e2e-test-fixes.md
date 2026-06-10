# 008 — 端到端功能测试发现的 Bug 修复

**日期:** 2026-06-08 ~ 2026-06-09
**范围:** 文件恢复 / 上传对话框 / ES 降级 / processStatus 故障

---

## 背景

用真实桌面文件（79KB 文本、138MB 视频、1.1GB 视频、25MB PDF）进行端到端上传→下载→删除→垃圾站→恢复→永久删除全链路测试。发现 1 个后端 Bug 和 2 个前端问题。

---

## 问题 1: 垃圾站恢复功能无效（严重 Bug）

**现象:**
- `PUT /api/file/trash/{id}/restore` 返回 `200 操作成功`
- 但文件仍在垃圾站，`delete_time` 未清除
- 数据库 `delete_time IS NOT NULL` 依然为 true

**原因:** `FileServiceImpl.restoreFile()` 调用 `fileMapper.updateByPrimaryKeySelective(file)`。MyBatis Generator 的 `updateByPrimaryKeySelective` 在 XML 中用 `<if test="deleteTime != null">` 判断，当 `deleteTime` 为 `null` 时跳过该列——导致 `SET delete_time = NULL` 永远不会生成。

**修复:** 将 `FileServiceImpl.java` 中 `restoreFile()` 和 `restoreChildren()` 的 `updateByPrimaryKeySelective` 改为 `updateByPrimaryKey`。

`updateByPrimaryKey` 无条件包含所有列，NULL 值也能正常写入：

```java
// 修复前 (FileServiceImpl.java:221)
file.setDeleteTime(null);
fileMapper.updateByPrimaryKeySelective(file);  // <if test="deleteTime != null"> 跳过

// 修复后
file.setDeleteTime(null);
fileMapper.updateByPrimaryKey(file);           // 所有列都包含，NULL 正常写入
```

> **影响范围:** `restoreFile()` 第 220-221 行 + `restoreChildren()` 第 232-233 行。`updateByPrimaryKey` 写全量字段，需确保 `selectByPrimaryKey` 拿到的是最新的完整记录。

---

## 问题 2: 上传对话框关闭后无法重新打开

**现象:** 关闭上传对话框后，再次点击"上传文件"按钮无响应。

**原因:** Element Plus 的 `el-dialog` 使用 teleport 渲染到 `body`，关闭后 `<div class="el-overlay el-modal-dialog">` 残留在 DOM 中（`display` 未置为 `none`），拦截后续按钮的点击事件。

**临时方案:** 刷新页面清除 DOM 残留。

**根因分析:** 对话框使用了 `destroy-on-close` 属性，但 Element Plus 在某些情况下（快速连续操作或异步任务未完成时关闭）可能不会完全清理 overlay 元素。

**长期修复建议:** 考虑监听对话框关闭事件，手动清理残留 overlay，或升级 Element Plus 版本。

---

## 问题 3: Playwright 右键菜单测试限制

**现象:** Playwright `page.mouse.click({ button: 'right' })` 不派发 `contextmenu` 事件，导致右键菜单无法通过标准 Playwright API 触发。

**根因:** Playwright 的 `mouse.click` 只派发 `mousedown` + `mouseup`，不派发 `contextmenu` 事件。Chromium 的 `contextmenu` 事件需要由操作系统右键手势触发，而非程序化鼠标事件。

**解决方案:** 使用 `page.evaluate()` 手动派发 `MouseEvent('contextmenu')`：
```js
card.dispatchEvent(new MouseEvent('contextmenu', {
  bubbles: true, cancelable: true,
  clientX: rect.left + rect.width/2,
  clientY: rect.top + rect.height/2,
  button: 2, buttons: 2, view: window
}));
```

> 这仅影响自动化测试，不影响真实用户操作。

---

## 问题 4: ES 索引异常导致所有文件 processStatus = -1（严重 Bug）

**现象:**
- 所有上传的文件最终状态显示"失败"
- 即使文件功能正常（可下载、可预览），前端也显示红色"失败"标签

**原因:**

`EsIndexServiceImpl.index()` 在 Elasticsearch 不可用时：

```java
} catch (Exception e) {
    throw new RuntimeException("ES 索引失败", e);  // ← 重新抛出！
}
```

而 `delete()` 方法已经正确处理了异常（吞掉）。ES 索引是"锦上添花"的搜索功能，不应该阻塞核心文件处理流水线。

整个失败链路：
1. 文件上传 → processStatus=0 (PENDING)
2. RabbitMQ 消费 → 缩略图生成成功 → processStatus=1
3. 进入 ES 索引阶段 → `restTemplate.postForEntity` 连接 `localhost:8081` 被拒 → RuntimeException
4. `FileProcessReceiver` catch 块捕获 → 重试 3 次（30s/60s/120s）
5. 3 次全部失败（ES/search 服务未启动）→ processStatus=-1

**修复:**

`EsIndexServiceImpl.java` — `index()` 改为降级处理（warn 日志 + 吞异常），与 `delete()` 行为一致：

```java
// 修复前
} catch (Exception e) {
    throw new RuntimeException("ES 索引失败", e);
}

// 修复后
} catch (Exception e) {
    LOG.warn("ES 索引失败（搜索服务不可用，文件仍可正常使用）: {}, 原因: {}",
            file.getFileName(), e.getMessage());
}
```

> **设计原则:** ES 索引是可选增强功能，不是核心流程。搜索服务不可用时文件上传/下载/管理应正常工作，只是搜索结果为空。

---

## 测试结果总结

| 功能 | 测试数据 | 结果 | 备注 |
|------|---------|------|------|
| 邮箱验证码登录 | browser@test.com | ✅ 正常 | |
| 密码登录 | Test123456 | ✅ 正常 | |
| 小文件上传 | 3月到7月 计划.txt (80KB) | ✅ 正常 | MD5 秒传 + MinIO 直传 |
| 中文件上传 | 战地5.mp4 (138MB) | ✅ 正常 | 本地 MinIO 秒级完成 |
| 大文件上传 | SpaceX 猎鹰重型.mp4 (1.1GB) | ✅ 正常 | 磁盘直写，~1秒完成 |
| 文件下载 | 全部文件 | ✅ 正常 | 预签名 URL + 文件完整性 OK |
| 软删除 | 单个 + 批量 | ✅ 正常 | |
| 垃圾站列表 | 分页查询 | ✅ 正常 | delete_time DESC 排序 |
| 垃圾站恢复 | PUT /trash/{id}/restore | 🔧 已修复 | updateByPrimaryKeySelective 不更新 NULL |
| 永久删除 | DELETE /trash/{id} | ✅ 正常 | DB 记录 + MinIO 对象清理 |
| 右键菜单 | FileCard 组件 | ⚠️ 仅测试限制 | 合成事件可用 |
| 面包屑导航 | 根目录 | ✅ 正常 | |
| 网格/列表切换 | viewMode | ✅ 正常 | |

### 最终数据库状态

```
| id | file_name                                     | size_mb | active |
|----|-----------------------------------------------|---------|--------|
| 1  | 《马来西亚史》_12619336.pdf                      | 25.0    | ✅     |
| 2  | 3月到7月 计划.txt                               | 0.1     | ✅     |
| 4  | SpaceX_猎鹰重型_现代工程的杰作(高燃混剪)....mp4    | 1088.1  | ✅     |
```

文件 3（战地5.mp4）已永久删除。

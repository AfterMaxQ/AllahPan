# 019 — 搜索高亮不显示 / contentSnippets 为空

## 现象

搜索返回了匹配结果（有 score），但前端不显示内容高亮片段（`contentSnippets`），也没有文件名高亮（`fileNameHighlight`）。用户只能看到文件列表，看不到关键词在原文中的匹配位置。

## 根因

ES `originText` 字段使用 `ik_max_word` 分词器。`ik_max_word` 会将「树木」作为一个整体 token，不产生单独的「树」token。当搜索单字「树」时，匹配发生在 `originText.char` 子字段（`char_split` 分析器逐字切分），但高亮（highlight）只配置了父字段 `originText`。

ES 的高亮机制在指定字段上重新运行分析器来定位匹配项——`originText` 的 `ik_max_word` 找不到「树」token，因此不生成高亮片段。

```
搜索"树" → multi_match 走 originText.char 命中 ✓
         → highlight 只配了 originText → ik_max_word 找不到"树" ✗
```

## 修复

**2026-06-10** — `EsFileServiceImpl.search()` 两处改动：

### 1. 添加 `originText.char` 高亮配置

```java
// 新增第三个 .fields() 调用
.fields("originText.char", hf -> hf.numberOfFragments(3).fragmentSize(100)
        .preTags("<mark>").postTags("</mark>"))
```

### 2. 高亮读取加 fallback

```java
// 原逻辑只读 originText
if (hit.highlight().containsKey("originText")) {
    item.put("contentSnippets", hit.highlight().get("originText"));
}
// 新增：originText 没高亮时 fallback 到 originText.char
else if (hit.highlight().containsKey("originText.char")) {
    item.put("contentSnippets", hit.highlight().get("originText.char"));
}
```

### 附带前端改进

`SearchResultItem.vue`：
- 内容片段区域添加「匹配内容」标签
- `<mark>` 背景色从 `--el-color-primary-light-7`（`#EEDBCE`）提升到 `--el-color-primary-light-5`（`#E2C7B1`），解决在 `#FAF7F2` 底色上几乎看不见的问题

## 验证

```bash
# 直接测 ES 高亮
curl -s -X POST "http://localhost:9200/allahpan_files/_search" \
  -H "Content-Type: application/json" -d '{
  "query": {"match": {"originText.char": "树"}},
  "highlight": {"fields": {"originText.char": {
    "number_of_fragments": 3, "fragment_size": 100,
    "pre_tags": ["<mark>"], "post_tags": ["</mark>"]
  }}},
  "size": 2
}'
```

前端搜索「树」，确认结果卡片显示「匹配内容」标签和带 `<mark>` 高亮的片段。

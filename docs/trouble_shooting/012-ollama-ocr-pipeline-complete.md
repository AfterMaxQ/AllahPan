# 012 — Ollama OCR 管线完整排查与修复

## 时间线

2026-06-09 — Ollama qwen3-vl:4b → qwen3.5:2b 迁移，经过 10+ 轮迭代测试，最终 OCR 管线稳定运行。

---

## 最终方案

**模型**：`qwen3.5:2b`（2.7GB，支持 Text + Image）
**关键参数**：`think: false` + `num_predict: 4096` + `num_ctx: 8192`
**性能**：3.1s / 359 tokens / 699 chars OCR 文本 / 无 thinking 开销

```yaml
# application-dev.yml
ollama:
  model: qwen3.5:2b
  timeout: 60
  num-predict: 4096
```

```java
// OllamaService.java — 原始 JSON 字符串请求体
String body = String.format(
    "{\"model\":\"%s\",\"stream\":false,\"think\":false,"
    + "\"options\":{\"num_predict\":%d,\"num_ctx\":8192},"
    + "\"messages\":[{\"role\":\"user\",\"content\":\"%s\",\"images\":[\"%s\"]}]}",
    model, numPredict, escapeJson(prompt), base64Image);
```

---

## 完整排查过程

### 第一层：qwen3-vl:4b OCR 输出始终为空

**现象**：Ollama API 返回 HTTP 200，`message.content` 为空字符串，`done_reason=length`，`eval_count` 仅 52~64 tokens。

**根因**：`qwen3-vl:4b` 的 Modelfile 使用 `RENDERER qwen3-vl-thinking`，模型在输出内容前进行内部推理（thinking），消耗全部 token 配额：

```
Modelfile:
  RENDERER qwen3-vl-thinking
  PARSER qwen3-vl-thinking
  # 未设置 num_predict → 默认 128 tokens
```

Ollama 响应中两个字段分离：
- `message.thinking` — 内部推理（6178 chars）
- `message.content` — 实际答案（0 chars，因为 token 被 thinking 耗尽）

**修复**：将 `num_predict` 提升到 32768，给 thinking + 输出留足空间。

**token 消耗分析**：

| num_predict | eval_count | thinking | content | done_reason |
|-------------|-----------|----------|---------|-------------|
| 未设置(~128) | 52 | 部分 | **0** | length |
| 4096 | 4096 | 部分 | **0** | length |
| 32768 | 3733 | 6178 chars | **956 chars** | stop |

---

### 第二层：Java 端 `num_predict` 不生效

**现象**：PowerShell curl 直调 Ollama 时 `num_predict=32768` 正常工作（content=956 chars），但 Java 代码通过 RestTemplate 发送相同参数时 `eval_count` 始终只有 43~64 tokens。

**根因**：Spring RestTemplate + Jackson 序列化 `Map<String, Object>` 对象时，`options` 子 Map 在序列化过程中丢失。Ollama 收到的请求中 `options` 为空或不完整，`num_predict` 从未传递到服务端。

```java
// ❌ 错误 — Jackson 序列化 Map 导致 options 丢失
Map<String, Object> request = new HashMap<>();
request.put("options", Map.of("num_predict", numPredict));
HttpEntity<Map<String, Object>> entity = new HttpEntity<>(request, headers);
// 实际发出的 JSON: {"model":"...","stream":false,"options":null,...}
```

**修复**：使用原始 JSON 字符串构建请求体，绕过 Jackson 序列化：

```java
// ✅ 正确 — 原始 JSON 字符串
String body = String.format(
    "{\"model\":\"%s\",\"stream\":false,\"options\":{\"num_predict\":%d,\"num_ctx\":8192},"
    + "\"messages\":[{\"role\":\"user\",\"content\":\"%s\",\"images\":[\"%s\"]}]}",
    model, numPredict, escapeJson(prompt), base64Image);
HttpEntity<String> entity = new HttpEntity<>(body, headers);
```

---

### 第三层：`think=false` 对 qwen3-vl 无效（Ollama 已知 Bug）

**现象**：在请求体中添加 `"think": false`（顶层字段，非 options），qwen3-vl:4b 仍然生成 thinking，`done_reason=length`，content 仍为空。

**根因**：这是 Ollama 官方已知 bug — [GitHub Issue #13353](https://github.com/ollama/ollama/issues/13353)。`Qwen3VLRenderer` 和 `Qwen3VLParser` 完全忽略 `think` API 参数：

```go
// ollama/model/renderers/qwen3vl.go — Bug 版本
// think 参数被接收但从未传递给 renderer
func (r *Qwen3VLRenderer) Render(...) {
    isThinking := r.isThinking  // 始终使用构造时的值
    // think 参数被丢弃
}
```

**状态**：截至 2026-06-09，该 issue 仍在 Open 状态，Ollama 0.30.6 尚未修复。

**尝试的 workaround 1 — 自定义 instruct 模型**：

```bash
# 创建非 thinking 变体
cat > Modelfile << EOF
FROM qwen3-vl:4b
RENDERER qwen3-vl-instruct
PARSER qwen3-vl-instruct
PARAMETER num_predict 8192
PARAMETER temperature 0
EOF
ollama create qwen3-vl:4b-ocr -f Modelfile
```

效果：thinking 不再进入 `message.thinking` 字段（`thinking_len=0`），但模型仍输出 `<think>...</think>` 标签到 `message.content` 中。需要后处理 `stripThinking()` 剥离标签。

问题：instruct 模型仍消耗大量 token 用于思考（eval=4144, raw=8973 chars），实际 OCR 结果仅 71 chars（被截断）。

---

### 第四层：迁移到 qwen3.5:2b

**发现**：qwen3.5 系列模型对 `think=false` 有完善支持（不同于 qwen3-vl）。

**qwen3.5:2b 测试结果**：

| 配置 | 耗时 | tokens | thinking | content | 状态 |
|------|------|--------|----------|---------|------|
| 默认（think 开启）| 9.4s | 194 | 0 | 311 chars | 输出为 JSON/bbox 格式 |
| `think=false` + plain text prompt | 8.0s | 37 | 0 | 61 chars | 文字格式正确但被截断 |
| `think=false` + num_predict=32768 | **6.5s** | 465 | 0 | **800 chars** | **完整提取** |
| `think=false` + num_predict=4096 | **3.1s** | 359 | 0 | **699 chars** | **完整提取** |

**关键发现**：`num_predict=4096` 对 qwen3.5:2b 已完全足够（359 tokens 即可完成），远小于 qwen3-vl:4b 的 3000+ tokens 需求。

**qwen3.5:2b vs qwen3-vl:4b 对比**：

| 指标 | qwen3-vl:4b | qwen3.5:2b | 提升 |
|------|------------|------------|------|
| OCR 耗时 | 42s | 3s | **14x** |
| Token 消耗 | 3700+ | 359 | **10x** |
| Thinking 开销 | 6178 chars | 0 | **消除** |
| 模型大小 | 3.3GB | 2.7GB | **-18%** |
| `think=false` | Bug #13353 | **正常** | — |
| 输出后处理 | 需 stripThinking | **无需** | — |

---

### 附带修复：`FileServiceImpl.preUpload()` md5 null 异常

**现象**：`POST /api/file/pre-upload` 在 `md5` 字段为 null 时返回 HTTP 200 + body `{"code":401}`。

**根因**：`FileServiceImpl.preUpload()` 调用 `andMd5EqualTo(null)` → MyBatis Generator 抛出 `RuntimeException("Value for md5 cannot be null")` → 异常被 AOP 层吞掉 → Spring 默认错误处理返回了 401 响应（误导性）。

**日志证据**：
```
ERROR --- POST /api/file/pre-upload
Class: FileController.preUpload
Error: Value for md5 cannot be null
```

**修复**：
```java
// 秒传检测仅在 md5 非空时执行
if (md5 != null && !md5.isEmpty()) {
    example.createCriteria().andMd5EqualTo(md5)...;
    // 秒传逻辑...
}
```

---

### Ollama 进程卡死

**现象**：所有 API 请求（包括 `ollama run` CLI）永久挂起，Ollama 进程存在但无 runner 子进程。

**根因**：qwen3-vl:4b 模型加载到 VRAM 后状态异常，模型 worker 进程退出但 Ollama 主进程未感知到，导致请求队列永久阻塞。

**修复**：强制终止 Ollama 进程并重启：
```powershell
Stop-Process -Name "ollama" -Force
Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
```

---

### 4K 图片处理

**qwen3-vl:4b**：4K（3840×2160）图片的 OCR 请求返回"无文字"或报错。根因是 Q4_K_M 量化（4-bit）限制了视觉编码器，4K 分辨率超出处理范围。需缩放到 1920×1080。

**qwen3.5:2b**：原生支持 4K，无需缩放。实测 20MB/23MB 的 4K 截图均正常处理：

| 4K 图片 | 耗时 | tokens | 结果 |
|---------|------|--------|------|
| Screenshot 1 (20MB) | 9.3s | 85 | 正确识别无文字 + 场景描述 |
| Screenshot 2 (23MB) | 6.3s | 42 | 正确识别无文字 + 场景描述 |

**结论**：迁移到 qwen3.5:2b 后，4K 不再是问题，无需额外缩放逻辑。

---

## 最终代码状态

### `OllamaService.java` 核心逻辑

```java
public String ocr(File file) {
    byte[] imageBytes;
    try (var is = minioUtil.getClient().getObject(
            GetObjectArgs.builder()
                .bucket(minioUtil.getBucketName())
                .object(file.getStorageKey())
                .build())) {
        imageBytes = is.readAllBytes();
    }
    String base64Image = Base64.getEncoder().encodeToString(imageBytes);

    String prompt = "Extract all text from this image. "
        + "If no text is present, respond with a single line of comma-separated keywords.";
    String body = String.format(
        "{\"model\":\"%s\",\"stream\":false,\"think\":false,"
        + "\"options\":{\"num_predict\":%d,\"num_ctx\":8192},"
        + "\"messages\":[{\"role\":\"user\",\"content\":\"%s\",\"images\":[\"%s\"]}]}",
        model, numPredict, escapeJson(prompt), base64Image);

    HttpHeaders headers = new HttpHeaders();
    headers.setContentType(MediaType.APPLICATION_JSON);
    HttpEntity<String> entity = new HttpEntity<>(body, headers);

    ResponseEntity<Map> response = restTemplate.exchange(
            baseUrl + "/api/chat", HttpMethod.POST, entity, Map.class);

    if (response.getBody() != null && response.getBody().get("message") != null) {
        Map<String, Object> message = (Map<String, Object>) response.getBody().get("message");
        String content = (String) message.get("content");
        String doneReason = (String) response.getBody().get("done_reason");
        Integer evalCount = (Integer) response.getBody().get("eval_count");
        LOG.info("OCR done_reason={} eval_count={} content={} chars",
                doneReason, evalCount, content != null ? content.length() : 0);
        return (content != null && !content.isEmpty()) ? content : null;
    }
    return null;
}

private String escapeJson(String s) {
    return s.replace("\\", "\\\\").replace("\"", "\\\"")
            .replace("\n", "\\n").replace("\r", "\\r");
}
```

### `FileServiceImpl.java` md5 null 修复

```java
@Override
public FileUploadResult preUpload(String md5, String fileName, Long parentId) {
    // 秒传检测（仅当 md5 非空时执行）
    if (md5 != null && !md5.isEmpty()) {
        FileExample example = new FileExample();
        example.createCriteria().andMd5EqualTo(md5)...;
        // ...
    }
    // 正常上传流程...
}
```

### 配置

```yaml
# application-dev.yml
ollama:
  base-url: http://localhost:11434
  model: qwen3.5:2b
  timeout: 60
  num-predict: 4096
```

---

## 端到端验证

```
Upload → RabbitMQ → Thumbnail(1) → Ollama OCR(2) → ES(fallback) → Completed(3)
                                         │
                                    qwen3.5:2b
                                    think=false
                                    num_predict=4096
                                    3.1s / 359 tokens
                                    699 chars OCR text
```

**验证命令**（PowerShell 直接测试 Ollama）：
```powershell
$imgBytes = [System.IO.File]::ReadAllBytes("图片路径")
$base64 = [Convert]::ToBase64String($imgBytes)

$body = @{
    model = "qwen3.5:2b"
    stream = $false
    think = $false
    options = @{ num_predict = 4096; num_ctx = 8192 }
    messages = @(@{
        role = "user"
        content = "Extract all text from this image."
        images = @($base64)
    })
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Uri "http://localhost:11434/api/chat" `
    -Method Post -Body $body -ContentType "application/json" -TimeoutSec 60
```

---

## 相关文档

- [009 — 文件上传卡在排队中或失败](009-file-upload-stuck-queuing-failed.md) — SpEL、端口冲突、管线韧性
- [010 — OllamaService HTTP 超时与提示词优化](010-ollama-timeout-and-prompt.md) — HTTP 超时修复、prompt 重写
- [011 — MinIO docker-compose 集成](011-minio-docker-compose-persistence.md) — MinIO 持久化配置
- [Ollama Issue #13353](https://github.com/ollama/ollama/issues/13353) — Qwen3VLRenderer 忽略 think 参数

---

## 已删除的模型

排查过程中创建/测试的临时模型已全部清理：
- ~~qwen3-vl:4b~~ — 原始模型（thinking bug，已删除）
- ~~qwen3-vl:4b-ocr~~ — 自定义 instruct 模型（已删除）
- ~~qwen3-vl:4b-nothink~~ — 自定义变体（已删除）

# 010 — OllamaService HTTP 超时与提示词优化

## 现象

当 Ollama 服务不可达或响应缓慢时，`OllamaService.ocr()` 的 HTTP 调用会永久阻塞，导致 RabbitMQ 消费者线程被挂起，所有后续消息都无法处理。

## 根因

`OllamaService` 中使用了 `new RestTemplate()` 的无参构造，该 RestTemplate 使用默认的 `SimpleClientHttpRequestFactory`，其 `connectTimeout` 和 `readTimeout` 均为 `-1`（无限等待）。

```java
// 修复前：无超时配置
private final RestTemplate restTemplate = new RestTemplate();
```

当 Ollama 服务（`localhost:11434`）不可达时：
1. TCP 连接尝试会等待操作系统默认超时（Windows 约 21 秒）
2. 即使连上，如果 Ollama 处理大图缓慢，读取也会无限等待
3. 消费者线程阻塞 → RabbitMQ 消息堆积 → 所有文件处理停滞

## 解决方案

### HTTP 超时

通过构造器注入 RestTemplate，设置显式超时：

```java
private final RestTemplate restTemplate;

public OllamaService(@Value("${ollama.timeout:60}") int timeoutSec) {
    SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
    factory.setConnectTimeout(Duration.ofSeconds(5));      // 连接超时 5s
    factory.setReadTimeout(Duration.ofSeconds(timeoutSec)); // 读取超时 60s（可配置）
    this.restTemplate = new RestTemplate(factory);
}
```

- **连接超时 5 秒**：TCP 握手超时，快速失败
- **读取超时可配置**：通过 `ollama.timeout` 控制（默认 60s），适配不同模型响应速度

### OCR 提示词重写

原提示词：
```
如果是文档内容，请提取这张图片中的所有文字内容，不要添加任何解释。如果是普通照片，请使用确定的关键词描述这张照片...
```

问题：冗长、指令模糊、输出格式不稳定。

新提示词（英文结构化）：
```
## Analysis Rule
- Text in image: transcribe verbatim.
- Photo/scene: output comma-separated keywords (e.g. cat,sofa,window,sunlight).
Output the result only. No prefixes, no explanations.
```

优势：
- 结构化规则格式（`##` + bullet points），模型更容易遵循
- 英文指令对 qwen3-vl 的 token 效率更高
- 明确输出格式（verbatim / comma-separated），便于下游 ES 索引
- "No prefixes, no explanations" 减少无用 token

## 验证

- 编译通过
- 原有 OCR 功能不受影响（仅超时控制和提示词变更）
- 配合 009 号修复的管线降级，Ollama 不可用时文件不会标记为失败

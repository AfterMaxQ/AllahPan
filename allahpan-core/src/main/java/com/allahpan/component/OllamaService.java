package com.allahpan.component;

import com.allahpan.mbg.model.File;
import com.allahpan.component.MinioUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.io.InputStream;
import java.util.Base64;
import java.util.Map;

@Service
public class OllamaService {

    private static final org.slf4j.Logger LOG = org.slf4j.LoggerFactory.getLogger(OllamaService.class);

    @Value("${ollama.base-url}")
    private String baseUrl;
    @Value("${ollama.model}")
    private String model;
    @Value("${ollama.num-predict:16384}")
    private int numPredict;

    @Autowired
    private MinioUtil minioUtil;

    private final RestTemplate restTemplate;

    public OllamaService(@Value("${ollama.timeout:120}") int timeoutSec) {
        org.springframework.http.client.SimpleClientHttpRequestFactory factory =
                new org.springframework.http.client.SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(java.time.Duration.ofSeconds(5));
        factory.setReadTimeout(java.time.Duration.ofSeconds(timeoutSec));
        this.restTemplate = new RestTemplate(factory);
    }

    public String ocr(File file) {
        try {
            byte[] imageBytes;
            LOG.info("OCR: reading from MinIO fileId={} storageKey='{}'", file.getId(), file.getStorageKey());
            try (InputStream is = minioUtil.getObject(file.getStorageKey())) {
                imageBytes = is.readAllBytes();
            }
            LOG.info("OCR: image read successfully fileId={} size={} bytes", file.getId(), imageBytes.length);
            String base64Image = Base64.getEncoder().encodeToString(imageBytes);

            // 图像分析提示词：根据图像是否包含文字，采用不同策略
            // - 含文字图像（文档/截图）：详细提取文字
            // - 无文字图像（风景/人物）：简短中文描述，不过度解读
            String prompt = "你是一个图像分析助手。请根据图像是否包含文字，选择对应规则输出：\n"
                    + "\n"
                    + "【含文字图像】（文档、截图、扫描件、带文字的图）：\n"
                    + "1. 文字提取：逐行提取所有可见文字，保留原文语言和排版。若无文字则写 [无文字]。\n"
                    + "2. 内容概括：1-2句话描述图像内容（中文）。\n"
                    + "3. 搜索标签：5-10个关键词，逗号分隔，中英文均可。\n"
                    + "\n"
                    + "【无文字图像】（风景、人物、绘画、纯图形）：\n"
                    + "1. 文字提取：[无文字]\n"
                    + "2. 内容概括：1句话描述画面内容（中文）。\n"
                    + "3. 搜索标签：3-5个关键词，逗号分隔，中英文均可。\n"
                    + "\n"
                    + "注意：\n"
                    + "- 只输出分析结果，不要寒暄或元评论。\n"
                    + "- 描述简洁实用，不要展开联想、抒情或过度解读。\n"
                    + "- 段落之间空行分隔。";
            String body = String.format(
                "{\"model\":\"%s\",\"stream\":false,\"think\":false,"
                + "\"options\":{\"num_predict\":%d,\"num_ctx\":8192},"
                + "\"messages\":[{\"role\":\"user\",\"content\":\"%s\",\"images\":[\"%s\"]}]}",
                model, numPredict, escapeJson(prompt), base64Image);

            LOG.info("OCR request: model={} num_predict={} body_size={} chars",
                    model, numPredict, body.length());

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
                        doneReason, evalCount,
                        content != null ? content.length() : 0);
                return (content != null && !content.isEmpty()) ? content : null;
            }
            return null;
        } catch (Exception e) {
            LOG.error("Ollama OCR failed: fileId={} storageKey='{}' errorType={} errorMessage={}",
                    file.getId(), file.getStorageKey(),
                    e.getClass().getSimpleName(), e.getMessage(), e);
            throw new RuntimeException("Ollama OCR failed for storageKey=" + file.getStorageKey(), e);
        }
    }

    private String escapeJson(String s) {
        return s.replace("\\", "\\\\").replace("\"", "\\\"")
                .replace("\n", "\\n").replace("\r", "\\r");
    }
}

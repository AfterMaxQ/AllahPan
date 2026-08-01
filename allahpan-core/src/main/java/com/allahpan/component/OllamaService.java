package com.allahpan.component;

import com.allahpan.common.log.StructuredLog;
import com.allahpan.mbg.model.File;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import javax.imageio.ImageIO;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
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
    @Value("${ollama.ocr-max-dimension:1536}")
    private int ocrMaxDimension;

    @Autowired
    private MinioUtil minioUtil;

    private final RestTemplate restTemplate;
    private final RestTemplate probeRestTemplate;

    public OllamaService(@Value("${ollama.timeout:120}") int timeoutSec) {
        org.springframework.http.client.SimpleClientHttpRequestFactory factory =
                new org.springframework.http.client.SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(java.time.Duration.ofSeconds(5));
        factory.setReadTimeout(java.time.Duration.ofSeconds(timeoutSec));
        this.restTemplate = new RestTemplate(factory);

        org.springframework.http.client.SimpleClientHttpRequestFactory probeFactory =
                new org.springframework.http.client.SimpleClientHttpRequestFactory();
        probeFactory.setConnectTimeout(java.time.Duration.ofSeconds(2));
        probeFactory.setReadTimeout(java.time.Duration.ofSeconds(3));
        this.probeRestTemplate = new RestTemplate(probeFactory);
    }

    /** 探测 Ollama 是否在线（轻量 GET /api/tags） */
    public boolean isAvailable() {
        try {
            ResponseEntity<String> resp = probeRestTemplate.getForEntity(baseUrl + "/api/tags", String.class);
            return resp.getStatusCode().is2xxSuccessful();
        } catch (Exception e) {
            LOG.debug("Ollama 不可用: {}", e.getMessage());
            return false;
        }
    }

    public String ocr(File file) {
        if (!isAvailable()) {
            throw new RuntimeException("Ollama 服务未启动或不可达: " + baseUrl);
        }
        try {
            byte[] imageBytes = loadOcrImageBytes(file);
            LOG.info(StructuredLog.event("file.ocr.started", "fileId", file.getId(),
                    "payloadBytes", imageBytes.length,
                    "source", file.getPreviewKey() != null ? "preview" :
                            (file.getThumbnailKey() != null ? "thumbnail" : "resized-original")));

            String base64Image = Base64.getEncoder().encodeToString(imageBytes);
            String prompt = buildPrompt();
            String body = String.format(
                "{\"model\":\"%s\",\"stream\":false,\"think\":false,"
                + "\"options\":{\"num_predict\":%d,\"num_ctx\":8192},"
                + "\"messages\":[{\"role\":\"user\",\"content\":\"%s\",\"images\":[\"%s\"]}]}",
                model, numPredict, escapeJson(prompt), base64Image);

            LOG.debug(StructuredLog.event("file.ocr.requested", "model", model,
                    "numPredict", numPredict, "bodyChars", body.length()));

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
                LOG.info(StructuredLog.event("file.ocr.completed", "fileId", file.getId(),
                        "doneReason", doneReason, "evalCount", evalCount,
                        "contentChars", content != null ? content.length() : 0));
                return (content != null && !content.isEmpty()) ? content : null;
            }
            return null;
        } catch (RuntimeException e) {
            throw e;
        } catch (Exception e) {
            LOG.error(StructuredLog.event("file.ocr.failed", "fileId", file.getId(),
                    "errorType", e.getClass().getSimpleName()), e);
            throw new RuntimeException("Ollama OCR failed", e);
        }
    }

    /**
     * 优先使用已生成的缩略图（~300px JPEG），否则将原图缩放至 ocr-max-dimension 以内再 JPEG 压缩。
     * 避免 20MB 原图 base64 后 ~30MB JSON 导致 OCR 极慢或超时。
     */
    private byte[] loadOcrImageBytes(File file) throws Exception {
        if (file.getPreviewKey() != null && !file.getPreviewKey().isBlank()) {
            try (InputStream is = minioUtil.getThumbnail(file.getPreviewKey())) {
                byte[] preview = is.readAllBytes();
                if (preview.length > 0) return preview;
            } catch (Exception e) {
                LOG.warn("预览图读取失败，回退缩略图: fileId={} {}", file.getId(), e.getMessage());
            }
        }
        if (file.getThumbnailKey() != null && !file.getThumbnailKey().isBlank()) {
            try (InputStream is = minioUtil.getThumbnail(file.getThumbnailKey())) {
                byte[] thumb = is.readAllBytes();
                if (thumb.length > 0) return thumb;
            } catch (Exception e) {
                LOG.warn("缩略图读取失败，回退原图缩放: fileId={} {}", file.getId(), e.getMessage());
            }
        }
        try (InputStream is = minioUtil.getObject(file.getStorageKey())) {
            BufferedImage original = ImageIO.read(is);
            if (original == null) {
                throw new RuntimeException("无法解码图片");
            }
            return toJpegBytes(resizeForOcr(original));
        }
    }

    private BufferedImage resizeForOcr(BufferedImage original) {
        int w = original.getWidth();
        int h = original.getHeight();
        int maxDim = Math.max(w, h);
        if (maxDim <= ocrMaxDimension) {
            if (original.getType() == BufferedImage.TYPE_INT_RGB) return original;
            BufferedImage rgb = new BufferedImage(w, h, BufferedImage.TYPE_INT_RGB);
            Graphics2D g = rgb.createGraphics();
            g.drawImage(original, 0, 0, null);
            g.dispose();
            return rgb;
        }
        double scale = (double) ocrMaxDimension / maxDim;
        int nw = Math.max(1, (int) Math.round(w * scale));
        int nh = Math.max(1, (int) Math.round(h * scale));
        BufferedImage scaled = new BufferedImage(nw, nh, BufferedImage.TYPE_INT_RGB);
        Graphics2D g = scaled.createGraphics();
        g.setRenderingHint(RenderingHints.KEY_INTERPOLATION, RenderingHints.VALUE_INTERPOLATION_BILINEAR);
        g.drawImage(original, 0, 0, nw, nh, null);
        g.dispose();
        return scaled;
    }

    private byte[] toJpegBytes(BufferedImage image) throws Exception {
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        ImageIO.write(image, "jpg", baos);
        return baos.toByteArray();
    }

    private String buildPrompt() {
        return "你是一个图像分析助手。请根据图像是否包含文字，选择对应规则输出：\n"
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
    }

    private String escapeJson(String s) {
        return s.replace("\\", "\\\\").replace("\"", "\\\"")
                .replace("\n", "\\n").replace("\r", "\\r");
    }
}

package com.allahpan.component;

import com.allahpan.domain.FileProcessMessage;
import com.allahpan.domain.FileProcessMessage.Stage;
import com.allahpan.mbg.mapper.FileMapper;
import com.allahpan.mbg.model.File;
import com.allahpan.service.FileService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.rabbit.annotation.RabbitHandler;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Component
@RabbitListener(queues = "allahpan.file.process")
public class FileProcessReceiver {
    private static final Logger LOG = LoggerFactory.getLogger(FileProcessReceiver.class);
    private static final int MAX_RETRY = 3;
    /** OCR 依赖宿主机 Ollama，允许更多次、更长间隔的重试（用户可能稍后手动启动） */
    private static final int MAX_OCR_RETRY = 12;

    @Autowired
    private ThumbnailGenerator thumbnailGenerator;
    @Autowired
    private TextExtractor textExtractor;
    @Autowired
    private EsIndexService esIndexService;
    @Autowired
    private FileMapper fileMapper;
    @Autowired
    private FileProcessSender sender;
    @Autowired
    private SseBroadcaster sseBroadcaster;
    @Autowired
    private OllamaService ollamaService;

    @RabbitHandler
    public void handle(FileProcessMessage message) {
        File file = fileMapper.selectByPrimaryKey(message.getFileId());
        if (file == null || file.getDeleteTime() != null) {
            LOG.warn("文件不存在或已删除: {}", message.getFileId());
            return;
        }
        LOG.info("Processing file: fileId={} fileName='{}' storageKey='{}' stage={}",
                file.getId(), file.getFileName(), file.getStorageKey(), message.getCurrentStage());
        try {
            switch (message.getCurrentStage()) {
                case UPLOADED -> {
                    boolean hasList = file.getThumbnailKey() != null && !file.getThumbnailKey().isBlank();
                    boolean hasPreview = file.getPreviewKey() != null && !file.getPreviewKey().isBlank();
                    if (file.getProcessStatus() != null && file.getProcessStatus() >= 1 && hasList && hasPreview) {
                        LOG.info("跳过已处理的缩略图阶段: fileId={}", file.getId());
                        return;
                    }
                    if (!hasList || !hasPreview) {
                        if (!hasList && !hasPreview) {
                            ThumbnailGenerator.ThumbnailResult result = thumbnailGenerator.generate(file);
                            if (result != null) {
                                file.setThumbnailKey(result.listKey());
                                file.setPreviewKey(result.previewKey());
                            }
                        } else if (!hasPreview) {
                            String previewKey = thumbnailGenerator.generatePreviewOnly(file);
                            if (previewKey != null) {
                                file.setPreviewKey(previewKey);
                            }
                        } else {
                            ThumbnailGenerator.ThumbnailResult result = thumbnailGenerator.generate(file);
                            if (result != null) {
                                file.setThumbnailKey(result.listKey());
                                if (file.getPreviewKey() == null) {
                                    file.setPreviewKey(result.previewKey());
                                }
                            }
                        }
                    }
                    file.setProcessStatus((byte) 1);
                    fileMapper.updateByPrimaryKeySelective(file);
                    notifyStatusChange(file);
                    if (needsTextExtraction(file)) {
                        sender.sendProcess(new FileProcessMessage(file.getId(), Stage.THUMBNAILED));
                    } else {
                        sender.sendProcess(new FileProcessMessage(file.getId(), Stage.TEXT_EXTRACTED));
                    }
                }
                case THUMBNAILED -> {
	                    if (file.getProcessStatus() != null && file.getProcessStatus() >= 2
                                && hasOriginText(file)) {
	                        LOG.info("跳过已处理的文本提取阶段: fileId={}", file.getId());
	                        return;
	                    }
                    String text = textExtractor.extract(file);
                    if (text != null && !text.isEmpty()) {
                        file.setOriginText(text);
                    }
                    file.setProcessStatus((byte) 2);
                    fileMapper.updateByPrimaryKeySelective(file);
                    notifyStatusChange(file);
	                    sender.sendProcess(new FileProcessMessage(file.getId(), Stage.TEXT_EXTRACTED));
                }
                case TEXT_EXTRACTED -> {
	                    if (file.getProcessStatus() != null && file.getProcessStatus() >= 3) {
	                        LOG.info("跳过已完成的索引阶段: fileId={}", file.getId());
	                        return;
	                    }
                    esIndexService.index(file);
                    file.setProcessStatus((byte) 3);
                    fileMapper.updateByPrimaryKeySelective(file);
                    notifyStatusChange(file);
                    LOG.info("文件处理完成: {}", file.getFileName());
                }
                default -> LOG.warn("未知处理阶段: {}", message.getCurrentStage());
            }
        } catch (Exception e) {
            Retryability decision = classify(e);
            LOG.error("文件处理失败: storageKey='{}', 阶段={}, 重试次数={}, 错误类型={}",
                    file.getStorageKey(), message.getCurrentStage(), message.getRetryCount(), decision, e);

            // 智能重试：OCR 阶段允许更多次重试；Ollama 离线时保持 processStatus=1 等待服务恢复
            int maxRetry = message.getCurrentStage() == Stage.THUMBNAILED ? MAX_OCR_RETRY : MAX_RETRY;
            if (decision == Retryability.TRANSIENT && message.getRetryCount() < maxRetry) {
                long delay = message.getCurrentStage() == Stage.THUMBNAILED
                        ? ocrBackoffWithJitter(message.getRetryCount())
                        : backoffWithJitter(message.getRetryCount());
                message.setRetryCount((byte) (message.getRetryCount() + 1));
                message.setLastError(e.getMessage());
                LOG.info("瞬时错误，{}ms 后重试（第 {}/{} 次）: {}",
                        delay, message.getRetryCount(), maxRetry, file.getFileName());
                sender.sendRetry(message, delay);
                return;
            }

            // OCR 阶段重试耗尽且 Ollama 仍不可用 → 保持 status=1，由定时任务在 Ollama 恢复后继续
            if (message.getCurrentStage() == Stage.THUMBNAILED
                    && decision == Retryability.TRANSIENT
                    && !ollamaService.isAvailable()) {
                LOG.warn("Ollama 仍不可用，OCR 暂缓（保持等待状态）: {} — 启动 Ollama 后将自动重试",
                        file.getFileName());
                file.setProcessStatus((byte) 1);
                fileMapper.updateByPrimaryKeySelective(file);
                notifyStatusChange(file);
                return;
            }

            if (decision == Retryability.FATAL) {
                // 源文件缺失/不可读 → 文件真正不可用
                file.setProcessStatus((byte) -1);
                fileMapper.updateByPrimaryKeySelective(file);
                notifyStatusChange(file);
                LOG.error("文件处理彻底失败（源文件不可用）: {} (阶段={})",
                        file.getFileName(), message.getCurrentStage());
                return;
            }

            // 永久错误，或瞬时错误重试耗尽 —— 这些都是「增强处理」失败（缩略图/OCR/索引），
            // 文件本身仍可正常下载与预览。跳过当前阶段并继续后续流水线，
            // 保证文件最终仍可用、尽量可被搜索，而不是粗暴标记整体失败。
            skipStageAndContinue(file, message, decision);
        }
    }

    /**
     * 增强处理某一阶段失败后，跳过该阶段并推进到下一阶段。
     * 这样缩略图/OCR 的失败不会阻断后续的索引，文件最终仍能被搜索到。
     */
    private void skipStageAndContinue(File file, FileProcessMessage message, Retryability decision) {
        String reason = decision == Retryability.PERMANENT ? "不可恢复的处理错误" : "外部服务多次重试仍不可用";
        switch (message.getCurrentStage()) {
            case UPLOADED -> {
                LOG.warn("缩略图生成失败（{}），跳过并继续: {}", reason, file.getFileName());
                file.setProcessStatus((byte) 1);
                fileMapper.updateByPrimaryKeySelective(file);
                notifyStatusChange(file);
                if (needsTextExtraction(file)) {
                    sender.sendProcess(new FileProcessMessage(file.getId(), Stage.THUMBNAILED));
                } else {
                    sender.sendProcess(new FileProcessMessage(file.getId(), Stage.TEXT_EXTRACTED));
                }
            }
            case THUMBNAILED -> {
                LOG.warn("文本提取失败（{}），跳过并继续索引: {}", reason, file.getFileName());
                file.setProcessStatus((byte) 2);
                fileMapper.updateByPrimaryKeySelective(file);
                notifyStatusChange(file);
                sender.sendProcess(new FileProcessMessage(file.getId(), Stage.TEXT_EXTRACTED));
            }
            default -> {
                // 索引阶段失败（搜索服务/ES 不可用）→ 文件可用，仅暂不可被搜索
                LOG.warn("索引失败（{}），降级为可用（暂不可被搜索）: {}", reason, file.getFileName());
                file.setProcessStatus((byte) 3);
                fileMapper.updateByPrimaryKeySelective(file);
                notifyStatusChange(file);
            }
        }
    }

    /**
     * 通过 SSE 推送文件状态变更，前端无需刷新即可看到排队状态更新。
     */
    private void notifyStatusChange(File file) {
        try {
            sseBroadcaster.broadcast("file-updated", java.util.Map.of(
                    "fileId", file.getId(),
                    "parentId", file.getParentId() != null ? file.getParentId() : 0L,
                    "processStatus", file.getProcessStatus() != null ? (int) file.getProcessStatus() : 0,
                    "thumbnailKey", file.getThumbnailKey() != null ? file.getThumbnailKey() : "",
                    "previewKey", file.getPreviewKey() != null ? file.getPreviewKey() : "",
                    "originText", file.getOriginText() != null ? file.getOriginText() : ""
            ));
        } catch (Exception e) {
            LOG.debug("SSE 状态推送失败: {}", file.getId(), e);
        }
    }

    /** 错误可重试性分类 */
    private enum Retryability {
        /** 瞬时错误（网络/超时/外部服务暂时不可用）—— 值得重试 */
        TRANSIENT,
        /** 永久错误（解析失败/格式不支持/损坏文件）—— 重试无意义，但文件本身仍可用 */
        PERMANENT,
        /** 致命错误（源文件缺失/不可读）—— 文件真正不可用 */
        FATAL
    }

    /**
     * 智能分类错误，决定重试策略。
     * - 网络/超时/外部服务（Ollama/ES/MinIO 暂时不可达）→ TRANSIENT（退避重试）
     * - 源文件在存储中缺失/不可读 → FATAL（重试无意义，文件不可用）
     * - 其余（文档解析失败、格式不支持、内容损坏等确定性错误）→ PERMANENT（跳过该阶段）
     */
    private Retryability classify(Exception e) {
        // 数据库瞬时不可用 → 值得重试
        if (e instanceof org.springframework.dao.TransientDataAccessException
                || e instanceof org.springframework.dao.RecoverableDataAccessException) {
            return Retryability.TRANSIENT;
        }
        String msg = collectMessages(e);

        // 源文件缺失 → 致命
        if (msg.contains("nosuchkey") || msg.contains("does not exist")
                || msg.contains("not exist") || msg.contains("object not found")
                || msg.contains("no such file") || msg.contains("filenotfound")) {
            return Retryability.FATAL;
        }

        // 网络 / 外部服务暂时不可用 → 瞬时
        if (msg.contains("connect") || msg.contains("timeout") || msg.contains("refused")
                || msg.contains("unreachable") || msg.contains("i/o error") || msg.contains("socket")
                || msg.contains("connection reset") || msg.contains("temporarily")
                || msg.contains("resourceaccessexception") || msg.contains("ollama")
                || msg.contains("502") || msg.contains("503") || msg.contains("504")) {
            return Retryability.TRANSIENT;
        }

        // 其余确定性错误 → 永久（重试也不会成功）
        return Retryability.PERMANENT;
    }

    /** 收集异常链上的类名与消息，统一小写用于关键字匹配 */
    private String collectMessages(Throwable e) {
        StringBuilder sb = new StringBuilder();
        int depth = 0;
        while (e != null && depth < 10) {
            sb.append(e.getClass().getSimpleName()).append(' ');
            if (e.getMessage() != null) sb.append(e.getMessage()).append(' ');
            e = e.getCause();
            depth++;
        }
        return sb.toString().toLowerCase();
    }

    private boolean hasOriginText(File file) {
        return file.getOriginText() != null && !file.getOriginText().isBlank();
    }

    /**
     * OCR 专用退避：前几次快速重试（用户可能正在启动 Ollama），之后逐步拉长。
     * 5s → 10s → 20s → 40s → 80s → 120s → 300s（封顶）
     */
    private long ocrBackoffWithJitter(int retryCount) {
        long base = switch (retryCount) {
            case 0 -> 5_000L;
            case 1 -> 10_000L;
            case 2 -> 20_000L;
            case 3 -> 40_000L;
            case 4 -> 80_000L;
            case 5 -> 120_000L;
            default -> 300_000L;
        };
        long jitter = (long) (base * 0.15 * Math.random());
        return base + jitter;
    }

    /**
     * 指数退避 + 抖动：30s / 60s / 120s（上限 5 分钟），叠加 0~20% 随机抖动，
     * 避免大量任务同时重试造成「惊群」冲击外部服务。
     */
    private long backoffWithJitter(int retryCount) {
        long base = Math.min(30_000L * (1L << retryCount), 300_000L);
        long jitter = (long) (base * 0.2 * Math.random());
        return base + jitter;
    }

    /**
     * 判断文件是否需要文本提取。
     * IMAGE 类型通过 OCR 提取，DOCUMENT 可通过 PDFBox 提取。
     */
    private boolean needsTextExtraction(File file) {
        if (file.getFileType() == null) return false;
        return "IMAGE".equals(file.getFileType()) || "DOCUMENT".equals(file.getFileType());
    }
}

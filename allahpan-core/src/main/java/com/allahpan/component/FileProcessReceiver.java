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
    private FileSystemWatcher fileSystemWatcher;

    @RabbitHandler
    public void handle(FileProcessMessage message) {
        File file = fileMapper.selectByPrimaryKey(message.getFileId());
        if (file == null || file.getDeleteTime() != null) {
            LOG.warn("文件不存在或已删除: {}", message.getFileId());
            return;
        }
        try {
            switch (message.getCurrentStage()) {
                case UPLOADED -> {
                    if (file.getThumbnailKey() == null) {
                        String thumbnailKey = thumbnailGenerator.generate(file);
                        if (thumbnailKey != null) {
                            file.setThumbnailKey(thumbnailKey);
                        }
                    }
                    // 先发送下一阶段消息，再更新 DB 状态。
                    // 如果发送失败抛异常，DB 未修改，重试从当前 stage 重新开始。
                    if (needsTextExtraction(file)) {
                        sender.sendProcess(new FileProcessMessage(file.getId(), Stage.THUMBNAILED));
                    } else {
                        sender.sendProcess(new FileProcessMessage(file.getId(), Stage.TEXT_EXTRACTED));
                    }
                    file.setProcessStatus((byte) 1);
                    fileMapper.updateByPrimaryKeySelective(file);
                    notifyStatusChange(file);
                }
                case THUMBNAILED -> {
                    String text = textExtractor.extract(file);
                    if (text != null && !text.isEmpty()) {
                        file.setOriginText(text);
                    }
                    // 先发送下一阶段消息，再更新 DB 状态
                    sender.sendProcess(new FileProcessMessage(file.getId(), Stage.TEXT_EXTRACTED));
                    file.setProcessStatus((byte) 2);
                    fileMapper.updateByPrimaryKeySelective(file);
                    notifyStatusChange(file);
                }
                case TEXT_EXTRACTED -> {
                    esIndexService.index(file);
                    file.setProcessStatus((byte) 3);
                    fileMapper.updateByPrimaryKeySelective(file);
                    notifyStatusChange(file);
                    LOG.info("文件处理完成: {}", file.getFileName());
                }
                default -> LOG.warn("未知处理阶段: {}", message.getCurrentStage());
            }
        } catch (Exception e) {
            LOG.error("文件处理失败: {}, 阶段: {}, 重试: {}",
                    file.getFileName(), message.getCurrentStage(), message.getRetryCount(), e);
            if (message.getRetryCount() < MAX_RETRY) {
                // 递增延迟: 30s / 60s / 120s
                long delay = 30_000L * (1L << message.getRetryCount());
                message.setRetryCount((byte) (message.getRetryCount() + 1));
                message.setLastError(e.getMessage());
                sender.sendRetry(message, delay);
            } else {
                // 重试耗尽 — 区分基础设施错误 vs 致命错误
                if (isInfrastructureError(e)) {
                    // 非关键组件（缩略图/Ollama/ES）不可用 → 降级，不标记失败
                    LOG.warn("非关键组件不可用，文件部分功能降级: {} (阶段: {})",
                            file.getFileName(), message.getCurrentStage());
                } else {
                    file.setProcessStatus((byte) -1);
                    fileMapper.updateByPrimaryKeySelective(file);
                    notifyStatusChange(file);
                    LOG.error("文件处理彻底失败: {}", file.getFileName());
                }
            }
        }
    }

    /**
     * 通过 SSE 推送文件状态变更，前端无需刷新即可看到排队状态更新。
     */
    private void notifyStatusChange(File file) {
        try {
            fileSystemWatcher.notifyAll("file-updated", java.util.Map.of(
                    "fileId", file.getId(),
                    "parentId", file.getParentId() != null ? file.getParentId() : 0L,
                    "processStatus", file.getProcessStatus() != null ? (int) file.getProcessStatus() : 0,
                    "thumbnailKey", file.getThumbnailKey() != null ? file.getThumbnailKey() : "",
                    "originText", file.getOriginText() != null ? file.getOriginText() : ""
            ));
        } catch (Exception e) {
            LOG.debug("SSE 状态推送失败: {}", file.getId(), e);
        }
    }

    /**
     * 判断是否为基础设施/外部服务错误（非致命，文件仍可使用）。
     * 网络连接、超时、服务不可达类错误 → true；数据库写入失败等 → false。
     */
    private boolean isInfrastructureError(Exception e) {
        if (e instanceof org.springframework.dao.DataAccessException) {
            return false; // 数据库错误 → 致命
        }
        String msg = (e.getMessage() != null ? e.getMessage() : "") + " "
                + (e.getCause() != null && e.getCause().getMessage() != null
                        ? e.getCause().getMessage() : "");
        String lower = msg.toLowerCase();
        return lower.contains("connect") || lower.contains("timeout")
                || lower.contains("refused") || lower.contains("unreachable")
                || lower.contains("i/o error") || lower.contains("socket")
                || lower.contains("ollama")
                || lower.contains("ocr") || e instanceof RuntimeException
                && e.getMessage() != null
                && (e.getMessage().contains("缩略图") || e.getMessage().contains("OCR"));
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

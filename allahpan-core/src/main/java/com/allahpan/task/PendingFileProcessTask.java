package com.allahpan.task;

import com.allahpan.component.FileProcessSender;
import com.allahpan.component.OllamaService;
import com.allahpan.component.SseBroadcaster;
import com.allahpan.component.ThumbnailGenerator;
import com.allahpan.domain.FileProcessMessage;
import com.allahpan.domain.FileProcessMessage.Stage;
import com.allahpan.mbg.mapper.FileMapper;
import com.allahpan.mbg.model.File;
import com.allahpan.mbg.model.FileExample;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * 扫描卡住或未完成的文件处理任务，重新入队。
 * 覆盖场景：RabbitMQ 短暂不可用导致消息丢失、Ollama 离线导致 OCR 暂缓等。
 */
@Component
public class PendingFileProcessTask {

    private static final Logger LOG = LoggerFactory.getLogger(PendingFileProcessTask.class);

    /** 创建超过此时间仍为 status=0 视为卡住（毫秒） */
    private static final long STUCK_UPLOADED_MS = 2 * 60_000L;
    /** OCR 等待超过此时间重新触发（毫秒） */
    private static final long STUCK_OCR_MS = 3 * 60_000L;

    @Autowired
    private FileMapper fileMapper;
    @Autowired
    private FileProcessSender sender;
    @Autowired
    private OllamaService ollamaService;
    @Autowired
    private ThumbnailGenerator thumbnailGenerator;
    @Autowired
    private SseBroadcaster sseBroadcaster;

    @Scheduled(fixedDelay = 120_000, initialDelay = 60_000)
    public void recoverPendingFiles() {
        recoverStuckAtUploaded();
        recoverMissingPreviews();
        recoverPendingOcr();
    }

    /** processStatus=0 且创建已超过 2 分钟 → 重新触发缩略图流水线 */
    private void recoverStuckAtUploaded() {
        FileExample example = new FileExample();
        example.createCriteria()
                .andIsFolderEqualTo((byte) 0)
                .andDeleteTimeIsNull()
                .andProcessStatusEqualTo((byte) 0);
        List<File> stuck = fileMapper.selectByExample(example);
        if (stuck.isEmpty()) return;

        long cutoff = System.currentTimeMillis() - STUCK_UPLOADED_MS;
        int count = 0;
        for (File file : stuck) {
            if (file.getCreateTime() != null && file.getCreateTime().getTime() > cutoff) continue;
            LOG.info("恢复卡住的上传后处理: fileId={} name='{}'", file.getId(), file.getFileName());
            sender.sendProcess(new FileProcessMessage(file.getId(), Stage.UPLOADED));
            count++;
        }
        if (count > 0) LOG.info("已恢复 {} 个卡住的上传后处理任务", count);
    }

    /** 历史文件缺少 previewKey → 补生成高清预览图（每轮最多 10 个） */
    private void recoverMissingPreviews() {
        FileExample example = new FileExample();
        example.createCriteria()
                .andIsFolderEqualTo((byte) 0)
                .andDeleteTimeIsNull()
                .andPreviewKeyIsNull();
        List<File> candidates = fileMapper.selectByExample(example);
        if (candidates.isEmpty()) return;

        int count = 0;
        for (File file : candidates) {
            if (count >= 10) break;
            if (!needsPreview(file)) continue;
            try {
                String previewKey = thumbnailGenerator.generatePreviewOnly(file);
                if (previewKey == null) continue;
                file.setPreviewKey(previewKey);
                fileMapper.updateByPrimaryKeySelective(file);
                notifyPreviewReady(file);
                LOG.info("补生成预览图: fileId={} name='{}'", file.getId(), file.getFileName());
                count++;
            } catch (Exception e) {
                LOG.warn("补生成预览图失败: fileId={} {}", file.getId(), e.getMessage());
            }
        }
        if (count > 0) LOG.info("已补生成 {} 个高清预览图", count);
    }

    private boolean needsPreview(File file) {
        if ("IMAGE".equals(file.getFileType())) return true;
        return "DOCUMENT".equals(file.getFileType())
                && file.getContentType() != null
                && file.getContentType().contains("pdf");
    }

    private void notifyPreviewReady(File file) {
        try {
            sseBroadcaster.broadcast("file-updated", java.util.Map.of(
                    "fileId", file.getId(),
                    "parentId", file.getParentId() != null ? file.getParentId() : 0L,
                    "processStatus", file.getProcessStatus() != null ? (int) file.getProcessStatus() : 0,
                    "thumbnailKey", file.getThumbnailKey() != null ? file.getThumbnailKey() : "",
                    "previewKey", file.getPreviewKey() != null ? file.getPreviewKey() : "",
                    "originText", ""
            ));
        } catch (Exception e) {
            LOG.debug("SSE 预览图推送失败: {}", file.getId(), e);
        }
    }

    /**
     * 图片 OCR 未完成（无 originText）且 Ollama 在线 → 重新触发 OCR。
     * 包括：status=1 等待中、status=2/3 但 OCR 被跳过的历史文件。
     */
    private void recoverPendingOcr() {
        if (!ollamaService.isAvailable()) return;

        FileExample example = new FileExample();
        example.createCriteria()
                .andIsFolderEqualTo((byte) 0)
                .andDeleteTimeIsNull()
                .andFileTypeEqualTo("IMAGE")
                .andProcessStatusLessThan((byte) 3);
        List<File> candidates = fileMapper.selectByExampleWithBLOBs(example);

        long ocrCutoff = System.currentTimeMillis() - STUCK_OCR_MS;
        int count = 0;
        for (File file : candidates) {
            if (hasOriginText(file)) continue;
            Byte status = file.getProcessStatus();
            if (status == null) continue;

            // status=0 由 recoverStuckAtUploaded 处理
            if (status == 0) continue;

            // status=1：等待 OCR，需超过冷却时间
            if (status == 1 && file.getCreateTime() != null
                    && file.getCreateTime().getTime() > ocrCutoff) {
                continue;
            }

            LOG.info("恢复待 OCR 图片: fileId={} status={} name='{}'",
                    file.getId(), status, file.getFileName());
            FileProcessMessage msg = new FileProcessMessage(file.getId(), Stage.THUMBNAILED);
            sender.sendProcess(msg);
            count++;
        }

        // 已标记就绪但缺少 OCR 的历史图片（Ollama 当时离线被跳过）
        FileExample readyExample = new FileExample();
        readyExample.createCriteria()
                .andIsFolderEqualTo((byte) 0)
                .andDeleteTimeIsNull()
                .andFileTypeEqualTo("IMAGE")
                .andProcessStatusEqualTo((byte) 3);
        for (File file : fileMapper.selectByExampleWithBLOBs(readyExample)) {
            if (hasOriginText(file)) continue;
            LOG.info("补跑历史图片 OCR: fileId={} name='{}'", file.getId(), file.getFileName());
            sender.sendProcess(new FileProcessMessage(file.getId(), Stage.THUMBNAILED));
            count++;
        }

        if (count > 0) LOG.info("已恢复/补跑 {} 个 OCR 任务", count);
    }

    private boolean hasOriginText(File file) {
        return file.getOriginText() != null && !file.getOriginText().isBlank();
    }
}

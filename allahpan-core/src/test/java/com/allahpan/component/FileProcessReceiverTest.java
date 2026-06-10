package com.allahpan.component;

import com.allahpan.domain.FileProcessMessage;
import com.allahpan.domain.FileProcessMessage.Stage;
import com.allahpan.mbg.mapper.FileMapper;
import com.allahpan.mbg.model.File;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

/**
 * FileProcessReceiver 管线韧性测试
 *
 * 核心规则：
 * - 非关键组件（缩略图、OCR、ES）失败 → 降级继续，不标记失败
 * - 只有数据库写入失败等关键错误才标记 status = -1
 */
@ExtendWith(MockitoExtension.class)
@org.mockito.junit.jupiter.MockitoSettings(strictness = org.mockito.quality.Strictness.LENIENT)
class FileProcessReceiverTest {

    @Mock private ThumbnailGenerator thumbnailGenerator;
    @Mock private TextExtractor textExtractor;
    @Mock private EsIndexService esIndexService;
    @Mock private FileMapper fileMapper;
    @Mock private FileProcessSender sender;

    @InjectMocks
    private FileProcessReceiver receiver;

    private File imageFile;
    private File otherFile;

    @BeforeEach
    void setUp() {
        imageFile = new File();
        imageFile.setId(1L);
        imageFile.setFileName("photo.jpg");
        imageFile.setFileType("IMAGE");
        imageFile.setStorageKey("1/2026/06/test.jpg");
        imageFile.setProcessStatus((byte) 0);
        imageFile.setDeleteTime(null);

        otherFile = new File();
        otherFile.setId(2L);
        otherFile.setFileName("doc.txt");
        otherFile.setFileType("OTHER");
        otherFile.setStorageKey("1/2026/06/test.txt");
        otherFile.setProcessStatus((byte) 0);
        otherFile.setDeleteTime(null);

        // Default: file exists
        when(fileMapper.selectByPrimaryKey(1L)).thenReturn(imageFile);
        when(fileMapper.selectByPrimaryKey(2L)).thenReturn(otherFile);
        when(fileMapper.updateByPrimaryKeySelective(any())).thenReturn(1);
        when(fileMapper.updateByPrimaryKeyWithBLOBs(any())).thenReturn(1);
    }

    // ======== RED 测试：基础设施错误不应标记文件为 -1 ========

    @Test
    void shouldDegradeNotFailWhenThumbnailExhaustsRetries() {
        // 缩略图生成始终失败（如 MinIO 挂了）
        when(thumbnailGenerator.generate(imageFile))
                .thenThrow(new RuntimeException("service connection refused"));

        // 模拟第 3 次重试（retryCount 已到最大值 MAX_RETRY=3）
        FileProcessMessage msg = new FileProcessMessage(1L, Stage.UPLOADED);
        msg.setRetryCount((byte) 3);  // 第 4 次尝试，应标记失败
        receiver.handle(msg);

        // ★ 期望：基础设施错误不应标记 processStatus = -1
        //    当前代码设置为 -1 → 这个断言会失败（RED）
        assertNotEquals((byte) -1, imageFile.getProcessStatus(),
                "基础设施错误（连接失败）不应导致文件标记为失败");
        // 文件应保留在 processStatus=0（未处理），管理员可手动重试
    }

    @Test
    void shouldDegradeNotFailWhenOllamaExhaustsRetries() {
        when(thumbnailGenerator.generate(imageFile)).thenReturn("thumb/test.jpg");
        when(textExtractor.extract(imageFile))
                .thenThrow(new RuntimeException("Ollama 连接超时"));

        FileProcessMessage msg = new FileProcessMessage(1L, Stage.THUMBNAILED);
        msg.setRetryCount((byte) 3);
        receiver.handle(msg);

        // ★ 期望：OCR 不可用时文件不标记为 -1，而是跳过 OCR 继续
        assertNotEquals((byte) -1, imageFile.getProcessStatus(),
                "OCR 服务不可用（Ollama）不应导致文件标记为失败");
    }

    @Test
    void shouldSkipThumbnailAndContinueWhenGeneratorThrows() {
        // 缩略图生成器抛异常（模拟服务不可达）
        when(thumbnailGenerator.generate(imageFile))
                .thenThrow(new RuntimeException("service connection refused"));
        // OCR 返回 null（不抛异常，因为缩略图失败后会跳过它吗？不 — UPLOADED 阶段抛异常会被全局 catch 拦截）
        // 这里的关键是：UPLOADED 阶段抛异常后，重试 3 次，最终应该降级而非标记 -1

        // 发送 UPLOADED 阶段消息
        FileProcessMessage msg = new FileProcessMessage(1L, Stage.UPLOADED);
        receiver.handle(msg);

        // 验证：不因缩略图失败就标记为 -1
        // 当前代码在 retryCount >= 3 时设置 -1；我们要改为：基础设施错误不标记 -1
        // 第一次失败时会进入 retry 分支，不会更新 status
        verify(fileMapper, never()).updateByPrimaryKeySelective(imageFile);
        // 但会发送重试消息
        verify(sender).sendRetry(any(), anyLong());
    }

    @Test
    void shouldCompletePipelineWhenTextExtractorThrows() {
        // 缩略图成功
        when(thumbnailGenerator.generate(imageFile)).thenReturn("thumb/abc.jpg");
        when(textExtractor.extract(imageFile))
                .thenThrow(new RuntimeException("Ollama 服务不可达"));

        // 发送 UPLOADED 阶段（会进入 THUMBNAILED）
        FileProcessMessage msg = new FileProcessMessage(1L, Stage.UPLOADED);
        receiver.handle(msg);

        // 验证：缩略图成功 → status 设置为 1，并发送下一阶段消息
        verify(sender).sendProcess(argThat(m -> m.getCurrentStage() == Stage.THUMBNAILED));
        verify(fileMapper).updateByPrimaryKeySelective(imageFile);
        assertEquals((byte) 1, imageFile.getProcessStatus());
    }

    @Test
    void shouldCompleteWhenThumbnailGeneratorReturnsNull() {
        // 非图片文件（如视频），缩略图生成返回 null
        when(thumbnailGenerator.generate(otherFile)).thenReturn(null);

        // OTHER 文件 needsTextExtraction = false → 跳过 THUMBNAILED，直接到 TEXT_EXTRACTED
        FileProcessMessage msg = new FileProcessMessage(2L, Stage.UPLOADED);
        receiver.handle(msg);

        // status 应该更新为 1
        verify(fileMapper).updateByPrimaryKeySelective(otherFile);
        assertEquals((byte) 1, otherFile.getProcessStatus());
        // 发送 TEXT_EXTRACTED 而不是 THUMBNAILED
        verify(sender).sendProcess(argThat(m -> m.getCurrentStage() == Stage.TEXT_EXTRACTED));
    }

    @Test
    void shouldCompletePipelineWhenEsIndexFails() {
        // ES 索引失败（但 EsIndexService.index() 内部已经 catch 了异常）
        doNothing().when(esIndexService).index(imageFile);

        // 发送 TEXT_EXTRACTED 阶段
        imageFile.setProcessStatus((byte) 2);
        FileProcessMessage msg = new FileProcessMessage(1L, Stage.TEXT_EXTRACTED);
        receiver.handle(msg);

        // ES 内部吞噬异常 → 状态正常流转到 3
        verify(esIndexService).index(imageFile);
        verify(fileMapper).updateByPrimaryKeySelective(imageFile);
        assertEquals((byte) 3, imageFile.getProcessStatus());
    }

    @Test
    void shouldNotProcessDeletedFile() {
        imageFile.setDeleteTime(new java.util.Date());
        FileProcessMessage msg = new FileProcessMessage(1L, Stage.UPLOADED);
        receiver.handle(msg);

        // 已删除文件 → 直接丢弃消息
        verify(thumbnailGenerator, never()).generate(any());
        verify(sender, never()).sendProcess(any());
    }

    @Test
    void shouldRetryWithIncreasingDelay() {
        when(thumbnailGenerator.generate(imageFile))
                .thenThrow(new RuntimeException("失败"));

        // retryCount = 0 → delay = 30s
        FileProcessMessage msg0 = new FileProcessMessage(1L, Stage.UPLOADED);
        receiver.handle(msg0);
        verify(sender).sendRetry(any(), eq(30_000L));

        // retryCount = 1 → delay = 60s
        FileProcessMessage msg1 = new FileProcessMessage(1L, Stage.UPLOADED);
        msg1.setRetryCount((byte) 1);
        receiver.handle(msg1);
        verify(sender).sendRetry(any(), eq(60_000L));

        // retryCount = 2 → delay = 120s
        FileProcessMessage msg2 = new FileProcessMessage(1L, Stage.UPLOADED);
        msg2.setRetryCount((byte) 2);
        receiver.handle(msg2);
        verify(sender).sendRetry(any(), eq(120_000L));
    }
}

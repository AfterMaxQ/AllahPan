package com.allahpan.domain;

import java.io.Serializable;

/**
 * RabbitMQ 消息实体：文件异步处理任务
 * 作用：封装文件处理的所有状态、参数，在队列中传输
 */
public class FileProcessMessage implements Serializable {
    public enum Stage {
        UPLOADED, THUMBNAILED, TEXT_EXTRACTED, INDEXED, FAILED
    }

    private Long fileId;
    private Stage currentStage;
    private byte retryCount;
    private String lastError;

    public FileProcessMessage() {}
    public FileProcessMessage(Long fileId, Stage currentStage) {
        this.fileId = fileId;
        this.currentStage = currentStage;
        this.retryCount = 0;
    }

    public Long getFileId() { return fileId; }
    public void setFileId(Long fileId) { this.fileId = fileId; }
    public Stage getCurrentStage() { return currentStage; }
    public void setCurrentStage(Stage currentStage) { this.currentStage = currentStage; }
    public byte getRetryCount() { return retryCount; }
    public void setRetryCount(byte retryCount) { this.retryCount = retryCount; }
    public String getLastError() { return lastError; }
    public void setLastError(String lastError) { this.lastError = lastError; }
}

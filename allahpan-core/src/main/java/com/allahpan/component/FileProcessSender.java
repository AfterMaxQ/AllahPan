package com.allahpan.component;

import com.allahpan.config.RabbitMqConfig;
import com.allahpan.domain.FileProcessMessage;
import com.allahpan.common.log.LogContext;
import com.allahpan.common.log.StructuredLog;
import org.springframework.amqp.core.MessagePostProcessor;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Autowired;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

@Component
public class FileProcessSender {
    private static final Logger LOG = LoggerFactory.getLogger(FileProcessSender.class);

    @Autowired
    private RabbitTemplate rabbitTemplate;

    public void sendProcess(FileProcessMessage message) {
        bindContext(message);
        rabbitTemplate.convertAndSend(
            RabbitMqConfig.PROCESS_EXCHANGE,  // 主交换机
            RabbitMqConfig.PROCESS_ROUTING_KEY, // 主路由键
            message);
        LOG.info(StructuredLog.event("file.process.queued", "fileId", message.getFileId(),
                "stage", message.getCurrentStage(), "retryCount", message.getRetryCount()));
    }

    public void sendRetry(FileProcessMessage message, long delayMs) {
    bindContext(message);
    // 消息后置处理器：修改消息属性
    MessagePostProcessor postProcessor = msg -> {
        // 设置消息过期时间（毫秒）
        msg.getMessageProperties().setExpiration(String.valueOf(delayMs));
        return msg;
    };
    // 发送到重试交换机
    rabbitTemplate.convertAndSend(
            RabbitMqConfig.RETRY_EXCHANGE, // 重试交换机
            RabbitMqConfig.RETRY_ROUTING_KEY_TTL, // 重试路由键
            message, // 消息
            postProcessor); // 携带过期时间
    LOG.warn(StructuredLog.event("file.process.retry", "fileId", message.getFileId(),
            "stage", message.getCurrentStage(), "retryCount", message.getRetryCount(),
            "delayMs", delayMs));
}

    private void bindContext(FileProcessMessage message) {
        String requestId = message.getRequestId();
        if (requestId == null || requestId.isBlank()) {
            requestId = LogContext.requestId() == null ? "scheduled" : LogContext.requestId();
            message.setRequestId(requestId);
        }
        if (message.getOperationId() == null || message.getOperationId().isBlank()) {
            message.setOperationId(LogContext.operationId() == null
                    ? LogContext.newJobId("file-process") : LogContext.operationId());
        }
    }
}

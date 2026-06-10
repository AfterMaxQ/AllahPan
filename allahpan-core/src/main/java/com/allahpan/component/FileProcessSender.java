package com.allahpan.component;

import com.allahpan.config.RabbitMqConfig;
import com.allahpan.domain.FileProcessMessage;
import org.springframework.amqp.core.MessagePostProcessor;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Component
public class FileProcessSender {

    @Autowired
    private RabbitTemplate rabbitTemplate;

    public void sendProcess(FileProcessMessage message) {
        rabbitTemplate.convertAndSend(
            RabbitMqConfig.PROCESS_EXCHANGE,  // 主交换机
            RabbitMqConfig.PROCESS_ROUTING_KEY, // 主路由键
            message); // 消息体
    }

    public void sendRetry(FileProcessMessage message, long delayMs) {
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
}
}

package com.allahpan.config;

import org.springframework.amqp.core.Binding;
import org.springframework.amqp.core.BindingBuilder;
import org.springframework.amqp.core.DirectExchange;
import org.springframework.amqp.core.ExchangeBuilder;
import org.springframework.amqp.core.Queue;
import org.springframework.amqp.core.QueueBuilder;
import org.springframework.amqp.support.converter.Jackson2JsonMessageConverter;
import org.springframework.amqp.support.converter.MessageConverter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * 文件处理消息队列配置
 * - 重试队列：TTL + DLX 模式，失败消息延迟重试
 */
@Configuration
public class RabbitMqConfig {

    public static final String PROCESS_EXCHANGE = "allahpan.file.process";
    public static final String PROCESS_QUEUE = "allahpan.file.process";
    public static final String PROCESS_ROUTING_KEY = "allahpan.file.process";

    // 重试相关（复用 mall 的 TTL + DLX 模式）
    public static final String RETRY_EXCHANGE = "allahpan.file.retry.direct";
    public static final String RETRY_QUEUE_TTL = "allahpan.file.retry.ttl";
    public static final String RETRY_ROUTING_KEY_TTL = "allahpan.file.retry.ttl";
    public static final String RETRY_ROUTING_KEY = "allahpan.file.retry";

    @Bean
    public DirectExchange processExchange() {
        return ExchangeBuilder.directExchange(PROCESS_EXCHANGE).durable(true).build();
    }

    @Bean
    public Queue processQueue() {
        return QueueBuilder.durable(PROCESS_QUEUE).build();
    }

    @Bean
    public Binding processBinding(DirectExchange processExchange, Queue processQueue) {
        return BindingBuilder.bind(processQueue).to(processExchange).with(PROCESS_ROUTING_KEY);
    }

    // ====== 重试延迟队列（TTL + DLX）======
    @Bean
    public DirectExchange retryExchange() {
        return ExchangeBuilder.directExchange(RETRY_EXCHANGE).durable(true).build();
    }

    @Bean
    public Queue retryTtlQueue() {
        return QueueBuilder.durable(RETRY_QUEUE_TTL)
                .withArgument("x-dead-letter-exchange", PROCESS_EXCHANGE)
                .withArgument("x-dead-letter-routing-key", PROCESS_ROUTING_KEY)
                .build();
    }

    @Bean
    public Binding retryTtlBinding(DirectExchange retryExchange, Queue retryTtlQueue) {
        return BindingBuilder.bind(retryTtlQueue).to(retryExchange).with(RETRY_ROUTING_KEY_TTL);
    }

    @Bean
    public MessageConverter messageConverter() {
        return new Jackson2JsonMessageConverter();
    }
}

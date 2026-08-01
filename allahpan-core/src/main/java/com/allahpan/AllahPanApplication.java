package com.allahpan;

import com.allahpan.config.RabbitMqConfig;
import com.allahpan.common.log.StructuredLog;
import org.mybatis.spring.annotation.MapperScan;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.rabbit.core.RabbitAdmin;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;

/**
 * AllahPan 共享云存储系统启动类
 */
@SpringBootApplication
@MapperScan({"com.allahpan.mbg.mapper", "com.allahpan.dao"})
public class AllahPanApplication {

    private static final Logger log = LoggerFactory.getLogger(AllahPanApplication.class);

    public static void main(String[] args) {
        SpringApplication.run(AllahPanApplication.class, args);
    }

    /**
     * 应用就绪后通过 RabbitTemplate.execute() 直接声明队列/交换机。
     * RabbitAdmin 的 declare*() 方法在某些条件下静默失败，
     * 此处直接通过 AMQP channel 声明，确保万无一失。
     */
    @Bean
    ApplicationRunner declareRabbitResources(RabbitTemplate rabbitTemplate) {
        return args -> {
            log.info(StructuredLog.event("rabbitmq.resources.declare_started"));
            try {
                rabbitTemplate.execute(channel -> {
                    channel.exchangeDeclare(RabbitMqConfig.PROCESS_EXCHANGE, "direct", true);
                    channel.queueDeclare(RabbitMqConfig.PROCESS_QUEUE, true, false, false, null);
                    channel.queueBind(RabbitMqConfig.PROCESS_QUEUE,
                            RabbitMqConfig.PROCESS_EXCHANGE,
                            RabbitMqConfig.PROCESS_ROUTING_KEY);

                    channel.exchangeDeclare(RabbitMqConfig.RETRY_EXCHANGE, "direct", true);
                    java.util.Map<String, Object> args_ = new java.util.HashMap<>();
                    args_.put("x-dead-letter-exchange", RabbitMqConfig.PROCESS_EXCHANGE);
                    args_.put("x-dead-letter-routing-key", RabbitMqConfig.PROCESS_ROUTING_KEY);
                    channel.queueDeclare(RabbitMqConfig.RETRY_QUEUE_TTL, true, false, false, args_);
                    channel.queueBind(RabbitMqConfig.RETRY_QUEUE_TTL,
                            RabbitMqConfig.RETRY_EXCHANGE,
                            RabbitMqConfig.RETRY_ROUTING_KEY_TTL);
                    return null;
                });
                log.info(StructuredLog.event("rabbitmq.resources.declared"));
            } catch (Exception e) {
                log.error(StructuredLog.event("rabbitmq.resources.declare_failed",
                        "errorType", e.getClass().getSimpleName()), e);
            }
        };
    }
}

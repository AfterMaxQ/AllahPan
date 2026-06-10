package com.allahpan.common.config;

import java.time.Duration;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.cache.RedisCacheConfiguration;
import org.springframework.data.redis.cache.RedisCacheManager;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.serializer.Jackson2JsonRedisSerializer;
import org.springframework.data.redis.serializer.RedisSerializationContext;
import org.springframework.data.redis.serializer.RedisSerializer;
import org.springframework.data.redis.serializer.StringRedisSerializer;

import com.fasterxml.jackson.annotation.JsonAutoDetect;
import com.fasterxml.jackson.annotation.PropertyAccessor;
import com.fasterxml.jackson.databind.ObjectMapper;

@Configuration
// Redis 基础配置：自定义序列化器、RedisTemplate、CacheManager
public class BaseRedisConfig {

    @Bean
    // 自定义 Redis 序列化器：使用 Jackson 以 JSON 形式存值，支持多态类型
    public RedisSerializer<Object> redisSerializer() {
        ObjectMapper objectMapper = new ObjectMapper();
        // 设置：所有字段（私有/公有）都能序列化
        objectMapper.setVisibility(PropertyAccessor.ALL, JsonAutoDetect.Visibility.ANY);
        // 存储类型信息，防止取出来的时候不知道转成什么对象
        objectMapper.activateDefaultTyping(
            com.fasterxml.jackson.databind.jsontype.impl.LaissezFaireSubTypeValidator.instance,
            ObjectMapper.DefaultTyping.NON_FINAL
        );
        // 创建 JSON 序列化器：对象 ↔ JSON 互相转换
        return new Jackson2JsonRedisSerializer<>(objectMapper, Object.class);
    }

    @Bean
    // 自定义 RedisTemplate：key 用 String，value 用 JSON 序列化
    public RedisTemplate<String, Object> redisTemplate(
            RedisConnectionFactory connectionFactory,
            RedisSerializer<Object> redisSerializer) {
        RedisTemplate<String, Object> redisTemplate = new RedisTemplate<>();
        // 1. 设置 Redis 服务器连接
        redisTemplate.setConnectionFactory(connectionFactory);
        // 2. key / hashKey 用字符串序列化
        redisTemplate.setKeySerializer(new StringRedisSerializer());
        redisTemplate.setValueSerializer(redisSerializer);
        // 3. hashKey / hashValue 用 JSON 序列化
        redisTemplate.setHashKeySerializer(new StringRedisSerializer());
        redisTemplate.setHashValueSerializer(redisSerializer);
        
        redisTemplate.afterPropertiesSet();
        return redisTemplate;
    }

    @Bean
    // 自定义缓存管理器：默认缓存 1 天，key 用 String，value 用 JSON，不缓存 null
    public RedisCacheManager redisCacheManager(
            RedisConnectionFactory connectionFactory,
            RedisSerializer<Object> redisSerializer) {
        RedisCacheConfiguration config = RedisCacheConfiguration.defaultCacheConfig()
                .entryTtl(Duration.ofDays(1))
                .serializeKeysWith(RedisSerializationContext.SerializationPair
                        .fromSerializer(new StringRedisSerializer()))
                .serializeValuesWith(RedisSerializationContext.SerializationPair
                        .fromSerializer(redisSerializer))
                .disableCachingNullValues();
        return RedisCacheManager.builder(connectionFactory)
                .cacheDefaults(config)
                .build();
    }
}
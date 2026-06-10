package com.allahpan.common.service.impl;

import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.TimeUnit;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;

import com.allahpan.common.service.RedisService;

@Service
public class RedisServiceImpl implements RedisService {
    @Autowired
    private RedisTemplate<String, Object> redisTemplate;

    @Override
    // 存数据（永久有效）
    public void set(String key, Object value) {
        redisTemplate.opsForValue().set(key, value);
    }
    @Override
    // 存数据 + 设置过期时间（默认单位：秒）
    public void set(String key, Object value, long time) {
        set(key, value, time, TimeUnit.SECONDS);
    }
    @Override
    // 存数据 + 自定义时间单位（秒/分钟/小时）
    public void set(String key, Object value, long time, TimeUnit timeUnit) {
        redisTemplate.opsForValue().set(key, value, time, timeUnit);
    }
    @Override
    // 根据 key 取数据
    public Object get(String key) {
        return redisTemplate.opsForValue().get(key);
    }
    @Override
    // 删除单个 key
    public Boolean del(String key) {
        return redisTemplate.delete(key);
    }
    @Override
    // 批量删除多个 key
    public Long del(List<String> keys) {
        return redisTemplate.delete(keys);
    }
    @Override
    // 给已存在的 key 设置过期时间
    public Boolean expire(String key, long time) {
        return redisTemplate.expire(key, time, TimeUnit.SECONDS);
    }
    @Override
    // 获取 key 的剩余过期时间
    public Long getExpire(String key) {
        return redisTemplate.getExpire(key, TimeUnit.SECONDS);
    }
    @Override
    // 判断 key 是否存在
    public Boolean hasKey(String key) {
        return redisTemplate.hasKey(key);
    }
    @Override
    // 数字自增
    public Long incr(String key, long delta) {
        return redisTemplate.opsForValue().increment(key, delta);
    }
    @Override
    // 数字自减
    public Long decr(String key, long delta) {
        return redisTemplate.opsForValue().decrement(key, delta);
    }
    @Override
    // 存哈希数据（key=大key，hashKey=字段名，value=字段值）
    public void hSet(String key, String hashKey, Object value) {
        redisTemplate.opsForHash().put(key, hashKey, value);
    }
    @Override
    // 存哈希数据 + 过期时间
    public void hSet(String key, String hashKey, Object value, long time) {
        redisTemplate.opsForHash().put(key, hashKey, value);
        expire(key, time);
    }
    @Override
    // 取哈希的单个字段
    public Object hGet(String key, String hashKey) {
        return redisTemplate.opsForHash().get(key, hashKey);
    }
    @Override
    // 取整个哈希对象（所有字段+值）
    public Map<Object, Object> hGetAll(String key) {
        return redisTemplate.opsForHash().entries(key);
    }
    @Override
    // 删除哈希里的指定字段
    public void hDel(String key, Object... hashKeys) {
        redisTemplate.opsForHash().delete(key, hashKeys);
    }
    @Override
    // 判断哈希里是否有这个字段
    public Boolean hHasKey(String key, String hashKey) {
        return redisTemplate.opsForHash().hasKey(key, hashKey);
    }
    @Override
    // 哈希字段数字自增（比如商品销量+1）
    public Long hIncr(String key, String hashKey, Long delta) {
        return redisTemplate.opsForHash().increment(key, hashKey, delta);
    }
    @Override
    // 添加数据（自动去重，重复数据存不进去）
    public Long sAdd(String key, Object... values) {
        return redisTemplate.opsForSet().add(key, values);
    }
    @Override
    // 添加数据 + 过期时间
    public Long sAdd(String key, long time, Object... values) {
        Long count = redisTemplate.opsForSet().add(key, values);
        expire(key, time);
        return count;
    }
    @Override
    // 获取集合里所有数据
    public Set<Object> sMembers(String key) {
        return redisTemplate.opsForSet().members(key);
    }
    @Override
    // 判断数据是否在集合里
    public Boolean sIsMember(String key, Object value) {
        return redisTemplate.opsForSet().isMember(key, value);
    }
    @Override
    // 删除集合里指定数据
    public Long sRemove(String key, Object... values) {
        return redisTemplate.opsForSet().remove(key, values);
    }
    @Override
    // 往列表左边添加数据（栈模式，后进先出）
    public Long lPush(String key, Object value) {
        return redisTemplate.opsForList().rightPush(key, value);
    }
    @Override
    // 获取列表指定区间的数据（比如第0-10条）
    public List<Object> lRange(String key, long start, long end) {
        return redisTemplate.opsForList().range(key, start, end);
    }
    @Override
    // 删除列表里指定数据
    public Long lRemove(String key, long count, Object value) {
        return redisTemplate.opsForList().remove(key, count, value);
    }
}
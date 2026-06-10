package com.allahpan.common.service;

import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.TimeUnit;

public interface RedisService {
    // 存数据（永久有效）
    void set(String key, Object value);
    // 存数据 + 设置过期时间（默认单位：秒）
    void set(String key, Object value, long time);
    // 存数据 + 自定义时间单位（秒/分钟/小时）
    void set(String key, Object value, long time, TimeUnit timeUnit);
    // 根据 key 取数据
    Object get(String key);
    // 删除单个 key
    Boolean del(String key);
    // 批量删除多个 key
    Long del(List<String> keys);
    // 给已存在的 key 设置过期时间
    Boolean expire(String key, long time);
    // 获取 key 的剩余过期时间
    Long getExpire(String key);
    // 判断 key 是否存在
    Boolean hasKey(String key);
    // 数字自增
    Long incr(String key, long delta);
    // 数字自减
    Long decr(String key, long delta);


    // 存哈希数据（key=大key，hashKey=字段名，value=字段值）
    void hSet(String key, String hashKey, Object value);
    // 存哈希数据 + 过期时间
    void hSet(String key, String hashKey, Object value, long time);
    // 取哈希的单个字段
    Object hGet(String key, String hashKey);
    // 取整个哈希对象（所有字段+值）
    Map<Object, Object> hGetAll(String key);
    // 删除哈希里的指定字段
    void hDel(String key, Object... hashKeys);
    // 判断哈希里是否有这个字段
    Boolean hHasKey(String key, String hashKey);
    // 哈希字段数字自增（比如商品销量+1）
    Long hIncr(String key, String hashKey, Long delta);

    // 添加数据（自动去重，重复数据存不进去）
    Long sAdd(String key, Object... values);
    // 添加数据 + 过期时间
    Long sAdd(String key, long time, Object... values);
    // 获取集合里所有数据
    Set<Object> sMembers(String key);
    // 判断数据是否在集合里
    Boolean sIsMember(String key, Object value);
    // 删除集合里指定数据
    Long sRemove(String key, Object... values);

    // 往列表左边添加数据（栈模式，后进先出）
    Long lPush(String key, Object value);
    // 获取列表指定区间的数据（比如第0-10条）
    List<Object> lRange(String key, long start, long end);
    // 删除列表里指定数据
    Long lRemove(String key, long count, Object value); 
    
}

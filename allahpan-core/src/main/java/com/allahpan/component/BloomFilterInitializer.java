package com.allahpan.component;

import com.allahpan.common.service.BloomFilterService;
import com.allahpan.mbg.mapper.UserMapper;
import com.allahpan.mbg.model.UserExample;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;

/**
 * 应用启动时，将所有已注册用户的 email 加载到布隆过滤器
 * 防止恶意请求不存在的 email 穿透到 MySQL
 */
@Component
public class BloomFilterInitializer implements ApplicationRunner {

    private static final Logger LOGGER = LoggerFactory.getLogger(BloomFilterInitializer.class);

    @Autowired
    private BloomFilterService bloomFilterService;
    @Autowired
    private UserMapper userMapper;

    @Override
    public void run(ApplicationArguments args) {
        try {
            bloomFilterService.reset();
            var users = userMapper.selectByExample(new UserExample());
            for (var user : users) {
                bloomFilterService.add(user.getEmail());
            }
            LOGGER.info("BloomFilter initialized with {} user emails", users.size());
        } catch (Exception e) {
            // Redis 不可用时仅记录，不阻断启动
            LOGGER.error("BloomFilter initialization failed: {}", e.getMessage());
        }
    }
}

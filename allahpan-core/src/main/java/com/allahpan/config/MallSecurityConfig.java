package com.allahpan.config;

import com.allahpan.bo.AdminUserDetails;
import com.allahpan.mbg.model.User;
import com.allahpan.service.UserCacheService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;

import java.util.Collections;

@Configuration
public class MallSecurityConfig {

    @Autowired
    private UserCacheService userCacheService;

    @Bean
    public UserDetailsService userDetailsService(){
        return useremail -> {
            // userCacheService.getUser 已实现读穿透（Redis miss → MySQL 回源 → 回填缓存）
            User user = userCacheService.getUser(useremail);
            if (user == null) {
                throw new UsernameNotFoundException("用户不存在：" + useremail);
            }
            return new AdminUserDetails(user, Collections.emptyList());
        };
    }
}

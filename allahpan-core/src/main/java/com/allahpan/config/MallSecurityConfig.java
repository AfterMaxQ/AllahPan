package com.allahpan.config;

import com.allahpan.bo.AdminUserDetails;
import com.allahpan.mbg.mapper.UserMapper;
import com.allahpan.mbg.model.User;
import com.allahpan.mbg.model.UserExample;
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
    private UserMapper userMapper;
    @Autowired
    private UserCacheService userCacheService;

    @Bean
    public UserDetailsService userDetailsService(){
        return useremail -> {
            User user = userCacheService.getUser(useremail);
            if (user == null){
                UserExample example = new UserExample();
                example.createCriteria().andEmailEqualTo(useremail).andStatusEqualTo((byte) 1);
                var list = userMapper.selectByExample(example);
                if (!list.isEmpty()) {
                    user = list.get(0);
                    userCacheService.setUser(user);
                }
            }
            if (user == null) {
                throw new UsernameNotFoundException("用户不存在：" + useremail);
            }
            return new AdminUserDetails(user, Collections.emptyList());
        };
    }
}

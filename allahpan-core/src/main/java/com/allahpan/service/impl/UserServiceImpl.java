package com.allahpan.service.impl;

import java.util.Date;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import com.allahpan.bo.AdminUserDetails;
import com.allahpan.common.exception.Asserts;
import com.allahpan.common.service.BloomFilterService;
import com.allahpan.mbg.mapper.UserMapper;
import com.allahpan.mbg.model.User;
import com.allahpan.mbg.model.UserExample;
import com.allahpan.service.UserCacheService;
import com.allahpan.service.UserService;

@Service
public class UserServiceImpl implements UserService {
    @Autowired
    private UserMapper userMapper;
    @Autowired
    private UserCacheService userCacheService;
    @Autowired
    private BloomFilterService bloomFilterService;
    @Autowired
    private PasswordEncoder passwordEncoder;

    @Value("${allahpan.register.enabled:true}")
    private boolean registerEnabled;

    @Override
    public User loginByCode(String email) {
        UserExample example = new UserExample();
        example.createCriteria().andEmailEqualTo(email);
        var list = userMapper.selectByExample(example);
        User user;
        if (list.isEmpty()) {
            // 自动注册
            Asserts.isTrue(registerEnabled, "注册功能已暂停，仅限已注册用户登录");
            user = new User();
            user.setEmail(email);
            user.setNickname(email.substring(0, email.indexOf('@')));
            user.setStatus((byte) 1);
            user.setFirstLogin((byte) 1);
            user.setCreateTime(new Date());
            userMapper.insert(user);
            bloomFilterService.add(email);
        } else {
            user = list.get(0);
            Asserts.isTrue(user.getStatus() == 1, "账号已被禁用");
            user.setLastLoginTime(new Date());
            userMapper.updateByPrimaryKeySelective(user);
        }
        userCacheService.delUserByEmail(user.getEmail());
        return user;
    }

    @Override
    public User loginByPassword(String email, String password) {
        UserExample example = new UserExample();
        example.createCriteria().andEmailEqualTo(email);
        var list = userMapper.selectByExample(example);
        Asserts.isTrue(!list.isEmpty(), "邮箱未注册");
        User user = list.get(0);
        Asserts.isTrue(user.getStatus() == 1, "账号已被禁用");
        Asserts.isTrue(passwordEncoder.matches(password, user.getPassword()), "密码错误");
        user.setLastLoginTime(new Date());
        userMapper.updateByPrimaryKeySelective(user);
        userCacheService.delUserByEmail(user.getEmail());
        return user;
    }

    @Override
    public User setPassword(Long userId, String newPassword) {
        User user = userMapper.selectByPrimaryKey(userId);
        Asserts.isTrue(user != null, "用户不存在");
        user.setPassword(passwordEncoder.encode(newPassword));
        user.setFirstLogin((byte) 0);
        userMapper.updateByPrimaryKeySelective(user);
        userCacheService.delUserByEmail(user.getEmail());
        return user;
    }

    @Override
    public User getCurrentUser() {
        AdminUserDetails details = (AdminUserDetails) SecurityContextHolder
                .getContext().getAuthentication().getPrincipal();
        return details.getUser();
    }
}

package com.allahpan.service;

import com.allahpan.mbg.model.User;

public interface UserService {
    User loginByCode(String email);
    User loginByPassword(String email, String password);
    User setPassword(Long userId, String newPassword);
    User getCurrentUser();
}

package com.allahpan.service;

public interface AuthCodeService {
    void sendCode(String email);
    void verifyCode(String email, String code);
}

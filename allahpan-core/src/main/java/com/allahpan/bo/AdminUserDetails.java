package com.allahpan.bo;

import com.allahpan.mbg.model.User;
import com.allahpan.common.log.UserIdentity;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.userdetails.UserDetails;

import java.util.Collection;
import java.util.List;

/**
 * Spring Security UserDetails 实现类
 * 将 User 实体适配为 Spring Security 的安全主体
 */
public class AdminUserDetails implements UserDetails, UserIdentity {
    /** 关联的用户实体 */
    private final User user;
    /** 权限列表（当前无 RBAC，返回空列表） */
    private final List<? extends GrantedAuthority> authorities;

    public AdminUserDetails(User user, List<? extends GrantedAuthority> authorities) {
        this.user = user;
        this.authorities = authorities;
    }

    /** 获取原始用户实体 */
    public User getUser() { return user; }
    /** 获取用户 ID */
    public Long getUserId() { return user.getId(); }

    @Override
    public Collection<? extends GrantedAuthority> getAuthorities() { return authorities; }
    @Override
    public String getPassword() { return user.getPassword(); }
    @Override
    public String getUsername() { return user.getEmail(); }
    @Override
    public boolean isAccountNonExpired() { return true; }
    @Override
    public boolean isAccountNonLocked() { return true; }
    @Override
    public boolean isCredentialsNonExpired() { return true; }
    @Override
    public boolean isEnabled() { return user.getStatus() == 1; }
}

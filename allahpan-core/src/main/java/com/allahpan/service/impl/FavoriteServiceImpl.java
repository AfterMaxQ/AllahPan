package com.allahpan.service.impl;

import com.allahpan.bo.AdminUserDetails;
import com.allahpan.common.exception.Asserts;
import com.allahpan.mbg.mapper.FileFavoriteMapper;
import com.allahpan.mbg.mapper.FileMapper;
import com.allahpan.mbg.model.File;
import com.allahpan.mbg.model.FileFavorite;
import com.allahpan.mbg.model.FileFavoriteExample;
import com.allahpan.service.FavoriteService;
import com.github.pagehelper.PageHelper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Service;

import java.util.Date;
import java.util.List;

@Service
public class FavoriteServiceImpl implements FavoriteService {
    @Autowired
    private FileFavoriteMapper favoriteMapper;
    @Autowired
    private FileMapper fileMapper;

    @Override
    public void addFavorite(Long fileId) {
        Long userId = getCurrentUserId();
        // 幂等：已收藏直接返回
        FileFavoriteExample example = new FileFavoriteExample();
        example.createCriteria().andUserIdEqualTo(userId).andFileIdEqualTo(fileId);
        if (!favoriteMapper.selectByExample(example).isEmpty()) return;

        FileFavorite fav = new FileFavorite();
        fav.setUserId(userId);
        fav.setFileId(fileId);
        fav.setCreateTime(new Date());
        favoriteMapper.insert(fav);
    }

    @Override
    public void removeFavorite(Long fileId) {
        Long userId = getCurrentUserId();
        FileFavoriteExample example = new FileFavoriteExample();
        example.createCriteria().andUserIdEqualTo(userId).andFileIdEqualTo(fileId);
        favoriteMapper.deleteByExample(example);
    }

    @Override
    public boolean isFavorited(Long fileId) {
        Long userId = getCurrentUserId();
        FileFavoriteExample example = new FileFavoriteExample();
        example.createCriteria().andUserIdEqualTo(userId).andFileIdEqualTo(fileId);
        return !favoriteMapper.selectByExample(example).isEmpty();
    }

    @Override
    public List<File> listFavorites(int pageNum, int pageSize) {
        Long userId = getCurrentUserId();
        PageHelper.startPage(pageNum, pageSize);
        return fileMapper.selectFavoritesByUserId(userId);
    }

    private Long getCurrentUserId() {
        var auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth != null && auth.getPrincipal() instanceof AdminUserDetails details) {
            return details.getUserId();
        }
        throw new RuntimeException("未登录");
    }
}

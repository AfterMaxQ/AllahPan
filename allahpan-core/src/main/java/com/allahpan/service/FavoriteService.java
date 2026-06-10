package com.allahpan.service;

import com.allahpan.mbg.model.File;
import java.util.List;

public interface FavoriteService {
    void addFavorite(Long fileId);
    void removeFavorite(Long fileId);
    boolean isFavorited(Long fileId);
    List<File> listFavorites(int pageNum, int pageSize);
}
package com.allahpan.controller;

import com.allahpan.common.api.CommonResult;
import com.allahpan.service.FavoriteService;
import io.swagger.v3.oas.annotations.Operation;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/favorite")
public class FavoriteController {

    @Autowired
    private FavoriteService favoriteService;

    @Operation(summary = "收藏文件")
    @PostMapping("/{fileId}")
    public CommonResult<Void> addFavorite(@PathVariable Long fileId) {
        favoriteService.addFavorite(fileId);
        return CommonResult.success(null);
    }

    @Operation(summary = "取消收藏")
    @DeleteMapping("/{fileId}")
    public CommonResult<Void> removeFavorite(@PathVariable Long fileId) {
        favoriteService.removeFavorite(fileId);
        return CommonResult.success(null);
    }

    @Operation(summary = "是否已收藏")
    @GetMapping("/check/{fileId}")
    public CommonResult<Boolean> isFavorited(@PathVariable Long fileId) {
        return CommonResult.success(favoriteService.isFavorited(fileId));
    }

    @Operation(summary = "收藏列表")
    @GetMapping("/list")
    public CommonResult<?> listFavorites(
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "20") int pageSize) {
        return CommonResult.success(favoriteService.listFavorites(pageNum, pageSize));
    }
}
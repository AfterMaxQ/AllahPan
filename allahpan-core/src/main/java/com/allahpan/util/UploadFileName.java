package com.allahpan.util;

/**
 * Normalizes the untrusted filename supplied by an upload client.
 *
 * <p>Files selected through a browser directory input can arrive with their
 * relative path in {@code MultipartFile#getOriginalFilename()}. The directory
 * hierarchy is already represented by {@code parentId}; persisting that path
 * again as {@code fileName} corrupts the display name and virtual file path.</p>
 */
public final class UploadFileName {
    private UploadFileName() {
    }

    public static String baseName(String clientFileName) {
        if (clientFileName == null) {
            return null;
        }
        String normalized = clientFileName.replace('\\', '/');
        int lastSeparator = normalized.lastIndexOf('/');
        return lastSeparator >= 0 ? normalized.substring(lastSeparator + 1) : normalized;
    }
}

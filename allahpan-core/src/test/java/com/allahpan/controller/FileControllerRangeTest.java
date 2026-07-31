package com.allahpan.controller;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;

class FileControllerRangeTest {

    @Test
    void returnsNullWhenRangeIsAbsent() {
        assertNull(FileController.parseRange(null, 100));
        assertNull(FileController.parseRange("  ", 100));
    }

    @Test
    void parsesOpenAndClosedRanges() {
        assertRange("bytes=10-19", 100, 10, 19);
        assertRange("bytes=90-", 100, 90, 99);
    }

    @Test
    void clampsRangeEndToObjectSize() {
        assertRange("bytes=90-999", 100, 90, 99);
    }

    @Test
    void parsesSuffixRange() {
        assertRange("bytes=-25", 100, 75, 99);
        assertRange("bytes=-200", 100, 0, 99);
    }

    @Test
    void rejectsUnsupportedOrUnsatisfiableRanges() {
        assertThrows(IllegalArgumentException.class,
                () -> FileController.parseRange("items=0-1", 100));
        assertThrows(IllegalArgumentException.class,
                () -> FileController.parseRange("bytes=100-", 100));
        assertThrows(IllegalArgumentException.class,
                () -> FileController.parseRange("bytes=20-10", 100));
        assertThrows(IllegalArgumentException.class,
                () -> FileController.parseRange("bytes=0-1,3-4", 100));
        assertThrows(IllegalArgumentException.class,
                () -> FileController.parseRange("bytes=0-1", 0));
    }

    private void assertRange(String header, long totalSize, long start, long end) {
        FileController.ByteRange range = FileController.parseRange(header, totalSize);
        assertEquals(start, range.start());
        assertEquals(end, range.end());
        assertEquals(end - start + 1, range.length());
    }
}

package com.allahpan.common.log;

/**
 * Formats one-line, key/value log messages without allowing user input to
 * create additional lines or accidentally corrupt the log record.
 */
public final class StructuredLog {
    private StructuredLog() {}

    public static String event(String name, Object... fields) {
        StringBuilder value = new StringBuilder("event=").append(clean(name));
        for (int i = 0; i + 1 < fields.length; i += 2) {
            Object field = fields[i];
            if (field == null) continue;
            Object fieldValue = fields[i + 1];
            if (fieldValue == null) continue;
            value.append(' ').append(clean(String.valueOf(field))).append('=')
                    .append(clean(String.valueOf(fieldValue)));
        }
        return value.toString();
    }

    private static String clean(String value) {
        return value.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ').replace(' ', '_')
                .replace('"', '\'');
    }
}

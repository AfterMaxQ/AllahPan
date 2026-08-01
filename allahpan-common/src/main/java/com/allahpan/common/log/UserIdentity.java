package com.allahpan.common.log;

/** Minimal identity contract used by the security layer without coupling it to Core. */
public interface UserIdentity {
    Long getUserId();
}

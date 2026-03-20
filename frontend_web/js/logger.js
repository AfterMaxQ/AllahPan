/**
 * AllahPan Web 前端日志模块
 * 提供分级日志、可选 localStorage 缓冲，便于排查问题与改进稳定性
 */
(function (global) {
  'use strict';

  var PREFIX = '[AllahPan]';
  var LEVELS = { debug: 0, info: 1, warn: 2, error: 3 };
  var MAX_BUFFER = 200;
  var STORAGE_KEY = 'allahpan_web_log';

  function now() {
    return new Date().toISOString();
  }

  function bufferLine(level, args) {
    try {
      var line = now() + ' ' + level.toUpperCase() + ' ' + PREFIX + ' ' + Array.prototype.map.call(args, function (a) {
        if (typeof a === 'object') try { return JSON.stringify(a); } catch (e) { return String(a); }
        return String(a);
      }).join(' ');
      var buf = [];
      try {
        var raw = global.localStorage.getItem(STORAGE_KEY);
        if (raw) buf = JSON.parse(raw);
      } catch (e) {}
      buf.push(line);
      if (buf.length > MAX_BUFFER) buf = buf.slice(-MAX_BUFFER);
      global.localStorage.setItem(STORAGE_KEY, JSON.stringify(buf));
    } catch (e) {}
  }

  var currentLevel = (function () {
    try {
      var s = global.localStorage.getItem('allahpan_log_level');
      if (s && LEVELS[s] !== undefined) return s;
    } catch (e) {}
    return 'info';
  })();

  function log(level, args) {
    if (LEVELS[level] < LEVELS[currentLevel]) return;
    var arr = [PREFIX].concat(Array.prototype.slice.call(args));
    if (level === 'error' || level === 'warn') bufferLine(level, args);
    if (global.console && global.console[level]) {
      global.console[level].apply(global.console, arr);
    } else if (global.console && global.console.log) {
      global.console.log.apply(global.console, arr);
    }
  }

  var Logger = {
    setLevel: function (level) {
      if (LEVELS[level] !== undefined) {
        currentLevel = level;
        try { global.localStorage.setItem('allahpan_log_level', level); } catch (e) {}
      }
    },
    getLevel: function () { return currentLevel; },
    debug: function () { log('debug', arguments); },
    info: function () { log('info', arguments); },
    warn: function () { log('warn', arguments); },
    error: function () { log('error', arguments); },
    /** 获取最近日志（用于调试或导出） */
    getBuffer: function () {
      try {
        var raw = global.localStorage.getItem(STORAGE_KEY);
        return raw ? JSON.parse(raw) : [];
      } catch (e) { return []; }
    },
    clearBuffer: function () {
      try { global.localStorage.removeItem(STORAGE_KEY); } catch (e) {}
    },
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = Logger;
  } else {
    global.AllahPanLogger = Logger;
  }
})(typeof window !== 'undefined' ? window : this);

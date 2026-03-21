/**
 * AllahPan 网页端 API 封装
 * 与后端 backend/app/api/v1 路由及请求/响应模型保持一致
 * 后端前缀: /api/v1
 */

(function (global) {
  'use strict';

  /**
   * API 根地址（无尾斜杠），可通过 window.ALLAH_PAN_API_BASE 或 meta[name=allahpan-api-base] 覆盖。
   * 独立静态服务器（如 run.py :3000）上若仍用页面 origin，会把 /api/v1 打到静态站 → GET 404、POST 501。
   */
  function getBaseUrl() {
    var ex = global.ALLAH_PAN_API_BASE != null ? String(global.ALLAH_PAN_API_BASE).trim() : '';
    if (ex) return ex.replace(/\/+$/, '');

    var loc = global.location;
    if (!loc || loc.protocol === 'file:') {
      return 'http://localhost:8000/api/v1';
    }
    var origin = loc.origin;
    if (!origin || origin === 'null') {
      return 'http://localhost:8000/api/v1';
    }

    var host = loc.hostname || '';
    var port = loc.port || '';
    var isLoopback = host === 'localhost' || host === '127.0.0.1';
    // 常见「只托管静态页」的端口：与 run.py(3000)、Live Server、Vite 等一致，API 默认同机 8000
    var staticDevPorts = { '3000': true, '5173': true, '8080': true, '5500': true };

    if (loc.protocol === 'http:' && port && port !== '8000') {
      if (isLoopback || staticDevPorts[port]) {
        return 'http://' + host + ':8000/api/v1';
      }
    }

    // 与后端同源（Uvicorn 托管 frontend_web 时在 8000）：origin + /api/v1
    return origin.replace(/\/+$/, '') + '/api/v1';
  }

  /**
   * 从后端错误响应中提取可读消息
   * 后端 FastAPI 可能返回 detail 为 string 或 array（校验错误）
   */
  function getErrorMessage(body, fallback) {
    if (!body || typeof body !== 'object') return fallback || '请求失败';
    var d = body.detail;
    if (typeof d === 'string') return d;
    if (Array.isArray(d)) {
      return d.map(function (e) {
        var loc = (e.loc || []).slice(1).join('.');
        return loc ? loc + ': ' + (e.msg || e.message || '') : (e.msg || e.message || '');
      }).filter(Boolean).join('；') || fallback;
    }
    return fallback || '请求失败';
  }

  /** 默认请求超时（毫秒） */
  var DEFAULT_TIMEOUT_MS = 60000;

  /**
   * 统一请求：自动加 Authorization、Content-Type、超时，解析 JSON 错误
   * @param {string} path - 相对 /api/v1 的路径，如 'auth/login'
   * @param {object} options - fetch 选项，可含 method, body, headers, token, timeoutMs
   * @returns {Promise<{ ok: boolean, data?: any, error?: string, status: number }>}
   */
  function request(path, options) {
    options = options || {};
    var base = getBaseUrl().replace(/\/$/, '');
    var url = base + (path.charAt(0) === '/' ? path : '/' + path);
    var method = (options.method || 'GET').toUpperCase();
    var headers = Object.assign({}, options.headers || {});
    var token = options.token !== undefined ? options.token : (global.currentToken || null);
    var timeoutMs = options.timeoutMs != null ? options.timeoutMs : DEFAULT_TIMEOUT_MS;

    if (token) headers['Authorization'] = 'Bearer ' + token;
    if (method !== 'GET' && options.body !== undefined && typeof options.body === 'string' && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }

    var controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
    var timeoutId = null;
    if (controller && timeoutMs > 0) {
      timeoutId = global.setTimeout(function () {
        controller.abort();
      }, timeoutMs);
    }

    var fetchOpts = {
      method: method,
      headers: headers,
      body: options.body,
      credentials: options.credentials || 'omit',
      signal: controller ? controller.signal : undefined,
    };

    return fetch(url, fetchOpts).then(function (res) {
      if (timeoutId) global.clearTimeout(timeoutId);
      return res.text().then(function (text) {
        var data = null;
        try {
          if (text) data = JSON.parse(text);
        } catch (e) {}
        if (!res.ok) {
          return {
            ok: false,
            status: res.status,
            data: data,
            error: getErrorMessage(data, res.statusText || '请求失败'),
          };
        }
        return { ok: true, status: res.status, data: data || {} };
      });
    }).catch(function (err) {
      if (timeoutId) global.clearTimeout(timeoutId);
      var msg = err.name === 'AbortError' ? '请求超时' : (err.message || '网络错误');
      return { ok: false, status: 0, error: msg };
    });
  }

  // ==================== 认证 API（与 auth.py 一致）====================

  /**
   * POST /auth/register
   * 请求: { username, password, email }
   * 响应: UserResponse { id, username, email }
   */
  function authRegister(username, password, email) {
    return request('auth/register', {
      method: 'POST',
      body: JSON.stringify({ username: username, password: password, email: email }),
    });
  }

  /**
   * POST /auth/login
   * 请求: { username, password }
   * 响应: TokenResponse { access_token, token_type, user: AuthUser }
   */
  function authLogin(username, password) {
    return request('auth/login', {
      method: 'POST',
      body: JSON.stringify({ username: username, password: password }),
    });
  }

  /**
   * GET /auth/me
   * 响应: UserResponse { id, username, email }
   */
  function authMe(token) {
    return request('auth/me', { method: 'GET', token: token });
  }

  // ==================== 文件 API（与 files.py 一致）====================

  /**
   * GET /files/list?path=
   * 响应: FileListResponse { directories: [{ name, path }], files: FileMetadataResponse[], total }
   */
  function filesList(path, token) {
    var q = (path == null || path === '') ? '' : '?path=' + encodeURIComponent(path);
    return request('files/list' + q, { method: 'GET', token: token });
  }

  /**
   * GET /files/{file_id}
   * 响应: FileMetadataResponse
   */
  function filesGet(fileId, token) {
    return request('files/' + encodeURIComponent(fileId), { method: 'GET', token: token });
  }

  /**
   * GET /files/{file_id}/download
   * 返回 Promise<{ ok, blob?, filename?, error? }>，用于前端触发下载
   */
  function filesDownload(fileId, token) {
    var base = getBaseUrl().replace(/\/$/, '');
    var url = base + '/files/' + encodeURIComponent(fileId) + '/download';
    var t = token !== undefined ? token : (global.currentToken || '');
    return fetch(url, {
      method: 'GET',
      headers: t ? { 'Authorization': 'Bearer ' + t } : {},
    }).then(function (res) {
      if (!res.ok) {
        return res.text().then(function (text) {
          var data = null;
          try { if (text) data = JSON.parse(text); } catch (e) {}
          return { ok: false, error: getErrorMessage(data, res.statusText) };
        });
      }
      return res.blob().then(function (blob) {
        var name = '';
        var cd = res.headers.get('Content-Disposition');
        if (cd && /filename[*]?=(?:UTF-8'')?([^;\n]+)/i.test(cd)) {
          name = RegExp.$1.trim().replace(/^["']|["']$/g, '');
          // 服务端可能对中文等做 URL 编码（%xx），需解码后保存为正确文件名
          try {
            if (name && name.indexOf('%') !== -1) {
              name = decodeURIComponent(name);
            }
          } catch (e) {
            /* 解码失败则保留原值 */
          }
        }
        if (!name) name = fileId;
        return { ok: true, blob: blob, filename: name };
      });
    }).catch(function (err) {
      return { ok: false, error: err.message || '网络错误' };
    });
  }

  /**
   * GET /files/{file_id}/preview
   * 返回 Promise<{ ok, blob?, error? }>，用于预览（图片/音视频等）
   */
  function filesPreview(fileId, token) {
    var base = getBaseUrl().replace(/\/$/, '');
    var url = base + '/files/' + encodeURIComponent(fileId) + '/preview';
    var t = token !== undefined ? token : (global.currentToken || '');
    var controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
    var timeoutMs = 60000;
    var timeoutId = controller ? global.setTimeout(function () { controller.abort(); }, timeoutMs) : null;
    return fetch(url, {
      method: 'GET',
      headers: t ? { 'Authorization': 'Bearer ' + t } : {},
      signal: controller ? controller.signal : undefined,
    }).then(function (res) {
      if (timeoutId) global.clearTimeout(timeoutId);
      if (!res.ok) {
        return res.text().then(function (text) {
          var data = null;
          try { if (text) data = JSON.parse(text); } catch (e) {}
          return { ok: false, error: getErrorMessage(data, res.statusText) };
        });
      }
      return res.blob().then(function (blob) {
        return { ok: true, blob: blob };
      });
    }).catch(function (err) {
      if (timeoutId) global.clearTimeout(timeoutId);
      return { ok: false, error: err.name === 'AbortError' ? '预览请求超时' : (err.message || '网络错误') };
    });
  }

  /**
   * PATCH /files/{file_id}/rename
   * body: { filename: string }
   * 响应: FileMetadataResponse
   */
  function filesRename(fileId, filename, token) {
    return request('files/' + encodeURIComponent(fileId) + '/rename', {
      method: 'PATCH',
      body: JSON.stringify({ filename: filename }),
      token: token,
    });
  }

  /**
   * DELETE /files/{file_id}
   * 响应: { success: boolean, file_id: string, message: string }
   */
  function filesDelete(fileId, token) {
    return request('files/' + encodeURIComponent(fileId), { method: 'DELETE', token: token });
  }

  /**
   * POST /files/upload
   * body: FormData，字段名 file
   * 响应: 201 FileMetadataResponse
   * onProgress(loaded, total) 可选
   */
  function filesUpload(file, token, onProgress) {
    var base = getBaseUrl().replace(/\/$/, '');
    var url = base + '/files/upload';
    return new Promise(function (resolve, reject) {
      var xhr = new XMLHttpRequest();
      var formData = new FormData();
      formData.append('file', file);

      xhr.upload.addEventListener('progress', function (e) {
        if (e.lengthComputable && typeof onProgress === 'function') {
          onProgress(e.loaded, e.total);
        }
      });

      xhr.addEventListener('load', function () {
        var text = xhr.responseText || '';
        var data = null;
        try { if (text) data = JSON.parse(text); } catch (e) {}
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve({ ok: true, status: xhr.status, data: data });
        } else {
          resolve({ ok: false, status: xhr.status, data: data, error: getErrorMessage(data, '上传失败') });
        }
      });

      xhr.addEventListener('error', function () {
        resolve({ ok: false, status: 0, error: '网络错误' });
      });

      xhr.open('POST', url);
      xhr.setRequestHeader('Authorization', 'Bearer ' + (token || global.currentToken || ''));
      xhr.send(formData);
    });
  }

  /** 分片大小，与后端 CHUNK_SIZE 一致（5MB） */
  var RESUMABLE_CHUNK_SIZE = 5 * 1024 * 1024;

  /**
   * 断点续传上传：POST /files/upload/init -> POST /files/upload/chunk（多次）-> POST /files/upload/complete/{upload_id}
   * 与后端 files.py 分片接口一致。
   * @param {File} file
   * @param {string} token
   * @param {function(number, number)} onProgress - onProgress(loaded, total)
   * @returns {Promise<{ok: boolean, status: number, data?: object, error?: string}>}
   */
  function filesUploadResumable(file, token, onProgress) {
    var base = getBaseUrl().replace(/\/$/, '');
    var t = token || global.currentToken || '';
    var chunkSize = RESUMABLE_CHUNK_SIZE;
    var totalChunks = Math.ceil(file.size / chunkSize);
    if (totalChunks < 1) totalChunks = 1;

    return request('files/upload/init', {
      method: 'POST',
      token: t,
      body: JSON.stringify({
        filename: file.name,
        file_size: file.size,
        chunk_size: chunkSize,
        content_type: file.type || 'application/octet-stream',
      }),
    }).then(function (initRes) {
      if (!initRes.ok) {
        return { ok: false, status: initRes.status || 0, error: initRes.error || '初始化分片上传失败' };
      }
      var uploadId = initRes.data && initRes.data.upload_id;
      var serverChunkSize = (initRes.data && initRes.data.chunk_size) || chunkSize;
      var serverTotalChunks = (initRes.data && initRes.data.total_chunks) || totalChunks;
      if (!uploadId) {
        return { ok: false, status: 0, error: '初始化响应缺少 upload_id' };
      }

      var loaded = 0;
      var total = file.size;
      function reportProgress() {
        if (typeof onProgress === 'function') onProgress(loaded, total);
      }

            var chain = Promise.resolve();
      for (var i = 0; i < serverTotalChunks; i++) {
        (function (chunkIndex) {
          chain = chain.then(function () {
            var start = chunkIndex * serverChunkSize;
            var end = Math.min(start + serverChunkSize, file.size);
            var blob = file.slice(start, end);
            var form = new FormData();
            form.append('file', blob, 'chunk');
            var chunkUrl = base + '/files/upload/chunk?upload_id=' + encodeURIComponent(uploadId) + '&chunk_index=' + chunkIndex;

            function doChunkUpload(attempt) {
              attempt = attempt != null ? attempt : 0;
              var maxAttempts = 3;
              return new Promise(function (resolve) {
                var xhr = new XMLHttpRequest();
                xhr.open('POST', chunkUrl);
                xhr.setRequestHeader('Authorization', 'Bearer ' + t);
                xhr.onload = function () {
                  var text = xhr.responseText || '';
                  var data = null;
                  try { if (text) data = JSON.parse(text); } catch (e) {}
                  if (xhr.status >= 200 && xhr.status < 300) {
                    loaded = (chunkIndex + 1) * serverChunkSize;
                    if (loaded > total) loaded = total;
                    reportProgress();
                    resolve({ ok: true, data: data });
                  } else {
                    resolve({ ok: false, _error: getErrorMessage(data, '分片上传失败'), _status: xhr.status });
                  }
                };
                xhr.onerror = function () {
                  resolve({ ok: false, _error: '网络错误', _status: 0 });
                };
                xhr.send(form);
              }).then(function (out) {
                if (out.ok) return out.data;
                if (attempt + 1 < maxAttempts) {
                  return new Promise(function (r) { global.setTimeout(r, 2000); }).then(function () {
                    return doChunkUpload(attempt + 1);
                  });
                }
                return Promise.reject(new Error(out._error || '分片上传失败'));
              });
            }
            return doChunkUpload(0);
          });
        })(i);
      }

      return chain.then(function () {
        return request('files/upload/complete/' + encodeURIComponent(uploadId), {
          method: 'POST',
          token: t,
        });
      }).then(function (completeRes) {
        if (!completeRes.ok) {
          return { ok: false, status: completeRes.status || 0, error: completeRes.error || '完成上传失败' };
        }
        var success = completeRes.data && completeRes.data.success;
        if (!success && completeRes.data && completeRes.data.error) {
          return { ok: false, status: 200, error: completeRes.data.error };
        }
        if (success) {
          return { ok: true, status: 201, data: completeRes.data.file_metadata || completeRes.data };
        }
        return { ok: false, status: 200, error: '完成上传失败' };
      });
    });
  }

  // ==================== AI API（与 ai.py 一致）====================

  /**
   * POST /ai/search
   * 请求: SearchRequest { query, limit?, search_mode? } search_mode: filename | vector | mixed
   * 响应: SearchResponse { results: SearchResult[], total, mode }
   */
  function aiSearch(query, limit, token, searchMode) {
    var body = { query: query, limit: limit == null ? 20 : limit };
    if (searchMode && searchMode !== 'mixed') body.search_mode = searchMode;
    return request('ai/search', {
      method: 'POST',
      body: JSON.stringify(body),
      token: token,
      timeoutMs: 90000,
    });
  }

  /**
   * POST /ai/parse/{file_id}
   * 可选 body: { force: boolean }
   * 响应: ParseResponse { file_id, success, message, extracted_text? }
   */
  function aiParse(fileId, force, token) {
    var path = 'ai/parse/' + encodeURIComponent(fileId);
    return request(path, {
      method: 'POST',
      body: JSON.stringify(force === true ? { force: true } : {}),
      token: token,
    });
  }

  /**
   * GET /ai/status
   * 响应: OllamaStatus { available, model, embedding_model, error? }
   */
  function aiStatus() {
    return request('ai/status', { method: 'GET' });
  }

  // ==================== 系统 API（与 system.py 一致）====================

  /**
   * GET /system/summary
   * 响应: SystemStatusSummary { storage, ollama, tunnel, watcher, image_parser }
   */
  function systemSummary(token) {
    return request('system/summary', { method: 'GET', token: token, timeoutMs: 15000 });
  }

  // ==================== 远程访问 Tunnel API（与 tunnel.py 一致）====================

  /**
   * GET /tunnel/status
   * 响应: TunnelStatusResponse { status, is_running, domain, connection_url, token_configured, error, ... }
   */
  function tunnelStatus(token) {
    return request('tunnel/status', { method: 'GET', token: token, timeoutMs: 10000 });
  }

  /**
   * GET /tunnel/connection
   * 响应: TunnelConnectionResponse { domain, url, status, uptime }
   */
  function tunnelConnection(token) {
    return request('tunnel/connection', { method: 'GET', token: token, timeoutMs: 10000 });
  }

  /**
   * POST /tunnel/config
   * 请求: { token: string, domain?: string }
   */
  function tunnelConfig(token, body, requestToken) {
    return request('tunnel/config', {
      method: 'POST',
      token: requestToken !== undefined ? requestToken : token,
      body: JSON.stringify(body),
      timeoutMs: 10000,
    });
  }

  /**
   * DELETE /tunnel/config
   */
  function tunnelClearConfig(token) {
    return request('tunnel/config', { method: 'DELETE', token: token, timeoutMs: 10000 });
  }

  /**
   * POST /tunnel/start
   */
  function tunnelStart(token) {
    return request('tunnel/start', { method: 'POST', token: token, timeoutMs: 35000 });
  }

  /**
   * POST /tunnel/stop
   */
  function tunnelStop(token) {
    return request('tunnel/stop', { method: 'POST', token: token, timeoutMs: 15000 });
  }

  /**
   * POST /tunnel/restart
   */
  function tunnelRestart(token) {
    return request('tunnel/restart', { method: 'POST', token: token, timeoutMs: 35000 });
  }

  var api = {
    getBaseUrl: getBaseUrl,
    getErrorMessage: getErrorMessage,
    request: request,

    auth: {
      register: authRegister,
      login: authLogin,
      me: authMe,
    },
    files: {
      list: filesList,
      get: filesGet,
      download: filesDownload,
      preview: filesPreview,
      rename: filesRename,
      delete: filesDelete,
      upload: filesUpload,
      uploadResumable: filesUploadResumable,
    },
    ai: {
      search: aiSearch,
      parse: aiParse,
      status: aiStatus,
    },
    system: {
      summary: systemSummary,
    },
    tunnel: {
      status: tunnelStatus,
      connection: tunnelConnection,
      config: tunnelConfig,
      clearConfig: tunnelClearConfig,
      start: tunnelStart,
      stop: tunnelStop,
      restart: tunnelRestart,
    },
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  } else {
    global.AllahPanAPI = api;
  }
})(typeof window !== 'undefined' ? window : this);

"""
启动极简 Web 前端的 HTTP 服务器。

将路径以 /api/ 开头的请求反向代理到本机后端（默认 http://127.0.0.1:8000），
避免页面仍在 localhost:3000 时把 POST 打到静态服务（501）而 GET 被误配到别处的不一致。
可通过环境变量 ALLAHPAN_API_UPSTREAM 指定后端根地址（无尾斜杠）。
"""
from __future__ import annotations

import http.client
import http.server
import os
import socketserver
import webbrowser
from urllib.parse import ParseResult, urlparse

PORT = 3000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
# 与 backend 默认监听一致；勿带尾斜杠
API_UPSTREAM = os.environ.get("ALLAHPAN_API_UPSTREAM", "http://127.0.0.1:8000").rstrip("/")

_FORWARD_HEADER_KEYS = frozenset(
    {
        "authorization",
        "content-type",
        "accept",
        "accept-language",
        "origin",
        "access-control-request-method",
        "access-control-request-headers",
    }
)


def _api_path_only(path: str) -> str:
    return path.split("?", 1)[0]


def _is_api_request(path: str) -> bool:
    p = _api_path_only(path)
    return p == "/api" or p.startswith("/api/")


def _build_client(up: ParseResult):
    host = up.hostname or "127.0.0.1"
    port = up.port
    if port is None:
        port = 443 if up.scheme == "https" else 80
    if up.scheme == "https":
        return http.client.HTTPSConnection(host, port, timeout=120)
    return http.client.HTTPConnection(host, port, timeout=120)


class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def _forward_headers(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for k, v in self.headers.items():
            if k.lower() in _FORWARD_HEADER_KEYS:
                out[k] = v
        return out

    def _read_request_body(self) -> bytes | None:
        if self.command not in ("POST", "PUT", "PATCH", "DELETE"):
            return None
        n = int(self.headers.get("Content-Length", 0) or 0)
        if n <= 0:
            return b""
        return self.rfile.read(n)

    def _proxy_to_backend(self) -> None:
        up = urlparse(API_UPSTREAM)
        body = self._read_request_body()
        hdrs = self._forward_headers()
        if body is not None:
            hdrs["Content-Length"] = str(len(body))

        conn = None
        try:
            conn = _build_client(up)
            conn.request(self.command, self.path, body=body, headers=hdrs)
            resp = conn.getresponse()
            data = resp.read()
        except (OSError, http.client.HTTPException) as e:
            msg = f"无法连接后端 {API_UPSTREAM}（请先启动 AllahPan 后端）: {e}"
            b = msg.encode("utf-8", errors="replace")
            self.send_response(502)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Access-Control-Allow-Origin", "*")
            http.server.BaseHTTPRequestHandler.end_headers(self)
            self.wfile.write(b)
            return
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

        self.send_response(resp.status)
        for k, v in resp.getheaders():
            kl = k.lower()
            if kl in ("transfer-encoding", "connection"):
                continue
            if kl in ("content-type", "content-length", "content-disposition"):
                self.send_header(k, v)
        self.send_header("Access-Control-Allow-Origin", "*")
        http.server.BaseHTTPRequestHandler.end_headers(self)
        self.wfile.write(data)

    def do_GET(self):
        if _is_api_request(self.path):
            self._proxy_to_backend()
            return
        if self.path.rstrip("/") == "/.well-known/appspecific/com.chrome.devtools.json":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"{}")
            return
        super().do_GET()

    def do_HEAD(self):
        if _is_api_request(self.path):
            self._proxy_to_backend()
            return
        super().do_HEAD()

    def do_POST(self):
        if _is_api_request(self.path):
            self._proxy_to_backend()
            return
        self.send_error(501, "Unsupported method ('POST')")

    def do_PUT(self):
        if _is_api_request(self.path):
            self._proxy_to_backend()
            return
        self.send_error(501, "Unsupported method ('PUT')")

    def do_PATCH(self):
        if _is_api_request(self.path):
            self._proxy_to_backend()
            return
        self.send_error(501, "Unsupported method ('PATCH')")

    def do_DELETE(self):
        if _is_api_request(self.path):
            self._proxy_to_backend()
            return
        self.send_error(501, "Unsupported method ('DELETE')")

    def do_OPTIONS(self):
        if _is_api_request(self.path):
            self._proxy_to_backend()
            return
        self.send_response(204)
        self.end_headers()

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, POST, PUT, OPTIONS, PATCH, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, Accept, Origin, Access-Control-Request-Method, Access-Control-Request-Headers")
        super().end_headers()


def main():
    os.chdir(DIRECTORY)

    with socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:
        print("🚀 Web 前端服务器已启动")
        print(f"📍 访问地址：http://localhost:{PORT}")
        print(f"📁 目录：{DIRECTORY}")
        print(f"🔀 /api/* → 反向代理至 {API_UPSTREAM}（环境变量 ALLAHPAN_API_UPSTREAM 可改）")
        print("按 Ctrl+C 停止服务")

        webbrowser.open(f"http://localhost:{PORT}")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 服务器已停止")


if __name__ == "__main__":
    main()

import http.server
import urllib.request
import os

# 88 端口是站点入口：页面和静态资源由 Vite 提供，只有 /api/ 转发到
# Spring Boot。之前所有路径都转发到后端，使访问 / 时被 Security 拦截并
# 返回“token 已过期”，登录页无法加载。
FRONTEND_BACKEND = "http://127.0.0.1:5173"
API_BACKEND = "http://127.0.0.1:8088"

class Proxy(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.proxy_request("GET")
    def do_POST(self):
        self.proxy_request("POST")
    def do_PUT(self):
        self.proxy_request("PUT")
    def do_DELETE(self):
        self.proxy_request("DELETE")
    def do_PATCH(self):
        self.proxy_request("PATCH")
    def do_HEAD(self):
        self.proxy_request("HEAD")
    def do_OPTIONS(self):
        self.proxy_request("OPTIONS")
    
    def proxy_request(self, method):
        backend = API_BACKEND if self.path.startswith("/api/") else FRONTEND_BACKEND
        
        url = backend + self.path
        body = None
        if method in ("POST", "PUT", "PATCH"):
            length = int(self.headers.get("Content-Length", 0))
            if length > 0:
                body = self.rfile.read(length)
        
        req = urllib.request.Request(url, data=body, method=method)
        skip_headers = {"Host", "Connection", "Proxy-Connection", "Transfer-Encoding"}
        for k, v in self.headers.items():
            if k not in skip_headers:
                req.add_header(k, v)
        
        try:
            resp = urllib.request.urlopen(req, timeout=30)
            self.send_response(resp.status)
            for k, v in resp.headers.items():
                if k.lower() not in ("transfer-encoding", "connection"):
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(resp.read())
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            self.send_response(502)
            self.end_headers()
            self.wfile.write(f"Proxy error: {e}".encode())

if __name__ == "__main__":
    port = 88
    server = http.server.HTTPServer(("0.0.0.0", port), Proxy)
    print(f"AllahPan proxy listening on port {port} → frontend={FRONTEND_BACKEND}, api={API_BACKEND}")
    server.serve_forever()

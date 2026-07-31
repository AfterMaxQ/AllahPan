import functools
import gzip
import http.client
import http.server
import mimetypes
import posixpath
import urllib.parse
from pathlib import Path


API_HOST = "127.0.0.1"
API_PORT = 8088
STATIC_ROOT = Path(__file__).resolve().parent / "allahpan-web" / "dist"
COPY_BUFFER_SIZE = 64 * 1024
CONNECT_TIMEOUT_SECONDS = 10
HOP_BY_HOP_HEADERS = {
    "connection",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "proxy-connection",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}
COMPRESSIBLE_CONTENT_TYPES = {
    "application/javascript",
    "application/json",
    "application/xml",
    "image/svg+xml",
}


@functools.lru_cache(maxsize=64)
def _gzip_file(path, modified_ns):
    del modified_ns
    return gzip.compress(Path(path).read_bytes(), compresslevel=5)


class AllahPanProxy(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "AllahPanProxy/2.0"

    def handle(self):
        try:
            super().handle()
        except (
            BrokenPipeError,
            ConnectionResetError,
            ConnectionAbortedError,
        ):
            # Browsers commonly reset SSE, preview, and cancelled download
            # sockets after the response has already been handled.
            return

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def do_PATCH(self):
        self._dispatch("PATCH")

    def do_HEAD(self):
        self._dispatch("HEAD")

    def do_OPTIONS(self):
        self._dispatch("OPTIONS")

    def _dispatch(self, method):
        if self.path.startswith("/api/"):
            self._proxy_api(method)
        elif method in ("GET", "HEAD"):
            self._serve_static(method)
        else:
            self.send_error(405, "Method not allowed")

    def _proxy_api(self, method):
        upstream = http.client.HTTPConnection(
            API_HOST,
            API_PORT,
            timeout=CONNECT_TIMEOUT_SECONDS,
        )
        response_started = False
        try:
            upstream.putrequest(
                method,
                self.path,
                skip_host=True,
                skip_accept_encoding=True,
            )
            for name, value in self.headers.items():
                lower_name = name.lower()
                if lower_name not in HOP_BY_HOP_HEADERS and lower_name != "expect":
                    upstream.putheader(name, value)
            upstream.putheader("Host", f"{API_HOST}:{API_PORT}")
            upstream.putheader("X-Forwarded-For", self.client_address[0])
            upstream.putheader("X-Forwarded-Proto", "http")
            upstream.endheaders()

            content_length = int(self.headers.get("Content-Length", "0") or "0")
            remaining = content_length
            while remaining > 0:
                chunk = self.rfile.read(min(COPY_BUFFER_SIZE, remaining))
                if not chunk:
                    raise ConnectionError("client request body ended early")
                upstream.send(chunk)
                remaining -= len(chunk)

            response = upstream.getresponse()
            content_type = response.getheader("Content-Type", "")
            is_sse = content_type.lower().startswith("text/event-stream")
            has_length = response.getheader("Content-Length") is not None

            if is_sse and upstream.sock is not None:
                upstream.sock.settimeout(None)

            self.send_response(response.status, response.reason)
            for name, value in response.getheaders():
                if name.lower() not in HOP_BY_HOP_HEADERS:
                    self.send_header(name, value)
            if not has_length:
                # http.client decodes upstream chunking. Closing the downstream
                # connection is the valid framing for an unknown-length body.
                self.send_header("Connection", "close")
                self.close_connection = True
            self.end_headers()
            response_started = True

            if method == "HEAD":
                return
            if is_sse:
                self._stream_sse(response)
            else:
                self._stream_response(response)
        except (
            BrokenPipeError,
            ConnectionResetError,
            ConnectionAbortedError,
        ):
            # The browser closed a preview, download, or SSE connection.
            return
        except Exception as exc:
            if not response_started:
                payload = f"Proxy error: {exc}".encode("utf-8")
                self.send_response(502)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                if method != "HEAD":
                    self.wfile.write(payload)
            else:
                self.close_connection = True
        finally:
            upstream.close()

    def _stream_sse(self, response):
        while True:
            line = response.readline()
            if not line:
                return
            self.wfile.write(line)
            self.wfile.flush()

    def _stream_response(self, response):
        while True:
            chunk = response.read(COPY_BUFFER_SIZE)
            if not chunk:
                return
            self.wfile.write(chunk)
            self.wfile.flush()

    def _serve_static(self, method):
        if not STATIC_ROOT.is_dir():
            payload = (
                "Frontend build not found. Run `npm run build` in allahpan-web."
            ).encode("utf-8")
            self.send_response(503)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if method != "HEAD":
                self.wfile.write(payload)
            return

        request_path = urllib.parse.unquote(
            urllib.parse.urlsplit(self.path).path
        )
        relative_path = posixpath.normpath(request_path).lstrip("/")
        candidate = STATIC_ROOT / relative_path
        if candidate.is_dir():
            candidate = candidate / "index.html"
        if not candidate.is_file():
            # Vue Router history fallback.
            candidate = STATIC_ROOT / "index.html"

        stat = candidate.stat()
        content_type = (
            mimetypes.guess_type(candidate.name)[0]
            or "application/octet-stream"
        )
        use_gzip = (
            stat.st_size >= 1024
            and "gzip" in self.headers.get("Accept-Encoding", "").lower()
            and (
                content_type.startswith("text/")
                or content_type in COMPRESSIBLE_CONTENT_TYPES
            )
        )
        compressed_payload = (
            _gzip_file(str(candidate), stat.st_mtime_ns)
            if use_gzip
            else None
        )
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header(
            "Content-Length",
            str(len(compressed_payload) if compressed_payload is not None else stat.st_size),
        )
        if compressed_payload is not None:
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Vary", "Accept-Encoding")
        self.send_header(
            "Cache-Control",
            (
                "public, max-age=31536000, immutable"
                if candidate.parent.name == "assets"
                else "no-cache"
            ),
        )
        self.send_header(
            "Last-Modified",
            self.date_time_string(stat.st_mtime),
        )
        self.end_headers()

        if method == "HEAD":
            return
        try:
            if compressed_payload is not None:
                self.wfile.write(compressed_payload)
                return
            with candidate.open("rb") as source:
                while chunk := source.read(COPY_BUFFER_SIZE):
                    self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return


class ConcurrentHTTPServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 128


if __name__ == "__main__":
    port = 88
    server = ConcurrentHTTPServer(("0.0.0.0", port), AllahPanProxy)
    print(
        f"AllahPan proxy listening on port {port} "
        f"→ static={STATIC_ROOT}, api=http://{API_HOST}:{API_PORT}",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

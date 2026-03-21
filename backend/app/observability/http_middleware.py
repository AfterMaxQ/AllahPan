"""HTTP 中间件：记录流量指标。"""

from starlette.middleware.base import BaseHTTPMiddleware


class TrafficRecordingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        try:
            from app.observability.traffic_stats import record_request

            record_request(request.url.path, request.method, response.status_code)
        except Exception:
            pass
        return response

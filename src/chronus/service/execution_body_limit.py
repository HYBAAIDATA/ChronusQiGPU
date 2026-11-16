"""Bound the encoded request body before JSON parsing on execution ingress."""
from starlette.responses import JSONResponse


class ExecutionBodyLimit:
    def __init__(self, app, max_bytes: int = 4 * 1024 * 1024):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] != "/api/v1/execute":
            return await self.app(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > self.max_bytes:
                response = JSONResponse({"detail": "Execution request exceeds 4 MiB"}, status_code=413)
                return await response(scope, receive, send)
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        consumed = False

        async def replay():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        return await self.app(scope, replay, send)

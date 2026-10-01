"""
Benchmark Target 5: http_router.py
"""
class HTTPRouter:
    def __init__(self):
        self.routes = {}

    def add_route(self, path: str, handler):
        self.routes[path] = handler

    def handle_request(self, path: str, request_data: dict):
        if path in self.routes:
            return self.routes[path](request_data)
        return {"status": 404, "body": "Not Found"}

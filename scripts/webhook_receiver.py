"""Recebedor de webhook só para a demonstração: imprime o que chega e responde 200.

Com FAIL_FIRST=N, responde 503 nas N primeiras chamadas, para ver o retry do Celery.
"""

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

fail_first = int(os.environ.get("FAIL_FIRST", "0"))
calls = 0


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        global calls
        calls += 1
        body = self.rfile.read(int(self.headers["Content-Length"]))
        status = 503 if calls <= fail_first else 200
        signature = self.headers.get("X-Signature-SHA256", "")[:12]
        event = json.loads(body)
        print(f"[{status}] chamada {calls} assinatura={signature}... {event}", flush=True)
        self.send_response(status)
        self.end_headers()

    def log_message(self, *args: object) -> None:
        pass


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8001), WebhookHandler).serve_forever()  # noqa: S104

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from charges.webhooks import HttpWebhookSender, WebhookDeliveryError


class RecordingHandler(BaseHTTPRequestHandler):
    received: list[bytes] = []

    def do_POST(self):
        length = int(self.headers["Content-Length"])
        RecordingHandler.received.append(self.rfile.read(length))
        self.send_response(202)
        self.end_headers()

    def log_message(self, *args):
        pass


@pytest.fixture
def receiver() -> Iterator[str]:
    # Servidor HTTP de verdade numa porta livre: testa o envio sem mock.
    server = HTTPServer(("127.0.0.1", 0), RecordingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/hook"
    server.shutdown()


def test_http_sender_posts_body_and_returns_status(receiver):
    status_code = HttpWebhookSender(timeout_seconds=2).post(
        receiver, b'{"ok":true}', {"Content-Type": "application/json"}
    )

    assert status_code == 202
    assert RecordingHandler.received[-1] == b'{"ok":true}'


def test_http_sender_wraps_connection_error():
    with pytest.raises(WebhookDeliveryError):
        HttpWebhookSender(timeout_seconds=1).post("http://127.0.0.1:9/hook", b"{}", {})

from dataclasses import dataclass, field

from charges.webhooks import WebhookDeliveryError


@dataclass
class SentWebhook:
    url: str
    body: bytes
    headers: dict[str, str]


@dataclass
class FakeWebhookSender:
    """Recebe os webhooks em memória. Cada item de `responses` é um status HTTP
    ou uma exceção a lançar; quando a lista acaba, responde 200."""

    responses: list[int | Exception] = field(default_factory=list)
    sent: list[SentWebhook] = field(default_factory=list)

    def post(self, url: str, body: bytes, headers: dict[str, str]) -> int:
        self.sent.append(SentWebhook(url, body, headers))
        response = self.responses.pop(0) if self.responses else 200
        if isinstance(response, Exception):
            raise response
        return response


_current = FakeWebhookSender()


def current_fake_sender() -> FakeWebhookSender:
    return _current


def install_fake_sender(sender: FakeWebhookSender) -> None:
    global _current
    _current = sender


def network_error() -> WebhookDeliveryError:
    return WebhookDeliveryError("connection refused")

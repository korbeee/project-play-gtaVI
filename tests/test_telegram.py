import json

import httpx

from radar.models import Offer
from radar.rules import Alert
from radar.telegram import format_alert, send

OFFER = Offer(title="Console PlayStation 5 Pro Sony, SSD 2TB", store="KaBuM!", seller="KaBuM!",
              price=6899.0, url="https://www.kabum.com.br/produto/1", source="kabum", item="ps5_pro")


def test_format_alert_queda():
    text = format_alert(Alert(OFFER, "queda", 7799.0, 0.1154), "PlayStation 5 Pro")
    assert text.splitlines() == [
        "🔥 PlayStation 5 Pro — R$ 6.899,00",
        "-12% vs. média dos últimos 7 dias (R$ 7.799,00)",
        "Loja: KaBuM!",
        "Console PlayStation 5 Pro Sony, SSD 2TB",
        "https://www.kabum.com.br/produto/1",
    ]


def test_format_alert_teto():
    text = format_alert(Alert(OFFER, "teto", 7000.0, 0.0144), "PlayStation 5 Pro")
    assert "Abaixo do seu teto de R$ 7.000,00" in text


def test_format_alert_minimo():
    text = format_alert(Alert(OFFER, "minimo", 7100.0, 0.028), "PlayStation 5 Pro")
    assert "Menor preço já visto (antes: R$ 7.100,00)" in text


def test_send_posts_to_bot_api():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"ok": True})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert send("TOKEN123", "-100", "oi", client=client) is True
    assert seen["url"] == "https://api.telegram.org/botTOKEN123/sendMessage"
    assert seen["body"]["chat_id"] == "-100" and seen["body"]["text"] == "oi"


def test_send_returns_false_on_api_error():
    client = httpx.Client(transport=httpx.MockTransport(
        lambda req: httpx.Response(401, json={"ok": False, "description": "Unauthorized"})))
    assert send("bad", "-100", "oi", client=client) is False


def test_send_returns_false_on_network_error():
    def boom(req):
        raise httpx.ConnectError("down")
    client = httpx.Client(transport=httpx.MockTransport(boom))
    assert send("t", "-100", "oi", client=client) is False

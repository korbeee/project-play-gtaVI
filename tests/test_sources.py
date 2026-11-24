from pathlib import Path

import httpx

from radar.http import fetch
from radar.prices import parse_brl
from radar.sources import ALL, amazon, kabum, zoom

FIX = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def test_parse_brl():
    assert parse_brl("R$ 4.369,05") == 4369.05
    assert parse_brl("R$ 7.799") == 7799.0
    assert parse_brl("R$\xa04.369,04") == 4369.04
    assert parse_brl("10x de R$ 779,90") == 779.90
    assert parse_brl("indisponível") is None


def test_kabum_parse():
    offers = kabum.parse(fixture("kabum.html"))
    assert len(offers) >= 5
    pro = [o for o in offers if "5 Pro" in o.title][0]
    assert pro.price == 7799 and pro.seller == "KaBuM!" and pro.store == "KaBuM!"
    assert pro.url.startswith("https://www.kabum.com.br/produto/")
    assert all(o.source == "kabum" and o.item is None for o in offers)


def test_kabum_uses_offer_price_when_active():
    offers = kabum.parse(fixture("kabum.html"))
    digital = [o for o in offers if o.url.endswith("/989702")][0]
    assert digital.price == 4369.05 and digital.old_price == 4893.76


def test_amazon_parse():
    offers = amazon.parse(fixture("amazon.html"))
    assert len(offers) >= 5
    assert all(o.price > 0 and "/dp/" in o.url for o in offers)
    first = [o for o in offers if o.url.endswith("/dp/B0FPGF9J2J")][0]
    assert first.price == 4369.04 and first.old_price == 4599.00 and first.seller == "Amazon"


def test_amazon_ignores_old_price_lower_than_price():
    offers = amazon.parse(fixture("amazon.html"))
    o = [o for o in offers if o.url.endswith("/dp/B0GWNKJDCZ")][0]
    assert o.price == 4259.0 and o.old_price is None


def test_zoom_parse():
    offers = zoom.parse(fixture("zoom.html"))
    pro = [o for o in offers if o.title == "Playstation 5 Pro 2TB"][0]
    assert pro.price == 7799.0 and pro.seller == "KaBuM!" and pro.store == "KaBuM!"
    assert pro.url.startswith("https://www.zoom.com.br/console-de-video-game/") and "?" not in pro.url
    slim = [o for o in offers if o.title == "Playstation 5 Slim 1TB"][0]
    assert slim.seller == "Magazine Luiza"


def test_search_urls():
    assert kabum.search_url("xbox series s") == "https://www.kabum.com.br/busca/xbox-series-s"
    assert amazon.search_url("gta 6 ps5") == "https://www.amazon.com.br/s?k=gta+6+ps5"
    assert zoom.search_url("playstation 5") == "https://www.zoom.com.br/search?q=playstation+5"
    assert [s.NAME for s in ALL] == ["kabum", "amazon", "zoom"]


def _client(status: int, body: str) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(status, text=body)))


def test_fetch_returns_body():
    assert fetch("https://x.test/", client=_client(200, "<html>ok</html>")) == "<html>ok</html>"


def test_fetch_detects_block_page():
    body = "<html><title>Just a moment...</title></html>"
    assert fetch("https://x.test/", client=_client(200, body)) is None


def test_fetch_returns_none_on_403():
    assert fetch("https://x.test/", client=_client(403, "denied")) is None


def test_fetch_returns_none_on_network_error():
    def boom(req):
        raise httpx.ConnectError("down")
    client = httpx.Client(transport=httpx.MockTransport(boom))
    assert fetch("https://x.test/", client=client) is None

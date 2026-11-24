import json
import re

from radar.models import Offer

NAME = "kabum"
_NEXT = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def search_url(query: str) -> str:
    return "https://www.kabum.com.br/busca/" + "-".join(query.split())


def parse(html: str) -> list[Offer]:
    m = _NEXT.search(html)
    if not m:
        return []
    data = json.loads(m.group(1))["props"]["pageProps"]["data"]
    if isinstance(data, str):
        data = json.loads(data)
    offers = []
    for it in data.get("catalogServer", {}).get("data", []):
        if not it.get("available", True):
            continue
        offer = it.get("offer") or {}
        price = offer.get("priceWithDiscount") or it.get("priceWithDiscount") or it.get("price")
        if not price:
            continue
        old = it.get("oldPrice")
        offers.append(Offer(
            title=it.get("name", ""),
            store="KaBuM!",
            seller=it.get("sellerName") or "KaBuM!",
            price=float(price),
            old_price=float(old) if old and old > price else None,
            url=f"https://www.kabum.com.br/produto/{it['code']}",
            source=NAME,
        ))
    return offers

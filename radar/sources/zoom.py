from urllib.parse import quote_plus

from selectolax.lexbor import LexborHTMLParser

from radar.models import Offer
from radar.prices import parse_brl

NAME = "zoom"


def search_url(query: str) -> str:
    return "https://www.zoom.com.br/search?q=" + quote_plus(query)


def parse(html: str) -> list[Offer]:
    tree = LexborHTMLParser(html)
    offers = []
    for card in tree.css('[data-testid="product-card::card"]'):
        name = card.css_first('[data-testid="product-card::name"]')
        price_node = card.css_first('[data-testid="product-card::price"]')
        href = card.attributes.get("href") or ""
        if not name or not price_node or not href.startswith("/"):
            continue
        price = parse_brl(price_node.text())
        via = next((s.text(strip=True) for s in card.css("span") if s.text(strip=True).startswith("Via ")), "")
        seller = via[4:].strip()
        # "Via Amazon" pode ser vendedor do marketplace; a Amazon entra pela fonte própria.
        if price is None or not seller or seller.casefold() == "amazon":
            continue
        offers.append(Offer(
            title=name.text(strip=True),
            store=seller,
            seller=seller,
            price=price,
            url="https://www.zoom.com.br" + href.split("?", 1)[0],
            source=NAME,
        ))
    return offers

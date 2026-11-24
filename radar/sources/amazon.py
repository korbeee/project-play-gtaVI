from urllib.parse import quote_plus

from selectolax.lexbor import LexborHTMLParser

from radar.models import Offer
from radar.prices import parse_brl

NAME = "amazon"


def search_url(query: str) -> str:
    return "https://www.amazon.com.br/s?k=" + quote_plus(query)


def parse(html: str) -> list[Offer]:
    tree = LexborHTMLParser(html)
    offers = []
    for card in tree.css('div[data-component-type="s-search-result"]'):
        asin = card.attributes.get("data-asin")
        title_node = card.css_first("h2")
        price_node = card.css_first(".a-price:not(.a-text-price) .a-offscreen")
        if not asin or not title_node or not price_node:
            continue
        price = parse_brl(price_node.text())
        if price is None:
            continue
        old_node = card.css_first(".a-text-price .a-offscreen")
        old = parse_brl(old_node.text()) if old_node else None
        offers.append(Offer(
            title=title_node.text(strip=True),
            # A busca não mostra o vendedor; a Amazon cobre o marketplace com a garantia A-Z.
            store="Amazon",
            seller="Amazon",
            price=price,
            old_price=old if old and old > price else None,
            url=f"https://www.amazon.com.br/dp/{asin}",
            source=NAME,
        ))
    return offers

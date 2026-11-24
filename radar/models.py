from dataclasses import dataclass


@dataclass(frozen=True)
class Offer:
    title: str
    store: str
    seller: str
    price: float
    url: str
    source: str
    old_price: float | None = None
    item: str | None = None

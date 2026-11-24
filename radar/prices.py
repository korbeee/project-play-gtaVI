import re

_BRL = re.compile(r"R\$\s*([0-9]{1,3}(?:\.[0-9]{3})*|[0-9]+)(?:,([0-9]{2}))?")


def parse_brl(text: str) -> float | None:
    """Converte "R$ 4.369,05" em 4369.05. Retorna None se não houver preço."""
    m = _BRL.search(text.replace("\xa0", " "))
    if not m:
        return None
    whole = m.group(1).replace(".", "")
    cents = m.group(2) or "00"
    return float(f"{whole}.{cents}")


def format_brl(value: float) -> str:
    """4369.05 -> "R$ 4.369,05"."""
    s = f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {s}"

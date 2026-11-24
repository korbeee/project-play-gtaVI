"""Decide a qual item monitorado um título de produto pertence."""

import re
import unicodedata

# Primeira palavra do título que indica acessório ou outro produto.
_ACCESSORY_FIRST = {
    "controle", "capa", "case", "suporte", "base", "carregador", "headset",
    "fone", "skin", "pelicula", "cabo", "dock", "cooler", "dualsense", "pulse",
    "volante", "cartao", "gift", "assinatura", "adesivo", "hd", "ssd", "bolsa",
    "estacao", "mochila", "grip", "protetor", "camera",
}
_ACCESSORY_ANYWHERE = re.compile(r"\bpara (o |a )?(ps5|xbox|console)\b|\bcompativel\b")
_BUNDLE = {"console", "bundle", "kit", "+"}
_GTA = re.compile(r"\bgta (6|vi)\b|\bgrand theft auto vi\b")


def _normalize(title: str) -> str:
    text = unicodedata.normalize("NFKD", title)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().replace("®", " ").replace("™", " ")
    text = re.sub(r"playstation\s*5|\bps\s+5\b", "ps5", text)
    text = re.sub(r"[^a-z0-9|+ ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _console(text: str) -> str | None:
    if re.search(r"\bps5 pro\b", text):
        return "ps5_pro"
    if re.search(r"\bps5\b", text):
        return "ps5"
    if re.search(r"\bseries x\b", text):
        return "xbox_series_x"
    if re.search(r"\bseries s\b", text):
        return "xbox_series_s"
    return None


def classify(title: str) -> str | None:
    text = _normalize(title)
    if not text:
        return None
    words = text.split(" ")
    first = words[0]
    if first in _ACCESSORY_FIRST or _ACCESSORY_ANYWHERE.search(text):
        return None
    is_gta = bool(_GTA.search(text))
    if first in ("jogo", "game"):
        return "gta6" if is_gta else None
    # Console vendido junto com o jogo conta como console.
    if is_gta and not _BUNDLE.intersection(words):
        return "gta6"
    return _console(text)


def is_trusted(seller: str, trusted: list[str]) -> bool:
    s = seller.casefold()
    return any(t.casefold() in s for t in trusted)

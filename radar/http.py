import logging

import httpx

log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Accept": "text/html,application/xhtml+xml",
}

# Páginas de desafio anti-robô. A loja que mostra uma delas é pulada, nunca contornada.
_BLOCK_MARKERS = (
    "<title>just a moment",
    "cf-chl-",
    "/errors/validatecaptcha",
    "captcha-delivery.com",
    "px-captcha",
)


def is_block_page(html: str) -> bool:
    head = html[:200_000].lower()
    return any(m in head for m in _BLOCK_MARKERS)


def fetch(url: str, client: httpx.Client | None = None) -> str | None:
    """Baixa a página. Retorna None se a loja recusar, bloquear ou a rede falhar."""
    own = client is None
    client = client or httpx.Client(headers=HEADERS, timeout=15, follow_redirects=True)
    try:
        resp = client.get(url)
    except httpx.HTTPError as e:
        log.warning("falha de rede em %s: %s", url, e.__class__.__name__)
        return None
    finally:
        if own:
            client.close()
    if resp.status_code != 200:
        log.warning("HTTP %s em %s", resp.status_code, url)
        return None
    if is_block_page(resp.text):
        log.warning("página de bloqueio em %s", url)
        return None
    return resp.text

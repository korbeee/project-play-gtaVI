import logging

import httpx

from radar.prices import format_brl
from radar.rules import Alert

log = logging.getLogger(__name__)


def format_alert(alert: Alert, label: str, window_days: int = 7) -> str:
    o = alert.offer
    ref = format_brl(alert.reference) if alert.reference is not None else ""
    if alert.reason == "teto":
        why = f"Abaixo do seu teto de {ref}"
    elif alert.reason == "queda":
        why = f"-{round((alert.pct or 0) * 100)}% vs. média dos últimos {window_days} dias ({ref})"
    else:
        why = f"Menor preço já visto (antes: {ref})"
    return "\n".join([f"🔥 {label} — {format_brl(o.price)}", why, f"Loja: {o.store}", o.title, o.url])


def send(token: str, chat_id: str, text: str, client: httpx.Client | None = None) -> bool:
    """Envia a mensagem ao grupo. Nunca levanta exceção nem registra o token."""
    own = client is None
    client = client or httpx.Client(timeout=20)
    try:
        resp = client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "disable_web_page_preview": False},
        )
    except httpx.HTTPError as e:
        log.error("Telegram: falha de rede (%s)", e.__class__.__name__)
        return False
    finally:
        if own:
            client.close()
    if resp.status_code != 200:
        try:
            desc = resp.json().get("description", "")
        except ValueError:
            desc = ""
        log.error("Telegram recusou a mensagem: HTTP %s %s", resp.status_code, desc)
        return False
    return True

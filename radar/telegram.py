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
        return _send(client, token, str(chat_id), text, follow_migration=True)
    finally:
        if own:
            client.close()


def _send(client: httpx.Client, token: str, chat_id: str, text: str, follow_migration: bool) -> bool:
    try:
        resp = client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "disable_web_page_preview": False},
        )
    except httpx.HTTPError as e:
        log.error("Telegram: falha de rede (%s)", e.__class__.__name__)
        return False
    if resp.status_code == 200:
        return True
    try:
        body = resp.json()
    except ValueError:
        body = {}
    new_id = (body.get("parameters") or {}).get("migrate_to_chat_id")
    if new_id and follow_migration:
        # O grupo virou supergrupo e ganhou outro ID: envia para o novo e avisa para atualizar.
        log.warning("o grupo virou supergrupo; atualize TELEGRAM_CHAT_ID para %s", new_id)
        return _send(client, token, str(new_id), text, follow_migration=False)
    log.error("Telegram recusou a mensagem: HTTP %s %s", resp.status_code, body.get("description", ""))
    return False

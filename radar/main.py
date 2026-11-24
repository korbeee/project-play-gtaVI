"""Uma rodada do radar: busca, classifica, compara com o histórico e avisa."""

import argparse
import logging
import os
import time
from dataclasses import replace
from datetime import UTC, datetime
from functools import partial
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable

from radar import telegram
from radar.classify import classify, is_trusted
from radar.config import Config, load_config
from radar.http import fetch as http_fetch
from radar.models import Offer
from radar.rules import Alert, check
from radar.sources import ALL
from radar.state import State

log = logging.getLogger("radar")
ROOT = Path(__file__).resolve().parent.parent
PING_TEXT = (
    "✅ Radar de Consoles ligado.\n"
    "Vou avisar aqui só quando PS5, PS5 Pro, Xbox Series X/S ou GTA 6 ficarem baratos."
)


def _collect(cfg: Config, item: str, fetch, sources, status: dict[str, str]) -> list[Offer]:
    item_cfg = cfg.items[item]
    found: list[Offer] = []
    for query in item_cfg.queries:
        for src in sources:
            html = fetch(src.search_url(query))
            if html is None:
                status.setdefault(src.NAME, "bloqueada/sem resposta")
                continue
            try:
                parsed = src.parse(html)
            except Exception as e:  # layout mudou: segue com as outras lojas
                log.warning("%s: erro ao ler a página (%s: %s)", src.NAME, e.__class__.__name__, e)
                status[src.NAME] = "erro de leitura"
                continue
            status[src.NAME] = "ok"
            for o in parsed:
                if (classify(o.title) == item and is_trusted(o.seller, cfg.trusted_sellers)
                        and o.price >= item_cfg.min_price):
                    found.append(replace(o, item=item))
    return found


def _run_item(cfg: Config, item: str, state: State, fetch, send, now, sources, status) -> Alert | None:
    item_cfg = cfg.items[item]
    offers = _collect(cfg, item, fetch, sources, status)
    if not offers:
        log.info("%s: nenhuma oferta encontrada", item)
        return None
    best = min(offers, key=lambda o: o.price)
    alert = check(best, state.history.get(item, []), now, cfg, item_cfg.cap, state.alerted)
    if alert is None:
        log.info("%s: menor preço R$ %.2f em %s, sem promoção (%s | %s)",
                 item, best.price, best.store, best.title[:80], best.url)
        state.record(item, now, best.price)
        return None
    if not send(telegram.format_alert(alert, item_cfg.label, cfg.window_days)):
        # Não registra o preço: senão a próxima rodada já não o veria como promoção.
        log.error("%s: aviso não enviado; tenta de novo na próxima rodada", item)
        return None
    state.alerted[best.url] = best.price
    state.record(item, now, best.price)
    log.info("%s: AVISO enviado (%s, R$ %.2f)", item, alert.reason, best.price)
    return alert


def run_once(
    cfg: Config,
    state: State,
    fetch: Callable[[str], str | None],
    send: Callable[[str], bool],
    now: datetime,
    sources=ALL,
) -> list[Alert]:
    alerts: list[Alert] = []
    status: dict[str, str] = {}
    for item in cfg.items:
        try:
            alert = _run_item(cfg, item, state, fetch, send, now, sources, status)
        except Exception as e:  # um item com problema não derruba os outros
            log.error("%s: erro inesperado (%s: %s)", item, e.__class__.__name__, e)
            continue
        if alert:
            alerts.append(alert)
    state.prune(now, cfg.history_days)
    for name, st in sorted(status.items()):
        log.info("fonte %s: %s", name, st)
    return alerts


def _polite_fetch(url: str) -> str | None:
    time.sleep(1.5)  # não martelar as lojas
    return http_fetch(url)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="radar", description="Radar de preços de consoles")
    parser.add_argument("--dry-run", action="store_true", help="mostra os avisos em vez de enviar")
    parser.add_argument("--ping", action="store_true", help="só manda uma mensagem de teste no grupo")
    parser.add_argument("--log-file", type=Path, help="grava o registro neste arquivo (até ~1 MB)")
    args = parser.parse_args(argv)
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if args.log_file:
        args.log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers = [RotatingFileHandler(args.log_file, maxBytes=1_000_000, backupCount=1, encoding="utf-8")]
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=handlers, force=True)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    cfg = load_config(ROOT / "config.toml")
    data_dir = ROOT / "data"
    state = State.load(data_dir)

    if args.dry_run:
        def send(text: str) -> bool:
            print("\n--- aviso (dry-run) ---\n" + text)
            return True
    else:
        token, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
        if not token or not chat:
            # Falha visível: o GitHub avisa por e-mail que a configuração está incompleta.
            log.error("TELEGRAM_TOKEN e TELEGRAM_CHAT_ID não configurados "
                      "(variáveis do Windows ou Secrets do GitHub); se acabou de salvar, abra um terminal novo")
            return 1
        send = partial(telegram.send, token, chat)

    if args.ping:
        ok = send(PING_TEXT)
        log.info("mensagem de teste %s", "enviada" if ok else "NÃO enviada")
        return 0 if ok else 1

    try:
        run_once(cfg, state, _polite_fetch, send, datetime.now(UTC))
    finally:
        # Salva mesmo se algo quebrar, para nunca repetir um aviso já enviado.
        if not args.dry_run:
            state.save(data_dir)
    return 0

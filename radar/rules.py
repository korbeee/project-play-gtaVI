"""Decide se uma oferta é barata o bastante para avisar."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import median

from radar.config import Config
from radar.models import Offer

# Um "novo mínimo" precisa ser pelo menos 1% menor que o anterior (ignora centavos).
MIN_NEW_LOW_PCT = 0.01


@dataclass(frozen=True)
class Alert:
    offer: Offer
    reason: str               # "teto" | "queda" | "minimo"
    reference: float | None   # teto, mediana dos últimos dias ou mínimo anterior
    pct: float | None = None  # queda em relação à referência (0.12 = 12%)


def check(
    offer: Offer,
    history: list[tuple[datetime, float]],
    now: datetime,
    cfg: Config,
    cap: float | None,
    alerted: dict[str, float],
) -> Alert | None:
    """`history` é o histórico ANTES de registrar a rodada atual."""
    if offer.url in alerted and offer.price >= alerted[offer.url]:
        return None
    if cap is not None and offer.price <= cap:
        return Alert(offer, "teto", cap, 1 - offer.price / cap)
    if not history or min(t for t, _ in history) > now - timedelta(hours=cfg.warmup_hours):
        return None
    window = [p for t, p in history if t >= now - timedelta(days=cfg.window_days)]
    if window:
        ref = median(window)
        if offer.price <= ref * (1 - cfg.drop_pct):
            return Alert(offer, "queda", ref, 1 - offer.price / ref)
    lowest = min(p for _, p in history)
    if offer.price <= lowest * (1 - MIN_NEW_LOW_PCT):
        return Alert(offer, "minimo", lowest, 1 - offer.price / lowest)
    return None

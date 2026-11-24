from datetime import UTC, datetime, timedelta

import pytest

from radar.config import Config, ItemCfg
from radar.models import Offer
from radar.rules import check

NOW = datetime(2026, 11, 24, 12, tzinfo=UTC)
CFG = Config(items={"ps5": ItemCfg("PlayStation 5", ["playstation 5"])}, trusted_sellers=["KaBuM!"])


def offer(price: float, url: str = "https://www.kabum.com.br/produto/1") -> Offer:
    return Offer(title="Console PS5", store="KaBuM!", seller="KaBuM!", price=price, url=url,
                 source="kabum", item="ps5")


def hourly(hours: int, price: float) -> list[tuple[datetime, float]]:
    return [(NOW - timedelta(hours=h), price) for h in range(hours, 0, -1)]


def test_cap_alert():
    alert = check(offer(4900), [], NOW, CFG, cap=5000, alerted={})
    assert alert.reason == "teto" and alert.reference == 5000


def test_no_alert_during_warmup():
    assert check(offer(3000), hourly(10, 5000), NOW, CFG, cap=None, alerted={}) is None


def test_drop_alert():
    alert = check(offer(4499), hourly(72, 5000), NOW, CFG, cap=None, alerted={})
    assert alert.reason == "queda"
    assert alert.reference == 5000
    assert alert.pct == pytest.approx(0.1002)


def test_9pct_drop_is_not_queda_but_is_new_minimum():
    alert = check(offer(4550), hourly(72, 5000), NOW, CFG, cap=None, alerted={})
    assert alert.reason == "minimo"


def test_cent_level_new_minimum_is_ignored():
    # Variações de centavos não são promoção: o novo mínimo precisa ser ≥ 1% menor.
    assert check(offer(4990), hourly(72, 5000), NOW, CFG, cap=None, alerted={}) is None


def test_new_minimum():
    history = hourly(72, 5000)
    history[10] = (history[10][0], 4700)
    alert = check(offer(4650), history, NOW, CFG, cap=None, alerted={})
    assert alert.reason == "minimo" and alert.reference == 4700


def test_median_uses_only_window_days():
    old = [(NOW - timedelta(days=20, hours=h), 9000) for h in range(48)]
    alert = check(offer(4499), old + hourly(72, 5000), NOW, CFG, cap=None, alerted={})
    assert alert.reason == "queda" and alert.reference == 5000


def test_dedup():
    alerted = {"https://www.kabum.com.br/produto/1": 4499}
    assert check(offer(4499), hourly(72, 5000), NOW, CFG, cap=None, alerted=alerted) is None
    assert check(offer(4400), hourly(72, 5000), NOW, CFG, cap=None, alerted=alerted) is not None

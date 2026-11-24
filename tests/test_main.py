from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from radar.config import load_config
from radar.main import run_once
from radar.models import Offer
from radar.sources import ALL
from radar.state import State

ROOT = Path(__file__).resolve().parent.parent
FIX = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 11, 24, 12, tzinfo=UTC)
CFG = load_config(ROOT / "config.toml")


def fixture_fetch(url: str) -> str | None:
    for name in ("kabum", "amazon", "zoom"):
        if f"{name}.com.br" in url:
            return (FIX / f"{name}.html").read_text(encoding="utf-8")
    return None


class Outbox:
    def __init__(self, ok: bool = True):
        self.ok, self.texts = ok, []

    def __call__(self, text: str) -> bool:
        self.texts.append(text)
        return self.ok


def history(price: float, days: int = 3) -> list[tuple[datetime, float]]:
    return [(NOW - timedelta(hours=h), price) for h in range(days * 24, 0, -1)]


def test_run_alerts_cheap_ps5_pro():
    state = State(history={"ps5_pro": history(9000)})
    out = Outbox()
    alerts = run_once(CFG, state, fixture_fetch, out, NOW)
    assert [a.offer.item for a in alerts] == ["ps5_pro"]
    assert alerts[0].offer.price <= 7799
    assert "PlayStation 5 Pro" in out.texts[0]
    assert state.alerted == {alerts[0].offer.url: alerts[0].offer.price}
    assert state.history["ps5_pro"][-1] == (NOW, alerts[0].offer.price)


def test_first_run_records_history_without_alerts():
    state = State()
    out = Outbox()
    assert run_once(CFG, state, fixture_fetch, out, NOW) == []
    assert out.texts == []
    assert {"ps5", "ps5_pro"} <= set(state.history)


def test_run_survives_failing_source():
    def fetch(url):
        return None if "kabum" in url else fixture_fetch(url)

    def broken(html):
        raise ValueError("layout mudou")

    zoom_broken = SimpleNamespace(NAME="zoom", search_url=ALL[2].search_url, parse=broken)
    state = State()
    run_once(CFG, state, fetch, Outbox(), NOW, sources=[ALL[0], ALL[1], zoom_broken])
    assert "ps5" in state.history  # Amazon ainda trouxe ofertas


def test_failed_send_not_marked():
    state = State(history={"ps5_pro": history(9000)})
    out = Outbox(ok=False)
    run_once(CFG, state, fixture_fetch, out, NOW)
    assert out.texts and state.alerted == {}


def test_no_duplicate_on_second_run():
    state = State(history={"ps5_pro": history(9000)})
    out = Outbox()
    run_once(CFG, state, fixture_fetch, out, NOW)
    run_once(CFG, state, fixture_fetch, out, NOW + timedelta(minutes=10))
    assert len(out.texts) == 1


def _fake_source(*offers: Offer) -> SimpleNamespace:
    return SimpleNamespace(NAME="fake", search_url=lambda q: "https://fake.test/" + q,
                           parse=lambda html: list(offers))


def _offer(title: str, seller: str, price: float) -> Offer:
    return Offer(title=title, store=seller, seller=seller, price=price,
                 url=f"https://fake.test/{seller}/{price}", source="fake")


def test_untrusted_seller_ignored():
    src = _fake_source(_offer("Console PlayStation 5 Pro", "Loja do Zé", 5000))
    state = State(history={"ps5_pro": history(9000)})
    out = Outbox()
    run_once(CFG, state, lambda url: "<html/>", out, NOW, sources=[src])
    assert out.texts == [] and "ps5_pro" not in state.alerted


def test_price_below_min_price_ignored():
    # Jogo ou acessório com título de console, ou golpe: abaixo do mínimo plausível.
    src = _fake_source(_offer("Console PlayStation 5 Pro", "KaBuM!", 300))
    state = State(history={"ps5_pro": history(9000)})
    out = Outbox()
    run_once(CFG, state, lambda url: "<html/>", out, NOW, sources=[src])
    assert out.texts == []
    assert state.history["ps5_pro"][-1][0] != NOW

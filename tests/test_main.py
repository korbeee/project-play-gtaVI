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


def test_failed_minimo_alert_is_retried_next_run():
    # 48 h a R$ 5000; uma oferta de R$ 4900 é novo mínimo. Se o envio falhar,
    # a rodada seguinte precisa tentar de novo (o preço não pode virar histórico).
    src = _fake_source(_offer("Console PlayStation 5 Pro", "KaBuM!", 4900))
    state = State(history={"ps5_pro": history(5000, days=2)})
    run_once(CFG, state, lambda url: "<html/>", Outbox(ok=False), NOW, sources=[src])
    out = Outbox()
    alerts = run_once(CFG, state, lambda url: "<html/>", out, NOW + timedelta(minutes=10), sources=[src])
    assert [a.reason for a in alerts] == ["minimo"] and len(out.texts) == 1


def test_error_in_one_item_does_not_stop_the_others():
    calls = []

    def send(text):
        calls.append(text)
        if len(calls) == 1:
            raise RuntimeError("falha inesperada")
        return True

    src = _fake_source(_offer("Console PlayStation 5 Pro", "KaBuM!", 5000),
                       _offer("Console Xbox Series X", "KaBuM!", 3000))
    state = State(history={"ps5_pro": history(9000), "xbox_series_x": history(9000)})
    run_once(CFG, state, lambda url: "<html/>", send, NOW, sources=[src])
    assert len(calls) == 2 and len(state.alerted) == 1


def test_main_without_secrets_fails_loudly(monkeypatch, tmp_path):
    import radar.main as m
    monkeypatch.delenv("TELEGRAM_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert m.main([]) == 1


def test_main_saves_state_even_if_run_crashes(monkeypatch, tmp_path):
    import radar.main as m
    (tmp_path / "config.toml").write_text((ROOT / "config.toml").read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(m, "ROOT", tmp_path)
    monkeypatch.setenv("TELEGRAM_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "c")

    def crash(cfg, state, fetch, send, now, sources=None):
        state.alerted["https://x/1"] = 1.0
        raise RuntimeError("boom")

    monkeypatch.setattr(m, "run_once", crash)
    with __import__("pytest").raises(RuntimeError):
        m.main([])
    assert (tmp_path / "data" / "alerted.json").exists()


def test_ping_sends_a_test_message(monkeypatch):
    import radar.main as m
    sent = []
    monkeypatch.setenv("TELEGRAM_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "c")
    monkeypatch.setattr(m.telegram, "send", lambda token, chat, text: sent.append(text) or True)
    monkeypatch.setattr(m, "run_once", lambda *a, **k: (_ for _ in ()).throw(AssertionError("não deve rodar")))
    assert m.main(["--ping"]) == 0
    assert len(sent) == 1 and "Radar de Consoles ligado" in sent[0]


def test_ping_fails_loudly_when_telegram_refuses(monkeypatch):
    import radar.main as m
    monkeypatch.setenv("TELEGRAM_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "c")
    monkeypatch.setattr(m.telegram, "send", lambda token, chat, text: False)
    assert m.main(["--ping"]) == 1


def test_log_file_records_the_run(monkeypatch, tmp_path):
    # No PC a tarefa roda escondida (pythonw): o registro precisa ir para um arquivo.
    import logging

    import radar.main as m
    log_file = tmp_path / "radar.log"
    monkeypatch.delenv("TELEGRAM_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert m.main(["--log-file", str(log_file)]) == 1
    for h in logging.getLogger().handlers[:]:
        h.close()
        logging.getLogger().removeHandler(h)
    assert "TELEGRAM_TOKEN" in log_file.read_text(encoding="utf-8")

from pathlib import Path

from radar.config import load_config

ROOT = Path(__file__).resolve().parent.parent


def test_load_project_config():
    cfg = load_config(ROOT / "config.toml")
    assert set(cfg.items) == {"ps5", "ps5_pro", "xbox_series_x", "xbox_series_s", "gta6"}
    assert cfg.items["gta6"].queries == ["gta 6 ps5", "gta 6 xbox"]
    assert cfg.items["ps5"].cap is None
    assert cfg.drop_pct == 0.10 and cfg.window_days == 7 and cfg.warmup_hours == 24
    assert "KaBuM!" in cfg.trusted_sellers


def test_min_price_guards_against_games_and_accessories():
    cfg = load_config(ROOT / "config.toml")
    assert cfg.items["ps5_pro"].min_price == 4500
    assert cfg.items["xbox_series_s"].min_price == 1500
    assert cfg.items["gta6"].min_price == 100

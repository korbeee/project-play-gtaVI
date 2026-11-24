from datetime import UTC, datetime, timedelta

from radar.state import State

NOW = datetime(2026, 11, 24, 12, tzinfo=UTC)


def test_load_missing_dir_is_empty(tmp_path):
    s = State.load(tmp_path / "nada")
    assert s.history == {} and s.alerted == {}


def test_state_roundtrip(tmp_path):
    s = State.load(tmp_path)
    s.record("ps5", NOW, 4369.05)
    s.alerted["https://x/1"] = 4369.05
    s.save(tmp_path)
    loaded = State.load(tmp_path)
    assert loaded.history == {"ps5": [(NOW, 4369.05)]}
    assert loaded.alerted == {"https://x/1": 4369.05}


def test_record_keeps_one_point_per_hour_with_the_lowest_price():
    # Rodadas de 10 em 10 min não devem inchar o histórico salvo no GitHub.
    s = State()
    s.record("ps5", NOW, 5000)
    s.record("ps5", NOW + timedelta(minutes=10), 4900)
    s.record("ps5", NOW + timedelta(minutes=20), 4950)
    s.record("ps5", NOW + timedelta(hours=1), 5100)
    assert s.history["ps5"] == [(NOW, 4900), (NOW + timedelta(hours=1), 5100)]


def test_prune_drops_older_than_30_days():
    s = State(history={}, alerted={})
    s.record("ps5", NOW - timedelta(days=31), 5000)
    s.record("ps5", NOW - timedelta(days=29), 4900)
    s.prune(NOW, days=30)
    assert s.history["ps5"] == [(NOW - timedelta(days=29), 4900)]

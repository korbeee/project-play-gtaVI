import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

HISTORY_FILE = "history.json"
ALERTED_FILE = "alerted.json"


@dataclass
class State:
    """Menor preço de cada item por rodada e ofertas já avisadas (url -> preço)."""

    history: dict[str, list[tuple[datetime, float]]] = field(default_factory=dict)
    alerted: dict[str, float] = field(default_factory=dict)

    @classmethod
    def load(cls, directory: Path) -> "State":
        directory = Path(directory)
        history: dict[str, list[tuple[datetime, float]]] = {}
        alerted: dict[str, float] = {}
        h = directory / HISTORY_FILE
        if h.exists():
            raw = json.loads(h.read_text(encoding="utf-8"))
            history = {k: [(datetime.fromisoformat(t), float(p)) for t, p in v] for k, v in raw.items()}
        a = directory / ALERTED_FILE
        if a.exists():
            alerted = {k: float(v) for k, v in json.loads(a.read_text(encoding="utf-8")).items()}
        return cls(history=history, alerted=alerted)

    def save(self, directory: Path) -> None:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        history = {k: [[t.isoformat(), p] for t, p in v] for k, v in sorted(self.history.items())}
        (directory / HISTORY_FILE).write_text(json.dumps(history, indent=1), encoding="utf-8")
        (directory / ALERTED_FILE).write_text(
            json.dumps(dict(sorted(self.alerted.items())), indent=1), encoding="utf-8")

    def record(self, item: str, now: datetime, price: float) -> None:
        """Um ponto por hora: rodadas da mesma hora mantêm o menor preço."""
        points = self.history.setdefault(item, [])
        hour = now.replace(minute=0, second=0, microsecond=0)
        if points:
            last_t, last_p = points[-1]
            if last_t.replace(minute=0, second=0, microsecond=0) == hour:
                points[-1] = (last_t, min(last_p, price))
                return
        points.append((now, price))

    def prune(self, now: datetime, days: int) -> None:
        cutoff = now - timedelta(days=days)
        self.history = {k: [(t, p) for t, p in v if t >= cutoff] for k, v in self.history.items()}

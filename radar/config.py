import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ItemCfg:
    label: str
    queries: list[str]
    cap: float | None = None
    min_price: float = 0.0


@dataclass(frozen=True)
class Config:
    items: dict[str, ItemCfg]
    trusted_sellers: list[str]
    drop_pct: float = 0.10
    window_days: int = 7
    warmup_hours: int = 24
    history_days: int = 30


def load_config(path: Path) -> Config:
    raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    items = {
        item_id: ItemCfg(
            label=v["label"],
            queries=list(v["queries"]),
            cap=v.get("cap"),
            min_price=float(v.get("min_price", 0.0)),
        )
        for item_id, v in raw["items"].items()
    }
    return Config(
        items=items,
        trusted_sellers=list(raw["trusted_sellers"]),
        drop_pct=float(raw.get("drop_pct", 0.10)),
        window_days=int(raw.get("window_days", 7)),
        warmup_hours=int(raw.get("warmup_hours", 24)),
        history_days=int(raw.get("history_days", 30)),
    )

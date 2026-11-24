# Radar de Consoles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Python bot, run by GitHub Actions every 10 minutes, that finds console and GTA 6 deals in trusted Brazilian stores and posts them to a Telegram group only when the price is really low.

**Architecture:** One run = fetch search pages per item from each source, parse into `Offer`s, classify titles into items, drop untrusted sellers, pick the cheapest offer per item, apply the "cheap" rules against stored history, send new alerts to Telegram, save state. State lives in `data/*.json`, committed back by the workflow.

**Tech Stack:** Python 3.12, `httpx`, `selectolax`, `pytest`, GitHub Actions, Telegram Bot API.

**Spec:** `docs/superpowers/specs/2026-11-24-radar-consoles-design.md`

## Global Constraints

- Items (ids): `ps5`, `ps5_pro`, `xbox_series_x`, `xbox_series_s`, `gta6`.
- Trusted sellers: KaBuM!, Amazon, Magazine Luiza / Magalu, Pichau, Terabyte. Shopee and AliExpress never.
- Cheap rules: ≥ 10% below the median of the per-run minimum prices of the last 7 days; or below the all-time minimum (only after 24 h of history); or ≤ optional fixed cap per item (empty by default).
- An offer (by URL) is alerted once; again only if its price drops below the alerted price.
- History kept 30 days.
- Never bypass anti-bot protections: a blocked source (403, captcha page) is skipped and logged.
- Telegram token and chat id come only from env vars `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` (GitHub Secrets). Never in code or config.
- Mercado Livre source: out of this plan (optional later, needs user token).
- Messages to the user are in Portuguese (pt-BR).

## Review Focus

1. A source returns 403 / captcha / changed layout → that source yields `[]`, the run continues with the others and exits 0 (a failing workflow would email the user every 10 minutes). → Task 4 test `test_run_survives_failing_source`.
2. Accessories and games mentioning a console ("Controle DualSense PS5", "Jogo GTA VI PS5", "Suporte vertical PS5 Pro") must not count as consoles; "PS5 Pro" must not count as "PS5"; "Console PS5 + GTA VI" counts as `ps5`. → Task 1 tests.
3. Brazilian price format "R$ 4.369,05" and "R$ 7.799" parsed as 4369.05 / 7799.0. → Task 2 test `test_parse_brl`.
4. First day of history: no alert from rules 1–2 until 24 h of history, so the group is not flooded at start. → Task 3 test `test_no_alert_during_warmup`.
5. Telegram send fails (bad token, network) → the offer is NOT marked as alerted, so it is retried next run. → Task 4 test `test_failed_send_not_marked`.

---

### Task 1: Project scaffold, models, config, classifier

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `config.toml`, `radar/__init__.py`, `radar/models.py`, `radar/config.py`, `radar/classify.py`
- Test: `tests/test_classify.py`

**Interfaces:**
- Produces:
  - `radar.models.Offer` — `@dataclass(frozen=True)`: `title: str, store: str, seller: str, price: float, url: str, source: str, old_price: float | None = None, item: str | None = None`
  - `radar.config.ItemCfg(label: str, queries: list[str], cap: float | None)`
  - `radar.config.Config(items: dict[str, ItemCfg], trusted_sellers: list[str], drop_pct: float, window_days: int, warmup_hours: int, history_days: int)`
  - `radar.config.load_config(path: Path) -> Config`
  - `radar.classify.classify(title: str) -> str | None`
  - `radar.classify.is_trusted(seller: str, trusted: list[str]) -> bool` (case-insensitive substring match)

- [ ] **Step 1: `git init`, `pyproject.toml`** (deps `httpx`, `selectolax`; dev `pytest`), `.gitignore` (`__pycache__/`, `.venv/`, `.pytest_cache/`).
- [ ] **Step 2: `config.toml`** with the 5 items. Labels: "PlayStation 5", "PlayStation 5 Pro", "Xbox Series X", "Xbox Series S", "GTA 6". Queries: `["playstation 5"]`, `["playstation 5 pro"]`, `["xbox series x"]`, `["xbox series s"]`, `["gta 6 ps5", "gta 6 xbox"]`. `cap` absent. `drop_pct = 0.10`, `window_days = 7`, `warmup_hours = 24`, `history_days = 30`, trusted list from Global Constraints.
- [ ] **Step 3: Write failing tests** in `tests/test_classify.py`:

```python
import pytest
from radar.classify import classify, is_trusted

@pytest.mark.parametrize("title,item", [
    ("Console Sony PlayStation 5, SSD 825GB, Edição Digital", "ps5"),
    ("PlayStation®5 Slim Disk - Pacote ASTRO BOT e Gran Turismo 7", "ps5"),
    ("Console PlayStation 5 Pro Sony, SSD 2TB", "ps5_pro"),
    ("Playstation 5 Pro 2TB", "ps5_pro"),
    ("Console Xbox Series X 1TB", "xbox_series_x"),
    ("Console Microsoft Xbox Series S 512GB", "xbox_series_s"),
    ("Jogo Grand Theft Auto VI, PS5", "gta6"),
    ("GTA 6 - Xbox Series X|S", "gta6"),
    ("Console PS5 + GTA VI", "ps5"),
    ("Controle Sem Fio Sony DualSense, PlayStation 5", None),
    ("Suporte Vertical para PS5 Pro", None),
    ("Headset Pulse 3D PS5", None),
    ("Capa protetora Xbox Series S", None),
    ("Jogo EA FC 26 PS5", None),
])
def test_classify(title, item):
    assert classify(title) == item

def test_is_trusted():
    assert is_trusted("KaBuM!", ["KaBuM!"])
    assert is_trusted("Via Magazine Luiza", ["Magazine Luiza"])
    assert not is_trusted("Loja do Zé", ["KaBuM!", "Amazon"])
```

- [ ] **Step 4: Run** `pytest tests/test_classify.py -v` → FAIL (module missing).
- [ ] **Step 5: Implement `classify`.** Normalize (lowercase, strip accents and ®/™). Order: if the title has an accessory word (controle, capa, case, suporte, base, carregador, headset, fone, skin, película, cabo, dock, cooler, "para ps5", "compatível") → `None`. If it has a console word ("console", or the title starts with the platform name) or no game marker → console checks first: "ps5 pro"/"playstation 5 pro" → `ps5_pro`; "ps5"/"playstation 5" → `ps5`; "series x" → `xbox_series_x`; "series s" → `xbox_series_s`. A title with "jogo"/"game" and a GTA marker ("gta 6", "gta vi", "grand theft auto vi") → `gta6`; "jogo" without GTA marker → `None`. "Xbox Series X|S" in a game title must not become a console.
- [ ] **Step 6: Run** `pytest tests/test_classify.py -v` → PASS.
- [ ] **Step 7: Commit** `feat: scaffold, config and title classifier`.

### Task 2: Sources (Kabum, Amazon, Zoom) parsed from saved pages

**Files:**
- Create: `radar/http.py`, `radar/sources/__init__.py`, `radar/sources/kabum.py`, `radar/sources/amazon.py`, `radar/sources/zoom.py`, `radar/prices.py`
- Create fixtures: `tests/fixtures/kabum.html`, `tests/fixtures/amazon.html`, `tests/fixtures/zoom.html` (copied from the 2026-11-24 recon downloads; re-download if missing)
- Test: `tests/test_sources.py`

**Interfaces:**
- Consumes: `Offer` (Task 1).
- Produces:
  - `radar.prices.parse_brl(text: str) -> float | None`
  - `radar.http.fetch(url: str, client: httpx.Client | None = None) -> str | None` — desktop Chrome User-Agent, `Accept-Language: pt-BR`, 25 s timeout; returns `None` on non-200 or on a block page (contains "just a moment", "captcha" form, "suspicious"); logs the reason.
  - Each source module: `NAME: str`, `search_url(query: str) -> str`, `parse(html: str) -> list[Offer]` (item left `None`).
  - `radar.sources.ALL: list[module]` = `[kabum, amazon, zoom]`.

Source details:
- **Kabum:** URL `https://www.kabum.com.br/busca/<query with spaces as ->`. JSON in `<script id="__NEXT_DATA__">` → `props.pageProps.data` is a JSON **string** → `catalogServer.data[]`. Price = `offer.priceWithDiscount` if `offer` else `priceWithDiscount`; `old_price` = `oldPrice`; seller = `sellerName`; store "KaBuM!"; skip `available == False`; URL `https://www.kabum.com.br/produto/<code>` (field name of the product code: check the fixture).
- **Amazon:** URL `https://www.amazon.com.br/s?k=<query>`. Each `div[data-component-type="s-search-result"]`: title from `h2`, price from `.a-price .a-offscreen` (fallback `a-price-whole` + `a-price-fraction`), old price from `.a-text-price .a-offscreen`, URL `https://www.amazon.com.br/dp/<data-asin>`. Seller = "Amazon" (search page does not show the seller; Amazon's A-to-z guarantee covers marketplace — decision recorded in spec). Skip cards without price or sponsored ones without ASIN.
- **Zoom:** URL `https://www.zoom.com.br/search?q=<query>`. Each `[data-testid="product-card::card"]`: title `[data-testid="product-card::name"]`, price `[data-testid="product-card::price"]`, seller from the "Via <loja>" text, URL `https://www.zoom.com.br` + card href without query string. Store = seller name.

- [ ] **Step 1: Copy fixtures** into `tests/fixtures/`.
- [ ] **Step 2: Write failing tests:**

```python
def test_parse_brl():
    assert parse_brl("R$ 4.369,05") == 4369.05
    assert parse_brl("R$ 7.799") == 7799.0
    assert parse_brl("10x de R$ 779,90") == 779.90
    assert parse_brl("indisponível") is None

def test_kabum_parse():
    offers = kabum.parse(fixture("kabum.html"))
    assert len(offers) >= 5
    pro = [o for o in offers if "5 Pro" in o.title][0]
    assert pro.price == 7799 and pro.seller == "KaBuM!" and pro.url.startswith("https://www.kabum.com.br/produto/")

def test_amazon_parse():
    offers = amazon.parse(fixture("amazon.html"))
    assert len(offers) >= 5
    assert all(o.price > 100 and "/dp/" in o.url for o in offers)

def test_zoom_parse():
    offers = zoom.parse(fixture("zoom.html"))
    pro = [o for o in offers if o.title == "Playstation 5 Pro 2TB"][0]
    assert pro.price == 7799.0 and pro.seller == "KaBuM!"

def test_fetch_detects_block_page(monkeypatch): ...  # httpx.MockTransport returning 200 with "<title>Just a moment...</title>" → fetch returns None
```

- [ ] **Step 3: Run** `pytest tests/test_sources.py -v` → FAIL.
- [ ] **Step 4: Implement** `parse_brl`, `fetch`, the three source modules.
- [ ] **Step 5: Run** `pytest -v` → PASS.
- [ ] **Step 6: Commit** `feat: kabum, amazon and zoom sources`.

### Task 3: State and cheap-price rules

**Files:**
- Create: `radar/state.py`, `radar/rules.py`
- Test: `tests/test_rules.py`, `tests/test_state.py`

**Interfaces:**
- Consumes: `Offer`, `Config` (Task 1).
- Produces:
  - `radar.state.State` — `history: dict[str, list[tuple[datetime, float]]]`, `alerted: dict[str, float]` (url → price alerted); `State.load(dir: Path) -> State` (missing files → empty), `save(dir: Path)` writes `history.json`, `alerted.json` (ISO timestamps, UTC); `record(item, now, price)`; `prune(now, days)`.
  - `radar.rules.Alert` — dataclass `offer: Offer, reason: str ("teto" | "queda" | "minimo"), reference: float | None, pct: float | None`
  - `radar.rules.check(offer: Offer, history: list[tuple[datetime, float]], now: datetime, cfg: Config, cap: float | None, alerted: dict[str, float]) -> Alert | None`

Rule order: dedup first (`offer.url in alerted and offer.price >= alerted[url]` → None). Then cap (`price <= cap` → "teto"). Then, only if history spans ≥ `warmup_hours` (oldest entry ≤ now − 24 h): median of entries in the last `window_days`; `price <= median * (1 - drop_pct)` → "queda" with `pct = 1 - price/median`; else `price < min(all history)` → "minimo". `history` passed in is BEFORE recording this run.

- [ ] **Step 1: Write failing tests** (`now = datetime(2026,11,24,12,tzinfo=UTC)`, helper builds hourly history):
  - `test_cap_alert`: cap 5000, price 4900, empty history → reason "teto".
  - `test_no_alert_during_warmup`: 10 h of history at 5000, price 3000 → None.
  - `test_drop_alert`: 3 days at 5000, price 4499 → "queda", pct ≈ 0.1002.
  - `test_no_drop_alert_at_9pct`: 3 days at 5000, price 4550 → None.
  - `test_new_minimum`: 3 days at 5000 with one 4700, price 4650 → "minimo".
  - `test_dedup`: alerted `{url: 4499}`, price 4499 → None; price 4400 → Alert.
  - `test_state_roundtrip` and `test_prune_drops_older_than_30_days`.
- [ ] **Step 2: Run** `pytest tests/test_rules.py tests/test_state.py -v` → FAIL.
- [ ] **Step 3: Implement** `State` and `check`.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: price history and cheap rules`.

### Task 4: Telegram message and the run orchestration

**Files:**
- Create: `radar/telegram.py`, `radar/main.py`, `radar/__main__.py`
- Test: `tests/test_main.py`, `tests/test_telegram.py`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces:
  - `radar.telegram.format_alert(alert: Alert, label: str) -> str`
  - `radar.telegram.send(token: str, chat_id: str, text: str, client: httpx.Client | None = None) -> bool` — POST `https://api.telegram.org/bot<token>/sendMessage` with `chat_id`, `text`, `disable_web_page_preview=False`; returns False on any error (never raises; never logs the token).
  - `radar.main.run_once(cfg: Config, state: State, fetch: Callable[[str], str | None], send: Callable[[str], bool], now: datetime, sources=ALL) -> list[Alert]`
  - `python -m radar [--dry-run]` → loads `config.toml`, `data/`, runs once, saves state; `--dry-run` prints messages instead of sending; missing env vars without `--dry-run` → print error, exit 0 without sending.

Message format (pt-BR), example:

```
🔥 PlayStation 5 Pro — R$ 6.899,00
-12% vs. média de 7 dias (R$ 7.799,00)
Loja: KaBuM!
Console PlayStation 5 Pro Sony, SSD 2TB...
https://www.kabum.com.br/produto/...
```
Reason line: "teto" → "Abaixo do seu teto de R$ X"; "minimo" → "Menor preço já visto".

run_once: for each item, each query, each source: `fetch(source.search_url(q))`; `None` → skip; `parse` inside try/except (exception → log, skip). Classify each offer; keep those whose class == item and trusted seller. Cheapest offer per item → `check` → if Alert: `send(format_alert(...))`; mark `alerted[url] = price` only when send returned True. Then `state.record(item, now, cheapest.price)` (only when the item had at least one offer). Finally `state.prune`. Log a one-line summary per source (ok / blocked / error).

- [ ] **Step 1: Write failing tests** with fake `fetch` (maps URL → fixture HTML or None) and fake `send` (records texts, returns configurable bool):
  - `test_run_alerts_cheap_ps5_pro`: history 3 days at 9000 for `ps5_pro`; fixtures → one alert for ps5_pro at 7799 (≥10% below 9000), text contains "R$ 7.799,00" and "KaBuM!".
  - `test_run_survives_failing_source`: fetch returns None for Kabum URLs and a parser raising for Zoom → still runs, no exception, Amazon offers recorded.
  - `test_failed_send_not_marked`: send returns False → `state.alerted` stays empty.
  - `test_no_duplicate_on_second_run`: two consecutive runs with same data → second sends nothing.
  - `test_untrusted_seller_ignored`: Zoom card with "Via Loja do Zé" never alerts.
  - `test_format_alert` for the three reasons.
- [ ] **Step 2: Run** `pytest -v` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest -v` → PASS.
- [ ] **Step 5: Live smoke test:** `python -m radar --dry-run` → per-source summary lines; no traceback. Delete the resulting `data/` changes afterwards (do not commit live data from the dev PC).
- [ ] **Step 6: Commit** `feat: telegram alerts and run orchestration`.

### Task 5: GitHub Actions workflow and setup guide

**Files:**
- Create: `.github/workflows/radar.yml`, `README.md`, `data/.gitkeep`

**Interfaces:**
- Consumes: `python -m radar` (Task 4).

Workflow:
- `on: schedule: - cron: "*/10 * * * *"` and `workflow_dispatch`.
- `concurrency: { group: radar, cancel-in-progress: false }` (two runs must not push at once).
- `permissions: contents: write`.
- Steps: checkout; setup-python 3.12 with pip cache; `pip install .`; `python -m radar` with `TELEGRAM_TOKEN: ${{ secrets.TELEGRAM_TOKEN }}`, `TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}`; commit `data/` if changed as `radar-bot` with message `data: atualiza histórico [skip ci]`, `git pull --rebase` then push.
- A second workflow job or step for tests is NOT needed on the schedule (keep runs short).

README (pt-BR): what it does; step-by-step: create GitHub account/public repo and push; create bot with @BotFather (`/newbot`), create group, add bot, get chat id via `https://api.telegram.org/bot<TOKEN>/getUpdates` after sending a message in the group; add the two Secrets; run once with "Run workflow"; how to set a `cap` in `config.toml`; how to pause (disable workflow).

- [ ] **Step 1: Write** workflow, README, `data/.gitkeep`.
- [ ] **Step 2: Validate YAML** parses: `python -c "import yaml,sys;yaml.safe_load(open('.github/workflows/radar.yml'))"` (install `pyyaml` locally if needed) → no error.
- [ ] **Step 3: Run full test suite** `pytest -v` → PASS.
- [ ] **Step 4: Commit** `ci: scheduled workflow and setup guide`.

"""
Dados simulados para demonstração sem chave de API.
Inclui arbitragens propositalmente para mostrar o sistema funcionando.
"""
import asyncio
import random
from datetime import datetime, timezone, timedelta
from arbitrage.collectors.base import BaseCollector
from arbitrage.models import Event, Odd


# ─────────────────────────────────────────────────────────────────────────────
# Templates de eventos
# ─────────────────────────────────────────────────────────────────────────────
_SOCCER_EVENTS = [
    ("Flamengo", "Palmeiras",      "soccer_brazil_campeonato",  "Campeonato Brasileiro"),
    ("Corinthians", "São Paulo",   "soccer_brazil_campeonato",  "Campeonato Brasileiro"),
    ("Grêmio", "Internacional",    "soccer_brazil_campeonato",  "Campeonato Brasileiro"),
    ("Atlético-MG", "Cruzeiro",    "soccer_brazil_campeonato",  "Campeonato Brasileiro"),
    ("Botafogo", "Fluminense",     "soccer_brazil_campeonato",  "Campeonato Brasileiro"),
    ("Vasco", "Athletico-PR",      "soccer_brazil_campeonato",  "Campeonato Brasileiro"),
    ("Boca Juniors", "River Plate","soccer_conmebol_copa_libertadores", "Copa Libertadores"),
    ("Barcelona SC", "Flamengo",   "soccer_conmebol_copa_libertadores", "Copa Libertadores"),
]

_BASKETBALL_EVENTS = [
    ("Los Angeles Lakers", "Golden State Warriors", "basketball_nba", "NBA"),
    ("Boston Celtics", "Miami Heat",                "basketball_nba", "NBA"),
]

_BOOKMAKERS = [
    ("betano",      "Betano"),
    ("sportingbet", "Sportingbet"),
    ("bet365",      "Bet365"),
    ("1xbet",       "1xBet"),
    ("pinnacle",    "Pinnacle"),
    ("superbet",    "Superbet"),
    ("betsul",      "Betsul"),
    ("kto",         "KTO"),
]


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def _future(hours: float) -> datetime:
    return _now_utc() + timedelta(hours=hours)


def _make_soccer_odds(
    home: str, away: str,
    bookmakers: list[tuple[str, str]],
    arb_pair: tuple[int, int] | None = None,
) -> list[Odd]:
    """
    Gera odds para um jogo de futebol (Home / Draw / Away).
    arb_pair: índices dos bookmakers que formam a arbitragem
    """
    # Probabilidades "verdadeiras" base
    p_home = random.uniform(0.40, 0.55)
    p_draw = random.uniform(0.20, 0.28)
    p_away = 1 - p_home - p_draw

    odds_list: list[Odd] = []
    last_updated = _now_utc()

    for i, (bk_key, bk_title) in enumerate(bookmakers):
        margin = random.uniform(0.04, 0.08)  # margem normal da casa

        if arb_pair and i in arb_pair:
            # Uma das casas dá odd melhor propositalmente para criar arb
            margin = random.uniform(-0.015, -0.005)  # margem negativa = arb

        # Aplicar margem: dividir probabilidades por (1 + margin)
        scale = 1 + margin
        raw_home = p_home * scale
        raw_draw = p_draw * scale
        raw_away = p_away * scale

        o_home = round(1 / raw_home, 2)
        o_draw = round(1 / raw_draw, 2)
        o_away = round(1 / raw_away, 2)

        # Pequena variação aleatória por casa
        jitter = lambda x: round(x * random.uniform(0.97, 1.03), 2)
        o_home = jitter(o_home)
        o_draw = jitter(o_draw)
        o_away = jitter(o_away)

        for outcome, price in [(home, o_home), ("Draw", o_draw), (away, o_away)]:
            odds_list.append(Odd(
                bookmaker=bk_title,
                bookmaker_key=bk_key,
                market="h2h",
                outcome=outcome,
                price=max(price, 1.01),
                last_updated=last_updated,
            ))

    return odds_list


def _make_basketball_odds(
    home: str, away: str,
    bookmakers: list[tuple[str, str]],
    arb_pair: tuple[int, int] | None = None,
) -> list[Odd]:
    """Gera odds para basquete (2-vias, sem empate)."""
    p_home = random.uniform(0.45, 0.60)
    p_away = 1 - p_home
    odds_list: list[Odd] = []
    last_updated = _now_utc()

    for i, (bk_key, bk_title) in enumerate(bookmakers):
        margin = random.uniform(0.04, 0.07)
        if arb_pair and i in arb_pair:
            margin = random.uniform(-0.012, -0.003)

        scale = 1 + margin
        o_home = round(1 / (p_home * scale), 2)
        o_away = round(1 / (p_away * scale), 2)

        jitter = lambda x: round(x * random.uniform(0.97, 1.03), 2)
        o_home, o_away = jitter(o_home), jitter(o_away)

        for outcome, price in [(home, o_home), (away, o_away)]:
            odds_list.append(Odd(
                bookmaker=bk_title,
                bookmaker_key=bk_key,
                market="h2h",
                outcome=outcome,
                price=max(price, 1.01),
                last_updated=last_updated,
            ))

    return odds_list


class MockCollector(BaseCollector):
    """Coletor de dados simulados para demo sem API key."""

    def __init__(self):
        self._call_count = 0

    def name(self) -> str:
        return "Mock (Simulado)"

    async def fetch_events(self) -> list[Event]:
        await asyncio.sleep(0.1)  # simula latência
        self._call_count += 1

        # Ligeira aleatoriedade nas odds a cada chamada (simula movimento de mercado)
        random.seed(self._call_count)

        events: list[Event] = []
        event_id = 0

        # ── Futebol: 8 jogos, 2 com arbitragem garantida ──────────────────
        arb_soccer_indices = {2, 5}  # jogos que terão arb

        for idx, (home, away, sport_key, league) in enumerate(_SOCCER_EVENTS):
            event_id += 1
            arb_pair = (1, 5) if idx in arb_soccer_indices else None
            bks = random.sample(_BOOKMAKERS, k=random.randint(4, 8))

            event = Event(
                event_id=f"mock-soccer-{event_id:03d}",
                sport_key=sport_key,
                sport_title=league,
                league=league,
                home_team=home,
                away_team=away,
                commence_time=_future(random.uniform(1, 72)),
                odds=_make_soccer_odds(home, away, bks, arb_pair=arb_pair),
            )
            events.append(event)

        # ── Basquete: 2 jogos, 1 com arbitragem ───────────────────────────
        for idx, (home, away, sport_key, league) in enumerate(_BASKETBALL_EVENTS):
            event_id += 1
            arb_pair = (0, 3) if idx == 0 else None
            bks = random.sample(_BOOKMAKERS, k=random.randint(3, 6))

            event = Event(
                event_id=f"mock-bball-{event_id:03d}",
                sport_key=sport_key,
                sport_title=league,
                league=league,
                home_team=home,
                away_team=away,
                commence_time=_future(random.uniform(1, 48)),
                odds=_make_basketball_odds(home, away, bks, arb_pair=arb_pair),
            )
            events.append(event)

        return events

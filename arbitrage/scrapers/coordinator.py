"""
Coordinator — executa todos os scrapers em paralelo e funde os eventos.

O ponto crítico de arbitragem: o mesmo jogo aparece em casas diferentes
com nomes de times levemente diferentes (ex: "Flamengo" vs "CR Flamengo").
Usamos normalização de nomes + similaridade para agrupar o mesmo evento.

Resultado final: uma lista de Event onde cada evento pode conter odds
de MÚLTIPLAS casas de apostas, permitindo detectar arbitragem cross-bookmaker.
"""
import asyncio
import logging
import re
import unicodedata
from collections import defaultdict

import httpx

from arbitrage.scrapers.base import BaseScraper
from arbitrage.scrapers.pinnacle             import PinnacleScraper
from arbitrage.scrapers.betano               import BetanoScraper
from arbitrage.scrapers.onexbet              import OneXBetScraper
from arbitrage.scrapers.sportingbet          import SportingbetScraper
from arbitrage.scrapers.superbet             import SuperbetScraper
from arbitrage.scrapers.betsul               import BetsulScraper
from arbitrage.scrapers.playwright_betano    import PlaywrightBetanoScraper
from arbitrage.scrapers.playwright_sportingbet import PlaywrightSportingbetScraper
from arbitrage.scrapers.playwright_superbet  import PlaywrightSuperbetScraper
from arbitrage.models import Event

logger = logging.getLogger(__name__)

# Scrapers httpx (rápidos, sem browser — funcionam para Pinnacle, 1xBet, Betsul)
_HTTP_SCRAPERS: list[BaseScraper] = [
    PinnacleScraper(),
    BetanoScraper(),       # fallback httpx para Betano
    OneXBetScraper(),
    SportingbetScraper(),  # fallback httpx para Sportingbet
    SuperbetScraper(),     # fallback httpx para Superbet
    BetsulScraper(),
]

# Scrapers Playwright (browser real — para sites com Cloudflare: Betano, Sportingbet, Superbet)
_PLAYWRIGHT_SCRAPERS: list = [
    PlaywrightBetanoScraper(),
    PlaywrightSportingbetScraper(),
    PlaywrightSuperbetScraper(),
]

# Por padrão usa httpx. Playwright é ativado com USE_PLAYWRIGHT=true no .env
import os as _os
_USE_PLAYWRIGHT = _os.getenv("USE_PLAYWRIGHT", "false").lower() == "true"

ALL_SCRAPERS: list[BaseScraper] = _HTTP_SCRAPERS

# ─────────────────────────────────────────────────────────────────────────────
# Normalização de nomes de times
# ─────────────────────────────────────────────────────────────────────────────

# Mapeamentos de nomes alternativos → nome canônico
_TEAM_ALIASES: dict[str, str] = {
    # Futebol brasileiro
    "cr flamengo":          "Flamengo",
    "flamengo rj":          "Flamengo",
    "clube de regatas flamengo": "Flamengo",
    "cr fluminense":        "Fluminense",
    "fluminense fc":        "Fluminense",
    "sport club corinthians paulista": "Corinthians",
    "corinthians paulista": "Corinthians",
    "sociedade esportiva palmeiras": "Palmeiras",
    "se palmeiras":         "Palmeiras",
    "sao paulo fc":         "São Paulo",
    "sao paulo":            "São Paulo",
    "atletico mg":          "Atlético-MG",
    "atletico mineiro":     "Atlético-MG",
    "clube atletico mineiro": "Atlético-MG",
    "atletico-mg":          "Atlético-MG",
    "cruzeiro ec":          "Cruzeiro",
    "gremio fbpa":          "Grêmio",
    "gremio":               "Grêmio",
    "internacional rs":     "Internacional",
    "sc internacional":     "Internacional",
    "sport club internacional": "Internacional",
    "vasco da gama":        "Vasco",
    "cr vasco da gama":     "Vasco",
    "botafogo rj":          "Botafogo",
    "botafogo fr":          "Botafogo",
    "botafogo de futebol e regatas": "Botafogo",
    "athletico paranaense": "Athletico-PR",
    "athletico-pr":         "Athletico-PR",
    "ca paranaense":        "Athletico-PR",
    "club atletico paranaense": "Athletico-PR",
    "boca juniors":         "Boca Juniors",
    "ca boca juniors":      "Boca Juniors",
    "river plate":          "River Plate",
    "ca river plate":       "River Plate",
    # NBA
    "la lakers":            "Los Angeles Lakers",
    "la clippers":          "Los Angeles Clippers",
    "gs warriors":          "Golden State Warriors",
    "golden state":         "Golden State Warriors",
    "ny knicks":            "New York Knicks",
    "new york":             "New York Knicks",
    "boston":               "Boston Celtics",
    "miami":                "Miami Heat",
    "chicago":              "Chicago Bulls",
}


def _normalize(name: str) -> str:
    """Remove acentos, lowercasing, strip, colapsa espaços."""
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = name.lower().strip()
    name = re.sub(r"\s+", " ", name)
    # Remove sufixos comuns: FC, SC, CF, AC, CA, EC, SL, CD, UD, RJ, SP, MG...
    name = re.sub(r"\b(fc|sc|cf|ac|ca|ec|sl|cd|ud|rj|sp|mg|rs|pr|ba|ce|pe)\b", "", name).strip()
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _canonical(name: str) -> str:
    """Retorna nome canônico se existir alias, senão retorna normalizado."""
    norm = _normalize(name)
    return _TEAM_ALIASES.get(norm, name.strip())


def _match_key(home: str, away: str) -> str:
    """Chave de agrupamento: nomes canônicos ordenados para encontrar o mesmo jogo."""
    h = _normalize(_canonical(home))
    a = _normalize(_canonical(away))
    # Ordena para que (A vs B) e (B vs A) não sejam chaves diferentes
    # mas preserva quem é home/away para o mercado
    return f"{h}|||{a}"


def _teams_similar(a: str, b: str, threshold: float = 0.75) -> bool:
    """Verifica se dois nomes de time são provavelmente o mesmo."""
    na, nb = _normalize(_canonical(a)), _normalize(_canonical(b))
    if na == nb:
        return True
    # Um contém o outro
    if na in nb or nb in na:
        return True
    # Similaridade simples por tokens comuns
    tokens_a = set(na.split())
    tokens_b = set(nb.split())
    if not tokens_a or not tokens_b:
        return False
    overlap = len(tokens_a & tokens_b) / max(len(tokens_a), len(tokens_b))
    return overlap >= threshold


# ─────────────────────────────────────────────────────────────────────────────
# Fusão de eventos cross-bookmaker
# ─────────────────────────────────────────────────────────────────────────────

def _merge_events(all_events: list[Event]) -> list[Event]:
    """
    Agrupa eventos do mesmo jogo (vindos de diferentes casas) em um único
    Event com odds de todas as casas. Esse é o passo que permite detectar
    arbitragem cross-bookmaker.
    """
    # Agrupa por chave (home|||away normalizado)
    groups: dict[str, list[Event]] = defaultdict(list)
    for ev in all_events:
        key = _match_key(ev.home_team, ev.away_team)
        groups[key].append(ev)

    merged: list[Event] = []
    for key, evs in groups.items():
        if not evs:
            continue

        # Evento de referência = o que tiver mais odds (geralmente Pinnacle)
        base = max(evs, key=lambda e: len(e.odds))

        # Coleta todas as odds de todos os eventos do grupo
        all_odds = []
        for ev in evs:
            all_odds.extend(ev.odds)

        # Normaliza nomes de outcomes para usar o home/away do evento base
        normalized_odds = []
        for odd in all_odds:
            outcome = odd.outcome
            if outcome == "Draw":
                pass  # mantém
            elif _teams_similar(outcome, base.home_team):
                outcome = base.home_team
            elif _teams_similar(outcome, base.away_team):
                outcome = base.away_team
            # Se não casou com nenhum, mantém original (pode ser Draw em outro idioma)
            normalized_odds.append(odd.__class__(
                bookmaker=odd.bookmaker,
                bookmaker_key=odd.bookmaker_key,
                market=odd.market,
                outcome=outcome,
                price=odd.price,
                last_updated=odd.last_updated,
            ))

        # Usa o commence_time mais cedo entre todos (mais provável ser correto)
        earliest = min(evs, key=lambda e: e.commence_time)

        merged.append(Event(
            event_id=base.event_id,
            sport_key=base.sport_key,
            sport_title=base.sport_title,
            league=base.league,
            home_team=base.home_team,
            away_team=base.away_team,
            commence_time=earliest.commence_time,
            odds=normalized_odds,
        ))

    return sorted(merged, key=lambda e: e.commence_time)


# ─────────────────────────────────────────────────────────────────────────────
# Coordinator
# ─────────────────────────────────────────────────────────────────────────────

class ScraperCoordinator:
    """
    Executa todos os scrapers em paralelo e retorna eventos fundidos.
    Scrapers que falham são ignorados silenciosamente (graceful degradation).
    """

    def __init__(self, scrapers: list[BaseScraper] | None = None, playwright_scrapers: list | None = None):
        self.scrapers = scrapers or ALL_SCRAPERS
        self.playwright_scrapers = playwright_scrapers  # None = usa _PLAYWRIGHT_SCRAPERS
        self._success_count: dict[str, int] = {}
        self._fail_count: dict[str, int] = {}

    def name(self) -> str:
        names = [s.bookmaker_name for s in self.scrapers]
        return "Scrapers: " + ", ".join(names)

    @property
    def requests_remaining(self) -> int:
        return -1  # ilimitado (sem cota de API)

    async def fetch_events(self) -> list[Event]:
        """
        Roda scrapers httpx em paralelo.
        Se USE_PLAYWRIGHT=true, também roda os scrapers Playwright para
        Betano, Sportingbet e Superbet (que têm Cloudflare).
        """
        all_events: list[Event] = []

        # ── Scrapers httpx (paralelos) ────────────────────────────────────────
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=20.0,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        ) as client:
            tasks = [self._run_http_scraper(s, client) for s in self.scrapers]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        for scraper, result in zip(self.scrapers, results):
            if isinstance(result, Exception):
                self._fail_count[scraper.bookmaker_key] = self._fail_count.get(scraper.bookmaker_key, 0) + 1
                logger.warning("Scraper httpx %s falhou: %s", scraper.bookmaker_name, result)
            elif isinstance(result, list):
                self._success_count[scraper.bookmaker_key] = len(result)
                all_events.extend(result)
                logger.info("Scraper httpx %s: %d eventos", scraper.bookmaker_name, len(result))

        # ── Scrapers Playwright (opcionais, sequenciais por site) ─────────────
        if _USE_PLAYWRIGHT:
            pw_scrapers = self.playwright_scrapers or _PLAYWRIGHT_SCRAPERS
            for s in pw_scrapers:
                try:
                    evs = await s.fetch_events()
                    if evs:
                        self._success_count[s.bookmaker_key + "_pw"] = len(evs)
                        all_events.extend(evs)
                        logger.info("Scraper PW %s: %d eventos", s.bookmaker_name, len(evs))
                except Exception as e:
                    logger.warning("Scraper PW %s falhou: %s", s.bookmaker_name, e)

        return _merge_events(all_events)

    async def _run_http_scraper(self, scraper: BaseScraper, client: httpx.AsyncClient) -> list[Event]:
        try:
            return await scraper.fetch_events(client)
        except Exception as e:
            logger.debug("Erro no scraper %s: %s", scraper.bookmaker_name, e)
            return []

    def stats(self) -> dict:
        return {
            "success": self._success_count,
            "failures": self._fail_count,
        }

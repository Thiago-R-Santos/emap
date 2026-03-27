"""
Betano Brasil — API interna JSON.

A Betano usa a plataforma Kaizen Gaming. O frontend consome uma API REST
interna que retorna JSON. Os endpoints são descobertos via DevTools (Network tab).

Estrutura principal:
  GET /api/sports/                → lista de esportes com slugs
  GET /api/sports/{slug}/regions/ → regiões/ligas
  GET /api/sports/{slug}/regions/{region}/leagues/{league}/events/
      ?lang=pt&version=2.0        → eventos com odds incluídas
"""
import logging
from datetime import datetime, timezone

import httpx

from arbitrage.scrapers.base import BaseScraper, _browser_headers, _get_json, utc_now
from arbitrage.models import Event, Odd

logger = logging.getLogger(__name__)

_BASE = "https://br.betano.com"
_REFERER = "https://br.betano.com/"

# Slugs de esportes + regiões/ligas monitoradas
# Formato: (sport_slug, region_slug, league_slug, display_name)
_LEAGUES = [
    ("futebol", "brasil",     "campeonato-brasileiro-serie-a",   "Campeonato Brasileiro"),
    ("futebol", "brasil",     "campeonato-brasileiro-serie-b",   "Brasileirão Série B"),
    ("futebol", "brasil",     "copa-do-brasil",                  "Copa do Brasil"),
    ("futebol", "america-do-sul", "copa-libertadores",           "Copa Libertadores"),
    ("futebol", "america-do-sul", "copa-sul-americana",          "Copa Sudamericana"),
    ("futebol", "europa",     "premier-league",                  "Premier League"),
    ("futebol", "europa",     "la-liga",                         "La Liga"),
    ("futebol", "europa",     "champions-league",                "Champions League"),
    ("basquete", "eua",       "nba",                             "NBA"),
]


def _parse_dt(value: str | int | None) -> datetime:
    if not value:
        return utc_now()
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return utc_now()


class BetanoScraper(BaseScraper):
    REQUEST_DELAY = 1.5

    @property
    def bookmaker_key(self) -> str:
        return "betano"

    @property
    def bookmaker_name(self) -> str:
        return "Betano"

    async def fetch_events(self, client: httpx.AsyncClient) -> list[Event]:
        events: list[Event] = []
        headers = _browser_headers(referer=_REFERER, extra={
            "X-Requested-With": "XMLHttpRequest",
            "Origin": _BASE,
        })

        for sport, region, league, display in _LEAGUES:
            url = f"{_BASE}/api/sports/{sport}/regions/{region}/leagues/{league}/events/"
            data = await _get_json(client, url, params={"lang": "pt", "version": "2.0"}, headers=headers)

            if not data:
                # Tenta endpoint alternativo mais genérico
                url2 = f"{_BASE}/api/sports/{sport}/leagues/{league}/events/"
                data = await _get_json(client, url2, params={"lang": "pt"}, headers=headers)

            if data:
                parsed = self._parse_response(data, display, sport)
                events.extend(parsed)

            import asyncio
            await asyncio.sleep(self.REQUEST_DELAY)

        return events

    def _parse_response(self, data: dict | list, league_display: str, sport_slug: str) -> list[Event]:
        # Betano retorna estrutura variável: às vezes data["data"], às vezes lista direta
        if isinstance(data, dict):
            events_raw = (
                data.get("data", {}).get("events")
                or data.get("events")
                or data.get("data")
                or []
            )
        else:
            events_raw = data

        if not isinstance(events_raw, list):
            return []

        result: list[Event] = []
        sport_title_map = {"futebol": "Futebol", "basquete": "Basquete", "tenis": "Tênis"}
        sport_title = sport_title_map.get(sport_slug, sport_slug.title())

        for ev in events_raw:
            try:
                home = ev.get("home_team") or ev.get("home", {}).get("name", "")
                away = ev.get("away_team") or ev.get("away", {}).get("name", "")
                eid  = str(ev.get("id") or ev.get("event_id", ""))
                start = _parse_dt(ev.get("start_time") or ev.get("startTime") or ev.get("date"))

                if not home or not away:
                    continue

                odds: list[Odd] = []

                # Mercados podem estar em .markets[] ou .odds[] dependendo da versão
                markets = ev.get("markets") or ev.get("odds") or []
                for market in markets:
                    market_type = market.get("market_type") or market.get("type") or ""
                    # Foco em moneyline (1X2 ou ML)
                    if market_type not in ("", "1", "1x2", "ml", "moneyline", "match_result", "h2h"):
                        if "1x2" not in str(market_type).lower() and "moneyline" not in str(market_type).lower():
                            continue

                    selections = market.get("selections") or market.get("outcomes") or []
                    for sel in selections:
                        name  = sel.get("name") or sel.get("outcome") or ""
                        price = sel.get("odds") or sel.get("price") or sel.get("odd") or 0
                        try:
                            price = float(price)
                        except (TypeError, ValueError):
                            continue

                        # Normaliza nomes
                        name_lower = str(name).lower()
                        if name_lower in ("empate", "draw", "x"):
                            outcome = "Draw"
                        elif name_lower in ("1", "casa", "home") or name.lower() == home.lower():
                            outcome = home
                        elif name_lower in ("2", "fora", "away") or name.lower() == away.lower():
                            outcome = away
                        else:
                            outcome = name  # mantém original

                        if price > 1.0:
                            odds.append(Odd(
                                bookmaker=self.bookmaker_name,
                                bookmaker_key=self.bookmaker_key,
                                market="h2h",
                                outcome=outcome,
                                price=round(price, 3),
                                last_updated=utc_now(),
                            ))

                if len(odds) >= 2:
                    result.append(Event(
                        event_id=f"betano-{eid}",
                        sport_key=sport_slug,
                        sport_title=sport_title,
                        league=league_display,
                        home_team=home,
                        away_team=away,
                        commence_time=start,
                        odds=odds,
                    ))

            except Exception as e:
                logger.debug("Betano: erro ao parsear evento: %s", e)
                continue

        return result

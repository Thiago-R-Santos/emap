"""
Sportingbet Brasil — API interna (plataforma SBTech).

A Sportingbet usa a plataforma SBTech (mesmo motor do Bet365 em alguns mercados).
A API interna retorna JSON com eventos e odds.

Endpoint principal:
  GET https://sports.sportingbet.com/en/sports/api/
      ?categoryId={catId}&subcategoryId={subcatId}&marketTypeId=1&limit=100

CategoryIds relevantes:
  6601 = Futebol (Brasileirão etc.)
  6602 = Basquete
"""
import asyncio
import logging

import httpx

from arbitrage.scrapers.base import BaseScraper, _browser_headers, _get_json, utc_now
from arbitrage.models import Event, Odd
from arbitrage.scrapers.betano import _parse_dt

logger = logging.getLogger(__name__)

_BASE = "https://sports.sportingbet.com"
_REFERER = "https://www.sportingbet.com/pt-br/sports"

# (category_id, subcategory_id, display_name)
_LEAGUES = [
    (6601, 46, "Campeonato Brasileiro"),
    (6601, 47, "Copa do Brasil"),
    (6601, 48, "Copa Libertadores"),
    (6601, 49, "Copa Sudamericana"),
    (6601, 1,  "Premier League"),
    (6602, 1,  "NBA"),
]


class SportingbetScraper(BaseScraper):
    REQUEST_DELAY = 1.5

    @property
    def bookmaker_key(self) -> str:
        return "sportingbet"

    @property
    def bookmaker_name(self) -> str:
        return "Sportingbet"

    async def fetch_events(self, client: httpx.AsyncClient) -> list[Event]:
        events: list[Event] = []
        headers = _browser_headers(referer=_REFERER, extra={"Origin": "https://www.sportingbet.com"})

        for cat_id, subcat_id, display in _LEAGUES:
            # Endpoint SBTech padrão
            data = await _get_json(
                client,
                f"{_BASE}/en/sports/api/",
                params={
                    "categoryId": cat_id,
                    "subcategoryId": subcat_id,
                    "marketTypeId": 1,   # 1 = moneyline / 1X2
                    "limit": 100,
                    "lng": "pt",
                },
                headers=headers,
            )

            if not data:
                # Fallback: endpoint alternativo
                data = await _get_json(
                    client,
                    f"{_BASE}/pt-br/sports/futebol/api/events",
                    params={"leagueId": subcat_id, "marketType": "1x2"},
                    headers=headers,
                )

            if data:
                parsed = self._parse_response(data, display)
                events.extend(parsed)

            await asyncio.sleep(self.REQUEST_DELAY)

        return events

    def _parse_response(self, data: dict | list, league_display: str) -> list[Event]:
        if isinstance(data, dict):
            events_raw = (
                data.get("events") or data.get("Events")
                or data.get("data", {}).get("events", [])
                or []
            )
        else:
            events_raw = data

        result: list[Event] = []
        for ev in events_raw:
            try:
                home = (
                    ev.get("HomeTeam") or ev.get("home_team")
                    or ev.get("home", {}).get("name", "")
                )
                away = (
                    ev.get("AwayTeam") or ev.get("away_team")
                    or ev.get("away", {}).get("name", "")
                )
                eid  = str(ev.get("Id") or ev.get("id") or ev.get("EventId", ""))
                start = _parse_dt(
                    ev.get("EventDate") or ev.get("start_time") or ev.get("startTime")
                )

                if not home or not away:
                    continue

                odds: list[Odd] = []
                markets = ev.get("Markets") or ev.get("markets") or []
                for market in markets:
                    market_name = str(market.get("Name") or market.get("name") or "").lower()
                    if not any(k in market_name for k in ("1x2", "moneyline", "resultado", "vencedor", "handicap 0")):
                        if market.get("MarketTypeId") not in (1, None):
                            continue

                    selections = market.get("Selections") or market.get("selections") or []
                    for sel in selections:
                        name  = sel.get("Name") or sel.get("name") or ""
                        price = sel.get("Price") or sel.get("price") or sel.get("Odds") or 0
                        try:
                            price = float(price)
                        except (TypeError, ValueError):
                            continue
                        if price <= 1.0:
                            continue

                        name_l = str(name).lower()
                        if name_l in ("empate", "draw", "x", "1x2-x"):
                            outcome = "Draw"
                        elif name_l in ("1", "casa") or name.lower() == home.lower():
                            outcome = home
                        elif name_l in ("2", "fora") or name.lower() == away.lower():
                            outcome = away
                        else:
                            outcome = name

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
                        event_id=f"sportingbet-{eid}",
                        sport_key="soccer" if "Futebol" in league_display or "Copa" in league_display else "basketball",
                        sport_title="Futebol" if "Copa" in league_display or "Brasileiro" in league_display else "Esportes",
                        league=league_display,
                        home_team=home,
                        away_team=away,
                        commence_time=start,
                        odds=odds,
                    ))

            except Exception as e:
                logger.debug("Sportingbet: erro ao parsear evento: %s", e)
                continue

        return result
